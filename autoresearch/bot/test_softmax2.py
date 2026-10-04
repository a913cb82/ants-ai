#!/usr/bin/env python
"""Nhaehnle soft 1-ply combat tests (self-contained, stdlib only).

Pins the faithful tactical behaviors before the bot exists:
(a) seeded sampling vs exhaustive best-reply differ,
    and the min-over-samples rule (not first-sample / mean);
(b) exact logistic aggression gate at 1v1/2v1/1v2;
(c) own-ant overvaluation flips a fixed board vs even weights;
(d) full turn <1s crowded and per-fight <50ms.
"""

import math
import os
import random
import sys
import time
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Softmax2 as SM  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
R2 = 5


class FakeAnts:
    """Minimal ants.Ants surface used by Softmax2.do_turn."""

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
    bot = SM.Softmax2()
    bot.do_turn(fake)
    return fake


def _dest(loc: Loc, direction: str) -> Loc:
    dr, dc = AIM[direction]
    return ((loc[0] + dr) % ROWS, (loc[1] + dc) % COLS)


def _passable(loc: Loc) -> bool:
    return True


def test_own_weight_overvalues_by_default() -> None:
    assert SM.OWN_ANT_WEIGHT > 1.0
    assert SM.OWN_ANT_WEIGHT == 1.5


def test_logistic_constants_documented() -> None:
    assert SM.LOGISTIC_A == 2.0
    assert SM.LOGISTIC_B == 0.0


def test_aggressive_probability_hand_computed() -> None:
    # p = 1/(1+exp(-(a*ln(own/enemy)+b))), a=2, b=0.
    # 1v1: ln1=0 -> 0.5; 2v1: 2*ln2=1.386... -> 0.8; 1v2 -> 0.2.
    assert SM.aggressive_probability(1, 1) == 0.5
    assert abs(SM.aggressive_probability(2, 1) - 0.8) < 1e-9
    assert abs(SM.aggressive_probability(1, 2) - 0.2) < 1e-9
    expect_3v1 = 1.0 / (1.0 + math.exp(-(2.0 * math.log(3.0))))
    assert abs(SM.aggressive_probability(3, 1) - expect_3v1) < 1e-12
    assert SM.aggressive_probability(5, 0) == 1.0
    assert SM.aggressive_probability(0, 5) == 0.0


def test_aggressive_roll_seeded_and_extreme() -> None:
    rng_a = random.Random(1234)
    rng_b = random.Random(1234)
    rolls_a = [SM.roll_aggressive(2, 1, rng_a) for _ in range(20)]
    rolls_b = [SM.roll_aggressive(2, 1, rng_b) for _ in range(20)]
    assert rolls_a == rolls_b
    assert any(rolls_a) and not all(rolls_a)
    rng = random.Random(0)
    assert all(SM.roll_aggressive(5, 0, rng) for _ in range(5))
    assert not any(SM.roll_aggressive(0, 5, rng) for _ in range(5))


def test_overvaluation_flips_equal_trade() -> None:
    even = SM.exchange_score(1, 1, own_weight=1.0)
    assert even == 0.0
    over = SM.exchange_score(1, 1, own_weight=SM.OWN_ANT_WEIGHT)
    assert over == 1.0 - SM.OWN_ANT_WEIGHT
    assert over < 0.0
    assert SM.should_accept(1, 1, aggressive=False) is False
    assert SM.should_accept(1, 1, aggressive=True) is True
    assert SM.should_accept(1, 0, aggressive=False) is False
    assert SM.should_accept(1, 0, aggressive=True) is False
    assert SM.should_accept(0, 1, aggressive=True) is True


