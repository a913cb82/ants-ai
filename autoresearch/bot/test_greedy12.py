#!/usr/bin/env python
"""Race-gated crowd cap tests (Greedy12 entry).

Base is Greedy8: any cluster with 5+ visible enemies is ceded
outright -- no claimants, foods unclaimed -- even when our ants
stand adjacent to the food and the nearest foe is steps farther
out. That pure count gate misfires: it donates winnable food and
may explain the 35.7 -> 13.3 donation. Greedy7's answer was a
distance race (cede only lost clusters); this entry reprices the
cap instead of removing it: a 5+ crowd is ceded ONLY when the
race is lost (our nearest ant farther than the nearest enemy,
ties deny). Adjacent ants still contest a crowd; beaten ants
still cede it.

Discriminating scenarios (fixed boards, before the bot code lands):
(a) crowd + adjacent ours: base cedes (0 claimants), tuned denies
    (2 claimants) -- the reprice binds,
(b) crowd + beaten ours: base and tuned both cede (0) -- the cede
    is preserved when the race is lost,
(c) tie race on a crowd: tuned denies (ties deny),
(d) small contest (3 foes): base and tuned deny identically,
(e) near/small boards byte-identical (duel behavior preserved),
(f) a crowded full turn still runs <1s.
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Greedy8 as Base  # noqa: E402

try:
    import Greedy12 as Tuned  # noqa: E402
except ImportError:
    Tuned = None

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


def make_bot(mod):
    return mod.Greedy12() if mod is Tuned else mod.Greedy8()


def run_turn(
    mod,
    mine,
    enemies,
    rows,
    cols,
    foods=None,
    water=None,
    enemy_hills=None,
    my_hills=None,
):
    fake = FakeAnts(mine, enemies, rows, cols, foods, water, enemy_hills, my_hills)
    make_bot(mod).do_turn(fake)
    return fake.orders


def manhattan(rows: int, cols: int, a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, rows - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, cols - dc)
    return dr + dc


def assign(mod, ants_list, foods, enemies, rows, cols):
    dist = lambda a, b: manhattan(rows, cols, a, b)  # noqa: E731
    return mod.assign_food_targets(ants_list, foods, enemies, dist, rows, cols)


def crowded_cluster() -> tuple[list[Loc], list[Loc]]:
    # Two adjacent foods plus six foes within CLUSTER_R of them.
    # Foods at (16,10),(16,11); foes march east from (16,13): all
    # six sit within 8 of a cluster food (crowd of 6), nearest foe
    # 2 steps off the (16,11) food.
    foods = [(16, 10), (16, 11)]
    enemies = [(16, 13 + i) for i in range(6)]
    return foods, enemies


# one-idea discipline --------------------------------------------------------


def test_constants_identical_to_base_plus_race_margin() -> None:
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
        "DENIAL_MAX_ENEMIES",
        "BRAVE_OBJECTIVE_R",
        "FOOD_RADIUS",
    ):
        assert getattr(Tuned, name) == getattr(Base, name), name
    assert Tuned.WEIGHTS == Base.WEIGHTS
    # The one repricing knob: ties deny, so the margin is 0.
    assert Tuned.DENIAL_RACE_MARGIN == 0


# (a) crowd + adjacent ours: reprice binds --------------------------------------
#
# Our ants stand adjacent to the food (nearest 1 step off) while
# the nearest foe is 2 steps out. Base's pure count gate cedes (0
# claimants); tuned wins the race and denies (2 claimants).


def test_won_race_crowd_denied() -> None:
    assert Tuned is not None
    mine = [(16, 8), (16, 9)]
    foods, enemies = crowded_cluster()
    assert len(assign(Base, mine, foods, enemies, 40, 40)) == 0
    tuned = assign(Tuned, mine, foods, enemies, 40, 40)
    assert len(tuned) == 2
    assert set(tuned.values()) <= set(foods)


# (b) crowd + beaten ours: cede preserved -----------------------------------------
#
# Our ants stand 6 steps off the food, the nearest foe 2. Both
# base and tuned cede (0 claimants): the race is lost, so the cap
# still binds. A pure always-deny alternative would spend 2 here.


def test_lost_race_crowd_ceded() -> None:
    assert Tuned is not None
    mine = [(10, 9), (10, 10)]
    foods, enemies = crowded_cluster()
    assert min(manhattan(40, 40, a, e) for a in mine for e in enemies) > 8
    assert assign(Base, mine, foods, enemies, 40, 40) == {}
    assert assign(Tuned, mine, foods, enemies, 40, 40) == {}
    assert run_turn(Tuned, mine, enemies, 40, 40, foods) == run_turn(
        Base, mine, enemies, 40, 40, foods
    )


# (c) tie race on a crowd denies ----------------------------------------------------


def test_tied_race_crowd_denied() -> None:
    assert Tuned is not None
    # Our ant 2 steps off the food, nearest foe 2 steps out.
    mine = [(14, 11), (14, 10)]
    foods = [(16, 10), (16, 11)]
    enemies = [(16, 13), (16, 14), (16, 15), (15, 14), (17, 14), (16, 16)]
    assert len(enemies) == 6
    assert all(min(manhattan(40, 40, e, f) for f in foods) <= 8 for e in enemies)
    ours = min(manhattan(40, 40, a, f) for a in mine for f in foods)
    theirs = min(manhattan(40, 40, e, f) for e in enemies for f in foods)
    assert ours == theirs == 2
    assert assign(Base, mine, foods, enemies, 40, 40) == {}
    assert len(assign(Tuned, mine, foods, enemies, 40, 40)) == 2


# (d) small contest unchanged ----------------------------------------------------------
#
# Three foes: below the crowd cap, so the race gate never binds --
# base and tuned deny identically.


def test_small_contest_still_denied_identically() -> None:
    assert Tuned is not None
    mine = [(16, 8), (16, 9)]
    foods = [(16, 10), (16, 11)]
    enemies = [(16, 13), (16, 14), (16, 15)]
    assert len(assign(Base, mine, foods, enemies, 40, 40)) == 2
    assert assign(Tuned, mine, foods, enemies, 40, 40) == assign(
        Base, mine, foods, enemies, 40, 40
    )


# (a2) full turn: won race contests while base treks away -------------------------------
#
# Same crowd, plus a safe lone food at (16,0) -- its own cluster,
# 10 steps off the contest. Base cedes the crowd and sends an ant
# trekking west to the safe food; tuned wins the race, spends both
# claimants on the cluster, and nobody treks west. The claim
# difference is visible in one full turn.


def test_won_race_full_turn_steps_onto_cluster() -> None:
    assert Tuned is not None
    mine = [(16, 8), (16, 9)]
    foods, enemies = crowded_cluster()
    foods = foods + [(16, 0)]
    base_targets = assign(Base, mine, foods, enemies, 40, 40)
    tuned_targets = assign(Tuned, mine, foods, enemies, 40, 40)
    assert set(base_targets.values()) == {(16, 0)}
    assert set(tuned_targets.values()) <= set(foods[:2])
    assert len(tuned_targets) == 2
    base_orders = run_turn(Base, mine, enemies, 40, 40, foods)
    tuned_orders = run_turn(Tuned, mine, enemies, 40, 40, foods)
    assert tuned_orders != base_orders
    assert tuned_orders == [((16, 8), "n"), ((16, 9), "e")]
    assert base_orders == [((16, 8), "w"), ((16, 9), "e")]


# (e) near boards byte-identical ------------------------------------------------------
#
# No cluster here reaches 5 foes, so the race gate never binds:
# tuned matches base exactly, preserving duel behavior.


def test_small_boards_byte_identical_to_base() -> None:
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
            [(10, 8), (10, 9)],
            [(10, 12), (10, 13)],
            [(10, 10), (10, 11)],
            None,
            None,
            None,
        ),
        # Four foes: contested but below the crowd cap, so the
        # race gate stays out of it.
        (
            [(10, 8), (10, 9)],
            [(10, 12), (10, 13), (10, 14), (10, 15)],
            [(10, 10), (10, 11)],
            None,
            None,
            None,
        ),
    ]
    for mine, enemies, foods, water, enemy_hills, my_hills in boards:
        assert run_turn(
            Tuned, mine, enemies, 20, 20, foods, water, enemy_hills, my_hills
        ) == run_turn(Base, mine, enemies, 20, 20, foods, water, enemy_hills, my_hills)


def test_brave_take_inside_small_contest_preserved() -> None:
    # Greedy8's duel take (lone 1v1 onto food) with a 1-foe
    # presence nearby -- below the contest threshold entirely.
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
