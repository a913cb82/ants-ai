#!/usr/bin/env python
"""Hedge (count-conditioned trade filter) tests. No engine games.

One change over champion Denial: the contact gate refuses even
(1-for-1) trades when outnumbered on visible ant count -- the
mover disengages instead of stepping in. Ahead or even on count,
the gate stays open and every order matches Denial exactly.
"""

import os
import sys
import time
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Hedge as HG  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20


def torus(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


class FakeAnts:
    def __init__(
        self,
        ants: list[Loc],
        foods: list[Loc],
        enemies: list[Loc],
        homes: list[Loc],
    ) -> None:
        self._ants = list(ants)
        self._foods = list(foods)
        self._enemies = list(enemies)
        self._homes = list(homes)
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = 5
        self.turntime = 1000
        self.orders: list[tuple[Loc, str]] = []

    def food(self) -> list[Loc]:
        return list(self._foods)

    def my_ants(self) -> list[Loc]:
        return list(self._ants)

    def enemy_ants(self) -> list[tuple[Loc, int]]:
        return [(e, 1) for e in self._enemies]

    def enemy_hills(self) -> list[tuple[Loc, int]]:
        return []

    def my_hills(self) -> list[Loc]:
        return list(self._homes)

    def distance(self, a: Loc, b: Loc) -> int:
        return torus(a, b)

    def destination(self, loc: Loc, direction: str) -> Loc:
        r, c = loc
        if direction == "n":
            return ((r - 1) % ROWS, c)
        if direction == "s":
            return ((r + 1) % ROWS, c)
        if direction == "e":
            return (r, (c + 1) % COLS)
        return (r, (c - 1) % COLS)

    def passable(self, loc: Loc) -> bool:
        assert 0 <= loc[0] < ROWS and 0 <= loc[1] < COLS
        return True

    def unoccupied(self, loc: Loc) -> bool:
        assert 0 <= loc[0] < ROWS and 0 <= loc[1] < COLS
        return loc not in self._ants and loc not in self._enemies

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 10000


def run_turn(
    ants: list[Loc],
    foods: list[Loc],
    enemies: list[Loc],
    homes: list[Loc],
) -> FakeAnts:
    bot = HG.Hedge()
    fake = FakeAnts(ants, foods, enemies, homes)
    bot.do_setup(cast(Any, fake))
    bot.do_turn(cast(Any, fake))
    return fake


# 15 ants: mover at (10, 10) plus 14 friends boxed rows 9-11,
# cols 15-19. Enemy E1 sits adjacent at (11, 11): every step
# the mover can take has exactly one enemy in attack range and
# zero friends in attack range, with all 14 friends near -- the
# champion's textbook even (1-for-1) trade.
FRIENDS = [
    (10, 15),
    (10, 16),
    (10, 17),
    (10, 18),
    (10, 19),
    (11, 15),
    (11, 16),
    (11, 17),
    (11, 18),
    (11, 19),
    (9, 15),
    (9, 16),
    (9, 17),
    (9, 18),
]
ANTS15 = [(10, 10)] + FRIENDS
FOOD = [(10, 13)]
HOME = [(10, 1)]
E1 = (11, 11)
FAR19 = [
    (0, 10),
    (0, 11),
    (0, 9),
    (1, 10),
    (1, 11),
    (1, 9),
    (0, 12),
    (0, 8),
    (1, 12),
    (1, 8),
    (0, 13),
    (0, 7),
    (1, 13),
    (1, 7),
    (2, 10),
    (2, 11),
    (2, 9),
    (19, 10),
    (19, 11),
]
ENEMIES_AHEAD = [E1, (0, 10), (0, 11), (1, 10), (1, 11)]
ENEMIES_EVEN = [E1] + FAR19[:14]
ENEMIES_BEHIND = [E1] + FAR19

# Captured champion-Denial reference orders on these boards. With
# contact the mover steps east into the even trade; with no
# contact nearby it diffuses north instead.
CHAMPION_TRADE = [
    ((10, 10), "e"),
    ((10, 15), "w"),
    ((10, 19), "n"),
    ((11, 15), "s"),
    ((11, 16), "s"),
    ((11, 17), "s"),
    ((11, 18), "s"),
    ((11, 19), "e"),
    ((9, 15), "n"),
    ((9, 16), "n"),
    ((9, 17), "n"),
    ((9, 18), "n"),
]
CHAMPION_QUIET = [
    ((10, 10), "n"),
    ((10, 15), "w"),
    ((10, 19), "n"),
    ((11, 15), "s"),
    ((11, 16), "s"),
    ((11, 17), "s"),
    ((11, 18), "s"),
    ((11, 19), "e"),
    ((9, 15), "n"),
    ((9, 16), "n"),
    ((9, 17), "n"),
    ((9, 18), "n"),
]


def test_gate_blocks_even_trade_when_outnumbered() -> None:
    assert HG.even_trade_allowed(15, 20) is False
    assert HG.even_trade_allowed(1, 2) is False
    assert HG.even_trade_allowed(0, 1) is False


def test_gate_opens_when_ahead_or_even() -> None:
    assert HG.even_trade_allowed(20, 15) is True
    assert HG.even_trade_allowed(15, 15) is True
    assert HG.even_trade_allowed(0, 0) is True


def test_outnumbered_contact_disengages() -> None:
    # 15 v 20: the mover refuses every contact square and holds
    # instead of taking the champion's ((10, 10), 'e') trade, and
    # no ant steps onto the contact square (10, 11) either.
    fake = run_turn(ANTS15, FOOD, ENEMIES_BEHIND, HOME)
    assert ((10, 10), "e") not in fake.orders
    assert all(origin != (10, 10) for origin, _ in fake.orders)
    assert (10, 11) not in [fake.destination(o, d) for o, d in fake.orders]


def test_ahead_contact_trades_as_champion() -> None:
    # 15 v 5: the gate is open, so the mover takes the even
    # trade and the whole turn matches Denial exactly.
    fake = run_turn(ANTS15, FOOD, ENEMIES_AHEAD, HOME)
    assert fake.orders == CHAMPION_TRADE


def test_even_contact_trades_as_champion() -> None:
    # 15 v 15: parity still takes the trade; full turn matches.
    fake = run_turn(ANTS15, FOOD, ENEMIES_EVEN, HOME)
    assert fake.orders == CHAMPION_TRADE


def test_no_contact_matches_champion_exactly() -> None:
    # No enemy near any mover: the gate never fires, so empty
    # and far-enemy turns both match Denial order for order.
    assert run_turn(ANTS15, FOOD, [], HOME).orders == CHAMPION_QUIET
    assert run_turn(ANTS15, FOOD, FAR19[:6], HOME).orders == CHAMPION_QUIET


def test_count_check_costs_under_half_a_ms() -> None:
    # The gate itself (two lens plus a compare) must stay far
    # under 0.5ms per call on average.
    n = 2000
    start = time.perf_counter()
    for _ in range(n):
        assert HG.even_trade_allowed(15, 20) is False
    assert (time.perf_counter() - start) / n < 0.0005


def test_crowded_board_turn_stays_fast() -> None:
    # 120 ants v 150 enemies packed shoulder to shoulder: the
    # full turn (gate included) finishes in well under the
    # 1000ms turn budget.
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(120)]
    enemies = [((r * 3 + 1) % ROWS, (r * 5 + 2) % COLS) for r in range(150)]
    foods = [(10, 10)]
    start = time.perf_counter()
    run_turn(ants, foods, enemies, HOME)
    assert time.perf_counter() - start < 1.0
