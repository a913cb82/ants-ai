"""Java map generators under tools/mapgen (TDD: written before the fixes).

Working commands (all run from the repo root; each exits 0 and emits a
parseable map; 2p ones additionally pass ml.mapgen.is_playable_2p):

- MapGenerator (full random symmetric map, 2/4/8 players):
    javac -d /tmp/mjclasses tools/mapgen/*.java
    java -cp /tmp/mjclasses MapGenerator --players 2 --seed 7 --rows 34 --cols 40 --out /tmp/mj2p.map
- MapWalker (walker-fill demo as a small 2-player map):
    java -cp /tmp/mjclasses MapWalker --seed 7 --out /tmp/mjwalk.map
- SymmetricMapgen (translation-symmetric 4-10 player map):
    java -cp /tmp/mjclasses SymmetricMapgen --seed 7 --out /tmp/mjsym.map
- Test (thin driver over MapGenerator, default 8 players):
    java -cp /tmp/mjclasses Test 2 --seed 7 --out /tmp/mjtest2p.map

Roles: MapGenerator generates a mirrored symmetric map (2/4/8 players) via
random-walk land fill; MapWalker is its land-fill library (walkers spread land
over water, enforcing connectivity); SymmetricMapgen builds translation-
symmetric 4-10p maps by carving water with random walks; Test is the
smoke driver for MapGenerator.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "tools"))

from ants import Ants  # noqa: E402
from mapgen import is_playable_2p, parse_text  # noqa: E402

MAPGEN = ROOT / "tools" / "mapgen"

ENGINE_OPTS = {
    "turns": 1,
    "loadtime": 1000,
    "turntime": 1000,
    "viewradius2": 77,
    "attackradius2": 5,
    "spawnradius2": 1,
}


def _engine_loads(path: Path) -> None:
    """Raise unless the engine parses the map (headers + grid consistent)."""
    Ants({"map": path.read_text(), **ENGINE_OPTS})


@pytest.fixture(scope="module")
def classes(tmp_path_factory):
    out = tmp_path_factory.mktemp("mjclasses")
    proc = subprocess.run(
        ["javac", "-d", str(out), *(str(p) for p in MAPGEN.glob("*.java"))],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"javac failed:\n{proc.stderr}"
    return out


def _run(classes, *args: str, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["java", "-cp", str(classes), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _emit(classes, tmp_path: Path, name: str, *args: str) -> Path:
    proc = _run(classes, *args)
    assert proc.returncode == 0, (
        f"{' '.join(args)} exited {proc.returncode}:\n{proc.stderr}"
    )
    assert proc.stdout.startswith(("players ", "rows ")), (
        f"{name} emitted no map header:\n{proc.stdout[:300]}\n{proc.stderr[:500]}"
    )
    path = tmp_path / name
    path.write_text(proc.stdout)
    assert "scratch" not in str(ROOT / "ml" / "archive"), (
        "guard: never touch the real archive"
    )
    return path


def test_test_driver_default_runnable(classes, tmp_path):
    """java Test (no args): exit 0 + parseable map the engine loads."""
    path = _emit(classes, tmp_path, "t8.map", "Test", "8")
    rows, cols, _players, grid = parse_text(path.read_text())
    assert len(grid) == rows and all(len(r) == cols for r in grid)
    _engine_loads(path)


def test_test_driver_2p_playable(classes, tmp_path):
    """java Test 2: small 2p invocation passes is_playable_2p."""
    path = _emit(classes, tmp_path, "t2.map", "Test", "2", "7")
    assert is_playable_2p(str(path)), f"not 2p-playable:\n{path.read_text()[:400]}"
    _engine_loads(path)


def test_mapgenerator_2p_small_playable(classes, tmp_path):
    """MapGenerator --players 2 small map: exit 0, playable + engine-valid."""
    out = str(tmp_path / "mg2.map")
    proc = _run(
        classes,
        "MapGenerator",
        "--players",
        "2",
        "--seed",
        "7",
        "--rows",
        "34",
        "--cols",
        "40",
        "--out",
        out,
    )
    assert proc.returncode == 0, f"MapGenerator failed:\n{proc.stderr}"
    path = Path(out)
    assert is_playable_2p(str(path)), f"not 2p-playable:\n{path.read_text()[:400]}"
    _engine_loads(path)


def test_mapgenerator_4p_engine_valid(classes, tmp_path):
    """MapGenerator --players 4: four distinct hills, engine loads."""
    path = _emit(
        classes, tmp_path, "mg4.map", "MapGenerator", "--players", "4", "--seed", "7"
    )
    _rows, _cols, players, grid = parse_text(path.read_text())
    assert players == 4
    flat = "".join(grid)
    assert all(str(i) in flat for i in range(4)), "each of 4 players needs a hill"
    _engine_loads(path)


def test_mapwalker_demo_2p(classes, tmp_path):
    """java MapWalker: walker demo emits a playable 2p map."""
    path = _emit(classes, tmp_path, "mw.map", "MapWalker", "--seed", "7")
    assert is_playable_2p(str(path)), f"not 2p-playable:\n{path.read_text()[:400]}"
    _engine_loads(path)


def test_symmetric_parseable_engine_valid(classes, tmp_path):
    """SymmetricMapgen: parseable, connected, every player owns a hill."""
    path = _emit(classes, tmp_path, "sym.map", "SymmetricMapgen", "--seed", "7")
    rows, cols, players, grid = parse_text(path.read_text())
    assert len(grid) == rows and all(len(r) == cols for r in grid)
    assert 4 <= players <= 10
    flat = "".join(grid)
    assert set(flat) <= set(".%ABCDEFGHIJ"), f"bad chars: {set(flat)}"
    # Every player owns an ant+hill (uppercase is ant+hill to the engine).
    assert all(chr(65 + i) in flat for i in range(players))
    # Fully connected over non-water (torus moves, like the generator).
    start = next((r, c) for r in range(rows) for c in range(cols) if grid[r][c] != "%")
    seen = {start}
    stack = [start]
    while stack:
        r, c = stack.pop()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = ((r + dr) % rows, (c + dc) % cols)
            if nxt not in seen and grid[nxt[0]][nxt[1]] != "%":
                seen.add(nxt)
                stack.append(nxt)
    assert sum(ch != "%" for row in grid for ch in row) == len(seen), "map disconnected"
    _engine_loads(path)
