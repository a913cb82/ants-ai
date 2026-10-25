"""Symmetric 2-player map generator.

The repo's real grid-map pool is 3 maps (tutorial1, maze_02p_02,
random_walk_02p_02); the maze/cell_maze/random_walk dirs otherwise hold
generator PARAMS, not playable grids. This generates real playable grids
in the engine's `m`-row format: 180-degree rotational symmetry (fair for
slot-alternated mirror games), guaranteed land connectivity, margined
hills, symmetric food. Deterministic per seed.
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


if __name__ == "__main__":
    import sys

    write(sys.argv[1], int(sys.argv[2]))
