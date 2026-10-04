#!/usr/bin/env python
"""Understudy2 (two-turn rotation of failed hill challengers) tests.

No engine games.

One change over champion Denial: when a hill challenge fails (the
muster hill is still enemy-held next turn), the last challenger
sits out that hill's next TWO challenges and a different ant goes
instead. The muster target formula is unchanged; success, other
hills, and single-ant armies all keep normal nearest-ant picks.
"""

import os
import sys
import time
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Understudy2 as U2  # noqa: E402

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
    homes: list[Loc],
) -> FakeAnts:
    fake = FakeAnts(ants, [], [], homes, hills)
    bot.do_turn(cast(Any, fake))
    return fake


def moved_to(fake: FakeAnts, origin: Loc) -> Loc:
    for o, d in fake.orders:
        if o == origin:
            return fake.destination(o, d)
    raise AssertionError(f"ant {origin} issued no order")


H1: Loc = (10, 5)
H2: Loc = (19, 19)
HOME: list[Loc] = [(10, 15)]
A: Loc = (10, 10)
B: Loc = (0, 0)
C: Loc = (0, 19)


def fresh_bot() -> Any:
    bot = U2.Understudy2()
    bot.do_setup(cast(Any, FakeAnts([], [], [], [], [])))
    return bot


def test_pick_challenger_is_nearest() -> None:
    assert U2.pick_challenger(H1, [A, B], torus) == A
    assert U2.pick_challenger(H1, [B, A], torus) == A


def test_pick_challenger_skips_excluded_set() -> None:
    assert U2.pick_challenger(H1, [A, B, C], torus, {A}) == B
    assert U2.pick_challenger(H1, [A, B, C], torus, {A, B}) == C
    assert U2.pick_challenger(H1, [A, B], torus, {A, B}) is None
    assert U2.pick_challenger(H1, [A], torus, {A}) is None
    assert U2.pick_challenger(H1, [], torus) is None


def test_exclusions_need_failed_challenge() -> None:
    held = {H1}
    rec = {H1: [A]}
    # Same hill, still held: the recorded challenger is excluded.
    assert U2.challenge_exclusions(H1, H1, held, rec, [A, B], torus) == {A}
    # Other hill, no last target, hill freed, or no record: open pick.
    assert U2.challenge_exclusions(H2, H1, held, rec, [A, B], torus) == set()
    assert U2.challenge_exclusions(H1, None, held, rec, [A, B], torus) == set()
    assert U2.challenge_exclusions(H1, H1, set(), rec, [A, B], torus) == set()
    assert U2.challenge_exclusions(H1, H1, held, {}, [A, B], torus) == set()


def test_exclusions_match_by_age() -> None:
    # Newest record (age 1): the challenger one step away is still
    # the same ant; two steps away means it is gone.
    assert U2.challenge_exclusions(
        H1, H1, {H1}, {H1: [(10, 10)]}, [(10, 9), B], torus
    ) == {(10, 9)}
    assert (
        U2.challenge_exclusions(H1, H1, {H1}, {H1: [(10, 10)]}, [(9, 9), B], torus)
        == set()
    )
    # Older record (age 2): the ant moved up to two squares since,
    # so a challenger two steps away is still recognised.
    assert U2.challenge_exclusions(
        H1, H1, {H1}, {H1: [(10, 10), (5, 6)]}, [(9, 9), (5, 5), C], torus
    ) == {(9, 9), (5, 5)}
    # A record whose ant is farther than its age allows is gone.
    assert (
        U2.challenge_exclusions(H1, H1, {H1}, {H1: [(10, 10)]}, [(0, 5), B], torus)
        == set()
    )


def test_failures_rotate_three_turns() -> None:
    # Turn 1: nearest ant A challenges H1. Turn 2: H1 still held,
    # so A sits out and B goes. Turn 3: both A and B sit out and
    # C goes -- the two-turn window, not the one-turn A-B-A.
    bot = fresh_bot()
    turn1 = run_turn(bot, [A, B, C], [H1], HOME)
    assert turn1.orders[0] == (A, "w")
    assert bot.challenger_history.get(H1) == [A]
    a2 = moved_to(turn1, A)
    assert a2 == (10, 9)
    b2 = moved_to(turn1, B)
    c2 = moved_to(turn1, C)
    turn2 = run_turn(bot, [a2, b2, c2], [H1], HOME)
    assert bot.challenger_history.get(H1) == [A, b2]
    assert (a2, "w") not in turn2.orders
    assert (a2, "n") in turn2.orders
    a3 = moved_to(turn2, a2)
    b3 = moved_to(turn2, b2)
    c3 = moved_to(turn2, c2)
    assert U2.challenge_exclusions(
        H1, H1, {H1}, {H1: [A, b2]}, [a3, b3, c3], torus
    ) == {
        a3,
        b3,
    }
    turn3 = run_turn(bot, [a3, b3, c3], [H1], HOME)
    assert bot.challenger_history.get(H1) == [b2, c3]
    assert c3 in [o for o, _ in turn3.orders]


