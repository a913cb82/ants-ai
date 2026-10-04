#!/usr/bin/env python
"""Outcast (army-wide rotation of failed hill challengers) tests.

No engine games.

One change over champion Denial: when a hill challenge fails (last
turn's muster hill is still enemy-held), the last challenger sits
out EVERY hill for one turn -- not just the failed hill -- and a
different ant goes instead. The muster target formula is unchanged;
success, a new turn, and single-ant armies all keep normal picks.
"""

import os
import sys
import time
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Outcast as OC  # noqa: E402

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
    ) -> None:
        self._ants = list(ants)
        self._foods = list(foods)
        self._enemies = list(enemies)
        self._homes = list(homes)
        self._hills = list(hills)
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
        return True

    def unoccupied(self, loc: Loc) -> bool:
        assert 0 <= loc[0] < ROWS and 0 <= loc[1] < COLS
        return loc not in self._ants and loc not in self._enemies

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 10000


def run_turn(
    bot: Any,
    ants: list[Loc],
    hills: list[Loc],
    homes: list[Loc] | None = None,
) -> FakeAnts:
    fake = FakeAnts(ants, [], [], homes or [], hills)
    bot.do_turn(cast(Any, fake))
    return fake


def moved_to(fake: FakeAnts, origin: Loc) -> Loc:
    for o, d in fake.orders:
        if o == origin:
            return fake.destination(o, d)
    raise AssertionError(f"ant {origin} issued no order")


H1: Loc = (10, 5)
H2: Loc = (10, 18)
A: Loc = (10, 10)
B: Loc = (1, 1)


def fresh_bot() -> Any:
    bot = OC.Outcast()
    bot.do_setup(cast(Any, FakeAnts([], [], [], [], [])))
    return bot


def open_challenge() -> tuple[Any, Loc, Loc]:
    """Turn 1: A is nearest H1, challenges it, steps to (10, 9)."""
    bot = fresh_bot()
    fake = run_turn(bot, [A, B], [H1, H2])
    assert moved_to(fake, A) == (10, 9)
    assert bot.last_target == H1
    assert bot.last_challenger[H1] == A
    return bot, moved_to(fake, B), (10, 9)


def test_pick_challenger_is_nearest() -> None:
    assert OC.pick_challenger(H1, [A, B], torus) == A
    assert OC.pick_challenger(H1, [B, A], torus) == A


def test_pick_challenger_skips_excluded() -> None:
    assert OC.pick_challenger(H1, [A, B], torus, exclude=A) == B
    assert OC.pick_challenger(H1, [A, B], torus, exclude=B) == A
    assert OC.pick_challenger(H1, [A], torus, exclude=A) is None
    assert OC.pick_challenger(H1, [], torus) is None


def test_exclusion_needs_failed_challenge() -> None:
    held = {H1, H2}
    rec = {H1: A}
    ants = [A, B]
    # Last turn's muster hill still held: the challenger sits out.
    assert OC.challenge_exclusion(H1, held, rec, ants, torus) == A
    # No last target, hill freed, or no record: open pick.
    assert OC.challenge_exclusion(None, held, rec, ants, torus) is None
    assert OC.challenge_exclusion(H1, {H2}, rec, ants, torus) is None
    assert OC.challenge_exclusion(H1, held, {}, ants, torus) is None


def test_exclusion_follows_moved_challenger() -> None:
    # The recorded challenger stepped one square: still the same ant.
    rec = {H1: A}
    assert OC.challenge_exclusion(H1, {H1}, rec, [(10, 9), B], torus) == (10, 9)
    # Gone (or dead and respawned far away): no exclusion.
    assert OC.challenge_exclusion(H1, {H1}, rec, [(0, 0), B], torus) is None
    assert OC.challenge_exclusion(H1, {H1}, rec, [], torus) is None


def test_exclusion_ignores_this_turn_muster() -> None:
    # Army-wide scope: even when this turn musters a DIFFERENT hill,
    # the failed challenger is still the excluded ant.
    rec = {H1: A}
    assert OC.challenge_exclusion(H1, {H1, H2}, rec, [A, B], torus) == A


def test_failed_challenger_sits_out_every_hill() -> None:
    # (a) Turn 2, both hills still held: A advances on neither hill
    # while B (the understudy) advances on the muster hill.
    bot, b2, a2 = open_challenge()
    fake = run_turn(bot, [a2, b2], [H1, H2])
    new_a = moved_to(fake, a2)
    assert torus(new_a, H1) >= torus(a2, H1)
    assert torus(new_a, H2) >= torus(a2, H2)
    assert torus(moved_to(fake, b2), H1) < torus(b2, H1)


def test_benched_ant_skips_reinforcement_too() -> None:
    # Army-wide means the reinforce block also skips the benched ant:
    # with the muster hill gone from A's reach, A still takes no
    # hill order. Same board as (a); A must not step toward H2 even
    # though per-hill scope would let it reinforce there.
    bot, b2, a2 = open_challenge()
    fake = run_turn(bot, [a2, b2], [H1, H2])
    new_a = moved_to(fake, a2)
    assert torus(new_a, H2) >= torus(a2, H2)


def test_challenger_returns_next_turn() -> None:
    # (b) Turn 3, hills still held: the bench rotates to B, so A is
    # eligible again and advances on the muster hill.
    bot, b2, a2 = open_challenge()
    fake2 = run_turn(bot, [a2, b2], [H1, H2])
    a3 = moved_to(fake2, a2)
    b3 = moved_to(fake2, b2)
    fake3 = run_turn(bot, [a3, b3], [H1, H2])
    assert torus(moved_to(fake3, a3), H1) < torus(a3, H1)


def test_success_clears_tracking() -> None:
    # (c) Razed hill: A stands on H1, so it leaves remembered hills
    # and nobody is excluded -- both ants advance on H2.
    bot, b2, _ = open_challenge()
    assert (
        OC.challenge_exclusion(H1, {H2}, bot.last_challenger, [H1, b2], torus) is None
    )
    fake = run_turn(bot, [H1, b2], [H2])
    assert torus(moved_to(fake, H1), H2) < torus(H1, H2)
    assert torus(moved_to(fake, b2), H2) < torus(b2, H2)


def test_lone_ant_never_benches_itself() -> None:
    bot = fresh_bot()
    fake1 = run_turn(bot, [A], [H1])
    a2 = moved_to(fake1, A)
    assert torus(a2, H1) < torus(A, H1)
    fake2 = run_turn(bot, [a2], [H1])
    assert torus(moved_to(fake2, a2), H1) < torus(a2, H1)


def test_exclusion_check_costs_under_half_ms() -> None:
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(60)]
    rec = {H1: ants[0]}
    held = {H1, H2}
    n = 2000
    start = time.perf_counter()
    for _ in range(n):
        OC.challenge_exclusion(H1, held, rec, ants, torus)
    assert (time.perf_counter() - start) / n < 0.0005


def test_crowded_board_turn_stays_fast() -> None:
    bot = fresh_bot()
    run_turn(bot, [A, B], [H1, H2])
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(120)]
    start = time.perf_counter()
    run_turn(bot, ants, [H1, H2])
    assert time.perf_counter() - start < 1.0
