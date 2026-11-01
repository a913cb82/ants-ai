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
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

import archive
import selfplay

VIS_DIR = ROOT / "tools" / "visualizer"
TEMPLATE = (VIS_DIR / "replay.html.template").read_text()

_memo_lock = threading.RLock()
def _memo(cache: dict, key, thunk):
    """One-slot memo: recompute only when the key changes.

    Lock-guarded (RLock: thunks nest, e.g. grouped build reads the
    games memo): ThreadingHTTPServer serves polls in threads, and a
    clear-then-fill without a lock lets a concurrent poll read an empty
    cache (KeyError: 'value'). Thunk runs inside the lock so concurrent
    snapshots queue instead of stampeding the 10s cold build."""
    with _memo_lock:
        if cache.get("key") != key:
            val = thunk()
            cache.clear()
            cache["key"] = key
            cache["value"] = val
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


def filter_history(rows: list[dict], member: str) -> list[dict]:
    """Member-aware history filter: id OR champion OR learner match.
    Empty member passes everything through."""
    if not member:
        return list(rows)
    return [g for g in rows
            if g.get("id") == member or g.get("champion") == member
            or g.get("learner") == member]


def filter_generations(gens: list[dict], member: str) -> list[dict]:
    """Legacy alias of filter_history (kept for the member-filter UI)."""
    return filter_history(gens, member)


def _rnd(x, nd: int):
    """Round JSON numbers server-side (P0-2/P1-5); pass anything else
    through untouched."""
    return round(x, nd) if isinstance(x, (int, float)) else x


# ---------------------------------------------------------------- LEAGUE BACKEND
# Continuous-league contracts (ml/runs/plan-league.md, phase 4): the game
# log is bucketed into K-game intervals (game order // K, K from
# league.json snapshot_every); the Elo panel is the anchor ladder from
# league.json; per-learner trajectories replace the duel cand/champ
# framing. Elo pass math itself is unchanged.


def league_state(base: Path) -> dict | None:
    """Scheduler state from league.json; None on legacy archives."""
    return archive.load_league(base)


def interval_size(base: Path) -> int:
    """K-game interval width: league.json snapshot_every, else the
    scheduler cadence (selfplay.SNAPSHOT_EVERY). Guards junk to 80."""
    try:
        k = (league_state(base) or {}).get("snapshot_every",
                                            selfplay.SNAPSHOT_EVERY)
        k = int(k)
    except (TypeError, ValueError):
        return selfplay.SNAPSHOT_EVERY
    return k if k > 0 else selfplay.SNAPSHOT_EVERY


def league_panel(base: Path) -> list[str]:
    """Fixed Elo reference panel: the anchor ladder from league.json.
    Replaces panel_ids (last-deposed-champs) in the duel path."""
    state = league_state(base)
    anchors = (state or {}).get("anchors", []) or []
    return [a for a in anchors if isinstance(a, str)]


def interval_batches(grouped: list[dict], K: int) -> list[list[dict]]:
    """Chronological K-game intervals, oldest first. grouped is newest-
    first (group_games order), so intervals count from the oldest game:
    interval(game) = chronological_order // K. A trailing partial
    interval is kept (it is the live one)."""
    if K <= 0:
        K = 1
    chrono = grouped[::-1]
    batches: list[list[dict]] = []
    for order, g in enumerate(chrono):
        idx = order // K
        while len(batches) <= idx:
            batches.append([])
        batches[idx].append(g)
    return batches


def interval_labels(grouped: list[dict], K: int) -> list[str]:
    """X-axis labels per interval: oldest-game..newest-game ordinals."""
    if K <= 0:
        K = 1
    n = len(grouped)
    labels = []
    for start in range(0, n, K):
        labels.append(f"{start}–{min(start + K - 1, n - 1)}")
    return labels


def interval_pair_buckets(grouped: list[dict], K: int,
                          pos: dict) -> list[dict]:
    """Per-interval aggregated unordered pairs, oldest interval first.

    Generalizes gen_pair_buckets to interval keys: one entry per
    (interval, seat-pair). Outcome from the canonically-first member's
    view (draws = 0.5, the outcome_of convention), train and eval kinds
    together. Pairs naming unknown members and self-pairs are skipped."""
    batches = interval_batches(grouped, K)
    per: list[dict] = [{} for _ in batches]
    for idx, games in enumerate(batches):
        for g in games:
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
                out = 1.0 if sa > sb else (0.0 if sb < sa else 0.5)
                key = (i, j) if i < j else (j, i)
                acc = per[idx].setdefault(key, [0.0, 0.0])
                if (i, j) == key:
                    acc[0] += out
                    acc[1] += 1.0 - out
                else:
                    acc[0] += 1.0 - out
                    acc[1] += out
    return per


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
_BT_REG = 1.0  # virtual win+loss vs a rating-0 opponent: shrinks the
# data-poor toward 0 instead of stranding them at +/-inf
# interval Elo, not per-generation Elo


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


def tracked_members(base: Path, grouped: list[dict]) -> list[str]:
    """Elo trajectories to plot: main + live slots + anchors.

    The league translation of the duel panel: the live main (whose games
    log under "main" forever) plus each exploiter's bare slot id
    ("me", "le-a", "le-b" -- games log under the slot across resets;
    the reset log severs the record instead of minting ids) plus the
    anchor ladder, deduped in that order. No league.json means no
    league: just the main."""
    state = league_state(base)
    if state is not None:
        ids: list[str] = ["main"]
        for _name, exp in (state.get("exploiters") or {}).items():
            live_id = (exp or {}).get("id")
            if isinstance(live_id, str) and live_id not in ids:
                ids.append(live_id)
        for a in league_panel(base):
            if a not in ids:
                ids.append(a)
        return ids
    return ["main"]


def _readout_member(mi: int, opps: dict, theta: list[float],
                    iters: int = 25, tol: float = 1e-9,
                    reg: float = _BT_REG) -> float:
    """One member's logit given a FIXED field (Hunter MM, member only).

    Same update as a joint Hunter-MM sweep (Laplace +1/+1 per pair,
    optional virtual win/loss vs rating-0), but only mi moves;
    opponents stay at their carried values.
    opps maps opp idx -> [mine, theirs] WITHOUT priors. Members with no
    pairs have nothing to fit (caller keeps the window value). Pure."""
    if not opps:
        return math.log(theta[mi]) if theta[mi] > 0 else 0.0
    t = theta[mi] if theta[mi] > 0 else 1.0
    wins = reg
    tot = {}
    for oi, w in opps.items():
        mine, theirs = w[0] + 1.0, w[1] + 1.0
        wins += mine
        tot[oi] = mine + theirs
    for _ in range(iters):
        denom = 2.0 * reg / (t + 1.0)
        for oi, total in tot.items():
            denom += total / (t + theta[oi])
        new = wins / denom if denom > 0 else t
        if new <= 0:
            break
        d = abs(math.log(new) - math.log(t)) if t > 0 else float("inf")
        t = new
        if d < tol:
            break
    return math.log(t) if t > 0 else 0.0


_RUN_SWEEPS = 4  # Gauss-Seidel sweeps per gen over that gen's pairs only.


def _gen_opponents(bucks: dict) -> dict:
    """Member idx -> {opp idx: [mine, theirs]} for one gen's buckets."""
    opps: dict = {}
    for (i, j), w in bucks.items():
        a = opps.setdefault(i, {})
        b = opps.setdefault(j, {})
        ai = a.setdefault(j, [0.0, 0.0])
        ai[0] += w[0]
        ai[1] += w[1]
        bj = b.setdefault(i, [0.0, 0.0])
        bj[0] += w[1]
        bj[1] += w[0]
    return opps


def _elo_of(t: float) -> float | None:
    """Theta-scale rating -> Elo points (None when unrated)."""
    return math.log(t) * _BT_ELO_SCALE if t > 0 else None


