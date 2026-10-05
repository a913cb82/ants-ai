#!/usr/bin/env python
"""Range-gated food tests (Greedy5 entry).

Base is Greedy4: food assignment is global-nearest with no range
cap, so on a big 10p-scale map an ant treks any distance to its
claimed food -- walking cross-map through up to nine enemies'
territory while nearby unseen ground goes unexplored. The census
winner (lazarant) instead gathers food only within 25 steps and
lets farther ants explore/cover (collectFoodDecision(ant, 25),
then explore25/control45 in its priority chain). Duel maps are
small, so the gate rarely binds there; 10p maps are big, so it
frees explorers exactly where greedy starves on expansion.

Greedy5 adds one mechanism -- range-gated food: assign_food_targets
ignores ant-food pairs farther than FOOD_RADIUS (25) apart, in both
the denial-claim loop and the global greedy loop. An ant with no
in-radius food falls through to guard/combat/muster/explore, which
in a quiet 10p opening means least-visited exploration instead of
a cross-map trek.

Proves, on fixed boards before the bot code lands:
(a) far food: lone ant with food 28 away -- base treks east,
    tuned explores north (least-visited tie order),
(b) boundary: food at exactly 25 claimed, at 26 not,
(c) mixed: two ants, near+far food -- tuned takes the near food
    and explores with the other; base treks both,
(d) far denial: contested cluster 30 away -- base spends two
    denial claimants trekking, tuned spends none,
(e) near boards byte-identical (duel behavior preserved),
(f) a crowded full turn still runs <1s.
"""

import os
import sys
import time
from types import ModuleType
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Greedy4 as Base  # noqa: E402
import Greedy5 as Tuned  # noqa: E402

Loc = tuple[int, int]
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
ATTACK_R2 = 5


class FakeAnts:
    """Minimal stand-in for ants.Ants covering do_turn's interface."""

    def __init__(
        self,
        mine: list[Loc],
        enemies: list[Loc],
        rows: int,
        cols: int,
        foods: list[Loc] | None = None,
        water: set[Loc] | None = None,
        enemy_hills: list[Loc] | None = None,
        my_hills: list[Loc] | None = None,
    ) -> None:
        self.rows = rows
        self.cols = cols
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
        return Tuned.Greedy5()
    return Base.Greedy4()


def run_turn(
    mod: ModuleType,
    mine: list[Loc],
    enemies: list[Loc],
    rows: int,
    cols: int,
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, rows, cols, foods, water, enemy_hills, my_hills)
    make_bot(mod).do_turn(fake)
    return fake.orders


def manhattan(rows: int, cols: int, a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, rows - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, cols - dc)
    return dr + dc


def assign(
    mod: ModuleType,
    ants_list: list[Loc],
    foods: list[Loc],
    enemies: list[Loc],
    rows: int,
    cols: int,
) -> dict[int, Loc]:
    dist = lambda a, b: manhattan(rows, cols, a, b)  # noqa: E731
    return mod.assign_food_targets(ants_list, foods, enemies, dist, rows, cols)


# one-idea discipline --------------------------------------------------------


def test_constants_identical_to_base_plus_food_radius() -> None:
    assert Tuned is not None
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
        "BRAVE_OBJECTIVE_R",
    ):
        assert getattr(Tuned, name) == getattr(Base, name), name
    assert Tuned.WEIGHTS == Base.WEIGHTS
    assert Tuned.FOOD_RADIUS == 25


# (a) far food: trek vs explore ------------------------------------------------
#
# Channeled 60x100 map: only row 30 plus a 5x5 open patch around
# the ant is passable, so BFS reaches 50 steps down the corridor
# inside its 250-node budget. Lone ant (30,10), one food (30,60)
# 50 east down the corridor, nothing else. Base claims it and
# steps east on the cross-map trek; tuned leaves it unclaimed and
# explores the open patch (fresh visits tie -> north first).


def corridor_water(rows: int, cols: int) -> set[Loc]:
    return {
        (r, c)
        for r in range(rows)
        for c in range(cols)
        if r != 30 and not (28 <= r <= 32 and 8 <= c <= 12)
    }


def test_far_food_base_treks_tuned_explores() -> None:
    assert Tuned is not None
    mine = [(30, 10)]
    foods = [(30, 60)]
    water = corridor_water(60, 100)
    assert manhattan(60, 100, mine[0], foods[0]) == 50
    assert run_turn(Base, mine, [], 60, 100, foods, water) == [((30, 10), "e")]
    tuned_orders = run_turn(Tuned, mine, [], 60, 100, foods, water)
    assert tuned_orders == [((30, 10), "n")]
    assert assign(Tuned, mine, foods, [], 60, 100) == {}
    assert assign(Base, mine, foods, [], 60, 100) == {0: (30, 60)}


# (b) boundary ------------------------------------------------------------------


def test_radius_boundary_25_claimed_26_not() -> None:
    assert Tuned is not None
    mine = [(30, 30)]
    near = [(30, 55)]  # distance exactly 25
    far = [(30, 56)]  # distance 26
    assert manhattan(60, 60, mine[0], near[0]) == 25
    assert manhattan(60, 60, mine[0], far[0]) == 26
    assert assign(Tuned, mine, near, [], 60, 60) == {0: (30, 55)}
    assert assign(Tuned, mine, far, [], 60, 60) == {}
    assert assign(Base, mine, far, [], 60, 60) == {0: (30, 56)}


