"""2p shaping for the working mapgen scripts.

Each test runs one generator with a DOCUMENTED command that produces a
small 2-player map (1 hill each) and checks the output passes
ml.mapgen.is_playable_2p. Scratch output goes to tmp_path (the real
archive under tools/maps is never written).

Breakage recorded while shaping (defaults observed before the fix):
- mapgen.py (walk/Grid): default random players (2-8) and 60-150px.
  Expresses 2p-small via flags alone; no code change.
- cell_maze.py: default random players (~2-10) and huge areas. Naive
  `-p 2 -a 900` dies two ways: final grids under 900 cells/player are
  rejected ("Map area is too small", floor in tools/mapgen/map.py), and
  exactly-1800-cell areas usually blow up in set_openness ("Map too
  open"). `-p 2 -a 2000 -g 1 2 -r 1.0 --hills 1` gives 44x44, the
  practical minimum square 2p cell maze; no code change.
- symmetric_mapgen.py: NO CLI at all; default random 2-10 players,
  50-150px. Could not express 2p-small -> added --players/--rows/
  --cols/--min_start_distance/--seed (defaults preserve old behavior).
  Small maps also need a short min_start_distance: the default 30px
  exceeds the max toroidal hill distance on a 30px map, so dimension
  search would loop forever.
- amstan/mapgen.py (cavemap): default 60x60 4p. Expresses 2p-small via
  flags alone; no code change. Must run with cwd=tools/mapgen/amstan
  (bare `from cavemap import ...`).
- asymmetric_mapgen.py: NO CLI at all; default random 4-10 players,
  70-120px, and min_players=4 forbids 2p entirely. Added
  --players/--rows/--cols/--min_start_distance/--seed; --players 2 pins
  the translation to half-rows/half-cols (lcm 2). Same start-distance
  caveat as symmetric_mapgen.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

sys.path.insert(0, str(ROOT / "ml"))


def _run(cmd, cwd, out):
    with open(out, "w") as f:
        proc = subprocess.run(
            [PY, *cmd],
            cwd=cwd,
            stdout=f,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
        )
    assert proc.returncode == 0, f"{cmd} exit {proc.returncode}: {proc.stderr[-500:]}"
    return out


def _grid(out):
    rows = cols = players = 0
    grid = []
    with open(out) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("rows "):
                rows = int(line.split()[1])
            elif line.startswith("cols "):
                cols = int(line.split()[1])
            elif line.startswith("players "):
                players = int(line.split()[1])
            elif line.startswith("m "):
                grid.append(line[2:])
    return rows, cols, players, grid


def _check_small_2p(out):
    """Bar: exit 0 (done by _run) + playable 2p + small + 1 hill each."""
    import mapgen as ml_mapgen

    assert ml_mapgen.is_playable_2p(str(out)), f"{out} not playable 2p"
    rows, cols, players, grid = _grid(out)
    assert players == 2, f"players={players}"
    assert 20 <= rows <= 50, f"rows={rows}"
    assert 20 <= cols <= 50, f"cols={cols}"
    flat = "".join(grid)
    first = sum(1 for c in flat if c in "0A")
    second = sum(1 for c in flat if c in "1B")
    assert (first, second) == (1, 1), f"hills={first, second}"


def test_walk_mapgen_2p(tmp_path):
    """python tools/mapgen/mapgen.py --no_players 2 --min_dimensions 20
    --max_dimensions 40 --min_hills 1 --max_hills 1 --min_starting_distance 9
    --symmetry rotational --rotational_symmetry 4 --seed 1"""
    out = tmp_path / "walk_2p.map"
    _run(
        [
            "tools/mapgen/mapgen.py",
            "--no_players",
            "2",
            "--min_dimensions",
            "20",
            "--max_dimensions",
            "40",
            "--min_hills",
            "1",
            "--max_hills",
            "1",
            "--min_starting_distance",
            "9",
            "--symmetry",
            "rotational",
            "--rotational_symmetry",
            "4",
            "--seed",
            "1",
        ],
        ROOT,
        out,
    )
    _check_small_2p(out)


def test_cell_maze_2p(tmp_path):
    """python tools/mapgen/cell_maze.py -p 2 -a 2000 -g 1 2 -r 1.0
    --hills 1 -s 1  (44x44: 900 cells/player floor rules out <=40px)"""
    out = tmp_path / "cell_maze_2p.map"
    _run(
        [
            "tools/mapgen/cell_maze.py",
            "-p",
            "2",
            "-a",
            "2000",
            "-g",
            "1",
            "2",
            "-r",
            "1.0",
            "--hills",
            "1",
            "-s",
            "1",
        ],
        ROOT,
        out,
    )
    _check_small_2p(out)


def test_symmetric_mapgen_2p(tmp_path):
    """python tools/mapgen/symmetric_mapgen.py --players 2 --rows 30
    --cols 30 --min_start_distance 10 --seed 1"""
    out = tmp_path / "symmetric_2p.map"
    _run(
        [
            "tools/mapgen/symmetric_mapgen.py",
            "--players",
            "2",
            "--rows",
            "30",
            "--cols",
            "30",
            "--min_start_distance",
            "10",
            "--seed",
            "1",
        ],
        ROOT,
        out,
    )
    _check_small_2p(out)


def test_cavemap_2p(tmp_path):
    """(cwd tools/mapgen/amstan) python mapgen.py --players 2 --rows 30
    --cols 30 --hills 1 --symmetry rotational --seed 1"""
    out = tmp_path / "cave_2p.map"
    _run(
        [
            "mapgen.py",
            "--players",
            "2",
            "--rows",
            "30",
            "--cols",
            "30",
            "--hills",
            "1",
            "--symmetry",
            "rotational",
            "--seed",
            "1",
        ],
        ROOT / "tools" / "mapgen" / "amstan",
        out,
    )
    _check_small_2p(out)


def test_asymmetric_mapgen_2p(tmp_path):
    """python tools/mapgen/asymmetric_mapgen.py --players 2 --rows 30
    --cols 30 --min_start_distance 10 --seed 1"""
    out = tmp_path / "asymmetric_2p.map"
    _run(
        [
            "tools/mapgen/asymmetric_mapgen.py",
            "--players",
            "2",
            "--rows",
            "30",
            "--cols",
            "30",
            "--min_start_distance",
            "10",
            "--seed",
            "1",
        ],
        ROOT,
        out,
    )
    _check_small_2p(out)
