"""Mirror bank: tick persistence, pending rows, dispatch budgets.

Where ticks live on disk (live weights + Adam, per-tick pending shards,
claimed tick numbers) and when a new tick may dispatch (seat budget,
backlog cap). No games, no training math — imported by train/selfplay.py.
"""

from __future__ import annotations

import contextlib
import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))

import algorithm
import archive
MICRO_BATCH = 16
# Memory budgets: the bot fan-out is concurrency x seats x ~240MB (a
# full torch per seat), so seats in flight are capped (~16 = ~3.8GB
# worst case instead of 4 x 10 x 240MB ~= 9.5GB). The background
# update trains the oldest whole games up to the row cap (~0.6GB of
# window tensors per full stack); the remainder stays banked for later
# boundaries, oldest first, so nothing is ever shed.
SEAT_BUDGET = 16
BATCH_CAP_ROWS = 65536
# Resting backlog cap: 250k rows (~2.3GB, ~60 max-size games).
# Steady state sits at 10-40k rows, so this is a firebreak, not a
# regulator: it binds only on restart-inherited backlogs or a
# stalled learner (the 1GB board alert fires first). The dispatcher
# stalls past it (timing, never shedding) and the stall force-starts
# a drain update when the learner is idle. Sized for the 15GB WSL
# guest; scale to 400k+ when the guest sees the full 32GB.
PENDING_CAP_ROWS = 250000

#: Serializes tick claims: load/compute/save must not interleave,
#: or two threads play the same tick number.
_CLAIM_LOCK = threading.Lock()



def _live_paths(base: Path) -> tuple[Path, Path]:
    d = base / "live"
    return d / "weights.json", d / "opt.json"



def _pending_path(base: Path) -> Path:
    """Bank directory: one file per tick, never a whole-list rewrite.

    Re-saving the full pending list every tick is O(n^2) serialization:
    at full-size 250-turn games the bank reaches hundreds of MB and each
    tick spends minutes pickling it (plus a same-size transient that
    OOM-killed a 14-game run). Shards cost O(game) each, once."""
    return base / "live" / "pending"



def _legacy_pending_path(base: Path) -> Path:
    return base / "live" / "pending.pt"



def _shard_tick(path: Path) -> int:
    return int(path.stem.replace("tick", "", 1))



def _pending_shards(base: Path) -> list:
    try:
        shards = list(_pending_path(base).glob("tick*.pt"))
    except OSError:
        return []
    return sorted(shards, key=_shard_tick)



def bank_pending(base: Path, items: list, arch: str, tick: int) -> None:
    """Bank one tick's PPO rows (empty clears that tick's shard)."""
    path = _pending_path(base) / f"tick{tick}.pt"
    if not items:
        try:
            path.unlink()
        except OSError:
            pass
        return
    algorithm.dump_pending(path, items, arch, tick)



def _drop_banked(base: Path, entries: list) -> None:
    """Delete the bank files a landed update consumed: legacy file for
    a None entry, that tick's shard otherwise. Removes the directory
    when nothing remains."""
    for entry in entries:
        with contextlib.suppress(OSError):
            if entry is None:
                _legacy_pending_path(base).unlink()
            else:
                (_pending_path(base) / f"tick{entry}.pt").unlink()
    with contextlib.suppress(OSError):
        _pending_path(base).rmdir()



def _take_batch(counts: list[int], cap_rows: int) -> tuple[int, int]:
    """Leading whole games up to cap_rows: (games_taken, rows_taken).

    At least one game always trains, so a lone monster game still
    updates instead of stalling the boundary forever."""
    taken = rows = 0
    for n in counts:
        if taken and rows + n > cap_rows:
            break
        taken += 1
        rows += n
    return (taken, rows)



def load_banked(base: Path, arch: str) -> tuple[list, list]:
    """(rows, banked): banked is (tick|None, nrows), oldest first.

    Shard order is tick-number, not completion, order; PPO shuffles
    minibatches anyway, so training cannot tell."""
    banked = []
    rows = algorithm.read_pending(_legacy_pending_path(base), arch)
    if rows:
        banked.append((None, len(rows)))
    for shard in _pending_shards(base):
        part = algorithm.read_pending(shard, arch)
        rows.extend(part)
        if part:
            banked.append((_shard_tick(shard), len(part)))
    return rows, banked



def load_pending(base: Path, arch: str) -> list:
    """Banked rows: legacy file first, then shards in tick order."""
    return load_banked(base, arch)[0]



def store_live(base: Path, weights: dict, opt_blob: dict | None) -> None:
    """Persist live training weights + Adam (atomic, old-or-new)."""
    wpath, opath = _live_paths(base)
    wpath.parent.mkdir(parents=True, exist_ok=True)
    archive.atomic_write_json(wpath, weights)
    if opt_blob is None:
        try:
            opath.unlink()
        except OSError:
            pass
    else:
        archive.atomic_write_json(opath, opt_blob)



def load_live(base: Path) -> tuple[dict, dict | None]:
    """Live training weights + Adam (None when never banked)."""
    wpath, opath = _live_paths(base)
    weights = json.loads(wpath.read_text())
    try:
        blob = json.loads(opath.read_text())
    except (OSError, ValueError):
        return weights, None
    return weights, blob



def _claim_tick(base: Path) -> int:
    """Next tick number, persisted at claim: never reused, even by
    restarts. A crashed tick's number is never handed out again, so
    its rows can simply stay logged — no stripping is ever needed."""
    with _CLAIM_LOCK:
        state = archive.load_state(base) or {}
        tick = max(state.get("tick", 0), state.get("next_tick", 0))
        state["next_tick"] = tick + 1
        archive.save_state(base, state)
    return tick



def _prospective_tick(base: Path) -> int:
    """Next tick without claiming it: dispatch may wait, never consume."""
    state = archive.load_state(base) or {}
    return max(state.get("tick", 0), state.get("next_tick", 0))



def _pending_stalled(cfg: dict, pending_rows: int) -> bool:
    """Resting backlog past the cap: hold dispatch until it drains."""
    return pending_rows >= cfg.get("pending_cap_rows", PENDING_CAP_ROWS)



def _bg_busy(live: dict) -> bool:
    """A background update is training (or landing) right now."""
    bg = live.get("bg")
    return bool(bg is not None and bg.get("busy"))



def _select_dispatch(
    base: Path, cfg: dict, in_flight_seats: int, pending_rows: int = 0
) -> tuple[int, str, int] | None:
    """(tick, map, seats) fitting seats and backlog, else None.

    Over either budget the tick waits UNCLAIMED, so the seed:tick map
    sequence never shifts, only its timing. The seat budget must cover
    the largest map (10 seats); in-flight games always drain and the
    backlog always trains down, so a held tick always dispatches."""
    from game_if import map_player_count

    if _pending_stalled(cfg, pending_rows):
        return None
    budget = cfg.get("seat_budget", SEAT_BUDGET)
    tick = _prospective_tick(base)
    rng = random.Random(f"{cfg.get('seed', 0)}:{tick}")
    map_path = rng.choice(cfg["maps"])
    seats = map_player_count(map_path)
    if in_flight_seats + seats > budget:
        return None
    return (tick, map_path, seats)

