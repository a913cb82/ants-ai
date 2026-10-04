#!/usr/bin/env python
"""Weaker-lure tuning tests (Greedy2 entry).

Base is the delineate greedy-fields champion: 1/(1+d^2) food /
enemy / hill / unseen fields plus a kill bonus gated on strict
local superiority, with enemy-field weight 2.0. The census reads
the lure marches ants into masses, so Greedy2 lowers only the
enemy-field weight to 0.5. Kill bonus, strict-superiority gate,
and every other weight are unchanged.

Proves, on fixed boards before the bot code lands:
(a) a board where base steps toward the enemy and tuned holds
    back (takes nearby food instead),
(b) kill-bonus boards behave byte-identically to base,
(c) food / hill / unseen boards behave byte-identically,
(d) per-move scoring <0.5ms and a crowded full turn <1s.
"""

import os
import sys
import time
from types import ModuleType
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Greedy as Base  # noqa: E402
import Greedy2 as Tuned  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}


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
        return Tuned.Greedy2()
    return Base.Greedy()


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


def open_passable(loc: Loc) -> bool:
    return True


def flat_sq(a: Loc, b: Loc) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def score_all(
    mod: ModuleType, ant: Loc, own: list[Loc], enemies: list[Loc], foods: set[Loc]
) -> dict[str, float]:
    opts = {
        "-": ant,
        "e": (ant[0], ant[1] + 1),
        "w": (ant[0], ant[1] - 1),
        "n": (ant[0] - 1, ant[1]),
        "s": (ant[0] + 1, ant[1]),
    }
    return {
        d: mod.score_move(
            loc,
            ant,
            own,
            enemies,
            foods,
            set(),
            None,
            open_passable,
            flat_sq,
            5,
            20,
            20,
        )
        for d, loc in opts.items()
    }


# tuning constants -----------------------------------------------------------


def test_enemy_weight_lowered_to_half() -> None:
    assert Base.W_ENEMY == 2.0
    assert Tuned.W_ENEMY == 0.5
    assert Tuned.WEIGHTS == (1.0, 0.5, 3.0, 0.1)


