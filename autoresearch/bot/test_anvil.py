#!/usr/bin/env python
"""Anvil (bait-and-ambush) tests.

No engine games.

One change over champion Denial: a lone ant adjacent to 2+ enemies
is bait -- the nearest 2 friends within 15 steps converge on the
bait's square instead of continuing economy, while the bait holds.
With fewer than 2 friends in reach no ambush forms and the turn is
champion-identical.
"""

import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Anvil as AV  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}


class FakeAnts:
    """Minimal stand-in for ants.Ants covering do_turn's interface."""

    def __init__(
        self,
        mine: list[Loc],
        enemies: list[Loc],
        foods: list[Loc] | None = None,
        water: set[Loc] | None = None,
    ) -> None:
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = 5
        self._mine = list(mine)
        self._enemies = list(enemies)
        self._foods = list(foods or [])
        self._water = set(water or set())
        self.orders: list[tuple[Loc, str]] = []

    def food(self) -> list[Loc]:
        return list(self._foods)

    def my_ants(self) -> list[Loc]:
        return list(self._mine)

    def enemy_ants(self) -> list[tuple[Loc, int]]:
        return [(e, 1) for e in self._enemies]

    def enemy_hills(self) -> list[tuple[Loc, int]]:
        return []

    def my_hills(self) -> list[Loc]:
        return []

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
) -> tuple[list[tuple[Loc, str]], Any]:
    fake = FakeAnts(mine, enemies, foods, water)
    bot = AV.Anvil()
    bot.do_turn(fake)
    return fake.orders, bot


def _no_anvil(
    ants_list: list[Loc], enemy_locs: list[Loc], rows: int, cols: int
) -> tuple[set[int], dict[int, Loc]]:
    return set(), {}


def test_bait_with_two_friends_pulls_both() -> None:
    # (5,5) sits between two enemies; friends at (5,0) and (0,5)
    # are each 5 steps away. Both must converge on the bait.
    mine = [(5, 5), (5, 0), (0, 5)]
    enemies = [(5, 6), (5, 4)]
    holders, rescues = AV.anvil_plans(mine, enemies, ROWS, COLS)
    assert holders == {0}
    assert rescues == {1: (5, 5), 2: (5, 5)}


def test_bait_holds_while_friends_close() -> None:
    # Even with food on the next square, the bait issues no order
    # and both rescuers step closer to it.
    mine = [(5, 5), (5, 0), (0, 5)]
    enemies = [(5, 6), (5, 4)]
    orders, _ = run_turn(mine, enemies, foods=[(6, 5)])
    by_src = dict(orders)
    assert (5, 5) not in by_src
    probe = FakeAnts(mine, enemies)
    for src in ((5, 0), (0, 5)):
        assert src in by_src
        moved = probe.destination(src, by_src[src])
        assert probe.distance(moved, (5, 5)) < probe.distance(src, (5, 5))


def test_bait_with_one_friend_is_champion() -> None:
    # One friend in reach: no ambush, plans empty, and the turn
    # matches the ambush-disabled (champion) path exactly.
    mine = [(5, 5), (5, 0)]
    enemies = [(5, 6), (5, 4)]
    assert AV.anvil_plans(mine, enemies, ROWS, COLS) == (set(), {})
    assert run_turn(mine, enemies)[0] == _champion_orders(mine, enemies)


def test_bait_with_distant_friends_is_champion() -> None:
    # Two friends exist but both are 19+ steps off: out of reach,
    # so no ambush forms.
    mine = [(5, 5), (15, 15), (15, 14)]
    enemies = [(5, 6), (5, 4)]
    assert AV.anvil_plans(mine, enemies, ROWS, COLS) == (set(), {})
    assert run_turn(mine, enemies)[0] == _champion_orders(mine, enemies)


def _champion_orders(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    orig = AV.anvil_plans
    AV.anvil_plans = _no_anvil
    try:
        fake = FakeAnts(mine, enemies, foods, water)
        AV.Anvil().do_turn(fake)
        return fake.orders
    finally:
        AV.anvil_plans = orig


def test_no_bait_turns_match_champion() -> None:
    # At most one enemy: bait (2+ adjacent foes) is impossible, so
    # every turn must equal the ambush-disabled path, over foods,
    # water, and ant counts.
    import random

    rng = random.Random(40)
    locs = [(r, c) for r in range(ROWS) for c in range(COLS)]
    for _ in range(100):
        n_ants = rng.randint(1, 6)
        pick = rng.sample(locs, n_ants + rng.randint(0, 4))
        mine = pick[:n_ants]
        foes = pick[n_ants : n_ants + 1]
        foods = rng.sample(locs, rng.randint(0, 3))
        water = set(rng.sample(locs, rng.randint(0, 5))) - set(mine)
        assert run_turn(mine, foes, foods, water)[0] == _champion_orders(
            mine, foes, foods, water
        )


def test_bait_scan_under_1ms() -> None:
    import random

    rng = random.Random(7)
    rows = cols = 100
    locs = [(r, c) for r in range(rows) for c in range(cols)]
    mine = rng.sample(locs, 300)
    foes = rng.sample(locs, 300)
    reps = 200
    start = time.perf_counter()
    for _ in range(reps):
        AV.anvil_plans(mine, foes, rows, cols)
    assert (time.perf_counter() - start) / reps < 0.001
