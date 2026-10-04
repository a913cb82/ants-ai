#!/usr/bin/env python
"""Softmax4 entry tests: owner-aware contest gate (stdlib only).

One idea: the contest-zone coin pays in crowds but donates in
duels against a single deterministic opponent, which exploits a
refused parity fight every time. So the gate reads duel shape
from visible owners: one (or zero) distinct enemy owners gates
deterministically (p >= 0.5, no coin consumed), two or more keep
the seeded per-fight coin. Pins:

(a) duel shape (n_owners <= 1): parity fights ignore the coin
    (both hostile coins agree), no rng draw consumed;
(b) crowd shape (n_owners >= 2): parity fights flip with the
    coin, seeded-reproducible, distributed ~p over seeds;
(c) decisive fights ignore the coin in both shapes;
(d) turn-level discrimination: single-owner 1v1 coin-independent,
    multi-owner 2v2 coin-dependent;
(e) economy pins unchanged; full turn <1s.
"""

import os
import random
import sys
import time
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Softmax4 as SM  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
R2 = 5


class FakeAnts:
    """Minimal ants.Ants surface used by Softmax4.do_turn."""

    def __init__(
        self,
        mine: list[Loc],
        enemies: list[Loc],
        foods: list[Loc] | None = None,
        water: set[Loc] | None = None,
        enemy_hills: list[Loc] | None = None,
        my_hills: list[Loc] | None = None,
        owners: list[int] | None = None,
    ) -> None:
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = R2
        self._mine = list(mine)
        self._enemies = list(enemies)
        self._owners = list(owners) if owners is not None else [1] * len(enemies)
        assert len(self._owners) == len(self._enemies)
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
        return list(zip(self._enemies, self._owners, strict=True))

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
    owners: list[int] | None = None,
) -> FakeAnts:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills, owners)
    bot = SM.Softmax4()
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


def test_contest_half_documented() -> None:
    assert SM.CONTEST_HALF == 0.2


def test_contest_zone_boundaries() -> None:
    # p(1v1)=0.5 centre -> contested; p(2v1)=0.8 / p(1v2)=0.2 -> out.
    assert SM.is_contested(1, 1) is True
    assert SM.is_contested(2, 1) is False
    assert SM.is_contested(1, 2) is False
    assert SM.is_contested(3, 1) is False
    assert SM.is_contested(1, 3) is False
    # Near-parity 3v2 (p~0.692) and 2v3 (p~0.308) stay contested.
    assert SM.is_contested(3, 2) is True
    assert SM.is_contested(2, 3) is True
    # Empty-side fights are decided, never a flip.
    assert SM.is_contested(5, 0) is False
    assert SM.is_contested(0, 5) is False


def test_decisive_fights_ignore_coin_both_shapes() -> None:
    for hostile in (_AlwaysLow, _AlwaysHigh):
        for n_owners in (0, 1, 2, 5):
            rng = hostile(0)
            assert SM.decide_aggression(2, 1, rng, n_owners=n_owners) is True
            assert SM.decide_aggression(3, 1, rng, n_owners=n_owners) is True
            assert SM.decide_aggression(1, 2, rng, n_owners=n_owners) is False
            assert SM.decide_aggression(1, 3, rng, n_owners=n_owners) is False
            assert SM.decide_aggression(5, 0, rng, n_owners=n_owners) is True
            assert SM.decide_aggression(0, 5, rng, n_owners=n_owners) is False


def test_duel_shape_presses_favored_parity() -> None:
    # Duel shape: one (or zero) visible owners -> favored-or-even
    # odds (p >= 0.5) press with no coin flip: 1v1/3v2 always True.
    for n_owners in (0, 1):
        assert SM.decide_aggression(1, 1, _AlwaysLow(0), n_owners=n_owners) is True
        assert SM.decide_aggression(1, 1, _AlwaysHigh(0), n_owners=n_owners) is True
        assert SM.decide_aggression(3, 2, _AlwaysLow(0), n_owners=n_owners) is True
        assert SM.decide_aggression(3, 2, _AlwaysHigh(0), n_owners=n_owners) is True
        # Decisive underdogs still refuse without drawing.
        assert SM.decide_aggression(1, 2, _AlwaysLow(0), n_owners=n_owners) is False
        assert SM.decide_aggression(1, 2, _AlwaysHigh(0), n_owners=n_owners) is False


