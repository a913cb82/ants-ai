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
GENERATORS = {"random", "symwalk", "cavemap"}


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
