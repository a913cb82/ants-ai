"""Map pool validation + one delegated generator.

Validation (`_read_grid` / `is_playable` / `is_playable_2p` /
`parse_text` / `default_pool`) is ours: comment-tolerant headers,
digit and A/B hills, hill-only maps, any seat count. Generation
delegates to tools/mapgen via gen_mixed (in-process import, no
subprocess, no sys.path pollution): `generate()` is one 2p symmetric
map, deterministic in seed, validated before return.
"""

from __future__ import annotations

import random

_GEN_MIXED = None


def _gen_mixed():
    """Load tools/mapgen/gen_mixed.py by path (imported once, cached).

    importlib file-location load: the host's sys.path is untouched, so
    the generic top-level names under tools/mapgen (map, mapgen,
    cavemap) never shadow anything. gen_mixed handles its own
    submodule keys the same way (_load_genmods snapshots sys.modules).
    """
    global _GEN_MIXED
    if _GEN_MIXED is None:
        import importlib.util
        from pathlib import Path

        path = (
            Path(__file__).resolve().parents[1]
            / "tools"
            / "mapgen"
            / "gen_mixed.py"
        )
        spec = importlib.util.spec_from_file_location("gen_mixed", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _GEN_MIXED = mod
    return _GEN_MIXED


def generate(seed: int) -> list[str]:
    """One 2p symmetric map as file-text lines (no trailing newline).

    Deterministic in seed: same seed, same map. Built in-process by
    the tools symmetric generator (digit hills, walk-carved,
    connectivity enforced by the generator's own validity loop, hills
    re-checked here). Global RNG is saved/restored around the build,
    so training/test streams never shift.
    """
    gm = _gen_mixed()
    rng = random.Random(seed)
    with gm.seeded(rng.randrange(1 << 30)):
        text, _argv, _cwd = gm.generate_one("symmetric", 2, rng)
    lines = text.splitlines()
    if not is_playable_2p_lines(lines):
        raise RuntimeError(f"tools output failed validation (seed {seed})")
    return lines


def parse_text(text: str) -> tuple[int, int, int, list[str]]:
    """(rows, cols, players, grid) from map text.

    Skips blank lines and `#` comments (upstream maps carry comment
    headers above the rows/cols/players lines); `m `-prefixed lines
    are grid rows. Headers default to 0 when absent — callers validate.
    """
    rows = cols = players = 0
    grid: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("rows "):
            rows = int(line.split()[1])
        elif line.startswith("cols "):
            cols = int(line.split()[1])
        elif line.startswith("players "):
            players = int(line.split()[1])
        elif line.startswith("m "):
            grid.append(line[2:])
    return rows, cols, players, grid


def _read_grid(path: str):
    """(rows, cols, players, grid) or None when unparseable."""
    rows, cols, players, grid = parse_text(open(path).read())
    if len(grid) != rows or rows == 0:
        return None
    if any(len(r) != cols for r in grid):
        return None
    flat = "".join(grid)
    if set(flat) - set(
        ".%*abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    ):
        return None
    return rows, cols, players, flat


def _seat_has_hill(flat: str, seat: int) -> bool:
    if str(seat) in flat:
        return True
    # legacy 2p aliases: ant+hills (A/B).
    return (seat == 0 and "A" in flat) or (seat == 1 and "B" in flat)


def is_playable(path: str) -> bool:
    """A real N-player grid: parseable header, full grid, a hill
    per seat.

    Comment lines (#) precede headers in most upstream maps, hills are
digits (0/1/...) or ant+hills (A/B), and hill-only maps are fine — hills
    spawn ants on turn 1, which is why maze_02p_02 plays with no 'a'/'b'.
    """
    parsed = _read_grid(path)
    if parsed is None:
        return False
    _rows, _cols, players, flat = parsed
    if players < 2:
        return False
    return all(_seat_has_hill(flat, s) for s in range(players))


def is_playable_lines(lines: list[str], players: int) -> bool:
    """is_playable over in-memory lines (no file): header parses, full
    grid, a hill per seat."""
    rows, cols, players_got, grid = parse_text("\n".join(lines))
    if players_got != players or len(grid) != rows or rows == 0:
        return False
    if any(len(r) != cols for r in grid):
        return False
    flat = "".join(grid)
    if set(flat) - set(
        ".%*abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    ):
        return False
    return all(_seat_has_hill(flat, s) for s in range(players))


def is_playable_2p(path: str) -> bool:
    """A real 2-player grid: parseable header, full grid, a hill each.

    Comment lines (#) precede headers in most upstream maps, hills are
    digits (0/1) or ant+hills (A/B), and hill-only maps are fine — hills
    spawn ants on turn 1, which is why maze_02p_02 plays with no 'a'/'b'.
    Kept for the mapgen scripts' 2p checks; the training pool uses
    is_playable (any seat count).
    """
    parsed = _read_grid(path)
    if parsed is None:
        return False
    _rows, _cols, players, flat = parsed
    return players == 2 and _seat_has_hill(flat, 0) and _seat_has_hill(flat, 1)


def is_playable_2p_lines(lines: list[str]) -> bool:
    """is_playable_2p over in-memory lines (no file)."""
    rows, cols, players, grid = parse_text("\n".join(lines))
    if players != 2 or len(grid) != rows or rows == 0:
        return False
    if any(len(r) != cols for r in grid):
        return False
    flat = "".join(grid)
    return _seat_has_hill(flat, 0) and _seat_has_hill(flat, 1)


def write(path: str, seed: int) -> None:
    with open(path, "w") as f:
        f.write("\n".join(generate(seed)) + "\n")


def default_pool() -> list[str]:
    """Every map in the four upstream dirs, sorted (any seat count)."""
    import glob as _glob

    pool = []
    for d in ("cell_maze", "maze", "multi_hill_maze", "random_walk"):
        pool.extend(_glob.glob(f"tools/maps/{d}/*.map"))
    assert all(is_playable(f) for f in pool), "unplayable map in pool"
    return sorted(pool)


if __name__ == "__main__":
    import sys

    write(sys.argv[1], int(sys.argv[2]))
