#!/usr/bin/env python
"""Softmax5 entry tests: small-fight parity press (stdlib only).

One idea, different from Softmax4's owner-count gate: fights with
at most SMALL_FIGHT_MAX ants (1v1, 2v2 — the atomic duel units)
press deterministically whenever the logistic odds favor or tie
(p >= 0.5), with no coin draw. Bigger fights (3v2, 2v3, crowds)
keep the Softmax3 contest-zone coin. The sensor is fight-local
headcount, never enemy owner identity (no n_owners parameter).

Pins before the bot exists:

(a) small parity fights ignore the coin (both hostile coins agree
    on press), while bigger parity fights still flip with it;
(b) decisive fights unchanged (2v1 press, 1v2 refuse, any size);
(c) the small-fight path consumes no rng draw, so crowd-fight
    sample streams stay identical;
(d) turn-level discrimination: 2v2 face-off is coin-independent,
    2v3 face-off still coin-flips;
(e) economy pins unchanged; full turn <1s.
"""

import os
import random
import sys
import time
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Softmax5 as SM  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
R2 = 5


class FakeAnts:
    """Minimal ants.Ants surface used by Softmax5.do_turn."""

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
        self.attackradius2 = R2
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


def run_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> FakeAnts:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = SM.Softmax5()
    bot.do_turn(fake)
    return fake


class _AlwaysHigh(random.Random):
    """Hostile coin: random() sticks near 1, forcing passive in zone."""

    _randbelow = random.Random._randbelow_with_getrandbits  # type: ignore[attr-defined]

    def random(self) -> float:
        return 0.999999


class _AlwaysLow(random.Random):
    """Hostile coin: random() sticks near 0, forcing aggressive in zone."""

    _randbelow = random.Random._randbelow_with_getrandbits  # type: ignore[attr-defined]

    def random(self) -> float:
        return 0.0


def _run_hostile(
    mine: list[Loc],
    enemies: list[Loc],
    hostile: type[random.Random],
    **kw: object,
) -> FakeAnts:
    with mock.patch.object(SM.random, "Random", hostile):
        return run_turn(mine, enemies, **kw)  # type: ignore[arg-type]


def test_small_fight_max_documented() -> None:
    assert SM.SMALL_FIGHT_MAX == 4


def test_small_fight_sensor_is_headcount_only() -> None:
    # 1v1 and 2v2 are small; 3v2 (5 ants) and 2v3 are not. Pure
    # headcount: no owner parameter anywhere on the gate.
    assert SM.is_small_fight(1, 1) is True
    assert SM.is_small_fight(2, 2) is True
    assert SM.is_small_fight(2, 1) is True
    assert SM.is_small_fight(1, 2) is True
    assert SM.is_small_fight(3, 2) is False
    assert SM.is_small_fight(2, 3) is False
    assert SM.is_small_fight(4, 4) is False
    import inspect

    assert "n_owners" not in inspect.signature(SM.decide_aggression).parameters


def test_small_parity_press_ignores_coin() -> None:
    # 1v1 (p=0.5) and 2v2 (p=0.5) press under both hostile coins.
    for hostile in (_AlwaysLow, _AlwaysHigh):
        assert SM.decide_aggression(1, 1, hostile(0)) is True
        assert SM.decide_aggression(2, 2, hostile(0)) is True


def test_big_parity_still_flips_with_coin() -> None:
    # 3v2 (p~0.69, 5 ants) and 2v3 (p~0.31) keep the contest coin.
    assert SM.decide_aggression(3, 2, _AlwaysLow(0)) is True
    assert SM.decide_aggression(3, 2, _AlwaysHigh(0)) is False
    assert SM.decide_aggression(2, 3, _AlwaysLow(0)) is True
    assert SM.decide_aggression(2, 3, _AlwaysHigh(0)) is False


def test_decisive_fights_unchanged_at_any_size() -> None:
    for hostile in (_AlwaysLow, _AlwaysHigh):
        rng = hostile(0)
        assert SM.decide_aggression(2, 1, rng) is True
        assert SM.decide_aggression(3, 1, rng) is True
        assert SM.decide_aggression(1, 2, rng) is False
        assert SM.decide_aggression(1, 3, rng) is False
        assert SM.decide_aggression(5, 0, rng) is True
        assert SM.decide_aggression(0, 5, rng) is False
        # Small underdog fights still refuse: 1v2 is decisive.
        assert SM.decide_aggression(1, 2, hostile(1)) is False


def test_small_press_consumes_no_rng_draw() -> None:
    # The deterministic small-fight path must not advance the rng,
    # so per-fight sample streams stay identical to base.
    rng = random.Random(7)
    state = rng.getstate()
    assert SM.decide_aggression(1, 1, rng) is True
    assert rng.getstate() == state
    assert SM.decide_aggression(2, 2, rng) is True
    assert rng.getstate() == state


def test_turn_small_melee_coin_independent() -> None:
    # 2v2 face-off carves one small fight: hostile coins agree.
    mine = [(5, 5), (5, 6)]
    foes = [(5, 8), (5, 9)]
    plain = run_turn(mine, foes)
    low = _run_hostile(mine, foes, _AlwaysLow)
    high = _run_hostile(mine, foes, _AlwaysHigh)
    assert low.orders == high.orders == plain.orders


def test_turn_big_melee_still_coin_flips() -> None:
    # 2v3 face-off is a big fight: hostile coins must disagree, so
    # crowd exploration survives the small-fight press.
    mine = [(5, 5), (5, 6)]
    foes = [(5, 7), (5, 8), (6, 8)]
    assert SM.is_small_fight(len(mine), len(foes)) is False
    low = _run_hostile(mine, foes, _AlwaysLow)
    high = _run_hostile(mine, foes, _AlwaysHigh)
    assert low.orders != high.orders


def test_non_gate_boards_match_base() -> None:
    food = run_turn([(5, 5), (15, 15)], [], foods=[(5, 8), (15, 12)])
    assert sorted(food.orders) == [((5, 5), "e"), ((15, 15), "w")]
    muster = run_turn([(5, 5), (6, 6)], [], enemy_hills=[(15, 15)])
    assert sorted(muster.orders) == [((5, 5), "n"), ((6, 6), "n")]
    guard = run_turn([(10, 10), (12, 12)], [(10, 15)], my_hills=[(10, 10)])
    assert sorted(guard.orders) == [((10, 10), "n"), ((12, 12), "n")]


def test_full_turn_under_1s_crowded() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [(3, 3), (17, 17), (10, 2)]
    start = time.perf_counter()
    fake = run_turn(mine, foes, foods, enemy_hills=[(15, 15)], my_hills=[(10, 10)])
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(fake.orders) > 0
