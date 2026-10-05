#!/usr/bin/env python
"""Objective-weighted bravery tests (Greedy4 entry).

Base is Greedy3: every combat step passes is_safe (strict local
superiority, zero foes in range, or equal numbers backed by
EQUAL_TRADE_NEAR friends nearby). The gate saves crowds but also
refuses every lone 1v1 -- even a trade that contests food or
presses a raze. Under the engine's focus combat, symmetric 1v1s
trade both ants, so refusing them all cedes the food race and the
hill pressure that decide duels. Greedy3 rules crowds (10p 1/10)
but drops duels (1-6), including to its own unsafe parent.

Greedy4 adds one mechanism -- objective-weighted bravery: an
even-trade combat step (ours == theirs >= 1, no strict edge, no
crowd backing) is allowed iff the destination stands within
BRAVE_OBJECTIVE_R of visible food or a remembered enemy hill.
Something worth dying for. 1vN (theirs > ours) is still always
refused, pointless 1v1s far from objectives still hold, and every
non-combat path keeps the full is_safe gate.

Proves, on fixed boards before the bot code lands:
(a) duel food-take: lone 1v1 with food near the step -- base
    retreats, tuned steps in (matches unsafe Greedy2's take),
(b) duel raze-press: lone 1v1 with an enemy hill near the step --
    base marches away, tuned steps in,
(c) pointless 1v1 far from objectives -- tuned == base (holds),
(d) 1v2 near food -- still refused (outnumbered, not even),
(e) packed wins / equal-crowd / quiet boards byte-identical,
(f) a crowded full turn still runs <1s.
"""

import os
import sys
import time
from types import ModuleType
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Greedy2 as Unsafe  # noqa: E402
import Greedy3 as Base  # noqa: E402
import Greedy4 as Tuned  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
ATTACK_R2 = 5


class FakeAnts:
    """Minimal stand-in for ants.Ants covering do_turn's interface."""

    def __init__(
        self,
        mine: list[Loc],
        enemies: list[Loc],
        foods: list[Loc] | None = None,
        water: set[Loc] | None = None,
        enemy_hills: list[Loc] | None = None,
        my_hills: list[Loc] | None = None,
    ) -> None:
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = ATTACK_R2
        self._mine = list(mine)
        self._enemies = list(enemies)
        self._foods = list(foods or [])
        self._water = set(water or set())
        self._enemy_hills = list(enemy_hills or [])
        self._my_hills = list(my_hills or [])
        self.orders: list[tuple[Loc, str]] = []

    def food(self) -> list[Loc]:
        return list(self._foods)

    def my_ants(self) -> list[Loc]:
        return list(self._mine)

    def enemy_ants(self) -> list[tuple[Loc, int]]:
        return [(e, 1) for e in self._enemies]

    def enemy_hills(self) -> list[tuple[Loc, int]]:
        return [(h, 1) for h in self._enemy_hills]

    def my_hills(self) -> list[Loc]:
        return list(self._my_hills)

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


def make_bot(mod: ModuleType) -> Any:
    if mod is Tuned:
        return Tuned.Greedy4()
    if mod is Base:
        return Base.Greedy3()
    return Unsafe.Greedy2()


