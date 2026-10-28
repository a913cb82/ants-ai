"""Smoke + playability tests for every generator under tools/mapgen/.

Working commands (all run from tools/mapgen/, outputs to stdout):
- walk (mapgen.py Grid): ``python mapgen.py --no_players 2 --min_hills 2
  --max_hills 2 --min_dimensions 32 --max_dimensions 40 --symmetry rotational
  --rotational_symmetry 3 --seed 1`` (2p, playable)
- cell_maze.py: ``python cell_maze.py -p 2 -g 1 2 --h_sym rotate --hills 2
  -a 2500 -r 1.0 -s 1`` (2p, playable)
- cavemap (amstan/mapgen.py, run from tools/mapgen/amstan/):
  ``python mapgen.py --cols 40 --rows 40 --symmetry rotational --players 2
  --hills 2 --seed 1`` (2p, playable)
- symmetric_mapgen.py: ``python symmetric_mapgen.py --players 2 --seed 1``
  (2p, playable; native floor is ~50px per side)
- asymmetric_mapgen.py: ``python asymmetric_mapgen.py --players 2
  --min_dim 30 --max_dim 40 --min_start_distance 10 --seed 1``
  (2p small; upstream defaults are 4+ players)
- random_map.py: ``python random_map.py`` (no args; random player count)
  or ``python random_map.py --rows 40 --cols 40 --players 2 --seed 1``
  (2p, playable)
- heightmap.py: ``python heightmap.py`` (no args; single-start map, NOT 2p:
  its 2p tiling is disabled upstream, so this only asserts parseable output)
- McMaps.py: ``python McMaps.py`` (no args; emits a cells maze with no
  player starts, NOT 2p: no hill-entry path exists upstream)
"""

import io
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPGEN = ROOT / "tools" / "mapgen"
AMSTAN = MAPGEN / "amstan"

sys.path.insert(0, str(ROOT / "ml"))

from mapgen import is_playable_2p  # noqa: E402


def _run(argv, cwd=MAPGEN, timeout=300):
    return subprocess.run(
        [sys.executable, *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _parse(text):
    rows = cols = players = 0
    grid = []
    for line in text.splitlines():
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


def _assert_parseable(text):
    rows, cols, players, grid = _parse(text)
    assert rows > 0 and cols > 0 and players >= 0, f"bad header in:\n{text[:500]}"
    assert len(grid) == rows, f"want {rows} rows, got {len(grid)}"
    assert all(len(r) == cols for r in grid), "ragged grid"
    return rows, cols, players, grid


def test_random_map_no_args_runs_and_parses():
    """random_map.py with no args must not crash (reports AttributeError)."""
    proc = _run(["random_map.py"])
    assert proc.returncode == 0, proc.stderr[-2000:]
    _assert_parseable(proc.stdout)


def test_random_map_2p_playable(tmp_path):
    """RandomMap must init the Map base so toText works; 2p map must play."""
    sys.path.insert(0, str(MAPGEN))
    try:
        from random_map import RandomMap
    finally:
        sys.path.pop(sys.path.index(str(MAPGEN)))
    import random

    random.seed(7)
    m = RandomMap({"rows": 40, "cols": 40, "players": 2})
    m.generate()
    buf = io.StringIO()
    m.toText(buf)
    out = tmp_path / "random2p.map"
    out.write_text(buf.getvalue())
    assert is_playable_2p(str(out))


def test_heightmap_no_args_runs_and_parses():
    """heightmap.py with no args must not crash (float randint TypeError)."""
    proc = _run(["heightmap.py", "--seed", "1"], timeout=600)
    assert proc.returncode == 0, proc.stderr[-2000:]
    _assert_parseable(proc.stdout)


def test_mcmaps_imports():
    """McMaps.py must import under PIL 13 (bare `import Image` fails)."""
    proc = _run(["-c", "import McMaps; print('ok')"])
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "ok" in proc.stdout


def test_mcmaps_emits_parseable_map():
    """McMaps.py must emit a parseable map (no 2p/hill path upstream)."""
    proc = _run(["McMaps.py"], timeout=600)
    assert proc.returncode == 0, proc.stderr[-2000:]
    _assert_parseable(proc.stdout)


def test_cell_maze_2p_playable(tmp_path):
    proc = _run(
        [
            "cell_maze.py",
            "-p",
            "2",
            "-g",
            "1",
            "2",
            "--h_sym",
            "rotate",
            "--hills",
            "2",
            "-a",
            "2500",
            "-r",
            "1.0",
            "-s",
            "1",
        ],
        timeout=600,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    out = tmp_path / "cell2p.map"
    out.write_text(proc.stdout)
    assert is_playable_2p(str(out))


def test_symmetric_mapgen_2p_playable(tmp_path):
    """symmetric_mapgen.py needs a real 2p invocation (defaults are random)."""
    proc = _run(["symmetric_mapgen.py", "--players", "2", "--seed", "1"])
    assert proc.returncode == 0, proc.stderr[-2000:]
    out = tmp_path / "sym2p.map"
    out.write_text(proc.stdout)
    assert is_playable_2p(str(out))


def test_cavemap_2p_playable(tmp_path):
    proc = _run(
        [
            "mapgen.py",
            "--cols",
            "40",
            "--rows",
            "40",
            "--symmetry",
            "rotational",
            "--players",
            "2",
            "--hills",
            "2",
            "--seed",
            "1",
        ],
        cwd=AMSTAN,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    out = tmp_path / "cave2p.map"
    out.write_text(proc.stdout)
    assert is_playable_2p(str(out))


def test_asymmetric_mapgen_2p_small(tmp_path):
    """asymmetric_mapgen.py needs a 2p-capable invocation (min is 4 upstream)."""
    proc = _run(
        [
            "asymmetric_mapgen.py",
            "--players",
            "2",
            "--min_dim",
            "30",
            "--max_dim",
            "40",
            "--min_start_distance",
            "10",
            "--seed",
            "1",
        ],
        timeout=600,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    out = tmp_path / "asym2p.map"
    out.write_text(proc.stdout)
    assert is_playable_2p(str(out))


def test_walk_grid_2p_playable(tmp_path):
    proc = _run(
        [
            "mapgen.py",
            "--no_players",
            "2",
            "--min_hills",
            "2",
            "--max_hills",
            "2",
            "--min_dimensions",
            "32",
            "--max_dimensions",
            "40",
            "--min_block_size",
            "4",
            "--max_block_size",
            "4",
            "--symmetry",
            "rotational",
            "--rotational_symmetry",
            "3",
            "--seed",
            "1",
        ],
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    out = tmp_path / "walk2p.map"
    out.write_text(proc.stdout)
    assert is_playable_2p(str(out))
