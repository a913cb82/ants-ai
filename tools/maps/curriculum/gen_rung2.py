"""Generate rung-2 pool maps (symmetric small boards with water shapes).

Every map: 180-degree rotational symmetry with players swapped,
hills beyond sight range (d2 > 77, scouting required), water that
shapes movement without walling the board. Symmetry is asserted.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ml"))

import mapgen  # noqa: E402
from grid import dist2  # noqa: E402

OUT = Path(__file__).resolve().parent


def emit(name, rows, cols, hills, waters, header):
    grid = [["."] * cols for _ in range(rows)]
    for r, c in waters:
        grid[r][c] = "%"
    (r0, c0), (r1, c1) = hills
    grid[r0][c0] = "0"
    grid[r1][c1] = "1"
    # 180-degree symmetry with players swapped.
    for r in range(rows):
        for c in range(cols):
            a = grid[r][c]
            b = grid[rows - 1 - r][cols - 1 - c]
            want = {"0": "1", "1": "0"}.get(a, a)
            assert want == b, (name, r, c, a, b)
    assert dist2(hills[0], hills[1], rows, cols) > 77, name
    lines = [f"rows {rows}", f"cols {cols}", "players 2"]
    lines += ["m " + "".join(row) for row in grid]
    text = "\n".join(header + lines) + "\n"
    path = OUT / name
    path.write_text(text)
    assert mapgen.is_playable_2p(str(path)), name
    print("ok:", name)


HDR = ["# Rung 2 pool: small symmetric boards; hills beyond sight."]

# b: tall central lake (8x2, self-symmetric). It sits on the direct
# hill-to-hill line, so east-west movement must route around its
# northern or southern end.
emit("rung2b_pond.map", 16, 24, [(7, 4), (8, 19)],
     [(r, c) for r in range(4, 12) for c in (11, 12)], HDR)

# c: water bar with a central gap (chokepoint). Battles happen at the gap.
bar = [(r, c) for r in list(range(2, 7)) + list(range(9, 14))
       for c in (11, 12)]
emit("rung2c_gap.map", 16, 24, [(7, 4), (8, 19)], bar, HDR)

# d: twin lakes (4x4). Wide routing, pocketed ground.
lake_a = [(r, c) for r in range(3, 7) for c in range(4, 8)]
lake_b = [(r, c) for r in range(13, 17) for c in range(20, 24)]
emit("rung2d_lakes.map", 20, 28, [(9, 6), (10, 21)],
     lake_a + lake_b, HDR)
