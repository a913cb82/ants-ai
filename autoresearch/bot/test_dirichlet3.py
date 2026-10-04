#!/usr/bin/env python
"""Dirichlet3 bigger-fight-budget tests (test-first for the tuning idea).

Self-contained: stdlib plus Dirichlet2.py plus Dirichlet3.py plus
ants.py only. Dirichlet3 is Dirichlet2 with exactly one idea --
FIGHT_BUDGET raised from 5ms to 15ms per combat decision, so more
Dirichlet draws score more moves now that suicides are vetoed.
Everything else is identical to Dirichlet2.

(a) Seeded decisions draw strictly more samples than base: under a
    mock clock (a fixed 1ms tick per perf_counter read) a counting
    RNG records strictly more Dirichlet draws for Dirichlet3 than
    for Dirichlet2 on every seed; the module budget is exactly 3x
    base (15ms vs 5ms) and both sample_fight_move defaults track
    their module constant.
(b) Plentiful-time full turns match base move-for-move on quiet
    boards (no enemies, and distant enemies outside the
    battle-local radius): identical orders across seeds and across
    a multi-turn scripted sequence, so no behavior change
    off-contact.
(c) Per-decision wall time stays under 20ms on crowded skirmishes
    (a 5v4 and a dense 6v5 mutually-local battle).
(d) Full turn stays under 1s on a crowded 48v30 board.
"""

import inspect
import os
import random
import sys
import time
from typing import Any
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Dirichlet2 as D2  # noqa: E402
import Dirichlet3 as D3  # noqa: E402

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

    def set_enemies(self, enemies: list[Loc]) -> None:
        self._enemies = list(enemies)

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


