#!/usr/bin/env python
"""Random map sampler: one script, many settings, labelled sample.

Generates a labelled pool of 2-player maps at fixed dimensions (default
20x28, 1 hill per side). Each map picks a random capable generator family
with RANDOM but SENSIBLE per-family settings, validates the output with
``ml.mapgen.is_playable_2p`` (plus an exact dimension / hill-count check),
and retries with new settings (up to MAX_TRIES) before skipping the family
with a warning. Never emits an invalid map.

Usage:
    gen_sample.py --count N --outdir DIR --seed S [--rows 20 --cols 28 --hills 1]

Filename provenance: <generator>_<key settings>_s<seed>.map, e.g.
``random_land80_s7.map``.

MAP SOURCE SURVEY, round 2 (plumbing fixes authorized; engine untouched):
  - random_map.RandomMap ......... CAPABLE (unchanged). land 70-95%.
  - symmetric_mapgen.SymmetricMap . CAPABLE (unchanged). land 60-95%,
    walks 20-40, scaled min_start_distance, even dims only.
  - amstan cavemap ............... CAPABLE (unchanged). symmetry in
    {translational, horizontal, point, rotational}, smooth 2-5.
  - mapgen.py Grid ............... CAPABLE (FIXED: exact_rows/exact_cols
    kwargs threaded through tile_symmetric_grid -> pick_tile_dimensions;
    None defaults = legacy path, byte-identical CLI output seeds 1-3).
    Exact 20x28 pins block_size=1 + translations (10,14) (only pair
    passing the lcm gate); seed drives h_loc + carving. Key `tileb1`;
    odd dims skip (no even translation satisfies the gate).
  - cell_maze.CellMazeMap ........ CAPABLE (no edit needed). Exact 20x28
    via area=561 + aspect_ratio=1.4 + grid=(1,2) (tile (20,14) mirrored
    to (20,28)); players=2, hills=1, seed via options; min_hill_dist=8
    override (tool default 20 exceeds the max toroidal hill gap ~17).
    Settings: maze_type in {prims, backtrack, growing} (cell carve),
    openness 0.2-0.8 (braid fraction), cell_size 4-8, cell_width 1-3.
  - asymmetric_mapgen ............ CAPABLE walk path (FIXED:
    exact_rows/exact_cols kwargs on pick_dimensions; None = legacy).
    min_players=2 + scaled min_start_distance=8 via instance attrs;
    land band 60-90% (tool default), walks 50-90 (tool default 70).
    Scatter path (add_random_land) HANGS at 20x28 (spins once land is
    full) - walk only. Even dims required.
  - heightmap.HeightMapMap ...... STILL EXCLUDED. Places exactly ONE hill
    total and the 2-way tiling call is commented out; 2p needs hill
    mirroring + tile heuristics = deep, not plumbing.
  - McMaps.py .................... STILL EXCLUDED as a family. Pillow
    13.0.0 installed OK; `import Image` shim applied (try/except PIL)
    so the module imports. But no 2p/fixed-dim/hill entry exists:
    random_box hardcodes 4 players + random sizes, cells() places no
    hills, voronoi() writes PNGs only. Wiring = new generator.
  - Java ......................... STILL EXCLUDED. MapGenerator: player
    count is a lottery in map2String (rnd.nextInt(9) -> 2/4/8p), output
    uses ants a/b not hills, sizes flow through shared MIN/MAX plus
    halving logic. SymmetricMapgen: MIN_PLAYERS=4, dims 70-120, no
    CLI. 2p 20x28 = rewrite, not constants.
"""

import argparse
import contextlib
import io
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAPGEN_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "mapgen"))
AMSTAN_DIR = os.path.join(MAPGEN_DIR, "amstan")
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, AMSTAN_DIR)
sys.path.insert(0, MAPGEN_DIR)
sys.path.insert(0, REPO_ROOT)

from ml.mapgen import is_playable_2p  # noqa: E402

# tools/mapgen/map.py and tools/mapgen/amstan/map.py share the top-level
# module name `map` (likewise terrain/util vs stdlib-adjacent names), so
# the two families cannot coexist in sys.modules. Each generator imports
# its upstream modules fresh with only its own dir on the path.
_SHADOWED = (
    "map", "mapgen", "terrain", "util", "symmetricmap", "cavemap",
    "random_map", "symmetric_mapgen", "cell_maze", "asymmetric_mapgen",
    "McMaps",
)


