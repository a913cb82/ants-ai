#!/usr/bin/env python
"""Sentry standing-guard tests. No engine games.

One change over champion Denial: every held home hill drafts exactly
2 spare ants as standing sentries BEFORE food assignment (not after,
not on threat). A threatened hill drafts nothing: its sentries are
released back to the economy while guards take over.
"""

import os
import sys
import time
from collections.abc import Callable
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Sentry  # noqa: E402

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


def test_each_hill_holds_two_sentries() -> None:
    hill: Loc = (5, 5)
    ants = [(5, 6), (5, 4), (6, 5), (4, 5), (0, 0)]
    sentries = Sentry.draft_sentries(ants, [hill], [], torus)
    assert sentries == {0, 1}


def test_two_hills_hold_two_each() -> None:
    a: Loc = (2, 2)
    b: Loc = (17, 17)
    ants = [(2, 3), (3, 2), (2, 1), (17, 16), (16, 17), (17, 18)]
    sentries = Sentry.draft_sentries(ants, [a, b], [], torus)
    assert len(sentries) == 4
    near_a = {i for i in sentries if torus(ants[i], a) <= torus(ants[i], b)}
    near_b = sentries - near_a
    assert len(near_a) == 2
    assert len(near_b) == 2


def test_threatened_hill_releases_its_sentries() -> None:
    a: Loc = (2, 2)
    b: Loc = (17, 17)
    ants = [(2, 3), (3, 2), (2, 1), (17, 16), (16, 17), (17, 18)]
    assert Sentry.draft_sentries(ants, [a, b], [b], torus) == {0, 1}
    assert Sentry.draft_sentries(ants, [a, b], [a, b], torus) == set()


def test_short_hills_keep_a_forager() -> None:
    hill: Loc = (5, 5)
    # Two ants: draft one, never both, so food is never starved.
    assert Sentry.draft_sentries([(5, 6), (5, 4)], [hill], [], torus) == {0}
    # One ant: no sentry at all.
    assert Sentry.draft_sentries([(5, 6)], [hill], [], torus) == set()
    # No ants: nothing to draft.
    assert Sentry.draft_sentries([], [hill], [], torus) == set()
    # Three ants over two hills: cap at N-1, one forager stays free.
    a: Loc = (2, 2)
    b: Loc = (17, 17)
    ants = [(2, 3), (17, 16), (0, 0)]
    sentries = Sentry.draft_sentries(ants, [a, b], [], torus)
    assert len(sentries) == 2
    assert len(ants) - len(sentries) >= 1


def test_foragers_still_claim_food() -> None:
    hill: Loc = (5, 5)
    ants = [(5, 6), (5, 4)]
    sentries = Sentry.draft_sentries(ants, [hill], [], torus)
    foragers = [a for i, a in enumerate(ants) if i not in sentries]
    assert len(foragers) == 1
    target = Sentry.assign_food_targets(foragers, [(0, 0)], [], torus, ROWS, COLS)
    assert len(target) == 1


def test_draft_costs_under_1ms_crowded() -> None:
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(120)]
    hills = [(5, 5), (5, 15), (15, 5), (15, 15)]
    for _ in range(3):
        start = time.perf_counter()
        sentries = Sentry.draft_sentries(ants, hills, [], torus)
        assert time.perf_counter() - start < 0.001
    assert len(sentries) == 8


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
    bot = Sentry.Sentry()
    fake = FakeAnts(ants, hills, foods, enemies)
    bot.do_setup(cast(Any, fake))
    bot.do_turn(cast(Any, fake))
    return fake


def test_sentries_hold_while_foragers_work() -> None:
    hill: Loc = (10, 10)
    ants = [(10, 11), (11, 10), (0, 0), (0, 1)]
    fake = run_turn(ants, [hill], [(0, 19)], [])
    moved = {loc for loc, _ in fake.orders}
    assert moved == {(0, 0), (0, 1)}
    assert len(fake.orders) == 2


def test_threat_releases_sentries_to_economy() -> None:
    hill: Loc = (10, 10)
    ants = [(10, 11), (11, 10), (0, 0), (0, 1)]
    fake = run_turn(ants, [hill], [(0, 19)], [(10, 12)])
    assert len(fake.orders) == 4
