#!/usr/bin/env python
"""Flowfield pathing tests: hand-built layouts, no engine games.

Repair note: the Flowfield entry was removed, so this suite no longer
imports it (nor the Flood oracle, which never landed on the branch).
The shared-field algorithm survives here as an inline snapshot with
the legacy per-ant lookup inlined beside it as the oracle: the maze
tests still prove field steps equal legacy steps. Bot-movement tests
run against Denial, which keeps Flood's movement everywhere denial is
inactive, pinning that parity. The once-per-turn cache test is dropped:
its subject (the shared field cache) left with the removed entry.
"""

import os
import sys
from collections import deque
from collections.abc import Callable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ants import Ants  # noqa: E402
from Denial import Denial  # noqa: E402

Loc = tuple[int, int]
DIRS = ("n", "e", "s", "w")
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
OPPOSITE = {"n": "s", "s": "n", "e": "w", "w": "e"}
Field = tuple[dict[Loc, int], dict[Loc, Loc], dict[Loc, str]]


def legacy_first_step(
    start: Loc,
    goal: Loc,
    destination: Callable[[Loc, str], Loc],
    passable: Callable[[Loc], bool],
    budget: int = 250,
) -> str | None:
    # Inlined oracle (the champion's per-ant BFS): shortest passable
    # path around water; return its first step.
    if start == goal:
        return None
    parent: dict[Loc, tuple[Loc, str]] = {}
    parent[start] = (start, "")
    queue: deque[Loc] = deque([start])
    expanded = 0
    while queue and expanded < budget:
        cur = queue.popleft()
        expanded += 1
        for d in DIRS:
            nxt = destination(cur, d)
            if nxt in parent or not passable(nxt):
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


def build_distance_field(
    destination: Callable[[Loc, str], Loc],
    passable: Callable[[Loc], bool],
    sources: list[Loc],
    budget: int,
) -> Field:
    # Snapshot of the removed entry's subject: one multi-source BFS
    # from all current targets. Every cell learns its nearest target
    # and the first step toward it.
    dist: dict[Loc, int] = {}
    origin: dict[Loc, Loc] = {}
    step: dict[Loc, str] = {}
    queue: deque[Loc] = deque()
    for src in sources:
        if src not in dist:
            dist[src] = 0
            origin[src] = src
            queue.append(src)
    expanded = 0
    while queue and expanded < budget:
        cur = queue.popleft()
        expanded += 1
        for d in DIRS:
            nxt = destination(cur, d)
            if nxt in dist or not passable(nxt):
                continue
            dist[nxt] = dist[cur] + 1
            origin[nxt] = origin[cur]
            step[nxt] = OPPOSITE[d]
            queue.append(nxt)
    return dist, origin, step


def field_first_step(field: Field, start: Loc, goal: Loc) -> str | None:
    # Snapshot of the removed entry's subject: first step toward the
    # goal through the shared field.
    if start == goal:
        return None
    _, origin, step = field
    if origin.get(start) != goal:
        return None
    return step.get(start)


