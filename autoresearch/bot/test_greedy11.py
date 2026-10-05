#!/usr/bin/env python
"""Soft-cede denial tests (Greedy11 entry).

Base is Greedy7: race-gated (winnable) denial where a LOST
cluster is ceded outright -- zero denial claimants AND its foods
stay unclaimed this turn (blocked from normal greedy too), so
the ants explore instead of marching into a lost fight. That
split duels from crowds the wrong way: duels went 6-1 on kept
takes, but crowds starved (10p 9/10) because nearby ants would
not gather food the enemy merely stands closer to.

Greedy11 adds one mechanism -- soft-cede: a lost cluster draws
no denial stacking (no forced claimants, no blocking), but its
foods stay eligible for normal nearest-pair greedy claims. Won
and tied races still deny exactly like base, so duel takes are
preserved; lost races gather fairly instead of starving.

Proves, on fixed boards before the bot code lands:
(a) lost-but-near: foes sit on a two-food cluster (theirs 0)
    with our ant 2 away and a free food by our second ant --
    base stacks denial AND steals the far ant cross-map, Greedy7
    leaves the near ant exploring (starves), Greedy11 feeds
    both ants fairly,
(b) far lost race: within the food radius Greedy11 gathers like
    base (fair nearest pairs) instead of exploring like Greedy7,
(c) won race: denies byte-identically to Greedy7/base,
(d) tie race: still denies byte-identically,
(e) duel boards byte-identical (no-contest boards plus won
    races and the brave take),
(f) a crowded full turn still runs <1s.
"""

import os
import sys
import time
from types import ModuleType
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Greedy5 as Base5  # noqa: E402
import Greedy7 as Base  # noqa: E402
import Greedy11 as Tuned  # noqa: E402

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
        return Tuned.Greedy11()
    if mod is Base:
        return Base.Greedy7()
    return Base5.Greedy5()


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


def race(
    ants_list: list[Loc],
    foods: list[Loc],
    enemies: list[Loc],
    rows: int,
    cols: int,
) -> tuple[int, int]:
    ours = min(manhattan(rows, cols, a, f) for a in ants_list for f in foods)
    theirs = min(manhattan(rows, cols, e, f) for e in enemies for f in foods)
    return ours, theirs


# one-idea discipline --------------------------------------------------------


def test_constants_identical_to_base() -> None:
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
        "FOOD_RADIUS",
        "DENIAL_RACE_MARGIN",
    ):
        assert getattr(Tuned, name) == getattr(Base, name), name
    assert Tuned.WEIGHTS == Base.WEIGHTS


# (a) lost-but-near: base steals, Greedy7 starves, tuned feeds ----------------------
#
# Two contested clusters, both lost (foes sit on every food), plus
# one free food a step from our second ant. Base stacks denial on
# both clusters and steals the far ant cross-map onto cluster-2
# food; Greedy7 cedes everything so the near ant explores instead
# of gathering food 2 away; tuned feeds both ants fairly.


def test_lost_near_base_steals_greedy7_starves_tuned_feeds() -> None:
    assert Tuned is not None
    mine = [(5, 8), (30, 20)]
    foods1 = [(5, 10), (5, 11)]
    foes1 = [(5, 10), (5, 11), (6, 10)]
    foods2 = [(30, 40), (30, 41)]
    foes2 = [(30, 40), (30, 41), (31, 40)]
    free = [(30, 21)]
    foods = foods1 + foods2 + free
    enemies = foes1 + foes2
    ours1, theirs1 = race(mine, foods1, foes1, 60, 60)
    assert (ours1, theirs1) == (2, 0)
    ours2, theirs2 = race(mine, foods2, foes2, 60, 60)
    assert (ours2, theirs2) == (20, 0)
    # Base forces one claimant per cluster: the near ant onto
    # cluster 1, and -- inside FOOD_RADIUS -- the far ant onto
    # cluster 2, abandoning the free food at distance 1.
    assert assign(Base5, mine, foods, enemies, 60, 60) == {
        0: (5, 10),
        1: (30, 40),
    }
    # Greedy7 cedes both clusters outright: the near ant gets
    # nothing and only the free food is gathered.
    assert assign(Base, mine, foods, enemies, 60, 60) == {1: (30, 21)}
    # Tuned gathers fairly: each ant takes its nearest food.
    assert assign(Tuned, mine, foods, enemies, 60, 60) == {
        0: (5, 10),
        1: (30, 21),
    }
    tuned_orders = run_turn(Tuned, mine, enemies, 60, 60, foods)
    by_start = dict(tuned_orders)
    assert by_start[(30, 20)] == "e"  # steps onto the free food
    # The nearby food step is suicide (3 foes adjacent), so safety
    # correctly vetoes it: tuned refuses exactly like Greedy7 --
    # soft-cede feeds crowds without ordering suicides.
    greedy7_orders = run_turn(Base, mine, enemies, 60, 60, foods)
    greedy7_by_start = dict(greedy7_orders)
    assert by_start[(5, 8)] == greedy7_by_start[(5, 8)] != "e"


