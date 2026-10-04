#!/usr/bin/env python
"""Hillfirst2 (hills before food) tests. No engine games.

One change over champion Denial: an ant holding a food claim AND a
hill march takes the hill move first, except ants within
HILL_FIRST_STEPS of their claimed food finish the pickup first. The
oracle below inlines the champion order (food before hills) for the
open-board, enemy-free cases tested here, so equality means the new
code is byte-identical to champion where the idea does not apply.
"""

import os
import sys
import time
from collections import deque
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Hillfirst2  # noqa: E402

Loc = tuple[int, int]

AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
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
        foods: list[Loc],
    ) -> None:
        self.rows = rows
        self.cols = cols
        self._land = land
        self._mine = mine
        self._enemies = enemies
        self._foods = foods
        self.attackradius2 = 5
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


def _greedy(ants_list: list[Loc], foods: list[Loc], distance: Any) -> dict[int, Loc]:
    # Champion greedy with no contested clusters (no enemies here).
    pairs = sorted(
        (distance(a, f), ai, fi)
        for ai, a in enumerate(ants_list)
        for fi, f in enumerate(foods)
    )
    target: dict[int, Loc] = {}
    claimed: set[int] = set()
    for _, ai, fi in pairs:
        if ai not in target and fi not in claimed:
            target[ai] = foods[fi]
            claimed.add(fi)
    return target


def _first_step(ants: Any, start: Loc, goal: Loc, budget: int = 250) -> str | None:
    if start == goal:
        return None
    parent: dict[Loc, tuple[Loc, str]] = {}
    parent[start] = (start, "")
    queue: deque[Loc] = deque([start])
    expanded = 0
    while queue and expanded < budget:
        cur = queue.popleft()
        expanded += 1
        for d in ("n", "e", "s", "w"):
            nxt = ants.destination(cur, d)
            if nxt in parent or not ants.passable(nxt):
                continue
            parent[nxt] = (cur, d)
            if nxt == goal:
                queue.clear()
                break
            queue.append(nxt)
    if goal not in parent:
        return None
    node = goal
    while parent[node][0] != start:
        node = parent[node][0]
    return parent[node][1]


class ChampionOracle:
    """Inlined champion Denial order (food before hills).

    Restricted to the cases tested here: open board, no enemies (so
    the safety filter is vacuous and there is no guard), same BFS and
    same least-visited exploration as champion.
    """

    def __init__(self) -> None:
        self.visits: dict[Loc, int] = {}
        self.remembered_hills: set[Loc] = set()

    def do_turn(self, ants: Any) -> None:
        ants_list = list(ants.my_ants())
        target = _greedy(ants_list, ants.food(), ants.distance)
        hills = sorted(self.remembered_hills)
        destinations: set[Loc] = set()

        def commit(ant_loc: Loc, step: str | None) -> bool:
            if step is None:
                return False
            new_loc = ants.destination(ant_loc, step)
            if (
                new_loc not in destinations
                and ants.passable(new_loc)
                and ants.unoccupied(new_loc)
            ):
                ants.issue_order((ant_loc, step))
                destinations.add(new_loc)
                return True
            return False

        for ai, ant_loc in enumerate(ants_list):
            self.visits[ant_loc] = self.visits.get(ant_loc, 0) + 1
            moved = False
            best = target.get(ai)
            if best is not None:
                moved = commit(ant_loc, _first_step(ants, ant_loc, best))
            if not moved and hills:
                muster = min(
                    hills, key=lambda h: sum(ants.distance(a, h) for a in ants_list)
                )
                moved = commit(ant_loc, _first_step(ants, ant_loc, muster))
            if not moved and hills:
                ordered = sorted(hills, key=lambda h: ants.distance(ant_loc, h))
                near = ordered[1] if len(ordered) > 1 else ordered[0]
                moved = commit(ant_loc, _first_step(ants, ant_loc, near))
            if not moved:
                dirs = sorted(
                    ("n", "e", "s", "w"),
                    key=lambda d: self.visits.get(ants.destination(ant_loc, d), 0),
                )
                for direction in dirs:
                    if commit(ant_loc, direction):
                        moved = True
                        break


def _open_board(rows: int = 20, cols: int = 20) -> set[Loc]:
    return {(r, c) for r in range(rows) for c in range(cols)}


def _run(bot_cls: Any, mine: list[Loc], foods: list[Loc], hills: list[Loc]) -> Any:
    fake = FakeAnts(20, 20, _open_board(), mine, [], foods)
    bot = bot_cls()
    bot.visits = {}
    bot.remembered_hills = set(hills)
    bot.do_turn(fake)
    return fake.orders


def test_both_options_takes_hill():
    # Food 6 steps east, hill 6 steps west: champion goes east for
    # food, Hillfirst2 marches west. The oracle pins the champion side.
    mine = [HOME]
    foods = [(10, 16)]
    hills = [(10, 4)]
    assert _run(Hillfirst2.Hillfirst2, mine, foods, hills) == [(HOME, "w")]
    assert _run(ChampionOracle, mine, foods, hills) == [(HOME, "e")]


def test_close_to_food_finishes_pickup():
    # Same hill, but the food is 3 steps away: the ant finishes the
    # pickup first instead of marching.
    mine = [HOME]
    foods = [(10, 13)]
    hills = [(10, 4)]
    assert _run(Hillfirst2.Hillfirst2, mine, foods, hills) == [(HOME, "e")]
    assert _run(ChampionOracle, mine, foods, hills) == [(HOME, "e")]


def test_food_only_matches_champion():
    # No hills: food-only ants move exactly like champion.
    mine = [HOME]
    foods = [(10, 16)]
    assert (
        _run(Hillfirst2.Hillfirst2, mine, foods, [])
        == _run(ChampionOracle, mine, foods, [])
        == [(HOME, "e")]
    )


def test_hill_only_matches_champion():
    # No food: hill-only ants march exactly like champion.
    mine = [HOME]
    assert (
        _run(Hillfirst2.Hillfirst2, mine, [], [(10, 4)])
        == _run(ChampionOracle, mine, [], [(10, 4)])
        == [(HOME, "w")]
    )


def test_reorder_costs_under_1ms_on_crowded_board():
    # The reorder is one distance check per ant; 200 ants must cost
    # less than 1ms.
    rows, cols = 30, 30
    ants_list = [(r, c) for r in range(0, 30, 2) for c in range(0, 30, 2)][:200]
    claims = [((r + 5) % rows, (c + 7) % cols) for r, c in ants_list]
    hills = [(0, 0), (15, 15), (29, 29)]

    def dist(a: Loc, b: Loc) -> int:
        return min(abs(a[0] - b[0]), rows - abs(a[0] - b[0])) + min(
            abs(a[1] - b[1]), cols - abs(a[1] - b[1])
        )

    start = time.perf_counter()
    for ant, claim in zip(ants_list, claims, strict=True):
        Hillfirst2.hill_first(ant, claim, hills, dist)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.001
