#!/usr/bin/env python
"""Militia threat-proportional draft tests. No engine games.

One change over champion Denial: each threatened home hill drafts a
number of nearest ants equal to its raider count (1-for-1 plus 1)
BEFORE food assignment, instead of the champion's fixed guard rule.
Unthreatened hills draft nothing.
"""

import os
import sys
import time
from collections.abc import Callable
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Militia  # noqa: E402

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]
ROWS = 20
COLS = 20


def torus(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


def test_three_raiders_draft_four_nearest() -> None:
    hill: Loc = (10, 10)
    ants = [(10, 11), (11, 10), (10, 9), (9, 10), (0, 0), (0, 1)]
    raiders = [(10, 12), (12, 10), (10, 8)]
    militia, posting = Militia.draft_militia(ants, {hill: raiders}, torus)
    assert militia == {0, 1, 2, 3}
    assert set(posting) == militia
    assert set(posting.values()) == {hill}


def test_unthreatened_hills_draft_zero() -> None:
    hill: Loc = (5, 5)
    ants = [(5, 6), (5, 4), (0, 0)]
    # No threat map at all: nothing drafted.
    militia, posting = Militia.draft_militia(ants, {}, torus)
    assert militia == set()
    assert posting == {}
    # A hill with no raiders in range is not threatened either.
    assert Militia.hill_raiders(hill, [(19, 19)], torus) == []
    assert Militia.hill_raiders(hill, [(5, 7)], torus) == [(5, 7)]


def test_single_raider_matches_champion_guard() -> None:
    # Champion's fixed guard rule answers one raider with two ants:
    # one holds the hill, one screens the razer. The proportional
    # draft (1-for-1 plus 1) drafts exactly those two nearest ants.
    hill: Loc = (10, 10)
    ants = [(10, 11), (11, 10), (0, 0), (0, 1)]
    militia, posting = Militia.draft_militia(ants, {hill: [(10, 12)]}, torus)
    assert militia == {0, 1}
    assert posting == {0: hill, 1: hill}


def test_draft_costs_under_1ms_crowded() -> None:
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(120)]
    hills = [(5, 5), (5, 15), (15, 5), (15, 15)]
    threat = {h: [(h[0], (h[1] + 1) % COLS) for _ in range(5)] for h in hills}
    for _ in range(3):
        start = time.perf_counter()
        militia, _ = Militia.draft_militia(ants, threat, torus)
        assert time.perf_counter() - start < 0.001
    assert len(militia) == 24


def test_militia_drafted_before_food() -> None:
    # The drafted ant sits on the food, yet the claim still goes to
    # the free forager: defenders are excluded pre-assignment.
    hill: Loc = (10, 10)
    ants = [(3, 3), (0, 10), (0, 0)]
    militia, _ = Militia.draft_militia(ants, {hill: [(10, 12)]}, torus)
    assert militia == {0, 1}
    foragers = [a for i, a in enumerate(ants) if i not in militia]
    assert foragers == [(0, 0)]
    sub = Militia.assign_food_targets(foragers, [(3, 3)], [], torus, ROWS, COLS)
    assert sub == {0: (3, 3)}


def test_closing_raiders_count_past_range_10() -> None:
    hill: Loc = (10, 10)
    # Distance 14: out of plain range, but closing counts to 16.
    assert Militia.hill_raiders(hill, [(4, 2)], torus) == []

    def closing(e: Loc, h: Loc) -> bool:
        return True

    assert Militia.hill_raiders(hill, [(4, 2)], torus, closing) == [(4, 2)]


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
        return []

    def my_hills(self) -> list[Loc]:
        return list(self._hills)

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
        return True

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 10000


def run_turn(
    ants: list[Loc], hills: list[Loc], foods: list[Loc], enemies: list[Loc]
) -> FakeAnts:
    bot = Militia.Militia()
    fake = FakeAnts(ants, hills, foods, enemies)
    bot.do_setup(cast(Any, fake))
    bot.do_turn(cast(Any, fake))
    return fake


def test_militia_guards_while_foragers_work() -> None:
    hill: Loc = (10, 10)
    ants = [(10, 11), (11, 10), (0, 0), (0, 1)]
    fake = run_turn(ants, [hill], [(0, 19)], [(10, 12)])
    moved = {loc for loc, _ in fake.orders}
    assert moved == set(ants)
    assert len(fake.orders) == 4


def test_no_threat_full_economy() -> None:
    hill: Loc = (10, 10)
    ants = [(10, 11), (11, 10), (0, 0), (0, 1)]
    fake = run_turn(ants, [hill], [(0, 19)], [])
    assert len(fake.orders) == 4
