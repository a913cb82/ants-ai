"""Training dashboard: key stats, population, games, replay links.

Stdlib only. Serves a live page over HTTP so it works from a Windows
browser against WSL (open http://localhost:PORT; WSL2 forwards
localhost automatically). Polls the archive; no restart needed between
generations.

  .venv/bin/python ml/dashboard.py [--port 8080] [--archive ml/archive]

Routes: / (page), /api/snapshot (everything as JSON),
/api/games?member=&limit=&offset= (game index slice + total),
/replay?f=<archive-relative replay> (visualizer page, new tab per link),
/static/v/<path> (visualizer js/data/img).
"""

from __future__ import annotations

import argparse
import functools
import html
import json
import math
import os
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

import archive
import selfplay

VIS_DIR = ROOT / "tools" / "visualizer"
TEMPLATE = (VIS_DIR / "replay.html.template").read_text()

_nash_cache: dict = {}
def _memo(cache: dict, key, thunk):
    """One-slot memo: recompute only when the key changes."""
    if cache.get("key") != key:
        cache.clear()
        cache["key"] = key
        cache["value"] = thunk()
    return cache["value"]


_games_cache: dict = {}
_grouped_cache: dict = {}


def cached_games(base: Path) -> list[dict]:
    """Parsed games.jsonl, re-parsed only when the file changes.

    snapshot() and /api/games share one parse per poll cycle."""
    path = base / "games.jsonl"
    try:
        st = path.stat()
    except OSError:
        return []
    return _memo(
        _games_cache,
        (str(base.resolve()), st.st_mtime_ns, st.st_size),
        lambda: archive.list_games(base),
    )


def cached_grouped(base: Path) -> list[dict]:
    """Pair rows -> per-game dicts, re-grouped only when games.jsonl
    changes. Grouping 80k rows costs ~1.5s; snapshot polls every few
    seconds, so this shares one grouping per file version like
    cached_games shares one parse."""
    path = base / "games.jsonl"
    try:
        st = path.stat()
    except OSError:
        return []
    return _memo(
        _grouped_cache,
        (str(base.resolve()), st.st_mtime_ns, st.st_size),
        lambda: group_games(cached_games(base)),
    )


_digest_cache: dict = {}


def _eval_digest(base: Path) -> tuple:
    """Cache key that ignores train-only churn (Nash/BT read eval only).

    The matrix file (~1MB) is stat-checked first: unchanged mtime+size
    reuses the last digest, so Nash and BT each cost one read per poll
    instead of one read+dump each."""
    path = base / "matrix.json"
    try:
        st = path.stat()
    except OSError:
        return (None, None)
    key = (str(base.resolve()), st.st_mtime_ns, st.st_size)
    if _digest_cache.get("key") == key:
        return _digest_cache["value"]
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return (None, None)
    digest = (tuple(data.get("ids", [])),
              json.dumps(data.get("eval", {}), sort_keys=True))
    _digest_cache["key"] = key
    _digest_cache["value"] = digest
    return digest


_history_cache: dict = {}


def cached_history(base: Path) -> list[dict]:
    """Parsed history.jsonl, re-parsed only when the file changes.

    snapshot() runs on every page poll; without this each poll re-reads
    ~12MB of generation summaries."""
    path = base / "history.jsonl"
    try:
        st = path.stat()
    except OSError:
        return []
    return _memo(
        _history_cache,
        (str(base.resolve()), st.st_mtime_ns, st.st_size),
        lambda: selfplay.read_history(base),
    )


SNAPSHOT_FILES = ("games.jsonl", "history.jsonl", "matrix.json")


def archive_mtime(base: Path) -> int:
    """Newest mtime (ns) across the polled archive files, 0 when absent.

    snapshot() exposes this as `mtime`; /api/snapshot?since= short-circuits
    against it (P0-2) so idle polls cost three stats, not a 1.8MB dump."""
    latest = 0
    for name in SNAPSHOT_FILES:
        try:
            latest = max(latest, (base / name).stat().st_mtime_ns)
        except OSError:
            continue
    return latest


def is_fresh(base: Path, since) -> bool:
    """True when `since` (an mtime ns from a prior snapshot) covers the
    current archive state: nothing to re-send."""
    try:
        stamp = int(since)
    except (TypeError, ValueError):
        return False
    now = archive_mtime(base)
    return now > 0 and stamp >= now


PAGE_SIZE = 100  # client-side table pages (P0-3): no new endpoints


def page_slice(rows: list, page: int, per: int = PAGE_SIZE) -> list:
    """One page of a client-paginated table. Pure so tests pin it; the
    page mirrors this slicing in JS from the held snapshot."""
    if page < 0:
        page = 0
    return rows[page * per:(page + 1) * per]


def filter_generations(gens: list[dict], member: str) -> list[dict]:
    """Member-aware generations filter (P1-3): challenger OR champion.
    Empty member passes everything through."""
    if not member:
        return list(gens)
    return [g for g in gens
            if g.get("id") == member or g.get("champion") == member]


def _rnd(x, nd: int):
    """Round JSON numbers server-side (P0-2/P1-5); pass anything else
    through untouched."""
    return round(x, nd) if isinstance(x, (int, float)) else x


def _split_pair(key: str, pos: dict) -> tuple[int, int] | None:
    """Indexes of an eval-matrix 'a vs b' key. Tries every split so ids
    containing ' vs ' still resolve; unknown ids return None."""
    parts = key.split(" vs ")
    for k in range(1, len(parts)):
        a, b = " vs ".join(parts[:k]), " vs ".join(parts[k:])
        if a in pos and b in pos:
            return pos[a], pos[b]
    return None


def _nash_cached(base: Path) -> dict:
    """Fictitious play is O(iters*n^2): redo only when eval data changes."""
    key = (str(base.resolve()), _eval_digest(base))
    return _memo(_nash_cache, key, lambda: _sparse_nash(base))


def _sparse_nash(base: Path, iters: int = 2000) -> dict[str, float]:
    """Fictitious play with the same result as archive.nash_mixture.

    The dense version matvecs a 1216x1216 numpy matrix 4000 times (~90%
    of cold first-load). The eval matrix is ~99.8% Laplace-prior zeros
    (unplayed pairs read as exactly 0.5-0.5=0), so each iteration walks
    only the few thousand played entries. Best responses use pre-update
    averages with first-index-wins ties, values reuse archive's exact
    mine/total-0.5 formula in ascending-index order, and the all-zero
    shortcut matches np.any (NaN counts, -0.0 does not): output is
    bit-identical to archive.nash_mixture on the 1200-gen archive,
    ~25x faster, with no new dependencies."""
    data = json.loads((base / "matrix.json").read_text())
    ids = data["ids"]
    n = len(ids)
    if not n:
        return {}
    pos = {cid: i for i, cid in enumerate(ids)}
    ev = data["eval"]
    rows: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    seen: set[tuple[int, int]] = set()
    any_nonzero = False
    for key, w in ev.items():
        pair = _split_pair(key, pos)
        if pair is None:
            continue
        i, j = pair
        if i == j or (j, i) in seen:
            continue
        seen.add((i, j))
        wba = ev.get(f"{ids[j]} vs {ids[i]}", [0.0, 0.0])
        mine = w[0] + wba[1] + 1.0
        theirs = w[1] + wba[0] + 1.0
        total = mine + theirs
        vij = mine / total - 0.5
        vji = theirs / total - 0.5
        if vij != 0.0 or vji != 0.0:
            any_nonzero = True
        rows[i].append((j, vij))
        rows[j].append((i, vji))
    if not any_nonzero:
        return {cid: round(1.0 / n, 4) for cid in ids}  # all draws: split evenly
    for r in rows:
        r.sort()
    trips = [(i, j, v) for i, r in enumerate(rows) for (j, v) in r]
    avg_r = [1.0 / n] * n
    avg_c = [1.0 / n] * n
    strat_r = [0] * n
    strat_c = [0] * n
    total_r = 0
    total_c = 0
    for _ in range(iters):
        best = 0
        best_val = None
        for i, r in enumerate(rows):
            s = 0.0
            for j, v in r:
                s += v * avg_c[j]
            if best_val is None or s > best_val:
                best_val = s
                best = i
        br_r = best
        col = [0.0] * n
        for i, j, v in trips:
            a = avg_r[i]
            if a:
                col[j] += v * a
        br_c = 0
        best_val = col[0]
        for j in range(1, n):
            if col[j] < best_val:
                best_val = col[j]
                br_c = j
        strat_r[br_r] += 1
        total_r += 1
        inv = 1.0 / total_r
        for i, c in enumerate(strat_r):
            avg_r[i] = c * inv
        strat_c[br_c] += 1
        total_c += 1
        inv = 1.0 / total_c
        for i, c in enumerate(strat_c):
            avg_c[i] = c * inv
    return {cid: (avg_r[i] + avg_c[i]) / 2 for i, cid in enumerate(ids)}


# ---------------------------------------------------------------- DATA


def rank_of(scores: list) -> list[int]:
    """Per-seat rank with the engine's formula (tools/engine.py): each seat
    takes the index of its score in the descending sort, so ties share a
    rank and the next rank skips ([10,10,5] -> [0,0,2])."""
    ordered = sorted(scores, reverse=True)
    return [ordered.index(s) for s in scores]


def _fallback_game_key(replay) -> str:
    """Per-game key for rows logged before the `game` id existed: every
    pair of one play shares its replay path, so the game directory (or the
    raw path when it has no /logs/ suffix) groups them back together."""
    text = replay if isinstance(replay, str) else str(replay)
    suffix = "/logs/0.replay"
    return text[:-len(suffix)] if text.endswith(suffix) else text


def game_key_of(row: dict) -> str:
    """Grouping key: the explicit per-play id when present, else the
    replay-derived fallback (covers all pre-id history)."""
    return row.get("game") or _fallback_game_key(row.get("replay", ""))


def _norm_row(row: dict) -> tuple:
    """Order-independent pair identity + aligned scores. Self-pairs sort
    their two scores so (X,X,2,3) and (X,X,3,2) dedupe: one unordered
    seat-pair, one logical row."""
    a, b, sa, sb = row["a"], row["b"], row["score_a"], row["score_b"]
    if a == b:
        return (a, b, min(sa, sb), max(sa, sb))
    if a <= b:
        return (a, b, sa, sb)
    return (b, a, sb, sa)


def _realize(normed: list[tuple]) -> list[list] | None:
    """Assign pair rows to numbered seat positions, fewest possible.

    Returns [[id, score], ...] in first-seen order, or None when the rows
    cannot share one game. Members drawn into several seats (mixture
    sampling is with replacement) get one position each; a repeated
    unordered seat-pair with different scores forces either extra seats
    or, failing that, a split by partition_group."""
    best: list | None = None

    def dfs(k: int, positions: list, used: set) -> None:
        nonlocal best
        if best is not None and len(positions) >= len(best):
            return
        if k == len(normed):
            if best is None or len(positions) < len(best):
                best = [list(p) for p in positions]
            return
        lo, hi, slo, shi = normed[k]
        if lo == hi and slo == shi:
            pairs = [ (i, i) for i, p in enumerate(positions)
                      if p[0] == lo and p[1] in (None, slo)]
            pairs.append(("new", "new"))
        else:
            pairs = []
            pa_list = [i for i, p in enumerate(positions)
                       if p[0] == lo and p[1] in (None, slo)] + ["new"]
            for pa in pa_list:
                pb_list = [i for i, p in enumerate(positions)
                           if i != pa and p[0] == hi
                           and p[1] in (None, shi)] + ["new"]
                for pb in pb_list:
                    pairs.append((pa, pb))
        for pa, pb in pairs:
            pos = [list(p) for p in positions]
            if pa == "new":
                pa = len(pos)
                pos.append([lo, None])
            if pb == "new":
                pb = len(pos)
                pos.append([hi, None])
            if pos[pa][1] is None:
                pos[pa][1] = slo
            if pos[pb][1] is None:
                pos[pb][1] = shi
            key = (min(pa, pb), max(pa, pb))
            if key in used:
                continue
            dfs(k + 1, pos, used | {key})

    dfs(0, [], set())
    return best


def _partition_exact(uniq: list[tuple]) -> list[list[tuple]]:
    """Best set partition: fewest total seat positions wins; ties split
    toward more games (a re-run collision costs 2+2 = 4 either way, while
    a true N-player game always merges strictly cheaper)."""
    n = len(uniq)
    realize: dict[int, int] = {}

    def cost(mask_rows: tuple) -> int:
        key = hash(mask_rows)
        if key not in realize:
            got = _realize(list(mask_rows))
            realize[key] = len(got) if got is not None else 10 ** 9
        return realize[key]

    best_assign: list[int] | None = None
    best_cost = (10 ** 9, 0)

    def rec(i: int, cur: list[int], mx: int) -> None:
        nonlocal best_assign, best_cost
        if i == n:
            blocks: dict[int, list] = {}
            for idx, b in enumerate(cur):
                blocks.setdefault(b, []).append(uniq[idx])
            total = sum(cost(tuple(b)) for b in blocks.values())
            key = (total, -len(blocks))
            if key < best_cost:
                best_cost = key
                best_assign = list(cur)
            return
        for b in range(mx + 1):
            cur.append(b)
            rec(i + 1, cur, mx)
            cur.pop()
        cur.append(mx + 1)
        rec(i + 1, cur, mx + 1)
        cur.pop()

    rec(0, [], -1)
    blocks = {}
    for idx, b in enumerate(best_assign or []):
        blocks.setdefault(b, []).append(uniq[idx])
    return [blocks[b] for b in sorted(blocks)]


def _partition_greedy(uniq: list[tuple]) -> list[list[tuple]]:
    """Best-effort split for pathological groups (>6 rows; all real
    history is <= 6): earliest block whose seat count would not grow,
    else a new block. Deterministic."""
    blocks: list[list[tuple]] = []
    for r in uniq:
        for b in blocks:
            before = _realize(b)
            after = _realize(b + [r])
            if after is not None and before is not None \
                    and len(after) <= len(before):
                b.append(r)
                break
        else:
            blocks.append([r])
    return blocks


def partition_group(normed: list[tuple]) -> list[list[tuple]]:
    """Split normalized pair rows into per-game blocks: exact-duplicate
    rows merge, conflicting re-runs of one replay path split (see
    _partition_exact), duplicate-seat games stay whole."""
    uniq = list(dict.fromkeys(normed))  # dedupe, first-seen order
    if not uniq:
        return []
    if len(uniq) <= 6:
        return _partition_exact(uniq)
    return _partition_greedy(uniq)


def build_game(gen: str, kind: str, map: str | None, replay: str,
               items: list[tuple[tuple, dict]]) -> dict | None:
    """One visual game from a consistent block: every seat with score,
    rank, margin vs field-best, effective points and outcome; the pair
    rows as detail. None when the block cannot be one game."""
    pos = _realize([n for n, _ in items])
    if pos is None:
        return None
    # Seat order follows the logged field order (seat 0 first), not the
    # normalized pair order: eval seats 0/1 are challenger/champion and the
    # page/tally read the default view off seats[0]. Duplicate-seat
    # positions share an id, so key on (id, score) by first appearance.
    seen: dict[tuple, int] = {}
    for r in [r for _, r in items]:
        for cid, sc in ((r["a"], r["score_a"]), (r["b"], r["score_b"])):
            seen.setdefault((cid, sc), len(seen))
    pos.sort(key=lambda p: seen.get((p[0], p[1]), len(seen)))
    scores = [s for _, s in pos]
    ranks = rank_of(scores)
    top = max(scores)
    ntop = sum(1 for s in scores if s == top)
    seats = []
    for k, (cid, sc) in enumerate(pos):
        others = [s for j, s in enumerate(scores) if j != k]
        margin = sc - (max(others) if others else sc)
        result = "win" if sc == top and ntop == 1 else \
            ("draw" if sc == top else "loss")
        seats.append({
            "id": cid, "score": sc, "rank": ranks[k],
            "margin": margin, "pts": 1.0 if result == "win" else
            (0.5 if result == "draw" else 0.0), "result": result,
        })
    return {
        "gen": gen, "kind": kind, "map": map, "replay": replay,
        "n": len(seats), "seats": seats,
        "pairs": [{"a": r["a"], "b": r["b"],
                    "score_a": r["score_a"], "score_b": r["score_b"]}
                   for _, r in items],
    }


def group_games(rows: list[dict]) -> list[dict]:
    """Pair rows -> per-game dicts, newest game first.

    Rows sharing a `game` id (one play, one id) group exactly; older rows
    fall back to the replay path, then split on conflicting re-runs and
    dedupe double-logs. Input newest-first (as from list_games) sets game
    order; seats/pairs build oldest-first for a stable picture."""
    keyed: dict[str, list] = {}
    meta: dict[str, dict] = {}
    for r in rows:
        key = game_key_of(r)
        keyed.setdefault(key, []).append(r)
        meta.setdefault(key, r)
    games = []
    for key, rs in keyed.items():
        oldest = rs[::-1]
        raws: dict[tuple, dict] = {}
        for r in oldest:
            raws.setdefault(_norm_row(r), r)
        m0 = meta[key]
        for block in partition_group([_norm_row(r) for r in oldest]):
            g = build_game(m0["gen"], m0["kind"], m0.get("map"),
                           m0["replay"], [(n, raws[n]) for n in block])
            if g is not None:
                games.append(g)
    return games


