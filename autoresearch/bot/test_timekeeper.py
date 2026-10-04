#!/usr/bin/env python
"""Timekeeper (turn-time governor) tests. No engine games.

One change over champion Denial: each turn records the wall-clock
start, and once 80% of the turn budget has elapsed the remaining
explore-diffusion orders are skipped -- food, defense, and hill
orders still issue. With time to spare the orders match Denial
exactly.
"""

import os
import sys
import time
from typing import Any, cast

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Timekeeper as TK  # noqa: E402

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
        homes: list[Loc] | None = None,
    ) -> None:
        self._ants = list(ants)
        self._hills = list(hills)
        self._foods = list(foods)
        self._enemies = list(enemies or [])
        self._homes = list(homes if homes is not None else [(0, 0)])
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = 5
        self.turntime = 1000
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
        return list(self._homes)

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


def run_turn(
    ants: list[Loc],
    hills: list[Loc],
    foods: list[Loc],
    enemies: list[Loc] | None = None,
    homes: list[Loc] | None = None,
) -> FakeAnts:
    bot = TK.Timekeeper()
    fake = FakeAnts(ants, hills, foods, enemies, homes)
    bot.do_setup(cast(Any, fake))
    bot.do_turn(cast(Any, fake))
    return fake


def force_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    # First perf_counter call (turn start) reads T0; every later
    # call reads T0 + 10s, so a 1000ms budget is 1000% spent from
    # the first order decision on.
    t0 = 1000.0
    calls = {"n": 0}

    def clock() -> float:
        calls["n"] += 1
        return t0 if calls["n"] == 1 else t0 + 10.0

    monkeypatch.setattr(TK.time, "perf_counter", clock)


RICH_ANTS = [(5, 5), (1, 1), (15, 15), (15, 16)]
RICH_HILLS = [(10, 10)]
RICH_FOODS = [(5, 6)]
RICH_ENEMIES = [(0, 9)]
RICH_HOME = [(0, 0)]
# Champion reference orders, captured from Denial on this board:
# food step east, hill-guard step north, two defense screens.
RICH_ORDERS = [((5, 5), "e"), ((1, 1), "n"), ((15, 15), "s"), ((15, 16), "n")]

EXPLORE_ANTS = [(15, 15), (15, 16), (3, 3)]
EXPLORE_ORDERS = [((15, 15), "n"), ((15, 16), "n"), ((3, 3), "n")]

MIXED_ANTS = [(5, 5), (15, 15), (15, 16)]
MIXED_FOODS = [(5, 6)]
MIXED_ORDERS = [((5, 5), "e"), ((15, 15), "n"), ((15, 16), "n")]

DEF_ANTS = [(5, 5), (1, 1)]
DEF_ORDERS = [((5, 5), "e"), ((1, 1), "n")]

MUSTER_ANTS = [(15, 15)]
MUSTER_HILLS = [(10, 10)]
MUSTER_ORDERS = [((15, 15), "n")]

ALLFED_ANTS = [(5, 5), (5, 8), (12, 12)]
ALLFED_FOODS = [(5, 6), (5, 7)]
ALLFED_ORDERS = [((5, 5), "e"), ((5, 8), "w"), ((12, 12), "n")]


def test_plentiful_turn_matches_champion_byte_for_byte() -> None:
    # Rich turn (food + guard + screens) and pure-explore turn:
    # with time to spare every order matches Denial exactly.
    fake = run_turn(RICH_ANTS, RICH_HILLS, RICH_FOODS, RICH_ENEMIES, RICH_HOME)
    assert fake.orders == RICH_ORDERS
    fake = run_turn(EXPLORE_ANTS, [], [], [], RICH_HOME)
    assert fake.orders == EXPLORE_ORDERS


def test_plentiful_turn_is_repeatable() -> None:
    # The wall clock never trips the governor on a fast turn, so
    # two identical turns issue identical orders.
    first = run_turn(RICH_ANTS, RICH_HILLS, RICH_FOODS, RICH_ENEMIES, RICH_HOME)
    second = run_turn(RICH_ANTS, RICH_HILLS, RICH_FOODS, RICH_ENEMIES, RICH_HOME)
    assert first.orders == second.orders == RICH_ORDERS


def test_timeout_drops_only_explore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Food ant keeps its exact plentiful order; both explore ants
    # lose theirs -- the governor drops explore, nothing else.
    plentiful = run_turn(MIXED_ANTS, [], MIXED_FOODS, [], RICH_HOME)
    assert plentiful.orders == MIXED_ORDERS
    force_timeout(monkeypatch)
    starved = run_turn(MIXED_ANTS, [], MIXED_FOODS, [], RICH_HOME)
    assert starved.orders == [((5, 5), "e")]


def test_timeout_empties_pure_explore_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No food, no hills, no threat: every order is explore
    # diffusion, so a starved turn issues nothing at all.
    force_timeout(monkeypatch)
    fake = run_turn(EXPLORE_ANTS, [], [], [], RICH_HOME)
    assert fake.orders == []


def test_governor_never_drops_food_defense_or_muster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Turns with no explore in them are identical with and
    # without time pressure: food, guard, and muster all survive.
    assert (
        run_turn(DEF_ANTS, [], MIXED_FOODS, RICH_ENEMIES, RICH_HOME).orders
        == DEF_ORDERS
    )
    assert run_turn(MUSTER_ANTS, MUSTER_HILLS, [], [], RICH_HOME).orders == (
        MUSTER_ORDERS
    )
    assert run_turn(ALLFED_ANTS, MUSTER_HILLS, ALLFED_FOODS, [], RICH_HOME).orders == (
        ALLFED_ORDERS
    )
    force_timeout(monkeypatch)
    assert run_turn(DEF_ANTS, [], MIXED_FOODS, RICH_ENEMIES, RICH_HOME).orders == (
        DEF_ORDERS
    )
    assert run_turn(MUSTER_ANTS, MUSTER_HILLS, [], [], RICH_HOME).orders == (
        MUSTER_ORDERS
    )
    assert run_turn(ALLFED_ANTS, MUSTER_HILLS, ALLFED_FOODS, [], RICH_HOME).orders == (
        ALLFED_ORDERS
    )


def test_explore_allowed_threshold() -> None:
    # 80% of a 1000ms budget is 0.8s: clearly under means go,
    # clearly over means skip; a missing budget never skips.
    assert TK.explore_allowed(100.0, 1000, 100.79) is True
    assert TK.explore_allowed(100.0, 1000, 100.81) is False
    assert TK.explore_allowed(100.0, 1000, 150.0) is False
    assert TK.explore_allowed(100.0, 0, 9999.0) is True


def test_clock_check_costs_under_0_1ms() -> None:
    # The per-ant governor check (wall clock read plus compare)
    # must stay far under 0.1ms on average.
    start = time.perf_counter()
    n = 2000
    for _ in range(n):
        assert TK.time_for_explore(start, 1000) is True
    assert (time.perf_counter() - start) / n < 0.0001