def test_sampler_seeded_deterministic_and_legal() -> None:
    foes = [(5, 7), (10, 10)]
    first = SM.sample_enemy_joints(foes, ROWS, COLS, _passable, _dest, random.Random(7))
    second = SM.sample_enemy_joints(
        foes, ROWS, COLS, _passable, _dest, random.Random(7)
    )
    assert first == second
    assert len(first) == SM.N_ENEMY_SAMPLES
    for joint in first:
        assert len(joint) == len(foes)
        for loc, foe in zip(joint, foes, strict=True):
            assert loc in SM.legal_dests(foe, ROWS, COLS, _passable)
    for joint in first:
        assert joint in SM.all_enemy_joints(foes, ROWS, COLS, _passable, _dest)


def test_maxmin_over_samples_differs_from_best_reply() -> None:
    # Own ant (5,5): stay dies vs holding foe, retreat (5,4) is
    # safe vs both. Samples see only the retreat; exhaustive sees
    # the killer too, so the argmax flips (sampling, not minimax).
    own = [(5, 5)]
    retreat_only = [[(5, 10)]]
    full = [[(5, 10)], [(5, 7)]]

    def best_against(samples: list[list[Loc]]) -> list[Loc]:
        joint, _ = SM.choose_own_joint(
            own, [(5, 7)], R2, ROWS, COLS, _passable, _dest, samples
        )
        return joint

    assert best_against(retreat_only) == [(5, 5)]
    assert best_against(full) == [(5, 4)]


def test_worst_is_min_not_first_or_mean() -> None:
    # Advance (5,6): safe (0) vs retreat, mutual (1,1) vs hold.
    # Min is -0.5; first-sample and mean both differ, so a pure
    # a1k0n-style sampler (first/average reply) gambles where our
    # max-min holds. This pins max-min-over-samples distinctly.
    advance = [(5, 6)]
    samples = [[(5, 10)], [(5, 7)]]
    worst = SM.worst_score_for_own(advance, samples, R2, ROWS, COLS)
    assert worst == 1.0 - SM.OWN_ANT_WEIGHT
    first_only = SM.worst_score_for_own(advance, samples[:1], R2, ROWS, COLS)
    assert first_only == 0.0
    assert worst != first_only
    mean = (
        SM.exchange_score(*SM.resolve_exchange(advance, samples[0], R2, ROWS, COLS))
        + SM.exchange_score(*SM.resolve_exchange(advance, samples[1], R2, ROWS, COLS))
    ) / 2.0
    assert mean == (0.0 + (1.0 - SM.OWN_ANT_WEIGHT)) / 2.0
    assert worst != mean
    safe = [(5, 4)]
    assert SM.worst_score_for_own(safe, samples, R2, ROWS, COLS) == 0.0
    joint, _ = SM.choose_own_joint(
        [(5, 5)], [(5, 7)], R2, ROWS, COLS, _passable, _dest, samples
    )
    assert joint == [(5, 4)]


