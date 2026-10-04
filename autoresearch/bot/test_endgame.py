#!/usr/bin/env python
"""Endgame closing tests. No engine games.

One change over champion Denial: past turn ENDGAME_TURN (600 of
1000), ants that would otherwise explore instead sit on held hills,
and sitters challenge the nearest uncontrolled hill only with strict
local superiority. Pre-600 behavior is byte-identical to champion.
The oracle below inlines the champion order (food before hills) for
the open-board, enemy-free cases tested here, so equality means the
new code matches champion where the idea does not apply.
"""

import os
import sys
import time
from collections import deque
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Endgame  # noqa: E402

Loc = tuple[int, int]

AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
HOME: Loc = (10, 10)
HILL_WEST: Loc = (10, 4)
HELD: Loc = (10, 10)


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
        my_hills: list[Loc] | None = None,
        enemy_hills: list[Loc] | None = None,
    ) -> None:
        self.rows = rows
        self.cols = cols
        self._land = land
        self._mine = mine
        self._enemies = enemies
        self._foods = foods
        self._my_hills = list(my_hills) if my_hills else []
        self._enemy_hills = list(enemy_hills) if enemy_hills else []
        self.attackradius2 = 5
        self.orders: list[tuple[Loc, str]] = []

    def food(self) -> list[Loc]:
        return list(self._foods)

    def my_ants(self) -> list[Loc]:
        return list(self._mine)

    def enemy_ants(self) -> list[tuple[Loc, int]]:
        return [(e, 1) for e in self._enemies]

    def enemy_hills(self) -> list[tuple[Loc, int]]:
        return [(h, 1) for h in self._enemy_hills]

    def my_hills(self) -> list[Loc]:
        return list(self._my_hills)

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


