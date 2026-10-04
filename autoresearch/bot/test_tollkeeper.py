#!/usr/bin/env python
"""Tollkeeper danger-routing tests. No engine games.

One change over champion Denial: squares adjacent to 2+ enemies where
the local enemy count exceeds the friendly count are toll squares that
cost +TOLL_COST steps in every BFS (food, muster, reinforce paths all
share first_step). Marches route around kill zones when a comparably
short safe path exists, and walk through when none does.

Grid parity note: on a bipartite grid any two walks between the same
endpoints differ by an even length, so the brief's "1-step-longer safe
path" is geometrically impossible; the tests below use the minimal
possible detour (+2 steps, which the +3 toll flips) and a +4 detour
(which correctly stays on the short path).
"""

import os
import random
import sys
import time
from collections.abc import Callable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Tollkeeper  # noqa: E402

Loc = tuple[int, int]
DestFn = Callable[[Loc, str], Loc]
PassFn = Callable[[Loc], bool]

ROWS = 20
COLS = 20
R2 = 5


def make_destination(rows: int, cols: int) -> DestFn:
    def destination(loc: Loc, direction: str) -> Loc:
        r, c = loc
        if direction == "n":
            return ((r - 1) % rows, c)
        if direction == "s":
            return ((r + 1) % rows, c)
        if direction == "e":
            return (r, (c + 1) % cols)
        return (r, (c - 1) % cols)

    return destination


DEST = make_destination(ROWS, COLS)

S: Loc = (10, 10)
A: Loc = (10, 11)
T: Loc = (10, 12)
B: Loc = (10, 13)
G: Loc = (10, 14)
SHORT = [S, A, T, B, G]
# Minimal (+2) safe detour around T.
LONG2 = [S, (11, 10), (11, 11), (11, 12), (11, 13), B, G]
# Long (+4) safe detour around T: must not flip.
LONG4 = [S, (11, 10), (12, 10), (12, 11), (12, 12), (12, 13), (11, 13), B, G]
# Two enemies orthogonally adjacent to T; only S nearby for friends.
FOES: list[Loc] = [(9, 12), (11, 12)]


def passable_in(corridor: list[Loc]) -> PassFn:
    inside = set(corridor)

    def passable(loc: Loc) -> bool:
        return loc in inside

    return passable


def champ_first_step(
    start: Loc, goal: Loc, destination: DestFn, passable: PassFn, budget: int = 250
) -> str | None:
    # Verbatim champion BFS oracle.
    from collections import deque

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


def tolls_for(corridor: list[Loc], friends: list[Loc]) -> set[Loc]:
    return Tollkeeper.compute_tolls(FOES, friends, ROWS, COLS, R2)


def test_toll_constant() -> None:
    assert Tollkeeper.TOLL_COST == 3


def test_kill_square_is_tolled() -> None:
    tolls = tolls_for(SHORT, [S])
    assert T in tolls


def test_single_enemy_not_tolled() -> None:
    tolls = Tollkeeper.compute_tolls(FOES[:1], [S], ROWS, COLS, R2)
    assert T not in tolls
    assert tolls == set()


def test_superior_friends_not_tolled() -> None:
    friends = [S, (9, 11), (9, 13), (10, 12)]
    tolls = Tollkeeper.compute_tolls(FOES, friends, ROWS, COLS, R2)
    assert T not in tolls


def walk(start: Loc, goal: Loc, step_fn: Callable[[Loc], str | None]) -> list[Loc]:
    path = [start]
    cur = start
    for _ in range(20):
        if cur == goal:
            break
        step = step_fn(cur)
        assert step is not None
        cur = DEST(cur, step)
        path.append(cur)
    assert path[-1] == goal
    return path


def test_routes_around_kill_zone() -> None:
    # Short path is 4 steps through the toll square T; the safe path
    # is 6. The tollkeeper's whole march avoids T (it steps onto A
    # first, then turns south around the kill zone).
    corridor = list(dict.fromkeys(SHORT + LONG2))
    assert len(LONG2) - 1 == (len(SHORT) - 1) + 2
    passable = passable_in(corridor)
    tolls = tolls_for(corridor, [S])
    assert T in tolls
    champ_path = walk(S, G, lambda cur: champ_first_step(cur, G, DEST, passable))
    assert champ_path == [S, A, T, B, G]
    toll_path = walk(
        S, G, lambda cur: Tollkeeper.route_first_step(cur, G, DEST, passable, tolls)
    )
    assert T not in toll_path
    assert len(toll_path) - 1 == 6


def test_walks_through_when_no_alternative() -> None:
    # No safe path at all: must still march (no stranding).
    passable = passable_in(SHORT)
    tolls = tolls_for(SHORT, [S])
    assert T in tolls
    assert Tollkeeper.route_first_step(S, G, DEST, passable, tolls) == "e"


def test_long_detour_stays_on_short_path() -> None:
    # Safe path is +4 (cost 8) vs through at 4 + 3 = 7: stay.
    corridor = list(dict.fromkeys(SHORT + LONG4))
    passable = passable_in(corridor)
    tolls = tolls_for(corridor, [S])
    assert T in tolls
    assert Tollkeeper.route_first_step(S, G, DEST, passable, tolls) == "e"


def test_open_board_matches_champion() -> None:
    # No enemies: no tolls, byte-identical to champion over random
    # start/goal pairs with random water.
    rng = random.Random(22)
    water = {(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(40)}
    outside = water

    def passable(loc: Loc) -> bool:
        return loc not in outside

    assert Tollkeeper.compute_tolls([], [(0, 0)], ROWS, COLS, R2) == set()
    for _ in range(200):
        start = (rng.randrange(ROWS), rng.randrange(COLS))
        goal = (rng.randrange(ROWS), rng.randrange(COLS))
        if start in water or goal in water:
            continue
        assert Tollkeeper.route_first_step(
            start, goal, DEST, passable, set()
        ) == champ_first_step(start, goal, DEST, passable)


def test_distant_tolls_match_champion() -> None:
    # Toll squares far from the route must not change the path.
    corridor = list(dict.fromkeys(SHORT + LONG2))
    passable = passable_in(corridor)
    tolls = tolls_for(corridor, [S])
    assert T in tolls
    far = {t for t in tolls if t != T}
    assert Tollkeeper.route_first_step(S, G, DEST, passable, far) == "e"


def test_marking_costs_under_2ms_crowded() -> None:
    # Crowded 40x40 board, 120 enemies vs 120 ants: marking < 2ms.
    rng = random.Random(7)
    rows, cols = 40, 40
    enemies = [(rng.randrange(rows), rng.randrange(cols)) for _ in range(120)]
    friends = [(rng.randrange(rows), rng.randrange(cols)) for _ in range(120)]
    worst = 0.0
    for _ in range(3):
        start = time.perf_counter()
        Tollkeeper.compute_tolls(enemies, friends, rows, cols, R2)
        worst = max(worst, time.perf_counter() - start)
    assert worst < 0.002
