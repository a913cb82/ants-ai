#!/usr/bin/env python
"""Coroner (loss-memory avoidance) tests.

No engine games.

One change over champion Denial: squares where one of our ants died
in contact (a visible enemy within 2 on either turn) are remembered,
and explore/food/muster paths route around them for 20 turns when an
alternative exists. Corridors with no alternative still pass through
(no stranding). Memory is pruned by age automatically.
"""

import os
import sys
import time
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Coroner as C  # noqa: E402

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
        hills: list[Loc],
        water: frozenset[Loc] = frozenset(),
    ) -> None:
        self._ants = list(ants)
        self._foods = list(foods)
        self._enemies = list(enemies)
        self._homes = list(homes)
        self._hills = list(hills)
        self._water = set(water)
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
        return [(h, 1) for h in self._hills]

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
        return loc not in self._water

    def unoccupied(self, loc: Loc) -> bool:
        assert 0 <= loc[0] < ROWS and 0 <= loc[1] < COLS
        return loc not in self._ants and loc not in self._enemies

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 10000


def fresh_bot() -> Any:
    bot = C.Coroner()
    bot.do_setup(cast(Any, FakeAnts([], [], [], [], [])))
    return bot


def run(bot: Any, fake: FakeAnts) -> FakeAnts:
    bot.do_turn(cast(Any, fake))
    return fake


GRAVE: Loc = (5, 5)
SCOUT: Loc = (5, 4)
HOME: list[Loc] = [(0, 0)]


def kill_in_contact(bot: Any) -> int:
    """Victim stands on GRAVE next to an enemy, then vanishes.

    Returns the turn the death is recorded on.
    """
    run(bot, FakeAnts([GRAVE], [], [(5, 6)], [], []))
    run(bot, FakeAnts([], [], [], [], []))
    assert GRAVE in bot.graves
    return int(bot.turn)


def scout_dest(bot: Any, turn: int) -> Loc:
    """One explore turn for SCOUT on an empty board; return where it goes."""
    bot.turn = turn - 1
    bot.visits = {}
    fake = run(bot, FakeAnts([SCOUT], [], [], HOME, []))
    assert len(fake.orders) == 1
    origin, direction = fake.orders[0]
    assert origin == SCOUT
    return fake.destination(origin, direction)


def test_contact_death_recorded() -> None:
    bot = fresh_bot()
    kill_in_contact(bot)
    assert GRAVE in bot.graves


def test_noncontact_loss_not_recorded() -> None:
    # The victim vanishes with no enemy within 2 on either turn: no grave.
    bot = fresh_bot()
    run(bot, FakeAnts([GRAVE], [], [(0, 0)], [], []))
    run(bot, FakeAnts([GRAVE], [], [(0, 0)], [], []))
    assert bot.graves == {}


def test_grave_avoided_for_20_turns() -> None:
    bot = fresh_bot()
    died = kill_in_contact(bot)
    for age in range(1, 21):
        assert C.is_grave(GRAVE, bot.graves, died + age)
        assert scout_dest(bot, died + age) != GRAVE
    assert int(bot.turn) == died + 20


def test_turn_21_steps_back_on_freely() -> None:
    bot = fresh_bot()
    died = kill_in_contact(bot)
    assert not C.is_grave(GRAVE, bot.graves, died + 21)
    # The expired grave is the only appealing square: the scout steps on.
    bot.turn = died + 20
    bot.visits = {(4, 4): 9, (6, 4): 9, (5, 3): 9, GRAVE: 0}
    fake = run(bot, FakeAnts([SCOUT], [], [], HOME, []))
    assert fake.orders == [(SCOUT, "e")]


def test_food_path_routes_around_grave() -> None:
    # Open board: food two east past the grave must not step onto it.
    bot = fresh_bot()
    died = kill_in_contact(bot)
    bot.turn = died
    bot.visits = {}
    fake = run(bot, FakeAnts([SCOUT], [(5, 6)], [], HOME, []))
    assert len(fake.orders) == 1
    origin, direction = fake.orders[0]
    assert origin == SCOUT
    assert direction != "e"


def test_no_alternative_corridor_passes_through() -> None:
    # Only the grave square connects ant to food: pass through, no hold.
    bot = fresh_bot()
    died = kill_in_contact(bot)
    bot.turn = died
    bot.visits = {}
    water = frozenset(
        (r, c)
        for r in range(ROWS)
        for c in range(COLS)
        if (r, c) not in (SCOUT, GRAVE, (5, 6))
    )
    fake = run(bot, FakeAnts([SCOUT], [(5, 6)], [], HOME, [], water=water))
    assert fake.orders == [(SCOUT, "e")]


def test_boxed_ant_steps_on_grave_rather_than_hold() -> None:
    # Explore with the grave as the only open neighbour: move, not strand.
    bot = fresh_bot()
    died = kill_in_contact(bot)
    bot.turn = died
    bot.visits = {}
    water = frozenset(
        (r, c) for r in range(ROWS) for c in range(COLS) if (r, c) not in (SCOUT, GRAVE)
    )
    fake = run(bot, FakeAnts([SCOUT], [], [], HOME, [], water=water))
    assert fake.orders == [(SCOUT, "e")]


def test_memory_pruned_by_age() -> None:
    bot = fresh_bot()
    died = kill_in_contact(bot)
    assert GRAVE in bot.graves
    C.record_deaths([], set(), [], [], torus, died + 21, bot.graves)
    assert bot.graves == {}


def test_memory_costs_under_1ms() -> None:
    # Crowded board: 120 ants, 40 enemies a side, 50 graves, fresh deaths.
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(120)]
    prev = ants + [(19, 19 - (i % 5)) for i in range(10)]
    enemies = [((i * 3) % ROWS, (i * 11) % COLS) for i in range(40)]
    graves = {(r % ROWS, (r * 13) % COLS): 100 for r in range(50)}
    cur = set(ants)
    n = 2000
    start = time.perf_counter()
    for _ in range(n):
        C.record_deaths(prev, cur, enemies, enemies, torus, 110, graves)
        for a in ants:
            assert C.is_grave(a, graves, 110) in (True, False)
    assert (time.perf_counter() - start) / n < 0.001


def test_crowded_board_turn_stays_fast() -> None:
    bot = fresh_bot()
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(120)]
    run(bot, FakeAnts(ants, [(5, 5)], [(6, 6)], HOME, [(10, 10)]))
    start = time.perf_counter()
    run(bot, FakeAnts(ants, [(5, 5)], [(6, 6)], HOME, [(10, 10)]))
    assert time.perf_counter() - start < 1.0
