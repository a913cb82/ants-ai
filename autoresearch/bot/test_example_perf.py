"""Performance tests for the example bot.

The engine kills slow bots: one turn must finish in 1000 ms,
startup in 3000 ms. These pins hold the budgets.
"""

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Example as EB  # noqa: E402
from test_example import FakeAnts  # noqa: E402

TURN_BUDGET = 1.0
STARTUP_BUDGET = 3.0


def test_startup_under_loadtime():
    start = time.perf_counter()
    subprocess.run(
        [sys.executable, "-c", "import Example"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        check=True,
        capture_output=True,
    )
    assert time.perf_counter() - start < STARTUP_BUDGET


def test_crowded_turn_under_turntime():
    own = [(r, c) for r in range(10) for c in range(10)]
    foods = [(r + 10, c) for r in range(5) for c in range(10)]
    foes = [(r + 15, c) for r in range(3) for c in range(10)]
    ants = FakeAnts(own, foods, foes)
    start = time.perf_counter()
    EB.Example().do_turn(ants)
    assert time.perf_counter() - start < TURN_BUDGET
    assert len(ants.orders) <= len(own)