def run_turn(
    mod: ModuleType,
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    make_bot(mod).do_turn(fake)
    return fake.orders


def post_move(start: Loc, direction: str) -> Loc:
    dr, dc = AIM[direction]
    return ((start[0] + dr) % ROWS, (start[1] + dc) % COLS)


def flat_sq(a: Loc, b: Loc) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


# one-idea discipline --------------------------------------------------------


def test_constants_identical_to_base_plus_brave_radius() -> None:
    for name in (
        "W_FOOD",
        "W_ENEMY",
        "W_HILL",
        "W_UNSEEN",
        "KILL_BONUS",
        "FIELD_HORIZON",
        "COMBAT_RANGE",
        "EQUAL_TRADE_NEAR",
        "CLUSTER_R",
        "DENIAL_ENEMIES",
        "DENIAL_CLAIMS",
    ):
        assert getattr(Tuned, name) == getattr(Base, name), name
    assert Tuned.WEIGHTS == Base.WEIGHTS
    assert Tuned.BRAVE_OBJECTIVE_R == 2


# (a) duel food-take ----------------------------------------------------------
#
# Lone ant (10,10), foe (10,12), food (10,13): the food claim's east
# step is unsafe, so combat decides. Base retreats west; the unsafe
# grandparent steps east onto (10,11) and contests the food at range
# 2. Tuned must recover that take: step east, byte-identical to the
# unsafe parent on this board.


def test_base_retreats_from_food_take() -> None:
    orders = run_turn(Base, [(10, 10)], [(10, 12)], [(10, 13)])
    assert orders[0] == ((10, 10), "w")


def test_tuned_recovers_food_take_like_unsafe_parent() -> None:
    mine = [(10, 10)]
    enemies = [(10, 12)]
    foods = [(10, 13)]
    unsafe_orders = run_turn(Unsafe, mine, enemies, foods)
    assert unsafe_orders[0] == ((10, 10), "e")
    tuned_orders = run_turn(Tuned, mine, enemies, foods)
    assert tuned_orders == unsafe_orders
    assert tuned_orders != run_turn(Base, mine, enemies, foods)


# (b) duel raze-press ---------------------------------------------------------
#
# Lone ant (5,5), foe (5,7), remembered hill (5,8): the east step
# onto (5,6) stands 2 from the hill -- a raze-press trade. Base
# refuses it and falls through to a safe square; tuned steps east.


def test_tuned_presses_raze_while_base_holds() -> None:
    mine = [(5, 5)]
    enemies = [(5, 7)]
    base_orders = run_turn(Base, mine, enemies, None, None, [(5, 8)], None)
    assert all(
        start != (5, 5) or post_move(start, d) != (5, 6) for start, d in base_orders
    )
    tuned_orders = run_turn(Tuned, mine, enemies, None, None, [(5, 8)], None)
    assert ((5, 5), "e") in tuned_orders


def test_far_hill_gives_no_courage() -> None:
    # Same duel, but the hill sits 4 from the step: no objective
    # nearby, so tuned matches base exactly (holds back).
    mine = [(5, 5)]
    enemies = [(5, 7)]
    assert run_turn(Tuned, mine, enemies, None, None, [(5, 10)], None) == run_turn(
        Base, mine, enemies, None, None, [(5, 10)], None
    )


# (c) pointless 1v1 still holds --------------------------------------------------


def test_pointless_1v1_byte_identical_to_base() -> None:
    # No food, no hills: nothing worth dying for, so the gate
    # stands and tuned retreats exactly like base.
    for mine, enemies in (
        ([(10, 10)], [(10, 12)]),
        ([(10, 10)], [(10, 13)]),
        ([(5, 5)], [(5, 7)]),
    ):
        assert run_turn(Tuned, mine, enemies) == run_turn(Base, mine, enemies)
        assert run_turn(Tuned, mine, enemies)[0][1] != "e" or mine[0] == (5, 5)


def test_food_too_far_gives_no_courage() -> None:
    # Food 5 from the step: outside the brave radius, so tuned
    # matches base (retreats west) instead of taking.
    mine = [(10, 10)]
    enemies = [(10, 12)]
    foods = [(10, 16)]
    assert run_turn(Base, mine, enemies, foods)[0] == ((10, 10), "w")
    assert run_turn(Tuned, mine, enemies, foods) == run_turn(Base, mine, enemies, foods)


# (d) outnumbered takes still refused ----------------------------------------------


def test_1v2_near_food_still_refused() -> None:
    # Two foes: stepping east dies outright (weakness 2 vs 1 under
    # focus combat). Bravery covers even trades only, so the ant
    # holds -- no order at all -- exactly like base.
    enemies = [(10, 12), (11, 11)]
    assert run_turn(Base, [(10, 10)], enemies, [(10, 13)]) == []
    assert run_turn(Tuned, [(10, 10)], enemies, [(10, 13)]) == []


def test_1v2_near_hill_still_refused() -> None:
    enemies = [(5, 7), (6, 6)]
    base_orders = run_turn(Base, [(5, 5)], enemies, None, None, [(5, 8)], None)
    tuned_orders = run_turn(Tuned, [(5, 5)], enemies, None, None, [(5, 8)], None)
    assert tuned_orders == base_orders
    assert all(post_move(s, d) != (5, 6) for s, d in tuned_orders)


# (e) winners, crowds, and quiet boards byte-identical ------------------------------


def test_packed_wins_byte_identical_to_base() -> None:
    boards = [
        ([(5, 5), (5, 4)], [(5, 7)], None, None, None, None),
        ([(5, 5), (5, 4), (6, 5)], [(5, 7), (6, 7)], None, None, None, None),
        ([(10, 10), (10, 7)], [(10, 12)], [(10, 8)], None, None, None),
    ]
    for mine, enemies, foods, water, enemy_hills, my_hills in boards:
        assert run_turn(
            Tuned, mine, enemies, foods, water, enemy_hills, my_hills
        ) == run_turn(Base, mine, enemies, foods, water, enemy_hills, my_hills)


def test_equal_trade_with_crowd_byte_identical_to_base() -> None:
    crowd = [
        (10, 4),
        (10, 5),
        (11, 4),
        (11, 5),
        (9, 4),
        (9, 5),
        (12, 4),
        (12, 5),
        (8, 4),
        (8, 5),
    ]
    mine = [(10, 10)] + crowd
    enemies = [(10, 12)]
    assert run_turn(Tuned, mine, enemies) == run_turn(Base, mine, enemies)
    assert run_turn(Tuned, mine, enemies, [(10, 13)]) == run_turn(
        Base, mine, enemies, [(10, 13)]
    )


def test_quiet_boards_byte_identical_to_base() -> None:
    boards = [
        ([(0, 0), (0, 19)], [], [(0, 1), (0, 18)], None, None, None),
        ([(0, 0)], [], None, None, [(10, 10)], None),
        ([(5, 5)], [(15, 15)], None, None, None, None),
        ([(3, 3)], [], None, None, None, [(3, 3)]),
    ]
    for mine, enemies, foods, water, enemy_hills, my_hills in boards:
        assert run_turn(
            Tuned, mine, enemies, foods, water, enemy_hills, my_hills
        ) == run_turn(Base, mine, enemies, foods, water, enemy_hills, my_hills)


def test_brave_step_never_outnumbered() -> None:
    # On every probe board, tuned never steps onto a square where
    # foes in attack range outnumber friends: bravery only ever
    # spends even trades.
    probes = [
        ([(10, 10)], [(10, 12)], [(10, 13)], None),
        ([(5, 5)], [(5, 7)], None, [(5, 8)]),
        ([(10, 10)], [(10, 12), (11, 11)], [(10, 13)], None),
        ([(10, 10)], [(10, 12)], [(10, 16)], None),
    ]
    for mine, enemies, foods, hills in probes:
        for start, direction in run_turn(
            Tuned, mine, enemies, foods, None, hills, None
        ):
            dest = post_move(start, direction)
            foes = sum(1 for e in enemies if flat_sq(dest, e) <= ATTACK_R2)
            assert foes <= 1, (mine, enemies, dest)


# (f) speed -----------------------------------------------------------------------


def test_crowded_full_turn_under_one_second() -> None:
    mine = [(r, c) for r in range(0, 20, 2) for c in range(0, 20, 2)][:60]
    enemies = [(r, c) for r in range(1, 20, 2) for c in range(1, 20, 2)][:60]
    foods = [(r, c) for r in range(0, 20, 3) for c in range(0, 20, 5)][:40]
    water = {(10, c) for c in range(20) if c not in (9, 10)}
    start = time.perf_counter()
    orders = run_turn(Tuned, mine, enemies, foods, water, [(19, 19)], [(0, 0)])
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(orders) > 0


def test_combat_heavy_turn_under_one_second() -> None:
    mine = [(10 + (i // 10), 8 + (i % 10)) for i in range(40)]
    enemies = [(10 + (i // 10), 12 + (i % 4)) for i in range(16)]
    start = time.perf_counter()
    orders = run_turn(Tuned, mine, enemies)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(orders) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
