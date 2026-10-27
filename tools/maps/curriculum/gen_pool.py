"""Generate one 2-player map per available tool generator.

Usage: gen_pool.py --size N --outdir DIR --seed S

Drives every 2p-capable generator under tools/mapgen/ at NxN (or its
nearest supported size), retrying seeds until the output passes the
repo's 2p-playability check (ml.mapgen.is_playable_2p -- imported, not
copied). Any invalid map is fatal: non-zero exit naming the map and the
reason. On success one review row per map goes to stdout:

    <name> <rows>x<cols> hills=<a>v<b> land=<x>% water=<y>% symmetric=<yes|no>

Covered (see survey in git history): walk (mapgen.py Grid), cell_maze,
cavemap (amstan/mapgen.py), symmetric (symmetric_mapgen.py),
random (random_map.py). Not covered: asymmetric_mapgen (needs >= 4
players), heightmap (emits a single start; its 2p tiling is disabled
upstream), McMaps (needs PIL, absent here).
"""
import argparse
import io
import random
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve()
MAPGEN = HERE.parents[2] / "mapgen"
AMSTAN = MAPGEN / "amstan"

sys.path.insert(0, str(HERE.parents[3] / "ml"))
sys.path.insert(0, str(AMSTAN))
sys.path.insert(0, str(MAPGEN))

# NOTE: `import mapgen` would resolve to tools/mapgen/mapgen.py (the walk
# generator), not ml/mapgen.py -- ml_mapgen is loaded by path below.

import importlib.util

import symmetric_mapgen  # noqa: E402
from map import Map as _ToolMap  # noqa: E402
from random_map import RandomMap  # noqa: E402

# RandomMap calls self.get_random_option() but never inherits Map (upstream
# bug; tools/ is read-only). Bind the helper at runtime instead.
RandomMap.get_random_option = _ToolMap.get_random_option


def _load_ml_mapgen():
    spec = importlib.util.spec_from_file_location(
        "ml_mapgen", HERE.parents[3] / "ml" / "mapgen.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ml_mapgen = _load_ml_mapgen()

TRIES = 100

_SWAP = {"0": "1", "1": "0", "A": "B", "B": "A", "a": "b", "b": "a"}


def _tool(argv, cwd):
    """Run a mapgen CLI; return stdout+stderr (cell_maze prints its map
    on stderr when its own checks reject it)."""
    proc = subprocess.run(
        [sys.executable] + argv,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return (proc.stdout or "") + (proc.stderr or "")


def gen_walk(size, seed):
    return _tool(
        [
            "mapgen.py",
            "--no_players", "2",
            "--min_hills", "2",
            "--max_hills", "2",
            "--min_dimensions", str(size - 8),
            "--max_dimensions", str(size),
            "--min_block_size", "4",
            "--max_block_size", "4",
            "--symmetry", "rotational",
            "--rotational_symmetry", "3",
            "--seed", str(seed),
        ],
        MAPGEN,
    )


def gen_cell_maze(size, seed):
    return _tool(
        [
            "cell_maze.py",
            "-p", "2",
            "-g", "1", "2",
            "--h_sym", "rotate",
            "--hills", "2",
            "-a", str(size * size),
            "-r", "1.0",
            "-s", str(seed),
        ],
        MAPGEN,
    )


def gen_cavemap(size, seed):
    return _tool(
        [
            "mapgen.py",
            "--cols", str(size),
            "--rows", str(size),
            "--symmetry", "rotational",
            "--players", "2",
            "--hills", "2",
            "--seed", str(seed),
        ],
        AMSTAN,
    )


def gen_symmetric(size, seed):
    """Native dimensions (tool floor is ~50px): nearest supported."""
    random.seed(seed)
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(io.StringIO()):
        m = symmetric_mapgen.SymmetricMap()
        m.random_walk_map()
        if m.no_players != 2:
            return None
        m.print_map()
    return buf.getvalue()


def gen_random(size, seed):
    random.seed(seed)
    m = RandomMap({"rows": size, "cols": size, "players": 2})
    m.generate()
    m.reports = []  # RandomMap skips Map.__init__; toText needs it
    buf = io.StringIO()
    m.toText(buf)
    return buf.getvalue()


GENERATORS = [
    # (filename, gen_fn, exact NxN dims required)
    ("walk.map", gen_walk, True),
    ("cell_maze.map", gen_cell_maze, True),
    ("cavemap.map", gen_cavemap, True),
    ("symmetric.map", gen_symmetric, False),
    ("random.map", gen_random, True),
]


def _parse(text):
    rows = cols = 0
    grid = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("rows "):
            rows = int(line.split()[1])
        elif line.startswith("cols "):
            cols = int(line.split()[1])
        elif line.startswith("m "):
            grid.append(line[2:])
    return rows, cols, grid


def _check(text, size, exact):
    """None when the candidate is a valid pool map, else the reason."""
    if not text or "m " not in text:
        return "no map grid in tool output"
    rows, cols, _ = _parse(text)
    if exact and (rows != size or cols != size):
        return f"dims {rows}x{cols} != {size}x{size}"
    return None


def _stats(rows, cols, grid):
    flat = "".join(grid)
    total = len(flat)
    h0 = flat.count("0") + flat.count("A")
    h1 = flat.count("1") + flat.count("B")
    water = 100.0 * flat.count("%") / total
    sym = True
    for r in range(rows):
        for c in range(cols):
            a = grid[r][c]
            b = grid[rows - 1 - r][cols - 1 - c]
            if _SWAP.get(a, a) != b:
                sym = False
                break
        if not sym:
            break
    return h0, h1, 100.0 - water, water, sym


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=40)
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    for fname, gen, exact in GENERATORS:
        picked = None
        reason = "no attempt produced output"
        for k in range(TRIES):
            text = gen(args.size, args.seed + k)
            reason = _check(text, args.size, exact)
            if reason is not None:
                continue
            tmp = outdir / (fname + ".tmp")
            tmp.write_text(text)
            if not ml_mapgen.is_playable_2p(str(tmp)):
                reason = "fails is_playable_2p"
                tmp.unlink()
                continue
            picked = (text, args.seed + k)
            tmp.unlink()
            break
        if picked is None:
            print(f"FAIL {fname}: {reason}", file=sys.stderr)
            sys.exit(1)
        text, used = picked
        header = (
            f"# pool map: {fname} via gen_pool.py --size {args.size}"
            f" --seed {used}\n"
        )
        path = outdir / fname
        path.write_text(header + text.strip() + "\n")
        if not ml_mapgen.is_playable_2p(str(path)):
            print(f"FAIL {fname}: written file fails is_playable_2p", file=sys.stderr)
            sys.exit(1)
        rows, cols, grid = _parse(text)
        h0, h1, land, water, sym = _stats(rows, cols, grid)
        print(
            f"{fname} {rows}x{cols} hills={h0}v{h1}"
            f" land={land:.1f}% water={water:.1f}%"
            f" symmetric={'yes' if sym else 'no'}"
        )


if __name__ == "__main__":
    main()
