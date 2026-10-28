"""Crash-repro + valid-output tests for the 3 owned mapgen scripts.

Working commands (all run from tools/mapgen/, outputs to stdout):
- random_map.py: ``python random_map.py`` (no args; random player count)
  or ``python random_map.py --rows 40 --cols 40 --players 2 --seed 1``
  (2p, playable)
- heightmap.py: ``python heightmap.py --seed 1`` (single-start map;
  2p tiling is disabled upstream, so this asserts parseable output only)
- McMaps.py: ``python McMaps.py`` (emits a cells maze with no player
  starts; no hill-entry path exists upstream, so parseable output only)

NOTE: walk/cell_maze/symmetric/cavemap/asymmetric 2p work belongs to a
sibling builder; *.java belongs to implmapgen-java. This file covers
random_map.py, heightmap.py and McMaps.py only.
"""

import io
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPGEN = ROOT / "tools" / "mapgen"

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