def member_game_result(game: dict, ref: str) -> str | None:
    """Ref's per-game outcome: best seat wins when a member holds several
    (duplicate-seat extras)."""
    order = {"win": 0, "draw": 1, "loss": 2}
    outs = [s["result"] for s in game["seats"] if s["id"] == ref]
    return min(outs, key=order.__getitem__) if outs else None


def tally_eval(games: list[dict]) -> dict[str, list[int]]:
    """Per-member W-D-L, one entry per eval GAME (win = sole top score,
    draw = tied top). Pairwise 2p history tallies exactly as before."""
    tally: dict[str, list[int]] = {}
    for g in games:
        if g["kind"] != "eval":
            continue
        for cid in dict.fromkeys(s["id"] for s in g["seats"]):
            w, d, l = tally.get(cid, [0, 0, 0])
            r = member_game_result(g, cid)
            tally[cid] = [w + (r == "win"), d + (r == "draw"),
                          l + (r == "loss")]
    return tally


def summarize_maps(games: list[dict]) -> list[dict]:
    """Per (map, seat-count): train/eval game counts plus the eval
    challenger-vs-champion record (fixed seats 0/1, valid for N seats).
    None-map rows are legacy pre-map-logging games, pinned last (P0-7)."""
    acc: dict[tuple, dict] = {}
    for g in games:
        key = (g.get("map"), g["n"])
        m = acc.setdefault(key, {"map": g.get("map"), "n": g["n"],
                                 "train": 0, "eval": 0,
                                 "cw": 0, "cd": 0, "cl": 0})
        if g["kind"] == "train":
            m["train"] += 1
        elif g["kind"] == "eval":
            m["eval"] += 1
            if g["n"] >= 2:
                a, b = g["seats"][0]["score"], g["seats"][1]["score"]
                m["cw"] += a > b
                m["cd"] += a == b
                m["cl"] += a < b
    return sorted(acc.values(),
                  key=lambda m: ((m["map"] is None), (m["map"] or ""), m["n"]))


# ---------------------------------------------------------------- CURVES
# Seven-curve progress board. All helpers are pure (history dicts +
# grouped games in, JSON-able arrays out) so tests pin them without an
# archive. snapshot() only wires them to cached files.

_BT_ELO_SCALE = 400.0 / math.log(10)  # logit -> Elo, like 400*log10 odds
_BT_ITERS = 100  # MM converges long before this on ~25k played pairs
_BT_REG = 1.0  # virtual win+loss vs a rating-0 opponent: shrinks the
# data-poor toward 0 instead of stranding them at +/-inf
_KNOCK_EFF = 0.50  # challenging at even money counts as knocking


