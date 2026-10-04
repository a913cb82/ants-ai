#!/usr/bin/env python
"""Bailiff (pre-contact evacuation) tests.

No engine games.

One change over champion Denial: ants standing on squares adjacent
to 3+ enemies with no friendly ant adjacent evacuate FIRST (before
food assignment) toward the nearest friendly ant; all other ants
behave exactly as champion.
"""

import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Bailiff as BF  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}


def torus(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


class FakeAnts:
    """Minimal stand-in for ants.Ants covering do_turn's interface."""

    def __init__(
        self,
        mine: list[Loc],
        enemies: list[Loc],
        foods: list[Loc] | None = None,
        water: set[Loc] | None = None,
    ) -> None:
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = 5
        self._mine = list(mine)
        self._enemies = list(enemies)
        self._foods = list(foods or [])
        self._water = set(water or set())
        self.orders: list[tuple[Loc, str]] = []

    def food(self) -> list[Loc]:
        return list(self._foods)

    def my_ants(self) -> list[Loc]:
        return list(self._mine)

    def enemy_ants(self) -> list[tuple[Loc, int]]:
        return [(e, 1) for e in self._enemies]

    def enemy_hills(self) -> list[tuple[Loc, int]]:
        return []

    def my_hills(self) -> list[Loc]:
        return []

    def distance(self, a: Loc, b: Loc) -> int:
        dr = abs(a[0] - b[0])
        dr = min(dr, self.rows - dr)
        dc = abs(a[1] - b[1])
        dc = min(dc, self.cols - dc)
        return dr + dc

    def destination(self, loc: Loc, direction: str) -> Loc:
        dr, dc = AIM[direction]
        return ((loc[0] + dr) % self.rows, (loc[1] + dc) % self.cols)

    def passable(self, loc: Loc) -> bool:
        return loc not in self._water

    def unoccupied(self, loc: Loc) -> bool:
        return (
            loc not in self._water
            and loc not in self._mine
            and loc not in self._enemies
        )

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 100000


def _no_doom(*args: Any) -> list[int]:
    return []


def run_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    bailiff_on: bool = True,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, water)
    bot: Any = BF.Bailiff()
    if bailiff_on:
        bot.do_turn(fake)
        return fake.orders
    orig = BF.doomed_ant_indices
    BF.doomed_ant_indices = _no_doom
    try:
        bot.do_turn(fake)
    finally:
        BF.doomed_ant_indices = orig
    return fake.orders


def test_doomed_ant_evacuates_toward_nearest_friend() -> None:
    mine = [(10, 10), (10, 15)]
    enemies = [(9, 10), (11, 10), (10, 9)]
    assert BF.doomed_ant_indices(mine, enemies, ROWS, COLS) == [0]
    got = run_turn(mine, enemies)
    assert dict(got).get((10, 10)) == "e"
    assert torus((10, 11), (10, 15)) < torus((10, 10), (10, 15))


def test_friendly_adjacency_holds_as_champion() -> None:
    mine = [(10, 10), (10, 11)]
    enemies = [(9, 10), (11, 10), (10, 9)]
    assert BF.doomed_ant_indices(mine, enemies, ROWS, COLS) == []
    assert run_turn(mine, enemies) == run_turn(mine, enemies, bailiff_on=False)


def test_two_adjacent_enemies_are_not_doomed() -> None:
    mine = [(10, 10), (10, 15)]
    enemies = [(9, 10), (11, 10)]
    assert BF.doomed_ant_indices(mine, enemies, ROWS, COLS) == []
    assert run_turn(mine, enemies) == run_turn(mine, enemies, bailiff_on=False)


def test_lone_doomed_ant_falls_through_as_champion() -> None:
    mine = [(10, 10)]
    enemies = [(9, 10), (11, 10), (10, 9)]
    assert BF.doomed_ant_indices(mine, enemies, ROWS, COLS) == [0]
    assert run_turn(mine, enemies) == run_turn(mine, enemies, bailiff_on=False)


def test_detection_uses_torus_wrap() -> None:
    mine = [(0, 0)]
    enemies = [(ROWS - 1, 0), (0, COLS - 1), (1, 0)]
    assert BF.doomed_ant_indices(mine, enemies, ROWS, COLS) == [0]


def test_no_threat_turns_match_champion_exactly() -> None:
    import random

    rng = random.Random(37)
    locs = [(r, c) for r in range(ROWS) for c in range(COLS)]
    compared = 0
    for _ in range(200):
        n_ants = rng.randint(1, 6)
        n_food = rng.randint(0, 8)
        n_enemy = rng.randint(0, 5)
        pick = rng.sample(locs, n_ants + n_food + n_enemy)
        mine = pick[:n_ants]
        foods = pick[n_ants : n_ants + n_food]
        enemies = pick[n_ants + n_food :]
        if BF.doomed_ant_indices(mine, enemies, ROWS, COLS):
            continue
        assert run_turn(mine, enemies, foods) == run_turn(
            mine, enemies, foods, bailiff_on=False
        )
        compared += 1
    assert compared > 100


def test_evacuation_scan_costs_under_1ms() -> None:
    import random

    rng = random.Random(7)
    rows = cols = 100
    locs = [(r, c) for r in range(rows) for c in range(cols)]
    pick = rng.sample(locs, 1000)
    mine = pick[:500]
    enemies = pick[500:]
    start = time.perf_counter()
    reps = 50
    doomed: list[int] = []
    for _ in range(reps):
        doomed = BF.doomed_ant_indices(mine, enemies, rows, cols)
    elapsed = (time.perf_counter() - start) / reps
    assert isinstance(doomed, list)
    assert elapsed < 0.001