def test_duel_shape_mixes_underdog_parity() -> None:
    # Duel shape: underdog contests (2v3, p~0.31) keep the coin,
    # because mixing outlasts pure refusal when behind.
    assert SM.decide_aggression(2, 3, _AlwaysLow(0), n_owners=1) is True
    assert SM.decide_aggression(2, 3, _AlwaysHigh(0), n_owners=1) is False
    assert SM.decide_aggression(2, 3, _AlwaysLow(0), n_owners=0) is True
    assert SM.decide_aggression(2, 3, _AlwaysHigh(0), n_owners=0) is False


def test_duel_shape_draws_only_on_coin() -> None:
    # Favored duel presses must not draw, so sample streams stay
    # identical; underdog duel contests draw exactly once.
    rng = random.Random(7)
    state = rng.getstate()
    assert SM.decide_aggression(1, 1, rng, n_owners=1) is True
    assert rng.getstate() == state
    assert SM.decide_aggression(1, 2, rng, n_owners=1) is False
    assert rng.getstate() == state
    SM.decide_aggression(2, 3, rng, n_owners=1)
    assert rng.getstate() != state


def test_crowd_shape_flips_with_coin() -> None:
    for n_owners in (2, 3, 9):
        assert SM.decide_aggression(1, 1, _AlwaysLow(0), n_owners=n_owners) is True
        assert SM.decide_aggression(1, 1, _AlwaysHigh(0), n_owners=n_owners) is False
        assert SM.decide_aggression(3, 2, _AlwaysLow(0), n_owners=n_owners) is True
        assert SM.decide_aggression(3, 2, _AlwaysHigh(0), n_owners=n_owners) is False


def test_crowd_flip_seeded_and_distributed() -> None:
    first = [
        SM.decide_aggression(1, 1, random.Random(s), n_owners=4) for s in range(100)
    ]
    second = [
        SM.decide_aggression(1, 1, random.Random(s), n_owners=4) for s in range(100)
    ]
    assert first == second
    rate = sum(first) / len(first)
    # p(1v1) == 0.5: the coin must explore, not stick to one branch.
    assert 0.3 <= rate <= 0.7
    assert any(first) and not all(first)


def test_turn_decisive_boards_coin_independent() -> None:
    mine = [(5, 5), (5, 6)]
    foes = [(5, 8)]
    plain = run_turn(mine, foes)
    low = _run_hostile(mine, foes, _AlwaysLow)
    high = _run_hostile(mine, foes, _AlwaysHigh)
    assert low.orders == high.orders == plain.orders
    mine1 = [(5, 5)]
    foes1 = [(5, 8), (6, 8)]
    plain1 = run_turn(mine1, foes1)
    low1 = _run_hostile(mine1, foes1, _AlwaysLow)
    high1 = _run_hostile(mine1, foes1, _AlwaysHigh)
    assert low1.orders == high1.orders == plain1.orders


def test_turn_duel_board_coin_independent() -> None:
    # Duel shape: single-owner 1v1 is contested but must gate
    # deterministically, so hostile coins agree with each other
    # and with the plain run.
    mine = [(5, 5)]
    foes = [(5, 8)]
    plain = run_turn(mine, foes, owners=[1])
    low = _run_hostile(mine, foes, _AlwaysLow, owners=[1])
    high = _run_hostile(mine, foes, _AlwaysHigh, owners=[1])
    assert low.orders == high.orders == plain.orders


def test_turn_crowd_board_coin_flips_orders() -> None:
    # Crowd shape: two-owner 2v2 is contested and keeps the coin,
    # so hostile coins must disagree while each stays reproducible.
    mine = [(5, 5), (5, 6)]
    foes = [(5, 8), (5, 9)]
    assert SM.is_contested(len(mine), len(foes)) is True
    low = _run_hostile(mine, foes, _AlwaysLow, owners=[1, 2])
    high = _run_hostile(mine, foes, _AlwaysHigh, owners=[1, 2])
    assert low.orders != high.orders
    assert _run_hostile(mine, foes, _AlwaysLow, owners=[1, 2]).orders == low.orders
    assert _run_hostile(mine, foes, _AlwaysHigh, owners=[1, 2]).orders == high.orders


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
    owners = [(i % 9) + 1 for i in range(30)]
    start = time.perf_counter()
    fake = run_turn(
        mine, foes, foods, enemy_hills=[(15, 15)], my_hills=[(10, 10)], owners=owners
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(fake.orders) > 0