def _run(
    bot_cls: Any,
    mine: list[Loc],
    foods: list[Loc],
    hills: list[Loc],
    turn: int = 1,
    my_hills: list[Loc] | None = None,
    enemies: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(
        20,
        20,
        _open_board(),
        mine,
        enemies if enemies else [],
        foods,
        my_hills=my_hills if my_hills else [],
        enemy_hills=hills,
    )
    bot = bot_cls()
    bot.visits = {}
    bot.remembered_hills = set(hills)
    bot.prev_enemies = []
    bot.turn = turn - 1
    bot.do_turn(fake)
    return list(fake.orders)


# (a) Pre-600 orders match the champion exactly. --------------------


def test_pre600_food_before_hill_single():
    mine = [HOME]
    foods = [(10, 16)]
    assert (
        _run(Endgame.Endgame, mine, foods, [HILL_WEST], turn=1)
        == _run(ChampionOracle, mine, foods, [HILL_WEST])
        == [(HOME, "e")]
    )


def test_pre600_multi_ant_food_only_matches_champion():
    mine = [(10, 10), (10, 12), (12, 10)]
    foods = [(10, 16), (16, 16), (4, 4)]
    assert _run(Endgame.Endgame, mine, foods, [], turn=599) == _run(
        ChampionOracle, mine, foods, []
    )


def test_pre600_hill_only_matches_champion():
    mine = [HOME]
    assert (
        _run(Endgame.Endgame, mine, [], [HILL_WEST], turn=250)
        == _run(ChampionOracle, mine, [], [HILL_WEST])
        == [(HOME, "w")]
    )


def test_pre600_pure_exploration_matches_champion():
    # No food, no hills: least-visited exploration, tie goes north.
    mine = [HOME]
    assert (
        _run(Endgame.Endgame, mine, [], [], turn=42)
        == _run(ChampionOracle, mine, [], [])
        == [(HOME, "n")]
    )


# (b) Post-600 explorers become hill-sitters. -----------------------


def test_post600_explorer_walks_to_held_hill():
    # No food, no uncontrolled hills: the ant sits on the held hill
    # instead of exploring north like the champion.
    mine = [(10, 11)]
    orders = _run(Endgame.Endgame, mine, [], [], turn=600, my_hills=[HELD])
    assert orders == [((10, 11), "w")]
    assert _run(ChampionOracle, mine, [], []) == [((10, 11), "n")]


def test_post600_sitter_holds_despite_walkoff():
    # Already on the held hill: no order at all. The champion would
    # explore away and walk off; the endgame ant sits.
    mine = [HELD]
    assert _run(Endgame.Endgame, mine, [], [], turn=750, my_hills=[HELD]) == []


def test_post600_boundary_turn_599_still_champion():
    mine = [(10, 11)]
    assert _run(Endgame.Endgame, mine, [], [], turn=599, my_hills=[HELD]) == [
        ((10, 11), "n")
    ]


# (c) Challenges issue only with strict superiority. ----------------


def _siege_mine() -> list[Loc]:
    # The sitter acts first and anchors its own hill (a no-op guard).
    # The far hill (10, 4) is the army-wide muster, and the sitter's
    # westward march/reinforce steps both land on (10, 9), which
    # reads occupied, so the sitter falls through to the endgame
    # branch while the (10, 14) challenge hill stays open east.
    return [(10, 10), (10, 2), (10, 3), (10, 9)]


def test_post600_challenge_with_superiority():
    # Two friends near (10, 14) vs one enemy: 2 > 1, so the sitter
    # challenges east through the endgame branch (its march steps
    # are blocked). A plain march would head west; east pins the
    # challenge.
    orders = _run(
        Endgame.Endgame,
        _siege_mine(),
        [],
        [(10, 4), (10, 14)],
        turn=800,
        my_hills=[HELD],
        enemies=[(14, 14)],
    )
    assert dict(orders)[(10, 10)] == "e"


def test_post600_no_challenge_when_equal():
    # Four friends near (10, 14) vs four enemies is not strict
    # superiority, so the sitter sits. (Distances wrap on the torus,
    # so the whole army counts as near.)
    orders = _run(
        Endgame.Endgame,
        _siege_mine(),
        [],
        [(10, 4), (10, 14)],
        turn=800,
        my_hills=[HELD],
        enemies=[(14, 14), (10, 18), (12, 16), (8, 12)],
    )
    assert (10, 10) not in dict(orders)


def test_post600_no_challenge_when_inferior():
    # Four friends vs five enemies: the sitter sits.
    orders = _run(
        Endgame.Endgame,
        _siege_mine(),
        [],
        [(10, 4), (10, 14)],
        turn=800,
        my_hills=[HELD],
        enemies=[(14, 14), (10, 18), (12, 16), (8, 12), (6, 14)],
    )
    assert (10, 10) not in dict(orders)


def test_post600_nonsitter_sits_first_despite_superiority():
    # The decision rule sends non-sitters to the nearest held hill
    # even when friendly forces at the uncontrolled hill are
    # superior; only sitters challenge.
    def dist(a: Loc, b: Loc) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    superior = {(10, 14): (3, 1)}
    assert Endgame.endgame_goal((10, 18), [HELD], [(10, 14)], superior, dist) == (HELD)
    assert Endgame.endgame_goal(HELD, [HELD], [(10, 14)], superior, dist) == (
        10,
        14,
    )
    tied = {(10, 14): (2, 2)}
    assert Endgame.endgame_goal(HELD, [HELD], [(10, 14)], tied, dist) is None


# (d) The switch costs <2ms on a crowded board. ---------------------


def test_endgame_switch_costs_under_2ms_crowded():
    rows, cols = 30, 30
    ants_list = [(r, c) for r in range(0, 30, 2) for c in range(0, 30, 2)][:200]
    enemies = [((r + 7) % rows, (c + 11) % cols) for r, c in ants_list[:60]]
    my_hills = [(0, 0), (15, 15), (29, 29)]
    hills = [(5, 5), (20, 25)]

    def dist(a: Loc, b: Loc) -> int:
        return min(abs(a[0] - b[0]), rows - abs(a[0] - b[0])) + min(
            abs(a[1] - b[1]), cols - abs(a[1] - b[1])
        )

    start = time.perf_counter()
    counts = Endgame.endgame_counts(hills, ants_list, enemies, dist)
    for ant in ants_list:
        Endgame.endgame_goal(ant, my_hills, hills, counts, dist)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.002
