#!/usr/bin/env python
"""Race-gated denial tests (Greedy7 entry).

Base is Greedy5: range-gated food plus denial that spends
DENIAL_CLAIMS ants on EVERY cluster with DENIAL_ENEMIES+ foes
nearby -- no matter who wins the race to it. On open 10p maps
the range gate rarely binds (food is everywhere within 25), but
enemies are everywhere too, so every cluster reads as contested
and the whole army treks into crowds it cannot beat: denial
over-triggers exactly where greedy must expand to contend.

Greedy7 adds one mechanism -- race-gated (winnable) denial: a
contested cluster draws denial claimants only when our nearest
ant stands no farther from the cluster than the nearest visible
enemy (ties still deny, so duel middle-food races are
preserved). A cluster we are losing is ceded outright -- zero
claimants and its foods stay unclaimed this turn, so the ants
fall through to guard/combat/muster/explore instead of marching
into a lost fight.

Proves, on fixed boards before the bot code lands:
(a) lost race: foes sitting on the food, our ants far -- base
    spends two denial claimants trekking, tuned spends none and
    its ants explore instead,
(b) won race: our ants adjacent, foes farther -- tuned denies
    exactly like base,
(c) tie race: equal distances -- tuned still denies like base,
(d) split: two contested clusters, one winnable and one lost --
    base claims on both, tuned only on the winnable one,
(e) duel boards byte-identical (no-contest boards plus a won
    race: tuned matches base move for move),
(f) a crowded full turn still runs <1s.
"""

import os
import sys
import time
from types import ModuleType
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Greedy5 as Base  # noqa: E402
import Greedy7 as Tuned  # noqa: E402

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
        return Tuned.Greedy7()
    return Base.Greedy5()


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
        "BRAVE_OBJECTIVE_R",
        "FOOD_RADIUS",
    ):
        assert getattr(Tuned, name) == getattr(Base, name), name
    assert Tuned.WEIGHTS == Base.WEIGHTS
    assert Tuned.DENIAL_RACE_MARGIN == 0


# (a) lost race: cede the cluster -------------------------------------------------
#
# Foes sit on a two-food cluster (their best distance 1) while our
# two ants stand ~29 away. Base spends both denial claimants on a
# cross-map trek; tuned cedes the cluster outright -- zero claims
# -- and both ants explore north (fresh-visits tie order) instead
# of marching into the crowd.


def test_lost_race_base_denies_tuned_cedes() -> None:
    assert Tuned is not None
    mine = [(10, 5), (12, 5)]
    foods = [(10, 15), (10, 16)]
    enemies = [(10, 17), (10, 18), (11, 17)]
    ours, theirs = race(mine, foods, enemies, 40, 40)
    assert (ours, theirs) == (10, 1)
    assert len(assign(Base, mine, foods, enemies, 60, 60)) == 2
    assert assign(Tuned, mine, foods, enemies, 60, 60) == {}
    tuned_orders = run_turn(Tuned, mine, enemies, 40, 40, foods)
    by_start = dict(tuned_orders)
    assert by_start[(10, 5)] == "n"
    assert by_start[(12, 5)] == "n"
    base_orders = run_turn(Base, mine, enemies, 40, 40, foods)
    base_by_start = dict(base_orders)
    for ant in mine:
        before = min(manhattan(40, 40, ant, f) for f in foods)
        dest = (
            (ant[0] + AIM[base_by_start[ant]][0]) % 40,
            (ant[1] + AIM[base_by_start[ant]][1]) % 40,
        )
        after = min(manhattan(40, 40, dest, f) for f in foods)
        assert after == before - 1  # base treks closer; tuned walked away


# (b) won race: deny exactly like base ----------------------------------------------
#
# Same cluster shape, but our ants stand adjacent (our best 1)
# while the foes lurk 3+ away. Tuned must deny byte-identically.


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


# (c) tie race: still denies ----------------------------------------------------------
#
# Equal best distances: the duel middle-food case. Ties must keep
# denying so head-to-head races play exactly like base.


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


# (d) split clusters: deny the winnable one, cede the lost one --------------------------
#
# Two contested clusters: our ant stands next to cluster 1 (won)
# while cluster 2's foes sit on its food (lost). Base claims on
# both; tuned claims only on cluster 1, and its far ant explores
# instead of trekking.


def test_split_clusters_base_claims_both_tuned_claims_won() -> None:
    assert Tuned is not None
    mine = [(5, 8), (30, 20)]
    foods1 = [(5, 10), (5, 11)]
    foes1 = [(5, 16), (5, 17), (6, 16)]
    foods2 = [(30, 40), (30, 41)]
    foes2 = [(30, 42), (30, 43), (31, 42)]
    foods = foods1 + foods2
    enemies = foes1 + foes2
    ours1, theirs1 = race(mine, foods1, foes1, 60, 60)
    assert ours1 < theirs1
    ours2, theirs2 = race(mine, foods2, foes2, 60, 60)
    assert ours2 > theirs2
    # Ant 1 stands 19 off cluster 2: inside FOOD_RADIUS, so base
    # spends a denial claimant trekking; tuned cedes it. Foes sit
    # 22+ away from ant 1, so combat does not pull it either.
    assert manhattan(60, 60, (30, 20), (30, 40)) == 20
    base_targets = assign(Base, mine, foods, enemies, 60, 60)
    assert set(base_targets.values()) == {(5, 10), (30, 40)}
    tuned_targets = assign(Tuned, mine, foods, enemies, 60, 60)
    assert tuned_targets == {0: (5, 10)}
    tuned_orders = run_turn(Tuned, mine, enemies, 60, 60, foods)
    by_start = dict(tuned_orders)
    assert by_start[(5, 8)] == "e"  # steps onto the winnable race
    assert by_start[(30, 20)] == "n"  # far ant explores, not treks


# (e) duel boards byte-identical ----------------------------------------------------------
#
# Boards with no contested cluster never reach the race gate, and
# a won race denies exactly like base: tuned matches base
# move for move, so duel behavior is preserved.


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
