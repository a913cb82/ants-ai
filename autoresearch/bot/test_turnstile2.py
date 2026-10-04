#!/usr/bin/env python
"""Turnstile2 (short-fuse sitter rotation) tests.

No engine games.

One change over champion Denial: an ant that sits on the same
square for 30+ consecutive turns rotates off -- it steps toward
the nearest non-sitting ant (falling back to the least-visited
safe square) instead of continuing champion economy -- so
visit-maps stay fresh and no ant idles for 50 turns. A sitter under
direct threat (enemy inside the attack radius) stays put, and
ants that moved recently never rotate.
"""

import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Turnstile2 as TS  # noqa: E402

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


def _no_swaps(
    sit: dict[Loc, int],
    ants_list: list[Loc],
    enemy_locs: list[Loc],
    attackradius2: int,
    rows: int,
    cols: int,
) -> dict[Loc, Loc]:
    return {}


def run_turn(
    mine: list[Loc],
    enemies: list[Loc],
    sit: dict[Loc, int] | None = None,
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], Any]:
    fake = FakeAnts(mine, enemies, foods, water)
    bot = TS.Turnstile2()
    bot.sit = dict(sit or {})
    bot.do_turn(fake)
    return fake.orders, bot


def step_to(fake: FakeAnts, loc: Loc, direction: str) -> Loc:
    return fake.destination(loc, direction)


def test_sitter_rotates_off_after_30() -> None:
    # (5,5) sat 30 turns; partner at (10,10). The sitter must vacate
    # toward its partner while a fresh ant would explore north.
    mine = [(5, 5), (10, 10)]
    orders, _ = run_turn(mine, [], {(5, 5): 30})
    assert (5, 5) in dict(orders)
    probe = FakeAnts(mine, [])
    moved = step_to(probe, (5, 5), dict(orders)[(5, 5)])
    assert probe.distance(moved, (10, 10)) < probe.distance((5, 5), (10, 10))
    fresh, _ = run_turn(mine, [], {(5, 5): 29})
    assert dict(fresh).get((5, 5)) != dict(orders).get((5, 5))
    assert dict(fresh).get((5, 5)) == "n"  # champion explore, untouched


def test_sitter_below_limit_matches_champion() -> None:
    # A 29-turn sitter stays as champion: the turn matches
    # rotation-off orders exactly.
    mine = [(5, 5), (10, 10)]
    assert TS.turnstile_swaps({(5, 5): 29}, mine, [], 5, ROWS, COLS) == {}
    assert TS.turnstile_swaps({(5, 5): 30}, mine, [], 5, ROWS, COLS) != {}
    orig = TS.turnstile_swaps
    TS.turnstile_swaps = _no_swaps
    try:
        assert run_turn(mine, [], {(5, 5): 29})[0] == run_turn(mine, [])[0]
    finally:
        TS.turnstile_swaps = orig


def test_threatened_sitter_stays() -> None:
    # Enemy adjacent to the 99-turn sitter: direct threat, so no
    # rotation entry and the sitter holds its square.
    mine = [(5, 5), (15, 15)]
    enemies = [(5, 6)]
    assert TS.turnstile_swaps({(5, 5): 99}, mine, enemies, 5, ROWS, COLS) == {}
    orders, _ = run_turn(mine, enemies, {(5, 5): 99})
    assert (5, 5) not in dict(orders)


def test_movers_never_rotate() -> None:
    # Squares below the limit -- including stale keys for squares no
    # ant occupies -- never produce a swap.
    mine = [(5, 5), (10, 10)]
    assert TS.turnstile_swaps({(5, 5): 29, (0, 0): 500}, mine, [], 5, ROWS, COLS) == {}
    assert TS.turnstile_swaps({}, mine, [], 5, ROWS, COLS) == {}
    # Full turns with all sits below the limit match rotation-off.
    import random

    rng = random.Random(39)
    locs = [(r, c) for r in range(ROWS) for c in range(COLS)]
    orig = TS.turnstile_swaps
    TS.turnstile_swaps = _no_swaps
    try:
        for _ in range(100):
            n_ants = rng.randint(1, 6)
            pick = rng.sample(locs, n_ants + rng.randint(0, 5))
            ants_here = pick[:n_ants]
            foes = pick[n_ants:]
            sit = {a: rng.randint(0, 29) for a in ants_here}
            assert run_turn(ants_here, foes, sit)[0] == run_turn(ants_here, foes)[0]
    finally:
        TS.turnstile_swaps = orig


def test_rotation_bookkeeping_under_half_ms() -> None:
    import random

    rng = random.Random(7)
    rows = cols = 100
    locs = [(r, c) for r in range(rows) for c in range(cols)]
    mine = rng.sample(locs, 300)
    foes = rng.sample(locs, 30)
    sit = {m: rng.randint(0, 29) for m in mine}
    for m in mine[:3]:
        sit[m] = 30 + rng.randint(0, 5)
    ordered = set(mine[::2])
    reps = 100
    start = time.perf_counter()
    for _ in range(reps):
        swaps = TS.turnstile_swaps(sit, mine, foes, 5, rows, cols)
        TS.age_sits(dict(sit), mine, ordered)
    elapsed = (time.perf_counter() - start) / reps
    assert len(swaps) == 3
    assert elapsed < 0.0005
