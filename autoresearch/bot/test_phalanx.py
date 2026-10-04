#!/usr/bin/env python
"""Phalanx (adjacent double-team) tests.

No engine games.

One change over champion Denial: when 2+ friendly ants stand
adjacent (toroid-manhattan distance 1) to the same enemy, the
engaging ant fights on as champion while an already-adjacent
friend mirrors it -- stepping toward the square opposite the
engager across that enemy when the square is free (holding still
when already opposite) -- instead of continuing economy. Solo
contact and no-contact turns behave exactly as champion.
"""

import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Phalanx as PH  # noqa: E402

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


def _no_phalanx(*args: Any, **kwargs: Any) -> dict[Loc, Loc]:
    return {}


def run_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    phalanx_on: bool = True,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, water)
    bot: Any = PH.Phalanx()
    if phalanx_on:
        bot.do_turn(fake)
        return fake.orders
    orig = PH.phalanx_mirrors
    PH.phalanx_mirrors = _no_phalanx
    try:
        bot.do_turn(fake)
    finally:
        PH.phalanx_mirrors = orig
    return fake.orders


def test_adjacent_friend_double_teams_opposite_enemy() -> None:
    # A=(10,9) west of E, B=(9,10) north of E. Engager is min-coords
    # B, so opposite is south (11,10); A must step toward it.
    mine = [(10, 9), (9, 10)]
    enemies = [(10, 10)]
    assert PH.phalanx_mirrors(mine, enemies, ROWS, COLS) == {(10, 9): (11, 10)}
    on = run_turn(mine, enemies, [(0, 0)])
    off = run_turn(mine, enemies, [(0, 0)], phalanx_on=False)
    assert dict(on).get((10, 9)) == "s"
    assert torus((11, 9), (11, 10)) < torus((10, 9), (11, 10))
    assert on != off  # champion would not mirror
    assert dict(on).get((9, 10)) == dict(off).get((9, 10))  # engager untouched


def test_friend_already_opposite_holds() -> None:
    # A=(10,9) west of E engages; B=(10,11) already sits opposite.
    mine = [(10, 9), (10, 11)]
    enemies = [(10, 10)]
    assert PH.phalanx_mirrors(mine, enemies, ROWS, COLS) == {(10, 11): (10, 11)}
    on = run_turn(mine, enemies, [(0, 0)])
    off = run_turn(mine, enemies, [(0, 0)], phalanx_on=False)
    assert (10, 11) not in dict(on)  # holds the 2-on-1
    assert (10, 11) in dict(off)  # champion walks it off to economy


def test_solo_contact_matches_champion() -> None:
    # One ant adjacent to the enemy, no adjacent friend: champion.
    mine = [(10, 9)]
    enemies = [(10, 10)]
    assert PH.phalanx_mirrors(mine, enemies, ROWS, COLS) == {}
    assert run_turn(mine, enemies, [(0, 0)]) == run_turn(
        mine, enemies, [(0, 0)], phalanx_on=False
    )


def test_blocked_opposite_falls_through_as_champion() -> None:
    # Opposite square (11,10) is water: no mirror, champion economy.
    mine = [(10, 9), (9, 10)]
    enemies = [(10, 10)]
    water = {(11, 10)}
    assert PH.phalanx_mirrors(mine, enemies, ROWS, COLS) == {(10, 9): (11, 10)}
    assert run_turn(mine, enemies, [(0, 0)], water) == run_turn(
        mine, enemies, [(0, 0)], water, phalanx_on=False
    )


def test_detection_uses_torus_wrap() -> None:
    mine = [(ROWS - 1, 0), (0, COLS - 1)]
    enemies = [(0, 0)]
    assert PH.phalanx_mirrors(mine, enemies, ROWS, COLS) == {(19, 0): (0, 1)}


def test_quiet_turns_match_champion_exactly() -> None:
    import random

    rng = random.Random(38)
    locs = [(r, c) for r in range(ROWS) for c in range(COLS)]
    compared = 0
    for _ in range(300):
        n_ants = rng.randint(1, 6)
        n_food = rng.randint(0, 8)
        n_enemy = rng.randint(0, 5)
        pick = rng.sample(locs, n_ants + n_food + n_enemy)
        mine = pick[:n_ants]
        foods = pick[n_ants : n_ants + n_food]
        enemies = pick[n_ants + n_food :]
        if PH.phalanx_mirrors(mine, enemies, ROWS, COLS):
            continue
        assert run_turn(mine, enemies, foods) == run_turn(
            mine, enemies, foods, phalanx_on=False
        )
        compared += 1
    assert compared > 100


def test_adjacency_scan_costs_under_1ms() -> None:
    import random

    rng = random.Random(7)
    rows = cols = 100
    locs = [(r, c) for r in range(rows) for c in range(cols)]
    pick = rng.sample(locs, 1000)
    mine = pick[:500]
    enemies = pick[500:]
    start = time.perf_counter()
    reps = 50
    mirrors: dict[Loc, Loc] = {}
    for _ in range(reps):
        mirrors = PH.phalanx_mirrors(mine, enemies, rows, cols)
    elapsed = (time.perf_counter() - start) / reps
    assert isinstance(mirrors, dict)
    assert elapsed < 0.001
