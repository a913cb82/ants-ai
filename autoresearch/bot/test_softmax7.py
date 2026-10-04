#!/usr/bin/env python
"""Softmax7 entry tests: contact-timing aggression gate (stdlib only).

One idea: contested fights press the coin only in contact range
(nearest own/foe pair within CONTACT_R); approaching fights hold
(passive) until contact. Timing, not odds, decides when to press.
Pins before the bot exists:

(a) zone boundaries from the exact logistic p (base preserved);
(b) decisive fights ignore the coin AND the range (timing never
    overrides decisive odds);
(c) close contested fights flip with the coin (base preserved);
(d) far contested fights refuse under both hostile coins;
(e) default (no range read) preserves the base coin behavior;
(f) turn-level discrimination: far parity boards coin-independent,
    close parity boards coin-flip;
(g) economy pins unchanged; full turn <1s.
"""

import os
import random
import sys
import time
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Softmax7 as SM  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
R2 = 5


class FakeAnts:
    """Minimal ants.Ants surface used by Softmax7.do_turn."""

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
    bot = SM.Softmax7()
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


def test_contact_r_documented() -> None:
    assert SM.CONTACT_R == 3


def test_fight_min_dist() -> None:
    dist = FakeAnts([(5, 5)], [(5, 11)]).distance
    assert SM.fight_min_dist([(5, 5)], [(5, 11)], dist) == 6
    assert SM.fight_min_dist([(5, 5), (5, 6)], [(5, 11), (5, 12)], dist) == 5
    assert SM.fight_min_dist([(5, 5)], [(5, 8)], dist) == 3
    # Toroidal wrap reads through the seam, not across the board.
    assert SM.fight_min_dist([(0, 0)], [(19, 0)], dist) == 1


def test_in_press_range_boundary() -> None:
    assert SM.in_press_range(3) is True
    assert SM.in_press_range(0) is True
    assert SM.in_press_range(4) is False
    assert SM.in_press_range(6) is False


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


def test_decisive_fights_ignore_coin_and_range() -> None:
    # Timing never overrides decisive odds: far favorites press,
    # far underdogs refuse, under either hostile coin.
    for hostile in (_AlwaysLow, _AlwaysHigh):
        rng = hostile(0)
        assert SM.decide_aggression(2, 1, rng, min_dist=6) is True
        assert SM.decide_aggression(3, 1, rng, min_dist=6) is True
        assert SM.decide_aggression(1, 2, rng, min_dist=6) is False
        assert SM.decide_aggression(1, 3, rng, min_dist=6) is False
        assert SM.decide_aggression(5, 0, rng, min_dist=6) is True
        assert SM.decide_aggression(0, 5, rng, min_dist=6) is False


def test_close_contested_flips_with_coin() -> None:
    assert SM.decide_aggression(1, 1, _AlwaysLow(0), min_dist=3) is True
    assert SM.decide_aggression(1, 1, _AlwaysHigh(0), min_dist=3) is False
    assert SM.decide_aggression(2, 2, _AlwaysLow(0), min_dist=2) is True
    assert SM.decide_aggression(2, 2, _AlwaysHigh(0), min_dist=2) is False
    assert SM.decide_aggression(3, 2, _AlwaysLow(0), min_dist=1) is True
    assert SM.decide_aggression(3, 2, _AlwaysHigh(0), min_dist=1) is False


def test_far_contested_refuses_under_both_coins() -> None:
    # Approaching parity holds until contact: no press by luck.
    for hostile in (_AlwaysLow, _AlwaysHigh):
        rng = hostile(0)
        assert SM.decide_aggression(1, 1, rng, min_dist=5) is False
        assert SM.decide_aggression(2, 2, rng, min_dist=4) is False
        assert SM.decide_aggression(3, 2, rng, min_dist=6) is False
        assert SM.decide_aggression(2, 3, rng, min_dist=4) is False


def test_default_range_preserves_base_coin() -> None:
    # No range read: the base contest-zone coin rules (back-compat).
    assert SM.decide_aggression(1, 1, _AlwaysLow(0)) is True
    assert SM.decide_aggression(1, 1, _AlwaysHigh(0)) is False
    assert SM.decide_aggression(2, 1, _AlwaysLow(0)) is True
    assert SM.decide_aggression(1, 2, _AlwaysHigh(0)) is False


def test_contested_flip_seeded_and_distributed_close() -> None:
    first = [
        SM.decide_aggression(1, 1, random.Random(s), min_dist=2) for s in range(100)
    ]
    second = [
        SM.decide_aggression(1, 1, random.Random(s), min_dist=2) for s in range(100)
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


def test_turn_far_parity_board_holds_regardless_of_coin() -> None:
    # 2v2 approach at gap 5: out of press range, so both hostile
    # coins hold (identical orders) instead of flipping a press.
    mine = [(5, 5), (5, 6)]
    foes = [(5, 11), (5, 12)]
    assert SM.fight_min_dist(mine, foes, FakeAnts(mine, foes).distance) == 5
    low = _run_hostile(mine, foes, _AlwaysLow)
    high = _run_hostile(mine, foes, _AlwaysHigh)
    assert low.orders == high.orders
    assert low.orders == run_turn(mine, foes).orders


def test_turn_close_parity_board_coin_flips_orders() -> None:
    # 1v1 face-off in range: hostile coins must disagree, so the
    # turn-level policy explores at contact instead of holding.
    mine = [(5, 5)]
    foes = [(5, 8)]
    assert SM.fight_min_dist(mine, foes, FakeAnts(mine, foes).distance) == 3
    low = _run_hostile(mine, foes, _AlwaysLow)
    high = _run_hostile(mine, foes, _AlwaysHigh)
    assert low.orders != high.orders
    # Both branches are reproducible per coin.
    assert _run_hostile(mine, foes, _AlwaysLow).orders == low.orders
    assert _run_hostile(mine, foes, _AlwaysHigh).orders == high.orders


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
