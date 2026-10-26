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
# WARNING: the committed map was hand-finished after generation
# (dry-route review) — re-running this file REWRITES rung2c with a
# different-but-valid variant. Do not regenerate blindly; the pool
# trains on the committed file.
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

BIG_HDR = ["# Rung 2 staged: big boards, scaled patterns."]


def _mirror(cells, rows, cols):
    """Add 180-degree counterparts: features come in swapped pairs."""
    out = set(cells)
    for r, c in cells:
        out.add((rows - 1 - r, cols - 1 - c))
    return out


def _rect(r0, r1, c0, c1):
    return [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]


def emit_multi(name, rows, cols, zeros, ones, waters, header):
    """Multi-hill emit: same contract as emit(), generalized.

    zeros/ones are the full per-side hill lists (swapped pairs).
    Waters pass mirrored (180-swap closed by construction, asserted
    cell-by-cell like emit). Cross-hill sight rule + BFS
    land-connectivity over every hill, then playable + print."""
    assert not (set(zeros) & set(ones)), name
    grid = [["."] * cols for _ in range(rows)]
    for r, c in waters:
        grid[r][c] = "%"
    for r, c in zeros:
        assert grid[r][c] == ".", (name, r, c)
        grid[r][c] = "0"
    for r, c in ones:
        assert grid[r][c] == ".", (name, r, c)
        grid[r][c] = "1"
    for r in range(rows):
        for c in range(cols):
            a = grid[r][c]
            b = grid[rows - 1 - r][cols - 1 - c]
            want = {"0": "1", "1": "0"}.get(a, a)
            assert want == b, (name, r, c, a, b)
    assert min(dist2(a, b, rows, cols) for a in zeros for b in ones) > 77, name
    seen = {zeros[0]}
    stack = [zeros[0]]
    while stack:
        r, c = stack.pop()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = ((r + dr) % rows, (c + dc) % cols)
            if nb not in seen and grid[nb[0]][nb[1]] != "%":
                seen.add(nb)
                stack.append(nb)
    assert all(h in seen for h in zeros + ones), name
    lines = [f"rows {rows}", f"cols {cols}", "players 2"]
    lines += ["m " + "".join(row) for row in grid]
    (OUT / name).write_text("\n".join(header + lines) + "\n")
    assert mapgen.is_playable_2p(str(OUT / name)), name
    print("ok:", name)


# k: double-scale pond (48x48, 2 hills/side). Twin center lakes +
# wrap-joined edge pair, hills between; routes run around the ends.
_k_wet = (_rect(14, 33, 22, 23) + _rect(14, 33, 0, 0)
          + _rect(14, 33, 47, 47))
emit_multi("rung2k_mapgen4.map", 48, 48, [(23, 12)], [(24, 35)],
     _mirror(_k_wet, 48, 48),
     BIG_HDR + ["# 48x48 (2x rung2f scale), 2 hills/side. STAGED:",
                "# joins the pool only by the promotion/demotion rules."],)

# l: double-scale lakes texture (48x48, 3 hills/side). Off-corridor
# by design (like d): scouting/texture at scale, not a funnel.
_l_wet = _rect(4, 9, 20, 25) + _rect(4, 9, 30, 35)
emit_multi("rung2l_mapgen5.map", 48, 48,
     [(12, 10), (24, 10), (36, 10)],
     [(35, 37), (23, 37), (11, 37)],
     _mirror(_l_wet, 48, 48),
     BIG_HDR + ["# 48x48 (2x rung2f scale), 3 hills/side. STAGED:",
                "# joins the pool only by the promotion/demotion rules."],)

# m: triple-scale gap (72x72, 2 hills/side). Twin full-span bars
# with a shared dry latitude + edge twins; battles on the band.
_m_wet = (_rect(0, 34, 34, 35) + _rect(37, 71, 34, 35)
          + _rect(0, 34, 0, 0) + _rect(37, 71, 0, 0)
          + _rect(0, 34, 71, 71) + _rect(37, 71, 71, 71))
emit_multi("rung2m_mapgen6.map", 72, 72, [(35, 16)], [(36, 55)],
     _mirror(_m_wet, 72, 72),
     BIG_HDR + ["# 72x72 (3x rung2f scale), 2 hills/side. STAGED:",
                "# joins the pool only by the promotion/demotion rules."],)

# n: triple-scale open texture (72x72, 3 hills/side). Scattered
# lakes, racing/scouting ground at scale.
_n_wet = (_rect(8, 15, 30, 37) + _rect(32, 39, 30, 37)
          + _rect(8, 15, 45, 52))
emit_multi("rung2n_mapgen7.map", 72, 72,
     [(18, 16), (36, 16), (54, 16)],
     [(53, 55), (35, 55), (17, 55)],
     _mirror(_n_wet, 72, 72),
     BIG_HDR + ["# 72x72 (3x rung2f scale), 3 hills/side. STAGED:",
                "# joins the pool only by the promotion/demotion rules."],)
