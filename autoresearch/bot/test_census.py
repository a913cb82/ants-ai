#!/usr/bin/env python
"""Census-Taker (adaptive opening) tests.

No engine games.

One change over champion Denial: the bot counts visible enemies
through turn 20. On quiet maps (zero enemies seen) it trades two
food claims for exploration in turns 21-60, buying earlier intel.
On maps where any enemy was seen, or outside turns 21-60, champion
claims stand untouched.
"""

import os
import sys
import time
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Census as C  # noqa: E402

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
    ) -> None:
        self._ants = list(ants)
        self._foods = list(foods)
        self._enemies = list(enemies)
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = 5
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
        return []

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


def fresh_bot() -> Any:
    bot = C.Census()
    bot.do_setup(cast(Any, FakeAnts([], [], [])))
    return bot


def run(bot: Any, fake: FakeAnts) -> FakeAnts:
    bot.do_turn(cast(Any, fake))
    return fake


def idle(bot: Any, turns: int) -> None:
    """Quiet filler turns: one ant, no food, no enemies."""
    for _ in range(turns):
        run(bot, FakeAnts([(0, 0)], [], []))


ANTS5: list[Loc] = [(10, 0), (10, 1), (10, 2), (10, 3), (10, 4)]
FOODS5: list[Loc] = [(15, 0), (15, 1), (15, 2), (15, 3), (15, 4)]
FAR: list[Loc] = [(0, 19)]


def test_shift_disabled_when_enemies_seen() -> None:
    for turn in (1, 20, 21, 30, 60, 61, 70):
        target = {i: (i, i) for i in range(5)}
        assert C.census_shift(dict(target), turn, True) == target


def test_shift_drops_two_highest_indices() -> None:
    target = {i: (i, i) for i in range(5)}
    assert C.census_shift(dict(target), 30, False) == {
        0: (0, 0),
        1: (1, 1),
        2: (2, 2),
    }


def test_shift_window_boundaries() -> None:
    target = {i: (i, i) for i in range(5)}
    assert C.census_shift(dict(target), 20, False) == target
    assert len(C.census_shift(dict(target), 21, False)) == 3
    assert len(C.census_shift(dict(target), 60, False)) == 3
    assert C.census_shift(dict(target), 61, False) == target


def test_shift_with_fewer_than_two_claims() -> None:
    assert C.census_shift({0: (3, 3)}, 30, False) == {}
    assert C.census_shift({}, 30, False) == {}


def test_census_flag_latches_from_early_sighting() -> None:
    # Enemy visible on turn 3 only: still an enemies-seen game.
    bot = fresh_bot()
    run(bot, FakeAnts([(0, 0)], [], []))
    run(bot, FakeAnts([(0, 0)], [], []))
    run(bot, FakeAnts([(0, 0)], [], FAR))
    assert bot.enemies_seen is True
    idle(bot, 17)
    assert bot.turn == 20
    assert bot.enemies_seen is True


def test_enemy_at_turn_20_counts_as_seen() -> None:
    bot = fresh_bot()
    idle(bot, 19)
    run(bot, FakeAnts([(0, 0)], [], FAR))
    assert bot.turn == 20
    assert bot.enemies_seen is True


def test_enemies_seen_game_matches_champion() -> None:
    # Enemies visible every turn: turn-30 orders must equal the
    # champion-mode orders (census shift patched to identity).
    boards = [FakeAnts(ANTS5[:4], [(15, i) for i in range(4)], FAR) for _ in range(30)]
    bot = fresh_bot()
    for fake in boards:
        run(bot, fake)
    assert bot.enemies_seen is True
    got = boards[-1].orders
    champion = C.census_shift
    try:
        C.census_shift = lambda t, turn, seen: t
        ref = fresh_bot()
        refs = [
            FakeAnts(ANTS5[:4], [(15, i) for i in range(4)], FAR) for _ in range(30)
        ]
        for fake in refs:
            run(ref, fake)
        want = refs[-1].orders
    finally:
        C.census_shift = champion
    assert got == want
    assert len(got) == 4


def test_empty_map_shifts_exactly_two_to_explore() -> None:
    # Quiet turns 1-20, then an open 5-ant board on turn 21: ants 3
    # and 4 explore north while ants 0-2 walk south to their food.
    bot = fresh_bot()
    idle(bot, 20)
    assert bot.enemies_seen is False
    bot.visits = {}
    fake = run(bot, FakeAnts(ANTS5, FOODS5, []))
    assert bot.turn == 21
    assert fake.orders == [
        ((10, 0), "s"),
        ((10, 1), "s"),
        ((10, 2), "s"),
        ((10, 3), "n"),
        ((10, 4), "n"),
    ]


def test_shift_holds_through_turn_60() -> None:
    bot = fresh_bot()
    idle(bot, 59)
    bot.visits = {}
    fake = run(bot, FakeAnts(ANTS5, FOODS5, []))
    assert bot.turn == 60
    assert fake.orders == [
        ((10, 0), "s"),
        ((10, 1), "s"),
        ((10, 2), "s"),
        ((10, 3), "n"),
        ((10, 4), "n"),
    ]


def test_turn_61_rejoins_champion() -> None:
    # Quiet all game, but turn 61 is past the window: all five ants
    # walk south to food, exactly the champion-mode orders.
    bot = fresh_bot()
    idle(bot, 60)
    bot.visits = {}
    fake = run(bot, FakeAnts(ANTS5, FOODS5, []))
    assert bot.turn == 61
    assert fake.orders == [
        ((10, 0), "s"),
        ((10, 1), "s"),
        ((10, 2), "s"),
        ((10, 3), "s"),
        ((10, 4), "s"),
    ]


def test_census_check_costs_under_half_ms() -> None:
    target = {i: (i, i) for i in range(60)}
    n = 5000
    start = time.perf_counter()
    for _ in range(n):
        C.census_shift(dict(target), 30, False)
    assert (time.perf_counter() - start) / n < 0.0005


def test_crowded_board_turn_stays_fast() -> None:
    bot = fresh_bot()
    idle(bot, 25)
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(120)]
    start = time.perf_counter()
    run(bot, FakeAnts(ants, [(5, 5)], []))
    assert time.perf_counter() - start < 1.0