def wilson_bounds(wins: float, games: int, z: float = 1.0) -> tuple:
    """Wilson score interval, both ends. Same z=1.0 convention as
    archive.wilson_lower (whose value this matches at the low end).
    Whiskers on the knock/conversion bars."""
    if games <= 0:
        return (0.0, 1.0)
    p = wins / games
    denom = 1.0 + z * z / games
    center = (p + z * z / (2 * games)) / denom
    half = z * math.sqrt(p * (1 - p) / games
                         + z * z / (4 * games * games)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def _hinges(vals: list[float]) -> tuple:
    """Median + Tukey hinges (median of each half, median excluded for
    odd n): robust center and IQR without numpy."""
    s = sorted(vals)
    n = len(s)
    med = (s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2)
    lo = s[:n // 2]
    hi = s[(n + 1) // 2:]
    q1 = (lo[len(lo) // 2] if len(lo) % 2
          else (lo[len(lo) // 2 - 1] + lo[len(lo) // 2]) / 2) if lo else med
    q3 = (hi[len(hi) // 2] if len(hi) % 2
          else (hi[len(hi) // 2 - 1] + hi[len(hi) // 2]) / 2) if hi else med
    return (med, q1, q3)


def roll_median(vals: list, window: int) -> list:
    """15-gen (or w-gen) rolling median over non-None values: the bold
    line to each curve's faint per-gen points."""
    out = []
    for i in range(len(vals)):
        win = [v for v in vals[max(0, i - window + 1):i + 1]
               if v is not None]
        out.append(_hinges(win)[0] if win else None)
    return out


def roll_mean(vals: list, window: int) -> list:
    """Rolling mean twin of roll_median (decisiveness MA)."""
    out = []
    for i in range(len(vals)):
        win = [v for v in vals[max(0, i - window + 1):i + 1]
               if v is not None]
        out.append(sum(win) / len(win) if win else None)
    return out


def merge_pairs(*dicts: dict) -> dict:
    """Sum per-key [wins_a, wins_b] across matrices (train + eval).

    Overlapping keys (same pair met in both phases) add: a win is a win
    wherever it was scored. Malformed values are skipped, never zeroed."""
    out: dict[str, list[float]] = {}
    for d in dicts:
        for key, w in (d or {}).items():
            try:
                w0, w1 = float(w[0]), float(w[1])
            except (TypeError, ValueError, IndexError):
                continue
            acc = out.setdefault(key, [0.0, 0.0])
            acc[0] += w0
            acc[1] += w1
    return out


def _mm_run(n: int, totals: dict, theta: list[float], iters: int,
            tol: float) -> list[float]:
    """Gauss-Seidel MM sweeps over played pairs (Hunter 2004), in place.

    totals maps (i, j), i<j, to [wins_ij, wins_ji] WITHOUT the Laplace
    prior (added here, +1/+1 per pair, cf. archive._head_to_head) plus
    the virtual-opponent regularizer: one virtual win and 2*_BT_REG
    virtual games vs a rating-0 opponent per member. Shared by the
    one-shot bt_fit and the warm-started causal refits; tol<=0 runs all
    `iters` sweeps (bt_fit parity), otherwise stops when no log-rating
    moves more than tol."""
    adj: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    wins = [0.0] * n
    for (i, j), w in totals.items():
        mine, theirs = w[0] + 1.0, w[1] + 1.0
        total = mine + theirs
        adj[i].append((j, total))
        adj[j].append((i, total))
        wins[i] += mine
        wins[j] += theirs
    theta = list(theta)
    for _ in range(iters):
        maxd = 0.0
        for i in range(n):
            denom = 2.0 * _BT_REG / (theta[i] + 1.0)
            for j, total in adj[i]:
                denom += total / (theta[i] + theta[j])
            new = (wins[i] + _BT_REG) / denom if denom > 0 else theta[i]
            if new > 0 and theta[i] > 0:
                d = abs(math.log(new) - math.log(theta[i]))
                if d > maxd:
                    maxd = d
            theta[i] = new
        if tol > 0 and maxd < tol:
            break
    return theta


def bt_fit(ids: list[str], ev: dict, iters: int = _BT_ITERS) -> dict:
    """Regularized Bradley-Terry ratings (logit) over train+eval pairs.

    Train games are valid engine games, so the fit takes both matrices
    merged (train + eval game-log pairs, see gen_pair_buckets): ~25k
    unordered pairs. Sparse MM (Hunter 2004): each sweep touches only
    played pairs, ~0.5s cold (100 sweeps), cached per matrix-digest like
    Nash. Draws ride as half-wins, the codebase-wide outcome_of
    convention. Turn-count confound, disclosed not corrected: gens
    g031-g045 ran train 60 vs eval 150 turns (see turn_mismatch); both
    eras' games mix into one fit, so cross-era Elo gaps partly reflect
    game length. Members with no games anywhere sit at exactly 0.
    Regularization is the same +1/+1 Laplace prior archive._head_to_head
    uses, plus one virtual win AND one virtual loss vs a rating-0
    opponent per member: thin samples shrink toward the pack."""
    n = len(ids)
    if not n:
        return {}
    pos = {cid: i for i, cid in enumerate(ids)}
    totals: dict[tuple[int, int], list[float]] = {}
    seen: set[tuple[int, int]] = set()
    for key, _w in ev.items():
        pair = _split_pair(key, pos)
        if pair is None:
            continue
        i, j = pair
        if i == j:
            continue
        # One entry per unordered pair (a matrix pair logged in both
        # directions still counts once); both orders fold into a single
        # mine/theirs split relative to canonical (a, b) order.
        a, b = (i, j) if i < j else (j, i)
        if (a, b) in seen:
            continue
        seen.add((a, b))
        wab = ev.get(f"{ids[a]} vs {ids[b]}", [0.0, 0.0])
        wba = ev.get(f"{ids[b]} vs {ids[a]}", [0.0, 0.0])
        try:
            wab0, wab1 = float(wab[0]), float(wab[1])
            wba0, wba1 = float(wba[0]), float(wba[1])
        except (TypeError, ValueError, IndexError):
            continue
        mine, theirs = wab0 + wba1, wab1 + wba0
        if mine + theirs <= 0:  # Laplace only: never actually played
            continue
        acc = totals.setdefault((a, b), [0.0, 0.0])
        acc[0] += mine
        acc[1] += theirs
    theta = _mm_run(n, totals, [1.0] * n, iters, tol=0.0)
    return {cid: (math.log(t) if t > 0 else 0.0) for cid, t in zip(ids, theta, strict=True)}


_bt_digest_cache: dict = {}


def _bt_digest(base: Path) -> tuple:
    """Cache key over BOTH matrices (the BT fit reads train + eval).

    Same stat-check trick as _eval_digest: unchanged mtime+size reuses
    the last digest, so a warm snapshot pays no re-dump."""
    path = base / "matrix.json"
    try:
        st = path.stat()
    except OSError:
        return (None, None, None)
    key = (str(base.resolve()), st.st_mtime_ns, st.st_size)
    if _bt_digest_cache.get("key") == key:
        return _bt_digest_cache["value"]
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return (None, None, None)
    digest = (tuple(data.get("ids", [])),
              json.dumps(data.get("eval", {}), sort_keys=True),
              json.dumps(data.get("train", {}), sort_keys=True))
    _bt_digest_cache["key"] = key
    _bt_digest_cache["value"] = digest
    return digest


def panel_ids(history: list[dict]) -> list[str]:
    """Fixed Elo anchor panel: BC g000 plus the last 3 deposed champs.

    Walk the verdicts in order; every promoted challenger deposes the
    reigning champ. Short histories yield a shorter panel (no padding:
    padding would invent data)."""
    deposed: list[str] = []
    reigning = history[0].get("champion") if history else None
    for h in history:
        if h.get("promoted"):
            if reigning is not None:
                deposed.append(reigning)
            reigning = h.get("challenger", reigning)
    panel = ["g000"] + [c for c in deposed[-3:] if c != "g000"]
    return list(dict.fromkeys(panel))


def anchored_elo(ids: list[str], ev: dict, panel: list[str],
                 iters: int = _BT_ITERS) -> dict:
    """BT ratings re-zeroed so the panel mean is 0, scaled to Elo."""
    ratings = bt_fit(ids, ev, iters)
    have = [ratings[p] for p in panel if p in ratings]
    zero = sum(have) / len(have) if have else 0.0
    return {cid: (r - zero) * _BT_ELO_SCALE for cid, r in ratings.items()}


CAUSAL_STEP = 15  # refit cadence, aligned to the knock/conversion windows
_CAUSAL_TOL = 3e-5  # warm-started sweeps stop here (cap stays _BT_ITERS).
# Cost/precision on the 1690-gen archive: full build ~7s cold (vs ~10s at
# tol 0 / 2s at tol 1e-3); worst plotted-series deviation vs the
# fully-converged reference is 0.41 Elo (p99 0.25, median 0.0002) —
# sub-pixel except single-point wobbles. Display precision, not truth.


def gen_pair_buckets(grouped: list[dict], gen_index: dict,
                     pos: dict, n_gen: int) -> list[dict]:
    """Per-gen aggregated unordered pairs from the grouped game log.

    One entry per (gen, seat-pair): outcome from the canonically-first
    member's view (draws = 0.5, the outcome_of convention), train and
    eval kinds together. Pairs naming unknown members and self-pairs
    are skipped, as in the matrix fits. The game log is used instead of
    matrix.json because only the log carries gen attribution; the two
    agree pair-for-pair (record_result and log_game fire together per
    seat-pair in train.py/evaluate.py) except legacy double-logs, which
    the matrix counts twice and grouping dedupes once."""
    per_gen: list[dict] = [{} for _ in range(n_gen)]
    for g in grouped:
        gi = gen_index.get(g.get("gen"))
        if gi is None:
            continue
        for p in g.get("pairs", []) or []:
            a, b = p.get("a"), p.get("b")
            if a not in pos or b not in pos:
                continue
            i, j = pos[a], pos[b]
            if i == j:
                continue
            try:
                sa, sb = float(p["score_a"]), float(p["score_b"])
            except (TypeError, ValueError, KeyError):
                continue
            out = 1.0 if sa > sb else (0.0 if sb > sa else 0.5)
            key = (i, j) if i < j else (j, i)
            acc = per_gen[gi].setdefault(key, [0.0, 0.0])
            if (i, j) == key:
                acc[0] += out
                acc[1] += 1.0 - out
            else:
                acc[0] += 1.0 - out
                acc[1] += out
    return per_gen


def _refits_from(ids: list[str], per_gen: list[dict], totals: dict,
                 theta: list[float], start: int,
                 step: int = CAUSAL_STEP, iters: int = _BT_ITERS,
                 tol: float = _CAUSAL_TOL) -> tuple[list, dict, list]:
    """Accumulate per-gen buckets from `start`, refitting at gi % step == 0.

    Warm-started: theta carries the previous refit's solution forward
    (extended with 1.0 for members first seen later), so each refit
    converges in a handful of sweeps. Returns (refit dicts, totals,
    theta) for the caller to cache; pure given its inputs."""
    n = len(ids)
    refits: list[dict] = []
    for gi in range(start, len(per_gen)):
        for key, w in per_gen[gi].items():
            acc = totals.setdefault(key, [0.0, 0.0])
            acc[0] += w[0]
            acc[1] += w[1]
        if gi % step == 0:
            theta = _mm_run(n, totals, theta, iters, tol)
            refits.append({cid: (math.log(t) if t > 0 else 0.0)
                           for cid, t in zip(ids, theta, strict=True)})
    return refits, totals, theta


def causal_refits(ids: list[str], per_gen: list[dict],
                  step: int = CAUSAL_STEP, iters: int = _BT_ITERS,
                  tol: float = _CAUSAL_TOL) -> list[dict]:
    """Quantized causal refits: refit r uses only pairs with gen <= r*step.

    No naive per-gen refits (1690 full fits): refits happen every `step`
    gens, each warm-started from the previous refit's theta, so late
    refits converge in a handful of sweeps (each window adds ~1% of the
    data). Members unseen so far sit at exactly 0 via the virtual
    regularizer. Returns one {cid: logit} dict per refit, in order;
    plotted value at gen G is refits[G // step] (step-held), which uses
    only games with gen <= step*(G//step) <= G: causal by construction.
    Later windows cannot move earlier refits (sequential accumulation)."""
    refits, _, _ = _refits_from(ids, per_gen, {}, [1.0] * len(ids), 0,
                                step, iters, tol)
    return refits


def causal_duel(history: list[dict], ids: list[str],
                refits: list[dict], step: int = CAUSAL_STEP) -> dict:
    """Candidate vs defending-champion Elo from the causal refits.

    cand[G] = this gen's challenger, champ[G] = the throne's defender,
    both read out of refits[G // step] and anchored at g000 (known at
    gen 0, so the zero is causal too). Panel members (g000 + last 3
    deposed) ride along as reference trajectories from the same refits;
    panel MEMBERSHIP is picked from full history (a display choice: which
    lines to draw), but every plotted VALUE uses only games <= G."""
    tables: list[dict] = []
    for r in refits:
        zero = r.get("g000", 0.0)
        tables.append({cid: (v - zero) * _BT_ELO_SCALE
                       for cid, v in r.items()})
    panel = panel_ids(history)
    cand: list = []
    champ: list = []
    refs: dict[str, list] = {pid: [] for pid in panel}
    reigning = history[0].get("champion") if history else None
    for gi, h in enumerate(history):
        tab = tables[gi // step] if tables else {}
        c = h.get("challenger")
        cand.append(tab.get(c))
        champ.append(tab.get(reigning) if reigning is not None else None)
        for pid in panel:
            refs[pid].append(tab.get(pid))
        if h.get("promoted"):
            reigning = c
    return {"cand": cand, "champ": champ, "panel": panel, "refs": refs}


def elo_duel(history: list[dict], elos: dict) -> dict:
    """Candidate vs defending-champion anchored Elo per gen.

    cand = this gen's challenger, champ = the throne's defender (the
    verdict may depose him after). Crossovers read as throne changes:
    in a staircase stretch the candidate line runs above the champ line
    before a promotion. Same panel anchoring as ever (zero = panel
    mean); same train/eval turn-count confound as bt_fit (disclosed in
    the card legend, not corrected)."""
    cand: list = []
    champ: list = []
    reigning = history[0].get("champion") if history else None
    for h in history:
        c = h.get("challenger")
        cand.append(elos.get(c))
        champ.append(elos.get(reigning) if reigning is not None else None)
        if h.get("promoted"):
            reigning = c
    return {"cand": cand, "champ": champ}


def turn_mismatch(history: list[dict]) -> list[dict]:
    """Consecutive-gen ranges where train and eval turns differed.

    Eval length is cfg eval_turns, defaulting to train's cfg turns
    (evaluate.py: `turns=cfg.get("eval_turns") or cfg["turns"]`).
    Ranges name challenger ids, e.g. g031-g045 at 60 vs 150. The Elo
    card legend discloses these ranges; the fit itself is uncorrected."""
    ranges: list[dict] = []
    start: int | None = None
    for i, h in enumerate(history):
        cfg = h.get("config", {}) or {}
        t = cfg.get("turns")
        et = cfg.get("eval_turns") or t
        bad = (t is not None and et is not None and et != t)
        if bad and start is None:
            start = i
        if not bad and start is not None:
            ranges.append({"from": history[start].get("challenger"),
                           "to": history[i - 1].get("challenger"),
                           "train_turns": history[start].get(
                               "config", {}).get("turns"),
                           "eval_turns": history[start].get(
                               "config", {}).get("eval_turns")})
            start = None
    if start is not None:
        ranges.append({"from": history[start].get("challenger"),
                       "to": history[-1].get("challenger"),
                       "train_turns": history[start].get(
                           "config", {}).get("turns"),
                       "eval_turns": history[start].get(
                           "config", {}).get("eval_turns")})
    return ranges


def _eff(h: dict) -> float | None:
    ev = h.get("eval", {}) or {}
    if ev.get("games"):
        return ev.get("win_rate", (ev.get("wins", 0)
                                    + 0.5 * ev.get("draws", 0)) / ev["games"])
    return None


def knock_conversion(history: list[dict], window: int = 15) -> dict:
    """Knock marks + dual 15-gen window rates with Wilson whiskers.

    knock = eff >= .50 (challenging at even money); conversion =
    promoted | knock. `knock` is the raw binary per-gen lane (1/0/None:
    no-eval gens are gaps, never zeros); the trailing-window rates and
    z=1.0 Wilson whiskers sit in a separate panel so they never fight
    the 1690 per-gen marks."""
    knock, rate, lo, hi, conv, clo, chi = [], [], [], [], [], [], []
    for i in range(len(history)):
        e = _eff(history[i])
        knock.append(1 if e is not None and e >= _KNOCK_EFF
                       else (0 if e is not None else None))
        win = history[max(0, i - window + 1):i + 1]
        effs = [(h.get("promoted", False), _eff(h)) for h in win]
        effs = [(p, e) for p, e in effs if e is not None]
        n = len(effs)
        k = sum(1 for _, e in effs if e >= _KNOCK_EFF)
        rate.append(k / n if n else None)
        blo, bhi = wilson_bounds(k, n)
        lo.append(blo if n else None)
        hi.append(bhi if n else None)
        pk = sum(1 for p, e in effs if e >= _KNOCK_EFF and p)
        conv.append(pk / k if k else None)
        clo_, chi_ = wilson_bounds(pk, k)
        clo.append(clo_ if k else None)
        chi.append(chi_ if k else None)
    return {"knock": knock, "rate": rate, "lo": lo, "hi": hi,
            "conv": conv, "clo": clo, "chi": chi}


def decisiveness(history: list[dict], games: list[dict],
                 window: int = 15) -> dict:
    """Nonzero-margin fraction: train from grouped games, eval from
    duel margins. Raw per-gen lines plus a 15-gen MA each.

    A game is decisive unless every seat tied (max != min). Train games
    key on the challenger id (= history order); eval margins are the
    signed challenger-minus-champ duels."""
    by_gen: dict[str, list] = {}
    for g in games:
        if g.get("kind") == "train":
            by_gen.setdefault(g.get("gen"), []).append(g)
    train, evalv = [], []
    for h in history:
        gs = by_gen.get(h.get("challenger"), [])
        if gs:
            dec = 0
            for g in gs:
                scores = [s["score"] for s in g.get("seats", [])]
                if scores and max(scores) != min(scores):
                    dec += 1
            train.append(dec / len(gs))
        else:
            train.append(None)
        margins = (h.get("eval", {}) or {}).get("margins", []) or []
        evalv.append(sum(1 for m in margins if m != 0) / len(margins)
                     if margins else None)
    return {"train": train, "train_ma": roll_mean(train, window),
            "eval": evalv, "eval_ma": roll_mean(evalv, window)}


def margin_band(history: list[dict], window: int = 15) -> dict:
    """Eval margin median +/- IQR over pooled 15-gen windows, signed
    challenger-minus-champ. Pooling (not median-of-medians) keeps big
    duel counts honest."""
    med, q1, q3 = [], [], []
    for i in range(len(history)):
        pool: list[float] = []
        for h in history[max(0, i - window + 1):i + 1]:
            pool.extend((h.get("eval", {}) or {}).get("margins", []) or [])
        if pool:
            m, a, b = _hinges([float(x) for x in pool])
            med.append(m)
            q1.append(a)
            q3.append(b)
        else:
            med.append(None)
            q1.append(None)
            q3.append(None)
    return {"med": med, "q1": q1, "q3": q3}


def pg_signal(history: list[dict], window: int = 10) -> dict:
    """PG signal ratio |pg_loss|/pg_abs at the last epoch + entropy.

    EXPERIMENTAL: no literature backing — the ratio is a local probe of
    whether the policy gradient still moves the update relative to its
    own scale, not an endorsed health metric. Missing/zero pg_abs (gens
    logged before the field existed) yield None, never 0."""
    ratio, entropy = [], []
    for h in history:
        tr = h.get("train", {}) or {}
        pl = tr.get("pg_loss", []) or []
        pa = tr.get("pg_abs", []) or []
        en = tr.get("entropies", []) or []
        last_abs = pa[-1] if pa else None
        ratio.append(abs(pl[-1]) / last_abs
                     if pl and isinstance(last_abs, (int, float))
                     and last_abs else None)
        entropy.append(en[-1] if en else None)
    return {"ratio": ratio, "ratio_med": roll_median(ratio, window),
            "entropy": entropy,
            "entropy_med": roll_median(entropy, window)}


def value_slope(history: list[dict]) -> list:
    """Critic fit per gen: (v_loss[0]-v_loss[-1])/v_loss[0]. Positive =
    the critic still learned within the gen; ~0 = saturated; negative =
    the value fit got worse. Zero/missing opener yields None."""
    out = []
    for h in history:
        v = (h.get("train", {}) or {}).get("v_loss", []) or []
        out.append((v[0] - v[-1]) / v[0]
                   if len(v) and isinstance(v[0], (int, float)) and v[0]
                   else None)
    return out


def norm01(vals: list) -> list:
    """Min-max normalize non-None values to [0,1] for legibility lanes.

    A near-constant series (mid-era Nash entropy: 0.14-0.26 against a
    0.004-3.89 global span) would render as a dead-flat line on a
    shared axis; normalized, its shape fills the lane. The card labels
    the lane with the true min/max so the scale is never a lie.
    Constant series sit mid-lane (0.5); all-None stays all-None."""
    have = [v for v in vals if v is not None]
    if not have:
        return [None] * len(vals)
    mn, mx = min(have), max(have)
    if not mx > mn:
        return [0.5 if v is not None else None for v in vals]
    return [(v - mn) / (mx - mn) if v is not None else None for v in vals]


def reign_strip(history: list[dict]) -> dict:
    """Tenure = gens held including current (the history-open throne
    predates the log, so it starts at 1: a documented lower bound).
    The crowning gen itself has tenure 0. turnover flags promotions.
    entropy is the Nash-mixture entropy (nats) stored per gen."""
    tenure, turnover, entropy = [], [], []
    t = 0
    for i, h in enumerate(history):
        if h.get("promoted"):
            t = 0
            turnover.append(1)
        else:
            t = t + 1 if i else 1
            turnover.append(0)
        tenure.append(t)
        mix = h.get("nash", {}) or {}
        entropy.append(-sum(p * math.log(p) for p in mix.values() if p > 0)
                         if mix else None)
    best = max(tenure) if tenure else 0
    last = tenure[-1] if tenure else 0
    return {"tenure": tenure, "turnover": turnover, "entropy": entropy,
            "entropy_n": norm01(entropy),
            "readout": f"tenure {last} · best {best}"}


def nplayer_start(history: list[dict], games: list[dict]) -> int | None:
    """First history index whose challenger logged a 3+ seat game.

    The N-player era boundary is DERIVED from grouped games, never
    hardcoded. (The jury era has no boundary: exam juries were proposed
    in run notes but no jury field or regime ever entered training
    data, so per the no-invented-data rule no jury band is drawn.)"""
    idx = {h.get("challenger"): i for i, h in enumerate(history)}
    starts = [idx[g.get("gen")] for g in games
              if (g.get("n", len(g.get("seats", []))) or 0) > 2
              and g.get("gen") in idx]
    return min(starts) if starts else None


def crown_type(gen: dict) -> str:
    """complete = beat the champ head-to-head AND the duel field;
    soft = otherwise; held gens wear no crown ("—").

    Derived from eval margins + totals only. Head-to-head = strict duel
    majority (wins > losses, draws excluded). Field = aggregate scoring
    edge (mean margin > 0 across ALL eval duels, draws included): a
    draw-carried or outscored promotion takes the throne but not the
    complete tag."""
    if not gen.get("promoted"):
        return "—"
    ev = gen.get("eval", {}) or {}
    wins = ev.get("wins", 0)
    losses = ev.get("games", 0) - wins - ev.get("draws", 0)
    margins = ev.get("margins", []) or []
    mean_m = (sum(margins) / len(margins) if margins
              else ev.get("mean_margin", 0.0))
    return "complete" if wins > losses and mean_m > 0 else "soft"


_causal_cache: dict = {}


def _causal_cached(base: Path, history: list[dict],
                   grouped: list[dict]) -> dict:
    """Causal duel series: full build once, streaming extends after.

    Training only appends (new games carry the current challenger's gen;
    matrix ids only append), so when the challenger list and member ids
    both extend the cached ones AND the rebuilt early buckets are
    unchanged, only gens past the cached point are accumulated and only
    refits at or past it re-run, warm-started from the stored theta.
    During a run that is one cheap refit per poll instead of 113; any
    rewrite (truncation, reorder) falls back to a full rebuild. The
    in-progress gen's games join its bucket (visible in training-curve
    detail) but only move plotted Elo at its window's refit, by design.
    Warm snapshots with no new gens reuse the stored series for free."""
    try:
        data = json.loads((base / "matrix.json").read_text())
        ids = data.get("ids", [])
    except (OSError, ValueError):
        return {"cand": [], "champ": [], "panel": [], "refs": {}}
    pos = {cid: i for i, cid in enumerate(ids)}
    gen_index = {h.get("challenger"): i for i, h in enumerate(history)}
    per_gen = gen_pair_buckets(grouped, gen_index, pos, len(history))
    challengers = [h.get("challenger") for h in history]
    st = _causal_cache.get("state")
    if (st is not None
            and len(challengers) >= len(st["challengers"])
            and challengers[:len(st["challengers"])] == st["challengers"]
            and len(ids) >= len(st["ids"])
            and ids[:len(st["ids"])] == st["ids"]
            and len(per_gen) >= st["ngen"]
            and all(per_gen[i] == st["buckets"][i]
                    for i in range(st["ngen"]))):
        theta = st["theta"] + [1.0] * (len(ids) - len(st["ids"]))
        new, totals, theta = _refits_from(ids, per_gen, st["totals"],
                                          theta, st["ngen"])
        refits = st["refits"] + new
        ngen = len(per_gen)
    else:
        refits, totals, theta = _refits_from(ids, per_gen, {},
                                             [1.0] * len(ids), 0)
        ngen = len(per_gen)
    _causal_cache["state"] = {"challengers": challengers, "ids": ids,
                                "buckets": per_gen, "totals": totals,
                                "theta": theta, "refits": refits,
                                "ngen": ngen}
    return causal_duel(history, ids, refits)


def build_board(base: Path, history: list[dict],
                grouped: list[dict]) -> dict:
    """All seven curves, aligned to history order (x = challenger ids)."""
    try:
        duel = _causal_cached(base, history, grouped)
    except (OSError, ValueError, KeyError, TypeError):
        duel = {"cand": [], "champ": [], "panel": [], "refs": {}}
    kc = knock_conversion(history)
    np_idx = nplayer_start(history, grouped)
    return {
        "ids": [h.get("challenger", "") or "" for h in history],
        "elo": {**duel, "turn_note": turn_mismatch(history)},
        "knock": kc,
        "decisive": decisiveness(history, grouped),
        "margin": margin_band(history),
        "pg": pg_signal(history),
        "vslope": value_slope(history),
        "reign": reign_strip(history),
        "regimes": {
            "nplayer": np_idx,
            "nplayer_gen": (history[np_idx].get("challenger")
                             if np_idx is not None else None),
        },
    }


def snapshot(base: Path) -> dict:
    """Everything the page needs, in one JSON-able dict. One read per file."""
    archive.init(base)
    champ = None
    try:
        champ = archive.get_champion(base)
    except (OSError, ValueError, KeyError, TypeError):
        champ = None
    try:
        mix = _nash_cached(base)
    except (OSError, ValueError, KeyError, TypeError):
        mix = {}
    history = cached_history(base)
    grouped = cached_grouped(base)
    tally = tally_eval(grouped)
    members = []
    for m in archive.members(base):
        cid = m["id"]
        w, d, l = tally.get(cid, [0, 0, 0])
        members.append({
            "id": cid, "role": m["role"], "parent": m["parent"],
            "nash": round(mix.get(cid, 0.0), 4),
            "wins": w, "draws": d, "losses": l,
        })
    gens = []
    for h in history:
        ev = h.get("eval", {}) or {}
        tr = h.get("train", {}) or {}
        losses = tr.get("losses", []) or []
        thr = (h.get("config", {}) or {}).get("promote_threshold", 0.5)
        draws = ev.get("draws", 0)
        ngames = ev.get("games", 0)
        wr = ev.get("win_rate", 0.0)
        lower = archive.wilson_lower(ev.get("wins", 0) + 0.5 * draws, ngames)
        cfg = h.get("config", {}) or {}
        if not ev:
            reason = "held: waiting on first eval"
        elif h.get("promoted"):
            reason = f"promoted: lower {lower:.2f} clears threshold {thr:.2f}"
        else:
            reason = f"held: lower {lower:.2f} vs threshold {thr:.2f}"
        gens.append({
            "id": h.get("challenger", h.get("id", "?")),
            "champion": h.get("champion"),
            "train_return": _rnd(tr.get("mean_return", 0.0), 2),
            "train_loss": _rnd((sum(losses) / len(losses)) if losses else 0.0, 3),
            "eval_w": ev.get("wins", 0), "eval_d": draws,
            "eval_games": ngames, "win_rate": wr,
            "wilson_lower": round(lower, 3),
            "threshold": thr,
            "promoted": bool(h.get("promoted")),
            "reason": reason,
            "crown": crown_type(h),
            "arch": cfg.get("arch", "base"),
            "turns": cfg.get("turns", 0),
            "gamma": cfg.get("gamma", 0.0),
            "mean_margin": _rnd(ev.get("mean_margin", 0.0), 2),
            "margins": ev.get("margins", []),  # kept: feeds the W/D/L dot strip (P2-4)
            "exploiter": bool(h.get("exploiter")),
            "started_at": h.get("started_at"),
            "finished_at": h.get("finished_at"),
            "duration_s": h.get("duration_s"),
        })
    gens.reverse()
    durs = [h.get("duration_s") for h in history
            if isinstance(h.get("duration_s"), (int, float))]
    recent = durs[-5:]
    avg = sum(recent) / len(recent) if recent else None
    plan = {}
    try:
        plan = json.loads((base / "run_plan.json").read_text())
    except (OSError, ValueError):
        plan = {}
    target = plan.get("target_gens")
    run = {
        "finished": len(history),
        "target": target if isinstance(target, int) else None,
        "avg_s": round(avg, 1) if avg else None,
        "last_finished_at": history[-1].get("finished_at") if history else None,
    }
    losses = []
    for h in history:
        ls = ((h.get("train", {}) or {}).get("losses", []) or [])
        losses.append(sum(ls) / len(ls) if ls else None)
    curves = {
        "loss": losses,
        "ret": [((h.get("train", {}) or {}).get("mean_return", 0.0)) for h in history],
        "ids": [h.get("challenger", "") or "" for h in history],
    }
    return {
        "champion": champ,
        "mtime": archive_mtime(base),
        "members": members,
        "run": run,
        "curves": curves,
        "board": build_board(base, history, grouped),
        "generations": gens,
        "games": grouped[:50],
        "game_total": len(grouped),
        "maps": summarize_maps(grouped),
        "status": archive.read_status(base),
        "counts": {"generations": len(history), "games": len(grouped)},
    }


def replay_page(base: Path, rel: str | None) -> str | None:
    """Visualizer HTML with the replay inlined. None if unsafe/missing."""
    if not rel or not rel.endswith(".replay"):
        return None
    target = (base / rel).resolve()
    if not str(target).startswith(str(base.resolve())) or not target.is_file():
        return None
    data = target.read_text()
    try:
        data = json.dumps(json.loads(data), separators=(",", ":"))
        data = data.replace("\\", "\\\\").replace("'", "\\'")
    except ValueError:
        data = data.replace("\n", "\\\\n").replace("'", "\\'")
    page = TEMPLATE.replace("## PATH PLACEHOLDER ##", "/static/v/")
    # Distinct tab titles per replay (P1-6): side-by-side comparison is
    # the workflow, and every tab read "Ant Canvas" before.
    page = page.replace("<title>Ant Canvas</title>",
                        f"<title>replay {html.escape(rel)} · AZDash</title>")
    return page.replace("## REPLAY PLACEHOLDER ##", data)


# ---------------------------------------------------------------- API


def _json(handler: BaseHTTPRequestHandler, obj: object, status: int = 200) -> None:
    body = json.dumps(obj).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def make_handler(base: Path):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AZDash"

        def log_message(self, *args):
            pass

        def _send(self, body: bytes, ctype: str):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/":
                    # Server-rendered first paint (P0-1): champion, counts,
                    # status and the first table pages inline, no JS needed.
                    # On failure fall back to the skeleton shell; the poll
                    # tick heals it on the next cycle.
                    try:
                        first = snapshot(base)
                    except Exception:
                        first = None
                    self._send(render_page(first).encode(), "text/html")
                elif parsed.path == "/api/snapshot":
                    q = parse_qs(parsed.query)
                    since = q.get("since", [None])[0]
                    if since is not None and is_fresh(base, since):
                        _json(self, {"unchanged": True,
                                     "mtime": archive_mtime(base)})
                    else:
                        _json(self, snapshot(base))
                elif parsed.path == "/api/games":
                    q = parse_qs(parsed.query)
                    member = q.get("member", [None])[0]
                    try:
                        limit = max(0, min(int(q.get("limit", ["50"])[0]), 200))
                    except ValueError:
                        limit = 50
                    try:
                        offset = max(int(q.get("offset", ["0"])[0]), 0)
                    except ValueError:
                        offset = 0
                    rows = cached_grouped(base)
                    if member is not None:
                        rows = [g for g in rows
                                if any(s["id"] == member for s in g["seats"])]
                    total = len(rows)
                    offset = min(offset, total)
                    _json(self, {"total": total,
                                 "rows": rows[offset:offset + limit]})
                elif parsed.path == "/replay":
                    rel = parse_qs(parsed.query).get("f", [None])[0]
                    page = replay_page(base, rel)
                    if page is None:
                        self.send_error(404, "no such replay")
                    else:
                        self._send(page.encode(), "text/html")
                elif parsed.path.startswith("/static/v/"):
                    target = (VIS_DIR / parsed.path[len("/static/v/"):]).resolve()
                    if not str(target).startswith(str(VIS_DIR.resolve())) or not target.is_file():
                        self.send_error(404, "no such file")
                    else:
                        ctype = "application/javascript" if target.suffix == ".js" else (
                            "text/html" if target.suffix in (".html", ".htm") else
                            "image/png" if target.suffix == ".png" else "application/octet-stream")
                        self._send(target.read_bytes(), ctype)
                else:
                    _json(self, {"error": f"unknown route: {parsed.path}"}, status=404)
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
                _json(self, {"error": f"{type(e).__name__}: {e}"}, status=500)

    return Handler


# ------------------------------------------------------- SERVER RENDER
# First-paint helpers (P0-1): render_page(snapshot) inlines the hero,
# strip and first table pages into the raw HTML so the first paint is
# content, not a fetch spinner. The JS poll takes over from the same
# JSON afterwards; row markup here mirrors the JS renderers below
# (any visual change needs both sides — search for the twin name).

EMPTY_GAMES = "no games logged yet — they appear here as each game finishes"
MAP_UNLABELLED = "unlabelled (pre-map logging)"


def _esc(x) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def fmt_dur(s) -> str:
    """Tagged durations (P1-5): `220 s`, past 60s `3m 40s`."""
    try:
        s = float(s)
    except (TypeError, ValueError):
        return "—"
    if s < 60:
        return f"{int(round(s))} s"
    m = int(s // 60)
    return f"{m}m {int(round(s - 60 * m)):02d}s"


def fmt_time(ts) -> str:
    """`HH:MM` today, `MMM d, HH:MM` older; full ISO goes in `title` (P0-6)."""
    if not isinstance(ts, (int, float)):
        return "—"
    import datetime as _dt
    d = _dt.datetime.fromtimestamp(ts)
    hm = d.strftime("%H:%M")
    if d.date() == _dt.date.today():
        return hm
    return d.strftime("%b %d, %H:%M")


def iso_time(ts) -> str:
    if not isinstance(ts, (int, float)):
        return ""
    import datetime as _dt
    return _dt.datetime.fromtimestamp(ts).astimezone().isoformat(timespec="minutes")


def dot_strip(margins, cap: int = 20) -> str:
    """Per-generation W/D/L dots (P2-4): close or blowout at a glance.
    Downsampled to `cap` cells; each dot titles its signed margin in pts."""
    ms = [m for m in (margins or []) if isinstance(m, (int, float))]
    if not ms:
        return '<span class="legend">no duels</span>'
    step = max(1, (len(ms) + cap - 1) // cap)
    cells = []
    for m in ms[::step][:cap]:
        cls = "w" if m > 0 else ("d" if m == 0 else "l")
        word = "win" if m > 0 else ("draw" if m == 0 else "loss")
        cells.append(
            f'<span class="dot {cls}" title="{word} {m:+g} pts">●</span>')
    return "".join(cells)


def replay_label(gen, replay) -> str:
    """`gen g1732 · eval0 →`: the tab reads where the link goes (P1-6)."""
    parts = [p for p in str(replay or "").split("/") if p]
    short = parts[-3] if len(parts) >= 3 else \
        (parts[-1].replace(".replay", "") if parts else "?")
    return f"gen {gen} · {short} →"


def hero_run_text(run: dict) -> str:
    """`gen 1690 · target 1689 reached` once finished >= target (P0-5)."""
    fin = run.get("finished", 0) or 0
    tgt = run.get("target")
    if isinstance(tgt, int):
        if fin >= tgt:
            return f"gen {fin} · target {tgt} reached"
        return f"gen {fin} · target {tgt}"
    return f"gen {fin}"


def map_label(m) -> str:
    """Nulls are legacy pre-map-logging rows, not a logging bug (P0-7)."""
    return m if m else MAP_UNLABELLED


def status_html(st: dict, champ, ngens: int) -> tuple[str, int]:
    """Status line + progress %, twin of the JS renderHeader branch."""
    st = st or {}
    phase = st.get("phase")
    if phase == "train":
        done, total = max(0, int(st.get("done", 0) or 0)), \
            max(1, int(st.get("total", 0) or 1))
        ret = st.get("last_mean_return", 0.0)
        try:
            ret_s = f"{float(ret):.2f}"
        except (TypeError, ValueError):
            ret_s = "—"
        return (f"training <b>{_esc(st.get('challenger', ''))}</b> · "
                f"game {done}/{st.get('total', 0)} · "
                f"last mean return <b>{ret_s}</b>", 100 * done // total)
    if phase == "eval":
        done, total = max(0, int(st.get("done", 0) or 0)), \
            max(1, int(st.get("total", 0) or 1))
        return (f"evaluating <b>{_esc(st.get('challenger', ''))}</b> · "
                f"duel {done}/{st.get('total', 0)} · "
                f"<b>{st.get('wins', 0)}W {st.get('draws', 0)}D</b> so far",
                100 * done // total)
    if phase == "done":
        badge = ('<span class="badge promoted">promoted ★</span>'
                 if st.get("promoted")
                 else '<span class="badge held">held</span>')
        return (f"last run finished: <b>{_esc(st.get('challenger', ''))}</b> "
                f"{badge} · champion {_esc(st.get('champion', ''))} · "
                f"idle, waiting for the next run", 100)
    if ngens:
        return (f"idle · last champion {_esc(champ or '—')}", 0)
    return ("waiting for the first generation…", 0)


def _num(x) -> float:
    """Coerce snapshot numbers for first-paint formatting; junk reads as 0."""
    return x if isinstance(x, (int, float)) else 0.0


def gen_row_html(g: dict) -> str:
    """Twin of JS genRow: challenger · return · loss · eval · result · crown."""
    pct = 100 * _num(g.get("win_rate"))
    losses_n = max(0, int(_num(g.get("eval_games"))) - int(_num(g.get("eval_w")))
                   - int(_num(g.get("eval_d"))))
    wdl = f"{int(_num(g.get('eval_w')))}-{int(_num(g.get('eval_d')))}-{losses_n}"
    rate = f"{_num(g.get('win_rate')) * 100:.1f}%"
    thr = g.get("threshold", 0.5)
    try:
        thr_pct = f"{(float(thr) * 100):.0f}%"
    except (TypeError, ValueError):
        thr_pct = "50%"
    mean_m = _num(g.get("mean_margin", 0.0))
    margin_s = f"{float(mean_m):+.2f} pts"
    crown = g.get("crown", "—")
    if crown == "complete":
        crown_h = ('<span class="badge promoted" '
                   'title="beat the champ head-to-head AND the duel field">'
                   'complete</span>')
    elif crown == "soft":
        crown_h = ('<span class="badge held" '
                   'title="took the throne without both edges">soft</span>')
    else:
        crown_h = '<span class="legend">—</span>'
    res = ('<span class="badge promoted">promoted ★</span>'
           if g.get("promoted") else '<span class="badge held">held</span>')
    expl = ' <span class="badge draw">exploiter</span>' if g.get("exploiter") else ""
    when = ""
    if g.get("finished_at"):
        when = (f'<div class="legend" title="{iso_time(g["finished_at"])} '
                f'· {fmt_dur(g.get("duration_s"))}">'
                f'{fmt_time(g["finished_at"])} · {fmt_dur(g.get("duration_s"))}</div>')
    return (
        f"<tr><td class=\"truncate\" title=\"{_esc(g.get('id'))}\">{_esc(g.get('id'))}{when}</td>"
        f"<td class=\"num\">{_num(g.get('train_return', 0.0)):.2f}</td>"
        f"<td class=\"num\">{_num(g.get('train_loss', 0.0)):.3f}</td>"
        f"<td><span class=\"rate-wrap rate-text\" "
        f"title=\"challenger W-D-L · Wilson lower bound (z=1.0) "
        f"{(g.get('wilson_lower', 0.0)):.2f} vs promotion threshold "
        f"{float(thr) if isinstance(thr, (int, float)) else thr} · "
        f"▲ {thr_pct} threshold\">"
        f"<span class=\"rate-bar\"><div style=\"width:{pct:.0f}%\"></div>"
        f"<span class=\"marker\" title=\"promotion threshold {thr}\" "
        f"style=\"left:{pct_of_thr(thr)}\"></span></span>"
        f"{wdl} · {rate} (draws count ½) · lower {_num(g.get('wilson_lower', 0.0)):.2f} · "
        f"<span title=\"mean eval margin, challenger-minus-champion\">margin {margin_s}</span>"
        f"<div class=\"dots\" title=\"per-duel margins: green win, blue draw, red loss\">"
        f"{dot_strip(g.get('margins'))}</div></span></td>"
        f"<td class=\"res-cell\">{res}<div class=\"legend\" style=\"margin:4px 0 0\">{_esc(g.get('reason', ''))}</div>{expl}</td>"
        f"<td>{crown_h}</td>"
        f"<td class=\"num legend truncate\" title=\"{_esc(g.get('arch'))} · {_esc(g.get('turns'))} turns\">"
        f"{_esc(g.get('arch'))} · {g.get('turns')} turns · γ {g.get('gamma')}</td></tr>")


def pct_of_thr(thr) -> str:
    try:
        return f"{(float(thr) * 100):.0f}%"
    except (TypeError, ValueError):
        return "50%"


def game_row_html(x: dict, member: str = "") -> str:
    """Twin of JS gameRow: gen · kind · matchup · result · replay."""
    seats = x.get("seats") or []
    ref = next((s for s in seats if s.get("id") == member), None) \
        if member else None
    ref = ref or (seats[0] if seats else {"id": "?", "result": "draw"})
    res = ref.get("result", "draw")
    if len(seats) <= 2:
        s0 = seats[0] if len(seats) > 0 else {"id": "?", "score": "?", "result": "draw"}
        s1 = seats[1] if len(seats) > 1 else {"id": "?", "score": "?", "result": "draw"}
        w0 = '<span class="winner">' + _esc(s0.get("id")) + '</span>' \
            if s0.get("result") == "win" else _esc(s0.get("id"))
        w1 = '<span class="winner">' + _esc(s1.get("id")) + '</span>' \
            if s1.get("result") == "win" else _esc(s1.get("id"))
        match = (f'<td class="matchup" title="engine score">'
                 f'{w0} {s0.get("score", "?")} – {s1.get("score", "?")} {w1}</td>')
    else:
        line = " · ".join(
            (('<span class="winner">' + _esc(s.get("id")) + " " +
              _esc(s.get("score")) + '</span>')
             if s.get("result") == "win"
             else _esc(s.get("id")) + " " + _esc(s.get("score")))
            for s in seats)
        pairs = " · ".join(
            f"{_esc(p.get('a'))} {p.get('score_a')}–{p.get('score_b')} {_esc(p.get('b'))}"
            for p in (x.get("pairs") or []))
        match = (f'<td class="matchup" title="engine scores, all {len(seats)} seats">'
                 f'{line}<div class="pairs">{pairs}</div></td>')
    names = " vs ".join(_esc(s.get("id")) for s in seats)
    label = replay_label(x.get("gen"), x.get("replay"))
    return (
        f"<tr><td>{_esc(x.get('gen'))}</td>"
        f"<td><span class=\"pill {_esc(x.get('kind'))}\">{_esc(x.get('kind'))}</span></td>"
        f"{match}<td><span class=\"badge {res}\">{res}</span></td>"
        f"<td class=\"replay\"><a href=\"/replay?f={_esc(x.get('replay'))}\" "
        f"target=\"_blank\" rel=\"noopener\" "
        f"title=\"{names}, gen {_esc(x.get('gen'))} — opens in a new tab\">"
        f"{_esc(label)}<span aria-hidden=\"true\"> ↗</span></a></td></tr>")


def pop_row_html(m: dict, champ) -> str:
    """Twin of JS popRow: id · role · parent · nash · W-D-L."""
    role = "seed" if m.get("role") == "main" else _esc(m.get("role"))
    star = ' <span class="champ-star">★</span>' if m.get("id") == champ else ""
    nash = m.get("nash", 0.0) or 0.0
    pct = float(nash) * 100
    bar = f"max({pct:.1f}%,{1 if nash > 0 else 0}px)"  # sub-1% still paints (P1-2)
    seed_note = ' <span class="legend">founding weights</span>' \
        if m.get("role") == "main" else ""
    return (
        f"<tr><td class=\"truncate\" title=\"{_esc(m.get('id'))}\">{_esc(m.get('id'))}{star}</td>"
        f"<td>{role}{seed_note}</td><td class=\"truncate\" title=\"{_esc(m.get('parent'))}\">"
        f"{_esc(m.get('parent') or '—')}</td>"
        f"<td><span class=\"nash-wrap\"><span class=\"nash-bar\">"
        f"<div style=\"width:{bar}\"></div></span>{pct:.1f}%</span></td>"
        f"<td class=\"num\">{m.get('wins', 0)}-{m.get('draws', 0)}-{m.get('losses', 0)}</td></tr>")


def map_row_html(m: dict) -> str:
    """Twin of JS mapRow."""
    return (
        f"<tr><td class=\"truncate\" title=\"{_esc(m.get('map') or MAP_UNLABELLED)}\">"
        f"{_esc(map_label(m.get('map')))}</td><td class=\"num\">{m.get('n', 0)}</td>"
        f"<td class=\"num\">{m.get('train', 0)}</td><td class=\"num\">{m.get('eval', 0)}</td>"
        f"<td class=\"num\">{m.get('cw', 0)}-{m.get('cd', 0)}-{m.get('cl', 0)}</td></tr>")


def pop_first_page(members: list, champ) -> list:
    """First paint mirrors the default view: Nash desc, zero-Nash hidden."""
    ranked = sorted(members, key=lambda m: -(m.get("nash", 0.0) or 0.0))
    return [m for m in ranked if (m.get("nash", 0.0) or 0.0) > 0]


# ---------------------------------------------------------------- PAGE


STYLES = """
:root{
  --bg:#F6F7F9; --card:#FFFFFF; --border:#E3E6EA; --border-strong:#C9CFD6;
  --ink:#16191D; --secondary:#5B6470; --muted:#67707B;
  --accent:#2456E0; --success:#18794E; --danger:#C4322B; --warn:#8A5A00;
  --eval-bg:#EAF0FE; --eval-ink:#2456E0; --train-bg:#EDEFF1; --train-ink:#5B6470;
  --grid:#E9EDF1; --chart-text:#6B7480;
}
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,Roboto,"Helvetica Neue",Arial,sans-serif;
  background:var(--bg); color:var(--ink); margin:0; padding:24px max(16px,4vw) 48px;}
.wrap{max-width:1720px; margin:0 auto;}
h1{font-size:20px; margin:0 0 4px;}
.sub{color:var(--secondary); font-size:13px; margin:0 0 20px;}
.section-title{font-size:14px; font-weight:700; text-transform:uppercase; letter-spacing:.06em;
  color:var(--secondary); margin:40px 0 12px;}
.section-title:first-of-type{margin-top:28px;}
.legend{font-size:12px; color:var(--muted); margin:-6px 0 12px;}
.stats{display:grid; grid-template-columns:repeat(3,1fr); gap:16px;}
.status-wide{grid-column:span 3;}
.card{background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px 20px;}
.stat-label{font-size:12px; color:var(--secondary);}
.stat-value{font-size:28px; font-weight:700; font-variant-numeric:tabular-nums; margin-top:2px;}
.stat-value .champ-star{font-size:20px;}
.champ-star{color:var(--warn); font-size:0.72em; vertical-align:1px;}
.progress{height:8px; background:var(--border); border-radius:4px; margin-top:10px; overflow:hidden;}
.progress>div{height:100%; background:var(--accent); border-radius:4px; transition:width .4s, background .4s;}
.status-line{font-size:14px; margin-top:2px;}
.charts{display:grid; grid-template-columns:repeat(3,1fr); gap:16px;}
.chart-card.chart-wide{grid-column:1/-1;}
.chart-card.chart-wide canvas{height:280px;}
.tables-2col{display:grid; grid-template-columns:1.35fr 1fr; gap:16px; align-items:start;}
.tables-2col.even{grid-template-columns:1fr 1fr;}
.res-cell{min-width:180px;}
.res-cell .badge{white-space:nowrap;}
.chart-card h3{margin:0 0 2px; font-size:14px;}
.chart-sub{font-size:12px; color:var(--muted); margin:0 0 8px;}
.chart-head{display:flex; justify-content:space-between; align-items:baseline;}
.chart-head #tenure-now{font-size:12px; font-weight:700; color:var(--accent); margin-left:8px; white-space:nowrap;}
.delta{font-size:12px; font-weight:700; padding:2px 8px; border-radius:20px;}
.delta.up{color:var(--success); background:#E6F4EC;}
.delta.down{color:var(--danger); background:#FBEAE8;}
.delta.flat{color:var(--secondary); background:var(--train-bg);}
canvas{width:100%; height:220px; display:block;}
.cols{display:grid; grid-template-columns:1fr 1.4fr; gap:16px; align-items:start;}
.table-scroll{overflow-x:auto;}
.table-tall{max-height:480px; overflow-y:auto;}
.table-tall thead th{position:sticky; top:0; z-index:1;}
table{border-collapse:collapse; width:100%; font-size:13.5px; font-variant-numeric:tabular-nums;}
th{background:#F1F3F5; text-align:left; font-size:12px; color:var(--secondary); font-weight:600;}
th,td{padding:9px 10px; border-bottom:1px solid var(--border);}
tr:last-child td{border-bottom:none;}
tbody tr:hover{background:#F8FAFC;}
td.num, th.num{text-align:right;}
.pill{display:inline-block; font-size:11px; font-weight:700; padding:2px 9px; border-radius:20px;}
.pill.eval{background:var(--eval-bg); color:var(--eval-ink);}
.pill.train{background:var(--train-bg); color:var(--train-ink);}
.badge{display:inline-block; font-size:11px; font-weight:700; padding:2px 9px; border-radius:20px;}
.badge.win{color:var(--success); background:#E6F4EC;}
.badge.loss{color:var(--danger); background:#FBEAE8;}
/* Badge palette (P2-6 — the whole page draws from these six, nowhere else):
   win green = ahead · loss red = behind · draw neutral-blue = tied first ·
   held amber = waiting (status, badges AND bars) · train gray = practice ·
   eval blue = promotion duels. Status is always text + color, never color alone. */
.badge.draw{color:var(--eval-ink); background:var(--eval-bg);}
.badge.promoted{color:var(--success); background:#E6F4EC;}
.badge.held{color:var(--warn); background:#FBF3E2;}
.nash-wrap{display:flex; align-items:center; gap:8px;}
.nash-bar{flex:1; min-width:60px; height:6px; background:var(--border); border-radius:3px; overflow:hidden;}
.nash-bar>div{height:100%; background:var(--accent);}
.rate-wrap{display:flex; align-items:center; gap:8px;}
td.matchup, td.replay, .rate-text{white-space:nowrap;}
.pairs{font-size:12px; color:var(--muted); margin-top:3px; white-space:normal;}
.rate-bar{flex:1 1 70px; min-width:70px; height:6px; background:var(--border); border-radius:3px; position:relative; overflow:hidden;}
.rate-bar>div{height:100%; background:var(--success);}
.rate-bar{overflow:visible;}
.rate-bar>div{border-radius:3px;}
.rate-bar .marker{position:absolute;left:0;width:2px;background:var(--ink);top:-3px;bottom:-3px;box-shadow:0 0 0 1px #fff;z-index:1;}
.toolbar{display:flex; gap:10px; align-items:center; margin-bottom:10px; flex-wrap:wrap;}
.toolbar label{font-size:13px; color:var(--secondary);}
select,input[list]{font-size:13px; padding:6px 10px; border:1px solid var(--border-strong); border-radius:8px; background:#fff;}
input[list]{min-width:140px;}
.clear-link{font-size:12px; white-space:nowrap;}
.live-toggle{display:flex; align-items:center; gap:6px; font-size:13px; color:var(--secondary);}
.pager{display:flex; gap:6px;}
.updated{font-size:12px; color:var(--muted); margin-left:auto;}
.pager button{font-size:12px; padding:5px 10px; border:1px solid var(--border-strong); border-radius:8px; background:#fff; cursor:pointer;}
.pager button:disabled{opacity:.4; cursor:default;}
#getting-started{margin-bottom:16px; font-size:14px;}
#stats-row{margin-top:0;}
.skip{position:absolute; left:-9999px; top:0; background:var(--ink); color:#fff; padding:8px 14px; z-index:99; border-radius:0 0 8px 0;}
.skip:focus{left:0; color:#fff;}
#error{display:none; background:#FBEAE8; color:var(--danger); border:1px solid #F0C4C0;
  border-radius:8px; padding:10px 14px; margin-bottom:16px; font-size:13px;}
.empty{padding:28px 20px; color:var(--secondary); font-size:14px;}
.empty code{background:#EFF1F4; padding:2px 6px; border-radius:4px; font-size:13px;}
a{color:var(--accent); text-decoration:none;}
a:hover{text-decoration:underline;}
.winner{font-weight:700;}
a:focus-visible,select:focus-visible,input:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:2px;}
caption{text-align:left; font-size:12px; color:var(--muted); padding:0 0 6px; caption-side:top;}
.hero{display:flex; gap:20px; align-items:center; flex-wrap:wrap;}
.hero-main{flex:2 1 320px; min-width:260px;}
.hero-side{flex:1 1 220px; min-width:200px;}
.hero-champ{font-size:30px; font-weight:800; font-variant-numeric:tabular-nums; margin:2px 0 4px;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
.hero-run{font-size:13px; color:var(--secondary); line-height:1.6; margin:4px 0 2px;}
#st-eta{margin:6px 0 0; line-height:1.6;}
.hero .progress{margin-top:12px;}
.strip{display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-top:16px;}
.mini{background:var(--card); border:1px solid var(--border); border-radius:10px; padding:10px 16px;}
.mini .stat-value{font-size:22px;}
.live-pill{font-size:12px; font-weight:700; padding:2px 10px; border-radius:20px; white-space:nowrap;}
.live-pill.ok{color:var(--success); background:#E6F4EC;}
.live-pill.stale{color:var(--warn); background:#FBF3E2;}
.live-pill.paused{color:var(--secondary); background:var(--train-bg);}
details.why{font-size:12.5px; color:var(--secondary); margin:-4px 0 12px;}
details.why summary{cursor:pointer; color:var(--accent); font-size:12.5px; display:inline-block;}
details.why p{margin:6px 0 0; max-width:90ch;}
.dots{margin-top:4px; letter-spacing:1px; font-size:10px; line-height:1.8; max-width:126px;}
.dot.w{color:var(--success);}
.dot.d{color:var(--eval-ink);}
.dot.l{color:var(--danger);}
td.truncate,.truncate{max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
tbody tr:nth-child(even){background:#FAFBFC;}
tbody tr:hover{background:#EFF4FA;}
.skel td{color:transparent !important;}
.skel td span{display:block; height:12px; border-radius:6px;
  background:linear-gradient(90deg,var(--border) 25%,#F1F3F5 50%,var(--border) 75%);
  background-size:200% 100%; animation:shimmer 1.2s infinite;}
@keyframes shimmer{to{background-position:-200% 0;}}
.footer{margin-top:40px; padding-top:12px; border-top:1px solid var(--border);
  font-size:12px; color:var(--muted); display:flex; gap:8px; flex-wrap:wrap;}
.footer .sep{opacity:.5;}
@media (max-width:1150px){
  .charts{grid-template-columns:1fr 1fr;}
  .chart-card.chart-wide{grid-column:1/-1;}
  .tables-2col,.tables-2col.even{grid-template-columns:1fr;}
}
@media (max-width:900px){
  .charts{grid-template-columns:1fr;}
  .strip{grid-template-columns:repeat(2,1fr);}
  .stats{grid-template-columns:repeat(2,1fr);}
  .stats>.card:nth-child(3){grid-column:span 2;}
  .status-wide{grid-column:span 2;}
  .cols{grid-template-columns:1fr;}
  body{padding:16px 16px 40px;}
}
"""

SCRIPT = """
let S=null, seq=0, lastHash="", lastGames="", live=true, lastTick=0;
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
async function fetchJSON(url){
  let r;
  try{r=await fetch(url);}
  catch(e){throw new Error("connection lost: "+e.message);}
  if(!r.ok){
    let detail="";
    try{const body=await r.json();if(body&&body.error)detail=": "+String(body.error).slice(0,140);}
    catch(e){}
    const kind=r.status>=500?"dashboard error":"request failed";
    throw new Error(kind+" HTTP "+r.status+detail+" on "+url);
  }
  return r.json();
}
function ago(ts){const s=Math.max(0,Math.round((Date.now()-ts)/1000));
  return s<2?"just now":s+"s ago";}
function shortReplay(rel){const p=(rel||"").split("/").filter(Boolean);
  return p.length>=3?p[p.length-3]:(p.pop()||"").replace(/\\.replay$/,"");}
function seatBadge(result){
  return {cls:result,label:result};
}
/* P0-6 timestamps: HH:MM today, MMM d + HH:MM older, ISO in title. */
function fmtTime(ts){
  if(ts===null||ts===undefined)return "—";
  const d=new Date(ts*1000),now=new Date();
  const hm=d.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});
  if(d.toDateString()===now.toDateString())return hm;
  return d.toLocaleDateString([], {month:"short",day:"numeric"})+", "+hm;
}
function isoT(ts){
  if(ts===null||ts===undefined)return "";
  return new Date(ts*1000).toISOString();
}
/* P1-5 durations: always tagged — `220 s`, past 60s `3m 40s`. */
function fmtDur(s){
  if(s===null||s===undefined||!Number.isFinite(+s))return "—";
  s=+s;
  if(s<60)return Math.round(s)+" s";
  const m=Math.floor(s/60);
  return m+"m "+String(Math.round(s-m*60)).padStart(2,"0")+"s";
}
function replayLabel(gen,rel){
  return "gen "+gen+" · "+shortReplay(rel)+" →";
}
/* P2-4 dot strip: per-duel W/D/L dots, green/blue/red with pts titles. */
function dotStrip(margins,cap){
  cap=cap||20;
  const ms=(margins||[]).filter(v=>Number.isFinite(v));
  if(!ms.length)return '<span class="legend">no duels</span>';
  const step=Math.max(1,Math.ceil(ms.length/cap));
  let out="";
  for(let i=0;i<ms.length&&out.split("●").length-1<cap;i+=step){
    const m=ms[i],cls=m>0?"w":(m===0?"d":"l"),
      word=m>0?"win":(m===0?"draw":"loss");
    out+=`<span class="dot ${cls}" title="${word} ${m>0?"+"+m:m} pts">●</span>`;
  }
  return out;
}
/* P1-4 envelope downsampling: one min/max segment per pixel column, so
   1690 overlapping points read as density instead of overplotted ink.
   Nulls split runs; x stays mapped to generation index via N. */
function envLine(F,arr,color,width,N){
  N=N||arr.length;
  const{ctx,X,Y,W,L,R}=F;
  const cols=Math.max(40,Math.floor(W-L-R));
  const per=N/cols;
  ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineJoin="round";
  ctx.globalAlpha=width<=1?0.55:1;
  let started=false;
  ctx.beginPath();
  for(let c=0;c<cols;c++){
    let mn=Infinity,mx=-Infinity,gi=-1;
    const lo=Math.floor(c*per),hi=Math.min(N,Math.floor((c+1)*per)+1);
    for(let i=lo;i<hi;i++){
      const v=arr[i];
      if(v===null||v===undefined||!Number.isFinite(v))continue;
      if(v<mn)mn=v; if(v>mx)mx=v; gi=i;
    }
    if(gi<0){started=false;continue;}
    const xx=N<2?(L+W-R)/2:X(gi);
    if(mx-mn>1e-12){
      ctx.moveTo(xx,Y(mx));ctx.lineTo(xx,Y(mn));
      if(width>1){ctx.stroke();ctx.beginPath();started=false;}
    }
    const mid=(mn+mx)/2;
    if(!started){ctx.moveTo(xx,Y(mid));started=true;}
    else ctx.lineTo(xx,Y(mid));
  }
  ctx.stroke();ctx.globalAlpha=1;
}
/* P1-4 aria cap: `series, N points, min .., max .., last ..`. */
function adesc(name,arr,ids){
  const have=[];
  arr.forEach((v,i)=>{if(v!==null&&Number.isFinite(v))have.push([v,i]);});
  if(!have.length)return name+", no data yet";
  let mn=have[0],mx=have[0];
  have.forEach(p=>{if(p[0]<mn[0])mn=p; if(p[0]>mx[0])mx=p;});
  const last=have[have.length-1];
  const f=v=>(Math.round(v*100)/100);
  return `${name}, ${arr.length} points, min ${f(mn[0])} at ${(ids||[])[mn[1]]||mn[1]}, `+
    `max ${f(mx[0])} at ${(ids||[])[mx[1]]||mx[1]}, last ${f(last[0])}`;
}
/* P1-4 delta chip: last value vs median of the previous 10, with tooltip. */
function deltaChip(id,arr){
  const el=$(id);
  if(!el)return;
  const have=arr.filter(v=>v!==null&&Number.isFinite(v));
  if(have.length<2){el.style.display="none";return;}
  const last=have[have.length-1];
  const prev=have.slice(-11,-1);
  const s=[...prev].sort((a,b)=>a-b);
  const med=s.length%2?s[s.length>>1]:(s[s.length/2-1]+s[s.length/2])/2;
  const d=last-med;
  const cls=Math.abs(d)<1e-9?"flat":(d>0?"up":"down");
  const arrow=cls==="flat"?"→":(cls==="up"?"▲ +":"▼ ");
  el.style.display="";
  el.className="delta "+cls;
  el.textContent=arrow+(Math.abs(d)<1e-9?"0":(Math.round(Math.abs(d)*100)/100));
  el.title=`last ${Math.round(last*100)/100} vs median of previous ${prev.length} gens (${Math.round(med*100)/100})`;
}
/* P0-3 guards: never clobber a table the reader is using; keep its scroll. */
function tableBusy(id){
  const el=$(id);
  return el.matches(":hover")||el.contains(document.activeElement);
}
function keepScroll(scroller,fn){
  const top=scroller?scroller.scrollTop:0;
  fn();
  if(scroller)scroller.scrollTop=top;
}
/* Board charts: shared frame geometry, gridlines, min/max labels, headroom, HiDPI. */
function clock(ts){const d=new Date(ts*1000);return d.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});}
function renderHeader(){
  $("st-champ").innerHTML=esc(S.champion||"—")+(S.champion?' <span class="champ-star">★</span>':"");
  $("getting-started").style.display=S.counts.generations?"none":"block";
  $("st-gen").textContent=S.counts.generations;
  $("st-games").textContent=S.counts.games;
  $("st-members").textContent=(S.members||[]).length;
  $("st-maps").textContent=(S.maps||[]).length;
  const r=S.run||{};
  const tgt=(typeof r.target==="number")?r.target:null;
  // P0-5: once finished >= target say so and suppress the ETA.
  if(tgt!==null&&r.finished>=tgt)
    $("st-run").textContent=`gen ${r.finished} · target ${tgt} reached`;
  else if(tgt!==null)
    $("st-run").textContent=`gen ${r.finished} · target ${tgt}`;
  else $("st-run").textContent=`gen ${r.finished||0}`;
  const bits=[];
  if(r.last_finished_at) bits.push("last finished "+fmtTime(r.last_finished_at));
  if(r.avg_s) bits.push(`avg ${r.avg_s}s/gen`);
  if(!(tgt!==null&&r.finished>=tgt)&&tgt!==null&&r.avg_s&&tgt>r.finished)
    bits.push(`ETA ${fmtTime(Date.now()/1000+(tgt-r.finished)*r.avg_s)}`);
  $("st-eta").textContent=bits.join(" · ")||"no timing data yet";
  $("st-eta").title=r.last_finished_at?("last finished "+isoT(r.last_finished_at)):"";
  const st=S.status||{},el=$("st-status"),bar=$("st-bar"),wrap=$("st-barwrap");
  let pct=0;
  bar.style.background="var(--accent)";
  if(st.phase==="train"){
    el.innerHTML=`training <b>${esc(st.challenger||"")}</b> · game ${Math.max(0,+st.done||0)}/${Math.max(0,+st.total||0)} · last mean return <b>${(+st.last_mean_return||0).toFixed(2)}</b>`;
    pct=100*st.done/Math.max(1,st.total);
  }else if(st.phase==="eval"){
    el.innerHTML=`evaluating <b>${esc(st.challenger||"")}</b> · duel ${Math.max(0,+st.done||0)}/${Math.max(0,+st.total||0)} · <b>${Math.max(0,+st.wins||0)}W ${Math.max(0,+st.draws||0)}D</b> so far`;
    pct=100*st.done/Math.max(1,st.total);
  }else if(st.phase==="done"){
    el.innerHTML=`last run finished: <b>${esc(st.challenger||"")}</b> `+
      (st.promoted?'<span class="badge promoted">promoted ★</span>':'<span class="badge held">held</span>')+
      ` · champion ${esc(st.champion||"")} · idle, waiting for the next run`;
    pct=100;
    // Held stays amber everywhere, including the bar (P2-6).
    bar.style.background=st.promoted?"var(--success)":"var(--warn)";
  }else{
    el.innerHTML=S.counts.generations?`idle · last champion ${esc(S.champion||"—")}`:"waiting for the first generation…";
  }
  bar.style.width=pct+"%";
  wrap.setAttribute("aria-valuenow",Math.round(pct));
  renderPill();
}
function renderPill(){
  // P1-7 status pill: text + color, never color alone.
  const el=$("live-pill");
  if(!el)return;
  const ageS=Math.max(0,Math.round((Date.now()-lastTick)/1000));
  if(!live){el.className="live-pill paused";el.textContent="○ paused";return;}
  const interval=activePhase()?5:15;
  if(ageS>2*interval){el.className="live-pill stale";el.textContent=`▲ stale ${ageS}s`;}
  else{el.className="live-pill ok";el.textContent=`● live · refreshed ${ageS}s ago`;}
  $("updated").textContent="updated "+ago(lastTick)+" · "+(live?"live":"paused");
}
function lineInto(F,arr,color,width){
  // One series with null gaps: moveTo restarts the path after a gap.
  const{ctx,X,Y}=F;
  ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineJoin="round";
  ctx.beginPath();
  let started=false;
  arr.forEach((v,i)=>{
    if(v===null||!Number.isFinite(v)){started=false;return;}
    if(!started){ctx.moveTo(X(i),Y(v));started=true;}
    else ctx.lineTo(X(i),Y(v));
  });
  ctx.stroke();
}
function frame(id,lists,labels,desc,opt){
  // Shared geometry for the board charts: spans every series, draws the
  // grid + zero line + end labels, returns mappers (null: nothing to draw).
  // opt: {yt} y-axis title in the gutter, {ticks} [[genIdx,label]] extras
  // marking champion changes between first and last (P1-4).
  const cv=$(id),ctx=cv.getContext("2d");
  const vals=[];
  lists.forEach(a=>(a||[]).forEach(v=>{if(v!==null&&Number.isFinite(v))vals.push(v);}));
  const dpr=window.devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;
  cv.width=W*dpr;cv.height=H*dpr;ctx.scale(dpr,dpr);
  ctx.clearRect(0,0,W,H);
  cv.setAttribute("role","img");
  if(!vals.length){ctx.fillStyle="#8A94A0";ctx.font="12px system-ui";
    ctx.fillText("no data yet",12,20);return null;}
  if(desc)cv.setAttribute("aria-label",desc);
  let mn=Math.min(...vals),mx=Math.max(...vals);
  if(mx-mn<1e-9){mn-=1;mx+=1;}
  const pad=(mx-mn)*0.12;mn-=pad;mx+=pad;
  const prec=(mx-mn)<0.5?3:2;
  const L=48,R=8,T=8,B=20,iw=W-L-R,ih=H-T-B;
  const n=Math.max(...lists.map(a=>(a||[]).length),1);
  const X=i=>L+iw*(n<2?0.5:i/(n-1));
  const Y=x=>T+ih*(1-(x-mn)/(mx-mn));
  ctx.strokeStyle="#E9EDF1";ctx.fillStyle="#6B7480";ctx.font="10px system-ui";ctx.lineWidth=1;
  for(let k=0;k<=3;k++){const t=mn+(mx-mn)*k/3,y=Y(t);
    ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(W-R,y);ctx.stroke();
    let s=t.toFixed(prec);if(s==="-0.000"||s==="-0.00")s=s.slice(1);
    ctx.fillText(s,4,y+3);}
  if(mn<0&&mx>0){ctx.save();ctx.setLineDash([4,3]);ctx.strokeStyle="#C9CFD6";
    ctx.beginPath();ctx.moveTo(L,Y(0));ctx.lineTo(W-R,Y(0));ctx.stroke();ctx.restore();}
  const x0=(labels&&labels[0])||"gen 0";
  const x1=(labels&&labels[labels.length-1])||("gen "+(n-1));
  ctx.fillText(x0,L,H-6);
  const w1=ctx.measureText(x1).width;
  ctx.fillText(x1,W-R-w1,H-6);
  const ticks=(opt&&opt.ticks)||[];
  let lastTx=-1e9;
  ticks.forEach(t=>{
    const tx=X(t[0]);
    if(tx-lastTx<44||W-R-tx<ctx.measureText(t[1]).width+2)return;
    lastTx=tx;
    ctx.fillStyle="#8A94A0";
    ctx.fillText(t[1],tx,H-6);
    ctx.strokeStyle="#C9CFD6";ctx.setLineDash([2,3]);
    ctx.beginPath();ctx.moveTo(tx,T);ctx.lineTo(tx,H-B);ctx.stroke();
    ctx.setLineDash([]);ctx.fillStyle="#6B7480";
  });
  if(opt&&opt.yt){
    ctx.save();ctx.translate(10,T+ih/2);ctx.rotate(-Math.PI/2);
    ctx.textAlign="center";ctx.fillStyle="#5B6470";
    ctx.fillText(opt.yt,0,0);ctx.restore();
  }
  return{ctx,W,H,X,Y,L,R,T,B,n};
}
function plotLines(id,arrs,colors,widths,labels,desc,opt){
  const F=frame(id,arrs,labels,desc,opt);
  if(!F)return;
  arrs.forEach((a,k)=>smoothLine(F,a,colors[k],widths[k]));
}
function smoothLine(F,arr,color,width){
  // Exact path for short series, envelope for crowded ones (P1-4).
  const cols=Math.max(40,Math.floor(F.W-F.L-F.R));
  if((arr||[]).length<=cols)lineInto(F,arr,color,width);
  else envLine(F,arr,color,width);
}
function band(F,lo,hi,fill){
  // Fill between hi and lo, restarting at null gaps (shared by the
  // margin IQR band and the knock rate panel).
  const{ctx,X,Y}=F;
  ctx.fillStyle=fill;
  let run=[];
  const flush=()=>{
    if(run.length>1){ctx.beginPath();
      run.forEach((i,k)=>k?ctx.lineTo(X(i),Y(hi[i])):ctx.moveTo(X(i),Y(hi[i])));
      [...run].reverse().forEach(i=>ctx.lineTo(X(i),Y(lo[i])));
      ctx.closePath();ctx.fill();}
    else if(run.length===1){const i=run[0];
      ctx.fillRect(X(i)-1,Y(hi[i]),2,Math.max(1,Y(lo[i])-Y(hi[i])));}
    run=[];};
  hi.forEach((h,i)=>{
    if(h===null||!Number.isFinite(h)||lo[i]===null||!Number.isFinite(lo[i]))flush();
    else run.push(i);});
  flush();
}
function plotBand(id,med,q1,q3,color,fill,labels,desc,opt){
  const F=frame(id,[med,q1,q3],labels,desc,opt);
  if(!F)return;
  band(F,q1,q3,fill);
  smoothLine(F,med,color,2);
}
function plotTicks(id,knock,labels,desc){
  // Binary per-gen knock lane: one tick per gen, same x-geometry as the
  // rate panel below (L=48/R=8) so marks line up with the curves.
  // 1690 ticks overplot, so knocks draw tall at alpha .55 (the envelope
  // reads as density) and holds draw short and faint; no-eval gens gap.
  const cv=$(id),ctx=cv.getContext("2d");
  const dpr=window.devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;
  cv.width=W*dpr;cv.height=H*dpr;ctx.scale(dpr,dpr);
  ctx.clearRect(0,0,W,H);
  cv.setAttribute("role","img");
  if(desc)cv.setAttribute("aria-label",desc);
  const L=48,R=8,T=6,B=16,n=Math.max(knock.length,1);
  const X=i=>L+(W-L-R)*(n<2?0.5:i/(n-1));
  ctx.strokeStyle="#E9EDF1";ctx.fillStyle="#6B7480";ctx.font="10px system-ui";ctx.lineWidth=1;
  ctx.beginPath();ctx.moveTo(L,H-B);ctx.lineTo(W-R,H-B);ctx.stroke();
  ctx.fillText("knock",4,T+6);
  ctx.fillText("held",4,H-B);
  const slot=n<2?20:(W-L-R)/n;
  const bw=Math.max(1,Math.min(4,slot*0.7));
  knock.forEach((k,i)=>{
    if(k===null||k===undefined)return;
    if(k){
      ctx.fillStyle="rgba(36,86,224,.55)";
      ctx.fillRect(X(i)-bw/2,T,bw,H-B-T);
    }else{
      ctx.fillStyle="rgba(91,100,112,.30)";
      ctx.fillRect(X(i)-bw/2,H-B-6,bw,6);
    }
  });
  const x0=(labels&&labels[0])||"gen 0";
  const x1=(labels&&labels[labels.length-1])||("gen "+(n-1));
  ctx.fillStyle="#6B7480";
  ctx.fillText(x0,L,H-4);
  const w1=ctx.measureText(x1).width;
  ctx.fillText(x1,W-R-w1,H-4);
}
function plotKnock(id,K,labels,desc,opt){
  // Rate panel under the marks lane: knock-rate (blue) and conversion
  // (green) lines with Wilson bands, one shared frame.
  const F=frame(id,[K.rate,K.lo,K.hi,K.conv,K.clo,K.chi],labels,desc,opt);
  if(!F)return;
  band(F,K.lo,K.hi,"rgba(36,86,224,.18)");
  band(F,K.clo,K.chi,"rgba(24,121,78,.16)");
  smoothLine(F,K.rate,"#2456E0",2);
  smoothLine(F,K.conv,"#18794E",2);
}
function plotNorm(id,norm,raw,labels,desc){
  // Normalized lane (0..1 geometry) labeled with the TRUE min/max so
  // the scale is never a lie: near-constant stretches fill the lane
  // and the axis still reads in real units.
  const F=frame(id,[norm],labels,desc);
  if(!F)return;
  const{ctx,X,Y,W,H,T,B}=F;
  const have=(raw||[]).filter(v=>v!==null&&Number.isFinite(v));
  if(have.length){
    const mn=Math.min(...have),mx=Math.max(...have);
    ctx.save();ctx.fillStyle="#5B6470";ctx.textAlign="right";
    ctx.fillText("max "+mx.toFixed(2),W-2,T+10);
    ctx.fillText("min "+mn.toFixed(2),W-2,H-B-4);
    ctx.restore();
  }
  ctx.fillStyle="rgba(22,25,29,.08)";
  let run=[];
  const flush=()=>{
    if(run.length>1){ctx.beginPath();
      run.forEach((i,k)=>k?ctx.lineTo(X(i),Y(norm[i])):ctx.moveTo(X(i),Y(norm[i])));
      ctx.lineTo(X(run[run.length-1]),Y(0));ctx.lineTo(X(run[0]),Y(0));
      ctx.closePath();ctx.fill();}
    run=[];};
  norm.forEach((v,i)=>{if(v===null||!Number.isFinite(v))flush();else run.push(i);});
  flush();
  smoothLine(F,norm,"#16191D",2.5);
}
function plotBars(id,groups,colors,labels,desc,whisk,opt){
  // groups: one array per bar series; whisk: matching [lo,hi] pairs.
  const all=groups.slice();
  if(whisk)whisk.forEach(w=>{if(w){all.push(w[0],w[1]);}});
  const F=frame(id,all,labels,desc,opt);
  if(!F)return;
  const{ctx,X,Y,W,L,R}=F,n=F.n,g=groups.length;
  const slot=n<2?20:Math.min(20,(W-L-R)/n);
  const bw=Math.max(1,slot/(g+0.5));
  groups.forEach((arr,s)=>{
    ctx.fillStyle=colors[s];
    arr.forEach((v,i)=>{
      if(v===null||!Number.isFinite(v))return;
      const cx=X(i)-slot/2+bw*(s+0.25),y0=Y(0),y1=Y(v);
      ctx.fillRect(cx,Math.min(y0,y1),bw,Math.abs(y1-y0)||1);
      if(whisk&&whisk[s]&&whisk[s][0][i]!==null&&whisk[s][1][i]!==null
         &&Number.isFinite(whisk[s][0][i])){
        ctx.strokeStyle="#16191D";ctx.lineWidth=1;
        ctx.beginPath();ctx.moveTo(cx+bw/2,Y(whisk[s][1][i]));
        ctx.lineTo(cx+bw/2,Y(whisk[s][0][i]));ctx.stroke();
      }
    });
  });
}
function plotDual(id,a,amed,b,bmed,labels,desc,opt){
  // Left axis: a (ratio). Right axis: b (entropy), drawn in green.
  const F=frame(id,[a,amed],labels,desc,opt);
  if(!F)return;
  const{ctx,X,W,R,H,T,B}=F;
  const bv=[];
  [b,bmed].forEach(x=>(x||[]).forEach(v=>{if(v!==null&&Number.isFinite(v))bv.push(v);}));
  if(!bv.length){lineInto(F,a,"#E8A0A6",1);lineInto(F,amed,"#C4322B",2);return;}
  let mn=Math.min(...bv),mx=Math.max(...bv);
  if(mx-mn<1e-9){mn-=1;mx+=1;}
  const pad=(mx-mn)*0.12;mn-=pad;mx+=pad;
  const ih=H-T-B;
  const Y2=x=>T+ih*(1-(x-mn)/(mx-mn));
  ctx.save();ctx.fillStyle="#18794E";ctx.textAlign="right";
  for(let k=0;k<=3;k++){const t=mn+(mx-mn)*k/3;
    ctx.fillText(t.toFixed(2),W-2,Y2(t)+3);}
  ctx.restore();
  lineInto({ctx,X,Y:Y2},b,"#9EC5A6",1);
  lineInto({ctx,X,Y:Y2},bmed,"#18794E",2);
  smoothLine(F,a,"#E8A0A6",1);
  smoothLine(F,amed,"#C4322B",2);
}
function plotStrip(id,tenure,turnover,nplayer,labels,desc){
  const F=frame(id,[tenure],labels,desc);
  if(!F)return;
  const{ctx,X,Y,W,R,T}=F,n=F.n;
  if(nplayer!==null&&nplayer!==undefined&&nplayer<n){
    ctx.fillStyle="rgba(36,86,224,.12)";
    ctx.fillRect(X(nplayer),T,W-R-X(nplayer),F.H-F.T-F.B);
    ctx.fillStyle="#2456E0";ctx.font="10px system-ui";
    ctx.fillText("N-player",X(nplayer)+4,T+12);
  }
  const slot=n<2?20:Math.min(20,(W-F.L-R)/n);
  ctx.fillStyle="#2456E0";
  tenure.forEach((v,i)=>{
    if(v===null||!Number.isFinite(v))return;
    const y1=Y(v),bw=Math.max(2,slot*0.7);
    ctx.fillRect(X(i)-bw/2,y1,bw,Math.max(1,Y(0)-y1));
  });
  turnover.forEach((t,i)=>{
    if(!t)return;
    const cx=X(i),cy=T+10,s=6;
    ctx.beginPath();ctx.moveTo(cx,cy-s);ctx.lineTo(cx+s,cy);
    ctx.lineTo(cx,cy+s);ctx.lineTo(cx-s,cy);ctx.closePath();
    ctx.fillStyle="#C4322B";ctx.fill();
    ctx.lineWidth=2;ctx.strokeStyle="#FFFFFF";ctx.stroke();
  });
}
function changeTicks(B,ids){
  // Champion-change gens label the x-axis between first and last (P1-4).
  const to=(B.reign&&B.reign.turnover)||[];
  let idx=[];
  to.forEach((t,i)=>{if(t)idx.push(i);});
  if(idx.length>8){const step=Math.ceil(idx.length/8);idx=idx.filter((_,k)=>k%step===0);}
  return idx.map(i=>[i,ids[i]||("gen "+i)]);
}
function renderBoard(){
  const B=S.board,ids=B.ids;
  const refIds=B.elo.panel||[];
  const ticks=changeTicks(B,ids);
  plotLines("ch-elo",[...refIds.map(pid=>((B.elo.refs||{})[pid]||[])),B.elo.cand,B.elo.champ],[...refIds.map(()=>"#C9CFD6"),"#9EC5FE","#2456E0"],[...refIds.map(()=>1),1.5,2],ids,
    adesc("candidate vs defending-champion causal Elo",B.elo.cand||[],ids),{yt:"Elo",ticks});
  deltaChip("d-elo",B.elo.cand||[]);
  const tn=(B.elo.turn_note||[]).map(r=>`${r.from}–${r.to}: train ${r.train_turns} vs eval ${r.eval_turns} turns`).join("; ");
  $("elo-turn").textContent=tn?`turn confound (${tn}) — mixed, not corrected`:
    "train+eval fit: turn counts match across eras";
  plotTicks("ch-knock-marks",B.knock.knock,ids,"knock marks, "+B.knock.knock.length+" gens");
  plotKnock("ch-knock",B.knock,ids,adesc("knock rate",B.knock.rate||[],ids),{yt:"rate",ticks});
  deltaChip("d-knock",B.knock.rate||[]);
  plotLines("ch-dec",[B.decisive.train,B.decisive.train_ma,B.decisive.eval,B.decisive.eval_ma],
    ["#E8A0A6","#C4322B","#9EC5FE","#2456E0"],[1,2,1,2],ids,
    adesc("decisiveness train vs eval",B.decisive.train||[],ids),{yt:"frac",ticks});
  deltaChip("d-dec",B.decisive.train_ma||[]);
  plotBand("ch-marg",B.margin.med,B.margin.q1,B.margin.q3,"#2456E0","rgba(36,86,224,.15)",ids,
    adesc("eval margin median",B.margin.med||[],ids),{yt:"pts",ticks});
  deltaChip("d-marg",B.margin.med||[]);
  plotDual("ch-pg",B.pg.ratio,B.pg.ratio_med,B.pg.entropy,B.pg.entropy_med,ids,
    adesc("PG signal ratio",B.pg.ratio||[],ids),{yt:"ratio",ticks});
  deltaChip("d-pg",B.pg.ratio_med||[]);
  plotBars("ch-vslope",[B.vslope],["#8A5A00"],ids,
    adesc("value-fit slope",B.vslope||[],ids),null,{yt:"slope",ticks});
  deltaChip("d-vsl",B.vslope||[]);
  plotStrip("ch-tenure",B.reign.tenure,B.reign.turnover,B.regimes.nplayer,ids,
    adesc("tenure",B.reign.tenure||[],ids));
  $("tenure-now").textContent=B.reign.readout||"";
  plotNorm("ch-entlane",B.reign.entropy_n,B.reign.entropy,ids,
    adesc("Nash entropy",B.reign.entropy||[],ids));
}
const PAGE=100;
let genPage=0, popPage=0, lastGens="", lastPop="", lastMaps="";
function genFiltered(){
  // P1-3: the member input filters generations too (challenger OR champ).
  const m=$("member").value.trim();
  return (S.generations||[]).filter(g=>!m||g.id===m||g.champion===m);
}
function genRow(g){
  // Twin of Python gen_row_html — keep both sides in step.
  const pct=g.eval_games?100*g.win_rate:0;
  const losses=Math.max(0,g.eval_games-g.eval_w-g.eval_d);
  const thr=(typeof g.threshold==="number")?g.threshold:0.5;
  const margin=(typeof g.mean_margin==="number")?g.mean_margin:0;
  const crown=g.crown==="complete"
    ?'<span class="badge promoted" title="beat the champ head-to-head AND the duel field">complete</span>'
    :g.crown==="soft"
    ?'<span class="badge held" title="took the throne without both edges">soft</span>'
    :'<span class="legend">—</span>';
  const when=g.finished_at
    ?`<div class="legend" title="${esc(isoT(g.finished_at))} · ${fmtDur(g.duration_s)}">${fmtTime(g.finished_at)} · ${fmtDur(g.duration_s)}</div>`:"";
  return `<tr><td class="truncate" title="${esc(g.id)}">${esc(g.id)}${when}</td>`+
  `<td class="num">${(+g.train_return||0).toFixed(2)}</td>`+
  `<td class="num">${(+g.train_loss||0).toFixed(3)}</td>`+
  `<td><span class="rate-wrap rate-text" title="challenger W-D-L · Wilson lower bound (z=1.0) ${g.wilson_lower.toFixed(2)} vs promotion threshold ${thr.toFixed(2)} · ▲ ${(thr*100).toFixed(0)}% threshold"><span class="rate-bar"><div style="width:${pct.toFixed(0)}%"></div>`+
  `<span class="marker" style="left:${(thr*100).toFixed(0)}%" title="promotion threshold ${thr.toFixed(2)}"></span></span>`+
  `${g.eval_w}-${g.eval_d}-${losses} · ${(g.win_rate*100).toFixed(1)}% (draws count ½) · lower ${g.wilson_lower.toFixed(2)} · `+
  `<span title="mean eval margin, challenger-minus-champion">margin ${margin>=0?"+"+margin.toFixed(2):margin.toFixed(2)} pts</span>`+
  `<div class="dots" title="per-duel margins: green win, blue draw, red loss">${dotStrip(g.margins)}</div></span></td>`+
  `<td class="res-cell">${g.promoted?'<span class="badge promoted">promoted ★</span>':'<span class="badge held">held</span>'}`+
  `<div class="legend" style="margin:4px 0 0">${esc(g.reason)}</div>`+(g.exploiter?` <span class="badge draw">exploiter</span>`:'')+`</td>`+
  `<td>${crown}</td>`+
  `<td class="num legend truncate" title="${esc(g.arch)} · ${g.turns} turns">${esc(g.arch)} · ${g.turns} turns · γ ${g.gamma}</td></tr>`;
}
function renderPopulation(){
  if(tableBusy("pop-body"))return; // P0-3: reader busy, retry next poll
  // P1-2: Nash desc, zero-Nash hidden by default, % at 1dp, ≥1px bars.
  const hide=$("hide-zero")&&$("hide-zero").checked;
  const ranked=[...(S.members||[])].sort((a,b)=>(b.nash||0)-(a.nash||0));
  const vis=hide?ranked.filter(m=>(m.nash||0)>0):ranked;
  const pages=Math.max(1,Math.ceil(vis.length/PAGE));
  popPage=Math.min(popPage,pages-1);
  const h=hide+"|"+popPage+"|"+JSON.stringify(vis.slice(popPage*PAGE,popPage*PAGE+PAGE));
  if(h===lastPop)return; // unchanged: keep focus, selection, scroll
  lastPop=h;
  const rows=vis.slice(popPage*PAGE,popPage*PAGE+PAGE).map(m=>popRow(m)).join("");
  keepScroll($("pop-scroll"),()=>{
    $("pop-body").innerHTML=rows||'<tr><td colspan="5" class="empty">no checkpoints yet — start a generation</td></tr>';
  });
  const page=Math.min(popPage+1,pages);
  const shown=vis.slice(popPage*PAGE,popPage*PAGE+PAGE).length;
  $("pop-count").textContent=`showing ${shown} of ${vis.length} · page ${page} of ${pages}`;
  $("pop-prev").disabled=popPage<=0;
  $("pop-next").disabled=popPage+1>=pages;
}
function popRow(m){
  // Twin of Python pop_row_html.
  const role=m.role==="main"?"seed":m.role;
  const pct=(m.nash||0)*100;
  const bar=`max(${pct.toFixed(1)}%,${(m.nash||0)>0?1:0}px)`;
  return `<tr><td class="truncate" title="${esc(m.id)}">${esc(m.id)}${m.id===S.champion?' <span class="champ-star">★</span>':""}</td>`+
  `<td>${esc(role)}${m.role==="main"?' <span class="legend">founding weights</span>':""}</td><td class="truncate" title="${esc(m.parent||"")}">${esc(m.parent||"—")}</td>`+
  `<td><span class="nash-wrap"><span class="nash-bar"><div style="width:${bar}"></div></span>${pct.toFixed(1)}%</span></td>`+
  `<td class="num">${m.wins}-${m.draws}-${m.losses}</td></tr>`;
}
function renderGenerations(){
  if(tableBusy("gen-body"))return; // P0-3: reader busy, retry next poll
  const vis=genFiltered();
  const pages=Math.max(1,Math.ceil(vis.length/PAGE));
  genPage=Math.min(genPage,pages-1);
  const h=$("member").value+"|"+genPage+"|"+JSON.stringify(vis.slice(genPage*PAGE,genPage*PAGE+PAGE));
  if(h===lastGens)return; // unchanged: keep focus, selection, scroll
  lastGens=h;
  const rows=vis.slice(genPage*PAGE,genPage*PAGE+PAGE).map(g=>genRow(g)).join("");
  keepScroll($("gen-scroll"),()=>{
    $("gen-body").innerHTML=rows||($("member").value
      ?`<tr><td colspan="7" class="empty">no generations for ${esc($("member").value)} yet — <a href="#" class="js-clear">clear filter</a></td></tr>`
      :'<tr><td colspan="7" class="empty">no completed generations yet</td></tr>');
  });
  bindClear();
  const page=Math.min(genPage+1,pages);
  $("gen-count").textContent=`showing ${vis.slice(genPage*PAGE,genPage*PAGE+PAGE).length} of ${vis.length} · page ${page} of ${pages}`;
  $("gen-prev").disabled=genPage<=0;
  $("gen-next").disabled=genPage+1>=pages;
}
function memberIds(){return S.members.map(m=>m.id);}
function renderMemberOptions(){
  // P0-3: text input + datalist (native autocomplete, keyboard-friendly).
  // The input keeps its own value/focus: only the option list refreshes.
  const dl=$("member-list"),ids=memberIds();
  const h=JSON.stringify(ids);
  if(h===dl.dataset.ids)return;
  dl.dataset.ids=h;
  dl.innerHTML=ids.map(id=>`<option value="${esc(id)}">`).join("");
  syncClear();
}
function syncClear(){
  // The clear-filter link is always one click away (P0-4).
  const has=!!$("member").value;
  $("clear-filter").style.display=has?"":"none";
}
function bindClear(){
  document.querySelectorAll(".js-clear").forEach(a=>{
    if(a.dataset.bound)return;
    a.dataset.bound="1";
    a.addEventListener("click",e=>{e.preventDefault();clearMember();});
  });
}
function clearMember(){
  $("member").value="";
  gamesOffset=0;genPage=0;
  history.replaceState(null,"",location.pathname);
  syncClear();renderGenerations();renderGames(++seq);
}
function gameRow(x){
  // Twin of Python game_row_html.
  const m=$("member").value.trim();
  const seats=x.seats||[];
  const refS=seats.find(s=>s.id===m)||seats[0]||{id:"?",score:"?",result:"draw"};
  const o=seatBadge(refS.result);
  const label=replayLabel(x.gen,x.replay);
  const names=seats.map(s=>s.id).join(" vs ");
  let match;
  if(seats.length<=2){
    const s0=seats[0]||{id:"?",score:"?",result:"draw"};
    const s1=seats[1]||{id:"?",score:"?",result:"draw"};
    const w0=s0.result==="win",w1=s1.result==="win";
    const w0h=(w0?'<span class="winner">':'')+esc(s0.id)+(w0?'</span>':'');
    const w1h=(w1?'<span class="winner">':'')+esc(s1.id)+(w1?'</span>':'');
    match=`<td class="matchup" title="engine score">${w0h} ${s0.score} – ${s1.score} ${w1h}</td>`;
  }else{
    const line=seats.map(s=>(s.result==="win"?'<span class="winner">':'')+esc(s.id)+" "+s.score+(s.result==="win"?'</span>':'')).join(" · ");
    const pairs=(x.pairs||[]).map(p=>esc(p.a)+" "+p.score_a+"–"+p.score_b+" "+esc(p.b)).join(" · ");
    match=`<td class="matchup" title="engine scores, all ${seats.length} seats">${line}<div class="pairs">${pairs}</div></td>`;
  }
  return `<tr><td>${esc(x.gen)}</td><td><span class="pill ${esc(x.kind)}">${esc(x.kind)}</span></td>`+
  match+`<td><span class="badge ${o.cls}">${o.label}</span></td>`+
  `<td class="replay"><a href="/replay?f=${encodeURIComponent(x.replay)}" target="_blank" rel="noopener" title="${esc(names)}, gen ${esc(x.gen)} — opens in a new tab">${esc(label)}<span aria-hidden="true"> ↗</span></a></td></tr>`;
}
async function renderGames(my){
  const m=$("member").value.trim();
  if(m)history.replaceState(null,"","#member="+encodeURIComponent(m));
  else if(!location.search)history.replaceState(null,"",location.pathname);
  syncClear();
  if(tableBusy("games-body")) return true; // reader busy: retry next poll
  const qparts=[];
  if(m)qparts.push("member="+encodeURIComponent(m));
  qparts.push("limit=100","offset="+gamesOffset);
  let data;
  try{data=await fetchJSON("/api/games?"+qparts.join("&"));}
  catch(e){
    $("error").style.display="block";
    $("error").textContent="games feed failed ("+e.message+") — showing last good table. retrying…";
    return false;
  }
  if(my!==seq||$("member").value.trim()!==m) return true; // a newer poll or filter won
  const h=m+"|"+gamesOffset+"|"+JSON.stringify(data);
  if(h===lastGames) return true; // unchanged: keep focus, selection, scroll
  lastGames=h;
  const rows=data.rows.map(x=>gameRow(x)).join("");
  keepScroll($("games-scroll"),()=>{
    // One shared empty-state shape (P2-2); the filtered case escapes via
    // the clear-filter link, not only by retyping (P0-4).
    $("games-body").innerHTML=rows||(data.total?`<tr><td colspan="5" class="empty">no games on this page — use the pager above</td></tr>`:(m?`<tr><td colspan="5" class="empty">no games logged for ${esc(m)} yet — <a href="#" class="js-clear">clear filter</a></td></tr>`:'<tr><td colspan="5" class="empty">no games logged yet — they appear here as each game finishes</td></tr>'));
  });
  bindClear();
  const pages=Math.max(1,Math.ceil(data.total/100));
  const page=Math.floor(gamesOffset/100)+1;
  $("games-count").textContent=`showing ${data.rows.length} of ${data.total} · page ${Math.min(page,pages)} of ${pages}`;
  $("pg-prev").disabled=gamesOffset<=0;
  $("pg-next").disabled=gamesOffset+100>=data.total;
  return true;
}
function renderMaps(){
  if(tableBusy("maps-body"))return;
  const h=JSON.stringify(S.maps||[]);
  if(h===lastMaps)return;
  lastMaps=h;
  // Null maps are legacy pre-map-logging rows, pinned last server-side.
  const rows=(S.maps||[]).map(m=>{
    const label=m.map||"unlabelled (pre-map logging)";
    return `<tr><td class="truncate" title="${esc(m.map||"unlabelled (pre-map logging)")}">${esc(label)}</td><td class="num">${m.n}</td>`+
    `<td class="num">${m.train}</td><td class="num">${m.eval}</td>`+
    `<td class="num">${m.cw}-${m.cd}-${m.cl}</td></tr>`;}).join("");
  keepScroll($("maps-scroll"),()=>{
    $("maps-body").innerHTML=rows||'<tr><td colspan="5" class="empty">no games logged yet — they appear here as each game finishes</td></tr>';
  });
}
function seedMember(){
  // P0-4: `?member=` seeds the filter on load, then the URL is replaced
  // with the canonical `#member=` form. Unknown ids stay in the input so
  // the empty state + clear-filter link show (never a silent ignore).
  const q=new URLSearchParams(location.search).get("member");
  const hm=new URLSearchParams(location.hash.slice(1)).get("member");
  const want=(hm!==null&&hm!=="")?hm:q;
  if(want===null||want===undefined||want===""){
    if(q)history.replaceState(null,"",location.pathname);
    return;
  }
  $("member").value=want;
  gamesOffset=0;genPage=0;
  history.replaceState(null,"","#member="+encodeURIComponent(want));
  syncClear();renderGenerations();
}
async function load(){
  if(!live) return;
  const my=++seq;
  try{
    // P0-2: idle polls send ?since= and get a tiny {unchanged:true}.
    const url=(S&&S.mtime)?"/api/snapshot?since="+encodeURIComponent(S.mtime):"/api/snapshot";
    const snap=await fetchJSON(url);
    if(my!==seq) return; // a newer poll won
    lastTick=Date.now();
    $("error").style.display="none";
    if(snap.unchanged&&S){renderHeader();}
    else{
      S=snap;
      const h=JSON.stringify(snap);
      if(h!==lastHash){lastHash=h;
        renderHeader();renderBoard();renderPopulation();renderGenerations();renderMemberOptions();renderMaps();}
      else renderHeader();
      if(!hashSeeded){hashSeeded=true;seedMember();}
    }
    renderPill();
    const ok=await renderGames(my);
    if(!ok)$("updated").textContent="updated "+ago(lastTick)+" · games feed stale · live snapshot";
  }catch(e){
    $("error").style.display="block";
    $("error").textContent=lastTick?"connection lost ("+e.message+") — showing last good data from "+ago(lastTick)+". retrying…"
      :"connection lost ("+e.message+") — no data yet. retrying…";
  }
}
function activePhase(){const p=S&&S.status&&S.status.phase;return p==="train"||p==="eval";}
function tick(){renderPill();load().finally(()=>setTimeout(tick,live?(activePhase()?5000:15000):15000));}
let gamesOffset=0,hashSeeded=false;
$("member").addEventListener("input",()=>{gamesOffset=0;genPage=0;++seq;syncClear();renderGenerations();renderGames(seq);});
$("member").addEventListener("change",()=>{gamesOffset=0;genPage=0;++seq;syncClear();renderGenerations();renderGames(seq);});
$("clear-filter").addEventListener("click",e=>{e.preventDefault();clearMember();});
$("gen-prev").addEventListener("click",()=>{genPage=Math.max(0,genPage-1);renderGenerations();});
$("gen-next").addEventListener("click",()=>{genPage+=1;renderGenerations();});
$("pop-prev").addEventListener("click",()=>{popPage=Math.max(0,popPage-1);renderPopulation();});
$("pop-next").addEventListener("click",()=>{popPage+=1;renderPopulation();});
$("hide-zero").addEventListener("change",()=>{popPage=0;lastPop="";renderPopulation();});
$("pg-prev").addEventListener("click",()=>{gamesOffset=Math.max(0,gamesOffset-100);renderGames(++seq);});
$("pg-next").addEventListener("click",()=>{gamesOffset+=100;renderGames(++seq);});
$("live-toggle").addEventListener("change",e=>{live=e.target.checked;
  if(!live)seq++; // invalidate in-flight polls
  $("live-label").textContent=live?"live":"paused";
  renderPill();load();});
let resizeT=0;
window.addEventListener("resize",()=>{clearTimeout(resizeT);resizeT=setTimeout(()=>{if(S)renderBoard();},150);});
load();
tick();
"""


def render_page(snap: dict | None = None) -> str:
    """Full page. With a snapshot the hero, strip and first table pages
    are server-rendered (P0-1 first paint); without one the shell carries
    skeleton shimmer rows so layout doesn't jump."""
    if snap is None:
        skel3 = "".join(
            '<tr class="skel">' + "<td><span></span></td>" * 4 + "</tr>" for _ in range(3))
        hero_champ, hero_run, hero_eta = "loading…", "gen —", ""
        status_line, pct, bar_bg = "loading…", 0, "var(--accent)"
        counts = ("0", "0", "0", "0")
        gen_rows = skel3
        gen_count = "loading…"
        game_rows = skel3
        game_count = "loading…"
        pop_rows = skel3
        pop_count = "loading…"
        map_rows = skel3
        footer_counts = "0 games"
    else:
        champ = snap.get("champion")
        star = ' <span class="champ-star">★</span>' if champ else ""
        hero_champ = f"{_esc(champ or '—')}{star}"
        run = snap.get("run", {}) or {}
        hero_run = _esc(hero_run_text(run))
        hero_eta = ""
        tgt = run.get("target")
        if not (isinstance(tgt, int) and (run.get("finished", 0) or 0) >= tgt):
            bits = []
            if run.get("last_finished_at"):
                bits.append("last finished " + fmt_time(run["last_finished_at"]))
            if run.get("avg_s"):
                bits.append(f"avg {run['avg_s']}s/gen")
            if isinstance(tgt, int) and run.get("avg_s") and tgt > (run.get("finished", 0) or 0):
                bits.append("ETA " + fmt_time(time.time() + (tgt - run["finished"]) * run["avg_s"]))
            hero_eta = _esc(" · ".join(bits) or "no timing data yet")
        status_line, pct = status_html(snap.get("status"), champ,
                                       snap.get("counts", {}).get("generations", 0))
        st = snap.get("status", {}) or {}
        bar_bg = ("var(--success)" if st.get("phase") == "done" and st.get("promoted")
                  else "var(--warn)" if st.get("phase") == "done"
                  else "var(--accent)")
        counts = (str(snap.get("counts", {}).get("generations", 0)),
                  str(snap.get("counts", {}).get("games", 0)),
                  str(len(snap.get("members", []))),
                  str(len(snap.get("maps", []))))
        gens = snap.get("generations", [])
        gen_rows = "".join(gen_row_html(g) for g in gens[:PAGE_SIZE]) or \
            '<tr><td colspan="7" class="empty">no completed generations yet</td></tr>'
        npages = max(1, (len(gens) + PAGE_SIZE - 1) // PAGE_SIZE)
        gen_count = f"showing {min(len(gens), PAGE_SIZE)} of {len(gens)} · page 1 of {npages}"
        games = snap.get("games", [])
        game_rows = "".join(game_row_html(x) for x in games) or \
            f'<tr><td colspan="5" class="empty">{EMPTY_GAMES}</td></tr>'
        total = snap.get("game_total", len(games))
        game_count = f"showing {len(games)} of {total} · page 1 of {max(1, (total + 99) // 100)}"
        vis = pop_first_page(snap.get("members", []), champ)
        pop_rows = "".join(pop_row_html(m, champ) for m in vis[:PAGE_SIZE]) or \
            '<tr><td colspan="5" class="empty">no checkpoints yet — start a generation</td></tr>'
        ppp = max(1, (len(vis) + PAGE_SIZE - 1) // PAGE_SIZE)
        pop_count = f"showing {min(len(vis), PAGE_SIZE)} of {len(vis)} · page 1 of {ppp}"
        maps = snap.get("maps", [])
        map_rows = "".join(map_row_html(m) for m in maps) or \
            f'<tr><td colspan="5" class="empty">{EMPTY_GAMES}</td></tr>'
        footer_counts = f"{snap.get('game_total', 0)} games"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AlphaAnt training</title>
<style>{STYLES}</style></head>
<body><a class="skip" href="#games-card">skip to games</a><a class="skip" href="#gen-card">skip to generations</a><div class="wrap">
<h1>AlphaAnt training</h1>
<p class="sub">mirror self-play · policy gradients · scripted promotion — nothing external, ever</p>
<div id="error" role="alert"></div>
<div class="card" id="getting-started" style="display:none"><b>No generations yet.</b> Start one with:
<code>.venv/bin/python ml/selfplay.py --train-games 4 --eval-games 6 --turns 50 --no-commit</code>
— games, curves and population appear here as it runs.</div>
<div class="card hero" id="hero">
  <div class="hero-main"><div class="stat-label">★ Champion</div>
    <div class="hero-champ" id="st-champ">{hero_champ}</div>
    <div class="hero-run" id="st-run">{hero_run}</div>
    <div class="legend" id="st-eta">{hero_eta}</div></div>
  <div class="hero-side"><div class="stat-label">Status</div>
    <div class="status-line" id="st-status">{status_line}</div>
    <div class="progress" role="progressbar" aria-label="run progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{pct}" id="st-barwrap"><div id="st-bar" style="width:{pct}%;background:{bar_bg}"></div></div></div>
</div>
<div class="strip" id="stats-row">
  <div class="mini"><div class="stat-label">Generations</div><div class="stat-value" id="st-gen">{counts[0]}</div></div>
  <div class="mini"><div class="stat-label">Games</div><div class="stat-value" id="st-games">{counts[1]}</div></div>
  <div class="mini"><div class="stat-label">Members</div><div class="stat-value" id="st-members">{counts[2]}</div></div>
  <div class="mini"><div class="stat-label">Maps × seats</div><div class="stat-value" id="st-maps">{counts[3]}</div></div>
</div>
<div class="section-title">Progress board</div>
<div class="legend">seven training curves, one point per generation, oldest → newest</div>
<details class="why"><summary>what am I looking at?</summary><p>Each card plots one signal per generation, oldest on the left. <b>Return</b> is the mean engine score per training game. Thick lines are window medians over faint per-generation points; shaded bands are the spread. The PG ratio card is experimental — it has no literature backing, unlike the rest.</p></details>
<div class="charts">
  <div class="card chart-card chart-wide"><div class="chart-head"><h3>Candidate vs champion Elo</h3><span class="delta flat" id="d-elo" style="display:none"></span></div>
    <p class="chart-sub">causal Bradley-Terry over train+eval pairs · refit every 15 gens · <span id="elo-turn"></span></p><canvas id="ch-elo"></canvas></div>
  <div class="card chart-card"><div class="chart-head"><h3>Knock marks + rates</h3><span class="delta flat" id="d-knock" style="display:none"></span></div>
    <p class="chart-sub">top: one tick per gen (blue knock ≥ .50, gray held) · bottom: 15-gen rates + Wilson bands</p><canvas id="ch-knock-marks" style="height:64px"></canvas><canvas id="ch-knock" style="margin-top:8px"></canvas></div>
  <div class="card chart-card"><div class="chart-head"><h3>Decisiveness train vs eval</h3><span class="delta flat" id="d-dec" style="display:none"></span></div>
    <p class="chart-sub">nonzero-margin fraction · faint raw, bold 15-gen average</p><canvas id="ch-dec"></canvas></div>
  <div class="card chart-card"><div class="chart-head"><h3>Eval margin median ± IQR</h3><span class="delta flat" id="d-marg" style="display:none"></span></div>
    <p class="chart-sub">pooled trailing 15-gen window · signed challenger-minus-champ, pts</p><canvas id="ch-marg"></canvas></div>
  <div class="card chart-card"><div class="chart-head"><h3>PG signal ratio + entropy</h3><span class="delta flat" id="d-pg" style="display:none"></span></div>
    <p class="chart-sub">ratio = |pg_loss|/pg_abs at last epoch · EXPERIMENTAL · entropy on right axis</p><canvas id="ch-pg"></canvas></div>
  <div class="card chart-card"><div class="chart-head"><h3>Value-fit slope</h3><span class="delta flat" id="d-vsl" style="display:none"></span></div>
    <p class="chart-sub">(v_loss[0]−v_loss[−1])/v_loss[0] · + means the critic learned in-gen</p><canvas id="ch-vslope"></canvas></div>
  <div class="card chart-card"><div class="chart-head"><h3>Tenure / turnover + Nash entropy <span id="tenure-now"></span></h3></div>
    <p class="chart-sub">tenure = gens held (crowning gen = 0) · ◆ = new crown · shaded = N-player era</p><canvas id="ch-tenure"></canvas><canvas id="ch-entlane" style="margin-top:8px"></canvas></div>
</div>
<div class="tables-2col">
<div>
<div class="section-title">Generations</div>
<div class="legend">challenger W-D-L vs the champion · green fill is win rate, ▲ is the promotion threshold</div>
<details class="why"><summary>jargon guide</summary><p>Each row is one challenger against the reigning champion. <b>Promoted</b> means its Wilson lower-bound win rate cleared the threshold (default 0.50) — it takes the throne. <b>Held</b> means it waits. <b>Crown</b> marks throne-takers: complete beat the champ head-to-head AND the duel field, soft took the throne without both. An <b>exploiter</b> badge flags challengers trained to probe weaknesses.</p></details>
<div class="toolbar">
<span class="pager"><button id="gen-prev" type="button" aria-label="newer generations page">← newer</button><button id="gen-next" type="button" aria-label="older generations page">older →</button></span>
<span class="legend" id="gen-count" style="margin:0">{gen_count}</span>
</div>
<div class="card table-scroll table-tall" id="gen-scroll"><table id="gen-card">
<caption>Generations, newest first — the member filter above applies here too</caption>
<tr><th scope="col">challenger</th><th scope="col" class="num">train return</th><th scope="col" class="num">train loss</th><th scope="col">eval vs champion</th><th scope="col">result</th><th scope="col">crown</th><th scope="col" class="num">config</th></tr>
<tbody id="gen-body">{gen_rows}</tbody></table></div>
</div>
<div>
<div class="section-title">Recent games</div>
<div class="legend">train = practice · eval = promotion duels vs champion · scores are engine points</div>
<details class="why"><summary>jargon guide</summary><p><b>Train</b> games are practice, including self-play. <b>Eval</b> games are promotion duels against the champion. The <b>result</b> badge reads from the filtered member's view when a filter is set, else the first-listed side. Games with 3+ seats list every seat with pair scores below.</p></details>
<div class="card" id="games-card">
<div class="toolbar">
<label for="member">member</label>
<input id="member" list="member-list" placeholder="all members" autocomplete="off" spellcheck="false">
<datalist id="member-list"></datalist>
<a href="#" id="clear-filter" class="clear-link" style="display:none">clear filter</a>
<label class="live-toggle"><input type="checkbox" id="live-toggle" checked> <span id="live-label">live</span></label>
<span class="live-pill ok" id="live-pill">● live</span>
<span class="pager"><button id="pg-prev" type="button" aria-label="newer games page">← newer</button><button id="pg-next" type="button" aria-label="older games page">older →</button></span>
<span class="legend" id="games-count" style="margin:0">{game_count}</span>
<span class="updated" id="updated" title="page refresh time — data may be older while the run is idle"></span>
</div>
<div class="table-scroll table-tall" id="games-scroll"><table>
<caption>Recent games, newest first</caption>
<tr><th scope="col">gen</th><th scope="col">kind</th><th scope="col">matchup</th><th scope="col">result</th><th scope="col">replay</th></tr>
<tbody id="games-body">{game_rows}</tbody></table></div>
</div>
</div>
<div class="tables-2col even">
<div>
<div class="section-title">Population</div>
<div class="legend">nash = mixture share in %, display only · W-D-L counts eval games</div>
<details class="why"><summary>jargon guide</summary><p><b>Nash</b> is each checkpoint's share of the equilibrium mixture: it guides matchmaking, never ranking. <b>W-D-L</b> counts eval games only — one entry per game, where a win is the sole top score and a draw is a tied top. <b>Seed</b> is the founding-weights checkpoint everything descends from.</p></details>
<div class="toolbar">
<label class="live-toggle"><input type="checkbox" id="hide-zero" checked> hide zero-Nash</label>
<span class="pager"><button id="pop-prev" type="button" aria-label="previous population page">← prev</button><button id="pop-next" type="button" aria-label="next population page">next →</button></span>
<span class="legend" id="pop-count" style="margin:0">{pop_count}</span>
</div>
<div class="card table-scroll table-tall" id="pop-scroll"><table>
<caption>Population by Nash share, highest first</caption>
<tr><th scope="col">id</th><th scope="col">role</th><th scope="col">parent</th><th scope="col">nash</th><th scope="col" class="num">W-D-L (eval)</th></tr>
<tbody id="pop-body">{pop_rows}</tbody></table></div>
</div>
<div>
<div class="section-title">Maps</div>
<div class="legend">per board and seat count — games per phase · challenger record on eval</div>
<details class="why"><summary>jargon guide</summary><p>Each row is one board at one seat count. The <b>challenger record</b> covers eval games only, read off fixed seats 0 and 1 — extra seats are shared weather. Rows labelled unlabelled ran before map logging existed.</p></details>
<div class="card table-scroll table-tall" id="maps-scroll"><table>
<caption>Maps by games logged</caption>
<tr><th scope="col">map</th><th scope="col" class="num">seats</th><th scope="col" class="num">train</th><th scope="col" class="num">eval</th><th scope="col" class="num">challenger W-D-L (eval)</th></tr>
<tbody id="maps-body">{map_rows}</tbody></table></div>
</div>
</div>
<div class="footer"><span>archive ml/archive</span><span class="sep">·</span><span>{footer_counts}</span><span class="sep">·</span><span>polls 5s active / 15s idle</span><span class="sep">·</span><span>AZDash</span></div>
</div>
<script>{SCRIPT}</script></body></html>
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Serve the training dashboard.")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--archive", default="ml/archive")
    args = p.parse_args(argv)
    base = (ROOT / args.archive).resolve() if not Path(args.archive).is_absolute() else Path(args.archive)
    server = ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(base))
    print(f"dashboard: http://localhost:{args.port}/  (archive: {base})")
    print("WSL note: open the localhost URL in your Windows browser.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
