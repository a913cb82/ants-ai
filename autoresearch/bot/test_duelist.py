#!/usr/bin/env python
"""Duelist trade-policy tests: hand-built layouts, no engine games.

Proves, on the Flood base, that 1-for-1 trades are refused by default
and allowed only when they buy something concrete: a blocked hill rush
(anthonyvh's 70% rule) or a hill-zone trade with backup arriving.
"""

import time

from ants import Ants
from Duelist import (
    BACKUP_STEPS,
    HILL_ATTACK_RADIUS,
    Duelist,
    blocked_rush,
    count_engagement,
    nearest_toroidal,
    trade_safe,
)

DIRS = ("n", "e", "s", "w")
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}


class FakeAnts(Ants):
    """Hand-built board stub: open land plus a chosen water set."""

    def __init__(
        self,
        rows: int,
        cols: int,
        my_ants: list[tuple[int, int]],
        enemies: list[tuple[int, int]],
        enemy_hills: list[tuple[int, int]],
        water: set[tuple[int, int]],
    ) -> None:
        super().__init__()
        self.rows = rows
        self.cols = cols
        self.attackradius2 = 5
        self._my = list(my_ants)
        self._enemies = list(enemies)
        self._hills = list(enemy_hills)
        self._water = set(water)
        self.orders: list[tuple[tuple[int, int], str]] = []

    def my_ants(self) -> list[tuple[int, int]]:
        return list(self._my)

    def enemy_ants(self) -> list[tuple[tuple[int, int], int]]:
        return [(loc, 1) for loc in self._enemies]

    def enemy_hills(self) -> list[tuple[tuple[int, int], int]]:
        return [(loc, 1) for loc in self._hills]

    def my_hills(self) -> list[tuple[int, int]]:
        return []

    def food(self) -> list[tuple[int, int]]:
        return []

    def visible(self, loc: tuple[int, int]) -> bool:
        return True

    def passable(self, loc: tuple[int, int]) -> bool:
        return loc not in self._water

    def unoccupied(self, loc: tuple[int, int]) -> bool:
        return loc not in self._my and loc not in self._enemies

    def destination(self, loc: tuple[int, int], direction: str) -> tuple[int, int]:
        dr, dc = AIM[direction]
        return ((loc[0] + dr) % self.rows, (loc[1] + dc) % self.cols)

    def distance(self, loc1: tuple[int, int], loc2: tuple[int, int]) -> int:
        d_col = min(abs(loc1[1] - loc2[1]), self.cols - abs(loc1[1] - loc2[1]))
        d_row = min(abs(loc1[0] - loc2[0]), self.rows - abs(loc1[0] - loc2[0]))
        return d_row + d_col

    def issue_order(self, order: tuple[tuple[int, int], str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 10000


def box(ants: list[tuple[int, int]], rows: int, cols: int) -> set[tuple[int, int]]:
    """Water ring around each ant so it cannot step anywhere."""
    water: set[tuple[int, int]] = set()
    for r, c in ants:
        for dr, dc in AIM.values():
            water.add(((r + dr) % rows, (c + dc) % cols))
    return water


def run(ants: FakeAnts) -> list[tuple[tuple[int, int], str]]:
    bot = Duelist()
    bot.do_setup(ants)
    bot.do_turn(ants)
    return ants.orders


def test_lone_1v1_refused() -> None:
    """A lone ant never walks into a 1-for-1: every exit is covered."""
    ants = FakeAnts(
        rows=20,
        cols=20,
        my_ants=[(10, 10)],
        enemies=[(10, 11)],
        enemy_hills=[],
        water=set(),
    )
    assert run(ants) == []
    assert trade_safe(0, 1, None, None, False) is False


def test_blocked_rush_1v1_accepted() -> None:
    """7 of 10 attackers boxed: the free ant trades into the march."""
    hill = (10, 20)
    boxed = [(24, 5), (24, 8), (24, 11), (24, 14), (24, 17), (24, 20), (24, 23)]
    ants = FakeAnts(
        rows=30,
        cols=30,
        my_ants=[(10, 14), (22, 5), (22, 8), *boxed],
        enemies=[(10, 16)],
        enemy_hills=[hill],
        water=box(boxed, 30, 30),
    )
    assert ((10, 14), "e") in run(ants)


def test_open_rush_1v1_refused() -> None:
    """Same fight, nobody stuck: the ant must not take the 1-for-1."""
    hill = (10, 20)
    boxed = [(24, 5), (24, 8), (24, 11), (24, 14), (24, 17), (24, 20), (24, 23)]
    ants = FakeAnts(
        rows=30,
        cols=30,
        my_ants=[(10, 14), (22, 5), (22, 8), *boxed],
        enemies=[(10, 16)],
        enemy_hills=[hill],
        water=set(),
    )
    assert ((10, 14), "e") not in run(ants)


def test_hill_zone_backup_1v1_accepted() -> None:
    """Open rush, but the trade is 5 from the hill with backup 4 away."""
    ants = FakeAnts(
        rows=30,
        cols=30,
        my_ants=[(10, 14), (10, 11)],
        enemies=[(10, 16)],
        enemy_hills=[(10, 20)],
        water=set(),
    )
    assert HILL_ATTACK_RADIUS >= 5 and BACKUP_STEPS >= 4
    assert ((10, 14), "e") in run(ants)


def test_hill_zone_no_backup_1v1_refused() -> None:
    """Same hill-zone trade with backup far away: refused."""
    ants = FakeAnts(
        rows=30,
        cols=30,
        my_ants=[(10, 14), (25, 25)],
        enemies=[(10, 16)],
        enemy_hills=[(10, 20)],
        water=set(),
    )
    assert ((10, 14), "e") not in run(ants)


def test_trade_gate_matrix() -> None:
    """Pure gate: strict wins always, equal only situational, never worse."""
    assert trade_safe(2, 1, None, None, False) is True
    assert trade_safe(0, 1, None, None, False) is False
    assert trade_safe(0, 1, 5, 3, False) is True
    assert trade_safe(0, 1, 5, 10, False) is False
    assert trade_safe(0, 1, 25, 2, False) is False
    assert trade_safe(0, 1, 25, 10, True) is True
    assert trade_safe(0, 2, 5, 3, True) is False


def test_blocked_rush_threshold() -> None:
    """anthonyvh's 70% rule: 7 of 10 unblocks, 6 of 10 does not."""
    assert blocked_rush(7, 10) is True
    assert blocked_rush(6, 10) is False
    assert blocked_rush(0, 0) is False


def test_decision_path_fast_on_crowded_board() -> None:
    """200 full trade decisions on a 120v120 board: avg under 5ms."""
    rows, cols = 40, 40
    my = [(r, c) for r in range(0, 40, 2) for c in range(0, 40, 4)][:120]
    foes = [(r, c) for r in range(1, 40, 2) for c in range(2, 40, 4)][:120]
    hills = [(0, 0), (39, 39)]
    attack_r2 = 5
    decisions: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for self_loc in my[:50]:
        for d in DIRS:
            dr, dc = AIM[d]
            decisions.append(
                (((self_loc[0] + dr) % rows, (self_loc[1] + dc) % cols), self_loc)
            )
    start = time.perf_counter()
    for nloc, self_loc in decisions:
        friends, enemies = count_engagement(
            nloc, self_loc, my, foes, attack_r2, rows, cols
        )
        hill_dist = nearest_toroidal(nloc, hills, rows, cols)
        backup_dist = nearest_toroidal(nloc, my, rows, cols, skip=self_loc)
        trade_safe(friends, enemies, hill_dist, backup_dist, False)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"{len(decisions)} decisions took {elapsed:.3f}s"
