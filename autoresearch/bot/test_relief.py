#!/usr/bin/env python
"""Relief (fearless reinforcement) tests. No engine games.

The one change over champion Denial: when a threatened home hill
has 2+ raiders inside its threat radius, ALL ants within 15 steps
abandon food and reinforce (no gatherer exception). A 1-raider
probe leaves gatherers on food, ants beyond 15 stay on task, and
the muster march runs untouched while reinforcing.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Relief import (  # noqa: E402
    FEARLESS_RADIUS,
    FEARLESS_RAIDERS,
    Relief,
    assign_food_targets,
    fearless_hills,
    needs_reinforcement,
)

Loc = tuple[int, int]


class FakeAnts:
    """Minimal engine double. Mirrors ants.py semantics (torus grid,
    water blocks, food squares count as occupied)."""

    def __init__(
        self,
        rows: int,
        cols: int,
        my_ants: list[Loc],
        foods: list[Loc],
        water: set[Loc] = frozenset(),  # type: ignore[assignment]
        my_hills: list[Loc] | None = None,
        enemies: list[Loc] | None = None,
        attackradius2: int = 5,
    ):
        self.rows = rows
        self.cols = cols
        self._ants = list(my_ants)
        self._foods = list(foods)
        self._water = set(water)
        self._hills = list(my_hills or [])
        self._enemies = list(enemies or [])
        self.attackradius2 = attackradius2
        self.orders: list[tuple[Loc, str]] = []

    def food(self) -> list[Loc]:
        return self._foods[:]

    def my_ants(self) -> list[Loc]:
        return self._ants[:]

    def enemy_ants(self) -> list[tuple[Loc, int]]:
        return [(loc, 1) for loc in self._enemies]

    def my_hills(self) -> list[Loc]:
        return self._hills[:]

    def enemy_hills(self) -> list[tuple[Loc, int]]:
        return []

    def distance(self, a: Loc, b: Loc) -> int:
        dc = min(abs(a[1] - b[1]), self.cols - abs(a[1] - b[1]))
        dr = min(abs(a[0] - b[0]), self.rows - abs(a[0] - b[0]))
        return dr + dc

    def destination(self, loc: Loc, direction: str) -> Loc:
        aim = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
        dr, dc = aim[direction]
        return ((loc[0] + dr) % self.rows, (loc[1] + dc) % self.cols)

    def passable(self, loc: Loc) -> bool:
        return loc not in self._water

    def unoccupied(self, loc: Loc) -> bool:
        taken = set(self._ants) | set(self._enemies) | set(self._foods)
        return loc not in taken

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 1000


HILL: Loc = (10, 10)
CLOSE_ANTS: list[Loc] = [(9, 7), (11, 8), (10, 6)]
WEST_FOODS: list[Loc] = [(10, 0), (11, 0), (9, 0)]


def fresh_relief() -> Relief:
    bot = Relief()
    bot.do_setup(FakeAnts(10, 10, [(0, 0)], []))
    return bot


def test_gate_two_raiders_fearless_one_is_probe():
    assert FEARLESS_RAIDERS == 2
    assert FEARLESS_RADIUS == 15

    def dist(a: Loc, b: Loc) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def still(cur: Loc, hill: Loc) -> bool:
        return False

    assert fearless_hills([HILL], [(12, 12)], dist, still) == []
    assert fearless_hills([HILL], [(12, 12), (13, 12)], dist, still) == [HILL]
    assert fearless_hills([], [(12, 12), (13, 12)], dist, still) == []


def test_reinforcement_radius_boundary():
    # An ant exactly 15 away reinforces; 16 away stays on task.

    def dist(a: Loc, b: Loc) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    assert needs_reinforcement((10, 0), [HILL], dist)
    assert needs_reinforcement((10, -5), [HILL], dist)
    assert not needs_reinforcement((10, -6), [HILL], dist)
    assert not needs_reinforcement((0, 0), [HILL], dist)


def raid_state(enemies: list[Loc], ants: list[Loc], foods: list[Loc]) -> FakeAnts:
    return FakeAnts(20, 20, ants, foods, my_hills=[HILL], enemies=enemies)


def test_two_raiders_pull_every_ant_inside_15_off_food():
    enemies = [(12, 12), (13, 12)]
    state = raid_state(enemies, CLOSE_ANTS, WEST_FOODS)
    # All three ants hold food claims: they are gatherers, no exception.
    targets = assign_food_targets(
        CLOSE_ANTS, WEST_FOODS, enemies, state.distance, 20, 20
    )
    assert len(targets) == 3
    bot = fresh_relief()
    bot.do_turn(state)
    assert len(state.orders) == 3
    assert {loc for loc, _ in state.orders} == set(CLOSE_ANTS)
    screen = min(enemies, key=lambda e: state.distance(HILL, e))
    for i, ant in enumerate(CLOSE_ANTS):
        goal = HILL if i == 0 else screen
        dest = state.destination(ant, dict(state.orders)[ant])
        assert state.distance(dest, goal) == state.distance(ant, goal) - 1
        # Nobody steps toward its food: the claim is abandoned.
        assert state.distance(dest, targets[i]) >= state.distance(ant, targets[i])


def test_one_raider_probe_keeps_gatherers_on_food():
    enemies = [(12, 12)]
    state = raid_state(enemies, CLOSE_ANTS, WEST_FOODS)
    targets = assign_food_targets(
        CLOSE_ANTS, WEST_FOODS, enemies, state.distance, 20, 20
    )
    assert len(targets) == 3
    bot = fresh_relief()
    bot.do_turn(state)
    assert len(state.orders) == 3
    for ant in CLOSE_ANTS:
        dest = state.destination(ant, dict(state.orders)[ant])
        assert state.distance(dest, targets[CLOSE_ANTS.index(ant)]) == (
            state.distance(ant, targets[CLOSE_ANTS.index(ant)]) - 1
        )


def test_ants_beyond_15_stay_on_food_during_raid():
    enemies = [(12, 12), (13, 12)]
    ants = [(9, 7), (0, 0)]
    foods = [(9, 0), (0, 3)]
    state = raid_state(enemies, ants, foods)
    assert state.distance((0, 0), HILL) > FEARLESS_RADIUS
    targets = assign_food_targets(ants, foods, enemies, state.distance, 20, 20)
    assert len(targets) == 2
    bot = fresh_relief()
    bot.do_turn(state)
    by_ant = dict(state.orders)
    assert by_ant[(0, 0)] == "e"  # strides to its food, ignoring the raid
    near_dest = state.destination((9, 7), by_ant[(9, 7)])
    assert state.distance(near_dest, HILL) < state.distance((9, 7), HILL)


def test_muster_march_unaffected_while_reinforcing():
    # Home hill ringed by water: defense is unreachable, so a foodless
    # ant falls through to the muster. Same march with 1 or 2 raiders.
    ring = {(9, 10), (11, 10), (10, 9), (10, 11)}
    march_orders = []
    for enemies in ([(12, 12)], [(12, 12), (13, 12)]):
        state = FakeAnts(
            20, 20, [(9, 7)], [], water=ring, my_hills=[HILL], enemies=enemies
        )
        bot = fresh_relief()
        bot.remembered_hills = {(5, 5)}
        bot.do_turn(state)
        assert len(state.orders) == 1
        dest = state.destination((9, 7), state.orders[0][1])
        assert state.distance(dest, (5, 5)) < state.distance((9, 7), (5, 5))
        march_orders.append(state.orders)
    assert march_orders[0] == march_orders[1]


def test_raid_cleared_returns_to_economy():
    enemies = [(12, 12), (13, 12)]
    bot = fresh_relief()
    raided = raid_state(enemies, CLOSE_ANTS, WEST_FOODS)
    bot.do_turn(raided)
    assert len(raided.orders) == 3  # everyone reinforced
    calm = raid_state([], CLOSE_ANTS, WEST_FOODS)
    bot.do_turn(calm)
    targets = assign_food_targets(CLOSE_ANTS, WEST_FOODS, [], calm.distance, 20, 20)
    assert len(calm.orders) == 3
    by_ant = dict(calm.orders)
    for i, ant in enumerate(CLOSE_ANTS):
        dest = calm.destination(ant, by_ant[ant])
        assert calm.distance(dest, targets[i]) == calm.distance(ant, targets[i]) - 1