def _sq(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


class CountingRng(random.Random):
    """Seeded RNG that counts Dirichlet gamma draws.

    Subclasses Random without touching random(), so the stream is
    identical to Random(seed); every dirichlet_sample call costs
    exactly five gammavariate calls, so gamma_calls // 5 is the
    sample count.
    """

    def __init__(self, seed: int) -> None:
        super().__init__(seed)
        self.gamma_calls = 0

    def gammavariate(self, alpha: float, beta: float) -> float:
        self.gamma_calls += 1
        return super().gammavariate(alpha, beta)


class FakeClock:
    """Mock perf_counter advancing a fixed tick per read.

    sample_fight_move reads the clock once for the deadline and
    once per sampling iteration, so with tick dt the iteration
    count is deterministic: ceil(budget / dt) draws per decision.
    """

    def __init__(self, dt: float) -> None:
        self.t = 0.0
        self.dt = dt

    def __call__(self) -> float:
        self.t += self.dt
        return self.t


def _samples(
    mod: Any, ant: Loc, mine: list[Loc], foes: list[Loc], seed: int
) -> tuple[str, int]:
    """One combat decision under the mock clock: (move, draws)."""
    probe = FakeAnts(mine, foes)
    rng = CountingRng(seed)
    with mock.patch("time.perf_counter", FakeClock(0.001)):
        move = mod.sample_fight_move(
            ant,
            mine,
            foes,
            5,
            probe.distance,
            _sq,
            probe.destination,
            probe.passable,
            probe.unoccupied,
            set(),
            ROWS,
            COLS,
            rng,
        )
    assert rng.gamma_calls % 5 == 0
    return move, rng.gamma_calls // 5


# Pinned contact front (from the Dirichlet2 suite): mover (19, 11)
# with foes (19, 13), (19, 12), (0, 12). Legal steps exist and a
# local battle is on, so the sampler always draws; the suicide
# veto may remap the move, but the draw count is veto-independent.
MINE_C = [(19, 11), (17, 12), (16, 12)]
FOES_C = [(19, 13), (19, 12), (0, 12)]
MOVER_C: Loc = (19, 11)


def test_budget_is_triple_and_default() -> None:
    # (a) The one idea: 15ms per combat decision, exactly 3x the
    # 5ms base, and both entry points default to their constant.
    assert D2.FIGHT_BUDGET == 0.005
    assert D3.FIGHT_BUDGET == 0.015
    assert D3.FIGHT_BUDGET == 3 * D2.FIGHT_BUDGET
    for mod in (D2, D3):
        param = inspect.signature(mod.sample_fight_move).parameters["budget"]
        assert param.default == mod.FIGHT_BUDGET


def test_seeded_decisions_draw_strictly_more_samples() -> None:
    # (a) Under the mock clock the draw count is exact: 5 draws at
    # the 5ms base budget, 15 at the 15ms budget -- strictly more
    # on every seed, with a legal move returned either way.
    for seed in range(10):
        base_move, base_n = _samples(D2, MOVER_C, MINE_C, FOES_C, seed)
        big_move, big_n = _samples(D3, MOVER_C, MINE_C, FOES_C, seed)
        assert base_n == 5, (seed, base_n)
        assert big_n == 15, (seed, big_n)
        assert big_n > base_n
        for move in (base_move, big_move):
            assert move in ("n", "e", "s", "w", "hold")


def _run_turn(mod: Any, seed: int, fake: FakeAnts) -> list[tuple[Loc, str]]:
    bot = mod.Dirichlet2(seed=seed) if mod is D2 else mod.Dirichlet3(seed=seed)
    bot.do_setup(fake)
    fake.orders = []
    bot.do_turn(fake)
    return list(fake.orders)


def test_quiet_boards_match_base_move_for_move() -> None:
    # (b) No contact, no sampling: with no enemies -- or with
    # every enemy outside the battle-local radius -- neither entry
    # draws, so full turns agree exactly across seeds, with food,
    # water, and remembered hills in play.
    mine = [(2, 2), (2, 5), (8, 8), (15, 15)]
    foods = [(3, 3), (9, 9), (14, 14)]
    water = {(4, 4), (4, 5)}
    far_foes = [(12, 0), (0, 12), (10, 18)]
    for seed in range(10):
        for foes in ([], far_foes):
            probe = FakeAnts(mine, foes, foods, water, [(18, 18)], [(2, 3)])
            for foe in foes:
                assert all(probe.distance(a, foe) > 6 for a in mine)
            assert _run_turn(D2, seed, probe) == _run_turn(D3, seed, probe)


def test_quiet_multiturn_sequence_matches_base() -> None:
    # (b) The match holds across turns: enemies patrol but stay
    # distant, so both RNG streams stay in lockstep and every
    # turn's orders agree -- no behavior change off-contact.
    mine = [(2, 2), (2, 5), (8, 8), (15, 15)]
    foods = [(3, 3), (9, 9), (14, 14)]
    patrol = [
        [(12, 0), (0, 12), (10, 18)],
        [(12, 2), (2, 12), (8, 16)],
        [(14, 2), (2, 14), (8, 0)],
        [(13, 0), (0, 13), (12, 19)],
        [(12, 0), (0, 12), (10, 18)],
    ]
    bots = {id(D2): D2.Dirichlet2(seed=3), id(D3): D3.Dirichlet3(seed=3)}
    fakes = {
        id(D2): FakeAnts(mine, patrol[0], foods, None, [(18, 18)], [(2, 3)]),
        id(D3): FakeAnts(mine, patrol[0], foods, None, [(18, 18)], [(2, 3)]),
    }
    for mod in (D2, D3):
        bots[id(mod)].do_setup(fakes[id(mod)])
    for foes in patrol:
        orders = {}
        for mod in (D2, D3):
            fake = fakes[id(mod)]
            fake.set_enemies(foes)
            for foe in foes:
                assert all(fake.distance(a, foe) > 6 for a in mine)
            fake.orders = []
            bots[id(mod)].do_turn(fake)
            orders[id(mod)] = list(fake.orders)
        assert orders[id(D2)] == orders[id(D3)]


# Crowded skirmishes: every ant mutually local, so each decision
# scores real provisional battles under the 15ms budget.
SKIRMISH_5V4 = (
    [(5, 5), (5, 6), (5, 7), (6, 6), (4, 6)],
    [(5, 8), (6, 8), (4, 8), (6, 9)],
    (5, 6),
)
SKIRMISH_6V5 = (
    [(10, 10), (10, 11), (10, 12), (11, 10), (11, 11), (11, 12)],
    [(10, 13), (11, 13), (12, 11), (12, 12), (9, 12)],
    (11, 11),
)


def test_per_decision_under_20ms_crowded() -> None:
    # (c) One combat decision on a crowded skirmish stays under
    # 20ms wall time: the 15ms budget plus one memoized
    # resolution overshoot, with a legal move returned.
    for mine, foes, ant in (SKIRMISH_5V4, SKIRMISH_6V5):
        probe = FakeAnts(mine, foes)
        worst = 0.0
        for seed in range(10):
            start = time.perf_counter()
            move = D3.sample_fight_move(
                ant,
                mine,
                foes,
                5,
                probe.distance,
                _sq,
                probe.destination,
                probe.passable,
                probe.unoccupied,
                set(),
                ROWS,
                COLS,
                random.Random(seed),
            )
            worst = max(worst, time.perf_counter() - start)
            assert move in ("n", "e", "s", "w", "hold")
            if move != "hold":
                assert probe.unoccupied(probe.destination(ant, move))
        assert worst < 0.020, (ant, worst)


def test_full_turn_under_1s_crowded() -> None:
    # (d) A full crowded turn (48 ours vs 30 foes, food and hills
    # in play) still decides in under a second.
    for seed in (7, 8):
        mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
        foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
        foods = [((i * 3 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(20)]
        fake = FakeAnts(mine, foes, foods, enemy_hills=[(15, 15)], my_hills=[(10, 10)])
        bot = D3.Dirichlet3(seed=seed)
        bot.do_setup(fake)
        start = time.perf_counter()
        bot.do_turn(fake)
        assert time.perf_counter() - start < 1.0
        assert len(fake.orders) > 0
