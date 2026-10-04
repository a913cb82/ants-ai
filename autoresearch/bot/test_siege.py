#!/usr/bin/env python
"""Siege (memetix deadlock-breaking) tests. No engine games.

Static no-trade rules deadlock crowded fronts: both sides stare
forever. The one change: allow a KILL move (an equal trade the
legacy check refuses) iff (a) the same ant has held position with
unbroken enemy contact for 3+ consecutive turns (per-ant contact
age), AND (b) the trade kills at least one enemy while dying
(provisional focus resolution proves the kill, not just the
attempt). Everything else keeps the legacy check untouched.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Siege import (  # noqa: E402
    SIEGE_AGE,
    Siege,
    siege_release,
    siege_would_kill,
    update_siege_age,
)

Loc = tuple[int, int]


class FakeAnts:
    """Minimal engine double. Mirrors ants.py semantics (torus grid,
    water blocks, food squares count as occupied)."""

    def __init__(
        self,
        rows: int,
        cols: int,
        my_ants: list[Loc],
        foods: list[Loc],
        water: set[Loc] = frozenset(),  # type: ignore[assignment]
        my_hills: list[Loc] | None = None,
        enemies: list[Loc] | None = None,
        attackradius2: int = 5,
    ):
        self.rows = rows
        self.cols = cols
        self._ants = list(my_ants)
        self._foods = list(foods)
        self._water = set(water)
        self._hills = list(my_hills or [])
        self._enemies = list(enemies or [])
        self.attackradius2 = attackradius2
        self.orders: list[tuple[Loc, str]] = []

    def food(self) -> list[Loc]:
        return self._foods[:]

    def my_ants(self) -> list[Loc]:
        return self._ants[:]

    def enemy_ants(self) -> list[tuple[Loc, int]]:
        return [(loc, 1) for loc in self._enemies]

    def my_hills(self) -> list[Loc]:
        return self._hills[:]

    def enemy_hills(self) -> list[tuple[Loc, int]]:
        return []

    def distance(self, a: Loc, b: Loc) -> int:
        dc = min(abs(a[1] - b[1]), self.cols - abs(a[1] - b[1]))
        dr = min(abs(a[0] - b[0]), self.rows - abs(a[0] - b[0]))
        return dr + dc

    def destination(self, loc: Loc, direction: str) -> Loc:
        aim = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
        dr, dc = aim[direction]
        return ((loc[0] + dr) % self.rows, (loc[1] + dc) % self.cols)

    def passable(self, loc: Loc) -> bool:
        return loc not in self._water

    def unoccupied(self, loc: Loc) -> bool:
        taken = set(self._ants) | set(self._enemies) | set(self._foods)
        return loc not in taken

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 1000


def kill_box() -> FakeAnts:
    # A=(10,10) walled N/S/W by water, food pulling east, one enemy
    # E=(10,12). East to (10,11) is an equal trade (0 friends vs 1
    # enemy) the legacy check refuses; provisional focus shows a
    # mutual kill. No other step is passable, so the ant either
    # takes the killing move or holds.
    return FakeAnts(
        20,
        20,
        [(10, 10)],
        [(10, 16)],
        water={(9, 10), (11, 10), (10, 9)},
        enemies=[(10, 12)],
    )


def suicide_box() -> FakeAnts:
    # Same walls, but two enemies cover the east step: 1v2, a losing
    # trade, and focus shows the mover dies killing nothing.
    return FakeAnts(
        20,
        20,
        [(10, 10)],
        [(10, 16)],
        water={(9, 10), (11, 10), (10, 9)},
        enemies=[(10, 12), (11, 12)],
    )


def fresh_siege() -> Siege:
    bot = Siege()
    bot.do_setup(FakeAnts(10, 10, [(0, 0)], []))
    return bot


def test_fresh_contact_refuses_killing_trade():
    assert SIEGE_AGE == 3
    # Gate level: a fresh contact (age 1) refuses even a proven kill.
    assert not siege_release(0, 1, 1, True)
    assert not siege_release(0, 1, 2, True)
    # Bot level: first turn in the box holds, no east order.
    bot = fresh_siege()
    state = kill_box()
    bot.do_turn(state)
    assert ((10, 10), "e") not in state.orders
    assert state.orders == []
    assert bot.siege_age.get((10, 10)) == 1


def test_three_turn_standoff_accepts_killing_move_only():
    # Gate level: exactly the killing equal trade opens at age 3.
    assert siege_release(0, 1, 3, True)
    assert siege_release(1, 2, 3, True)
    assert not siege_release(0, 1, 3, False)  # non-killer stays shut
    assert not siege_release(0, 2, 3, True)  # losing trade stays shut
    assert not siege_release(0, 0, 3, True)  # not a trade at all
    assert not siege_release(1, 1, 3, True)  # winning trades need no gate
    # Provisional proof: east from (10,10) dies killing E.
    assert siege_would_kill([(10, 10)], [(10, 12)], (10, 10), (10, 11), 5, 20, 20)
    # Bot level: the same staring ant holds twice, then takes east.
    bot = fresh_siege()
    for turn in range(3):
        state = kill_box()
        bot.do_turn(state)
        if turn < 2:
            assert state.orders == [], f"turn {turn}: {state.orders}"
        else:
            assert ((10, 10), "e") in state.orders


def test_suicide_without_kill_refused_at_any_age():
    # Provisional proof: east into 1v2 dies killing nothing.
    assert not siege_would_kill(
        [(10, 10)], [(10, 12), (11, 12)], (10, 10), (10, 11), 5, 20, 20
    )
    bot = fresh_siege()
    bot.siege_age = {(10, 10): 99}
    bot._prev_siege_positions = {(10, 10)}
    state = suicide_box()
    bot.do_turn(state)
    assert state.orders == []
    # Even a five-turn stare never talks the ant into it.
    bot2 = fresh_siege()
    for _ in range(5):
        state = suicide_box()
        bot2.do_turn(state)
        assert state.orders == []


def test_contact_age_counts_holds_breaks_moves_and_gaps():
    r2, rows, cols = 5, 20, 20
    ants = [(10, 10)]
    enemies = [(10, 12)]
    age = update_siege_age({}, set(), ants, enemies, r2, rows, cols)
    assert age == {(10, 10): 1}
    prev = set(ants)
    age = update_siege_age(age, prev, ants, enemies, r2, rows, cols)
    assert age == {(10, 10): 2}
    age = update_siege_age(age, prev, ants, enemies, r2, rows, cols)
    assert age == {(10, 10): 3}
    # The ant steps away: the new square starts fresh at 1.
    moved = [(10, 11)]
    age = update_siege_age(age, set(ants), moved, enemies, r2, rows, cols)
    assert age == {(10, 11): 1}
    # Contact lost (enemy gone): the age drops off the map.
    age = update_siege_age(age, set(moved), moved, [], r2, rows, cols)
    assert age == {}
    # A newcomer stepping into contact starts at 1, not 3.
    age = update_siege_age(age, {(0, 0)}, ants, enemies, r2, rows, cols)
    assert age == {(10, 10): 1}


def _time_update(
    old: dict[Loc, int],
    prev: set[Loc],
    own: list[Loc],
    enemies: list[Loc],
    r2: int,
    rows: int,
    cols: int,
) -> float:
    start = time.perf_counter()
    update_siege_age(old, prev, own, enemies, r2, rows, cols)
    return (time.perf_counter() - start) * 1000


def test_contact_age_tracking_under_1ms_on_crowded_board():
    rows, cols, r2 = 40, 40, 5
    own = [(8 + (i % 15), 8 + (i // 15)) for i in range(150)]
    enemies = [(8 + (i % 15), 10 + (i // 15)) for i in range(150)]
    prev = set(own)
    old = dict.fromkeys(own, 2)
    update_siege_age(old, prev, own, enemies, r2, rows, cols)  # warmup
    best_ms = min(
        _time_update(old, prev, own, enemies, r2, rows, cols) for _ in range(5)
    )
    new = update_siege_age(old, prev, own, enemies, r2, rows, cols)
    assert len(new) == 150
    assert all(v == 3 for v in new.values())
    assert best_ms < 1.0, f"{best_ms:.3f}ms"
