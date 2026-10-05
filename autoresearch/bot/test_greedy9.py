#!/usr/bin/env python
"""Strength-gated denial-release tests (Greedy9 entry).

Base is Greedy4: contested food clusters (DENIAL_ENEMIES+ foes
within CLUSTER_R of a member food) draw exactly DENIAL_CLAIMS
claimants; the cluster's other foods stay unclaimed. The cap is
blind to force ratio: even when our ants locally outnumber the
foes around a cluster -- a winning take -- the extra foods are
still withheld, and in a crowded 10p census those idle ants lose
the expansion race instead of converting a won fight into food.

Greedy9 adds one mechanism -- strength-gated denial release: a
contested cluster whose nearby own ants (within CLUSTER_R of a
member food, the same metric as the foe count) strictly outnumber
its contesting foes is released to full greedy claiming. Tied or
losing clusters keep the champion cap. No food-radius gate
anywhere: this differs from Greedy5/Greedy7/Greedy8 (range gate,
distance race, crowd cede) by gating on counted force, not
distance.

Proves, on fixed boards before the bot code lands:
(a) winning take: 5 ours vs 3 foes on a 3-food cluster -- base
    claims 2, tuned claims all 3 (recovers the refused take),
(b) release helper marks exactly the winning cluster,
(c) tie (ours == theirs) still denied -- tuned == base,
(d) losing cluster (ours < theirs) still denied -- tuned == base,
(e) uncontested / quiet boards byte-identical,
(f) full-turn: tuned sends a third claimant at the won cluster
    while base leaves that ant off-cluster; crowded turn <1s.
"""

import os
import sys
import time
from types import ModuleType
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Greedy4 as Base  # noqa: E402
import Greedy9 as Tuned  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}


