#!/usr/bin/env python
"""Dirichlet4 small-fights-only sampling tests (test-first for the tuning idea).

Self-contained: stdlib plus Dirichlet3.py plus Dirichlet4.py plus
ants.py only. Dirichlet4 is Dirichlet3 with exactly one idea --
run the Dirichlet sampler ONLY with fewer than 10 enemies visible;
with 10+ visible, skip the combat block entirely (no Dirichlet
draws, no provisional resolutions) and fall through to the static
champion safety (strict superiority + 10-near equal gate).
Everything else is identical to Dirichlet3.

(a) A 12-enemy board never samples: the sampler spy records zero
    calls, orders match base-with-sampler-held-out exactly, and
    every step passes is_safe_step.
(b) A 5-enemy board samples exactly as base: seeded equality of
    full-turn orders across seeds, with the sampler running.
(c) Boundary: 9 visible enemies sample like base; a 10th (distant)
    foe disables sampling and matches static orders.
(d) A crowded 48v30 full turn stays under 1s without sampling.
"""

import inspect
import os
import sys
import time
from typing import Any
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Dirichlet3 as D3  # noqa: E402
import Dirichlet4 as D4  # noqa: E402

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


def _sq(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


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


def _run_turn(mod: Any, seed: int, fake: FakeAnts) -> list[tuple[Loc, str]]:
    cls = D4.Dirichlet4 if mod is D4 else D3.Dirichlet3
    bot = cls(seed=seed)
    bot.do_setup(fake)
    fake.orders = []
    bot.do_turn(fake)
    return list(fake.orders)


def _run_turn_clocked(mod: Any, seed: int, fake: FakeAnts) -> list[tuple[Loc, str]]:
    """Full turn under the mock clock, so sampling draws are exact."""
    with mock.patch("time.perf_counter", FakeClock(0.001)):
        return _run_turn(mod, seed, fake)


def _static_orders(mod: Any, seed: int, fake: FakeAnts) -> list[tuple[Loc, str]]:
    """Full-turn orders with the sampler held out (static safety only)."""
    with mock.patch.object(mod, "sample_fight_move", return_value="hold"):
        return _run_turn(mod, seed, fake)


# (a) board: two of ours near four foes (one in attack range), two
# of ours far away exploring freely, plus eight distant foes that
# push the visible count to 12 without touching local tactics.
MINE_A = [(5, 5), (5, 6), (15, 15), (15, 16)]
FOES_A = [
    (5, 8),
    (6, 8),
    (4, 8),
    (5, 7),
    (0, 0),
    (0, 19),
    (19, 0),
    (19, 19),
    (10, 0),
    (0, 10),
    (19, 10),
    (10, 19),
]

# (b) board: three of ours in a real local battle with five foes.
MINE_B = [(5, 5), (5, 6), (6, 6)]
FOES_B = [(5, 8), (6, 8), (4, 8), (6, 9), (4, 9)]

# (c) boards: boundary layout, 9 near foes, plus one distant foe.
MINE_C = [(10, 10), (10, 11), (11, 10)]
FOES_9 = [
    (10, 13),
    (11, 13),
    (12, 11),
    (12, 12),
    (9, 12),
    (12, 10),
    (9, 10),
    (8, 11),
    (12, 13),
]
FOES_10 = FOES_9 + [(0, 0)]


def test_crowded_board_never_samples() -> None:
    # (a) 12 visible enemies: the sampler is never called, yet the
    # turn still issues (safe, distant) orders.
    assert len(FOES_A) == 12
    for seed in range(5):
        fake = FakeAnts(MINE_A, FOES_A)
        bot = D4.Dirichlet4(seed=seed)
        bot.do_setup(fake)
        with mock.patch.object(D4, "sample_fight_move") as spy:
            spy.side_effect = AssertionError("no sampling with 12 visible")
            bot.do_turn(fake)
        assert spy.call_count == 0
        assert len(fake.orders) > 0


def test_crowded_board_matches_static_safety_orders() -> None:
    # (a) The crowded turn matches base-with-sampler-held-out
    # exactly, and every issued step passes the static majority
    # filter (strict superiority + 10-near equal gate).
    for seed in range(5):
        d4_orders = _run_turn(D4, seed, FakeAnts(MINE_A, FOES_A))
        static_orders = _static_orders(D3, seed, FakeAnts(MINE_A, FOES_A))
        assert d4_orders == static_orders
        assert len(d4_orders) > 0
        probe = FakeAnts(MINE_A, FOES_A)
        mine = probe.my_ants()
        foes = [loc for loc, _ in probe.enemy_ants()]
        for loc, direction in d4_orders:
            nloc = probe.destination(loc, direction)
            assert D4.is_safe_step(nloc, loc, mine, foes, 5, _sq, probe.distance)


def test_crowded_board_base_would_sample() -> None:
    # Sanity: the (a) board reaches the combat block in base (one
    # sampler call per ant), so zero calls above is the gate
    # working, not an unreachable block.
    for seed in range(3):
        fake = FakeAnts(MINE_A, FOES_A)
        bot = D3.Dirichlet3(seed=seed)
        bot.do_setup(fake)
        with mock.patch.object(D3, "sample_fight_move", return_value="hold") as spy:
            bot.do_turn(fake)
        assert spy.call_count == len(MINE_A)


def test_small_fight_samples_exactly_as_base() -> None:
    # (b) 5 visible enemies: the sampler runs for every ant and
    # full-turn orders match base exactly across seeds.
    assert len(FOES_B) == 5
    for seed in range(10):
        expected = _run_turn_clocked(D3, seed, FakeAnts(MINE_B, FOES_B))
        fake = FakeAnts(MINE_B, FOES_B)
        bot = D4.Dirichlet4(seed=seed)
        bot.do_setup(fake)
        with (
            mock.patch("time.perf_counter", FakeClock(0.001)),
            mock.patch.object(
                D4, "sample_fight_move", wraps=D4.sample_fight_move
            ) as spy,
        ):
            bot.do_turn(fake)
        assert spy.call_count == len(MINE_B)
        assert list(fake.orders) == expected


def test_nine_enemies_sample_like_base() -> None:
    # (c) Boundary lower side: 9 visible enemies still sample, one
    # call per ant, with orders exactly as base across seeds.
    assert len(FOES_9) == 9
    assert D4.SMALL_FIGHT_ENEMIES == 10
    for seed in range(5):
        expected = _run_turn_clocked(D3, seed, FakeAnts(MINE_C, FOES_9))
        fake = FakeAnts(MINE_C, FOES_9)
        bot = D4.Dirichlet4(seed=seed)
        bot.do_setup(fake)
        with (
            mock.patch("time.perf_counter", FakeClock(0.001)),
            mock.patch.object(
                D4, "sample_fight_move", wraps=D4.sample_fight_move
            ) as spy,
        ):
            bot.do_turn(fake)
        assert spy.call_count == len(MINE_C)
        assert list(fake.orders) == expected


def test_ten_enemies_use_static_safety_only() -> None:
    # (c) Boundary upper side: the 10th (distant) foe disables
    # sampling entirely; orders match static safety, and the
    # distant foe changes nothing about the static orders.
    assert len(FOES_10) == 10
    for seed in range(5):
        fake = FakeAnts(MINE_C, FOES_10)
        bot = D4.Dirichlet4(seed=seed)
        bot.do_setup(fake)
        with mock.patch.object(D4, "sample_fight_move") as spy:
            spy.side_effect = AssertionError("no sampling with 10 visible")
            bot.do_turn(fake)
        assert spy.call_count == 0
        static10 = _static_orders(D3, seed, FakeAnts(MINE_C, FOES_10))
        static9 = _static_orders(D3, seed, FakeAnts(MINE_C, FOES_9))
        assert list(fake.orders) == static10
        assert static10 == static9


def test_crowded_full_turn_under_1s_without_sampling() -> None:
    # (d) A crowded 48v30 full turn (food and hills in play) stays
    # under a second with the sampler gated off.
    for seed in (7, 8):
        mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
        foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
        foods = [((i * 3 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(20)]
        fake = FakeAnts(mine, foes, foods, enemy_hills=[(15, 15)], my_hills=[(10, 10)])
        bot = D4.Dirichlet4(seed=seed)
        bot.do_setup(fake)
        with mock.patch.object(D4, "sample_fight_move") as spy:
            spy.side_effect = AssertionError("no sampling in crowds")
            start = time.perf_counter()
            bot.do_turn(fake)
            elapsed = time.perf_counter() - start
        assert spy.call_count == 0
        assert elapsed < 1.0, (seed, elapsed)
        assert len(fake.orders) > 0


def test_everything_else_identical_to_base() -> None:
    # Only one idea: constants, helpers, and the sampler itself are
    # source-identical to base; the gate constant is the addition.
    assert D4.FIGHT_BUDGET == D3.FIGHT_BUDGET == 0.015
    assert D4.MOVES == D3.MOVES
    assert D4.ENEMY_MOVES == D3.ENEMY_MOVES
    assert D4.LOCAL_R == D3.LOCAL_R
    assert D4.EQUAL_TRADE_NEAR == D3.EQUAL_TRADE_NEAR
    assert D4.CLUSTER_R == D3.CLUSTER_R
    assert D4.DENIAL_ENEMIES == D3.DENIAL_ENEMIES
    assert D4.DENIAL_CLAIMS == D3.DENIAL_CLAIMS
    assert D4.SMALL_FIGHT_ENEMIES == 10
    shared = [
        "_scan_board",
        "denied_food_groups",
        "assign_food_targets",
        "dirichlet_sample",
        "turn_order",
        "resolve_focus",
        "combat_score",
        "is_safe_step",
        "intercept_square",
        "best_reply_score",
        "best_reply_casualties",
        "is_needless_suicide",
        "veto_fallback",
        "sample_fight_move",
    ]
    for name in shared:
        assert inspect.getsource(getattr(D4, name)) == inspect.getsource(
            getattr(D3, name)
        ), name
    assert "SMALL_FIGHT_ENEMIES" in inspect.getsource(D4.Dirichlet4.do_turn)
