"""Example tests for the example bot."""

import os
import random
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join("tools"))

import Example as EB  # noqa: E402
from ants import Ants  # noqa: E402
from engine import run_game  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
TURN_BUDGET = 1.0
STARTUP_BUDGET = 3.0


class FakeAnts:
    """Tiny toroidal world with ants, food, and foes."""

    def __init__(self, own, foods, foes, water=()):
        self._own = list(own)
        self._foods = list(foods)
        self._foes = list(foes)
        self._water = set(water)
        self.orders = []

    def my_ants(self):
        return list(self._own)

    def food(self):
        return list(self._foods)

    def enemy_ants(self):
        return [(f, 1) for f in self._foes]

    def distance(self, loc1, loc2):
        (a_row, a_col), (b_row, b_col) = loc1, loc2
        dr = min(abs(a_row - b_row), ROWS - abs(a_row - b_row))
        dc = min(abs(a_col - b_col), COLS - abs(a_col - b_col))
        return dr + dc

    def direction(self, loc1, loc2):
        (a_row, a_col), (b_row, b_col) = loc1, loc2
        d = []
        if a_row != b_row:
            d.append("s" if (b_row - a_row) % ROWS < ROWS // 2 else "n")
        if a_col != b_col:
            d.append("e" if (b_col - a_col) % COLS < COLS // 2 else "w")
        return d or ["n"]

    def destination(self, loc, direction):
        row, col = loc
        dr, dc = AIM[direction]
        return ((row + dr) % ROWS, (col + dc) % COLS)

    def unoccupied(self, loc):
        return loc not in self._water

    def issue_order(self, order):
        (loc, direction) = order
        self.orders.append((loc[0], loc[1], direction))


def run(own, foods, foes, seed=0, water=()):
    random.seed(seed)
    ants = FakeAnts(own, foods, foes, water)
    EB.Example().do_turn(ants)
    return ants


# 1. correctness


def test_hunts_nearest_target():
    ants = run([(10, 10)], [(10, 13), (10, 5)], [])
    assert ants.orders, "ant with food in sight must move"
    row, col, direction = ants.orders[0]
    assert (row, col) == (10, 10)
    assert direction in ("e", "w")


def test_one_order_per_ant():
    ants = run([(5, 5), (5, 6)], [(0, 0)], [(19, 19)])
    locs = [(o[0], o[1]) for o in ants.orders]
    assert len(locs) == len(set(locs)), "no ant moves twice"


def test_orders_land_off_water():
    water = [(10, 11)]
    ants = run([(10, 10)], [(10, 12)], [], water=water)
    for row, col, direction in ants.orders:
        assert ants.destination((row, col), direction) not in water


def test_idles_with_no_targets():
    assert run([(7, 7)], [], []).orders == []


# 2. runtime


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

    own = [(r, c) for r in range(10) for c in range(10)]
    foods = [(r + 10, c) for r in range(5) for c in range(10)]
    foes = [(r + 15, c) for r in range(3) for c in range(10)]
    ants = FakeAnts(own, foods, foes)
    start = time.perf_counter()
    EB.Example().do_turn(ants)
    assert time.perf_counter() - start < TURN_BUDGET
    assert len(ants.orders) <= len(own)


# 3. scenario


def generate_duel_map(tmp_path):
    """Small symmetric 2p map, built by the scenario itself."""
    inner = ["." * 26 for _ in range(28)]
    inner[2] = "...A......................"
    inner[3] = "...a......................"
    inner[25] = "......................B..."
    inner[10] = "......*..................."
    inner[17] = "...................*......"
    lines = ["%" * 30] + ["%%" + row + "%%" for row in inner] + ["%" * 30]
    text = "rows 30\ncols 30\nplayers 2\n"
    text += "".join("m " + row + "\n" for row in lines)
    path = str(tmp_path / "duel.map")
    with open(path, "w") as fh:
        fh.write(text)
    return text


def test_scenario_scores_short_game(tmp_path):
    """50 real engine turns, Example vs RandomBot. Reports score."""
    text = generate_duel_map(tmp_path)
    game = Ants(
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
            os.path.join(HERE, "..", "..", "tools", "sample_bots", "python"),
            sys.executable + " RandomBot.py",
        ),
    ]
    result = run_game(game, bots, {"turns": 50, "turntime": 1000, "loadtime": 3000})
    assert result["game_length"] == 50, "scenario must run the full game"
    assert result["status"] == ["survived", "survived"]
    score = result["score"][0] - result["score"][1]
    print(f"\nscenario score (Example - Random): {score} (ranks {result['rank']})")