def torus(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


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
        self.attackradius2 = 5
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
        return torus(a, b)

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
        return Tuned.Greedy9()
    return Base.Greedy4()


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


def targets(
    mod: ModuleType, mine: list[Loc], foods: list[Loc], enemies: list[Loc]
) -> dict[int, Loc]:
    return mod.assign_food_targets(mine, foods, enemies, torus, ROWS, COLS)


# Shared boards ---------------------------------------------------------------
#
# One 3-food cluster (pairwise gaps 2, well within CLUSTER_R=8, far
# from any seam on the 20x20 torus): foods (10,10), (10,12),
# (10,14). Foes loitering on the cluster: (10,11), (11,11),
# (9,11) -- each within 8 of a member food, so the cluster is
# contested (3 >= DENIAL_ENEMIES).

CLUSTER = [(10, 10), (10, 12), (10, 14)]
FOES3 = [(10, 11), (11, 11), (9, 11)]
WIN_MINE = [(10, 8), (10, 9), (11, 10), (9, 9), (10, 7)]


def test_contested_cluster_setup() -> None:
    # Sanity: the shared boards really are contested under base.
    groups = Base.denied_food_groups(CLUSTER, FOES3, torus, ROWS, COLS)
    assert len(groups) == 1 and sorted(groups[0]) == [0, 1, 2]


# one-idea discipline ---------------------------------------------------------


def test_constants_identical_to_base_plus_strength_margin() -> None:
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
    assert "FOOD_RADIUS" not in dir(Tuned)
    assert Tuned.DENIAL_STRENGTH_MARGIN == 0


# (a) winning take: the refused third food is recovered --------------------------


def test_base_caps_won_cluster_at_two() -> None:
    got = targets(Base, WIN_MINE, CLUSTER, FOES3)
    assert sorted(got.values()) == [(10, 10), (10, 12)]


def test_tuned_claims_all_won_cluster_foods() -> None:
    got = targets(Tuned, WIN_MINE, CLUSTER, FOES3)
    assert sorted(got.values()) == [(10, 10), (10, 12), (10, 14)]


# (b) the release helper marks exactly the winning cluster ------------------------


def test_released_groups_marks_winning_cluster_only() -> None:
    far_cluster = [(0, 0), (0, 2)]
    foods = CLUSTER + far_cluster
    foes = FOES3 + [(0, 1), (1, 1), (19, 1)]
    released = Tuned.released_food_groups(WIN_MINE, foods, foes, torus, ROWS, COLS)
    assert len(released) == 1
    assert sorted(foods[i] for i in released[0]) == sorted(CLUSTER)


def test_no_release_without_contest() -> None:
    assert Tuned.released_food_groups(WIN_MINE, CLUSTER, [], torus, ROWS, COLS) == []
    assert (
        Tuned.released_food_groups(WIN_MINE, CLUSTER, [(10, 11)], torus, ROWS, COLS)
        == []
    )


# (c) tie still denied -------------------------------------------------------------


def test_tie_cluster_byte_identical_to_base() -> None:
    mine = [(10, 8), (10, 9), (11, 10)]  # 3 near vs 3 foes: tie
    assert targets(Tuned, mine, CLUSTER, FOES3) == targets(Base, mine, CLUSTER, FOES3)
    assert len(targets(Tuned, mine, CLUSTER, FOES3)) == 2


# (d) losing cluster still denied -----------------------------------------------------


def test_losing_cluster_byte_identical_to_base() -> None:
    mine = [(10, 8), (0, 0), (0, 19), (19, 0)]  # 1 near vs 5 foes
    foes = FOES3 + [(11, 12), (9, 13)]
    assert targets(Tuned, mine, CLUSTER, foes) == targets(Base, mine, CLUSTER, foes)
    assert len(targets(Tuned, mine, CLUSTER, foes)) == 2


def test_losing_cluster_full_turn_byte_identical() -> None:
    mine = [(10, 8), (0, 0), (0, 19), (19, 0)]
    foes = FOES3 + [(11, 12), (9, 13)]
    assert run_turn(Tuned, mine, foes, CLUSTER) == run_turn(Base, mine, foes, CLUSTER)


# (e) uncontested and quiet boards byte-identical --------------------------------------


def test_uncontested_boards_byte_identical_to_base() -> None:
    boards = [
        (WIN_MINE, [], CLUSTER),
        (WIN_MINE, [(10, 11)], CLUSTER),
        (WIN_MINE, [(10, 11), (11, 11)], CLUSTER),
        ([(0, 0), (0, 19)], [], [(0, 1), (0, 18)]),
        ([(5, 5)], [(15, 15)], [(5, 6)]),
    ]
    for mine, enemies, foods in boards:
        assert targets(Tuned, mine, foods, enemies) == targets(
            Base, mine, foods, enemies
        )
        assert run_turn(Tuned, mine, enemies, foods) == run_turn(
            Base, mine, enemies, foods
        )


def test_quiet_full_turns_byte_identical_to_base() -> None:
    boards = [
        ([(0, 0)], [], None, None, [(10, 10)], None),
        ([(5, 5)], [(15, 15)], None, None, None, None),
        ([(3, 3)], [], None, None, None, [(3, 3)]),
        ([(10, 10)], [(10, 12)], [(10, 13)], None, None, None),
        ([(5, 5)], [(5, 7)], None, None, [(5, 8)], None),
    ]
    for mine, enemies, foods, water, enemy_hills, my_hills in boards:
        assert run_turn(
            Tuned, mine, enemies, foods, water, enemy_hills, my_hills
        ) == run_turn(Base, mine, enemies, foods, water, enemy_hills, my_hills)


# (f) full-turn effect and speed ----------------------------------------------------------


def test_full_turn_sends_third_claimant_at_won_cluster() -> None:
    # Foes contest from afar (safe food paths, no collisions): base
    # caps the won cluster at 2 and the fourth ant explores south;
    # tuned releases it and that ant steps east toward (10,14).
    mine = [(10, 4), (8, 10), (12, 10), (6, 12)]
    foes = [(10, 17), (12, 15), (8, 15)]
    assert targets(Tuned, mine, CLUSTER, foes) != targets(Base, mine, CLUSTER, foes)
    base_orders = run_turn(Base, mine, foes, CLUSTER)
    tuned_orders = run_turn(Tuned, mine, foes, CLUSTER)
    assert ((6, 12), "s") in base_orders
    assert ((6, 12), "e") in tuned_orders


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