# (c) mixed near + far ------------------------------------------------------------
#
# Two ants: one beside near food, one whose only food is 30 away.
# Base treks both; tuned gathers near and explores with the other.


def test_mixed_board_tuned_gathers_near_explores_far() -> None:
    assert Tuned is not None
    mine = [(5, 5), (30, 30)]
    foods = [(5, 6), (30, 0)]
    assert manhattan(60, 60, (30, 30), (30, 0)) == 30
    base_targets = assign(Base, mine, foods, [], 60, 60)
    assert base_targets == {0: (5, 6), 1: (30, 0)}
    tuned_targets = assign(Tuned, mine, foods, [], 60, 60)
    assert tuned_targets == {0: (5, 6)}
    tuned_orders = run_turn(Tuned, mine, [], 60, 60, foods)
    by_start = dict(tuned_orders)
    assert by_start[(5, 5)] == "e"  # steps onto adjacent food
    assert (30, 30) in by_start  # far ant moves (explores)...
    dest = (
        (30 + AIM[by_start[(30, 30)]][0]) % 60,
        (30 + AIM[by_start[(30, 30)]][1]) % 60,
    )
    assert manhattan(60, 60, dest, (30, 0)) >= manhattan(60, 60, (30, 30), (30, 0))


# (d) far contested cluster draws no denial trekkers ---------------------------------
#
# Three foes sit on a food cluster 30 away: base spends its two
# denial claimants marching cross-map; tuned spends none.


def test_far_contested_cluster_no_denial_trek() -> None:
    assert Tuned is not None
    mine = [(30, 30), (30, 31)]
    foods = [(30, 0), (30, 1)]
    enemies = [(30, 2), (30, 3), (31, 2)]
    assert len(assign(Base, mine, foods, enemies, 60, 60)) == 2
    assert assign(Tuned, mine, foods, enemies, 60, 60) == {}


def test_near_contested_cluster_still_denied() -> None:
    # Same shape close up: the gate must not disarm denial where
    # it matters (duels). Both spend two claimants.
    assert Tuned is not None
    mine = [(5, 5), (5, 6)]
    foods = [(5, 10), (5, 11)]
    enemies = [(5, 12), (5, 13), (6, 12)]
    assert assign(Base, mine, foods, enemies, 20, 20) == assign(
        Tuned, mine, foods, enemies, 20, 20
    )
    assert len(assign(Tuned, mine, foods, enemies, 20, 20)) == 2


# (e) near boards byte-identical ------------------------------------------------------
#
# Everything within radius (20x20 boards max out at distance 20):
# tuned matches base exactly, so duel behavior is preserved.


def test_near_boards_byte_identical_to_base() -> None:
    assert Tuned is not None
    boards = [
        ([(10, 10)], [(10, 12)], [(10, 13)], None, None, None),
        ([(10, 10)], [(10, 12)], None, None, None, None),
        ([(5, 5)], [(5, 7)], None, None, [(5, 8)], None),
        ([(0, 0), (0, 19)], [], [(0, 1), (0, 18)], None, None, None),
        ([(0, 0)], [], None, None, [(10, 10)], None),
        ([(5, 5)], [(15, 15)], None, None, None, None),
        ([(5, 5), (5, 4)], [(5, 7)], None, None, None, None),
        ([(10, 10), (10, 7)], [(10, 12)], [(10, 8)], None, None, None),
        ([(3, 3)], [], None, None, None, [(3, 3)]),
    ]
    for mine, enemies, foods, water, enemy_hills, my_hills in boards:
        assert run_turn(
            Tuned, mine, enemies, 20, 20, foods, water, enemy_hills, my_hills
        ) == run_turn(Base, mine, enemies, 20, 20, foods, water, enemy_hills, my_hills)


def test_brave_take_inside_radius_preserved() -> None:
    # Greedy4's signature duel take (lone 1v1 onto food at range 2)
    # sits far inside the radius: tuned must still take it.
    assert Tuned is not None
    mine = [(10, 10)]
    enemies = [(10, 12)]
    foods = [(10, 13)]
    assert run_turn(Tuned, mine, enemies, 20, 20, foods) == run_turn(
        Base, mine, enemies, 20, 20, foods
    )
    assert run_turn(Tuned, mine, enemies, 20, 20, foods) == [((10, 10), "e")]


# (f) speed -----------------------------------------------------------------------


def test_crowded_full_turn_under_one_second() -> None:
    assert Tuned is not None
    mine = [(r, c) for r in range(0, 20, 2) for c in range(0, 20, 2)][:60]
    enemies = [(r, c) for r in range(1, 20, 2) for c in range(1, 20, 2)][:60]
    foods = [(r, c) for r in range(0, 20, 3) for c in range(0, 20, 5)][:40]
    water = {(10, c) for c in range(20) if c not in (9, 10)}
    start = time.perf_counter()
    orders = run_turn(Tuned, mine, enemies, 20, 20, foods, water, [(19, 19)], [(0, 0)])
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(orders) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