def _purge_shadowed():
    for name in _SHADOWED:
        sys.modules.pop(name, None)


@contextlib.contextmanager
def _family_imports(first):
    _purge_shadowed()
    saved = sys.path[:]
    rest = [p for p in sys.path if p not in (AMSTAN_DIR, MAPGEN_DIR)]
    sys.path[:] = [first] + rest
    try:
        yield
    finally:
        sys.path[:] = saved
        _purge_shadowed()


MAX_TRIES = 10
FAMILIES = ("random", "symwalk", "cavemap", "gridwalk", "asymwalk",
            "cellmaze")
CAVE_SYMMETRIES = ("translational", "horizontal", "point", "rotational")


class FamilySkipped(Exception):
    """Raised when a generator family cannot produce a valid map."""


def land_water_pct(text):
    land = water = 0
    for line in text.splitlines():
        if line.startswith("m "):
            for ch in line[2:].strip():
                if ch == "%":
                    water += 1
                else:
                    land += 1
    total = land + water
    return (100.0 * land / total, 100.0 * water / total) if total else (0.0, 0.0)


def symmetric_flag(text, rows, cols):
    """Best-effort symmetry label for a 2p map: y(<kind>) or n."""
    grid = [
        line[2:].strip()
        for line in text.splitlines()
        if line.startswith("m ")
    ]
    if len(grid) != rows or any(len(r) != cols for r in grid):
        return "n"

    def land(ch):
        return "." if ch in "01" else ch

    def same(a, b):
        return land(a) == land(b) and ((a in "01") == (b in "01"))

    def hills_swapped(a, b):
        swap = {"0": "1", "1": "0"}
        return swap.get(a, a) == b and swap.get(b, b) == a

    def check(mate):
        for r in range(rows):
            for c in range(cols):
                mr, mc = mate(r, c)
                a, b = grid[r][c], grid[mr][mc]
                if not (same(a, b) or hills_swapped(a, b)):
                    return False
        return True

    if check(lambda r, c: (rows - 1 - r, c)):
        return "y(hmirror)"
    if check(lambda r, c: (r, cols - 1 - c)):
        return "y(vmirror)"
    if check(lambda r, c: (rows - 1 - r, cols - 1 - c)):
        return "y(rot180)"
    if check(lambda r, c: ((r + rows // 2) % rows, (c + cols // 2) % cols)):
        return "y(trans)"
    if cols % 2 == 0 and check(lambda r, c: (r, (c + cols // 2) % cols)):
        return "y(trans)"
    if rows % 2 == 0 and check(lambda r, c: ((r + rows // 2) % rows, c)):
        return "y(trans)"
    return "n"


def exact_shape_ok(text, rows, cols, hills):
    grid = [
        line[2:].strip()
        for line in text.splitlines()
        if line.startswith("m ")
    ]
    if len(grid) != rows or any(len(r) != cols for r in grid):
        return False
    flat = "".join(grid)
    ok_hills = flat.count("0") == hills and flat.count("1") == hills
    header_ok = (
        f"rows {rows}" in text
        and f"cols {cols}" in text
        and "players 2" in text
    )
    return ok_hills and header_ok


def gen_random(rng, rows, cols, hills, seed):
    """RandomMap: scatter water + random starts. Setting: land 70-95%."""
    with _family_imports(MAPGEN_DIR):
        from random_map import RandomMap

    land = rng.randint(70, 95)
    random.seed(seed)
    with contextlib.redirect_stderr(io.StringIO()):
        m = RandomMap(
            {"rows": rows, "cols": cols, "players": 2, "land": (land, land)}
        )
        m.generate()
        m.reports = []  # RandomMap skips Map.__init__; toText needs this
        buf = io.StringIO()
        m.toText(buf)
    return buf.getvalue(), f"land{land}"


def gen_symwalk(rng, rows, cols, hills, seed):
    """SymmetricMap random walk. Settings: target land 60-95%, walks 20-40."""
    with _family_imports(MAPGEN_DIR):
        from symmetric_mapgen import SymmetricMap

    if rows % 2 or cols % 2:
        raise FamilySkipped("symwalk needs even dims (tool loops forever)")
    target = rng.randint(60, 95)
    walks = rng.randint(20, 40)
    start_dist = int(0.5 * ((rows / 2) ** 2 + (cols / 2) ** 2) ** 0.5)
    random.seed(seed)
    with contextlib.redirect_stderr(io.StringIO()):
        for _ in range(300):
            s = SymmetricMap()
            s.min_players = s.max_players = 2
            s.per_player_dim = (rows // 2, cols // 2)
            s.dim_bounds = (rows, cols)
            s.min_start_distance = start_dist
            s.min_land_proportion = max(0.30, (target - 3) / 100.0)
            s.max_land_proportion = min(0.99, (target + 3) / 100.0)
            s.no_extra_walks = walks
            s.random_walk_map()
            if s.rows == rows and s.cols == cols:
                break
        else:
            raise FamilySkipped(f"no exact {rows}x{cols} in 300 dim draws")
    text = (
        f"rows {s.rows}\ncols {s.cols}\nplayers {s.no_players}\n"
        + "".join("m " + "".join(r) + "\n" for r in s.map_data)
    )
    return text, f"land{target}w{walks}"


def gen_cavemap(rng, rows, cols, hills, seed):
    """Amstan Cavemap. Settings: symmetry + smooth passes 2-5."""
    with _family_imports(AMSTAN_DIR):
        from cavemap import Cavemap
        from util import Point

    sym = rng.choice(CAVE_SYMMETRIES)
    smooth = rng.randint(2, 5)
    random.seed(seed)
    with contextlib.redirect_stderr(io.StringIO()):
        cavemap = Cavemap(
            size=Point(cols, rows), num_players=2, symmetry=sym
        )
        cavemap.add_hill(cavemap.size.random_upto())
        cavemap.generate(smooth=smooth)
        text = str(cavemap) + "\n"
    return text, f"{sym}sm{smooth}"


def gen_gridwalk(rng, rows, cols, hills, seed):
    """Grid tile walk. Settings fixed by exactness: tile + block 1."""
    from mapgen import Grid

    if rows % 2 or cols % 2:
        raise FamilySkipped("gridwalk needs even dims (lcm gate)")
    random.seed(seed)
    with contextlib.redirect_stderr(io.StringIO()):
        g = Grid()
        g.no_hills = hills
        g.symmetry = "tile"
        if not g.tile_symmetric_grid(2, rows, cols, 100, 1, 1,
                                     exact_rows=rows, exact_cols=cols):
            raise FamilySkipped(f"no valid tile grid at {rows}x{cols}")
        g.squares = [["%" for _ in range(g.cols)] for _ in range(g.rows)]
        g.add_starting_hills()
        g.generate_basis_information()
        g.add_land_with_recursive_backtracking()
        g.add_extra_land_blocks()
        g.add_extra_land_locs()
        g.make_symmetric()
        g.add_extra_hills()
        g.translate()
        text = (
            f"rows {g.rows}\ncols {g.cols}\nplayers {g.no_players}\n"
            + "".join("m " + "".join(r) + "\n" for r in g.squares)
        )
    return text, "tileb1"


def gen_asymwalk(rng, rows, cols, hills, seed):
    """Asymmetric walk. Settings: target land 60-90%, walks 50-90."""
    from asymmetric_mapgen import AsymmetricMap

    if rows % 2 or cols % 2:
        raise FamilySkipped("asymwalk needs even dims (translation gate)")
    target = rng.randint(60, 90)
    walks = rng.randint(50, 90)
    start_dist = int(0.5 * ((rows / 2) ** 2 + (cols / 2) ** 2) ** 0.5)
    random.seed(seed)
    with contextlib.redirect_stderr(io.StringIO()):
        m = AsymmetricMap()
        m.min_players = m.max_players = 2
        m.min_start_distance = start_dist
        m.min_land_proportion = max(0.30, (target - 3) / 100.0)
        m.max_land_proportion = min(0.99, (target + 3) / 100.0)
        m.no_extra_walks = walks
        m.pick_dimensions(exact_rows=rows, exact_cols=cols)
        m.map_data = [["%" for _ in range(m.cols)] for _ in range(m.rows)]
        m.add_ants()
        m.basis = m.get_basis()
        m.start_walks()
        m.add_land()  # walk path only; scatter hangs at this size
        text = (
            f"rows {m.rows}\ncols {m.cols}\nplayers {m.no_players}\n"
            + "".join("m " + "".join(r) + "\n" for r in m.map_data)
        )
    return text, f"land{target}w{walks}"


def gen_cellmaze(rng, rows, cols, hills, seed):
    """CellMaze. Pins area/aspect/grid for exact 20x28; varies carve."""
    from cell_maze import CellMazeMap

    if (rows, cols) != (20, 28):
        raise FamilySkipped("cellmaze pins are tuned for 20x28 only")
    maze = rng.choice(["prims", "backtrack", "growing"])
    openness = round(rng.uniform(0.2, 0.8), 2)
    cell_size = round(rng.uniform(4.0, 8.0), 1)
    cell_width = round(rng.uniform(1.0, 3.0), 1)
    with contextlib.redirect_stderr(io.StringIO()):
        m = CellMazeMap({"players": 2, "area": 561, "aspect_ratio": 1.4,
                         "grid": (1, 2), "hills": hills, "seed": seed,
                         "maze_type": maze, "openness": openness,
                         "cell_size": cell_size, "cell_width": cell_width})
        m.min_hill_dist = 8
        m.generate()
        buf = io.StringIO()
        m.toText(buf)
    key = f"{maze}o{int(openness * 100)}c{cell_size}w{cell_width}".replace(
        ".0", "")
    return buf.getvalue(), key


GENERATORS = {
    "random": gen_random,
    "symwalk": gen_symwalk,
    "cavemap": gen_cavemap,
    "gridwalk": gen_gridwalk,
    "asymwalk": gen_asymwalk,
    "cellmaze": gen_cellmaze,
}

FEELS = {
    "random": lambda lp: "open field" if lp > 90 else "scattered ponds",
    "symwalk": lambda lp: "winding corridors" if lp > 80 else "tight corridors",
    "cavemap": lambda lp: "smooth lakes" if lp > 85 else "cavernous pockets",
    "gridwalk": lambda lp: "carved grid" if lp > 80 else "dense grid",
    "asymwalk": lambda lp: "patchy walk" if lp > 80 else "tight walk",
    "cellmaze": lambda lp: "braided maze" if lp > 80 else "tight maze",
}


def make_one(family, rng, rows, cols, hills, seed):
    """Generate+validate one map; raise FamilySkipped after MAX_TRIES."""
    gen = GENERATORS[family]
    for _ in range(MAX_TRIES):
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                text, key = gen(rng, rows, cols, hills, seed)
        except FamilySkipped:
            raise
        except Exception:
            continue
        if exact_shape_ok(text, rows, cols, hills):
            return text, key
    raise FamilySkipped(f"{family}: {MAX_TRIES} invalid draws")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sample a labelled 2p map pool.")
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--rows", type=int, default=20)
    ap.add_argument("--cols", type=int, default=28)
    ap.add_argument("--hills", type=int, default=1)
    args = ap.parse_args(argv)

    if args.hills != 1:
        ap.error("only --hills 1 is supported (1 hill per side)")
    rows, cols, hills = args.rows, args.cols, args.hills
    os.makedirs(args.outdir, exist_ok=True)

    rng = random.Random(args.seed)
    # Shuffled round-robin: random family order, balanced family counts.
    order = list(FAMILIES * ((args.count + len(FAMILIES) - 1) // len(FAMILIES)))
    rng.shuffle(order)
    order = order[: args.count]

    live = list(FAMILIES)
    made = 0
    for i, family in enumerate(order):
        if family not in live:
            others = [f for f in live if f != family]
            if not others:
                print("warning: all families skipped; stopping early")
                break
            family = rng.choice(others)
        seed = rng.randrange(10**6)
        try:
            text, key = make_one(family, rng, rows, cols, hills, seed)
        except FamilySkipped as e:
            print(f"warning: skipping family: {e}")
            live.remove(family)
            continue
        fname = f"{family}_{key}_s{seed}.map"
        path = os.path.join(args.outdir, fname)
        with open(path, "w") as f:
            f.write(text)
        if not is_playable_2p(path):
            # Never emit an invalid map; drop it and skip the family.
            os.remove(path)
            print(f"warning: skipping family: {family} failed validation")
            live.remove(family)
            continue
        lp, wp = land_water_pct(text)
        sym = symmetric_flag(text, rows, cols)
        print(
            f"{fname} | {family} | {key} | "
            f"land {lp:.0f}% water {wp:.0f}% | sym {sym} | "
            f"{FEELS[family](lp)}"
        )
        made += 1
    print(f"wrote {made}/{args.count} maps to {args.outdir}")


if __name__ == "__main__":
    main()
