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


SNAPSHOT_FILES = ("games.jsonl", "matrix.json", "manifest.jsonl",
                  "league.json", "anchor.jsonl")


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
               items: list[tuple[tuple, dict]],
               tick: int | None = None) -> dict | None:
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
        "tick": tick,
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
        ticks = [r.get("tick") for r in oldest
                 if isinstance(r.get("tick"), (int, float))]
        tick = max(ticks) if ticks else None
        for block in partition_group([_norm_row(r) for r in oldest]):
            g = build_game(m0["gen"], m0["kind"], m0.get("map"),
                           m0["replay"], [(n, raws[n]) for n in block],
                           tick=tick)
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


def _parent_map(base: Path) -> dict:
    """Member id -> parent id from the checkpoint manifest ({} if absent)."""
    try:
        rows = [json.loads(l) for l in
                (base / "manifest.jsonl").read_text().splitlines()]
    except (OSError, ValueError):
        return {}
    return {r["id"]: r.get("parent") for r in rows if "id" in r}


_interval_elo_cache: dict = {}


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
    carry no gradient, so this ladder moves only when the main does."""
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
    return {"snapshots": snaps, "series": series}


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
    return {
        "k": K,
        "labels": labels,
        "elo": duel,
        "conv": conversion(batches),
        "decisive": decisiveness(batches),
        "margin": margin_band(batches),
    }


_snapshot_cache: dict = {}


def _snapshot_key(base: Path) -> tuple:
    """Memo key covering every file snapshot() reads: mtime+size per
    file, so any writer (scheduler, trainer, status) invalidates."""
    parts = []
    for name in ("games.jsonl", "matrix.json", "manifest.jsonl",
                 "league.json", "anchor.jsonl"):
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


# ---------------------------------------------------------------- NEW CONTRACT
# build/dashboard2: h0, anchors, standings, bars, pairs, behavior,
# games, alerts, mtime. Derived from games.jsonl rows (tick + behavior
# facts), the eval matrix (existing bucket + running-Elo math, untouched),
# league.json (scheduler state + admission windows), the manifest
# (snapshot ids) and anchor.jsonl (the ladder). Unknowns read as None
# and render as a dash, never as zero.

#: Live slots: the four permanent lineages (frozen achievements live
#: under family ids, never here).
LIVE_SLOTS = ("main", "me", "le-a", "le-b")
SLOT_CLASS = {"main": "main", "me": "me", "le-a": "le",
              "le-b": "le"}

#: A row older than this many ticks vs h0.tick reads grayed out.
STALE_TICKS = 200
#: No game for this long: the scheduler is stuck.
ALERT_IDLE_S = 15 * 60
#: Exploiter games since its last admission past this multiple of the
#: window: an admission drought.
ALERT_DROUGHT_X = 3
#: Snapshot-to-snapshot anchor share drop, in percentage points.
ALERT_ANCHOR_PP = 10.0
#: Recent games scanned for length-0 timeouts.
ALERT_TIMEOUT_N = 20


def behavior_ids(base: Path) -> list[str]:
    """Board row ids: live slots plus frozen snapshot/admission ids.

    Manifest order (snapshots first), live slots pinned first."""
    ids = list(LIVE_SLOTS)
    for m in archive.members(base):
        cid = m.get("id")
        if (isinstance(cid, str) and cid not in ids
                and m.get("role") in archive.LEAGUE_ROLES):
            ids.append(cid)
    return ids


def _wall_now() -> float:
    import time as _time
    return _time.time()


def rate_window(base: Path) -> tuple[int | None, float | None]:
    """(games in the last hour, seconds since the last game).

    From the wall-clock stamps the scheduler logs per game; the game
    index mtime is the recency fallback when rows predate stamps.
    None when nothing is logged yet."""
    stamps = sorted(r["t"] for r in cached_games(base)
                    if isinstance(r.get("t"), (int, float)))
    if stamps:
        now = _wall_now()
        return (sum(1 for t in stamps if t > now - 3600),
                max(0.0, now - stamps[-1]))
    try:
        return (None, max(0.0, _wall_now()
                           - (base / "games.jsonl").stat().st_mtime))
    except OSError:
        return (None, None)


def anchor_verdict(trend: dict) -> str:
    """Water-mark read of the ladder: new-high when the latest snapshot
    averages above every prior one, down when it slips below the
    previous snapshot, else flat."""
    snaps = trend.get("snapshots", []) or []
    series = trend.get("series", {}) or {}
    avgs = []
    for i in range(len(snaps)):
        vals = [line[i] for line in series.values()
                if i < len(line) and isinstance(line[i], (int, float))]
        avgs.append(sum(vals) / len(vals) if vals else None)
    known = [a for a in avgs if a is not None]
    if len(known) < 2:
        return "flat"
    if known[-1] > max(known[:-1]):
        return "new-high"
    if known[-1] < known[-2]:
        return "down"
    return "flat"


def h0_panel(base: Path, state: dict | None, grouped: list[dict],
             trend: dict) -> dict:
    """Sticky strip facts: tick · game# · learner · micro · rate ·
    recency · anchor verdict."""
    state = state or {}
    order = list(archive.SCHEDULER_ORDER)
    learner = order[state.get("scheduler_pos", 0) % len(order)]
    micro = (state.get("micro", {}) or {}).get(learner, 0)
    micro_size = state.get("micro_batch_size",
                           archive.MICRO_BATCH_SIZE) or 8
    games_per_h, secs = rate_window(base)
    return {
        "tick": state.get("tick", 0),
        "game_n": len(grouped),
        "learner": learner,
        "micro_n": micro % micro_size,
        "micro_size": micro_size,
        "games_per_h": games_per_h,
        "secs_since_game": secs,
        "anchor_verdict": anchor_verdict(trend),
    }


def standings_panel(base: Path, grouped: list[dict], K: int) -> list[dict]:
    """Four live rows: running-Elo math (untouched) plus W-D-L and the
    last tick each slot played. Unplayed slots read null, never zero."""
    tally = tally_eval(grouped)
    try:
        elo = _interval_elo_cached(
            base, grouped, K, list(LIVE_SLOTS))["series"]
    except (OSError, ValueError, KeyError, TypeError):
        elo = {s: [] for s in LIVE_SLOTS}
    last: dict[str, float] = {}
    for g in grouped:
        tick = g.get("tick")
        if not isinstance(tick, (int, float)):
            continue
        for s in g.get("seats", []) or []:
            sid = s.get("id")
            if isinstance(sid, str) and sid in LIVE_SLOTS:
                last[sid] = max(last.get(sid, tick), tick)
    rows = []
    for sid in LIVE_SLOTS:
        w, d, lo = tally.get(sid, [0, 0, 0])
        vals = [v for v in (elo.get(sid) or [])
                if isinstance(v, (int, float))]
        rows.append({
            "id": sid, "class": SLOT_CLASS[sid],
            "elo": int(round(vals[-1])) if vals else None,
            "w": w, "d": d, "l": lo, "n": w + d + lo,
            "last_tick": last.get(sid),
        })
    return rows


def bars_panel(state: dict | None) -> list[dict]:
    """Distance-to-bar per live exploiter: window W-D-L vs its target
    from league.json, plus games to eligibility (window fill)."""
    out = []
    for name, exp in ((state or {}).get("exploiters", {}) or {}).items():
        window = [x for x in (exp or {}).get("window", []) or []
                  if isinstance(x, (int, float))]
        w = sum(1 for x in window if x == 1.0)
        d = sum(1 for x in window if x == 0.5)
        n = len(window)
        out.append({
            "id": name,
            "target": (exp or {}).get("target"),
            "rate": round((w + 0.5 * d) / n, 4) if n else None,
            "record_wdl": f"{w}-{d}-{n - w - d}",
            "eligible_in": max(0, archive.WINDOW_SIZE - n),
        })
    return out


def pairs_panel(base: Path, grouped: list[dict]) -> list[dict]:
    """Unordered pairs: existing bucket math, Laplace share, last tick.

    One interval over the whole log reuses interval_pair_buckets
    exactly (train+eval together, strays skipped); the share smooths
    unseen pairs to 0.5 like the Elo pass."""
    try:
        data = json.loads((base / "matrix.json").read_text())
        ids = data.get("ids", [])
    except (OSError, ValueError):
        return []
    pos = {cid: i for i, cid in enumerate(ids)}
    per = interval_pair_buckets(grouped, max(1, len(grouped)), pos)
    buck = per[0] if per else {}
    last: dict[tuple, float] = {}
    for g in grouped:
        tick = g.get("tick")
        for p in g.get("pairs", []) or []:
            a, b = p.get("a"), p.get("b")
            if a not in pos or b not in pos:
                continue
            i, j = pos[a], pos[b]
            if i == j:
                continue
            key = (i, j) if i < j else (j, i)
            if isinstance(tick, (int, float)):
                last[key] = max(last.get(key, tick), tick)
    out = []
    for (i, j), (w, lo) in buck.items():
        total = w + lo
        out.append({
            "a": ids[i], "b": ids[j],
            "share": int(round(100 * (w + 1) / (total + 2))),
            "n": int(total),
            "last_tick": last.get((i, j)),
        })
    out.sort(key=lambda r: (-r["n"], r["a"], r["b"]))
    return out


def behavior_panel(base: Path) -> list[dict]:
    """Per snapshot id + live slots: mean food/kills/army share/length
    over logged behavior rows. Null when unplayed or unstamped."""
    acc: dict[str, dict] = {}
    for cid in behavior_ids(base):
        acc[cid] = {"food": [], "kills": [], "army": [],
                    "length": [], "n": 0}
    for r in cached_games(base):
        food, kills, army = r.get("food"), r.get("kills"), r.get("army")
        if not (isinstance(food, list) and isinstance(kills, list)
                and isinstance(army, list)):
            continue
        if len(food) < 2 or len(kills) < 2 or len(army) < 2:
            continue
        try:
            f = (float(food[0]), float(food[1]))
            k = (float(kills[0]), float(kills[1]))
            a = (float(army[0]), float(army[1]))
        except (TypeError, ValueError):
            continue
        length = r.get("length")
        length = length if isinstance(length, (int, float)) else None
        sides = ((r.get("a"), f[0], k[0], a[0]),
                 (r.get("b"), f[1], k[1], a[1]))
        for cid, fi, ki, ai in sides:
            cell = acc.get(cid)
            if cell is None:
                continue
            cell["food"].append(fi)
            cell["kills"].append(ki)
            if a[0] + a[1] > 0:
                cell["army"].append(100 * ai / (a[0] + a[1]))
            if length is not None:
                cell["length"].append(length)
            cell["n"] += 1
    out = []
    for cid, cell in acc.items():
        n = cell["n"]

        def _mean(vals):
            return sum(vals) / len(vals) if vals else None
        out.append({
            "id": cid,
            "food": round(_mean(cell["food"]), 1)
            if cell["food"] else None,
            "kills": round(_mean(cell["kills"]), 1)
            if cell["kills"] else None,
            "army_pct": int(round(_mean(cell["army"])))
            if cell["army"] else None,
            "length": int(round(_mean(cell["length"])))
            if cell["length"] else None,
            "n": n,
        })
    return out


def games_panel(grouped: list[dict],
                limit: int = 100) -> tuple[list[dict], int]:
    """Recent games newest-first: dual ordinal+tick, learner-side result."""
    total = len(grouped)
    out = []
    for idx, g in enumerate(grouped[:limit]):
        seats = g.get("seats", []) or []
        ref = seats[0].get("id") if seats else None
        out.append({
            "game_n": total - 1 - idx,
            "tick": g.get("tick"),
            "learner": g.get("gen"),
            "seats": [s.get("id") for s in seats],
            "scores": [s.get("score") for s in seats],
            "result": member_game_result(g, ref) if ref else None,
            "replay": g.get("replay"),
        })
    return out, total


def _fmt_idle(secs: float) -> str:
    s = int(round(secs))
    if s < 60:
        return f"{s}s"
    return f"{s // 60}m {s % 60:02d}s"


def alerts_panel(base: Path, state: dict | None, trend: dict,
                 h0: dict) -> list[dict]:
    """Attention queue, max 5: stuck scheduler, admission drought,
    anchor drops, length-0 timeouts; else one all-clear line."""
    state = state or {}
    tick = h0.get("tick", 0)
    out = []
    secs = h0.get("secs_since_game")
    if isinstance(secs, (int, float)) and secs > ALERT_IDLE_S:
        out.append({"level": "alert",
                    "msg": f"no game for {_fmt_idle(secs)}",
                    "tick": tick})
    last_at: dict[str, int] = {}
    for a in state.get("admissions", []) or []:
        if not isinstance(a, dict) or not isinstance(a.get("role"), str):
            continue
        try:
            at = int(a.get("at_game", 0))
        except (TypeError, ValueError):
            continue
        last_at[a["role"]] = max(last_at.get(a["role"], 0), at)
    for name, exp in (state.get("exploiters", {}) or {}).items():
        games = (exp or {}).get("games", 0)
        since = games - last_at.get(name, 0)
        if since > ALERT_DROUGHT_X * archive.WINDOW_SIZE:
            out.append({
                "level": "alert",
                "msg": (f"admission drought {name}: {since} games "
                        f"since last admission "
                        f"(>3×{archive.WINDOW_SIZE})"),
                "tick": tick})
    for aid, line in (trend.get("series", {}) or {}).items():
        pts = [v for v in line if isinstance(v, (int, float))]
        if len(pts) >= 2 and pts[-2] - pts[-1] > ALERT_ANCHOR_PP / 100:
            drop = (pts[-2] - pts[-1]) * 100
            out.append({
                "level": "alert",
                "msg": (f"{aid} down {drop:.0f}pp "
                        f"snapshot-to-snapshot"),
                "tick": tick})
    seen: list = []
    timeouts = 0
    for r in cached_games(base):
        key = r.get("game") or r.get("replay")
        if key in seen:
            continue
        seen.append(key)
        if len(seen) > ALERT_TIMEOUT_N:
            break
        if r.get("length") == 0:
            timeouts += 1
    if timeouts:
        out.append({
            "level": "alert",
            "msg": (f"{timeouts} timeout" +
                    ("s" if timeouts > 1 else "") +
                    " (length 0) in recent games"),
            "tick": tick})
    if not out:
        return [{"level": "ok", "msg": "all clear", "tick": tick}]
    return out[:5]


def _build_snapshot(base: Path) -> dict:
    archive.init(base)
    state = league_state(base)
    grouped = cached_grouped(base)
    K = interval_size(base)
    trend = anchor_trend(base, state)
    h0 = h0_panel(base, state, grouped, trend)
    games, total = games_panel(grouped)
    return {
        "h0": h0,
        "anchors": trend,
        "standings": standings_panel(base, grouped, K),
        "bars": bars_panel(state),
        "pairs": pairs_panel(base, grouped),
        "behavior": behavior_panel(base),
        "games": games,
        "game_total": total,
        "alerts": alerts_panel(base, state, trend, h0),
        "mtime": archive_mtime(base),
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
                        limit = max(0, min(int(q.get("limit", ["100"])[0]), 200))
                    except ValueError:
                        limit = 100
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
# First-paint helpers: render_page(snapshot) inlines the H0 strip and
# every table card into the raw HTML, so the first paint is content
# with zero JS. Canvas cards (ladder, pairs) carry a text fallback with
# the same numbers. The JS poll takes over from the same JSON; row
# markup here mirrors the JS renderers (any visual change needs both
# sides — search for the twin name).

PAGE_SIZE = 100  # games pager page (matches /api/games default)

EMPTY_GAMES = "no games logged yet \u2014 they appear here as each game finishes"

SLOT_COLORS = {"main": "#1d4ed8", "me": "#b45309", "le-a": "#047857",
               "le-b": "#65a30d"}
FROZEN_COLOR = "#6b7280"


def _esc(x) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def slot_color(cid) -> str:
    """Slot ink: main blue, me amber, le greens, everything else gray."""
    return SLOT_COLORS.get(cid, FROZEN_COLOR)


def fmt_age(secs) -> str:
    """Recency: `12s ago`, past 60s `3m 04s ago`, unknown `—`."""
    if not isinstance(secs, (int, float)):
        return "—"
    s = max(0, int(round(secs)))
    if s < 60:
        return f"{s}s ago"
    return f"{s // 60}m {s % 60:02d}s ago"


def fmt_rate(games_per_h) -> str:
    if not isinstance(games_per_h, (int, float)):
        return "—"
    return f"{games_per_h:.0f}/h"


def fmt_elo(elo) -> str:
    return str(int(elo)) if isinstance(elo, (int, float)) else "—"


def fmt_share100(share) -> str:
    """A 0-100 share to 0dp, unknown to a dash."""
    return f"{share:.0f}%" if isinstance(share, (int, float)) else "—"


def fmt_tick(t) -> str:
    return f"t{t}" if isinstance(t, (int, float)) else "t—"


def dual(g, t) -> str:
    """Dual time, everywhere: g1234 · t5678, dashes for unknowns."""
    gg = f"g{g}" if isinstance(g, (int, float)) else "g—"
    return f"{gg} · {fmt_tick(t)}"


def is_stale(row_tick, h0_tick) -> bool:
    """A row older than 200 ticks vs the H0 tick reads grayed out."""
    return (isinstance(row_tick, (int, float))
            and isinstance(h0_tick, (int, float))
            and h0_tick - row_tick > STALE_TICKS)


def _dot(cid) -> str:
    return (f'<span aria-hidden="true" style="color:{slot_color(cid)}">'
            f"●</span> ")


def h0_strip_html(h0: dict | None) -> str:
    """Twin of JS renderH0."""
    if h0 is None:
        return '<span class="stat-label">loading…</span>'
    verdict = h0.get("anchor_verdict", "flat")
    return (
        f"<span><b>tick</b> {_esc(h0.get('tick', 0))}</span>"
        f"<span><b>game</b> {_esc(h0.get('game_n', 0))}</span>"
        f"<span>{_dot(h0.get('learner'))}<b>{_esc(h0.get('learner'))}</b>"
        "</span>"
        f"<span><b>micro</b> {_esc(h0.get('micro_n'))}"
        f"/{_esc(h0.get('micro_size'))}</span>"
        f"<span><b>rate</b> {fmt_rate(h0.get('games_per_h'))}</span>"
        f"<span><b>last game</b> {fmt_age(h0.get('secs_since_game'))}</span>"
        f'<span class="verdict {verdict}"><b>{_esc(verdict)}</b></span>')


def ladder_fallback_html(trend: dict | None) -> str:
    """Twin of JS ladderFallback: latest share per anchor, in text."""
    if not trend or not trend.get("snapshots"):
        return '<div class="empty">no snapshots yet</div>'
    snaps = trend["snapshots"]
    series = trend.get("series", {}) or {}
    bits = []
    for aid, line in series.items():
        vals = [v for v in line if isinstance(v, (int, float))]
        bits.append(f"{aid} {vals[-1] * 100:.0f}%" if vals else f"{aid} —")
    return (f'<div class="fallback">latest of {len(snaps)} snapshots: '
            f"{_esc(' · '.join(bits) if bits else 'no anchors')}</div>")


def bars_rows_html(bars: list | None) -> str:
    """Twin of JS barsRow: distance-to-bar per live exploiter."""
    if not bars:
        return ('<tr><td colspan="5" class="empty">no exploiters yet — '
                "start the league loop</td></tr>")
    rows = []
    for b in bars:
        rate = b.get("rate")
        pct = rate * 100 if isinstance(rate, (int, float)) else 0.0
        bar = f"max({pct:.1f}%,{1 if pct > 0 else 0}px)"
        eli = b.get("eligible_in")
        eli_s = f"{eli} to go" if isinstance(eli, (int, float)) and eli > 0 \
            else "due"
        rows.append(
            f"<tr><td>{_dot(b.get('id'))}{_esc(b.get('id'))}</td>"
            f"<td class=\"truncate\">{_esc(b.get('target') or '—')}</td>"
            f"<td><span class=\"share-wrap\"><span class=\"share-bar\">"
            f"<div style=\"width:{bar}\"></div></span>"
            f"{fmt_share100(pct) if rate is not None else '—'}</span></td>"
            f"<td class=\"num\">{_esc(b.get('record_wdl'))}</td>"
            f"<td class=\"num\">{eli_s}</td></tr>")
    return "".join(rows)


def standings_rows_html(rows: list | None, h0_tick) -> str:
    """Twin of JS standingsRow."""
    if not rows:
        return ('<tr><td colspan="6" class="empty">no standings yet</td></tr>')
    out = []
    for r in rows:
        stale = ' class="stale"' if is_stale(r.get("last_tick"),
                                            h0_tick) else ""
        wdl = f"{r.get('w', 0)}-{r.get('d', 0)}-{r.get('l', 0)}"
        out.append(
            f"<tr{stale}><td>{_dot(r.get('id'))}{_esc(r.get('id'))}</td>"
            f"<td>{_esc(r.get('class'))}</td>"
            f"<td class=\"num\">{fmt_elo(r.get('elo'))}</td>"
            f"<td class=\"num\">{wdl}</td>"
            f"<td class=\"num\">{_esc(r.get('n'))}</td>"
            f"<td class=\"num\">{fmt_tick(r.get('last_tick'))}</td></tr>")
    return "".join(out)


def alerts_html(alerts: list | None) -> str:
    """Twin of JS renderAlerts: red text lines, or one all-clear."""
    if not alerts:
        return '<div class="empty">loading…</div>'
    return "".join(
        f"<div class=\"alert-{a.get('level', 'ok')}\">"
        f"{_esc(a.get('msg'))} <span class=\"legend\">"
        f"{fmt_tick(a.get('tick'))}</span></div>"
        for a in alerts)


def pairs_fallback_html(pairs: list | None) -> str:
    """Twin of JS pairsFallback: top pairs as text under the canvas."""
    if not pairs:
        return '<div class="empty">no pairs yet</div>'
    top = pairs[:5]
    bits = [f"{p['a']} vs {p['b']} · {fmt_share100(p.get('share'))} · "
            f"n={p.get('n')} · {fmt_tick(p.get('last_tick'))}"
            for p in top]
    return f"<div class=\"fallback\">{_esc(' · '.join(bits))}</div>"


def behavior_rows_html(rows: list | None, h0_tick) -> str:
    """Twin of JS behaviorRow."""
    if not rows:
        return ('<tr><td colspan="6" class="empty">no behavior yet — '
                "games log food/kills/army as they finish</td></tr>")
    out = []
    for r in rows:
        # behavior rows carry means, not ticks: never stale by recency.
        food = r.get("food")
        kills = r.get("kills")
        out.append(
            f"<tr><td>{_dot(r.get('id'))}{_esc(r.get('id'))}</td>"
            f"<td class=\"num\">"
            f"{f'{food:.1f}' if isinstance(food, (int, float)) else '—'}</td>"
            f"<td class=\"num\">"
            f"{f'{kills:.1f}' if isinstance(kills, (int, float)) else '—'}</td>"
            f"<td class=\"num\">{fmt_share100(r.get('army_pct'))}</td>"
            f"<td class=\"num\">{_esc(r.get('length')) if r.get('length') is not None else '—'}</td>"
            f"<td class=\"num\">{_esc(r.get('n'))}</td></tr>")
    return "".join(out)


def game_replay_label(g: dict) -> str:
    """`c 3 · m 1`: seat ids with scores, winner bold upstream."""
    seats = g.get("seats", []) or []
    scores = g.get("scores", []) or []
    bits = []
    for i, sid in enumerate(seats):
        sc = scores[i] if i < len(scores) else "?"
        if g.get("result") == "win" and i == 0:
            bits.append(f"<b>{_esc(sid)} {_esc(sc)}</b>")
        else:
            bits.append(f"{_esc(sid)} {_esc(sc)}")
    return " · ".join(bits)


def game_row_html(g: dict) -> str:
    """Twin of JS gameRow: dual time · learner · matchup · replay."""
    res = g.get("result") or "draw"
    names = " vs ".join(_esc(s) for s in g.get("seats", []) or [])
    return (
        f"<tr><td class=\"num\">{dual(g.get('game_n'), g.get('tick'))}</td>"
        f"<td>{_dot(g.get('learner'))}{_esc(g.get('learner'))}</td>"
        f"<td>{game_replay_label(g)}</td>"
        f"<td><span class=\"badge {res}\">{res}</span></td>"
        f"<td class=\"replay\"><a href=\"/replay?f={_esc(g.get('replay'))}\" "
        f"target=\"_blank\" rel=\"noopener\" "
        f"title=\"{names} — opens in a new tab\">"
        f"replay<span aria-hidden=\"true\"> ↗</span></a></td></tr>")


# ---------------------------------------------------------------- PAGE

STYLES = """
:root{
  --bg:#F6F7F9; --card:#FFFFFF; --border:#E3E6EA; --border-strong:#C9CFD6;
  --ink:#16191D; --secondary:#5B6470; --muted:#67707B;
  --blue:#1d4ed8; --amber:#b45309; --green1:#047857; --green2:#65a30d;
  --gray:#6b7280; --red:#b91c1c;
  --grid:#E9EDF1; --chart-text:#6B7480;
}
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,Roboto,"Helvetica Neue",Arial,sans-serif;
  background:var(--bg); color:var(--ink); margin:0; padding:0 0 48px; font-size:13px;}
