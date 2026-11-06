"""Dashboard data layer: archive reads, snapshot, panels, alerts.

Pure data (no HTML, no HTTP). Imported by train/dashboard.py (server) and
train/dashpage.py (first-paint render).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import html
import json
import threading
import time

import archive

VIS_DIR = ROOT / "tools" / "visualizer"
TEMPLATE = (VIS_DIR / "replay.html.template").read_text()

_memo_lock = threading.RLock()



def _memo(cache: dict, key, thunk):
    """One-slot memo: recompute only when the key changes.

    Lock-guarded (RLock: thunks nest, e.g. panel build reads the
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



def cached_panel(base: Path) -> list[dict]:
    """Panel rows, newest first, rebuilt only when games.jsonl changes.

    snapshot() and /api/games share one build per poll cycle."""
    path = base / "games.jsonl"
    try:
        st = path.stat()
    except OSError:
        return []
    return _memo(
        _panel_cache,
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



PAGE_SIZE = 100  # games pager limit (matches /api/games default)



SPARK_MAX = 40  # sparkline points (behavior sparks cover the last 40)



def _rnd(x, nd: int):
    """Round JSON numbers server-side (P0-2/P1-5); pass anything else
    through untouched."""
    return round(x, nd) if isinstance(x, (int, float)) else x



def rank_of(scores: list) -> list[int]:
    """Per-seat rank with the engine's formula (tools/engine.py): each seat
    takes the index of its score in the descending sort, so ties share a
    rank and the next rank skips ([10,10,5] -> [0,0,2])."""
    ordered = sorted(scores, reverse=True)
    return [ordered.index(s) for s in scores]



def _seat_stats(row: dict, i: int) -> dict:
    """Per-seat behavior facts from a mirror row: food/kills raw, army
    as the seat's share of all living armies. Unknown reads None."""
    food, kills, army = row.get("food"), row.get("kills"), row.get("army")
    try:
        f = float(food[i])
        k = float(kills[i])
        a = [float(x) for x in army]
    except (TypeError, ValueError, IndexError):
        return {"food": None, "kills": None, "army_pct": None}
    total = sum(a)
    share = 100 * a[i] / total if total > 0 else None
    return {
        "food": f,
        "kills": k,
        "army_pct": int(round(share)) if share is not None else None,
    }



def build_game(row: dict) -> dict | None:
    """One row is one game: N mirror seats, seat-0 result.

    None when the row cannot be a game. Behavior facts default to None
    per seat; the board renders a dash for unknown."""
    seats = row.get("seats")
    raw = row.get("scores")
    if (
        not isinstance(seats, list)
        or not isinstance(raw, list)
        or len(seats) != len(raw)
        or not seats
    ):
        return None
    try:
        scores = [float(s) for s in raw]
    except (TypeError, ValueError):
        return None
    ranks = rank_of(scores)  # engine tie rule: shared top shares rank 0
    ntop = sum(1 for r in ranks if r == 0)

    def _result(rank):
        if rank == 0 and ntop == 1:
            return "win"
        return "draw" if rank == 0 else "loss"

    length = row.get("length")
    miss = row.get("trace_miss")

    def _count(key):
        v = row.get(key)
        return v if isinstance(v, int) and v >= 0 else None

    return {
        "tick": row.get("tick"),
        "learner": "main",
        "map": row.get("map"),
        "seats": list(seats),
        "scores": list(raw),
        "stats": [_seat_stats(row, i) for i in range(len(seats))],
        "length": length if isinstance(length, (int, float)) else None,
        "trace_miss": miss if isinstance(miss, (int, float)) else None,
        "timeouts": _count("timeouts"),
        "breaks": _count("breaks"),
        "result": _result(ranks[0]),
        "replay": row.get("replay"),
    }



def group_games(rows: list[dict]) -> list[dict]:
    """Rows -> per-game dicts, newest first. One play logs one row, so
    one row is one game; rows with bad facts drop (list_games already
    skips malformed lines, this skips bad scores)."""
    games = []
    for r in rows:
        g = build_game(r)
        if g is not None:
            games.append(g)
    return games



def _snapshot_key(base: Path) -> tuple:
    """Memo key covering every file snapshot() reads: mtime+size per
    file, so any writer invalidates."""
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
    last build instead of rebuilding the panel from games.jsonl."""
    return _memo(_snapshot_cache, _snapshot_key(base), lambda: _build_snapshot(base))



ALERT_IDLE_S = 15 * 60



def rate_window(base: Path) -> tuple[int | None, float | None]:
    """(games in the last hour, seconds since the last game).

    From the wall-clock stamps the scheduler logs per game; the game
    index mtime is the recency fallback when rows predate stamps.
    None when nothing is logged yet."""
    stamps = sorted(
        r["t"] for r in cached_games(base) if isinstance(r.get("t"), (int, float))
    )
    if stamps:
        now = time.time()
        return (sum(1 for t in stamps if t > now - 3600), max(0.0, now - stamps[-1]))
    try:
        return (None, max(0.0, time.time() - (base / "games.jsonl").stat().st_mtime))
    except OSError:
        return (None, None)



def h0_panel(
    base: Path, state: dict | None, games: list[dict], updates: list[dict]
) -> dict:
    """Sticky strip facts: tick · games · updates · micro · last game ·
    decisive rate over the last 40."""
    state = state or {}
    games_per_h, secs = rate_window(base)
    last = games[0] if games else None
    last_result = (last or {}).get("result")
    last_length = (last or {}).get("length")
    recent = games[:40]
    dec = [g for g in recent if g.get("result") != "draw"]
    return {
        "tick": state.get("tick", 0),
        "games": len(games),
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
    """Main's means: food/kills/army share/length over logged behavior
    rows. Null when unplayed or unstamped."""
    acc = {"main": {"food": [], "kills": [], "army": [], "length": [], "n": 0}}
    for r in reversed(cached_games(base)):
        seats = r.get("seats") or []
        food, kills, army = r.get("food"), r.get("kills"), r.get("army")
        if not (
            isinstance(food, list)
            and isinstance(kills, list)
            and isinstance(army, list)
        ):
            continue
        if not seats or not (
            len(food) == len(kills) == len(army) == len(seats)
        ):
            continue
        try:
            f = [float(x) for x in food]
            k = [float(x) for x in kills]
            a = [float(x) for x in army]
        except (TypeError, ValueError):
            continue
        total = sum(a)
        length = r.get("length")
        length = length if isinstance(length, (int, float)) else None
        sides = tuple((seats[i], f[i], k[i], a[i]) for i in range(len(seats)))
        for cid, fi, ki, ai in sides:
            cell = acc.get(cid)
            if cell is None:
                continue
            cell["food"].append(fi)
            cell["kills"].append(ki)
            if total > 0:
                cell["army"].append(100 * ai / total)
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
                "update_seconds": u.get("update_seconds"),
                "pg_loss": u.get("pg_loss"),
                "v_loss": u.get("v_loss"),
            }
        )
    return rows



def trace_miss_mean(games: list[dict], window: int = 40) -> float | None:
    """Mean trace-miss over the most recent window of games that log it.

    None when no game carries the fact yet (pre-alarm rows). The 5%
    alert threshold sits far above healthy order-lost noise (~1%) and
    far below a real mask breach (~21%): it fires on bugs, not infra."""
    vals = [
        g.get("trace_miss")
        for g in (games or [])[:window]
        if isinstance(g.get("trace_miss"), (int, float))
    ]
    if not vals:
        return None
    return sum(vals) / len(vals)



PENDING_ALERT_GB = 1.0



def pending_gb(base: Path) -> float:
    """Untrained bank on disk: shard files plus the legacy bank."""
    base = Path(base)
    total = 0
    for name in ("pending.pt",):
        try:
            total += (base / "live" / name).stat().st_size
        except OSError:
            pass
    try:
        for shard in (base / "live" / "pending").glob("tick*.pt"):
            total += shard.stat().st_size
    except OSError:
        pass
    return total / 1e9



def limit_hits(games: list[dict], window: int = 40) -> tuple[int, int]:
    """(timeout seats, BREAK turns) over the most recent window.

    Rows that predate either fact are unknown, not zero: only numeric
    entries count. Both signals are bounded at zero in a healthy run
    (cutoffs need box-scale load, breaks need 1000+ ant-turns), so any
    occurrence in the window pages."""
    recent = games or []
    def _sum(key):
        return sum(
            g.get(key) for g in recent[:window]
            if isinstance(g.get(key), int)
        )
    return (_sum("timeouts"), _sum("breaks"))



def alerts_panel(
    h0: dict,
    trace_miss: float | None = None,
    pending_gb: float | None = None,
    limit: tuple[int, int] | None = None,
) -> list[dict]:
    """Attention queue: stuck training, trace-miss breach, backlog;
    else all-clear."""
    tick = h0.get("tick", 0)
    secs = h0.get("secs_since_game")
    rows = []
    if isinstance(secs, (int, float)) and secs > ALERT_IDLE_S:
        rows.append(
            {"level": "alert", "msg": f"no game for {_fmt_idle(secs)}", "tick": tick}
        )
    if isinstance(trace_miss, (int, float)) and trace_miss > 0.05:
        rows.append(
            {
                "level": "alert",
                "msg": f"trace miss {trace_miss:.0%} over recent games — decisions the replay cannot explain",
                "tick": tick,
            }
        )
    if limit is not None:
        nto, nbr = limit
        if isinstance(nto, int) and nto > 0:
            rows.append(
                {
                    "level": "alert",
                    "msg": f"{nto} engine timeouts over recent games — whole turns cut off; watch box load",
                    "tick": tick,
                }
            )
        if isinstance(nbr, int) and nbr > 0:
            rows.append(
                {
                    "level": "alert",
                    "msg": f"{nbr} BREAK turns over recent games — the decide guard fired; the bot is starved for time",
                    "tick": tick,
                }
            )
    if isinstance(pending_gb, (int, float)) and pending_gb > PENDING_ALERT_GB:
        rows.append(
            {
                "level": "alert",
                "msg": f"pending backlog {pending_gb:.1f}GB — learner behind the games; watch RAM",
                "tick": tick,
            }
        )
    if not rows:
        rows.append({"level": "ok", "msg": "all clear", "tick": tick})
    return rows



def _build_snapshot(base: Path) -> dict:
    archive.init(base)
    state = archive.load_state(base)
    panel = cached_panel(base)
    updates = archive.list_updates(base)
    h0 = h0_panel(base, state, panel, updates)
    miss = trace_miss_mean(panel)
    return {
        "h0": h0,
        "training": training_panel(updates),
        "behavior": behavior_panel(base),
        "games": panel[:100],
        "game_total": len(panel),
        "trace_miss": miss,
        "pending_gb": (pgb := pending_gb(base)),
        "alerts": alerts_panel(h0, miss, pgb, limit_hits(panel)),
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

