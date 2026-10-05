#!/usr/bin/env python
"""Softmax9 entry tests: hill-gated small-fight press (stdlib only).

One idea, different from Softmax5's open-field parity press: carved
fights with own+enemy <= SMALL_FIGHT_MAX press deterministically at
p >= 0.5 ONLY when the fight contests a prize (any combatant within
HILL_PRIZE_R of a hill, own or remembered enemy). Open-field parity
keeps the Softmax3 contest-zone coin. Bigger fights keep the coin
everywhere. The sensor is fight-local headcount plus prize proximity,
never enemy owner identity (no n_owners parameter).

Pins before the bot exists:

(a) prize-adjacent small parity presses under both hostile coins
    with no rng draw; open-field small parity still flips;
(b) decisive fights unchanged at any size, prize or open;
(c) big parity still flips with the coin even next to a hill;
(d) turn-level: 2v2 near a hill is coin-independent, 2v2 in the
    open still coin-flips;
(e) economy pins unchanged; full turn <1s.
"""

import os
import random
import sys
import time
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Softmax9 as SM  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
R2 = 5


class FakeAnts:
    """Minimal ants.Ants surface used by Softmax9.do_turn."""

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
    bot = SM.Softmax9()
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


def test_hill_prize_radius_documented() -> None:
    assert SM.HILL_PRIZE_R == 5


def test_gate_sensor_is_headcount_plus_prize_only() -> None:
    assert SM.is_small_fight(1, 1) is True
    assert SM.is_small_fight(2, 2) is True
    assert SM.is_small_fight(3, 2) is False
    assert SM.is_small_fight(2, 3) is False
    import inspect

    params = inspect.signature(SM.decide_aggression).parameters
    assert "near_prize" in params
    assert "n_owners" not in params


def test_prize_small_parity_press_ignores_coin() -> None:
    for hostile in (_AlwaysLow, _AlwaysHigh):
        assert SM.decide_aggression(1, 1, hostile(0), near_prize=True) is True
        assert SM.decide_aggression(2, 2, hostile(0), near_prize=True) is True


def test_open_small_parity_still_flips_with_coin() -> None:
    assert SM.decide_aggression(2, 2, _AlwaysLow(0), near_prize=False) is True
    assert SM.decide_aggression(2, 2, _AlwaysHigh(0), near_prize=False) is False
    assert SM.decide_aggression(1, 1, _AlwaysLow(0), near_prize=False) is True
    assert SM.decide_aggression(1, 1, _AlwaysHigh(0), near_prize=False) is False


def test_big_parity_still_flips_even_at_prize() -> None:
    assert SM.decide_aggression(3, 2, _AlwaysLow(0), near_prize=True) is True
    assert SM.decide_aggression(3, 2, _AlwaysHigh(0), near_prize=True) is False
    assert SM.decide_aggression(2, 3, _AlwaysLow(0), near_prize=True) is True
    assert SM.decide_aggression(2, 3, _AlwaysHigh(0), near_prize=True) is False


def test_decisive_fights_unchanged_anywhere() -> None:
    for hostile in (_AlwaysLow, _AlwaysHigh):
        for prize in (False, True):
            rng = hostile(0)
            assert SM.decide_aggression(2, 1, rng, near_prize=prize) is True
            assert SM.decide_aggression(3, 1, rng, near_prize=prize) is True
            assert SM.decide_aggression(1, 2, rng, near_prize=prize) is False
            assert SM.decide_aggression(1, 3, rng, near_prize=prize) is False
            assert SM.decide_aggression(5, 0, rng, near_prize=prize) is True
            assert SM.decide_aggression(0, 5, rng, near_prize=prize) is False


def test_prize_press_consumes_no_rng_draw() -> None:
    rng = random.Random(7)
    state = rng.getstate()
    assert SM.decide_aggression(2, 2, rng, near_prize=True) is True
    assert rng.getstate() == state


def test_open_press_consumes_rng_draw() -> None:
    rng = random.Random(7)
    state = rng.getstate()
    SM.decide_aggression(2, 2, rng, near_prize=False)
    assert rng.getstate() != state


def test_fight_near_prize_sensor() -> None:
    dist = FakeAnts([(5, 5)], []).distance
    assert SM.fight_near_prize([(5, 5)], [(5, 8)], [(5, 10)], dist) is True
    assert SM.fight_near_prize([(5, 5)], [(5, 8)], [(16, 16)], dist) is False
    assert SM.fight_near_prize([(5, 5)], [(5, 8)], [], dist) is False


def test_turn_prize_melee_coin_independent() -> None:
    # 2v2 face-off beside an enemy hill: hostile coins agree.
    mine = [(5, 5), (5, 6)]
    foes = [(5, 8), (5, 9)]
    plain = run_turn(mine, foes, enemy_hills=[(5, 13)])
    low = _run_hostile(mine, foes, _AlwaysLow, enemy_hills=[(5, 13)])
    high = _run_hostile(mine, foes, _AlwaysHigh, enemy_hills=[(5, 13)])
    assert low.orders == high.orders == plain.orders


def test_turn_open_melee_still_coin_flips() -> None:
    # Same 2v2 in the open (hills far): hostile coins must disagree.
    mine = [(5, 5), (5, 6)]
    foes = [(5, 8), (5, 9)]
    low = _run_hostile(mine, foes, _AlwaysLow, my_hills=[(16, 16)])
    high = _run_hostile(mine, foes, _AlwaysHigh, my_hills=[(16, 16)])
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
