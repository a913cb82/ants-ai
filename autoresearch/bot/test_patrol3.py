#!/usr/bin/env python
"""Patrol-3 ranged enemy-hill patrol tests. No engine games.

One change over champion Denial: past turn 400, idle exploration
ants walk through the nearest uncontrolled enemy hill ONLY when it
is within 30 steps; farther hills are ignored and the ant explores
normally. Pre-400 orders are byte-identical to the champion; food,
guard, and hill-muster ants are unaffected at any turn.
"""

import importlib.util
import os
import sys
import time
from collections.abc import Callable
from typing import Any, cast

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Patrol3 as P3  # noqa: E402

Loc = tuple[int, int]


def make_torus(rows: int, cols: int) -> Callable[[Loc, Loc], int]:
    def torus(a: Loc, b: Loc) -> int:
        dr = abs(a[0] - b[0])
        dr = min(dr, rows - dr)
        dc = abs(a[1] - b[1])
        dc = min(dc, cols - dc)
        return dr + dc

    return torus


class FakeAnts:
    def __init__(
        self,
        ants: list[Loc],
        hills: list[Loc],
        foods: list[Loc],
        enemies: list[Loc] | None = None,
        rows: int = 20,
        cols: int = 20,
    ) -> None:
        self._ants = list(ants)
        self._hills = list(hills)
        self._foods = list(foods)
        self._enemies = list(enemies or [])
        self.rows = rows
        self.cols = cols
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
        return []

    def distance(self, a: Loc, b: Loc) -> int:
        dr = abs(a[0] - b[0])
        dr = min(dr, self.rows - dr)
        dc = abs(a[1] - b[1])
        dc = min(dc, self.cols - dc)
        return dr + dc

    def destination(self, loc: Loc, direction: str) -> Loc:
        r, c = loc
        if direction == "n":
            return ((r - 1) % self.rows, c)
        if direction == "s":
            return ((r + 1) % self.rows, c)
        if direction == "e":
            return (r, (c + 1) % self.cols)
        return (r, (c - 1) % self.cols)

    def passable(self, loc: Loc) -> bool:
        assert 0 <= loc[0] < self.rows and 0 <= loc[1] < self.cols
        return True

    def unoccupied(self, loc: Loc) -> bool:
        assert 0 <= loc[0] < self.rows and 0 <= loc[1] < self.cols
        return loc not in self._ants and loc not in self._enemies

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 10000


def run_turn_at(
    bot: Any,
    ants: list[Loc],
    hills: list[Loc],
    foods: list[Loc],
    enemies: list[Loc],
    turn: int,
    rows: int = 20,
    cols: int = 20,
) -> FakeAnts:
    fake = FakeAnts(ants, hills, foods, enemies, rows, cols)
    bot.turn = turn - 1
    bot.do_turn(cast(Any, fake))
    assert bot.turn == turn
    return fake


def fresh_bot(bot: Any, rows: int = 20, cols: int = 20) -> Any:
    bot.do_setup(cast(Any, FakeAnts([], [], [], [], rows, cols)))
    return bot


