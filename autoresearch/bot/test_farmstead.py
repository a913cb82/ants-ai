#!/usr/bin/env python
"""Farmstead (feet-plus-fallback) tests. No engine games.

The one change over champion Denial: an idle ant (no food move, no
hill move) steps toward the nearest friendly ant that has a task
instead of diffusing to least-visited squares. Only a truly
isolated idle (no tasked friend within 20) falls back to
least-visited explore. Followers join the pool, so chains form
transitively (idle follows idle follows tasked).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Farmstead import (  # noqa: E402
    FOLLOW_RADIUS,
    Farmstead,
    assign_food_targets,
    nearest_follow_target,
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


def fresh_farmstead(follow: bool = True) -> Farmstead:
    bot = Farmstead()
    bot.do_setup(FakeAnts(10, 10, [(0, 0)], []))
    bot.use_follow = follow
    return bot


def test_follow_radius_is_twenty():
    assert FOLLOW_RADIUS == 20


def test_nearest_follow_target_picks_closest_in_range():
    def dist(a: Loc, b: Loc) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    me: Loc = (10, 10)
    near: Loc = (10, 13)
    far: Loc = (10, 16)
    assert nearest_follow_target(me, [far, near], dist) == near
    assert nearest_follow_target(me, [far], dist, radius=5) is None
    assert nearest_follow_target(me, [me], dist) is None
    assert nearest_follow_target(me, [], dist) is None


def test_idle_steps_toward_not_away_from_tasked_friend():
    # One food, two ants: the closer ant is tasked, the other is idle
    # with no hills known. Untouched explore would step north (all
    # squares unvisited, stable order n/e/s/w); feet step west, toward
    # the tasked friend, shrinking the gap.
    tasked: Loc = (10, 10)
    idle: Loc = (10, 14)
    state = FakeAnts(20, 20, [tasked, idle], [(10, 8)])
    targets = assign_food_targets([tasked, idle], [(10, 8)], [], state.distance, 20, 20)
    assert 0 in targets and 1 not in targets
    bot = fresh_farmstead()
    bot.do_turn(state)
    by_ant = dict(state.orders)
    assert by_ant[tasked] == "w"  # strides to its food
    assert by_ant[idle] == "w"  # steps toward the tasked friend
    assert state.distance((10, 13), tasked) < state.distance(idle, tasked)


def test_chains_form_transitively_idle_follows_idle():
    # A is tasked; B is idle within 20 of A; C is idle within 20 of B
    # but 26 from A, so C can only link through B. Explore would send
    # both north; feet send both west, down the chain.
    a: Loc = (10, 4)
    b: Loc = (10, 16)
    c: Loc = (10, 30)
    state = FakeAnts(60, 60, [a, b, c], [(10, 2)])
    assert state.distance(c, a) > FOLLOW_RADIUS
    assert state.distance(c, b) <= FOLLOW_RADIUS
    assert state.distance(b, a) <= FOLLOW_RADIUS
    targets = assign_food_targets([a, b, c], [(10, 2)], [], state.distance, 60, 60)
    assert 0 in targets and 1 not in targets and 2 not in targets
    bot = fresh_farmstead()
    bot.do_turn(state)
    by_ant = dict(state.orders)
    assert by_ant[b] == "w"  # B follows tasked A
    assert by_ant[c] == "w"  # C follows follower B, not least-visited
    assert state.distance(state.destination(c, "w"), b) < state.distance(c, b)


def test_isolated_idle_still_explores_least_visited():
    # One ant, no food, no hills, no friends: the fallback survives.
    idle: Loc = (10, 10)
    state = FakeAnts(20, 20, [idle], [])
    bot = fresh_farmstead()
    bot.visits = {(9, 10): 5, (10, 11): 4, (11, 10): 3, (10, 9): 0}
    bot.do_turn(state)
    assert state.orders == [(idle, "w")]


def test_out_of_range_idle_still_explores_least_visited():
    # A tasked friend 26 away is no feet to follow: the idle must
    # explore least-visited (west) instead of marching east toward it.
    a: Loc = (10, 4)
    idle: Loc = (10, 30)
    state = FakeAnts(60, 60, [a, idle], [(10, 2)])
    assert state.distance(idle, a) > FOLLOW_RADIUS
    bot = fresh_farmstead()
    bot.visits = {(9, 30): 5, (10, 31): 4, (11, 30): 3, (10, 29): 0}
    bot.do_turn(state)
    assert dict(state.orders)[idle] == "w"


def test_tasked_orders_identical_with_feature_on_vs_off():
    # Tasked ants never reach the fallback, so the flag must not move
    # them by a byte. Tasked ants run first, so idle feet cannot steal
    # their squares either.
    ants = [(10, 10), (12, 12), (15, 15)]
    foods = [(10, 8), (12, 10)]
    on = FakeAnts(20, 20, ants, foods)
    off = FakeAnts(20, 20, ants, foods)
    fresh_farmstead(follow=True).do_turn(on)
    fresh_farmstead(follow=False).do_turn(off)
    on_by = dict(on.orders)
    off_by = dict(off.orders)
    assert on_by[(10, 10)] == off_by[(10, 10)] == "w"
    assert on_by[(12, 12)] == off_by[(12, 12)]
    # The feature flag exists and the old path still moves idles.
    assert len(off.orders) == 3
