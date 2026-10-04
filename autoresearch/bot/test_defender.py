#!/usr/bin/env python
"""Defender proportional-guard tests: hand-built layouts, no engine games.

Proves, on the Flood base, that hill defense scales with the raid:
1 guard per 2 raiders (rounded up), free ants march first, gatherers
are drafted only up to a third of their number, and the muster home
front calls for help at 20 steps while the old closing rule stays
silent.
"""

from ants import Ants
from Duelist import (
    Duelist,
    assign_guards,
    guards_needed,
    hill_threatened,
    hill_threatened_old,
    max_gatherer_draft,
)

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
        my_hills: list[tuple[int, int]],
        foods: list[tuple[int, int]],
        water: set[tuple[int, int]] | None = None,
    ) -> None:
        super().__init__()
        self.rows = rows
        self.cols = cols
        self.attackradius2 = 5
        self._my = list(my_ants)
        self._enemies = list(enemies)
        self._hills = list(enemy_hills)
        self._home = list(my_hills)
        self._food = list(foods)
        self._water = set(water or set())
        self.orders: list[tuple[tuple[int, int], str]] = []

    def my_ants(self) -> list[tuple[int, int]]:
        return list(self._my)

    def enemy_ants(self) -> list[tuple[tuple[int, int], int]]:
        return [(loc, 1) for loc in self._enemies]

    def enemy_hills(self) -> list[tuple[tuple[int, int], int]]:
        return [(loc, 1) for loc in self._hills]

    def my_hills(self) -> list[tuple[int, int]]:
        return list(self._home)

    def food(self) -> list[tuple[int, int]]:
        return list(self._food)

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


def run(ants: FakeAnts, prev: list[tuple[int, int]] | None = None) -> FakeAnts:
    bot = Duelist()
    bot.do_setup(ants)
    if prev is not None:
        bot.prev_enemies = list(prev)
    bot.do_turn(ants)
    return ants


def test_probe_draws_exactly_one_guard() -> None:
    """A 1-raider probe draws exactly 1 guard; the other ant musters.

    The second ant sits inside screen range, so the old code marches
    it west too; the quota holds it on the muster instead.
    """
    ants = run(
        FakeAnts(
            rows=30,
            cols=60,
            my_ants=[(10, 20), (10, 14)],
            enemies=[(10, 4)],
            enemy_hills=[(10, 29)],
            my_hills=[(10, 10)],
            foods=[],
        )
    )
    assert ants.orders == [((10, 20), "w"), ((10, 14), "n")]
    assert ((10, 14), "w") not in ants.orders


def test_pack_of_six_draws_three_not_six() -> None:
    """A 6-raider pack draws 3 guards; the fourth ant musters on.

    Raiders sit east of the hill, inside BFS reach of the guards, so
    every drafted guard has a path and the quota is the only cap.
    """
    raiders = [(10, 16), (10, 17), (9, 16), (11, 16), (10, 18), (8, 14)]
    ants = run(
        FakeAnts(
            rows=30,
            cols=60,
            my_ants=[(10, 21), (10, 23), (10, 25), (10, 27)],
            enemies=raiders,
            enemy_hills=[(10, 29)],
            my_hills=[(10, 10)],
            foods=[],
        )
    )
    assert ants.orders == [
        ((10, 21), "w"),
        ((10, 23), "w"),
        ((10, 25), "w"),
        ((10, 27), "e"),
    ]


def test_gatherer_draft_never_exceeds_a_third() -> None:
    """6 raiders want 3 guards; the 1 free ant plus at most 1 of the 3
    gatherers march, so 2 gatherers stay on their food."""
    raiders = [(10, 16), (10, 17), (9, 16), (11, 16), (10, 18), (8, 14)]
    ants = run(
        FakeAnts(
            rows=30,
            cols=30,
            my_ants=[(10, 20), (12, 20), (12, 22), (12, 24)],
            enemies=raiders,
            enemy_hills=[(10, 29)],
            my_hills=[(10, 10)],
            foods=[(13, 20), (13, 22), (13, 24)],
        )
    )
    assert len(ants.orders) == 4
    assert ((10, 20), "w") in ants.orders
    food_orders = [o for o in ants.orders if o[1] == "s"]
    assert len(food_orders) == 2
    assert len(ants.orders) - len(food_orders) == 2


def test_early_call_fires_while_old_rule_silent() -> None:
    """A raider retreating at distance 12 is past the old rule (too far
    and not closing) but inside the 20-step early call, so a guard
    still marches."""
    assert hill_threatened_old(12, False) is False
    assert hill_threatened(12, False, True) is True
    ants = run(
        FakeAnts(
            rows=30,
            cols=30,
            my_ants=[(10, 4), (12, 4)],
            enemies=[(10, 22)],
            enemy_hills=[(25, 25)],
            my_hills=[(10, 10)],
            foods=[],
        ),
        prev=[(10, 12)],
    )
    assert len(ants.orders) == 2
    assert ((10, 4), "e") in ants.orders


def test_guard_scale_matrix() -> None:
    """1 guard per 2 raiders, rounded up."""
    assert guards_needed(1) == 1
    assert guards_needed(2) == 1
    assert guards_needed(3) == 2
    assert guards_needed(6) == 3
    assert guards_needed(10) == 5


def test_draft_cap_matrix() -> None:
    """Never more than a third of the gatherers."""
    assert max_gatherer_draft(0) == 0
    assert max_gatherer_draft(2) == 0
    assert max_gatherer_draft(5) == 1
    assert max_gatherer_draft(6) == 2
    assert max_gatherer_draft(9) == 3


def test_assign_guards_matrix() -> None:
    """Free ants first, gatherers only up to the cap."""
    assert assign_guards([0, 1, 2, 3], [], [1], 0) == {0: 0}
    assert assign_guards(list(range(8)), [], [3], 0) == {0: 0, 1: 0, 2: 0}
    got = assign_guards([0, 1], [2, 3, 4, 5, 6, 7], [5], 2)
    assert got == {0: 0, 1: 0, 2: 0, 3: 0}
    assert assign_guards([0], [1, 2, 3], [4], 1) == {0: 0, 1: 0}


def test_threat_matrix() -> None:
    """Old radii unchanged; the early call adds only 17-20 with muster."""
    assert hill_threatened_old(10, False) is True
    assert hill_threatened_old(11, False) is False
    assert hill_threatened_old(16, True) is True
    assert hill_threatened_old(17, True) is False
    assert hill_threatened(20, False, True) is True
    assert hill_threatened(21, False, True) is False
    assert hill_threatened(20, False, False) is False
    assert hill_threatened(9, False, True) is True