class FakeAnts(Ants):
    """Hand-built board stub: open land plus a chosen water set."""

    def __init__(
        self,
        rows: int,
        cols: int,
        my_ants: list[tuple[int, int]],
        enemies: list[tuple[int, int]],
        enemy_hills: list[tuple[int, int]],
        water: set[tuple[int, int]],
        foods: list[tuple[int, int]] | None = None,
        my_hills: list[tuple[int, int]] | None = None,
    ) -> None:
        super().__init__()
        self.rows = rows
        self.cols = cols
        self.attackradius2 = 5
        self._my = list(my_ants)
        self._enemies = list(enemies)
        self._hills = list(enemy_hills)
        self._water = set(water)
        self._foods = list(foods or [])
        self._my_hills = list(my_hills or [])
        self.orders: list[tuple[tuple[int, int], str]] = []

    def my_ants(self) -> list[tuple[int, int]]:
        return list(self._my)

    def enemy_ants(self) -> list[tuple[tuple[int, int], int]]:
        return [(loc, 1) for loc in self._enemies]

    def enemy_hills(self) -> list[tuple[tuple[int, int], int]]:
        return [(loc, 1) for loc in self._hills]

    def my_hills(self) -> list[tuple[int, int]]:
        return list(self._my_hills)

    def food(self) -> list[tuple[int, int]]:
        return list(self._foods)

    def visible(self, loc: tuple[int, int]) -> bool:
        return True

    def passable(self, loc: tuple[int, int]) -> bool:
        return loc not in self._water

    def unoccupied(self, loc: tuple[int, int]) -> bool:
        return loc not in self._my and loc not in self._enemies

    def destination(self, loc: tuple[int, int], direction: str) -> tuple[int, int]:
        dr, dc = AIM[direction]
        return ((loc[0] + dr) % self.rows, (loc[1] + dc) % self.cols)

    def distance(self, loc1: tuple[int, int], loc2: tuple[int, int]) -> int:
        d_col = min(abs(loc1[1] - loc2[1]), self.cols - abs(loc1[1] - loc2[1]))
        d_row = min(abs(loc1[0] - loc2[0]), self.rows - abs(loc1[0] - loc2[0]))
        return d_row + d_col

    def issue_order(self, order: tuple[tuple[int, int], str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 10000


def land(rows: int, cols: int) -> set[tuple[int, int]]:
    return {(r, c) for r in range(rows) for c in range(cols)}


def maze_layouts() -> list[
    tuple[
        int,
        int,
        set[tuple[int, int]],
        list[tuple[int, int]],
        list[tuple[tuple[int, int], tuple[int, int]]],
    ]
]:
    """(rows, cols, water, sources, [(start, goal)]) with 1-wide corridors.

    One-wide corridors force unique shortest paths, and each start sits
    in its goal's chamber so the shared field's nearest source is the
    assigned goal.
    """
    layouts = []
    # A: T corridor. Vertical col 3, horizontal row 7 cols 3..11.
    rows, cols = 15, 15
    keep = {(r, 3) for r in range(rows)} | {(7, c) for c in range(3, 12)}
    sources = [(0, 3), (7, 11)]
    queries = [((5, 3), (0, 3)), ((2, 3), (0, 3)), ((7, 5), (7, 11)), ((7, 9), (7, 11))]
    layouts.append((rows, cols, land(rows, cols) - keep, sources, queries))
    # B: U corridor. Row 1 cols 1..9, col 9 rows 1..9, row 9 cols 1..9.
    rows, cols = 11, 11
    keep = (
        {(1, c) for c in range(1, 10)}
        | {(r, 9) for r in range(1, 10)}
        | {(9, c) for c in range(1, 10)}
    )
    sources = [(1, 1), (9, 9)]
    queries = [((1, 5), (1, 1)), ((3, 9), (9, 9)), ((9, 5), (9, 9)), ((7, 9), (9, 9))]
    layouts.append((rows, cols, land(rows, cols) - keep, sources, queries))
    # C: plus corridor. Col 6 all rows, row 6 all cols.
    rows, cols = 13, 13
    keep = {(r, 6) for r in range(rows)} | {(6, c) for c in range(cols)}
    sources = [(0, 6), (12, 6), (6, 0), (6, 12)]
    queries = [((3, 6), (0, 6)), ((9, 6), (12, 6)), ((6, 3), (6, 0)), ((6, 9), (6, 12))]
    layouts.append((rows, cols, land(rows, cols) - keep, sources, queries))
    return layouts


def test_field_matches_legacy_on_mazes() -> None:
    """Shared field first steps equal per-ant BFS on 3 maze layouts."""
    for rows, cols, water, sources, queries in maze_layouts():
        ants = FakeAnts(
            rows=rows, cols=cols, my_ants=[], enemies=[], enemy_hills=[], water=water
        )
        field = build_distance_field(
            ants.destination, ants.passable, sources, rows * cols
        )
        assert len(queries) >= 4
        for start, goal in queries:
            old = legacy_first_step(
                start, goal, ants.destination, ants.passable, budget=250
            )
            new = field_first_step(field, start, goal)
            assert old is not None, f"{start} -> {goal} unreachable by legacy BFS"
            assert new is not None, f"{start} -> {goal} missed its field source"
            assert new == old, f"{start} -> {goal}: field {new} != legacy {old}"


def test_field_distances_are_shortest() -> None:
    """Spot check: the plus center sits 6 from every arm source."""
    rows, cols, water, sources, _ = maze_layouts()[2]
    ants = FakeAnts(
        rows=rows, cols=cols, my_ants=[], enemies=[], enemy_hills=[], water=water
    )
    dist, _, _ = build_distance_field(
        ants.destination, ants.passable, sources, rows * cols
    )
    assert dist[(6, 6)] == 6
    assert dist[(0, 6)] == 0
    assert dist[(3, 6)] == 3


def corridor_hold() -> FakeAnts:
    """Lone marcher, open row-10 corridor, hill east, enemy covering step 2.

    Ant (10,10) -> N1 (10,11) is outside both enemies' range but
    N2 (10,12) sits inside both (sq 5 each): step 1 safe (2v1 up
    the corridor is fine), step 2 faces 2v2 without backup.
    """
    return FakeAnts(
        rows=30,
        cols=30,
        my_ants=[(10, 10)],
        enemies=[(8, 13), (12, 13)],
        enemy_hills=[(10, 15)],
        water=set(),
    )


def test_legacy_lookup_walks_into_corridor() -> None:
    """The inlined oracle marches east: the old code walked in here."""
    ants = corridor_hold()
    assert legacy_first_step((10, 10), (10, 15), ants.destination, ants.passable) == "e"


def test_denial_marches_open_corridor() -> None:
    """Two enemies, no denial trigger: Denial marches like Flood did."""
    ants = corridor_hold()
    bot = Denial()
    bot.do_setup(ants)
    bot.do_turn(ants)
    assert ants.orders == [((10, 10), "e")]


def test_denial_marches_when_both_safe() -> None:
    """No enemy: the march goes through like before."""
    ants = FakeAnts(
        rows=30,
        cols=30,
        my_ants=[(10, 10)],
        enemies=[],
        enemy_hills=[(10, 15)],
        water=set(),
    )
    bot = Denial()
    bot.do_setup(ants)
    bot.do_turn(ants)
    assert ants.orders == [((10, 10), "e")]


def test_full_turn_completes_on_150_ants() -> None:
    """150 mustering ants: the turn completes and the army moves."""
    my = [(r, c) for r in range(0, 30, 2) for c in range(0, 30, 2)][:150]
    assert len(my) == 150
    ants = FakeAnts(
        rows=30,
        cols=30,
        my_ants=my,
        enemies=[],
        enemy_hills=[(0, 0), (15, 15)],
        water=set(),
    )
    bot = Denial()
    bot.do_setup(ants)
    bot.do_turn(ants)
    assert len(ants.orders) > 100