def load_champion() -> Any:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "..", "champion-Denial.py")
    path = os.path.normpath(path)
    if not os.path.exists(path):
        pytest.skip("champion staging file not present")
    spec = importlib.util.spec_from_file_location("champion_denial", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Denial()


def test_patrol_gate_only_past_400() -> None:
    assert P3.patrol_after(1) is False
    assert P3.patrol_after(400) is False
    assert P3.patrol_after(401) is True
    assert P3.patrol_after(600) is True


def test_patrol_target_picks_nearest_within_range() -> None:
    torus = make_torus(100, 100)
    ant: Loc = (50, 50)
    near: Loc = (50, 70)
    far: Loc = (90, 50)
    assert P3.patrol_target(ant, [far, near], torus) == near
    assert P3.patrol_target(ant, [near, far], torus) == near
    assert P3.patrol_target(ant, [], torus) is None


def test_patrol_target_range_boundary() -> None:
    torus = make_torus(100, 100)
    ant: Loc = (50, 50)
    # Exactly 30 steps away counts as within range; 31 does not.
    assert P3.patrol_target(ant, [(50, 80)], torus) == (50, 80)
    assert P3.patrol_target(ant, [(50, 81)], torus) is None
    assert P3.PATROL_RANGE == 30


def test_pre400_orders_match_champion() -> None:
    # Byte-identical gating: same boards, turns 1 and 400, the new
    # bot issues exactly the champion's orders.
    boards = [
        ([(10, 10)], [(0, 0)], [], []),
        ([(10, 10)], [(10, 15)], [(0, 0)], []),
        ([(10, 10), (0, 0)], [(0, 0), (19, 19)], [(5, 5)], [(9, 11)]),
    ]
    for ants, hills, foods, enemies in boards:
        for turn in (1, 400):
            mine = fresh_bot(P3.Patrol3())
            champ = load_champion()
            champ.do_setup(cast(Any, FakeAnts([], [], [], [])))
            got = run_turn_at(mine, ants, hills, foods, enemies, turn)
            want_fake = FakeAnts(ants, hills, foods, enemies)
            champ.do_turn(cast(Any, want_fake))
            assert got.orders == want_fake.orders


def test_post400_near_hill_is_patrolled() -> None:
    # Hill 20 steps away: the lurker makes every safe step fail, so
    # pre-400 the ant sits (no orders); post-400 it steps toward
    # the hill instead.
    ant: Loc = (10, 10)
    hill: Loc = (0, 0)
    lurker: Loc = (9, 11)
    assert make_torus(20, 20)(ant, hill) == 20
    pre = run_turn_at(fresh_bot(P3.Patrol3()), [ant], [hill], [], [lurker], 400)
    assert pre.orders == []
    post = run_turn_at(fresh_bot(P3.Patrol3()), [ant], [hill], [], [lurker], 401)
    assert len(post.orders) == 1
    origin, direction = post.orders[0]
    assert origin == ant
    moved = post.destination(origin, direction)
    assert make_torus(20, 20)(moved, hill) < 20


def test_post400_far_hill_is_ignored() -> None:
    # Hill 40 steps away on a 100x100 board: post-400 the ant
    # explores normally, exactly as it did pre-400.
    ant: Loc = (50, 50)
    hill: Loc = (90, 50)
    assert make_torus(100, 100)(ant, hill) == 40
    pre = run_turn_at(
        fresh_bot(P3.Patrol3(), 100, 100), [ant], [hill], [], [], 400, 100, 100
    )
    post = run_turn_at(
        fresh_bot(P3.Patrol3(), 100, 100), [ant], [hill], [], [], 401, 100, 100
    )
    assert pre.orders != []
    assert post.orders == pre.orders


def test_range_check_costs_under_1ms() -> None:
    # Nearest-within-range over a crowded board (120 ants, 60
    # hills) must average far under 1ms per ant.
    torus = make_torus(100, 100)
    ants = [(r % 100, (r * 7) % 100) for r in range(120)]
    hills = [((h * 13) % 100, (h * 29) % 100) for h in range(60)]
    n = 500
    start = time.perf_counter()
    for _ in range(n):
        for ant in ants:
            P3.patrol_target(ant, hills, torus)
    per_ant = (time.perf_counter() - start) / (n * len(ants))
    assert per_ant < 0.001


def test_crowded_board_turn_stays_fast() -> None:
    # 120 ants plus near and far hills post-400: the full turn
    # still finishes well under the 1000ms turn budget.
    bot = fresh_bot(P3.Patrol3(), 100, 100)
    ants = [(r % 100, (r * 7) % 100) for r in range(120)]
    hills = [(90, 50), (10, 10)]
    bot.turn = 400
    start = time.perf_counter()
    run_turn_at(bot, ants, hills, [], [], 401, 100, 100)
    assert time.perf_counter() - start < 1.0
