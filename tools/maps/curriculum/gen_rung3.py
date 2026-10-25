"""Generate rung-3 mid-size boards (1000-1700 tiles).

Same four water shapes as rung 2, scaled up: the ladder gap was
560 tiles (rung2d) -> 3000 (random_walk), with nothing between —
and the 3k boards proved too big to meet in 150 turns. Hills stay
beyond sight, symmetry is asserted, playability checked."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ml"))

import mapgen  # noqa: E402
from grid import dist2  # noqa: E402

OUT = Path(__file__).resolve().parent
HDR = ["# Rung 3: mid-size symmetric boards; hills beyond sight."]


def emit(name, rows, cols, hills, waters, header):
    grid = [["."] * cols for _ in range(rows)]
    for r, c in waters:
        grid[r][c] = "%"
    (r0, c0), (r1, c1) = hills
    grid[r0][c0] = "0"
    grid[r1][c1] = "1"
    for r in range(rows):
        for c in range(cols):
            a = grid[r][c]
            b = grid[rows - 1 - r][cols - 1 - c]
            want = {"0": "1", "1": "0"}.get(a, a)
            assert want == b, (name, r, c, a, b)
    assert dist2(hills[0], hills[1], rows, cols) > 77, name
    lines = [f"rows {rows}", f"cols {cols}", "players 2"]
    lines += ["m " + "".join(row) for row in grid]
    path = OUT / name
    path.write_text("\n".join(header + lines) + "\n")
    assert mapgen.is_playable_2p(str(path)), name
    print("ok:", name)


# a: open baseline, 24x40.
emit("rung3a_open.map", 24, 40, [(11, 8), (12, 31)], [], HDR)

# b: twin 5x5 lakes.
lake_a = [(r, c) for r in range(7, 12) for c in range(8, 13)]
lake_b = [(r, c) for r in range(12, 17) for c in range(27, 32)]
emit("rung3b_pond.map", 24, 40, [(11, 5), (12, 34)],
     lake_a + lake_b, HDR)

# c: water bar with a central gap (chokepoint), 28x44.
bar = [(r, c) for r in list(range(4, 12)) + list(range(16, 24))
       for c in (21, 22)]
emit("rung3c_gap.map", 28, 44, [(13, 9), (14, 34)], bar, HDR)

# d: twin 6x6 lakes, 32x52.
big_a = [(r, c) for r in range(8, 14) for c in range(10, 16)]
big_b = [(r, c) for r in range(18, 24) for c in range(36, 42)]
emit("rung3d_lakes.map", 32, 52, [(15, 8), (16, 43)],
     big_a + big_b, HDR)
