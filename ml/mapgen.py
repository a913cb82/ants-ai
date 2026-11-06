"""Symmetric map generator + pool validation.

Standalone in-process generator (imports nothing but stdlib): noise on
one half, 180-degree rotational mirror, symmetric hill pair,
flood-fill connectivity check. Deterministic per seed, microseconds
per map — see FORK note below for why it does not import
tools/mapgen (subprocess/CLI scripts with their own import
conventions; usable in-process, but heavier and stdout-based).

The training pool is any map in the four upstream dirs (cell_maze,
maze, multi_hill_maze, random_walk): every tick plays one map, so map
size is the player-count curriculum. generate()/write() are currently
test/utility-only (tests/test_pool.py pins determinism); the pool
does not include generated maps since tools/maps/generated/ was
removed (2a4031d).
"""

from __future__ import annotations

import random

SIZES = [(40, 40), (50, 50), (60, 54), (72, 72), (60, 96)]


def generate(seed: int) -> list[str]:
    """Full map file text (without trailing newline) for seed."""
    rnd = random.Random(seed)
    rows, cols = SIZES[seed % len(SIZES)]
    for attempt in range(100):
        grid = _try_grid(rnd, rows, cols)
        if grid is not None:
            break
    else:
        raise RuntimeError(f"no connected map in 100 attempts (seed {seed})")
    lines = [f"rows {rows}", f"cols {cols}", "players 2", ""]
    lines += ["m " + "".join(row) for row in grid]
    return lines


def _try_grid(rnd: random.Random, rows: int, cols: int) -> list[list[str]] | None:
    water_frac = rnd.uniform(0.12, 0.25)
    # Noise on one half; 180-degree rotation mirrors it (symmetric by
    # construction, so hills/food placed as rotated pairs stay fair).
    land = [[True] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            r2, c2 = rows - 1 - r, cols - 1 - c
            if (r, c) > (r2, c2):
                continue
            water = rnd.random() < water_frac
            land[r][c] = land[r2][c2] = not water
    # Hills: symmetric pair, margined from edges and each other.
    hills = _hill_pair(rnd, rows, cols, land)
    if hills is None:
        return None
    (ar, ac), (br, bc) = hills
    if not _connected(land, (ar, ac)):
        return None
    grid = [["." if cell else "%" for cell in row] for row in land]
    grid[ar][ac] = "A"
    grid[br][bc] = "B"
    _sprinkle(rnd, grid, land, rows, cols, hills, fraction=0.03)
    return grid


def _hill_pair(
    rnd: random.Random, rows: int, cols: int, land: list[list[bool]]
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    margin = 4
    for _ in range(200):
        ar = rnd.randrange(margin, rows - margin)
        ac = rnd.randrange(margin, cols - margin)
        br, bc = rows - 1 - ar, cols - 1 - ac
        if (ar, ac) == (br, bc):
            continue
        if not land[ar][ac]:
            continue
        dist = abs(ar - br) + abs(ac - bc)
        if dist >= (rows + cols) // 2:
            return (ar, ac), (br, bc)
    return None


def _connected(land: list[list[bool]], start: tuple[int, int]) -> bool:
    """Every land cell reachable from start (4-neighbourhood)."""
    rows, cols = len(land), len(land[0])
    seen = {start}
    stack = [start]
    while stack:
        r, c = stack.pop()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (r + dr, c + dc)
            if (
                0 <= nxt[0] < rows
                and 0 <= nxt[1] < cols
                and land[nxt[0]][nxt[1]]
                and nxt not in seen
            ):
                seen.add(nxt)
                stack.append(nxt)
    return sum(sum(row) for row in land) == len(seen)


def _sprinkle(
    rnd: random.Random,
    grid: list[list[str]],
    land: list[list[bool]],
    rows: int,
    cols: int,
    hills: tuple[tuple[int, int], tuple[int, int]],
    fraction: float,
) -> None:
    cells = [
        (r, c)
        for r in range(rows)
        for c in range(cols)
        if land[r][c] and (r, c) not in hills
    ]
    for r, c in cells:
        r2, c2 = rows - 1 - r, cols - 1 - c
        if (r, c) > (r2, c2):
            continue
        if rnd.random() < fraction:
            grid[r][c] = grid[r2][c2] = "*"


def write(path: str, seed: int) -> None:
    with open(path, "w") as f:
        f.write("\n".join(generate(seed)) + "\n")


def _read_grid(path: str):
    """(rows, cols, players, grid) or None when unparseable."""
    rows = cols = players = 0
    grid: list[str] = []
    with open(path) as f:
        for line in f:
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