def reset_cut_intervals(grouped: list[dict], K: int,
                          resets: list[dict]) -> dict[str, set[int]]:
    """Reset log -> {seat id: cut interval indices}.

    Each reset entry names the game that triggered it (seat + game_no
    identify games/{seat}/train{game_no}/logs/0.replay, unique per seat).
    The cut fires at the first interval AFTER that game: the game itself
    still counts pre-reset (its weights were), everything after restarts
    from seed. grouped is newest-first (interval_batches counts from the
    oldest). Unknown games and empty logs map to no cuts, never a crash.
    Pure."""
    if K <= 0:
        K = 1
    if not resets:
        return {}
    by_replay: dict[str, int] = {}
    for order, g in enumerate(reversed(grouped)):
        rp = g.get("replay", "") if isinstance(g, dict) else ""
        if isinstance(rp, str) and rp not in by_replay:
            by_replay[rp] = order
    cuts: dict[str, set[int]] = {}
    for r in resets:
        if not isinstance(r, dict):
            continue
        seat, game = r.get("seat"), r.get("game")
        if not isinstance(seat, str):
            continue
        try:
            n = int(game)
        except (TypeError, ValueError):
            continue
        key = f"games/{seat}/train{n}/logs/0.replay"
        if key in by_replay:
            cuts.setdefault(seat, set()).add(by_replay[key] // K + 1)
    return cuts


def _interval_elo_extend(ids: list[str], per_interval: list[dict],
                       tracked: list[str], sweeps: int, start: int,
                       theta: list[float], series: dict,
                       parents: dict | None = None,
                       seen: set | None = None,
                       played: set | None = None,
                       cuts: dict | None = None) -> None:
    """Extend per-learner trajectories over intervals, in place.

    Same math as the retired duel pass: one sequential theta vector,
    each interval's pairs move both endpoints (Gauss-Seidel sweeps
    against the fixed field), g000 pinned at 1.0, lineage seeding for
    first appearances, virtual win+loss gauge (_BT_REG). Only the
    iteration unit (K-game intervals, not gens) and the readout
    (tracked learner/anchor trajectories, not cand/champ) changed.
    Every plotted value uses only games <= its interval (causal);
    extending from stored theta continues bitwise."""
    pos = {cid: i for i, cid in enumerate(ids)}
    g0 = pos.get("g000")
    if seen is None:
        seen = set()
    if parents is None:
        parents = {}
    if played is None:
        played = set()
    for mid in tracked:
        series.setdefault(mid, [])
    for gi in range(start, len(per_interval)):
        if cuts:
            for mid, idxs in cuts.items():
                if gi in idxs:
                    mi = pos.get(mid)
                    if mi is not None and mi != g0:
                        # Reset seam: the slot's weights restarted (fresh
                        # g000 net or newly admitted peak elsewhere), so
                        # its carried peak must not leak past this point.
                        theta[mi] = 1.0
        opps = _gen_opponents(per_interval[gi]
                              if gi < len(per_interval) else {})
        act = [m for m in opps if m != g0]
        for m in act:
            if m not in seen:
                p = parents.get(ids[m])
                if p in pos:
                    theta[m] = theta[pos[p]]
        # Gameless trackers carry their lineage at its CURRENT value
        # every interval (a never-played member is still the same
        # continuing entity); members with games keep their own rating.
        for mid in tracked:
            mi = pos.get(mid)
            if mi is not None and mi != g0 and mi not in played:
                p = parents.get(mid)
                if p in pos:
                    theta[mi] = theta[pos[p]]
        if act:
            for _ in range(sweeps):
                for m in act:
                    theta[m] = math.exp(_readout_member(m, opps[m], theta))
        seen.update(act)
        played.update(act)
        for mid in tracked:
            mi = pos.get(mid)
            series[mid].append(_elo_of(theta[mi])
                               if mi is not None else None)


def running_elo_intervals(ids: list[str], per_interval: list[dict],
                          tracked: list[str],
                          sweeps: int = _RUN_SWEEPS,
                          parents: dict | None = None,
                          cuts: dict | None = None) -> dict:
    """Per-learner trajectories in one sequential pass, interval 0 -> I.

    The pass maintains a single theta vector: each interval's pairs
    move both endpoints against the field as it stands, then every
    tracked member (live main + live exploiters + anchors) is read
    out. No windows, no refits, no lookahead, no takeover breaks --
    the value at interval I is exactly what the games <= I imply.
    parents maps member id -> parent id for lineage seeding. cuts maps
    member id -> reset interval indices: entering a cut interval resets
    that member's theta to seed (1.0) before its games move it, so a
    reset slot restarts from g000's level instead of peak-continuing.
    Pure."""
    theta = [1.0] * len(ids)
    series: dict = {}
    _interval_elo_extend(ids, per_interval, tracked, sweeps, 0, theta,
                         series, parents, set(), cuts=cuts)
    return {"tracked": list(tracked), "series": series}


def seat0_outcome(game: dict) -> str | None:
    """Training-side outcome for one game: seats[0] is the training side
    (learner first in run_tick, challenger first in legacy gens)."""
    seats = game.get("seats", []) or []
    if not seats:
        return None
    return member_game_result(game, seats[0].get("id"))


def game_margin(game: dict) -> float | None:
    """Training-side edge for 2-seat games: seats[0] minus seats[1].

    N-player games have no single training-side edge (extra seats are
    shared weather); they read as None, never 0."""
    seats = game.get("seats", []) or []
    if len(seats) != 2:
        return None
    try:
        return float(seats[0]["score"]) - float(seats[1]["score"])
    except (TypeError, ValueError, KeyError):
        return None


def conversion(batches: list[list[dict]], window: int = 15) -> dict:
    """Per-interval training-side conversion with Wilson whiskers.

    The league translation of promoted|knock: no throne, just how often
    the training side (seats[0]) converts eval games into wins. Each
    trailing window pools its eval games (wins + draws/2 over games);
    the mean plus z=1.0 Wilson whiskers smooth it. Train games are
    practice, never conversion. Empty windows are gaps (None), never
    zeros."""
    conv, clo, chi = [], [], []
    for i in range(len(batches)):
        w = d = n = 0.0
        window_games = [g for games in batches[max(0, i - window + 1):i + 1]
                        for g in games]
        for g in window_games:
            if g.get("kind") != "eval":
                continue
            r = seat0_outcome(g)
            if r == "win":
                w += 1
            elif r == "draw":
                d += 1
            elif r != "loss":
                continue
            n += 1
        conv.append((w + 0.5 * d) / n if n else None)
        lo, hi = wilson_bounds(w + 0.5 * d, n)
        clo.append(lo if n else None)
        chi.append(hi if n else None)
    return {"conv": conv, "clo": clo, "chi": chi}


def main_history(history: list[dict]) -> list[dict]:
    """Main-learner history rows only: league snapshot entries carry a
    learner field; legacy gen entries predate roles and all read as
    main, so old archives keep their PG/value curves."""
    return [h for h in history if h.get("learner", "main") == "main"]


def decisiveness(batches: list[list[dict]],
                 window: int = 15) -> dict:
    """Nonzero-margin fraction per K-game interval, split by kind.

    A game is decisive unless every seat tied (max != min). Raw per-
    interval lines plus a trailing-window MA each. League games log as
    eval kind, so the train lane fills only from legacy archives."""
    train, evalv = [], []
    for games in batches:
        for kind, out in (("train", train), ("eval", evalv)):
            gs = [g for g in games if g.get("kind") == kind]
            if gs:
                dec = 0
                for g in gs:
                    scores = [s["score"] for s in g.get("seats", [])]
                    if scores and max(scores) != min(scores):
                        dec += 1
                out.append(dec / len(gs))
            else:
                out.append(None)
    return {"train": train, "train_ma": roll_mean(train, window),
            "eval": evalv, "eval_ma": roll_mean(evalv, window)}


def margin_band(batches: list[list[dict]], window: int = 15) -> dict:
    """Training-side margin median +/- IQR over pooled trailing windows.

    Per-game seats[0]-minus-seats[1] over eval 2-seat games. Pooling
    (not median-of-medians) keeps game counts honest."""
    med, q1, q3 = [], [], []
    for i in range(len(batches)):
        pool: list[float] = []
        window_games = [g for games in batches[max(0, i - window + 1):i + 1]
                        for g in games]
        for g in window_games:
            if g.get("kind") != "eval":
                continue
            m = game_margin(g)
            if m is not None:
                pool.append(m)
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


_interval_elo_cache: dict = {}


def _parent_map(base: Path) -> dict:
    """Member id -> parent id from the checkpoint manifest ({} if absent)."""
    try:
        rows = [json.loads(l) for l in
                (base / "manifest.jsonl").read_text().splitlines()]
    except (OSError, ValueError):
        return {}
    return {r["id"]: r.get("parent") for r in rows if "id" in r}


def _interval_elo_cached(base: Path, grouped: list[dict], K: int,
                          tracked: list[str]) -> dict:
    """Per-learner trajectories: full pass once, streaming extends after.

    Same memo pattern as the retired duel cache: the game log only
    appends, so when member ids extend the cached ones and the rebuilt
    early buckets match, the pass continues from the stored theta (one
    cheap extension per poll instead of a full rebuild); any rewrite
    falls back to a full pass. Tracked-set changes force a rebuild
    (every trajectory needs the final set)."""
    try:
        data = json.loads((base / "matrix.json").read_text())
        ids = data.get("ids", [])
    except (OSError, ValueError):
        return {"tracked": tracked, "series": {m: [] for m in tracked}}
    pos = {cid: i for i, cid in enumerate(ids)}
    per_interval = interval_pair_buckets(grouped, K, pos)
    counts = [len(b) for b in per_interval]
    parents = _parent_map(base)
    resets = []
    try:
        st_league = json.loads((base / "league.json").read_text())
        if isinstance(st_league, dict):
            resets = st_league.get("resets", []) or []
    except (OSError, ValueError):
        pass
    cuts = reset_cut_intervals(grouped, K, resets)
    cuts_sig = sorted((m, sorted(s)) for m, s in cuts.items())
    st = _interval_elo_cache.get("state")
    if (st is not None
            and len(ids) >= len(st["ids"])
            and ids[:len(st["ids"])] == st["ids"]
            and len(per_interval) >= st["n_interval"]
            and counts[:st["n_interval"]] == st["counts"]
            and tracked == st["tracked"]
            and cuts_sig == st.get("cuts_sig", [])):
        theta = st["theta"] + [1.0] * (len(ids) - len(st["ids"]))
        series = {k: list(v) for k, v in st["series"].items()}
        seen = set(st["seen"])
        played = set(st["played"])
        _interval_elo_extend(ids, per_interval, tracked, _RUN_SWEEPS,
                             st["n_interval"], theta, series,
                             parents, seen, played, cuts=cuts)
        n_interval = len(per_interval)
    else:
        theta = [1.0] * len(ids)
        series, seen, played = {}, set(), set()
        _interval_elo_extend(ids, per_interval, tracked, _RUN_SWEEPS, 0,
                             theta, series, parents, seen, played,
                             cuts=cuts)
        n_interval = len(per_interval)
    _interval_elo_cache["state"] = {
        "ids": ids, "counts": counts, "theta": theta,
        "tracked": tracked, "series": series, "seen": seen,
        "played": played, "cuts_sig": cuts_sig,
        "n_interval": n_interval}
    # No matrix-membership filter: anchors and learner slots with no
    # logged games yet read as None gaps (unknown) or the 0.0 default
    # (known but unplayed), never dropped from the card.
    return {"tracked": list(tracked), "series": series}


def anchor_trend(base: Path, state: dict | None) -> dict:
    """Main-vs-ladder per snapshot: THE absolute progress curve.

    anchor.jsonl rows {snapshot_id, main_id, anchor_id, wins, losses,
    draws} accumulate per (snapshot, anchor); the share is
    (wins + draws/2) / total, one point per main snapshot in snapshot
    order (state main_snapshots, else first-seen order). Anchor games
    carry no gradient, so this curve moves only when the main does."""
    anchors = list((state or {}).get("anchors", []) or [])
    acc: dict[tuple, list] = {}
    order: list[str] = []
    for r in archive.list_anchors(base):
        key = (r.get("snapshot_id"), r.get("anchor_id"))
        cell = acc.setdefault(key, [0.0, 0.0, 0.0])
        cell[0] += r.get("wins", 0)
        cell[1] += r.get("losses", 0)
        cell[2] += r.get("draws", 0)
        if isinstance(key[0], str) and key[0] not in order:
            order.append(key[0])
    snaps = [s for s in (state or {}).get("main_snapshots", []) or []
             if isinstance(s, str)]
    snaps += [s for s in order if s not in snaps]
    series = {}
    for a in anchors:
        line = []
        for sid in snaps:
            w, lo, d = acc.get((sid, a), [0.0, 0.0, 0.0])
            t = w + lo + d
            line.append((w + 0.5 * d) / t if t else None)
        series[a] = line
    return {"snapshots": snaps, "anchors": anchors, "series": series}


def participation(grouped: list[dict]) -> dict[str, int]:
    """Game appearances per member (one per game seating the member)."""
    tally: dict[str, int] = {}
    for g in grouped:
        seen_here = {s.get("id") for s in g.get("seats", []) or []}
        for sid in seen_here:
            if isinstance(sid, str):
                tally[sid] = tally.get(sid, 0) + 1
    return tally


def sampling_share(grouped: list[dict], top_n: int = 20) -> dict:
    """Realized sampling share: game appearances of the top-N most-
    played members over all appearances. The league-mechanism check
    (plan falsifier: top-20 members >= 80% of matches means weighting
    works, no junk churn)."""
    tally = participation(grouped)
    total = sum(tally.values())
    covered = sum(sorted(tally.values(), reverse=True)[:top_n])
    return {"top_n": top_n,
            "share": covered / total if total else None,
            "covered": covered, "total": total}


def pool_health(base: Path, grouped: list[dict],
                members: list[dict]) -> dict:
    """Pool-health card: growth, sampling concentration, newcomer queue.

    Growth = total members + by-role splits + league snapshot counter
    (every snapshot is permanent; removal is forbidden). Newcomers =
    members with <10 total games (the x5 boost window). Share = top-20
    realized sampling share."""
    part = participation(grouped)
    try:
        totals = archive.member_game_counts(base)
    except (OSError, ValueError, KeyError, TypeError):
        totals = {}
    newcomers = sorted(
        m["id"] for m in members
        if isinstance(m.get("id"), str)
        and totals.get(m["id"], part.get(m["id"], 0)) < 10)
    by_role: dict[str, int] = {}
    for m in members:
        role = m.get("role") or "?"
        by_role[role] = by_role.get(role, 0) + 1
    state = league_state(base) or {}
    return {"total": len(members), "by_role": by_role,
            "snapshot_counter": state.get("snapshot_counter", 0),
            "newcomers": newcomers, "newcomer_count": len(newcomers),
            "top20": sampling_share(grouped)}


def window_record(window: list) -> tuple[str, float | None]:
    """Last-40 window to record text: ("W-D-L", win share)."""
    plays = [x for x in window if isinstance(x, (int, float))]
    w = sum(1 for x in plays if x == 1.0)
    d = sum(1 for x in plays if x == 0.5)
    n = len(plays)
    return (f"{w}-{d}-{n - w - d}", (w + 0.5 * d) / n if n else None)


def scheduler_strip(state: dict | None) -> dict | None:
    """Scheduler-state strip: current learner, micro-batch progress,
    live exploiter records. None on legacy archives without league.json."""
    if not state:
        return None
    order = list(archive.SCHEDULER_ORDER)
    exploiters = {}
    for name, exp in (state.get("exploiters") or {}).items():
        record, rate = window_record((exp or {}).get("window", []) or [])
        exploiters[name] = {
            "id": (exp or {}).get("id"),
            "games": (exp or {}).get("games", 0),
            "target": (exp or {}).get("target"),
            "record": record, "rate": rate,
        }
    return {"learner": order[state.get("scheduler_pos", 0) % len(order)],
            "tick": state.get("tick", 0),
            "main_id": state.get("main_id"),
            "progress": state.get("micro_batch_progress", 0),
            "micro_size": state.get("micro_batch_size", 8),
            "per_learner": state.get("micro", {}) or {},
            "exploiters": exploiters}


def history_rows(history: list[dict], base: Path) -> list[dict]:
    """History table rows, newest first: league snapshot entries and
    legacy gen entries side by side. Snapshot rows carry learner, tick
    and anchor W-D-L; legacy rows carry train return/loss and eval
    W-D-L. No verdicts, no crowns: the throne UI is retired."""
    per: dict[str, list] = {}
    for r in archive.list_anchors(base):
        cell = per.setdefault(r.get("snapshot_id"), [0.0, 0.0, 0.0])
        cell[0] += r.get("wins", 0)
        cell[1] += r.get("losses", 0)
        cell[2] += r.get("draws", 0)
    anchor_wld = {sid: f"{int(w)}-{int(d)}-{int(lo)}"
                  for sid, (w, lo, d) in per.items()}
    rows = []
    for h in history:
        if h.get("snapshot"):
            rows.append({
                "kind": "snapshot",
                "id": h.get("snapshot"),
                "learner": h.get("learner"),
                "tick": h.get("tick"),
                "games": h.get("games"),
                "anchors": anchor_wld.get(h.get("snapshot")),
            })
            continue
        ev = h.get("eval", {}) or {}
        tr = h.get("train", {}) or {}
        losses = tr.get("losses", []) or []
        rows.append({
            "kind": "gen",
            "id": h.get("challenger", h.get("id", "?")),
            "champion": h.get("champion"),
            "train_return": _rnd(tr.get("mean_return", 0.0), 2),
            "train_loss": _rnd((sum(losses) / len(losses))
                                 if losses else 0.0, 3),
            "eval_w": ev.get("wins", 0), "eval_d": ev.get("draws", 0),
            "eval_games": ev.get("games", 0),
            "win_rate": ev.get("win_rate", 0.0),
            "mean_margin": _rnd(ev.get("mean_margin", 0.0), 2),
            "margins": ev.get("margins", []),
            "started_at": h.get("started_at"),
            "finished_at": h.get("finished_at"),
            "duration_s": h.get("duration_s"),
        })
    rows.reverse()
    return rows


def build_board(base: Path, history: list[dict],
                grouped: list[dict]) -> dict:
    """League progress board, aligned to K-game intervals."""
    K = interval_size(base)
    batches = interval_batches(grouped, K)
    labels = interval_labels(grouped, K)
    try:
        duel = _interval_elo_cached(base, grouped, K,
                                    tracked_members(base, grouped))
    except (OSError, ValueError, KeyError, TypeError):
        duel = {"tracked": [], "series": {}}
    main_hist = main_history(history)
    return {
        "k": K,
        "labels": labels,
        "elo": duel,
        "conv": conversion(batches),
        "decisive": decisiveness(batches),
        "margin": margin_band(batches),
        "pg": pg_signal(main_hist),
        "vslope": value_slope(main_hist),
    }


_snapshot_cache: dict = {}


def _snapshot_key(base: Path) -> tuple:
    """Memo key covering every file snapshot() reads: mtime+size per
    file, so any writer (scheduler, trainer, status) invalidates."""
    parts = []
    for name in ("games.jsonl", "history.jsonl", "matrix.json",
                 "manifest.jsonl", "league.json", "anchor.jsonl",
                 "champion.json", "status.json"):
        try:
            st = (base / name).stat()
            parts.append((name, st.st_mtime_ns, st.st_size))
        except OSError:
            parts.append((name, None, None))
    return (str(base.resolve()), tuple(parts))


def snapshot(base: Path) -> dict:
    """Everything the page needs, in one JSON-able dict.

    Memoized on the file stats (same one-slot pattern as the grouped
    cache): a poll storm between scheduler ticks reuses the last build
    instead of regrouping 80k games and rerunning the Elo pass."""
    return _memo(_snapshot_cache, _snapshot_key(base),
                  lambda: _build_snapshot(base))


def _build_snapshot(base: Path) -> dict:
    archive.init(base)
    state = league_state(base)
    try:
        champ = archive.get_champion(base)
    except (OSError, ValueError, KeyError, TypeError):
        champ = None
    main = (state or {}).get("main_id", champ)
    history = cached_history(base)
    grouped = cached_grouped(base)
    tally = tally_eval(grouped)
    part = participation(grouped)
    total_seats = sum(part.values())
    members = []
    for m in archive.members(base):
        cid = m["id"]
        w, d, l = tally.get(cid, [0, 0, 0])
        appearance = part.get(cid, 0)
        members.append({
            "id": cid, "role": m["role"], "parent": m["parent"],
            "share": (round(appearance / total_seats, 4)
                        if total_seats else None),
            "wins": w, "draws": d, "losses": l,
        })
    rows = history_rows(history, base)
    K = interval_size(base)
    games_total = len(grouped)
    n_interval = (games_total + K - 1) // K if K > 0 else 0
    return {
        "main": main,
        "mtime": archive_mtime(base),
        "members": members,
        "league": scheduler_strip(state),
        "admissions": (state or {}).get("admissions", []) or [],
        "anchor_trend": anchor_trend(base, state),
        "pool": pool_health(base, grouped, members),
        "intervals": {"k": K, "n": n_interval},
        "board": build_board(base, history, grouped),
        "history": rows,
        "games": grouped[:50],
        "game_total": games_total,
        "maps": summarize_maps(grouped),
        "status": archive.read_status(base),
        "counts": {"rows": len(rows), "games": games_total,
                   "members": len(members)},
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


def hero_league_text(league: dict | None, intervals: dict) -> str:
    """Hero sub-line for the continuous league: tick + interval shape."""
    if not league:
        return "no scheduler state yet — start the league loop"
    k = (intervals or {}).get("k", "?")
    n = (intervals or {}).get("n", "?")
    return (f"tick {league.get('tick', 0)} · {n} × {k}-game intervals · "
            f"current learner {league.get('learner', '?')}")


def map_label(m) -> str:
    """Nulls are legacy pre-map-logging rows, not a logging bug (P0-7)."""
    return m if m else MAP_UNLABELLED


def status_html(st: dict, main, nrows: int) -> tuple[str, int]:
    """Status line + progress %, twin of the JS renderHeader branch."""
    st = st or {}
    phase = st.get("phase")
    if phase == "league":
        return (f"tick {st.get('tick', '?')}: <b>{_esc(st.get('learner', ''))}</b> "
                f"vs {_esc(st.get('opponent', ''))} · "
                f"own-games {st.get('own_games', '?')} · "
                f"micro {st.get('micro', '?')}" +
                (f" · admitted <b>{_esc(st['admitted'])}</b>"
                 if st.get("admitted") else "") +
                (f" · snapshot <b>{_esc(st['snapshot'])}</b>"
                 if st.get("snapshot") else ""),
                0)
    if phase == "anchor":
        done, total = max(0, int(st.get("done", 0) or 0)), \
            max(1, int(st.get("total", 0) or 1))
        return (f"measuring <b>{_esc(st.get('snapshot', ''))}</b> vs anchor "
                f"<b>{_esc(st.get('anchor', ''))}</b> · "
                f"game {done}/{st.get('total', 0)}", 100 * done // total)
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
    if nrows:
        return (f"idle · live main {_esc(main or '—')}", 0)
    return ("waiting for the first games…", 0)


def _num(x) -> float:
    """Coerce snapshot numbers for first-paint formatting; junk reads as 0."""
    return x if isinstance(x, (int, float)) else 0.0


def hist_row_html(g: dict) -> str:
    """Twin of JS histRow: league snapshot rows and legacy gen rows.

    Snapshot: id · learner · tick · own-games · anchor W-D-L. Legacy:
    id · train return/loss · eval W-D-L + margin dots. No verdicts, no
    crowns: the throne UI is retired."""
    when = ""
    if g.get("finished_at"):
        when = (f'<div class="legend" title="{iso_time(g["finished_at"])} '
                f'· {fmt_dur(g.get("duration_s"))}">'
                f'{fmt_time(g["finished_at"])} · {fmt_dur(g.get("duration_s"))}</div>')
    if g.get("kind") == "snapshot":
        anchor = _esc(g.get("anchors") or "—")
        return (
            f"<tr><td class=\"truncate\" title=\"{_esc(g.get('id'))}\">"
            f"{_esc(g.get('id'))}</td>"
            f"<td><span class=\"pill train\">{_esc(g.get('learner'))}</span></td>"
            f"<td class=\"num\">{_esc(g.get('tick'))}</td>"
            f"<td class=\"num\">{_esc(g.get('games'))}</td>"
            f"<td class=\"num\">{anchor}</td></tr>")
    pct = 100 * _num(g.get("win_rate"))
    losses_n = max(0, int(_num(g.get("eval_games"))) - int(_num(g.get("eval_w")))
                   - int(_num(g.get("eval_d"))))
    wdl = f"{int(_num(g.get('eval_w')))}-{int(_num(g.get('eval_d')))}-{losses_n}"
    rate = f"{_num(g.get('win_rate')) * 100:.1f}%"
    mean_m = _num(g.get("mean_margin", 0.0))
    margin_s = f"{float(mean_m):+.2f} pts"
    return (
        f"<tr><td class=\"truncate\" title=\"{_esc(g.get('id'))}\">{_esc(g.get('id'))}{when}</td>"
        f"<td class=\"num\">{_num(g.get('train_return', 0.0)):.2f}</td>"
        f"<td class=\"num\">{_num(g.get('train_loss', 0.0)):.3f}</td>"
        f"<td><span class=\"rate-wrap rate-text\" "
        f"title=\"legacy eval W-D-L · draws count ½\">"
        f"<span class=\"rate-bar\"><div style=\"width:{pct:.0f}%\"></div></span>"
        f"{wdl} · {rate} (draws count ½) · "
        f"<span title=\"mean eval margin\">margin {margin_s}</span>"
        f"<div class=\"dots\" title=\"per-duel margins: green win, blue draw, red loss\">"
        f"{dot_strip(g.get('margins'))}</div></span></td></tr>")


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


def pop_row_html(m: dict, main) -> str:
    """Twin of JS popRow: id · role · parent · sampling share · W-D-L."""
    role = "seed" if m.get("role") == "main" else _esc(m.get("role"))
    star = ' <span class="champ-star">★</span>' if m.get("id") == main else ""
    share = m.get("share")
    pct = float(share) * 100 if isinstance(share, (int, float)) else 0.0
    bar = f"max({pct:.1f}%,{1 if pct > 0 else 0}px)"  # sub-1% still paints
    seed_note = ' <span class="legend">founding weights</span>' \
        if m.get("role") == "main" else ""
    share_s = f"{pct:.1f}%" if share is not None else "—"
    return (
        f"<tr><td class=\"truncate\" title=\"{_esc(m.get('id'))}\">{_esc(m.get('id'))}{star}</td>"
        f"<td>{role}{seed_note}</td><td class=\"truncate\" title=\"{_esc(m.get('parent'))}\">"
        f"{_esc(m.get('parent') or '—')}</td>"
        f"<td><span class=\"share-wrap\"><span class=\"share-bar\">"
        f"<div style=\"width:{bar}\"></div></span>{share_s}</span></td>"
        f"<td class=\"num\">{m.get('wins', 0)}-{m.get('draws', 0)}-{m.get('losses', 0)}</td></tr>")


def map_row_html(m: dict) -> str:
    """Twin of JS mapRow."""
    return (
        f"<tr><td class=\"truncate\" title=\"{_esc(m.get('map') or MAP_UNLABELLED)}\">"
        f"{_esc(map_label(m.get('map')))}</td><td class=\"num\">{m.get('n', 0)}</td>"
        f"<td class=\"num\">{m.get('train', 0)}</td><td class=\"num\">{m.get('eval', 0)}</td>"
        f"<td class=\"num\">{m.get('cw', 0)}-{m.get('cd', 0)}-{m.get('cl', 0)}</td></tr>")


def league_strip_html(league: dict | None) -> str:
    """Scheduler strip first-paint rows: learner · micro · exploiters."""
    if not league:
        return ('<tr><td colspan="4" class="empty">no scheduler state yet — '
                'start the league loop</td></tr>')
    rows = []
    size = league.get("micro_size", 8) or 8
    for name, exp in (league.get("exploiters") or {}).items():
        rate = exp.get("rate")
        rate_s = f"{rate * 100:.0f}%" if isinstance(rate, (int, float)) else "—"
        rows.append(
            f"<tr><td>{_esc(name)}</td>"
            f"<td class=\"truncate\" title=\"{_esc(exp.get('id'))}\">"
            f"{_esc(exp.get('id') or '—')}</td>"
            f"<td class=\"num\">{exp.get('games', 0)}</td>"
            f"<td class=\"num\">{_esc(exp.get('record', '—'))} · {rate_s}</td></tr>")
    per = league.get("per_learner", {}) or {}
    micro_s = ", ".join(f"{k} {v % size}/{size}" for k, v in per.items())
    head = (f"<tr><td><b>{_esc(league.get('learner', '?'))}</b></td>"
            f"<td class=\"num\">tick {_esc(league.get('tick', 0))}</td>"
            f"<td class=\"num\" colspan=\"2\">{_esc(micro_s or '—')}</td></tr>")
    return head + "".join(rows)


def admissions_rows_html(admissions: list[dict]) -> str:
    """Admissions log first-paint rows: id · role · at-game · record."""
    if not admissions:
        return ('<tr><td colspan="4" class="empty">no admissions yet — '
                'exploiters are admitted past the bar</td></tr>')
    return "".join(
        f"<tr><td class=\"truncate\" title=\"{_esc(a.get('id'))}\">"
        f"{_esc(a.get('id'))}</td><td>{_esc(a.get('role'))}</td>"
        f"<td class=\"num\">{_esc(a.get('at_game'))}</td>"
        f"<td class=\"num\">{_esc(a.get('record'))}</td></tr>"
        for a in admissions)


def pool_html(pool: dict | None) -> tuple[str, str, str]:
    """Pool-health first paint: (summary line, role line, newcomer line)."""
    if not pool:
        return ("—", "—", "no pool data yet")
    top = pool.get("top20", {}) or {}
    share = top.get("share")
    share_s = f"{share * 100:.1f}%" if isinstance(share, (int, float)) else "—"
    summary = (f"{pool.get('total', 0)} members · snapshots "
               f"{pool.get('snapshot_counter', 0)} · top-20 share {share_s}")
    roles = ", ".join(f"{k} {v}"
                       for k, v in sorted((pool.get("by_role") or {}).items()))
    newcs = pool.get("newcomers", []) or []
    newcomers = (", ".join(newcs[:12]) + (f" +{len(newcs) - 12} more"
                                            if len(newcs) > 12 else "")
                 if newcs else "none — every member has 10+ games")
    return (summary, roles or "—", newcomers)


def pop_first_page(members: list, main) -> list:
    """First paint mirrors the default view: share desc, zero-share hidden."""
    ranked = sorted(members, key=lambda m: -(m.get("share") or 0.0))
    return [m for m in ranked if (m.get("share") or 0.0) > 0] or ranked[:100]


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
.tables-2col{display:grid; grid-template-columns:1.3fr 1fr; gap:16px; align-items:stretch;}
.tcell{display:flex; flex-direction:column; min-width:0;}
.tcell>.card{flex:1 1 auto;}
.tables-2col .toolbar{min-height:34px;}
.res-cell{min-width:180px;}
.res-cell .badge{white-space:nowrap;}
.chart-card h3{margin:0 0 2px; font-size:14px;}
.chart-sub{font-size:12px; color:var(--muted); margin:0 0 8px;}
.chart-head{display:flex; justify-content:space-between; align-items:baseline;}
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
.share-wrap{display:flex; align-items:center; gap:8px;}
.share-bar{flex:1; min-width:60px; height:6px; background:var(--border); border-radius:3px; overflow:hidden;}
.share-bar>div{height:100%; background:var(--accent);}
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
  .tables-2col{grid-template-columns:1fr;}
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
  $("st-champ").innerHTML=esc(S.main||"—")+(S.main?' <span class="champ-star">★</span>':"");
  $("getting-started").style.display=S.counts.rows?"none":"block";
  $("st-gen").textContent=S.counts.rows;
  $("st-games").textContent=S.counts.games;
  $("st-members").textContent=(S.members||[]).length;
  $("st-maps").textContent=(S.maps||[]).length;
  const L=S.league,iv=S.intervals||{};
  if(L) $("st-run").textContent=`tick ${L.tick} · ${iv.n??"?"} × ${iv.k??"?"}-game intervals · current learner ${L.learner||"?"}`;
  else $("st-run").textContent="no scheduler state yet";
  const st=S.status||{},el=$("st-status"),bar=$("st-bar"),wrap=$("st-barwrap");
  let pct=0;
  bar.style.background="var(--accent)";
  if(st.phase==="league"){
    let extra="";
    if(st.admitted)extra+=` · admitted <b>${esc(st.admitted)}</b>`;
    if(st.snapshot)extra+=` · snapshot <b>${esc(st.snapshot)}</b>`;
    el.innerHTML=`tick ${st.tick??"?"}: <b>${esc(st.learner||"")}</b> vs ${esc(st.opponent||"")} · own-games ${esc(st.own_games??"?")} · micro ${esc(st.micro??"?")}`+extra;
  }else if(st.phase==="anchor"){
    el.innerHTML=`measuring <b>${esc(st.snapshot||"")}</b> vs anchor <b>${esc(st.anchor||"")}</b> · game ${Math.max(0,+st.done||0)}/${Math.max(0,+st.total||0)}`;
    pct=100*st.done/Math.max(1,st.total);
  }else if(st.phase==="train"){
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
    el.innerHTML=S.counts.rows?`idle · live main ${esc(S.main||"—")}`:"waiting for the first games…";
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
function anchorPalette(n){
  const base=["#2456E0","#18794E","#8A5A00","#C4322B","#6B4EFF","#0E7C86","#B23C8A","#5B6470"];
  const out=[];
  for(let i=0;i<n;i++)out.push(base[i%base.length]);
  return out;
}
function renderBoard(){
  const B=S.board,ids=B.labels||[];
  const tracked=B.elo.tracked||[];
  const series=tracked.map(m=>((B.elo.series||{})[m]||[]));
  plotLines("ch-elo",series,anchorPalette(Math.max(1,tracked.length)),tracked.map(()=>2),ids,
    adesc("per-learner causal Elo",series[0]||[],ids),{yt:"Elo"});
  deltaChip("d-elo",series.length?series[0]:[]);
  $("elo-note").textContent=`K=${B.k} from league.json · ${tracked.length} tracked`;
  const AT=S.anchor_trend||{snapshots:[],anchors:[],series:{}};
  const alabels=AT.snapshots||[];
  const aseries=(AT.anchors||[]).map(a=>((AT.series||{})[a]||[]));
  plotLines("ch-anchor",aseries,anchorPalette(Math.max(1,aseries.length)),aseries.map(()=>2),alabels,
    adesc("anchor trend",aseries[0]||[],alabels),{yt:"share"});
  plotBand("ch-conv",B.conv.conv,B.conv.clo,B.conv.chi,"#18794E","rgba(24,121,78,.16)",ids,
    adesc("train conversion",B.conv.conv||[],ids),{yt:"share"});
  deltaChip("d-conv",B.conv.conv||[]);
  plotLines("ch-dec",[B.decisive.train,B.decisive.train_ma,B.decisive.eval,B.decisive.eval_ma],
    ["#E8A0A6","#C4322B","#9EC5FE","#2456E0"],[1,2,1,2],ids,
    adesc("decisiveness train vs eval",B.decisive.train||[],ids),{yt:"frac"});
  deltaChip("d-dec",B.decisive.train_ma||[]);
  plotBand("ch-marg",B.margin.med,B.margin.q1,B.margin.q3,"#2456E0","rgba(36,86,224,.15)",ids,
    adesc("training-side margin median",B.margin.med||[],ids),{yt:"pts"});
  deltaChip("d-marg",B.margin.med||[]);
  plotDual("ch-pg",B.pg.ratio,B.pg.ratio_med,B.pg.entropy,B.pg.entropy_med,ids,
    adesc("PG signal ratio",B.pg.ratio||[],ids),{yt:"ratio"});
  deltaChip("d-pg",B.pg.ratio_med||[]);
  plotBars("ch-vslope",[B.vslope],["#8A5A00"],ids,
    adesc("value-fit slope",B.vslope||[],ids),null,{yt:"slope"});
  deltaChip("d-vsl",B.vslope||[]);
}
function renderLeague(){
  const L=S.league;
  const size=(L&&L.micro_size)||8;
  let rows;
  if(!L)rows='<tr><td colspan="4" class="empty">no scheduler state yet — start the league loop</td></tr>';
  else{
    const per=L.per_learner||{};
    const micro=Object.keys(per).map(k=>`${esc(k)} ${(per[k]%size+size)%size}/${size}`).join(", ")||"—";
    rows=`<tr><td><b>${esc(L.learner||"?")}</b></td><td class="num">tick ${L.tick??0}</td><td class="num" colspan="2">${micro} · main ${esc(L.main_id||"—")}</td></tr>`;
    for(const[name,exp]of Object.entries(L.exploiters||{})){
      const rate=(typeof exp.rate==="number")?`${(exp.rate*100).toFixed(0)}%`:"—";
      rows+=`<tr><td>${esc(name)}</td><td class="truncate" title="${esc(exp.id||"")}">${esc(exp.id||"—")}</td><td class="num">${exp.games??0}</td><td class="num">${esc(exp.record||"—")} · ${rate} vs ${esc(exp.target||"")}</td></tr>`;
    }
  }
  if($("league-body").innerHTML!==rows)$("league-body").innerHTML=rows;
  const admits=(S.admissions||[]).map(a=>`<tr><td class="truncate" title="${esc(a.id)}">${esc(a.id)}</td><td>${esc(a.role)}</td><td class="num">${a.at_game}</td><td class="num">${esc(a.record)}</td></tr>`).join("")||'<tr><td colspan="4" class="empty">no admissions yet — exploiters are admitted past the bar</td></tr>';
  if($("admit-body").innerHTML!==admits)$("admit-body").innerHTML=admits;
  const P=S.pool;
  if(P){
    const sh=(P.top20&&typeof P.top20.share==="number")?`${(P.top20.share*100).toFixed(1)}%`:"—";
    $("pool-summary").textContent=`${P.total} members · snapshots ${P.snapshot_counter} · top-20 share ${sh}`;
    $("pool-roles").textContent=Object.entries(P.by_role||{}).sort().map(([k,v])=>`${k} ${v}`).join(", ")||"—";
    const nq=P.newcomers||[];
    $("pool-new").textContent=nq.length?nq.slice(0,12).join(", ")+(nq.length>12?` +${nq.length-12} more`:""):"none — every member has 10+ games";
  }
}
const PAGE=100;
let histPage=0, popPage=0, lastHist="", lastPop="", lastMaps="";
function histFiltered(){
  // P1-3: the member input filters history too (id OR champion OR learner).
  const m=$("member").value.trim();
  return (S.history||[]).filter(g=>!m||g.id===m||g.champion===m||g.learner===m);
}
function histRow(g){
  // Twin of Python hist_row_html — keep both sides in step.
  const when=g.finished_at
    ?`<div class="legend" title="${esc(isoT(g.finished_at))} · ${fmtDur(g.duration_s)}">${fmtTime(g.finished_at)} · ${fmtDur(g.duration_s)}</div>`:"";
  if(g.kind==="snapshot")
    return `<tr><td class="truncate" title="${esc(g.id)}">${esc(g.id)}</td>`+
    `<td><span class="pill train">${esc(g.learner)}</span> tick ${esc(g.tick)}</td>`+
    `<td class="num">${esc(g.games)} own-games</td>`+
    `<td class="num">anchors ${esc(g.anchors||"—")}</td></tr>`;
  const pct=g.eval_games?100*g.win_rate:0;
  const losses=Math.max(0,g.eval_games-g.eval_w-g.eval_d);
  const margin=(typeof g.mean_margin==="number")?g.mean_margin:0;
  return `<tr><td class="truncate" title="${esc(g.id)}">${esc(g.id)}${when}</td>`+
  `<td>vs ${esc(g.champion||"?")}</td>`+
  `<td class="num">${(+g.train_return||0).toFixed(2)} · ${(+g.train_loss||0).toFixed(3)}</td>`+
  `<td><span class="rate-wrap rate-text" title="legacy eval W-D-L · draws count ½"><span class="rate-bar"><div style="width:${pct.toFixed(0)}%"></div></span>`+
  `${g.eval_w}-${g.eval_d}-${losses} · ${(g.win_rate*100).toFixed(1)}% · `+
  `<span title="mean eval margin">margin ${margin>=0?"+"+margin.toFixed(2):margin.toFixed(2)} pts</span>`+
  `<div class="dots" title="per-duel margins: green win, blue draw, red loss">${dotStrip(g.margins)}</div></span></td></tr>`;
}
function renderPopulation(){
  if(tableBusy("pop-body"))return; // P0-3: reader busy, retry next poll
  // Share desc, zero-share hidden by default, % at 1dp, ≥1px bars.
  const hide=$("hide-zero")&&$("hide-zero").checked;
  const ranked=[...(S.members||[])].sort((a,b)=>((b.share||0)-(a.share||0)));
  const vis=hide?ranked.filter(m=>(m.share||0)>0):ranked;
  const pages=Math.max(1,Math.ceil(vis.length/PAGE));
  popPage=Math.min(popPage,pages-1);
  const h=hide+"|"+popPage+"|"+JSON.stringify(vis.slice(popPage*PAGE,popPage*PAGE+PAGE));
  if(h===lastPop)return; // unchanged: keep focus, selection, scroll
  lastPop=h;
  const rows=vis.slice(popPage*PAGE,popPage*PAGE+PAGE).map(m=>popRow(m)).join("");
  keepScroll($("pop-scroll"),()=>{
    $("pop-body").innerHTML=rows||'<tr><td colspan="5" class="empty">no checkpoints yet — start the league loop</td></tr>';
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
  const share=(typeof m.share==="number")?m.share:null;
  const pct=share===null?0:share*100;
  const bar=`max(${pct.toFixed(1)}%,${pct>0?1:0}px)`;
  const disp=share===null?"—":`${pct.toFixed(1)}%`;
  return `<tr><td class="truncate" title="${esc(m.id)}">${esc(m.id)}${m.id===S.main?' <span class="champ-star">★</span>':""}</td>`+
  `<td>${esc(role)}${m.role==="main"?' <span class="legend">founding weights</span>':""}</td><td class="truncate" title="${esc(m.parent||"")}">${esc(m.parent||"—")}</td>`+
  `<td><span class="share-wrap"><span class="share-bar"><div style="width:${bar}"></div></span>${disp}</span></td>`+
  `<td class="num">${m.wins}-${m.draws}-${m.losses}</td></tr>`;
}
function renderHistory(){
  if(tableBusy("hist-body"))return; // P0-3: reader busy, retry next poll
  const vis=histFiltered();
  const pages=Math.max(1,Math.ceil(vis.length/PAGE));
  histPage=Math.min(histPage,pages-1);
  const h=$("member").value+"|"+histPage+"|"+JSON.stringify(vis.slice(histPage*PAGE,histPage*PAGE+PAGE));
  if(h===lastHist)return; // unchanged: keep focus, selection, scroll
  lastHist=h;
  const rows=vis.slice(histPage*PAGE,histPage*PAGE+PAGE).map(g=>histRow(g)).join("");
  keepScroll($("hist-scroll"),()=>{
    $("hist-body").innerHTML=rows||($("member").value
      ?`<tr><td colspan="4" class="empty">no history for ${esc($("member").value)} yet — <a href="#" class="js-clear">clear filter</a></td></tr>`
      :'<tr><td colspan="4" class="empty">no history yet — games appear here as the league ticks</td></tr>');
  });
  bindClear();
  const page=Math.min(histPage+1,pages);
  $("hist-count").textContent=`showing ${vis.slice(histPage*PAGE,histPage*PAGE+PAGE).length} of ${vis.length} · page ${page} of ${pages}`;
  $("hist-prev").disabled=histPage<=0;
  $("hist-next").disabled=histPage+1>=pages;
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
  gamesOffset=0;histPage=0;
  history.replaceState(null,"",location.pathname);
  syncClear();renderHistory();renderGames(++seq);
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
  gamesOffset=0;histPage=0;
  history.replaceState(null,"","#member="+encodeURIComponent(want));
  syncClear();renderHistory();
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
        renderHeader();renderBoard();renderLeague();renderPopulation();renderHistory();renderMemberOptions();renderMaps();}
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
function activePhase(){const p=S&&S.status&&S.status.phase;return p==="train"||p==="eval"||p==="league"||p==="anchor";}
function tick(){renderPill();load().finally(()=>setTimeout(tick,live?(activePhase()?5000:15000):15000));}
let gamesOffset=0,hashSeeded=false;
$("member").addEventListener("input",()=>{gamesOffset=0;histPage=0;++seq;syncClear();renderHistory();renderGames(seq);});
$("member").addEventListener("change",()=>{gamesOffset=0;histPage=0;++seq;syncClear();renderHistory();renderGames(seq);});
$("clear-filter").addEventListener("click",e=>{e.preventDefault();clearMember();});
$("hist-prev").addEventListener("click",()=>{histPage=Math.max(0,histPage-1);renderHistory();});
$("hist-next").addEventListener("click",()=>{histPage+=1;renderHistory();});
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
        hero_main, hero_run = "loading…", "tick —"
        status_line, pct, bar_bg = "loading…", 0, "var(--accent)"
        counts = ("0", "0", "0", "0")
        league_rows = skel3
        admit_rows = skel3
        pool_summary, pool_roles, pool_new = "loading…", "loading…", "loading…"
        hist_rows = skel3
        hist_count = "loading…"
        game_rows = skel3
        game_count = "loading…"
        pop_rows = skel3
        pop_count = "loading…"
        map_rows = skel3
        map_count = "loading…"
        footer_counts = "0 games"
    else:
        main = snap.get("main")
        star = ' <span class="champ-star">★</span>' if main else ""
        hero_main = f"{_esc(main or '—')}{star}"
        league = snap.get("league")
        hero_run = _esc(hero_league_text(league, snap.get("intervals")))
        status_line, pct = status_html(snap.get("status"), main,
                                       snap.get("counts", {}).get("rows", 0))
        st = snap.get("status", {}) or {}
        bar_bg = ("var(--success)" if st.get("phase") == "done" and st.get("promoted")
                  else "var(--warn)" if st.get("phase") == "done"
                  else "var(--accent)")
        counts = (str(snap.get("counts", {}).get("rows", 0)),
                  str(snap.get("counts", {}).get("games", 0)),
                  str(len(snap.get("members", []))),
                  str(len(snap.get("maps", []))))
        league_rows = league_strip_html(league)
        admit_rows = admissions_rows_html(snap.get("admissions", []))
        pool_summary, pool_roles, pool_new = pool_html(snap.get("pool"))
        rows = snap.get("history", [])
        hist_rows = "".join(hist_row_html(g) for g in rows[:PAGE_SIZE]) or \
            '<tr><td colspan="4" class="empty">no history yet — games appear here as the league ticks</td></tr>'
        npages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
        hist_count = f"showing {min(len(rows), PAGE_SIZE)} of {len(rows)} · page 1 of {npages}"
        games = snap.get("games", [])
        game_rows = "".join(game_row_html(x) for x in games) or \
            f'<tr><td colspan="5" class="empty">{EMPTY_GAMES}</td></tr>'
        total = snap.get("game_total", len(games))
        game_count = f"showing {len(games)} of {total} · page 1 of {max(1, (total + 99) // 100)}"
        vis = pop_first_page(snap.get("members", []), main)
        pop_rows = "".join(pop_row_html(m, main) for m in vis[:PAGE_SIZE]) or \
            '<tr><td colspan="5" class="empty">no checkpoints yet — start the league loop</td></tr>'
        ppp = max(1, (len(vis) + PAGE_SIZE - 1) // PAGE_SIZE)
        pop_count = f"showing {min(len(vis), PAGE_SIZE)} of {len(vis)} · page 1 of {ppp}"
        maps = snap.get("maps", [])
        map_rows = "".join(map_row_html(m) for m in maps) or \
            f'<tr><td colspan="5" class="empty">{EMPTY_GAMES}</td></tr>'
        map_count = f"{len(maps)} boards"
        footer_counts = f"{snap.get('game_total', 0)} games"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AlphaAnt training</title>
<style>{STYLES}</style></head>
<body><a class="skip" href="#games-card">skip to games</a><a class="skip" href="#hist-card">skip to history</a><div class="wrap">
<h1>AlphaAnt continuous league</h1>
<p class="sub">four learners, equal shares · fixed anchor ladder · no generations, no throne</p>
<div id="error" role="alert"></div>
<div class="card" id="getting-started" style="display:none"><b>No games yet.</b> Start the league with:
<code>.venv/bin/python ml/selfplay.py --ticks 100 --anchors g000</code>
— games, curves and population appear here as it ticks.</div>
<div class="card hero" id="hero">
  <div class="hero-main"><div class="stat-label">Live main</div>
    <div class="hero-champ" id="st-champ">{hero_main}</div>
    <div class="hero-run" id="st-run">{hero_run}</div></div>
  <div class="hero-side"><div class="stat-label">Status</div>
    <div class="status-line" id="st-status">{status_line}</div>
    <div class="progress" role="progressbar" aria-label="run progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{pct}" id="st-barwrap"><div id="st-bar" style="width:{pct}%;background:{bar_bg}"></div></div></div>
</div>
<div class="strip" id="stats-row">
  <div class="mini"><div class="stat-label">History rows</div><div class="stat-value" id="st-gen">{counts[0]}</div></div>
  <div class="mini"><div class="stat-label">Games</div><div class="stat-value" id="st-games">{counts[1]}</div></div>
  <div class="mini"><div class="stat-label">Members</div><div class="stat-value" id="st-members">{counts[2]}</div></div>
  <div class="mini"><div class="stat-label">Maps × seats</div><div class="stat-value" id="st-maps">{counts[3]}</div></div>
</div>
<div class="section-title">Scheduler</div>
<div class="legend">current learner · micro-batch progress · live exploiter records vs their bar</div>
<div class="card table-scroll" id="league-card"><table>
<caption>Scheduler state, live</caption>
<tr><th scope="col">learner</th><th scope="col">tick</th><th scope="col" class="num">own-games</th><th scope="col" class="num">last-40 record</th></tr>
<tbody id="league-body">{league_rows}</tbody></table></div>
<div class="section-title">Progress board</div>
<div class="legend">one point per K-game interval, oldest → newest</div>
<details class="why"><summary>what am I looking at?</summary><p>Each card plots one signal per K-game interval, oldest on the left. The anchor-trend card is the absolute progress curve: each main snapshot's win share against the frozen ladder. Thick lines are window medians over faint per-interval points; shaded bands are the spread. The PG ratio card is experimental — it has no literature backing, unlike the rest.</p></details>
<div class="charts">
  <div class="card chart-card chart-wide"><div class="chart-head"><h3>Per-learner Elo</h3><span class="delta flat" id="d-elo" style="display:none"></span></div>
    <p class="chart-sub">running Bradley-Terry over train+eval pairs · one pass, interval 0 to I · g000 pinned at 0 · live main + exploiters + anchors · <span id="elo-note"></span></p><canvas id="ch-elo"></canvas></div>
  <div class="card chart-card chart-wide"><div class="chart-head"><h3>Anchor trend — main vs ladder</h3></div>
    <p class="chart-sub">main snapshot win share per frozen anchor · measurement only, no training · THE progress curve</p><canvas id="ch-anchor"></canvas></div>
  <div class="card chart-card"><div class="chart-head"><h3>Train conversion</h3><span class="delta flat" id="d-conv" style="display:none"></span></div>
    <p class="chart-sub">training-side win share per interval · trailing mean + Wilson bands</p><canvas id="ch-conv"></canvas></div>
  <div class="card chart-card"><div class="chart-head"><h3>Decisiveness train vs eval</h3><span class="delta flat" id="d-dec" style="display:none"></span></div>
    <p class="chart-sub">nonzero-margin fraction · faint raw, bold 15-interval average</p><canvas id="ch-dec"></canvas></div>
  <div class="card chart-card"><div class="chart-head"><h3>Training-side margin median ± IQR</h3><span class="delta flat" id="d-marg" style="display:none"></span></div>
    <p class="chart-sub">pooled trailing 15-interval window · seats[0]-minus-seats[1], pts</p><canvas id="ch-marg"></canvas></div>
  <div class="card chart-card"><div class="chart-head"><h3>PG signal ratio + entropy</h3><span class="delta flat" id="d-pg" style="display:none"></span></div>
    <p class="chart-sub">ratio = |pg_loss|/pg_abs at last epoch · main snapshots only · EXPERIMENTAL · entropy on right axis</p><canvas id="ch-pg"></canvas></div>
  <div class="card chart-card"><div class="chart-head"><h3>Value-fit slope</h3><span class="delta flat" id="d-vsl" style="display:none"></span></div>
    <p class="chart-sub">(v_loss[0]−v_loss[−1])/v_loss[0] · main snapshots only · + means the critic learned</p><canvas id="ch-vslope"></canvas></div>
</div>
<div class="tables-2col">
<div class="tcell">
<div class="section-title">History</div>
<div class="legend">league snapshots (learner · tick · anchors) and legacy challenger rows, newest first</div>
<details class="why"><summary>jargon guide</summary><p>Each row is one league snapshot (its learner, scheduler tick, own-games and anchor W-D-L) or, from before the league, one challenger with its train return/loss and eval W-D-L. There are no promotions, no crowns, no verdicts — snapshots are permanent.</p></details>
<div class="toolbar">
<span class="pager"><button id="hist-prev" type="button" aria-label="newer history page">← newer</button><button id="hist-next" type="button" aria-label="older history page">older →</button></span>
<span class="legend" id="hist-count" style="margin:0">{hist_count}</span>
</div>
<div class="card table-scroll table-tall" id="hist-scroll"><table id="hist-card">
<caption>History, newest first — the member filter above applies here too</caption>
<tr><th scope="col">id</th><th scope="col">vs / learner</th><th scope="col" class="num">training</th><th scope="col">eval / anchors</th></tr>
<tbody id="hist-body">{hist_rows}</tbody></table></div>
</div>
<div class="tcell">
<div class="section-title">Recent games</div>
<div class="legend">train = practice · eval = league games (learner seats first) · scores are engine points</div>
<details class="why"><summary>jargon guide</summary><p><b>Train</b> games are practice, including self-play. <b>Eval</b> games are league games; the learner always seats first, so the <b>result</b> badge reads from the training side unless a member filter is set. Games with 3+ seats list every seat with pair scores below.</p></details>
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
<div class="tcell">
<div class="section-title">Population</div>
<div class="legend">share = realized sampling share (game seats) · W-D-L counts eval games</div>
<details class="why"><summary>jargon guide</summary><p><b>Share</b> is each member's fraction of logged game seats: it shows where the scheduler actually spends games, never a ranking. <b>W-D-L</b> counts eval games only — one entry per game, where a win is the sole top score and a draw is a tied top. <b>Seed</b> is the founding-weights checkpoint everything descends from.</p></details>
<div class="toolbar">
<label class="live-toggle"><input type="checkbox" id="hide-zero" checked> hide zero-share</label>
<span class="pager"><button id="pop-prev" type="button" aria-label="previous population page">← prev</button><button id="pop-next" type="button" aria-label="next population page">next →</button></span>
<span class="legend" id="pop-count" style="margin:0">{pop_count}</span>
</div>
<div class="card table-scroll table-tall" id="pop-scroll"><table>
<caption>Population by sampling share, highest first</caption>
<tr><th scope="col">id</th><th scope="col">role</th><th scope="col">parent</th><th scope="col">share</th><th scope="col" class="num">W-D-L (eval)</th></tr>
<tbody id="pop-body">{pop_rows}</tbody></table></div>
</div>
<div class="tcell">
<div class="section-title">Admissions</div>
<div class="legend">exploiters frozen into the pool past the bar, newest last</div>
<div class="card table-scroll table-tall" id="admit-scroll"><table>
<caption>Admissions log from league.json</caption>
<tr><th scope="col">id</th><th scope="col">role</th><th scope="col" class="num">at game</th><th scope="col" class="num">record</th></tr>
<tbody id="admit-body">{admit_rows}</tbody></table></div>
</div>
<div class="tcell">
<div class="section-title">Pool health</div>
<div class="legend" id="pool-summary">{pool_summary}</div>
<div class="card" id="pool-card">
<div class="legend" style="margin:0 0 8px">roles: <span id="pool-roles">{pool_roles}</span></div>
<div style="font-size:13.5px">newcomer queue (&lt;10 games): <span id="pool-new">{pool_new}</span></div>
</div>
</div>
<div class="tcell">
<div class="section-title">Maps</div>
<div class="legend">per board and seat count — games per phase · training-side record on eval</div>
<details class="why"><summary>jargon guide</summary><p>Each row is one board at one seat count. The <b>record</b> covers eval games only, read off fixed seats 0 and 1 — extra seats are shared weather. Rows labelled unlabelled ran before map logging existed.</p></details>
<div class="toolbar">
<span class="legend" id="maps-count" style="margin:0">{map_count}</span>
</div>
<div class="card table-scroll table-tall" id="maps-scroll"><table>
<caption>Maps by games logged</caption>
<tr><th scope="col">map</th><th scope="col" class="num">seats</th><th scope="col" class="num">train</th><th scope="col" class="num">eval</th><th scope="col" class="num">training-side W-D-L (eval)</th></tr>
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
