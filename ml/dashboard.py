"""Training dashboard: key stats, population, games, replay links.

Stdlib only. Serves a live page over HTTP so it works from a Windows
browser against WSL (open http://localhost:PORT; WSL2 forwards
localhost automatically). Polls the archive; no restart needed between
generations.

  .venv/bin/python ml/dashboard.py [--port 8080] [--archive ml/archive]

Routes: / (page), /api/snapshot (everything as JSON),
/api/games?limit=&offset= (game index slice + total),
/replay?f=<archive-relative replay> (visualizer page, new tab per link),
/static/v/<path> (visualizer js/data/img).
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

import archive

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


SNAPSHOT_FILES = ("games.jsonl", "updates.jsonl", "state.json")


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

SPARK_MAX = 40  # sparkline points (behavior sparks cover the last 40)


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
    return text[: -len(suffix)] if text.endswith(suffix) else text


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
            pairs = [
                (i, i)
                for i, p in enumerate(positions)
                if p[0] == lo and p[1] in (None, slo)
            ]
            pairs.append(("new", "new"))
        else:
            pairs = []
            pa_list = [
                i for i, p in enumerate(positions) if p[0] == lo and p[1] in (None, slo)
            ] + ["new"]
            for pa in pa_list:
                pb_list = [
                    i
                    for i, p in enumerate(positions)
                    if i != pa and p[0] == hi and p[1] in (None, shi)
                ] + ["new"]
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
            realize[key] = len(got) if got is not None else 10**9
        return realize[key]

    best_assign: list[int] | None = None
    best_cost = (10**9, 0)

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
            if after is not None and before is not None and len(after) <= len(before):
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


def build_game(
    gen: str,
    kind: str,
    map: str | None,
    replay: str,
    items: list[tuple[tuple, dict]],
    tick: int | None = None,
) -> dict | None:
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
    buckets: dict[tuple, dict] = {}
    for r in [r for _, r in items]:
        food, kills, army = r.get("food"), r.get("kills"), r.get("army")
        if not (
            isinstance(food, list)
            and isinstance(kills, list)
            and isinstance(army, list)
        ):
            continue
        if len(food) < 2 or len(kills) < 2 or len(army) < 2:
            continue
        try:
            f = (float(food[0]), float(food[1]))
            k = (float(kills[0]), float(kills[1]))
            a = (float(army[0]), float(army[1]))
        except (TypeError, ValueError):
            continue
        for cid, sc, fi, ki, ai in (
            (r["a"], r["score_a"], f[0], k[0], a[0]),
            (r["b"], r["score_b"], f[1], k[1], a[1]),
        ):
            cell = buckets.setdefault((cid, sc), {"food": [], "kills": [], "army": []})
            cell["food"].append(fi)
            cell["kills"].append(ki)
            if a[0] + a[1] > 0:
                cell["army"].append(100 * ai / (a[0] + a[1]))
    length = None
    for r in [r for _, r in items]:
        if isinstance(r.get("length"), (int, float)):
            length = r["length"]
            break
    for k, (cid, sc) in enumerate(pos):
        others = [s for j, s in enumerate(scores) if j != k]
        margin = sc - (max(others) if others else sc)
        result = "win" if sc == top and ntop == 1 else ("draw" if sc == top else "loss")
        cell = buckets.get((cid, sc), {"food": [], "kills": [], "army": []})

        def _mean(vals):
            return sum(vals) / len(vals) if vals else None

        seats.append(
            {
                "id": cid,
                "score": sc,
                "rank": ranks[k],
                "margin": margin,
                "pts": 1.0 if result == "win" else (0.5 if result == "draw" else 0.0),
                "result": result,
                "food": _mean(cell["food"]),
                "kills": _mean(cell["kills"]),
                "army_pct": int(round(_mean(cell["army"]))) if cell["army"] else None,
            }
        )
    return {
        "gen": gen,
        "kind": kind,
        "map": map,
        "replay": replay,
        "n": len(seats),
        "seats": seats,
        "pairs": [
            {"a": r["a"], "b": r["b"], "score_a": r["score_a"], "score_b": r["score_b"]}
            for _, r in items
        ],
        "tick": tick,
        "length": length,
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
        ticks = [
            r.get("tick") for r in oldest if isinstance(r.get("tick"), (int, float))
        ]
        tick = max(ticks) if ticks else None
        for block in partition_group([_norm_row(r) for r in oldest]):
            g = build_game(
                m0.get("gen", "main"),
                m0.get("kind", "train"),
                m0.get("map"),
                m0["replay"],
                [(n, raws[n]) for n in block],
                tick=tick,
            )
            if g is not None:
                games.append(g)
    return games


def member_game_result(game: dict, ref: str) -> str | None:
    """Ref's per-game outcome: best seat wins when a member holds several
    (duplicate-seat extras)."""
    order = {"win": 0, "draw": 1, "loss": 2}
    outs = [s["result"] for s in game["seats"] if s["id"] == ref]
    return min(outs, key=order.__getitem__) if outs else None


_snapshot_cache: dict = {}


def _snapshot_key(base: Path) -> tuple:
    """Memo key covering every file snapshot() reads: mtime+size per
    file, so any writer (scheduler, trainer, status) invalidates."""
    parts = []
    for name in ("games.jsonl", "updates.jsonl", "state.json"):
        try:
            st = (base / name).stat()
            parts.append((name, st.st_mtime_ns, st.st_size))
        except OSError:
            parts.append((name, None, None))
    return (str(base.resolve()), tuple(parts))


def snapshot(base: Path) -> dict:
    """Everything the page needs, in one JSON-able dict.

    Memoized on the file stats: a poll storm between games reuses the
    last build instead of regrouping the game log."""
    return _memo(_snapshot_cache, _snapshot_key(base), lambda: _build_snapshot(base))


# ---------------------------------------------------------------- NEW CONTRACT
# Pure AZ board: h0, training, behavior, games, alerts, mtime. Derived
# from games.jsonl rows (tick + behavior facts), updates.jsonl (PPO
# measurements) and state.json (tick + micro). Unknowns read as None
# and render as a dash, never as zero.

#: No game for this long: training is stuck.
ALERT_IDLE_S = 15 * 60


def behavior_ids(base: Path) -> list[str]:
    """Board row ids: just main. One learner, one row."""
    return ["main"]


def _wall_now() -> float:
    import time as _time

    return _time.time()


def rate_window(base: Path) -> tuple[int | None, float | None]:
    """(games in the last hour, seconds since the last game).

    From the wall-clock stamps the scheduler logs per game; the game
    index mtime is the recency fallback when rows predate stamps.
    None when nothing is logged yet."""
    stamps = sorted(
        r["t"] for r in cached_games(base) if isinstance(r.get("t"), (int, float))
    )
    if stamps:
        now = _wall_now()
        return (sum(1 for t in stamps if t > now - 3600), max(0.0, now - stamps[-1]))
    try:
        return (None, max(0.0, _wall_now() - (base / "games.jsonl").stat().st_mtime))
    except OSError:
        return (None, None)


def h0_panel(
    base: Path, state: dict | None, grouped: list[dict], updates: list[dict]
) -> dict:
    """Sticky strip facts: tick · games · updates · micro · last game ·
    decisive rate over the last 40."""
    state = state or {}
    games_per_h, secs = rate_window(base)
    last = grouped[0] if grouped else None
    seats = (last or {}).get("seats", []) or []
    last_result = seats[0].get("result") if seats else None
    last_length = (last or {}).get("length")
    recent = grouped[:40]
    dec = [g for g in recent if (g.get("seats", [{}])[0].get("result")) != "draw"]
    return {
        "tick": state.get("tick", 0),
        "games": len(grouped),
        "updates": len(updates),
        "micro": state.get("micro", 0),
        "games_per_h": games_per_h,
        "secs_since_game": secs,
        "last_result": last_result,
        "last_length": last_length,
        "decisive": round(len(dec) / len(recent), 2) if recent else None,
    }


def spark_svg(vals: list, w: int = 90, h: int = 18) -> str:
    """Inline sparkline: min/max-normalized polyline, flat renders midline.

    Empty input renders nothing (the cell shows — instead)."""
    pts = [v for v in vals if isinstance(v, (int, float))]
    if not pts:
        return ""
    lo, hi = min(pts), max(pts)
    span = hi - lo or 1.0
    n = len(pts)

    def _x(i):
        return round(i * w / max(n - 1, 1), 1)

    def _y(v):
        return round(h - 2 - (v - lo) * (h - 4) / span, 1)

    line = " ".join(f"{_x(i)},{_y(v)}" for i, v in enumerate(pts))
    return (
        f'<svg class="spk" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" aria-hidden="true">'
        f'<polyline points="{line}" /></svg>'
    )


def behavior_panel(base: Path) -> list[dict]:
    """Per snapshot id + live slots: mean food/kills/army share/length
    over logged behavior rows. Null when unplayed or unstamped."""
    acc: dict[str, dict] = {}
    for cid in behavior_ids(base):
        acc[cid] = {"food": [], "kills": [], "army": [], "length": [], "n": 0}
    for r in reversed(cached_games(base)):
        food, kills, army = r.get("food"), r.get("kills"), r.get("army")
        if not (
            isinstance(food, list)
            and isinstance(kills, list)
            and isinstance(army, list)
        ):
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
        sides = ((r.get("a"), f[0], k[0], a[0]), (r.get("b"), f[1], k[1], a[1]))
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

        out.append(
            {
                "id": cid,
                "food": round(_mean(cell["food"]), 1) if cell["food"] else None,
                "kills": round(_mean(cell["kills"]), 1) if cell["kills"] else None,
                "army_pct": int(round(_mean(cell["army"]))) if cell["army"] else None,
                "length": int(round(_mean(cell["length"]))) if cell["length"] else None,
                "n": n,
                "spark": {
                    "food": [round(v, 1) for v in cell["food"][-SPARK_MAX:]],
                    "kills": [round(v, 1) for v in cell["kills"][-SPARK_MAX:]],
                    "army": [int(round(v)) for v in cell["army"][-SPARK_MAX:]],
                    "length": list(cell["length"][-SPARK_MAX:]),
                },
            }
        )
    return out


def games_panel(grouped: list[dict], limit: int = 100) -> tuple[list[dict], int]:
    """Recent games newest-first: the tick IS the game number."""
    total = len(grouped)
    out = []
    for idx, g in enumerate(grouped[:limit]):
        seats = g.get("seats", []) or []
        ref = seats[0].get("id") if seats else None
        out.append(
            {
                "tick": g.get("tick"),
                "learner": g.get("gen"),
                "seats": [s.get("id") for s in seats],
                "scores": [s.get("score") for s in seats],
                "stats": [
                    {
                        "food": s.get("food"),
                        "kills": s.get("kills"),
                        "army_pct": s.get("army_pct"),
                    }
                    for s in seats
                ],
                "length": g.get("length"),
                "result": member_game_result(g, ref) if ref else None,
                "replay": g.get("replay"),
            }
        )
    return out, total


def _fmt_idle(secs: float) -> str:
    s = int(round(secs))
    if s < 60:
        return f"{s}s"
    return f"{s // 60}m {s % 60:02d}s"


def training_panel(updates: list[dict], limit: int = 8) -> list[dict]:
    """Latest PPO updates, newest first: the AZ training vital signs.

    One row per update: loss, entropy, KL, clipfrac, explained variance
    and mean return. Flat or rising loss with collapsing entropy means
    the policy stopped learning; clipfrac pinned near 1 means the clip
    binds every step."""
    rows = []
    for u in list(reversed(updates[-40:]))[:limit]:
        rows.append(
            {
                "tick": u.get("tick"),
                "rows": u.get("rows"),
                "mean_return": u.get("mean_return"),
                "explained_var": u.get("explained_var"),
                "loss": u.get("loss"),
                "entropy": u.get("entropy"),
                "kl": u.get("kl"),
                "clipfrac": u.get("clipfrac"),
                "pg_loss": u.get("pg_loss"),
                "v_loss": u.get("v_loss"),
            }
        )
    return rows


def alerts_panel(base: Path, h0: dict) -> list[dict]:
    """Attention queue: stuck training; else one all-clear line."""
    tick = h0.get("tick", 0)
    secs = h0.get("secs_since_game")
    if isinstance(secs, (int, float)) and secs > ALERT_IDLE_S:
        return [
            {"level": "alert", "msg": f"no game for {_fmt_idle(secs)}", "tick": tick}
        ]
    return [{"level": "ok", "msg": "all clear", "tick": tick}]


def _build_snapshot(base: Path) -> dict:
    archive.init(base)
    state = archive.load_state(base)
    grouped = cached_grouped(base)
    updates = archive.list_updates(base)
    h0 = h0_panel(base, state, grouped, updates)
    games, total = games_panel(grouped)
    return {
        "h0": h0,
        "training": training_panel(updates),
        "behavior": behavior_panel(base),
        "games": games,
        "game_total": total,
        "alerts": alerts_panel(base, h0),
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
    page = page.replace(
        "<title>Ant Canvas</title>",
        f"<title>replay {html.escape(rel)} · AZDash</title>",
    )
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
                        _json(self, {"unchanged": True, "mtime": archive_mtime(base)})
                    else:
                        _json(self, snapshot(base))
                elif parsed.path == "/api/games":
                    q = parse_qs(parsed.query)
                    try:
                        limit = max(0, min(int(q.get("limit", ["100"])[0]), 200))
                    except ValueError:
                        limit = 100
                    try:
                        offset = max(int(q.get("offset", ["0"])[0]), 0)
                    except ValueError:
                        offset = 0
                    rows = cached_grouped(base)
                    total = len(rows)
                    offset = min(offset, total)
                    _json(self, {"total": total, "rows": rows[offset : offset + limit]})
                elif parsed.path == "/replay":
                    rel = parse_qs(parsed.query).get("f", [None])[0]
                    page = replay_page(base, rel)
                    if page is None:
                        self.send_error(404, "no such replay")
                    else:
                        self._send(page.encode(), "text/html")
                elif parsed.path.startswith("/static/v/"):
                    target = (VIS_DIR / parsed.path[len("/static/v/") :]).resolve()
                    if (
                        not str(target).startswith(str(VIS_DIR.resolve()))
                        or not target.is_file()
                    ):
                        self.send_error(404, "no such file")
                    else:
                        ctype = (
                            "application/javascript"
                            if target.suffix == ".js"
                            else (
                                "text/html"
                                if target.suffix in (".html", ".htm")
                                else "image/png"
                                if target.suffix == ".png"
                                else "application/octet-stream"
                            )
                        )
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

SLOT_COLORS = {"main": "#1d4ed8"}
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


def fmt_share100(share) -> str:
    """A 0-100 share to 0dp, unknown to a dash."""
    return f"{share:.0f}%" if isinstance(share, (int, float)) else "—"


def fmt_tick(t) -> str:
    return f"t{t}" if isinstance(t, (int, float)) else "t—"


def is_stale(row_tick, h0_tick) -> bool:
    """A row older than 200 ticks vs the H0 tick reads grayed out."""
    return (
        isinstance(row_tick, (int, float))
        and isinstance(h0_tick, (int, float))
        and h0_tick - row_tick > 200
    )


def _dot(cid) -> str:
    return f'<span aria-hidden="true" style="color:{slot_color(cid)}">●</span> '


def h0_strip_html(h0: dict | None) -> str:
    """Twin of JS renderH0."""
    if h0 is None:
        return '<span class="stat-label">loading…</span>'
    last = h0.get("last_result") or "—"
    last_len = h0.get("last_length")
    last_len = last_len if isinstance(last_len, (int, float)) else "—"
    dec = h0.get("decisive")
    dec = f"{dec:.0%}" if isinstance(dec, (int, float)) else "—"
    return (
        f"<span><b>game</b> {_esc(h0.get('tick', 0))}</span>"
        f"<span>{_dot('main')}main</span>"
        f"<span><b>updates</b> {_esc(h0.get('updates', 0))}</span>"
        f"<span><b>micro</b> {_esc(h0.get('micro', 0))}/8</span>"
        f"<span><b>decisive÷40</b> {dec}</span>"
        f"<span><b>last</b> {_esc(last)} {last_len}</span>"
        f"<span><b>rate</b> {fmt_rate(h0.get('games_per_h'))}</span>"
        f"<span><b>last game</b> {fmt_age(h0.get('secs_since_game'))}</span>"
    )


def alerts_html(alerts: list | None) -> str:
    """Twin of JS renderAlerts: red text lines, or one all-clear."""
    if not alerts:
        return '<div class="empty">loading…</div>'
    return "".join(
        f'<div class="alert-{a.get("level", "ok")}">'
        f'{_esc(a.get("msg"))} <span class="legend">'
        f"{fmt_tick(a.get('tick'))}</span></div>"
        for a in alerts
    )


def behavior_rows_html(rows: list | None, h0_tick) -> str:
    """Twin of JS behaviorRow."""
    if not rows:
        return (
            '<tr><td colspan="6" class="empty">no behavior yet — '
            "games log food/kills/army as they finish</td></tr>"
        )
    out = []
    for r in rows:
        # behavior rows carry means, not ticks: never stale by recency.
        food = r.get("food")
        kills = r.get("kills")
        sp = r.get("spark") or {}
        out.append(
            f"<tr><td>{_dot(r.get('id'))}{_esc(r.get('id'))}</td>"
            f'<td class="num">'
            f"{f'{food:.1f}' if isinstance(food, (int, float)) else '—'}"
            f"{spark_svg(sp.get('food') or [])}</td>"
            f'<td class="num">'
            f"{f'{kills:.1f}' if isinstance(kills, (int, float)) else '—'}"
            f"{spark_svg(sp.get('kills') or [])}</td>"
            f'<td class="num">{fmt_share100(r.get("army_pct"))}'
            f"{spark_svg(sp.get('army') or [])}</td>"
            f'<td class="num">{_esc(r.get("length")) if r.get("length") is not None else "—"}'
            f"{spark_svg(sp.get('length') or [])}</td>"
            f'<td class="num">{_esc(r.get("n"))}</td></tr>'
        )
    return "".join(out)


def _stat_text(food, kills, army_pct) -> str:
    """`8.0f · 23.0k · 33%`, unknowns read as dashes."""
    f = "—" if food is None else f"{food:.1f}f"
    k = "—" if kills is None else f"{kills:.1f}k"
    a = "—" if army_pct is None else f"{army_pct}%"
    return f"{f} · {k} · {a}"


def game_replay_label(g: dict) -> str:
    """`c 3 (8.0f · 23.0k · 33%) · m 1 (…)`: seat ids with scores and
    per-seat behavior, winner bold upstream."""
    seats = g.get("seats", []) or []
    scores = g.get("scores", []) or []
    stats = g.get("stats", []) or []
    bits = []
    for i, sid in enumerate(seats):
        sc = scores[i] if i < len(scores) else "?"
        st = stats[i] if i < len(stats) else {}
        bit = (
            f"{_esc(sid)} {_esc(sc)} "
            f"({_stat_text(st.get('food'), st.get('kills'), st.get('army_pct'))})"
        )
        if g.get("result") == "win" and i == 0:
            bits.append(f"<b>{bit}</b>")
        else:
            bits.append(bit)
    return " · ".join(bits)


def game_row_html(g: dict) -> str:
    """Twin of JS gameRow: tick · learner · matchup(+behavior) · len ·
    result · replay."""
    res = g.get("result") or "draw"
    names = " vs ".join(_esc(s) for s in g.get("seats", []) or [])
    length = g.get("length")
    return (
        f'<tr><td class="num">{fmt_tick(g.get("tick"))}</td>'
        f"<td>{_dot(g.get('learner'))}{_esc(g.get('learner'))}</td>"
        f"<td>{game_replay_label(g)}</td>"
        f'<td class="num">{length if isinstance(length, (int, float)) else "—"}</td>'
        f'<td><span class="badge {res}">{res}</span></td>'
        f'<td class="replay"><a href="/replay?f={_esc(g.get("replay"))}" '
        f'target="_blank" rel="noopener" '
        f'title="{names} — opens in a new tab">'
        f'replay<span aria-hidden="true"> ↗</span></a></td></tr>'
    )


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
.spk{width:90px;height:18px;vertical-align:middle;margin-left:8px;}
.spk polyline{fill:none;stroke:#64748b;stroke-width:1.2;}
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
const COLORS={main:"#1d4ed8"};
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
function fmtShare(s){return (s===null||s===undefined||!Number.isFinite(+s))?"—":Math.round(s)+"%";}
function fmtTick(t){return (t===null||t===undefined)?"t—":"t"+t;}
function dot(id){return '<span aria-hidden="true" style="color:'+col(id)+'">●</span> ';}
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
  const dec=(typeof h.decisive==="number")?Math.round(h.decisive*100)+"%":"—";
  const last=h.last_result||"—";
  const lastLen=(h.last_length===null||h.last_length===undefined)?"—":h.last_length;
  $("h0").innerHTML=
    "<span><b>game</b> "+esc(h.tick)+"</span>"+
    "<span>"+dot("main")+"main</span>"+
    "<span><b>updates</b> "+esc(h.updates)+"</span>"+
    "<span><b>micro</b> "+esc(h.micro)+"/8</span>"+
    "<span><b>decisive÷40</b> "+dec+"</span>"+
    "<span><b>last</b> "+esc(last)+" "+lastLen+"</span>"+
    "<span><b>rate</b> "+fmtRate(h.games_per_h)+"</span>"+
    "<span><b>last game</b> "+fmtAge(h.secs_since_game)+"</span>";
}
function num(v,dp){
  return (v===null||v===undefined||!Number.isFinite(+v))?"—":Number(v).toFixed(dp===undefined?3:dp);
}
function renderTraining(){
  const h="t|"+JSON.stringify(S.training);
  if(h===renderTraining._last)return;
  renderTraining._last=h;
  $("training-body").innerHTML=(S.training||[]).map(u=>
    "<tr><td class=num>"+fmtTick(u.tick)+'</td><td class="num">'+esc(u.rows)+
    '</td><td class="num">'+num(u.mean_return,2)+'</td><td class="num">'+num(u.explained_var,2)+
    '</td><td class="num">'+num(u.loss)+'</td><td class="num">'+num(u.entropy)+
    '</td><td class="num">'+num(u.kl)+'</td><td class="num">'+num(u.clipfrac,2)+"</td></tr>"
  ).join("")||'<tr><td colspan="8" class="empty">no updates yet — the first lands after 8 games</td></tr>';
}
function renderAlerts(){
  const h="a|"+JSON.stringify(S.alerts);
  if(h===renderAlerts._last)return;
  renderAlerts._last=h;
  $("alerts").innerHTML=S.alerts.map(a=>
    '<div class="alert-'+esc(a.level)+'">'+esc(a.msg)+' <span class="legend">'+fmtTick(a.tick)+"</span></div>"
  ).join("");
}
function spark(vals){
  const p=(vals||[]).filter(v=>typeof v==="number");
  if(!p.length)return "";
  const lo=Math.min.apply(null,p),hi=Math.max.apply(null,p),sp=(hi-lo)||1;
  const w=90,h=18,n=p.length;
  const pts=p.map((v,i)=>((i*w/Math.max(n-1,1)).toFixed(1))+","+(h-2-(v-lo)*(h-4)/sp).toFixed(1)).join(" ");
  return '<svg class="spk" width="'+w+'" height="'+h+'" viewBox="0 0 '+w+' '+h+'" aria-hidden="true"><polyline points="'+pts+'"/></svg>';
}
function renderBehavior(){
  const h="bh|"+JSON.stringify(S.behavior);
  if(h===renderBehavior._last)return;
  renderBehavior._last=h;
  const cell=(v,sp,fmt)=>'<td class="num">'+v+sp+"</td>";
  $("behavior-body").innerHTML=S.behavior.map(r=>{
    const sp=r.spark||{};
    return "<tr><td>"+dot(r.id)+esc(r.id)+"</td>"+
    cell(typeof r.food==="number"?r.food.toFixed(1):"—",spark(sp.food))+
    cell(typeof r.kills==="number"?r.kills.toFixed(1):"—",spark(sp.kills))+
    cell(fmtShare(r.army_pct),spark(sp.army))+
    cell(r.length===null||r.length===undefined?"—":esc(r.length),spark(sp.length))+
    '<td class="num">'+esc(r.n)+"</td></tr>";
  }).join("");
}
/* Canvas frame: shared geometry, gridlines, HiDPI. Direct end labels —
   no legends for ≤4 series (and none above either: labels ride the lines). */
function statText(food,kills,army){const f=(food==null?"—":Number(food).toFixed(1)+"f");const k=(kills==null?"—":Number(kills).toFixed(1)+"k");const a=(army==null?"—":army+"%");return f+" · "+k+" · "+a;}
function gameRow(g){
  const res=g.result||"draw";
  const names=(g.seats||[]).join(" vs ");
  const bits=(g.seats||[]).map((sid,i)=>{
    const sc=(g.scores||[])[i]??"?";
    const st=(g.stats||[])[i]||{};
    const cell=esc(sid)+" "+esc(sc)+" ("+statText(st.food,st.kills,st.army_pct)+")";
    return (res==="win"&&i===0)?"<b>"+cell+"</b>":cell;
  }).join(" · ");
  const len=(g.len==null?"—":g.len);
  return "<tr><td class=num>"+fmtTick(g.tick)+"</td><td>"+dot(g.learner)+esc(g.learner)+"</td><td>"+bits+
    '</td><td class="num">'+len+'</td><td><span class="badge '+res+'">'+res+"</span></td>"+
    '<td class="replay"><a href="/replay?f='+encodeURIComponent(g.replay)+'" target="_blank" rel="noopener" title="'+esc(names)+' — opens in a new tab">replay<span aria-hidden="true"> ↗</span></a></td></tr>';
}
async function renderGames(my){
  if(tableBusy("games-body"))return true;
  const qparts=["limit=100","offset="+gamesOffset];
  let data;
  try{data=await fetchJSON("/api/games?"+qparts.join("&"));}
  catch(e){
    $("error").style.display="block";
    $("error").textContent="games feed failed ("+e.message+") — showing last good table. retrying…";
    return false;
  }
  if(my!==seq)return true;
  const h=gamesOffset+"|"+JSON.stringify(data);
  if(h===lastGames)return true;
  lastGames=h;
  keepScroll($("games-scroll"),()=>{
    $("games-body").innerHTML=data.rows.map(g=>gameRow({
      tick:g.tick,learner:g.gen,
      seats:(g.seats||[]).map(s=>s.id),scores:(g.seats||[]).map(s=>s.score),
      stats:(g.seats||[]).map(s=>({food:s.food,kills:s.kills,army_pct:s.army_pct})),
      len:g.length,
      result:gameResult(g),replay:g.replay})).join("")||(data.total
      ?'<tr><td colspan="6" class="empty">no games on this page — use the pager above</td></tr>'
      :'<tr><td colspan="6" class="empty">no games logged yet — they appear here as each game finishes</td></tr>');
  });
  bindClear();
  const pages=Math.max(1,Math.ceil(data.total/100));
  const page=Math.min(Math.floor(gamesOffset/100)+1,pages);
  $("games-count").textContent="showing "+data.rows.length+" of "+data.total+" · page "+page+" of "+pages;
  $("pg-prev").disabled=gamesOffset<=0;
  $("pg-next").disabled=gamesOffset+100>=data.total;
  return true;
}
function gameResult(g){
  const seats=g.seats||[];
  const ref=seats[0];
  return (ref&&ref.result)||"draw";
}
function bindClear(){
  /* no-op: the learner filter is gone (one learner, no filter). */
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
        renderH0();renderAlerts();renderBehavior();renderTraining();}
      else renderH0();
    }
    renderPill();
    await renderGames(my);
  }catch(e){
    $("error").style.display="block";
    $("error").textContent=lastTick?"connection lost ("+e.message+") — showing last good data. retrying…"
      :"connection lost ("+e.message+") — no data yet. retrying…";
  }
}
let gamesOffset=0;
$("pg-prev").addEventListener("click",()=>{gamesOffset=Math.max(0,gamesOffset-100);renderGames(++seq);});
$("pg-next").addEventListener("click",()=>{gamesOffset+=100;renderGames(++seq);});
$("live-toggle").addEventListener("change",e=>{live=e.target.checked;
  if(!live)seq++;
  $("live-label").textContent=live?"live":"paused";
  renderPill();load();});
function tick(){renderPill();load().finally(()=>setTimeout(tick,live?10000:10000));}
load();
tick();
"""


