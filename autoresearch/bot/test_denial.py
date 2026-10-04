#!/usr/bin/env python
"""Food denial tests: hold a contested food field.

When 3+ visible enemies contest the same food cluster (foods within
radius 8 of each other), the bot assigns TWO ants to the two closest
foods of that cluster instead of one ant per food. Everywhere else
the champion's one-ant-per-food greedy is untouched.

Layouts are hand-built; no engine games.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ants import Ants  # noqa: E402
from Denial import (  # noqa: E402
    CLUSTER_R,
    DENIAL_ENEMIES,
    Denial,
    assign_food_targets,
    denied_food_groups,
)

Loc = tuple[int, int]
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}


def make_dist(rows: int, cols: int):  # type: ignore[no-untyped-def]
    def dist(a: Loc, b: Loc) -> int:
        return min(abs(a[0] - b[0]), rows - abs(a[0] - b[0])) + min(
            abs(a[1] - b[1]), cols - abs(a[1] - b[1])
        )

    return dist


def flood_greedy(
    ants_list: list[Loc], foods: list[Loc], dist: object
) -> dict[int, Loc]:
    """Champion's one-ant-per-food greedy, the behavior denial must keep."""
    from collections.abc import Callable

    d: Callable[[Loc, Loc], int] = dist  # type: ignore[assignment]
    pairs = sorted(
        (d(a, f), ai, fi)
        for ai, a in enumerate(ants_list)
        for fi, f in enumerate(foods)
    )
    target: dict[int, Loc] = {}
    claimed: set[int] = set()
    for _, ai, fi in pairs:
        if ai not in target and fi not in claimed:
            target[ai] = foods[fi]
            claimed.add(fi)
    return target


class FakeAnts(Ants):
    """Minimal board stub for end-to-end turn tests."""

    def __init__(
        self,
        rows: int,
        cols: int,
        my_ants: list[Loc],
        enemies: list[Loc],
        foods: list[Loc],
    ) -> None:
        super().__init__()
        self.rows = rows
        self.cols = cols
        self.attackradius2 = 5
        self._my = list(my_ants)
        self._enemies = list(enemies)
        self._foods = list(foods)
        self.orders: list[tuple[Loc, str]] = []

    def my_ants(self) -> list[Loc]:
        return list(self._my)

    def enemy_ants(self) -> list[tuple[Loc, int]]:
        return [(loc, 1) for loc in self._enemies]

    def enemy_hills(self) -> list[tuple[Loc, int]]:
        return []

    def my_hills(self) -> list[Loc]:
        return [(0, 0)]

    def food(self) -> list[Loc]:
        return list(self._foods)

    def passable(self, loc: Loc) -> bool:
        return True

    def unoccupied(self, loc: Loc) -> bool:
        return loc not in self._my and loc not in self._enemies

    def destination(self, loc: Loc, direction: str) -> Loc:
        dr, dc = AIM[direction]
        return ((loc[0] + dr) % self.rows, (loc[1] + dc) % self.cols)

    def distance(self, loc1: Loc, loc2: Loc) -> int:
        d_col = min(abs(loc1[1] - loc2[1]), self.cols - abs(loc1[1] - loc2[1]))
        d_row = min(abs(loc1[0] - loc2[0]), self.rows - abs(loc1[0] - loc2[0]))
        return d_row + d_col

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 10000


def contested_layout() -> tuple[list[Loc], list[Loc], list[Loc]]:
    """One 3-food cluster, three enemies on it, two near ants, two far ants."""
    foods = [(5, 5), (5, 6), (5, 7)]
    enemies = [(5, 10), (6, 10), (7, 10)]
    ants_list = [(0, 5), (0, 6), (29, 29), (29, 28)]
    return ants_list, foods, enemies


def test_contested_cluster_draws_exactly_two_claimants() -> None:
    """3 enemies on the cluster: exactly 2 ants on the 2 closest foods."""
    ants_list, foods, enemies = contested_layout()
    dist = make_dist(30, 30)
    groups = denied_food_groups(foods, enemies, dist, 30, 30)
    assert len(groups) == 1
    assert sorted(groups[0]) == [0, 1, 2]
    target = assign_food_targets(ants_list, foods, enemies, dist, 30, 30)
    assert len(target) == DENIAL_ENEMIES - 1  # exactly two denial ants
    assert set(target.values()) == {(5, 5), (5, 6)}
    assert len(set(target.keys())) == 2
    # The third cluster food stays unclaimed even with idle ants left.
    assert (5, 7) not in target.values()


def test_two_enemy_cluster_draws_one() -> None:
    """2 enemies: no denial, the champion greedy claims every food."""
    ants_list, foods, _ = contested_layout()
    enemies = [(5, 10), (6, 10)]
    dist = make_dist(30, 30)
    assert denied_food_groups(foods, enemies, dist, 30, 30) == []
    target = assign_food_targets(ants_list, foods, enemies, dist, 30, 30)
    assert len(target) == 3
    assert set(target.values()) == set(foods)


def test_uncontested_keeps_one_ant_per_food() -> None:
    """Spread foods, no enemies: assignment equals the champion greedy."""
    ants_list = [(2, 3), (2, 19), (19, 2), (21, 20)]
    foods = [(2, 2), (2, 20), (20, 2), (20, 20)]
    dist = make_dist(30, 30)
    assert denied_food_groups(foods, [], dist, 30, 30) == []
    target = assign_food_targets(ants_list, foods, [], dist, 30, 30)
    assert target == flood_greedy(ants_list, foods, dist)
    assert sorted(target.values()) == sorted(foods)


def test_cluster_scan_under_2ms_on_crowded_board() -> None:
    """60 foods + 60 enemies on 40x40: median scan stays under 2 ms."""
    rows, cols = 40, 40
    foods = [((i * 7) % rows, (i * 13) % cols) for i in range(60)]
    enemies = [((i * 11 + 3) % rows, (i * 17 + 5) % cols) for i in range(60)]
    dist = make_dist(rows, cols)
    elapsed = []
    for _ in range(7):
        start = time.perf_counter()
        denied_food_groups(foods, enemies, dist, rows, cols)
        elapsed.append(time.perf_counter() - start)
    median = sorted(elapsed)[3]
    assert median < 0.002, f"cluster scan median took {median * 1000:.2f} ms"


def test_denial_end_to_end_uncontested() -> None:
    """Two ants beside two foods: both walk, one ant per food."""
    ants = FakeAnts(
        rows=30, cols=30, my_ants=[(5, 5), (8, 8)], enemies=[], foods=[(5, 6), (8, 9)]
    )
    bot = Denial()
    bot.do_setup(ants)
    bot.do_turn(ants)
    assert ants.orders == [((5, 5), "e"), ((8, 8), "e")]


def test_denial_turn_completes_on_contested_cluster() -> None:
    """Contested turn runs to completion and sends ants at the cluster."""
    ants_list, foods, enemies = contested_layout()
    ants = FakeAnts(rows=30, cols=30, my_ants=ants_list, enemies=enemies, foods=foods)
    bot = Denial()
    bot.do_setup(ants)
    bot.do_turn(ants)
    assert isinstance(ants.orders, list)
    assert len(ants.orders) >= 2
    assert CLUSTER_R == 8