def test_everything_else_identical_to_base() -> None:
    for name in (
        "W_FOOD",
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


# (a) weaker lure holds back -------------------------------------------------
#
# Ant (10,10), foe (10,12), food (10,8), second ant (10,7) takes the
# food claim. Hand-computed, visits-free: east gains enemy 0.3 but
# loses food 0.3; base values the enemy swing at 2.0 (0.6 > 0.3, so
# it marches east into the foe) while tuned values it at 0.5
# (0.15 < 0.3, so west to the food wins and it holds back).


def test_base_marches_east_tuned_steps_west_to_food() -> None:
    ant = (10, 10)
    own = [ant, (10, 7)]
    enemies = [(10, 12)]
    foods = {(10, 8)}
    base = score_all(Base, ant, own, enemies, foods)
    tuned = score_all(Tuned, ant, own, enemies, foods)
    assert base["e"] == pytest.approx(1.1)
    assert base["w"] == pytest.approx(0.7)
    assert base["-"] == pytest.approx(0.6)
    assert tuned["w"] == pytest.approx(0.55)
    assert tuned["e"] == pytest.approx(0.35)
    assert tuned["-"] == pytest.approx(0.3)
    assert Base.pick_best(base) == "e"
    assert Tuned.pick_best(tuned) == "w"


def test_do_turn_base_advances_tuned_holds_back() -> None:
    mine = [(10, 10), (10, 7)]
    enemies = [(10, 12)]
    foods = [(10, 8)]
    base_orders = run_turn(Base, mine, enemies, foods)
    tuned_orders = run_turn(Tuned, mine, enemies, foods)
    assert base_orders[0] == ((10, 10), "e")
    assert tuned_orders[0] == ((10, 10), "w")
    probe = FakeAnts(mine, enemies, foods)
    base_after = probe.distance(probe.destination(*base_orders[0]), enemies[0])
    tuned_after = probe.distance(probe.destination(*tuned_orders[0]), enemies[0])
    before = probe.distance(mine[0], enemies[0])
    assert base_after < before
    assert tuned_after >= before


# (b) kill bonus unchanged ----------------------------------------------------


def test_kill_bonus_constant_and_gate_unchanged() -> None:
    assert Tuned.KILL_BONUS == Base.KILL_BONUS == 2.0


def test_tuned_kill_bonus_fires_only_with_strict_superiority() -> None:
    # Same board as the base gate test: dest (5,6) touches one foe
    # at (5,7). Lone, ours is 1 == 1 and the score stays
    # field-only (food 0.1, weak enemy 0.5 * 0.5 = 0.25); packed,
    # ours is 2 > 1 and exactly KILL_BONUS is added.
    dest = (5, 6)
    mover = (5, 5)
    foods = {(5, 9)}
    lone = Tuned.score_move(
        dest,
        mover,
        [mover],
        [(5, 7)],
        foods,
        set(),
        None,
        open_passable,
        flat_sq,
        5,
        20,
        20,
    )
    packed = Tuned.score_move(
        dest,
        mover,
        [mover, (6, 6)],
        [(5, 7)],
        foods,
        set(),
        None,
        open_passable,
        flat_sq,
        5,
        20,
        20,
    )
    assert lone == pytest.approx(0.1 + 0.25)
    assert packed - lone == pytest.approx(2.0)


def test_packed_advance_byte_identical_to_base() -> None:
    # Strict superiority (2v1 at the step): both march east onto
    # (5,6) with the exact same full order list.
    mine = [(5, 5), (5, 4)]
    enemies = [(5, 7)]
    assert run_turn(Tuned, mine, enemies) == run_turn(Base, mine, enemies)
    assert run_turn(Base, mine, enemies)[0] == ((5, 5), "e")


def test_lone_equality_boards_byte_identical_to_base() -> None:
    # No superiority anywhere: lone ant, one foe and one far food.
    # Neither earns the bonus, so both hold back together.
    for mine, enemies, foods in (
        ([(5, 5)], [(5, 7)], [(5, 9)]),
        ([(5, 5)], [(5, 7), (6, 8)], [(0, 0)]),
        ([(5, 5), (0, 0)], [(5, 7)], [(19, 19)]),
    ):
        assert run_turn(Tuned, mine, enemies, foods) == run_turn(
            Base, mine, enemies, foods
        )


# (c) food / hill / unseen boards byte-identical -------------------------------


def test_scores_identical_without_enemies() -> None:
    # No foes in the field: the enemy weight cannot matter, so every
    # candidate square scores exactly like base.
    ant = (10, 10)
    own = [ant, (0, 0)]
    foods = {(10, 12), (3, 3)}
    hills = {(19, 19)}
    visits = {(10, 10): 1, (10, 11): 2}
    for dest in [(10, 10), (10, 11), (10, 9), (9, 10), (11, 10)]:
        kwargs = {
            "passable": open_passable,
            "sq_dist": flat_sq,
            "attack_r2": 5,
            "rows": 20,
            "cols": 20,
        }
        assert Tuned.score_move(
            dest,
            ant,
            own,
            [],
            foods,
            hills,
            visits,
            **kwargs,
        ) == Base.score_move(
            dest,
            ant,
            own,
            [],
            foods,
            hills,
            visits,
            **kwargs,
        )


def test_quiet_boards_byte_identical_to_base() -> None:
    # No foe within combat range anywhere: combat never fires, so
    # food claims, guard, muster, explore, and walk-off match base
    # order for order.
    boards = [
        ([(0, 0), (0, 19)], [], [(0, 1), (0, 18)], None, None, None),
        ([(0, 0)], [], None, None, [(10, 10)], None),
        ([(5, 5)], [(15, 15)], None, None, None, None),
        ([(3, 3)], [], None, None, None, [(3, 3)]),
        ([(5, 5)], [(2, 5)], None, None, None, [(2, 2)]),
    ]
    for mine, enemies, foods, water, enemy_hills, my_hills in boards:
        assert run_turn(
            Tuned, mine, enemies, foods, water, enemy_hills, my_hills
        ) == run_turn(Base, mine, enemies, foods, water, enemy_hills, my_hills)


# (d) speed --------------------------------------------------------------------


def test_per_move_scoring_under_half_ms() -> None:
    rows = cols = 30
    water = {(15, c) for c in range(30) if c != 15}

    def passable(loc: Loc) -> bool:
        return loc not in water

    def sq(a: Loc, b: Loc) -> int:
        dr = abs(a[0] - b[0])
        dr = min(dr, rows - dr)
        dc = abs(a[1] - b[1])
        dc = min(dc, cols - dc)
        return dr * dr + dc * dc

    enemies = [(r, c) for r in range(5, 25, 2) for c in range(5, 25, 3)][:60]
    foods = {(r, c) for r in range(0, 30, 3) for c in range(0, 30, 4)}
    hills = {(0, 0), (29, 29)}
    visits = {(r, c): 1 for r in range(12, 18) for c in range(12, 18)}
    own = [(15, 14), (14, 15), (16, 15)]
    Tuned.score_move(
        (15, 15),
        (15, 14),
        own,
        enemies,
        foods,
        hills,
        visits,
        passable,
        sq,
        5,
        rows,
        cols,
    )
    reps = 200
    start = time.perf_counter()
    for _ in range(reps):
        Tuned.score_move(
            (15, 15),
            (15, 14),
            own,
            enemies,
            foods,
            hills,
            visits,
            passable,
            sq,
            5,
            rows,
            cols,
        )
    mean_ms = (time.perf_counter() - start) / reps * 1000
    assert mean_ms < 0.5


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
