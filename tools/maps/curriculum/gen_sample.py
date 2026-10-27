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

MAP SOURCE SURVEY (tools/mapgen + Java):
  Python generators under tools/mapgen/:
  - random_map.RandomMap ......... CAPABLE. Explicit rows/cols/players/land
    options; hills are the 2 player starts. Setting range: land 70-95%
    (below 70% is swamp soup, above 95% an empty field).
  - symmetric_mapgen.SymmetricMap . CAPABLE (with small-map tuning). Random
    translational random-walk map; dims drawn from per_player_dim/
    dim_bounds class attrs. Settings: target land 60-95% (tool default
    band), extra walks 20-40 (tool default 30), min_start_distance scaled
    to half the max toroidal hill distance (tool default 30 is impossible
    below ~60x60 since hills sit ~17 apart on 20x28). Even dims required
    (tool loops forever on odd dims, so odd dims skip this family).
  - amstan cavemap (Cavemap) ..... CAPABLE. Explicit size/players/symmetry;
    random-walk carve + cellular-automaton smooth. Settings: symmetry in
    {translational, horizontal, point, rotational} (diagonal needs square
    maps), smooth passes 2-5 (tool default 4; 0-1 leaves static, 6+
    washes out), hills=1 placed uniformly then mirrored by symmetry.
  - mapgen.py Grid ............... EXCLUDED (tool limit). Dims are drawn
    from [min_dimensions, max_dimensions] and must also satisfy block /
    lcm symmetry constraints; 0 exact-20x28 hits in 500 seeds (~1/28000
    by construction). Cannot target fixed dims.
  - cell_maze.CellMazeMap ........ EXCLUDED (tool limit). Dims derive from
    area/aspect_ratio heuristics; no exact-size control.
  - heightmap.HeightMapMap ...... EXCLUDED (tool limit). Needs a >=16x16
    tile per player ( recurses forever for 2 players below ~32x32).
  - asymmetric_mapgen ........... EXCLUDED (tool limit). min_players = 4,
    cannot emit 2-player maps.
  - McMaps.py .................... UNRUNNABLE here: `import Image` (pre-PIL
    namespace) fails; vendoring/installing is out of scope.
  Java generators (java/javac 25 available; all run headless, no GUI):
  - MapGenerator.java ............ EXCLUDED (tool limit). Map size
    constants 80-120, no dimension parameters; cannot do 20x28.
  - SymmetricMapgen.java ......... EXCLUDED (tool limit). MIN_PLAYERS=4,
    dims 70-120; cannot do 2-player 20x28.
  - MapWalker.java is a helper, Test.java a harness (not generators).
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
    "map", "terrain", "util", "symmetricmap", "cavemap",
    "random_map", "symmetric_mapgen",
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
FAMILIES = ("random", "symwalk", "cavemap")
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


GENERATORS = {
    "random": gen_random,
    "symwalk": gen_symwalk,
    "cavemap": gen_cavemap,
}

FEELS = {
    "random": lambda lp: "open field" if lp > 90 else "scattered ponds",
    "symwalk": lambda lp: "winding corridors" if lp > 80 else "tight corridors",
    "cavemap": lambda lp: "smooth lakes" if lp > 85 else "cavernous pockets",
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
