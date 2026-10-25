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

# b: twin lakes east and west (8x2 each, edge pair joined by the wrap).
# Hills sit between the lakes: both toroidal paths hill-to-hill are
# wet, so movement must route around the northern or southern ends.
# The col-23/col-0 pair is one lake split across the wrap edge.
emit("rung2b_pond.map", 16, 24, [(7, 4), (8, 19)],
     [(r, c) for r in range(4, 12) for c in (11, 12)]
     + [(r, c) for r in range(4, 12) for c in (0, 23)], HDR)

# c: twin full-span bars with a shared dry latitude (rows 7-8).
# Columns wrap, so one bar only blocks eastward: the westward route
# slips around via cols 0-4/19-23 untouched. The edge twin (cols
# 0+23, adjacent toroidally) closes it. Both bars run the full
# height except rows 7-8, so every hill-to-hill route crosses water
# somewhere — the only dry crossings are at the gap latitude, and
# battles happen on that band. Hills sit on the dry latitude.
bar = [(r, c) for r in list(range(0, 7)) + list(range(9, 16))
       for c in (11, 12)]
bar += [(r, c) for r in list(range(0, 7)) + list(range(9, 16))
        for c in (0, 23)]
emit("rung2c_gap.map", 16, 24, [(7, 4), (8, 19)], bar, HDR)

# d: twin 4x4 lakes (texture/scouting variety). Off the corridor by
# design: not every board must funnel movement.
# (Corridor-blocking already taught by pond; no duplicates.)
lake_a = [(r, c) for r in range(3, 7) for c in range(4, 8)]
lake_b = [(r, c) for r in range(13, 17) for c in range(20, 24)]
emit("rung2d_lakes.map", 20, 28, [(9, 6), (10, 21)],
     lake_a + lake_b, HDR)