def training_rows_html(rows: list | None) -> str:
    """Twin of JS renderTraining."""
    if not rows:
        return (
            '<tr><td colspan="8" class="empty">no updates yet — '
            "the first lands after 8 games</td></tr>"
        )
    out = []
    for u in rows:
        out.append(
            '<tr><td class="num">' + fmt_tick(u.get("tick")) + "</td>"
            '<td class="num">' + _esc(u.get("rows")) + "</td>"
            '<td class="num">' + _num(u.get("mean_return"), 2) + "</td>"
            '<td class="num">' + _num(u.get("explained_var"), 2) + "</td>"
            '<td class="num">' + _num(u.get("loss")) + "</td>"
            '<td class="num">' + _num(u.get("entropy")) + "</td>"
            '<td class="num">' + _num(u.get("kl")) + "</td>"
            '<td class="num">' + _num(u.get("clipfrac"), 2) + "</td></tr>"
        )
    return "".join(out)


def _num(v, dp: int = 3) -> str:
    """Number to dp places, unknown to a dash."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    if f != f or f in (float("inf"), float("-inf")):
        return "—"
    return f"{f:.{dp}f}"


def render_page(snap: dict | None = None) -> str:
    """Full page. With a snapshot the H0 strip and all table cards are
    server-rendered (zero JS required to read); without one the shell
    carries shimmer rows so layout doesn't jump."""
    if snap is None:
        skel3 = "".join(
            '<tr class="skel">' + "<td><span></span></td>" * 5 + "</tr>"
            for _ in range(3)
        )
        skel8 = "".join(
            '<tr class="skel">' + "<td><span></span></td>" * 8 + "</tr>"
            for _ in range(3)
        )
        h0 = h0_strip_html(None)
        training = skel8
        alerts = '<div class="empty">loading…</div>'
        behavior = skel3
        games = skel3
        game_count = "loading…"
        footer_counts = "0 games"
    else:
        h0 = h0_strip_html(snap.get("h0"))
        tick = (snap.get("h0") or {}).get("tick", 0)
        training = training_rows_html(snap.get("training"))
        alerts = alerts_html(snap.get("alerts"))
        behavior = behavior_rows_html(snap.get("behavior"), tick)
        games = "".join(game_row_html(g) for g in snap.get("games", [])) or (
            f'<tr><td colspan="6" class="empty">{EMPTY_GAMES}</td></tr>'
        )
        total = snap.get("game_total", len(snap.get("games", [])))
        game_count = (
            f"showing {len(snap.get('games', []))} of {total} · "
            f"page 1 of {max(1, (total + 99) // 100)}"
        )
        footer_counts = f"{total} games"
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
<h1>AlphaAnt mirror self-play</h1>
<p class="sub">one net · latest vs latest · every 8th game trains</p>
<div id="error" role="alert" style="display:none"></div>
<div class="grid12">
<div class="tcell span12">
<div class="section-title">Training</div>
<div class="legend">PPO vital signs per update, newest first · flat or rising loss with collapsing entropy means learning stopped · clipfrac near 1 means the clip binds every step · explained variance tracks the value head (1 is perfect)</div>
<div class="card table-scroll"><table>
<caption style="display:none">Training updates, newest first</caption>
<tr><th scope="col">update</th><th scope="col" class="num">rows</th><th scope="col" class="num">mean ret</th><th scope="col" class="num">expl var</th><th scope="col" class="num">loss</th><th scope="col" class="num">entropy</th><th scope="col" class="num">kl</th><th scope="col" class="num">clipfrac</th></tr>
<tbody id="training-body">{training}</tbody></table></div>
</div>
<div class="tcell span12">
<div class="section-title">Attention queue</div>
<div class="card" id="alerts">{alerts}</div>
</div>
<div class="tcell span12">
<div class="section-title">Behavior</div>
<div class="legend">per-game means: food · kills · army share · length · games · sparks cover the member's last 40 games</div>
<div class="card table-scroll"><table>
<caption style="display:none">Behavior</caption>
<tr><th scope="col">id</th><th scope="col" class="num">food</th><th scope="col" class="num">kills</th><th scope="col" class="num">army</th><th scope="col" class="num">len</th><th scope="col" class="num">n</th></tr>
<tbody id="behavior-body">{behavior}</tbody></table></div>
</div>
<div class="tcell span12">
<div class="section-title">Recent games</div>
<div class="legend">tick is the game number · learner seats first · replay names the bots · per-seat food/kills/army% + game length</div>
<div class="card" id="games-card">
<div class="toolbar">
<label class="live-toggle"><input type="checkbox" id="live-toggle" checked> <span id="live-label">live</span></label>
<span class="pager"><button id="pg-prev" type="button" aria-label="newer games page">← newer</button><button id="pg-next" type="button" aria-label="older games page">older →</button></span>
<span class="legend" id="games-count" style="margin:0">{game_count}</span>
</div>
<div class="table-scroll table-tall" id="games-scroll"><table>
<caption style="display:none">Recent games, newest first</caption>
<tr><th scope="col">game</th><th scope="col">learner</th><th scope="col">matchup</th><th scope="col" class="num">len</th><th scope="col">result</th><th scope="col">replay</th></tr>
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
    base = (
        (ROOT / args.archive).resolve()
        if not Path(args.archive).is_absolute()
        else Path(args.archive)
    )
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
