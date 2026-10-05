#!/usr/bin/env python
"""Crowd-capped denial tests (Greedy8 entry).

Base is Greedy5: any cluster contested by DENIAL_ENEMIES (3)+
visible enemies draws exactly DENIAL_CLAIMS (2) denial claimants,
no matter how big the enemy crowd is. On crowded 10p maps that
over-triggers: two ants march into five, six, eight foes sitting
on a food cluster -- a donation, not denial. Greedy7's answer is a
distance race (cede when our nearest ant is farther than the
nearest enemy); this entry does NOT race. It caps the crowd: a
contested cluster draws denial claimants only while its visible
enemy count stays at or below DENIAL_MAX_ENEMIES (4). Five or more
foes on one cluster cedes it outright -- no claimants, foods
unclaimed -- freeing the ants to expand elsewhere.

Discriminating scenarios (fixed boards, before the bot code lands):
(a) small contest (3 foes): base and tuned both spend 2 claimants,
(b) crowd (6 foes): base spends 2, tuned spends 0 and leaves the
    foods unclaimed,
(c) boundary: 4 foes denied, 5 foes ceded,
(d) mixed: one crowded cluster ceded while a second small contest
    on the same board is still denied,
(e) near/small boards byte-identical (duel behavior preserved),
(f) a crowded full turn still runs <1s.
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Greedy5 as Base  # noqa: E402

try:
    import Greedy8 as Tuned  # noqa: E402
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
    return mod.Greedy8() if mod is Tuned else mod.Greedy5()


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


def contested_cluster(cols_food: int) -> tuple[list[Loc], list[Loc]]:
    # Two adjacent foods plus a ring of `cols_food` foes within
    # CLUSTER_R of them. Foods at (10,10),(10,11); foes march east.
    foods = [(10, 10), (10, 11)]
    enemies = [(10, 12 + i) for i in range(cols_food)]
    return foods, enemies


# one-idea discipline --------------------------------------------------------


def test_constants_identical_to_base_plus_crowd_cap() -> None:
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
    ):
        assert getattr(Tuned, name) == getattr(Base, name), name
    assert Tuned.WEIGHTS == Base.WEIGHTS
    assert Tuned.DENIAL_MAX_ENEMIES == 4


# (a) small contest preserved --------------------------------------------------


def test_small_contest_still_denied() -> None:
    # Three foes on the cluster: base and tuned both spend two
    # denial claimants. Our ants stand adjacent, so any race gate
    # would also deny here -- this scenario pins the floor, not
    # the difference.
    assert Tuned is not None
    mine = [(10, 8), (10, 9)]
    foods, enemies = contested_cluster(3)
    assert len(assign(Base, mine, foods, enemies, 30, 30)) == 2
    assert assign(Tuned, mine, foods, enemies, 30, 30) == assign(
        Base, mine, foods, enemies, 30, 30
    )


# (b) crowd ceded -----------------------------------------------------------------
#
# Six foes sit on the cluster with our ants adjacent (a race gate
# would call this winnable and deny). Base spends two claimants
# marching in; tuned spends none and leaves both foods unclaimed
# so the ants explore/expand instead.


def test_crowded_cluster_ceded() -> None:
    assert Tuned is not None
    # Geometry separates the mechanisms: foes sit 3+ steps past the
    # foods, so our ants (6-7 away) see a contested cluster but no
    # foe within COMBAT_RANGE -- no combat step can coincide with a
    # food trek. Base marches south onto the cluster; tuned, with no
    # claim, explores north instead.
    mine = [(10, 10), (10, 11)]
    foods = [(16, 10), (16, 11)]
    enemies = [(16, 14 + i) for i in range(6)]
    assert min(manhattan(40, 40, a, e) for a in mine for e in enemies) > 8
    assert len(assign(Base, mine, foods, enemies, 40, 40)) == 2
    assert assign(Tuned, mine, foods, enemies, 40, 40) == {}
    assert run_turn(Base, mine, enemies, 40, 40, foods) == [
        ((10, 10), "s"),
        ((10, 11), "s"),
    ]
    assert run_turn(Tuned, mine, enemies, 40, 40, foods) == [
        ((10, 10), "n"),
        ((10, 11), "n"),
    ]


# (c) boundary --------------------------------------------------------------------


def test_crowd_boundary_4_denied_5_ceded() -> None:
    assert Tuned is not None
    mine = [(10, 8), (10, 9)]
    foods4, enemies4 = contested_cluster(4)
    foods5, enemies5 = contested_cluster(5)
    assert len(assign(Tuned, mine, foods4, enemies4, 30, 30)) == 2
    assert assign(Tuned, mine, foods5, enemies5, 30, 30) == {}
    # Base denies both: the cap is the only difference.
    assert len(assign(Base, mine, foods4, enemies4, 30, 30)) == 2
    assert len(assign(Base, mine, foods5, enemies5, 30, 30)) == 2


# (d) mixed: cede the crowd, deny the skirmish --------------------------------------
#
# Two clusters on one board: a 6-foe crowd around (10,10)-(10,11)
# and a 3-foe skirmish around (20,20)-(20,21). Tuned denies only
# the skirmish (2 claimants on its foods); base denies both (2+2
# across four foods).


def test_mixed_board_cedes_crowd_denies_skirmish() -> None:
    assert Tuned is not None
    mine = [(10, 8), (10, 9), (20, 18), (20, 19)]
    crowd = [(10, 10), (10, 11)]
    skirmish = [(20, 20), (20, 21)]
    foods = crowd + skirmish
    enemies = [(10, 12 + i) for i in range(6)] + [(20, 22 + i) for i in range(3)]
    base_targets = assign(Base, mine, foods, enemies, 40, 40)
    assert len(base_targets) == 4
    tuned_targets = assign(Tuned, mine, foods, enemies, 40, 40)
    assert len(tuned_targets) == 2
    assert set(tuned_targets.values()) <= set(skirmish)
    assert set(base_targets.values()) & set(crowd)


# (e) near boards byte-identical ------------------------------------------------------
#
# No cluster here reaches 3 foes, so the cap never binds: tuned
# matches base exactly, preserving duel behavior.


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
    ]
    for mine, enemies, foods, water, enemy_hills, my_hills in boards:
        assert run_turn(
            Tuned, mine, enemies, 20, 20, foods, water, enemy_hills, my_hills
        ) == run_turn(Base, mine, enemies, 20, 20, foods, water, enemy_hills, my_hills)


def test_brave_take_inside_small_contest_preserved() -> None:
    # Greedy5's duel take (lone 1v1 onto food) with a 2-foe
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