def test_per_fight_under_50ms() -> None:
    own = [(5, 5), (5, 6), (6, 5), (6, 6)]
    foes = [(5, 9), (5, 10), (6, 9), (4, 9)]
    rng = random.Random(0)
    samples = SM.sample_enemy_joints(foes, ROWS, COLS, _passable, _dest, rng)
    start = time.perf_counter()
    joint, score = SM.choose_own_joint(
        own, foes, R2, ROWS, COLS, _passable, _dest, samples
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 0.05
    assert len(joint) == len(own)
    assert isinstance(score, float)


def test_full_turn_under_1s_crowded() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [(3, 3), (17, 17), (10, 2)]
    start = time.perf_counter()
    fake = run_turn(mine, foes, foods, enemy_hills=[(15, 15)], my_hills=[(10, 10)])
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(fake.orders) > 0


class _AlwaysHigh(random.Random):
    """Hostile coin: random() sticks near 1, forcing base passive.

    _randbelow stays getrandbits-based (explicit binding defeats the
    __init_subclass__ rebind), so sampling is seed-identical and only
    the coin flip is forced.
    """

    _randbelow = random.Random._randbelow_with_getrandbits  # type: ignore[attr-defined]

    def random(self) -> float:
        return 0.999999


class _AlwaysLow(random.Random):
    """Hostile coin: random() sticks near 0, forcing base aggressive."""

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


def test_deterministic_gate_threshold() -> None:
    # Aggressive iff logistic p >= 0.5, same formula, no coin flip.
    assert SM.is_aggressive(1, 1) is True
    assert SM.is_aggressive(2, 1) is True
    assert SM.is_aggressive(3, 2) is True
    assert SM.is_aggressive(1, 2) is False
    assert SM.is_aggressive(2, 3) is False
    assert SM.is_aggressive(5, 0) is True
    assert SM.is_aggressive(0, 5) is False


def test_gate_ignores_coin_flip_press() -> None:
    # 2v1: p == 0.8 >= 0.5, so both hostile coins must still press
    # with the aggressive branch's orders.
    mine = [(5, 5), (5, 6)]
    foes = [(5, 8)]
    assert SM.is_aggressive(len(mine), len(foes)) is True
    plain = run_turn(mine, foes)
    low = _run_hostile(mine, foes, _AlwaysLow)
    high = _run_hostile(mine, foes, _AlwaysHigh)
    assert low.orders == high.orders == plain.orders
    assert sorted(plain.orders) == [((5, 5), "w"), ((5, 6), "n")]
    # 3v2 column push, p ~ 0.69: same demand, aggressive branch.
    mine3 = [(4, 5), (5, 5), (6, 5)]
    foes3 = [(5, 8), (5, 9)]
    assert SM.is_aggressive(len(mine3), len(foes3)) is True
    plain3 = run_turn(mine3, foes3)
    low3 = _run_hostile(mine3, foes3, _AlwaysLow)
    high3 = _run_hostile(mine3, foes3, _AlwaysHigh)
    assert low3.orders == high3.orders == plain3.orders
    assert sorted(plain3.orders) == [
        ((4, 5), "n"),
        ((5, 5), "w"),
        ((6, 5), "s"),
    ]


def test_gate_ignores_coin_flip_underdog() -> None:
    # 1v2 (p == 0.2): both coins must still refuse with passive orders.
    mine = [(5, 5)]
    foes = [(5, 8), (6, 8)]
    assert SM.is_aggressive(len(mine), len(foes)) is False
    plain = run_turn(mine, foes)
    low = _run_hostile(mine, foes, _AlwaysLow)
    high = _run_hostile(mine, foes, _AlwaysHigh)
    assert low.orders == high.orders == plain.orders
    assert sorted(plain.orders) == [((5, 5), "n")]
    mine = [(5, 5), (5, 6)]
    foes = [(5, 9), (6, 9), (5, 10)]
    low2 = _run_hostile(mine, foes, _AlwaysLow)
    high2 = _run_hostile(mine, foes, _AlwaysHigh)
    assert low2.orders == high2.orders
    assert sorted(low2.orders) == [((5, 5), "n"), ((5, 6), "n")]


def test_determinism_across_seeds() -> None:
    mine = [(5, 5), (5, 6), (6, 5)]
    foes = [(5, 8), (6, 8)]
    first: list[tuple[Loc, str]] | None = None
    for seed in range(5):
        random.seed(seed)
        fake = run_turn(mine, foes)
        if first is None:
            first = list(fake.orders)
        assert list(fake.orders) == first
    random.seed()


def test_non_gate_boards_match_base() -> None:
    # Boards whose path never consults the gate: byte-identical pins
    # captured from the base entry, so economy/guard/muster cannot drift.
    food = run_turn([(5, 5), (15, 15)], [], foods=[(5, 8), (15, 12)])
    assert sorted(food.orders) == [((5, 5), "e"), ((15, 15), "w")]
    muster = run_turn([(5, 5), (6, 6)], [], enemy_hills=[(15, 15)])
    assert sorted(muster.orders) == [((5, 5), "n"), ((6, 6), "n")]
    guard = run_turn([(10, 10), (12, 12)], [(10, 15)], my_hills=[(10, 10)])
    assert sorted(guard.orders) == [((10, 10), "n"), ((12, 12), "n")]
