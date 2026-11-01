"""Game store: logged games, live training state, behavior facts.

Everything learned lives here, outside git: one row per game in
games.jsonl, the live weights + Adam + banked batch under live/, and
two counters in state.json. Pure files; knows nothing about torch or
the engine.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parent / "archive"


def _paths(base: Path) -> dict[str, Path]:
    return {"dir": base}


def init(base: Path = DEFAULT_DIR) -> None:
    base.mkdir(parents=True, exist_ok=True)


def atomic_write_json(path: Path, obj: object) -> None:
    """Write JSON atomically: readers see old-or-new, never torn."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(obj))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def append_jsonl(path: Path, row: dict) -> None:
    """One JSON line appended (single-threaded: no lock needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(row) + "\n")


def read_jsonl(path: Path, valid) -> list[dict]:
    """Tolerant line reader: skips blanks, bad JSON, rejected rows."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if valid(row):
            out.append(row)
    return out


def load_state(base: Path) -> dict | None:
    """Training counters {tick, next_tick, micro}, else None."""
    p = base / "state.json"
    try:
        state = json.loads(p.read_text())
    except (OSError, ValueError):
        return None
    return state if isinstance(state, dict) else None


def save_state(base: Path, state: dict) -> None:
    init(base)
    atomic_write_json(base / "state.json", state)


def behavior_from_replay(replaydata, n: int = 2, length=None) -> dict | None:
    """Per-seat behavior stats from one game dict (parsed once per game).

    food[s]: food entries gathered by seat s (replaydata food owner).
    kills[s]: enemy ants dead before game end for seat s (ants die only
    by combat; killed = end - spawn == len(orders), the trajectories
    convention from rewards). army[s]: ants of seat s alive at game end.
    length: the played game length, passed in (game["length"]). Returns
    None when the replay carries no ant/food facts (unknown, not zero)."""
    if not isinstance(replaydata, dict):
        return None
    ants = replaydata.get("ants") or []
    foods = replaydata.get("food") or []
    if not ants and not foods:
        return None
    top = n
    for entry in list(ants) + list(foods):
        if (
            isinstance(entry, (list, tuple))
            and len(entry) >= 5
            and isinstance(entry[4], int)
        ):
            top = max(top, entry[4] + 1)
    food = [0] * top
    kills = [0] * top
    army = [0] * top
    for entry in foods:
        if (
            isinstance(entry, (list, tuple))
            and len(entry) >= 5
            and isinstance(entry[4], int)
            and 0 <= entry[4] < top
        ):
            food[entry[4]] += 1
    for entry in ants:
        if not (isinstance(entry, (list, tuple)) and len(entry) >= 6):
            continue
        _r, _c, spawn, end, owner, orders = entry[:6]
        if not (isinstance(owner, int) and 0 <= owner < top):
            continue
        try:
            killed = (end - spawn) == len(orders)
        except TypeError:
            continue
        if killed:
            for s in range(top):
                if s != owner:
                    kills[s] += 1
        else:
            army[owner] += 1
    return {"food": food, "kills": kills, "army": army, "length": length}


def log_game(
    base: Path,
    seats: list,
    scores: list,
    replay: str,
    map: str | None = None,
    game: str | None = None,
    tick: int | None = None,
    food=None,
    kills=None,
    army=None,
    length=None,
    t=None,
) -> None:
    """Append one game to the dashboard index (replay path archive-relative).

    One row is logged per mirror game: every seat is "main", always.
    tick/food/kills/army/length are per-game behavior facts aligned to
    the seats; t is the wall-clock stamp. All default to None
    and are omitted then, so the board renders a dash for unknown. The
    game id is informational (one row is one game)."""
    init(base)
    row = {
        "seats": list(seats),
        "scores": list(scores),
        "replay": replay,
        "map": map,
        "game": game,
    }
    if tick is not None:
        row["tick"] = tick
    if food is not None:
        row["food"] = list(food)
    if kills is not None:
        row["kills"] = list(kills)
    if army is not None:
        row["army"] = list(army)
    if length is not None:
        row["length"] = length
    if t is not None:
        row["t"] = t
    append_jsonl(base / "games.jsonl", row)


def log_update(base: Path, row: dict) -> None:
    """Append one PPO update's measurements (one row per update)."""
    init(base)
    append_jsonl(base / "updates.jsonl", row)


def _update_row(row: object) -> bool:
    return isinstance(row, dict) and isinstance(row.get("tick"), (int, float))


def list_updates(base: Path) -> list[dict]:
    """Oldest first. Skips malformed lines: never bricks the page."""
    return read_jsonl(base / "updates.jsonl", _update_row)


def _game_row(row: object) -> bool:
    # Mirror rows carry seats/scores lists (any player count).
    # Both validate: the required game facts never changed.
    if not (isinstance(row, dict) and {"seats", "scores", "replay"} <= set(row)):
        return False
    seats, scores = row["seats"], row["scores"]
    return (
        isinstance(seats, list)
        and isinstance(scores, list)
        and len(seats) == len(scores)
        and len(seats) >= 2
        and all(isinstance(s, (int, float)) for s in scores)
    )


def list_games(base: Path) -> list[dict]:
    """Newest first. Skips malformed lines/rows: one bad line must not
    brick the page."""
    rows = read_jsonl(base / "games.jsonl", _game_row)
    rows.reverse()
    return rows
