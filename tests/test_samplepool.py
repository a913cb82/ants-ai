"""TDD for tools/maps/curriculum/gen_sample.py: labelled 20x28 2p sample pool.

(a) --count 4 yields 4 files, all passing ml.mapgen.is_playable_2p.
(b) every filename parses back to generator + settings.
(c) each map is exactly 20 rows x 28 cols with exactly 1 hill per side.
(d) same seed reproduces byte-identical files.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "maps" / "curriculum" / "gen_sample.py"

sys.path.insert(0, str(ROOT))
from ml.mapgen import is_playable_2p

NAME_RE = re.compile(
    r"^(?P<gen>[a-z]+)_(?P<settings>.+)_s(?P<seed>\d+)\.map$"
)
GENERATORS = {"random", "symwalk", "cavemap", "gridwalk", "asymwalk",
                "cellmaze"}


def run_sampler(tmp_path, count=4, seed=7):
    outdir = tmp_path / f"pool_{seed}_{count}"
    cmd = [
        sys.executable, str(SCRIPT),
        "--count", str(count), "--outdir", str(outdir),
        "--seed", str(seed), "--rows", "20", "--cols", "28", "--hills", "1",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, f"sampler failed:\n{proc.stderr[-2000:]}"
    return sorted(outdir.glob("*.map"))


def parse_map(path):
    header = {}
    grid = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("rows ", "cols ", "players ")):
            key, val = line.split()
            header[key] = int(val)
        elif line.startswith("m "):
            grid.append(line[2:])
    return header, grid


def test_sample_of_4_all_playable(tmp_path):
    files = run_sampler(tmp_path)
    assert len(files) == 4, f"expected 4 maps, got {len(files)}"
    for f in files:
        assert is_playable_2p(str(f)), f"unplayable: {f.name}"


def test_filenames_parse_to_generator_and_settings(tmp_path):
    for f in run_sampler(tmp_path):
        m = NAME_RE.match(f.name)
        assert m, f"filename does not encode provenance: {f.name}"
        assert m.group("gen") in GENERATORS, f"unknown generator: {f.name}"
        assert len(m.group("settings")) >= 3, f"empty settings: {f.name}"
        assert m.group("seed").isdigit()


def test_dimensions_and_hill_counts(tmp_path):
    for f in run_sampler(tmp_path):
        header, grid = parse_map(f)
        assert (header["rows"], header["cols"]) == (20, 28), f.name
        assert header["players"] == 2, f.name
        assert len(grid) == 20 and all(len(r) == 28 for r in grid), f.name
        flat = "".join(grid)
        assert flat.count("0") == 1, f"{f.name}: side-0 hills != 1"
        assert flat.count("1") == 1, f"{f.name}: side-1 hills != 1"


def test_same_seed_reproduces_identical_files(tmp_path):
    first = run_sampler(tmp_path / "a", seed=7)
    second = run_sampler(tmp_path / "b", seed=7)
    assert [f.name for f in first] == [f.name for f in second]
    for a, b in zip(first, second):
        assert a.read_bytes() == b.read_bytes(), f"nondeterministic: {a.name}"


# Regression coverage for newly-enabled families (round 2).
# Each drives the upstream tool with 2p small-map settings and requires
# exact 20x28 dims, 1 hill per side, and is_playable_2p.
import io  # noqa: E402
from contextlib import redirect_stderr  # noqa: E402

MAPGEN_DIR = ROOT / "tools" / "mapgen"
AMSTAN_DIR = MAPGEN_DIR / "amstan"


def _with_path(first):
    import sys as _sys

    class _Guard:
        _NAMES = ("map", "mapgen", "terrain", "util", "symmetricmap",
                  "cavemap", "random_map", "symmetric_mapgen",
                  "cell_maze", "asymmetric_mapgen", "McMaps")

        def __enter__(self):
            for _n in self._NAMES:
                _sys.modules.pop(_n, None)
            self._saved = _sys.path[:]
            rest = [p for p in _sys.path if str(p) not in
                    (str(MAPGEN_DIR), str(AMSTAN_DIR))]
            _sys.path[:] = [str(first)] + rest
            return self

        def __exit__(self, *exc):
            _sys.path[:] = self._saved
            for _n in self._NAMES:
                _sys.modules.pop(_n, None)
            return False
    return _Guard()


def _check_text_20x28_1hill(text):
    assert f"rows 20" in text and f"cols 28" in text
    grid = [ln[2:].strip() for ln in text.splitlines()
            if ln.startswith("m ")]
    assert len(grid) == 20 and all(len(r) == 28 for r in grid)
    flat = "".join(grid)
    assert flat.count("0") == 1 and flat.count("1") == 1


def test_mcmaps_imports_with_pillow():
    with _with_path(MAPGEN_DIR):
        import McMaps  # noqa: F401  -- must import (was `import Image`)


def test_grid_targets_exact_dims():
    import random
    with _with_path(MAPGEN_DIR):
        from mapgen import Grid
        random.seed(5)
        g = Grid()
        g.no_hills = 1
        g.symmetry = "tile"
        assert g.tile_symmetric_grid(2, 20, 28, 100, 1, 1,
                                     exact_rows=20, exact_cols=28)
        assert (g.rows, g.cols) == (20, 28)
        g.squares = [["%" for _ in range(28)] for _ in range(20)]
        g.add_starting_hills()
        g.generate_basis_information()
        with redirect_stderr(io.StringIO()):
            g.add_land_with_recursive_backtracking()
            g.add_extra_land_blocks()
            g.add_extra_land_locs()
        g.make_symmetric()
        g.add_extra_hills()
        g.translate()
        _check_text_20x28_1hill(_grid_text(g))


def _grid_text(g):
    lines = [f"rows {g.rows}", f"cols {g.cols}",
             f"players {g.no_players}"]
    lines += ["m " + "".join(r) for r in g.squares]
    return "\n".join(lines) + "\n"


def test_grid_default_path_unchanged():
    """No exact args -> legacy random-dim path still works."""
    import random
    with _with_path(MAPGEN_DIR):
        from mapgen import Grid
        random.seed(5)
        g = Grid()
        g.no_hills = 1
        g.symmetry = "tile"
        assert g.tile_symmetric_grid(2, 60, 150, 100, 3, 4)
        assert not (g.rows == 20 and g.cols == 28)


def test_asymmetric_targets_exact_dims_walk():
    import random
    with _with_path(MAPGEN_DIR):
        from asymmetric_mapgen import AsymmetricMap
        random.seed(11)
        m = AsymmetricMap()
        m.min_players = m.max_players = 2
        m.min_start_distance = 8
        m.pick_dimensions(exact_rows=20, exact_cols=28)
        assert (m.rows, m.cols) == (20, 28)
        assert m.no_players == 2
        m.map_data = [["%" for _ in range(28)] for _ in range(20)]
        m.add_ants()
        m.basis = m.get_basis()
        m.start_walks()
        with redirect_stderr(io.StringIO()):
            m.add_land()
        buf = io.StringIO()
        import sys as _sys
        old = _sys.stdout
        _sys.stdout = buf
        try:
            m.print_map()
        finally:
            _sys.stdout = old
        text = buf.getvalue()
        _check_text_20x28_1hill(text)
        assert is_playable_2p(_write_tmp(text)) is True


def _write_tmp(text):
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".map")
    with open(fd, "w") as f:
        f.write(text)
    return path


def test_cell_maze_targets_exact_dims_via_options():
    import random
    with _with_path(MAPGEN_DIR):
        from cell_maze import CellMazeMap
        random.seed(0)  # options seed drives determinism instead
        m = CellMazeMap({"players": 2, "area": 561, "aspect_ratio": 1.4,
                         "grid": (1, 2), "hills": 1, "seed": 1000,
                         "maze_type": "prims", "openness": 0.5,
                         "cell_size": 6.0, "cell_width": 1.0})
        m.min_hill_dist = 8
        with redirect_stderr(io.StringIO()):
            m.generate()
        buf = io.StringIO()
        with redirect_stderr(io.StringIO()):
            m.toText(buf)
        _check_text_20x28_1hill(buf.getvalue())
