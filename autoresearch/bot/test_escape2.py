#!/usr/bin/env python
"""Escape2 (most-open escape) tests. No engine games.

The one change over champion Denial: in the stuck-exploration
fallback, among the moves the safety filter already passes, the ant
takes the one with the most open space (passable squares within
Manhattan radius 3) instead of the least-visited-first order. Safety
verdicts are unchanged.
"""

import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Escape2  # noqa: E402

Loc = tuple[int, int]

AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}

OPEN_SPOT: Loc = (11, 10)
TIGHT_SPOT: Loc = (9, 10)
HOME: Loc = (10, 10)


class FakeAnts:
    """Minimal stand-in for ants.Ants covering do_turn's surface."""

    def __init__(
        self,
        rows: int,
        cols: int,
        land: set[Loc],
        mine: list[Loc],
        enemies: list[Loc],
    ) -> None:
        self.rows = rows
        self.cols = cols
        self._land = land
        self._mine = mine
        self._enemies = enemies
        self.attackradius2 = 5
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
        return []

    def destination(self, loc: Loc, direction: str) -> Loc:
        dr, dc = AIM[direction]
        return ((loc[0] + dr) % self.rows, (loc[1] + dc) % self.cols)

    def distance(self, a: Loc, b: Loc) -> int:
        return min(abs(a[0] - b[0]), self.rows - abs(a[0] - b[0])) + min(
            abs(a[1] - b[1]), self.cols - abs(a[1] - b[1])
        )

    def passable(self, loc: Loc) -> bool:
        return loc in self._land

    def unoccupied(self, loc: Loc) -> bool:
        return loc in self._land and loc not in self._mine and loc not in self._enemies

    def time_remaining(self) -> int:
        return 100000

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)


def _diamond(center: Loc, radius: int) -> set[Loc]:
    out: set[Loc] = set()
    for dr in range(-radius, radius + 1):
        for dc in range(-(radius - abs(dr)), radius - abs(dr) + 1):
            out.add((center[0] + dr, center[1] + dc))
    return out


def _escape_board() -> set[Loc]:
    # HOME ant; OPEN_SPOT ('s') sits in a clear diamond (openness 25);
    # TIGHT_SPOT ('n') is land but ringed by water (openness 2: itself
    # plus HOME). 'e'/'w' neighbours are water: exactly two candidates.
    land = _diamond(OPEN_SPOT, 3)
    land.add(HOME)
    land.add(TIGHT_SPOT)
    return land


def _make_bot() -> Any:
    return Escape2.Escape2()


def test_two_safe_moves_pick_the_opener():
    # Visits are seeded against openness (tight 0, open 9): champion
    # order would take tight 'n'; most-open escape must take 's'.
    fake: Any = FakeAnts(20, 20, _escape_board(), [HOME], [])
    bot = _make_bot()
    bot.visits = {TIGHT_SPOT: 0, OPEN_SPOT: 9}
    bot.do_turn(fake)
    assert fake.orders == [(HOME, "s")]


def test_unsafe_open_loses_to_safe_tight():
    # Open square least-visited AND most open, but an enemy sits on it
    # (sq_dist 1 <= attackradius2): safety still wins, tight 'n' moves.
    land = _escape_board()
    land.add((12, 10))
    fake: Any = FakeAnts(20, 20, land, [HOME], [(12, 10)])
    bot = _make_bot()
    bot.visits = {TIGHT_SPOT: 9, OPEN_SPOT: 0}
    bot.do_turn(fake)
    assert fake.orders == [(HOME, "n")]


def test_single_safe_move_byte_identical_to_champion():
    # Only 'e' is passable+safe: Escape2 must issue exactly the
    # champion's orders on the identical position.
    import importlib.util

    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
    spec = importlib.util.spec_from_file_location(
        "champion_denial", os.path.join(root, "champion-Denial.py")
    )
    assert spec is not None and spec.loader is not None
    champ_mod: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(champ_mod)
    land = {HOME, (10, 11)}
    new_fake: Any = FakeAnts(20, 20, land, [HOME], [])
    old_fake: Any = FakeAnts(20, 20, land, [HOME], [])
    new_bot = _make_bot()
    old_bot: Any = champ_mod.Denial()
    new_bot.do_turn(new_fake)
    old_bot.do_turn(old_fake)
    assert new_fake.orders == old_fake.orders == [(HOME, "e")]


def test_openness_counts_diamond_on_open_board():
    fake: Any = FakeAnts(10, 10, {(r, c) for r in range(10) for c in range(10)}, [], [])
    assert Escape2.open_space(fake, (5, 5)) == 25
    assert Escape2.open_space(fake, (0, 0)) == 25


def test_openness_scan_costs_under_1ms_on_crowded_board():
    rows, cols = 30, 30
    land = {
        (r, c) for r in range(rows) for c in range(cols) if (r * 7 + c * 13) % 5 != 0
    }
    land.add((15, 15))
    fake: Any = FakeAnts(rows, cols, land, [(15, 15)], [])
    start = time.perf_counter()
    seen = Escape2.open_space(fake, (15, 15))
    elapsed = time.perf_counter() - start
    assert seen > 0
    assert elapsed < 0.001