# (b) far lost race gathers fairly instead of exploring ------------------------------
#
# Foes sit on a two-food cluster (theirs 1) while our ants stand
# 10+ away. Greedy7 cedes and explores north; tuned claims both
# foods through normal nearest-pair greedy, like base.


def test_far_lost_race_tuned_gathers_like_base() -> None:
    assert Tuned is not None
    mine = [(10, 5), (12, 5)]
    foods = [(10, 15), (10, 16)]
    enemies = [(10, 17), (10, 18), (11, 17)]
    ours, theirs = race(mine, foods, enemies, 60, 60)
    assert (ours, theirs) == (10, 1)
    assert assign(Base, mine, foods, enemies, 60, 60) == {}
    assert assign(Tuned, mine, foods, enemies, 60, 60) == assign(
        Base5, mine, foods, enemies, 60, 60
    )
    assert assign(Tuned, mine, foods, enemies, 60, 60) == {
        0: (10, 15),
        1: (10, 16),
    }
    tuned_orders = run_turn(Tuned, mine, enemies, 40, 40, foods)
    by_start = dict(tuned_orders)
    for ant in mine:
        before = min(manhattan(40, 40, ant, f) for f in foods)
        dest = (
            (ant[0] + AIM[by_start[ant]][0]) % 40,
            (ant[1] + AIM[by_start[ant]][1]) % 40,
        )
        after = min(manhattan(40, 40, dest, f) for f in foods)
        assert after == before - 1  # tuned treks to gather, not away


# (c) won race: deny exactly like base --------------------------------------------------


def test_won_race_denies_like_base() -> None:
    assert Tuned is not None
    mine = [(5, 9), (5, 8)]
    foods = [(5, 10), (5, 11)]
    enemies = [(5, 14), (5, 15), (6, 14)]
    ours, theirs = race(mine, foods, enemies, 20, 20)
    assert ours < theirs
    assert assign(Tuned, mine, foods, enemies, 20, 20) == assign(
        Base, mine, foods, enemies, 20, 20
    )
    assert len(assign(Tuned, mine, foods, enemies, 20, 20)) == 2
    assert run_turn(Tuned, mine, enemies, 20, 20, foods) == run_turn(
        Base, mine, enemies, 20, 20, foods
    )


# (d) tie race: still denies ----------------------------------------------------------------


def test_tied_race_still_denies() -> None:
    assert Tuned is not None
    mine = [(5, 8)]
    foods = [(5, 10)]
    enemies = [(5, 12), (5, 13), (6, 12)]
    ours, theirs = race(mine, foods, enemies, 20, 20)
    assert ours == theirs == 2
    assert assign(Tuned, mine, foods, enemies, 20, 20) == assign(
        Base, mine, foods, enemies, 20, 20
    )
    assert assign(Tuned, mine, foods, enemies, 20, 20) == {0: (5, 10)}


# (e) duel boards byte-identical ------------------------------------------------------------------
#
# Boards with no contested cluster never reach the race gate, won
# races deny exactly like base, and far lost races gather exactly
# like Greedy5 -- which on these small duel boards (every food
# within reach, no competing free food) is what base does too.


def test_duel_boards_byte_identical_to_base() -> None:
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
        (
            [(5, 9), (5, 8)],
            [(5, 14), (5, 15), (6, 14)],
            [(5, 10), (5, 11)],
            None,
            None,
            None,
        ),
    ]
    for mine, enemies, foods, water, enemy_hills, my_hills in boards:
        assert run_turn(
            Tuned, mine, enemies, 20, 20, foods, water, enemy_hills, my_hills
        ) == run_turn(Base, mine, enemies, 20, 20, foods, water, enemy_hills, my_hills)


def test_brave_take_inside_radius_preserved() -> None:
    # Greedy5's signature duel take (lone 1v1 onto food at range 2)
    # has no contested cluster: tuned must still take it.
    assert Tuned is not None
    mine = [(10, 10)]
    enemies = [(10, 12)]
    foods = [(10, 13)]
    assert run_turn(Tuned, mine, enemies, 20, 20, foods) == run_turn(
        Base, mine, enemies, 20, 20, foods
    )
    assert run_turn(Tuned, mine, enemies, 20, 20, foods) == [((10, 10), "e")]


# (f) speed ---------------------------------------------------------------------------------


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
