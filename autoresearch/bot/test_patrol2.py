#!/usr/bin/env python
"""Patrol-2 enemy-hill patrol tests. No engine games.

One change over champion Denial: past turn 400, idle exploration
ants walk PAST the nearest uncontrolled enemy hill (touch the hill
square, then resume explore) instead of sitting on it or ignoring
it. Pre-400 orders are byte-identical to the champion; food, guard,
and hill-muster ants are unaffected at any turn.
"""

import os
import sys
import time
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Patrol2  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20


def torus(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


class FakeAnts:
    def __init__(
        self,
        ants: list[Loc],
        hills: list[Loc],
        foods: list[Loc],
        enemies: list[Loc] | None = None,
    ) -> None:
        self._ants = list(ants)
        self._hills = list(hills)
        self._foods = list(foods)
        self._enemies = list(enemies or [])
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = 5
        self.orders: list[tuple[Loc, str]] = []

    def food(self) -> list[Loc]:
        return list(self._foods)

    def my_ants(self) -> list[Loc]:
        return list(self._ants)

    def enemy_ants(self) -> list[tuple[Loc, int]]:
        return [(e, 1) for e in self._enemies]

    def enemy_hills(self) -> list[tuple[Loc, int]]:
        return [(h, 1) for h in self._hills]

    def my_hills(self) -> list[Loc]:
        return []

    def distance(self, a: Loc, b: Loc) -> int:
        return torus(a, b)

    def destination(self, loc: Loc, direction: str) -> Loc:
        r, c = loc
        if direction == "n":
            return ((r - 1) % ROWS, c)
        if direction == "s":
            return ((r + 1) % ROWS, c)
        if direction == "e":
            return (r, (c + 1) % COLS)
        return (r, (c - 1) % COLS)

    def passable(self, loc: Loc) -> bool:
        assert 0 <= loc[0] < ROWS and 0 <= loc[1] < COLS
        return True

    def unoccupied(self, loc: Loc) -> bool:
        assert 0 <= loc[0] < ROWS and 0 <= loc[1] < COLS
        return loc not in self._ants and loc not in self._enemies

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 10000


def run_turn_at(
    ants: list[Loc],
    hills: list[Loc],
    foods: list[Loc],
    enemies: list[Loc],
    turn: int,
    visits: dict[Loc, int] | None = None,
) -> FakeAnts:
    bot = Patrol2.Patrol2()
    fake = FakeAnts(ants, hills, foods, enemies)
    bot.do_setup(cast(Any, fake))
    bot.turn = turn - 1
    if visits is not None:
        bot.visits = dict(visits)
    bot.do_turn(cast(Any, fake))
    assert bot.turn == turn
    return fake


def test_patrol_gate_only_past_400() -> None:
    assert Patrol2.patrol_after(1) is False
    assert Patrol2.patrol_after(100) is False
    assert Patrol2.patrol_after(400) is False
    assert Patrol2.patrol_after(401) is True
    assert Patrol2.patrol_after(600) is True


def test_pre400_orders_identical_turn1_and_turn400() -> None:
    # Byte-identical gating: same board, turn 1 and turn 400 agree.
    ant: Loc = (10, 10)
    hill: Loc = (10, 15)
    early = run_turn_at([ant], [hill], [], [], 1)
    late = run_turn_at([ant], [hill], [], [], 400)
    assert early.orders == late.orders == [(ant, "e")]


def test_post400_idle_ant_walks_through_danger_to_hill() -> None:
    # The lurker makes every safe step fail, so the champion sits
    # (no orders). Post-400 the idle ant fearlessly steps toward
    # the hill instead of sitting on its square.
    ant: Loc = (10, 10)
    hill: Loc = (10, 13)
    lurker: Loc = (9, 11)
    pre = run_turn_at([ant], [hill], [], [lurker], 400)
    assert pre.orders == []
    post = run_turn_at([ant], [hill], [], [lurker], 401)
    assert post.orders == [(ant, "e")]
    assert torus((10, 11), hill) < torus(ant, hill)


def test_post400_on_hill_steps_off_continues() -> None:
    # Touch and continue: an ant standing ON the single hill must
    # step off to its least-visited neighbor, never sit -- at both
    # turns identically.
    hill: Loc = (10, 15)
    visits = {(9, 15): 0, (10, 16): 5, (11, 15): 5, (10, 14): 5}
    pre = run_turn_at([hill], [hill], [], [], 400, visits)
    post = run_turn_at([hill], [hill], [], [], 500, visits)
    assert pre.orders == post.orders == [(hill, "n")]


def test_sitters_and_hunters_unaffected() -> None:
    # Food sitter works its adjacent food identically either side
    # of the gate.
    ant: Loc = (10, 10)
    pre_food = run_turn_at([ant], [(0, 0)], [(10, 11)], [], 200)
    post_food = run_turn_at([ant], [(0, 0)], [(10, 11)], [], 600)
    assert pre_food.orders == post_food.orders == [(ant, "e")]
    # Hunter musters on the nearby hill identically either side.
    pre_hunt = run_turn_at([ant], [(10, 12)], [], [], 200)
    post_hunt = run_turn_at([ant], [(10, 12)], [], [], 600)
    assert pre_hunt.orders == post_hunt.orders == [(ant, "e")]


def test_patrol_routing_costs_under_2ms_crowded() -> None:
    # Times the real patrol helper over a crowded board with plain
    # board functions (no assert-laden fakes in the hot path).
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(150)]
    occupied = set(ants)
    hill: Loc = (10, 15)

    def dest(loc: Loc, direction: str) -> Loc:
        r, c = loc
        if direction == "n":
            return ((r - 1) % ROWS, c)
        if direction == "s":
            return ((r + 1) % ROWS, c)
        if direction == "e":
            return (r, (c + 1) % COLS)
        return (r, (c - 1) % COLS)

    taken: set[Loc] = set()
    for _ in range(3):
        start = time.perf_counter()
        for ant in ants:
            Patrol2.patrol_step_toward(
                ant,
                hill,
                {},
                torus,
                dest,
                lambda loc: True,
                lambda loc: loc not in occupied,
                taken,
            )
        assert time.perf_counter() - start < 0.002