.wrap{max-width:1720px; margin:0 auto; padding:24px max(16px,4vw) 0;}
h1{font-size:22px; margin:0 0 4px;}
.sub{color:var(--secondary); font-size:13px; margin:0 0 20px;}
.h0{position:sticky; top:0; z-index:10; background:var(--card); border-bottom:1px solid var(--border-strong);
  padding:10px max(16px,4vw); display:flex; gap:18px; align-items:center; flex-wrap:wrap; font-size:13px;}
.h0 .verdict.new-high{color:var(--green1);}
.h0 .verdict.down{color:var(--red);}
.h0 .verdict.flat{color:var(--gray);}
.live-pill{font-size:11px; font-weight:700; padding:2px 10px; border-radius:20px; white-space:nowrap;}
.live-pill.ok{color:var(--green1); background:#E6F4EC;}
.live-pill.stale{color:var(--amber); background:#FBF3E2;}
.live-pill.paused{color:var(--secondary); background:#EDEFF1;}
.section-title{font-size:16px; font-weight:700; margin:32px 0 12px;}
.legend{font-size:11px; color:var(--muted); margin:-6px 0 12px;}
.card{background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px 20px;}
.grid12{display:grid; grid-template-columns:repeat(12,1fr); gap:16px; align-items:stretch;}
.span7{grid-column:span 7;} .span5{grid-column:span 5;} .span6{grid-column:span 6;} .span12{grid-column:span 12;}
.tcell{display:flex; flex-direction:column; min-width:0;}
.tcell>.card{flex:1 1 auto;}
canvas{width:100%; display:block;}
#ch-ladder{height:280px;} #ch-pairs{height:300px;}
.fallback{font-size:11px; color:var(--muted); margin-top:8px;}
.alert-alert{color:var(--red); font-size:13px; padding:4px 0;}
.alert-ok{font-size:13px; padding:4px 0;}
.stale{opacity:.55;}
table{border-collapse:collapse; width:100%; font-size:13px; font-variant-numeric:tabular-nums;}
th{background:#F1F3F5; text-align:left; font-size:11px; color:var(--secondary); font-weight:600;}
th,td{padding:9px 10px; border-bottom:1px solid var(--border);}
tr:last-child td{border-bottom:none;}
tbody tr:hover{background:#F8FAFC;}
td.num, th.num{text-align:right;}
td.truncate,.truncate{max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
.badge{display:inline-block; font-size:11px; font-weight:700; padding:2px 9px; border-radius:20px;}
.badge.win{color:var(--green1); background:#E6F4EC;}
.badge.loss{color:var(--red); background:#FBEAE8;}
.badge.draw{color:var(--blue); background:#EAF0FE;}
.share-wrap{display:flex; align-items:center; gap:8px;}
.share-bar{flex:1; min-width:60px; height:6px; background:var(--border); border-radius:3px; overflow:hidden;}
.share-bar>div{height:100%; background:var(--blue);}
td.matchup, td.replay{white-space:nowrap;}
.toolbar{display:flex; gap:10px; align-items:center; margin-bottom:10px; flex-wrap:wrap;}
.toolbar label{font-size:13px; color:var(--secondary);}
input{font-size:13px; padding:6px 10px; border:1px solid var(--border-strong); border-radius:8px; background:#fff;}
input#member{min-width:140px;}
.clear-link{font-size:12px; white-space:nowrap;}
.live-toggle{display:flex; align-items:center; gap:6px; font-size:13px; color:var(--secondary);}
.pager{display:flex; gap:6px;}
.pager button{font-size:12px; padding:5px 10px; border:1px solid var(--border-strong); border-radius:8px; background:#fff; cursor:pointer;}
.pager button:disabled{opacity:.4; cursor:default;}
.updated{font-size:11px; color:var(--muted); margin-left:auto;}
.table-scroll{overflow-x:auto;}
.table-tall{max-height:480px; overflow-y:auto;}
.table-tall thead th{position:sticky; top:0; z-index:1;}
.empty{padding:28px 20px; color:var(--secondary); font-size:13px;}
a{color:var(--blue); text-decoration:none;}
a:hover{text-decoration:underline;}
a:focus-visible,input:focus-visible,button:focus-visible{outline:2px solid var(--blue); outline-offset:2px;}
.skip{position:absolute; left:-9999px; top:0; background:var(--ink); color:#fff; padding:8px 14px; z-index:99; border-radius:0 0 8px 0;}
.skip:focus{left:0; color:#fff;}
.footer{margin-top:40px; padding-top:12px; border-top:1px solid var(--border);
  font-size:11px; color:var(--muted); display:flex; gap:8px; flex-wrap:wrap;}
.footer .sep{opacity:.5;}
.skel td{color:transparent !important;}
.skel td span{display:block; height:12px; border-radius:6px;
  background:linear-gradient(90deg,var(--border) 25%,#F1F3F5 50%,var(--border) 75%);
  background-size:200% 100%; animation:shimmer 1.2s infinite;}
@keyframes shimmer{to{background-position:-200% 0;}}
@media (max-width:1100px){
  .span7,.span5,.span6{grid-column:span 12;}
}
"""

SCRIPT = """
let S=null, seq=0, lastSnap="", lastGames="", live=true, lastTick=0;
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const COLORS={main:"#1d4ed8",me:"#b45309","le-a":"#047857","le-b":"#65a30d"};
const GRAY="#6b7280";
const col=id=>COLORS[id]||GRAY;
async function fetchJSON(url){
  let r;
  try{r=await fetch(url);}
  catch(e){throw new Error("connection lost: "+e.message);}
  if(!r.ok){
    let detail="";
    try{const body=await r.json();if(body&&body.error)detail=": "+String(body.error).slice(0,140);}
    catch(e){}
    throw new Error("request failed HTTP "+r.status+detail+" on "+url);
  }
  return r.json();
}
function fmtAge(s){
  if(s===null||s===undefined||!Number.isFinite(+s))return "—";
  s=Math.max(0,Math.round(+s));
  if(s<60)return s+"s ago";
  return Math.floor(s/60)+"m "+String(s%60).padStart(2,"0")+"s ago";
}
function fmtRate(h){return (h===null||h===undefined||!Number.isFinite(+h))?"—":Math.round(h)+"/h";}
function fmtElo(e){return (e===null||e===undefined)?"—":String(Math.round(e));}
function fmtShare(s){return (s===null||s===undefined||!Number.isFinite(+s))?"—":Math.round(s)+"%";}
function fmtTick(t){return (t===null||t===undefined)?"t—":"t"+t;}
function dual(g,t){return (g===null||g===undefined?"g—":"g"+g)+" · "+fmtTick(t);}
function dot(id){return '<span aria-hidden="true" style="color:'+col(id)+'">●</span> ';}
function staleCls(t,h){return (Number.isFinite(t)&&Number.isFinite(h)&&h-t>200)?' class="stale"':"";}
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
function renderH0(){
  const h=S.h0;
  $("h0").innerHTML=
    "<span><b>tick</b> "+esc(h.tick)+"</span>"+
    "<span><b>game</b> "+esc(h.game_n)+"</span>"+
    "<span>"+dot(h.learner)+"<b>"+esc(h.learner)+"</b></span>"+
    "<span><b>micro</b> "+esc(h.micro_n)+"/"+esc(h.micro_size)+"</span>"+
    "<span><b>rate</b> "+fmtRate(h.games_per_h)+"</span>"+
    "<span><b>last game</b> "+fmtAge(h.secs_since_game)+"</span>"+
    '<span class="verdict '+esc(h.anchor_verdict)+'"><b>'+esc(h.anchor_verdict)+"</b></span>";
}
function renderBars(){
  const h="b|"+JSON.stringify(S.bars);
  if(h===renderBars._last)return;
  renderBars._last=h;
  $("bars-body").innerHTML=S.bars.map(b=>{
    const pct=(typeof b.rate==="number")?b.rate*100:0;
    const bar="max("+pct.toFixed(1)+"%, "+(pct>0?1:0)+"px)";
    const eli=(typeof b.eligible_in==="number"&&b.eligible_in>0)?b.eligible_in+" to go":"due";
    return "<tr><td>"+dot(b.id)+esc(b.id)+'</td><td class="truncate">'+esc(b.target||"—")+"</td>"+
      '<td><span class="share-wrap"><span class="share-bar"><div style="width:'+bar+'"></div></span>'+
      (typeof b.rate==="number"?fmtShare(pct):"—")+"</span></td>"+
      '<td class="num">'+esc(b.record_wdl)+'</td><td class="num">'+eli+"</td></tr>";
  }).join("")||'<tr><td colspan="5" class="empty">no exploiters yet</td></tr>';
}
function renderStandings(){
  const h="s|"+S.h0.tick+"|"+JSON.stringify(S.standings);
  if(h===renderStandings._last)return;
  renderStandings._last=h;
  $("standings-body").innerHTML=S.standings.map(r=>
    "<tr"+staleCls(r.last_tick,S.h0.tick)+"><td>"+dot(r.id)+esc(r.id)+"</td><td>"+esc(r.class)+
    '</td><td class="num">'+fmtElo(r.elo)+'</td><td class="num">'+r.w+"-"+r.d+"-"+r.l+
    '</td><td class="num">'+esc(r.n)+'</td><td class="num">'+fmtTick(r.last_tick)+"</td></tr>"
  ).join("");
}
function renderAlerts(){
  const h="a|"+JSON.stringify(S.alerts);
  if(h===renderAlerts._last)return;
  renderAlerts._last=h;
  $("alerts").innerHTML=S.alerts.map(a=>
    '<div class="alert-'+esc(a.level)+'">'+esc(a.msg)+' <span class="legend">'+fmtTick(a.tick)+"</span></div>"
  ).join("");
}
function renderBehavior(){
  const h="bh|"+JSON.stringify(S.behavior);
  if(h===renderBehavior._last)return;
  renderBehavior._last=h;
  $("behavior-body").innerHTML=S.behavior.map(r=>
    "<tr><td>"+dot(r.id)+esc(r.id)+"</td>"+
    '<td class="num">'+(typeof r.food==="number"?r.food.toFixed(1):"—")+"</td>"+
    '<td class="num">'+(typeof r.kills==="number"?r.kills.toFixed(1):"—")+"</td>"+
    '<td class="num">'+fmtShare(r.army_pct)+"</td>"+
    '<td class="num">'+(r.length===null||r.length===undefined?"—":esc(r.length))+"</td>"+
    '<td class="num">'+esc(r.n)+"</td></tr>"
  ).join("");
}
/* Canvas frame: shared geometry, gridlines, HiDPI. Direct end labels —
   no legends for ≤4 series (and none above either: labels ride the lines). */
function frame(id){
  const cv=$(id),ctx=cv.getContext("2d");
  const dpr=window.devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;
  cv.width=W*dpr;cv.height=H*dpr;ctx.scale(dpr,dpr);
  ctx.clearRect(0,0,W,H);
  cv.setAttribute("role","img");
  return{ctx,W,H};
}
function drawLadder(){
  const F=frame("ch-ladder"),T=S.anchors,snaps=T.snapshots||[],series=T.series||{};
  const ids=Object.keys(series);
  if(!snaps.length||!ids.length){
    F.ctx.fillStyle="#8A94A0";F.ctx.font="12px system-ui";F.ctx.fillText("no snapshots yet",12,20);return;
  }
  const L=44,R=84,Tp=10,B=22,{ctx,W,H}=F;
  const X=i=>L+(W-L-R)*(snaps.length<2?0.5:i/(snaps.length-1));
  const Y=v=>Tp+(H-Tp-B)*(1-v);
  ctx.strokeStyle="#E9EDF1";ctx.fillStyle="#6B7480";ctx.font="10px system-ui";ctx.lineWidth=1;
  for(let k=0;k<=4;k++){const v=k/4,y=Y(v);
    ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(W-R,y);ctx.stroke();
    ctx.fillText(Math.round(v*100)+"%",6,y+3);}
  ctx.fillStyle="#6B7480";
  ctx.fillText(esc(snaps[0]),L,H-6);
  if(snaps.length>1){const last=snaps[snaps.length-1];
    ctx.fillText(esc(last),W-R-ctx.measureText(last).width,H-6);}
  ids.forEach(aid=>{
    const line=series[aid]||[];
    ctx.strokeStyle="#16191D";ctx.lineWidth=2;ctx.beginPath();
    let started=false,lastX=0,lastY=0;
    line.forEach((v,i)=>{
      if(v===null||v===undefined||!Number.isFinite(v)){started=false;return;}
      const x=X(i),y=Y(v);
      if(!started){ctx.moveTo(x,y);started=true;}
      else ctx.lineTo(x,y);
      lastX=x;lastY=y;});
    ctx.stroke();
    /* direct end label: the series name rides its last point. */
    ctx.fillStyle="#16191D";ctx.font="11px system-ui";
    ctx.fillText(aid,Math.min(lastX+5,W-R+4),lastY+3);
  });
  $("ladder-fallback").innerHTML=ladderFallback();
}
function ladderFallback(){
  const T=S.anchors,snaps=T.snapshots||[],series=T.series||{};
  if(!snaps.length)return '<div class="empty">no snapshots yet</div>';
  const bits=Object.keys(series).map(aid=>{
    const vals=(series[aid]||[]).filter(v=>Number.isFinite(v));
    return aid+" "+(vals.length?Math.round(vals[vals.length-1]*100)+"%":"—");});
  return '<div class="fallback">latest of '+snaps.length+" snapshots: "+esc(bits.join(" · "))+"</div>";
}
function drawPairs(){
  const F=frame("ch-pairs"),{ctx,W,H}=F,pairs=S.pairs||[];
  const order=S.behavior.map(r=>r.id);
  let ids=order.filter(id=>pairs.some(p=>p.a===id||p.b===id));
  pairs.forEach(p=>{[p.a,p.b].forEach(id=>{if(!ids.includes(id))ids.push(id);});});
  ids=ids.slice(0,14);
  if(!ids.length||!pairs.length){
    ctx.fillStyle="#8A94A0";ctx.font="12px system-ui";ctx.fillText("no pairs yet",12,20);return;
  }
  const shareOf={};
  pairs.forEach(p=>{shareOf[p.a+"|"+p.b]=p.share;shareOf[p.b+"|"+p.a]=100-p.share;});
  const L=64,Tp=30,n=ids.length;
  const cell=Math.min((W-L-8)/n,(H-Tp-8)/n);
  ctx.font="10px system-ui";
  ids.forEach((id,i)=>{
    ctx.fillStyle=col(id);
    ctx.fillText(id,L+cell*i+2,Tp-6);
    ctx.fillText(id,4,Tp+cell*i+cell/2+3);
  });
  ids.forEach((a,i)=>{ids.forEach((b,j)=>{
    const x=L+cell*j,y=Tp+cell*i;
    let s=shareOf[a+"|"+b];
    if(a===b||s===undefined||!Number.isFinite(s)){ctx.fillStyle="#F1F3F5";ctx.fillRect(x+1,y+1,cell-2,cell-2);return;}
    const t=Math.abs(s-50)/50;
    ctx.fillStyle=s>=50?"rgba(29,78,216,"+(0.12+0.73*t).toFixed(2)+")":"rgba(22,25,29,"+(0.06+0.25*t).toFixed(2)+")";
    ctx.fillRect(x+1,y+1,cell-2,cell-2);
    if(cell>=26){ctx.fillStyle=s>=50?"#fff":"#16191D";ctx.textAlign="center";
      ctx.fillText(Math.round(s)+"%",x+cell/2,y+cell/2+3);ctx.textAlign="left";}
  });});
  $("pairs-fallback").innerHTML=pairsFallback();
}
function pairsFallback(){
  const top=(S.pairs||[]).slice(0,5);
  if(!top.length)return '<div class="empty">no pairs yet</div>';
  return '<div class="fallback">'+esc(top.map(p=>p.a+" vs "+p.b+" · "+fmtShare(p.share)+" · n="+p.n+" · "+fmtTick(p.last_tick)).join(" · "))+"</div>";
}
function gameRow(g){
  const res=g.result||"draw";
  const names=(g.seats||[]).join(" vs ");
  const bits=(g.seats||[]).map((sid,i)=>{
    const sc=(g.scores||[])[i]??"?";
    const cell=esc(sid)+" "+esc(sc);
    return (res==="win"&&i===0)?"<b>"+cell+"</b>":cell;
  }).join(" · ");
  return "<tr><td class=num>"+dual(g.game_n,g.tick)+"</td><td>"+dot(g.learner)+esc(g.learner)+"</td><td>"+bits+
    '</td><td><span class="badge '+res+'">'+res+"</span></td>"+
    '<td class="replay"><a href="/replay?f='+encodeURIComponent(g.replay)+'" target="_blank" rel="noopener" title="'+esc(names)+' — opens in a new tab">replay<span aria-hidden="true"> ↗</span></a></td></tr>';
}
async function renderGames(my){
  const m=$("member").value.trim();
  if(m)history.replaceState(null,"","#member="+encodeURIComponent(m));
  else history.replaceState(null,"",location.pathname);
  syncClear();
  if(tableBusy("games-body"))return true;
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
  if(my!==seq||$("member").value.trim()!==m)return true;
  const h=m+"|"+gamesOffset+"|"+JSON.stringify(data);
  if(h===lastGames)return true;
  lastGames=h;
  keepScroll($("games-scroll"),()=>{
    $("games-body").innerHTML=data.rows.map(g=>gameRow({
      game_n:g.game_n,tick:g.tick,learner:g.gen,
      seats:(g.seats||[]).map(s=>s.id),scores:(g.seats||[]).map(s=>s.score),
      result:(g.seats&&g.seats.length&&(g.seats[0].result||"draw"))||"draw",
      replay:g.replay})).join("")||(data.total
      ?'<tr><td colspan="5" class="empty">no games on this page — use the pager above</td></tr>'
      :(m?'<tr><td colspan="5" class="empty">no games logged for '+esc(m)+' yet — <a href="#" class="js-clear">clear filter</a></td></tr>'
        :'<tr><td colspan="5" class="empty">no games logged yet — they appear here as each game finishes</td></tr>'));
  });
  bindClear();
  const pages=Math.max(1,Math.ceil(data.total/100));
  const page=Math.min(Math.floor(gamesOffset/100)+1,pages);
  $("games-count").textContent="showing "+data.rows.length+" of "+data.total+" · page "+page+" of "+pages;
  $("pg-prev").disabled=gamesOffset<=0;
  $("pg-next").disabled=gamesOffset+100>=data.total;
  return true;
}
function syncClear(){
  $("clear-filter").style.display=$("member").value?"":"none";
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
  gamesOffset=0;
  history.replaceState(null,"",location.pathname);
  syncClear();renderGames(++seq);
}
function seedMember(){
  const q=new URLSearchParams(location.search).get("member");
  const hm=new URLSearchParams(location.hash.slice(1)).get("member");
  const want=(hm!==null&&hm!=="")?hm:q;
  if(want===null||want===undefined||want===""){
    if(q)history.replaceState(null,"",location.pathname);
    return;
  }
  $("member").value=want;
  gamesOffset=0;
  history.replaceState(null,"","#member="+encodeURIComponent(want));
  syncClear();
}
function renderPill(){
  const el=$("live-pill");
  if(!el)return;
  const ageS=Math.max(0,Math.round((Date.now()-lastTick)/1000));
  if(!live){el.className="live-pill paused";el.textContent="○ paused";return;}
  if(ageS>30){el.className="live-pill stale";el.textContent="▲ stale "+ageS+"s";}
  else{el.className="live-pill ok";el.textContent="● live · "+ageS+"s";}
  $("updated").textContent="updated "+ageS+"s ago · "+(live?"live":"paused");
}
async function load(){
  if(!live)return;
  const my=++seq;
  try{
    const url=(S&&S.mtime)?"/api/snapshot?since="+encodeURIComponent(S.mtime):"/api/snapshot";
    const snap=await fetchJSON(url);
    if(my!==seq)return;
    lastTick=Date.now();
    $("error").style.display="none";
    if(!(snap.unchanged&&S)){
      S=snap.unchanged?S:snap;
      const h=JSON.stringify(snap);
      if(h!==lastSnap){lastSnap=h;
        renderH0();renderBars();renderStandings();renderAlerts();renderBehavior();
        /* canvases repaint from the same snapshot; member options refresh. */
        drawLadder();drawPairs();renderMemberOptions();}
      else renderH0();
      if(!load._seeded){load._seeded=true;seedMember();}
    }
    renderPill();
    await renderGames(my);
  }catch(e){
    $("error").style.display="block";
    $("error").textContent=lastTick?"connection lost ("+e.message+") — showing last good data. retrying…"
      :"connection lost ("+e.message+") — no data yet. retrying…";
  }
}
function renderMemberOptions(){
  const dl=$("member-list"),ids=(S.behavior||[]).map(r=>r.id);
  const h=JSON.stringify(ids);
  if(h===dl.dataset.ids)return;
  dl.dataset.ids=h;
  dl.innerHTML=ids.map(id=>'<option value="'+esc(id)+'">').join("");
  syncClear();
}
let gamesOffset=0;
$("member").addEventListener("input",()=>{gamesOffset=0;++seq;syncClear();renderGames(seq);});
$("member").addEventListener("change",()=>{gamesOffset=0;++seq;syncClear();renderGames(seq);});
$("clear-filter").addEventListener("click",e=>{e.preventDefault();clearMember();});
$("pg-prev").addEventListener("click",()=>{gamesOffset=Math.max(0,gamesOffset-100);renderGames(++seq);});
$("pg-next").addEventListener("click",()=>{gamesOffset+=100;renderGames(++seq);});
$("live-toggle").addEventListener("change",e=>{live=e.target.checked;
  if(!live)seq++;
  $("live-label").textContent=live?"live":"paused";
  renderPill();load();});
let resizeT=0;
window.addEventListener("resize",()=>{clearTimeout(resizeT);resizeT=setTimeout(()=>{if(S){drawLadder();drawPairs();}},150);});
function tick(){renderPill();load().finally(()=>setTimeout(tick,live?10000:10000));}
load();
tick();
"""


def render_page(snap: dict | None = None) -> str:
    """Full page. With a snapshot the H0 strip and all table cards are
    server-rendered (zero JS required to read); without one the shell
    carries shimmer rows so layout doesn't jump."""
    if snap is None:
        skel3 = "".join(
            '<tr class="skel">' + "<td><span></span></td>" * 5 + "</tr>"
            for _ in range(3))
        h0 = h0_strip_html(None)
        ladder_fb = '<div class="empty">loading…</div>'
        bars = skel3
        standings = skel3
        alerts = '<div class="empty">loading…</div>'
        pairs_fb = '<div class="empty">loading…</div>'
        behavior = skel3
        games = skel3
        game_count = "loading…"
        footer_counts = "0 games"
    else:
        h0 = h0_strip_html(snap.get("h0"))
        tick = (snap.get("h0") or {}).get("tick", 0)
        ladder_fb = ladder_fallback_html(snap.get("anchors"))
        bars = bars_rows_html(snap.get("bars"))
        standings = standings_rows_html(snap.get("standings"), tick)
        alerts = alerts_html(snap.get("alerts"))
        pairs_fb = pairs_fallback_html(snap.get("pairs"))
        behavior = behavior_rows_html(snap.get("behavior"), tick)
        games = "".join(game_row_html(g) for g in snap.get("games", [])) or \
            (f'<tr><td colspan="5" class="empty">{EMPTY_GAMES}</td></tr>')
        total = snap.get("game_total", len(snap.get("games", [])))
        game_count = (f"showing {len(snap.get('games', []))} of {total} · "
                      f"page 1 of {max(1, (total + 99) // 100)}")
        footer_counts = f"{total} games · tick {tick}"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AlphaAnt training</title>
<style>{STYLES}</style></head>
<body><a class="skip" href="#games-card">skip to games</a>
<div class="h0" id="h0">{h0}
<span class="live-pill ok" id="live-pill">● live</span>
<span class="updated" id="updated" title="page refresh time"></span></div>
<div class="wrap">
<h1>AlphaAnt continuous league</h1>
<p class="sub">1 main + me + le-a + le-b · equal shares · frozen ladder · no generations</p>
<div id="error" role="alert" style="display:none"></div>
<div class="grid12">
<div class="tcell span7">
<div class="section-title">Anchor ladder</div>
<div class="legend">main snapshot win share vs the frozen ladder, oldest → newest</div>
<div class="card"><canvas id="ch-ladder"></canvas><div id="ladder-fallback">{ladder_fb}</div></div>
</div>
<div class="tcell span5">
<div class="section-title">Distance to bar</div>
<div class="legend">live exploiter window vs its admission bar</div>
<div class="card table-scroll"><table>
<caption style="display:none">Distance to bar</caption>
<tr><th scope="col">slot</th><th scope="col">target</th><th scope="col">rate</th><th scope="col" class="num">window</th><th scope="col" class="num">in</th></tr>
<tbody id="bars-body">{bars}</tbody></table></div>
<div class="section-title">Standings</div>
<div class="legend">running Elo, integers · W-D-L over eval games · rows older than 200 ticks gray out</div>
<div class="card table-scroll"><table>
<caption style="display:none">Standings</caption>
<tr><th scope="col">slot</th><th scope="col">class</th><th scope="col" class="num">elo</th><th scope="col" class="num">w-d-l</th><th scope="col" class="num">n</th><th scope="col" class="num">last</th></tr>
<tbody id="standings-body">{standings}</tbody></table></div>
</div>
<div class="tcell span12">
<div class="section-title">Attention queue</div>
<div class="card" id="alerts">{alerts}</div>
</div>
<div class="tcell span6">
<div class="section-title">Pair matrix</div>
<div class="legend">row share vs column, Laplace-smoothed, 0dp · darker reads stronger</div>
<div class="card"><canvas id="ch-pairs"></canvas><div id="pairs-fallback">{pairs_fb}</div></div>
</div>
<div class="tcell span6">
<div class="section-title">Behavior</div>
<div class="legend">per-game means: food · kills · army share · length · games</div>
<div class="card table-scroll"><table>
<caption style="display:none">Behavior</caption>
<tr><th scope="col">id</th><th scope="col" class="num">food</th><th scope="col" class="num">kills</th><th scope="col" class="num">army</th><th scope="col" class="num">len</th><th scope="col" class="num">n</th></tr>
<tbody id="behavior-body">{behavior}</tbody></table></div>
</div>
<div class="tcell span12">
<div class="section-title">Recent games</div>
<div class="legend">dual time g1234 · t5678 · learner seats first · replay names the bots</div>
<div class="card" id="games-card">
<div class="toolbar">
<label for="member">member</label>
<input id="member" list="member-list" placeholder="all members" autocomplete="off" spellcheck="false">
<datalist id="member-list"></datalist>
<a href="#" id="clear-filter" class="clear-link" style="display:none">clear filter</a>
<label class="live-toggle"><input type="checkbox" id="live-toggle" checked> <span id="live-label">live</span></label>
<span class="pager"><button id="pg-prev" type="button" aria-label="newer games page">← newer</button><button id="pg-next" type="button" aria-label="older games page">older →</button></span>
<span class="legend" id="games-count" style="margin:0">{game_count}</span>
</div>
<div class="table-scroll table-tall" id="games-scroll"><table>
<caption style="display:none">Recent games, newest first</caption>
<tr><th scope="col">game</th><th scope="col">learner</th><th scope="col">matchup</th><th scope="col">result</th><th scope="col">replay</th></tr>
<tbody id="games-body">{games}</tbody></table></div>
</div>
</div>
</div>
<div class="footer"><span>archive ml/archive</span><span class="sep">·</span><span>{footer_counts}</span><span class="sep">·</span><span>polls every 10s, values replace in place</span></div>
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
