"""Pool generator: one 2p map per tool generator, every map validated.

Runs tools/maps/curriculum/gen_pool.py at small fixed size into tmp_path,
then checks: (a) each generator entry produced a file, (b) every map
passes ml.mapgen.is_playable_2p, (c) review-row fields parse and match
the file on disk.
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "tools" / "maps" / "curriculum" / "gen_pool.py"

sys.path.insert(0, str(REPO / "ml"))

import mapgen  # noqa: E402

EXPECTED = [
    "walk.map",
    "cell_maze.map",
    "cavemap.map",
    "symmetric.map",
    "random.map",
]

ROW = re.compile(
    r"^(?P<name>\S+\.map) (?P<dims>\d+x\d+) hills=(?P<h0>\d+)v(?P<h1>\d+) "
    r"land=(?P<land>[\d.]+)% water=(?P<water>[\d.]+)% symmetric=(?P<sym>yes|no)$"
)


def _read_grid(path):
    rows = cols = 0
    grid = []
    with open(path) as f:
        for line in f:
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


@pytest.fixture(scope="module")
def pool(tmp_path_factory):
    outdir = tmp_path_factory.mktemp("pool")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--size", "24", "--outdir", str(outdir),
         "--seed", "7"],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert proc.returncode == 0, f"gen_pool failed:\n{proc.stderr}"
    return outdir, proc.stdout


def test_each_generator_produces_a_file(pool):
    outdir, _ = pool
    for name in EXPECTED:
        assert (outdir / name).is_file(), name


def test_every_map_is_playable_2p(pool):
    outdir, _ = pool
    maps = sorted(outdir.glob("*.map"))
    assert len(maps) == len(EXPECTED)
    for path in maps:
        assert mapgen.is_playable_2p(str(path)), path.name


def test_review_rows_parse_and_match_files(pool):
    outdir, stdout = pool
    rows = [ROW.match(line) for line in stdout.splitlines() if line.strip()]
    assert len(rows) == len(EXPECTED), stdout
    assert all(r is not None for r in rows), stdout
    by_name = {r.group("name"): r for r in rows}
    assert sorted(by_name) == sorted(EXPECTED)
    for name, r in by_name.items():
        fr, fc, grid = _read_grid(outdir / name)
        assert f"{fr}x{fc}" == r.group("dims"), name
        flat = "".join(grid)
        h0 = flat.count("0") + flat.count("A")
        h1 = flat.count("1") + flat.count("B")
        assert (h0, h1) == (int(r.group("h0")), int(r.group("h1"))), name
        water = 100.0 * flat.count("%") / len(flat)
        assert abs(water - float(r.group("water"))) < 0.15, name
        assert abs(float(r.group("land")) + float(r.group("water")) - 100.0) < 0.2, name
