#!/usr/bin/env python
"""Scout-2 early chicken-probe tests. No engine games.

One change over champion Denial: at turn 10 the ant nearest the
nearest known enemy hill detaches as a scout and walks that hill;
on first enemy contact it retreats toward home, and by turn 60 it
rejoins the economy. Turns 1-9 and 60+ are byte-identical to the
champion; every other ant is unaffected on every turn.
"""

import os
import sys
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Scout2  # noqa: E402

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
        hills: list[Loc],
        foods: list[Loc],
        enemies: list[Loc] | None = None,
        homes: list[Loc] | None = None,
    ) -> None:
        self._ants = list(ants)
        self._hills = list(hills)
        self._foods = list(foods)
        self._enemies = list(enemies or [])
        self._homes = list(homes if homes is not None else [(0, 0)])
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


def fresh_orders(
    ants: list[Loc],
    hills: list[Loc],
    foods: list[Loc],
    enemies: list[Loc],
    turn: int,
    homes: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    bot = Scout2.Scout2()
    fake = FakeAnts(ants, hills, foods, enemies, homes)
    bot.do_setup(cast(Any, fake))
    bot.turn = turn - 1
    bot.do_turn(cast(Any, fake))
    assert bot.turn == turn
    return list(fake.orders)


def step_to(order: tuple[Loc, str], fake: FakeAnts) -> Loc:
    return fake.destination(order[0], order[1])


# Shared board: army camps hill A, one ant strays near hill B.
# Muster aims at A (nearest the army); the stray ant is nearest B,
# so the scout detaches toward B while the champion would muster
# it back to A.
ARMY: list[Loc] = [(10, 2), (10, 3), (10, 4)]
STRAY: Loc = (10, 14)
HILL_A: Loc = (10, 8)
HILL_B: Loc = (10, 16)
HOME: Loc = (0, 0)


def test_scout_window_gate() -> None:
    for turn in (1, 5, 9):
        assert Scout2.scout_window(turn) is False
    for turn in (10, 11, 30, 59):
        assert Scout2.scout_window(turn) is True
    for turn in (60, 61, 100, 400):
        assert Scout2.scout_window(turn) is False


def test_pick_scout_takes_nearest_pair() -> None:
    ants = ARMY + [STRAY]
    ai, hill = Scout2.pick_scout(ants, [HILL_A, HILL_B], torus)
    assert ants[ai] == STRAY
    assert hill == HILL_B


def test_contact_radius() -> None:
    assert Scout2.scout_contacted((10, 10), [(10, 15)], torus) is True
    assert Scout2.scout_contacted((10, 10), [(10, 16)], torus) is False
    assert Scout2.scout_contacted((10, 10), [], torus) is False


def apply_orders(cur: list[Loc], fake: FakeAnts) -> list[Loc]:
    nxt: list[Loc] = list(cur)
    for loc, d in fake.orders:
        if loc in nxt:
            nxt.remove(loc)
            nxt.append(fake.destination(loc, d))
    return nxt


def test_turns_1_to_9_match_champion() -> None:
    # Fresh bot, fixed board: champion-equivalent turns must agree
    # byte-for-byte, since the scout gate is shut before turn 10.
    ants = ARMY + [STRAY]
    ref = fresh_orders(ants, [HILL_A, HILL_B], [], [], 1)
    assert ref != []
    for turn in (2, 5, 9):
        assert fresh_orders(ants, [HILL_A, HILL_B], [], [], turn) == ref


def test_turn_10_dispatches_exactly_one_scout() -> None:
    ants = ARMY + [STRAY]
    base = fresh_orders(ants, [HILL_A, HILL_B], [], [], 9)
    probe = fresh_orders(ants, [HILL_A, HILL_B], [], [], 10)
    assert len(base) == len(probe) == len(ants)
    diffs = [i for i in range(len(ants)) if base[i] != probe[i]]
    assert diffs == [3]
    fake = FakeAnts(ants, [HILL_A, HILL_B], [], [])
    scout_order = probe[3]
    assert scout_order[0] == STRAY
    assert torus(step_to(scout_order, fake), HILL_B) < torus(STRAY, HILL_B)
    assert torus(step_to(scout_order, fake), HILL_A) > torus(STRAY, HILL_A)


def test_no_hill_means_no_scout_at_turn_10() -> None:
    ants = ARMY + [STRAY]
    base = fresh_orders(ants, [], [], [], 9)
    assert fresh_orders(ants, [], [], [], 10) == base


def test_contact_triggers_retreat() -> None:
    # Drive one bot: dispatch at 10, then an enemy in contact range
    # of the scout at 11 (well off its homeward step squares). The
    # scout must step homeward while the army still musters on A.
    ants = ARMY + [STRAY]
    bot = Scout2.Scout2()
    fake10 = FakeAnts(ants, [HILL_A, HILL_B], [], [], [HOME])
    bot.do_setup(cast(Any, fake10))
    bot.turn = 9
    bot.do_turn(cast(Any, fake10))
    assert bot.turn == 10
    assert bot.scout_loc is not None
    scout_at_10 = bot.scout_loc
    assert torus(scout_at_10, HILL_B) < torus(STRAY, HILL_B)
    cur = apply_orders(ants, fake10)
    assert scout_at_10 in cur
    contact: Loc = (10, 10)
    assert torus(scout_at_10, contact) <= Scout2.SCOUT_CONTACT_R
    fake11 = FakeAnts(cur, [HILL_A, HILL_B], [], [contact], [HOME])
    bot.do_turn(cast(Any, fake11))
    assert bot.turn == 11
    assert bot.retreating is True
    scout_orders = [o for o in fake11.orders if o[0] == scout_at_10]
    assert len(scout_orders) == 1
    after = step_to(scout_orders[0], fake11)
    assert torus(after, HOME) < torus(scout_at_10, HOME)


def test_immediate_contact_retreats_at_dispatch() -> None:
    # Enemy already adjacent at turn 10: the scout retreats at
    # once instead of walking into the fight.
    ants = ARMY + [STRAY]
    contact: Loc = (10, 9)
    assert torus(STRAY, contact) <= Scout2.SCOUT_CONTACT_R
    probe = fresh_orders(ants, [HILL_A, HILL_B], [], [contact], 10, [HOME])
    stray_orders = [o for o in probe if o[0] == STRAY]
    assert len(stray_orders) == 1
    fake = FakeAnts(ants, [HILL_A, HILL_B], [], [contact], [HOME])
    assert torus(step_to(stray_orders[0], fake), HOME) < torus(STRAY, HOME)


def test_turn_60_matches_champion() -> None:
    # Past the window the scout is gone: turns 60+ agree with the
    # pre-10 champion baseline on the same board.
    ants = ARMY + [STRAY]
    ref = fresh_orders(ants, [HILL_A, HILL_B], [], [], 1)
    for turn in (60, 61, 100):
        assert fresh_orders(ants, [HILL_A, HILL_B], [], [], turn) == ref


def test_scout_state_cleared_at_60() -> None:
    # A live scout driven into turn 60 vanishes: state cleared and
    # orders byte-identical to a scout-less bot on the same board.
    ants = ARMY + [STRAY]
    enemies: list[Loc] = [(10, 10)]
    scouted = Scout2.Scout2()
    fake = FakeAnts(ants, [HILL_A, HILL_B], [], enemies, [HOME])
    scouted.do_setup(cast(Any, fake))
    scouted.turn = 59
    scouted.scout_loc = STRAY
    scouted.scout_hill = HILL_B
    scouted.scout_home = HOME
    scouted.retreating = True
    scouted.do_turn(cast(Any, fake))
    assert scouted.turn == 60
    assert scouted.scout_loc is None
    assert scouted.scout_hill is None
    assert scouted.scout_home is None
    assert scouted.retreating is False
    champion = fresh_orders(ants, [HILL_A, HILL_B], [], enemies, 60, [HOME])
    assert fake.orders == champion
