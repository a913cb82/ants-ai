#!/usr/bin/env python
"""Softmax6 entry tests: standing-adjusted aggression gate (stdlib only).

One idea: the 0.5 gate threshold should move with overall standing
(rank-position in the game), not sit at absolute parity. When the army
is ahead globally, even a local underdog fight may press (the line
drops); when behind globally, even a local favorite must refuse equal
trades (the line rises). Deterministic, no coin, no owner read:

(a) standing_bias is zero at parity globals and with no visible
    enemy, grows with ln(global own/enemy), and clamps at
    STANDING_CAP;
(b) at parity globals the gate equals the base deterministic gate
    (1v1 press, 2v1 press, 1v2 refuse);
(c) discrimination: 2v3 refuses at parity globals but presses when
    far ahead; 3v2 presses at parity but refuses when far behind;
    1v1 presses at parity but refuses when far behind;
(d) the gate takes no rng (deterministic across calls);
(e) economy pins unchanged vs Softmax2; full turn <1s.
"""

import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Softmax2 as BASE  # noqa: E402
import Softmax6 as SM  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
R2 = 5


def test_bias_zero_at_parity_and_empty() -> None:
    assert SM.standing_bias(8, 8) == 0.0
    assert SM.standing_bias(1, 1) == 0.0
    assert SM.standing_bias(5, 0) == 0.0
    assert SM.standing_bias(0, 5) == 0.0


def test_bias_sign_and_log_shape() -> None:
    ahead = SM.standing_bias(6, 3)
    assert ahead == math.log(2.0)
    assert ahead > 0.0
    behind = SM.standing_bias(3, 6)
    assert behind == -math.log(2.0)
    assert behind < 0.0
    assert SM.standing_bias(10, 5) == SM.standing_bias(6, 3)


def test_bias_clamps() -> None:
    assert SM.standing_bias(100, 1) == SM.STANDING_CAP
    assert SM.standing_bias(1, 100) == -SM.STANDING_CAP
    assert SM.standing_bias(10, 3) == SM.STANDING_CAP  # ln(10/3) > 1
    assert SM.standing_bias(3, 10) == -SM.STANDING_CAP


def test_gate_matches_base_at_parity_globals() -> None:
    for own, enemy in [(1, 1), (2, 1), (1, 2), (3, 2), (2, 3), (5, 5)]:
        assert SM.decide_aggression_standing(own, enemy, 8, 8) == BASE.is_aggressive(
            own, enemy
        )


def test_underdog_presses_when_ahead() -> None:
    # 2v3 refuses at parity globals (base behavior)...
    assert BASE.is_aggressive(2, 3) is False
    assert SM.decide_aggression_standing(2, 3, 8, 8) is False
    # ...but presses when the army leads 10v3 globally.
    assert SM.decide_aggression_standing(2, 3, 10, 3) is True


def test_favorite_refuses_when_behind() -> None:
    # 3v2 presses at parity globals (base behavior)...
    assert BASE.is_aggressive(3, 2) is True
    assert SM.decide_aggression_standing(3, 2, 8, 8) is True
    # ...but refuses when the army trails 3v12 globally.
    assert SM.decide_aggression_standing(3, 2, 3, 12) is False


def test_parity_refuses_when_behind() -> None:
    assert SM.decide_aggression_standing(1, 1, 8, 8) is True
    assert SM.decide_aggression_standing(1, 1, 2, 12) is False


def test_gate_deterministic_without_rng() -> None:
    first = SM.decide_aggression_standing(2, 3, 10, 3)
    for _ in range(20):
        assert SM.decide_aggression_standing(2, 3, 10, 3) == first
    # No rng parameter: the gate cannot flip by luck of the draw.
    import inspect

    params = inspect.signature(SM.decide_aggression_standing).parameters
    assert "rng" not in params


def test_threshold_moves_monotonically_with_standing() -> None:
    # Fix the local fight at 2v3; marching global standing from
    # crushed to dominant must flip refuse -> press exactly once.
    states = [
        SM.decide_aggression_standing(2, 3, own_total, 6)
        for own_total in (1, 2, 4, 6, 12, 24)
    ]
    assert states[0] is False
    assert states[-1] is True
    flips = sum(a != b for a, b in zip(states, states[1:], strict=False))
    assert flips == 1


def test_economy_matches_base() -> None:
    def manhattan(a: Loc, b: Loc) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    ants_list = [(5, 5), (6, 6), (15, 15)]
    foods = [(5, 6), (5, 7), (14, 14)]
    enemies = [(0, 0)]
    assert SM.assign_food_targets(
        ants_list, foods, enemies, manhattan, ROWS, COLS
    ) == BASE.assign_food_targets(ants_list, foods, enemies, manhattan, ROWS, COLS)


class FakeAnts:
    """Minimal ants.Ants surface used by Softmax6.do_turn."""

    def __init__(self, mine: list[Loc], enemies: list[Loc]) -> None:
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = R2
        self._mine = list(mine)
        self._enemies = list(enemies)
        self.orders: list[tuple[Loc, str]] = []

    def food(self) -> list[Loc]:
        return []

    def my_ants(self) -> list[Loc]:
        return list(self._mine)

    def enemy_ants(self) -> list[tuple[Loc, int]]:
        return [(e, 1) for e in self._enemies]

    def enemy_hills(self) -> list[tuple[Loc, int]]:
        return []

    def my_hills(self) -> list[Loc]:
        return [(0, 0)]

    def distance(self, a: Loc, b: Loc) -> int:
        dr = abs(a[0] - b[0])
        dr = min(dr, self.rows - dr)
        dc = abs(a[1] - b[1])
        dc = min(dc, self.cols - dc)
        return dr + dc

    def destination(self, loc: Loc, direction: str) -> Loc:
        aim = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
        dr, dc = aim[direction]
        return ((loc[0] + dr) % self.rows, (loc[1] + dc) % self.cols)

    def passable(self, loc: Loc) -> bool:
        return True

    def unoccupied(self, loc: Loc) -> bool:
        return True

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 100000


def test_full_turn_under_1s_crowded() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    bot = SM.Softmax6()
    ants = FakeAnts(mine, foes)
    start = time.perf_counter()
    bot.do_turn(ants)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert ants.orders
