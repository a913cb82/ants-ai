"""Example tests for the example bot."""

import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TOOLS = os.path.join(ROOT, "tools")
# HERE first: `ants` is the real bot-side code beside this file.
# `engine` (and `game`) resolve to tools/, which holds no Example.
sys.path.insert(0, TOOLS)
sys.path.insert(0, HERE)

import importlib.util  # noqa: E402

import Example as EB  # noqa: E402
from ants import Ants  # noqa: E402
from engine import run_game  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "engine_ants", os.path.join(TOOLS, "ants.py")
)
assert _spec is not None and _spec.loader is not None
_engine_ants = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_engine_ants)
GameAnts = _engine_ants.Ants

TURN_BUDGET = 1.0
STARTUP_BUDGET = 3.0

SETUP = (
    "cols 20\nrows 20\nplayer_seed 0\nturntime 1000\n"
    "loadtime 3000\nviewradius2 77\nattackradius2 5\n"
    "spawnradius2 1\nturns 100"
)


def run(turn, seed=0, capsys=None):
    """One real turn: engine protocol in, engine orders out.

    No fakes, no subprocesses: the bot drives the real bot-side
    ants through one turn of real protocol text.
    """
    random.seed(seed)
    ants = Ants()
    ants.setup(SETUP)
    ants.update(turn)
    EB.Example().do_turn(ants)
    if capsys is not None:
        out, _ = capsys.readouterr()
        return [
            tuple(line.split()) for line in out.splitlines() if line.startswith("o ")
        ]
    return ants


def test_hunts_nearest_target(capsys):
    orders = run("a 10 10 0\nf 10 13\nf 10 5", capsys=capsys)
    assert orders, "ant with food in sight must move"
    ((_, row, col, direction),) = [o for o in orders if o[1:3] == ("10", "10")]
    assert direction in ("e", "w")


def test_one_order_per_ant(capsys):
    orders = run("a 5 5 0\na 5 6 0\nf 0 0\na 19 19 1", capsys=capsys)
    locs = [(o[1], o[2]) for o in orders]
    assert len(locs) == len(set(locs)), "no ant moves twice"


def test_orders_land_off_water(capsys):
    orders = run("a 10 10 0\nf 10 12\nw 10 11", capsys=capsys)
    ants = Ants()
    ants.setup(SETUP)
    for _, row, col, direction in orders:
        assert ants.destination(((int(row), int(col))), direction) != (10, 11)


def test_idles_with_no_targets(capsys):
    assert run("a 7 7 0", capsys=capsys) == []


def test_startup_under_loadtime():
    import time

    start = time.perf_counter()
    subprocess.run(
        [sys.executable, "-c", "import Example"],
        cwd=HERE,
        check=True,
        capture_output=True,
    )
    assert time.perf_counter() - start < STARTUP_BUDGET


def test_crowded_turn_under_turntime():
    import time

    lines = [f"a {r} {c} 0" for r in range(10) for c in range(10)]
    lines += [f"f {r + 10} {c}" for r in range(5) for c in range(10)]
    lines += [f"a {r + 15} {c} 1" for r in range(3) for c in range(10)]
    ants = Ants()
    ants.setup(SETUP)
    ants.update("\n".join(lines))
    start = time.perf_counter()
    EB.Example().do_turn(ants)
    assert time.perf_counter() - start < TURN_BUDGET


def generate_duel_map(tmp_path):
    """Small knife-fight map, built by the scenario itself."""
    inner = [
        "........",
        ".A......",
        ".a......",
        "...**...",
        "...**...",
        "......b.",
        "......B.",
        "........",
    ]
    lines = ["%" * 12] + ["%%" + row + "%%" for row in inner] + ["%" * 12]
    text = "rows 10\ncols 12\nplayers 2\n"
    text += "".join("m " + row + "\n" for row in lines)
    path = str(tmp_path / "duel.map")
    with open(path, "w") as fh:
        fh.write(text)
    return text


def test_scenario_scores_short_game(tmp_path):
    """Example vs RandomBot on a knife-fight map. Hunter must win."""
    text = generate_duel_map(tmp_path)
    game = GameAnts(
        {
            "map": text,
            "turns": 50,
            "loadtime": 3000,
            "turntime": 1000,
            "viewradius2": 77,
            "attackradius2": 5,
            "spawnradius2": 1,
            "player_seed": 7,
            "engine_seed": 7,
        }
    )
    bots = [
        (HERE, sys.executable + " Example.py"),
        (
            os.path.join(ROOT, "tools", "sample_bots", "python"),
            sys.executable + " RandomBot.py",
        ),
    ]
    result = run_game(game, bots, {"turns": 50, "turntime": 1000, "loadtime": 3000})
    assert result["rank"] == [0, 1], "hunter takes first"
    assert result["status"] == ["survived", "eliminated"]
    score = result["score"][0] - result["score"][1]
    assert score > 0, "hunter outscores the random walker"
    print(f"\nscenario score (Example - Random): {score}")