def test_two_ant_army_keeps_first_failure_excluded() -> None:
    # Only A and B: on turn 3 both are inside the window, so the
    # fallback retries the nearest ant while A stays excluded.
    bot = fresh_bot()
    turn1 = run_turn(bot, [A, B], [H1], HOME)
    assert bot.challenger_history.get(H1) == [A]
    ants2 = [moved_to(turn1, A), moved_to(turn1, B)]
    turn2 = run_turn(bot, ants2, [H1], HOME)
    assert bot.challenger_history.get(H1) == [A, ants2[1]]
    ants3 = [moved_to(turn2, a) for a in ants2]
    excluded = U2.challenge_exclusions(H1, H1, {H1}, {H1: [A, ants2[1]]}, ants3, torus)
    assert ants3[0] in excluded
    assert len(excluded) == 2
    turn3 = run_turn(bot, ants3, [H1], HOME)
    assert U2.pick_challenger(H1, ants3, torus, excluded) is None
    assert len(turn3.orders) == 2


def test_stale_record_frees_the_ant() -> None:
    # The two-turn window lapses: a record two turns old whose ant
    # moved three squares matches nobody, so that ant challenges
    # again while the fresher record still sits out.
    bot = fresh_bot()
    bot.remembered_hills = {H1}
    bot.last_target = H1
    bot.challenger_history = {H1: [(10, 10), (5, 6)]}
    ants = [(8, 9), (5, 5), (0, 0)]
    turn = run_turn(bot, ants, [H1], HOME)
    assert turn.orders[0][0] == (8, 9)
    assert bot.challenger_history.get(H1) == [(5, 6), (8, 9)]


def test_successful_challenge_keeps_normal_selection() -> None:
    # H1 captured on turn 2 (an ant stands on it, razed from the
    # hill list): tracking is pruned, and the next challenge of
    # the re-held hill picks the plain nearest ant again.
    bot = fresh_bot()
    run_turn(bot, [A, B], [H1], HOME)
    assert bot.challenger_history.get(H1) == [A]
    run_turn(bot, [H1, B], [], HOME)
    assert H1 not in bot.challenger_history
    assert bot.last_target is None
    turn3 = run_turn(bot, [(10, 6), (0, 5)], [H1], HOME)
    assert bot.challenger_history.get(H1) == [(10, 6)]
    assert turn3.orders[0] == ((10, 6), "w")


def test_rotation_is_per_hill() -> None:
    # H1 failed with A, but H2 is a fresh hill: A still answers
    # H2 (reinforce) while only B challenges H1.
    bot = fresh_bot()
    turn1 = run_turn(bot, [A, B], [H1], HOME)
    ants2 = [moved_to(turn1, A), moved_to(turn1, B)]
    turn2 = run_turn(bot, ants2, [H1, H2], HOME)
    assert bot.challenger_history.get(H1) == [A, ants2[1]]
    assert (ants2[0], "w") not in turn2.orders
    assert ants2[0] in [o for o, _ in turn2.orders]
    assert ants2[1] in [o for o, _ in turn2.orders]


def test_single_ant_keeps_challenging() -> None:
    # No understudy exists: the lone ant retries the failed hill
    # on turns 2 and 3 instead of sitting itself out.
    bot = fresh_bot()
    turn1 = run_turn(bot, [A], [H1], HOME)
    assert turn1.orders == [(A, "w")]
    turn2 = run_turn(bot, [(10, 9)], [H1], HOME)
    assert ((10, 9), "w") in turn2.orders
    assert bot.challenger_history.get(H1) == [A, (10, 9)]
    a3 = moved_to(turn2, (10, 9))
    turn3 = run_turn(bot, [a3], [H1], HOME)
    assert a3 in [o for o, _ in turn3.orders]


def test_tracking_costs_under_half_a_ms() -> None:
    # The per-turn tracking (exclusion match plus challenger
    # pick over a 120-ant army) must stay far under 0.5ms.
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(120)]
    rec = {H1: [ants[0], ants[1]]}
    held = {H1}
    n = 2000
    start = time.perf_counter()
    for _ in range(n):
        out = U2.challenge_exclusions(H1, H1, held, rec, ants, torus)
        assert U2.pick_challenger(H1, ants, torus, out) is not None
    assert (time.perf_counter() - start) / n < 0.0005


def test_crowded_board_turn_stays_fast() -> None:
    # 120 ants plus a failed hill challenge: the full turn still
    # finishes well under the 1000ms turn budget.
    bot = fresh_bot()
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(120)]
    run_turn(bot, ants, [H1], HOME)
    ants2 = ants[:]
    start = time.perf_counter()
    run_turn(bot, ants2, [H1, H2], HOME)
    assert time.perf_counter() - start < 1.0
