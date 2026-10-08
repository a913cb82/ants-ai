#!/usr/bin/env python
"""Turnstile5 (far-sight scout) tests.

No engine games.

One change over Turnstile: an ant that reaches the explore branch
scouts far-sight instead of stepping to the least-visited neighbor.
First the shortest passable path to the nearest never-visited
square (budget-capped BFS), so idle ants push fog instead of
re-wandering home ground; claimed frontier targets are skipped
per-turn so the army splits across frontiers. With no unseen
square in range, the ant drifts toward the stalest ground in range
-- but only when it beats standing local -- so corridors get
re-swept for new food instead of jittering on trampled ground.
Scout steps keep the champion safety filter, and anything missing
falls back to base least-visited explore. Food, guard, hills,
rotation, and economy are untouched.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Turnstile5 as TS5  # noqa: E402

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
        home: list[Loc] | None = None,
    ) -> None:
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = 5
        self._mine = list(mine)
        self._enemies = list(enemies)
        self._foods = list(foods or [])
        self._water = set(water or set())
        self._home = list(home or [])
        self._time_ms = 100000
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
        return list(self._home)

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
        return self._time_ms


def _all_seen_bot(
    visits: dict[Loc, int], skip: set[Loc] | None = None
) -> "TS5.Turnstile5":
    bot = TS5.Turnstile5()
    skip = skip or set()
    for r in range(ROWS):
        for c in range(COLS):
            if (r, c) not in skip:
                visits[(r, c)] = 5
    bot.visits = dict(visits)
    return bot


def run_turn_with(
    bot: "TS5.Turnstile5",
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    home: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, water, home)
    bot.sit = {}
    bot.do_turn(fake)
    return fake.orders


def test_scout_seeks_unseen_frontier() -> None:
    # Every square seen except (10,14), five east of the ant. All four
    # neighbors tie at 5 visits, so base least-visited explore would
    # step north; the scout must step east toward the frontier.
    visits: dict[Loc, int] = {}
    bot = _all_seen_bot(visits, skip={(10, 14)})
    orders = run_turn_with(bot, [(10, 10)], [])
    assert dict(orders).get((10, 10)) == "e"


def test_scout_blocked_water_falls_back() -> None:
    # Water walls off every neighbor's onward path, so no unseen
    # square is reachable: the ant drifts to the stalest neighbor
    # (north, visits 1 < 2 < 3 < 4).
    mine = [(5, 5)]
    water = set()
    for r in range(ROWS):
        for c in range(COLS):
            if (r, c) not in mine and (r, c) not in [
                (4, 5),
                (5, 6),
                (6, 5),
                (5, 4),
            ]:
                water.add((r, c))
    bot = TS5.Turnstile5()
    bot.visits = {(4, 5): 1, (5, 6): 2, (6, 5): 3, (5, 4): 4, (5, 5): 9}
    fake = FakeAnts(mine, [], None, water)
    bot.sit = {}
    bot.do_turn(fake)
    assert dict(fake.orders).get((5, 5)) == "n"


def test_scout_ants_split_frontiers() -> None:
    # One unseen square for two ants: the first ant scouts it, the
    # second must not chase the same target and drifts locally
    # (north) instead.
    visits: dict[Loc, int] = {}
    bot = _all_seen_bot(visits, skip={(10, 14)})
    orders = run_turn_with(bot, [(10, 10), (12, 10)], [])
    by = dict(orders)
    assert by.get((10, 10)) == "e"
    assert by.get((12, 10)) == "n"


def test_scout_step_keeps_safety_filter() -> None:
    # The frontier lies east but an enemy sits on the path: the scout
    # step (and its north/south alternatives) is suicide, so the ant
    # falls back west instead of walking into the attack radius.
    visits: dict[Loc, int] = {}
    bot = _all_seen_bot(visits, skip={(10, 14)})
    orders = run_turn_with(bot, [(10, 10)], [(10, 12)])
    assert dict(orders).get((10, 10)) == "w"


def test_rotation_still_works() -> None:
    # Base behavior locked: a 50-turn sitter rotates off toward its
    # partner, and a threatened sitter stays put.
    mine = [(5, 5), (10, 10)]
    visits: dict[Loc, int] = {}
    bot = _all_seen_bot(visits)
    bot.sit = {(5, 5): 50}
    fake = FakeAnts(mine, [])
    bot.do_turn(fake)
    assert (5, 5) in dict(fake.orders)
    probe = FakeAnts(mine, [])
    moved = probe.destination((5, 5), dict(fake.orders)[(5, 5)])
    assert probe.distance(moved, (10, 10)) < probe.distance((5, 5), (10, 10))
    assert TS5.turnstile_swaps({(5, 5): 99}, mine, [(5, 6)], 5, ROWS, COLS) == {}


def test_blinded_scout_falls_back_to_greedy() -> None:
    # With the scout blinded, explore is pure least-visited greedy:
    # all neighbors tie at 5, so the ant steps north.
    visits: dict[Loc, int] = {}
    bot = _all_seen_bot(visits)
    orig = TS5.farsight_first_step
    TS5.farsight_first_step = lambda *a, **k: (None, None)  # noqa: E731
    try:
        orders = run_turn_with(bot, [(10, 10)], [])
    finally:
        TS5.farsight_first_step = orig
    assert dict(orders).get((10, 10)) == "n"


def test_scout_paths_around_water() -> None:
    # A wall blocks the straight line east; the gap sits one south.
    # Base least-visited explore would step north (all tie); the
    # scout routes through the gap, first step east.
    visits: dict[Loc, int] = {}
    bot = _all_seen_bot(visits, skip={(5, 8)})
    water = {(r, 7) for r in (3, 4, 5, 7)}
    orders = run_turn_with(bot, [(5, 5)], [], None, water)
    assert dict(orders).get((5, 5)) == "e"


def test_hill_duty_beats_scout() -> None:
    # A nearby remembered hill plus an unseen square elsewhere: the
    # ant marches the hill (south), scout untouched.
    visits: dict[Loc, int] = {}
    bot = _all_seen_bot(visits, skip={(10, 14)})
    bot.remembered_hills = {(12, 10)}
    orders = run_turn_with(bot, [(10, 10)], [])
    assert dict(orders).get((10, 10)) == "s"


def test_scout_drifts_to_stale_pocket() -> None:
    # No unseen square anywhere, but a stale pocket (visits 2) sits
    # three east past trampled ground (visits 10): the ant heads
    # east toward it instead of diffusing north like base would.
    visits: dict[Loc, int] = {}
    bot = _all_seen_bot(visits)
    bot.visits[(10, 10)] = 10
    bot.visits[(10, 13)] = 2
    orders = run_turn_with(bot, [(10, 10)], [])
    assert dict(orders).get((10, 10)) == "e"


def test_scout_holds_on_fresh_ground() -> None:
    # No unseen square, and the ant stands on the freshest ground
    # around: no drift target beats staying local, so the ant takes
    # least-visited greedy (north on the tie).
    visits: dict[Loc, int] = {}
    bot = _all_seen_bot(visits)
    bot.visits[(10, 10)] = 1
    bot.visits[(10, 13)] = 2
    orders = run_turn_with(bot, [(10, 10)], [])
    assert dict(orders).get((10, 10)) == "n"


def test_food_claim_beats_scout() -> None:
    # Food next door plus an unseen square elsewhere: the ant takes
    # the food (west), scout untouched.
    visits: dict[Loc, int] = {}
    bot = _all_seen_bot(visits, skip={(10, 14)})
    orders = run_turn_with(bot, [(10, 10)], [], [(10, 9)])
    assert dict(orders).get((10, 10)) == "w"


def test_scout_wraps_the_torus() -> None:
    # The only unseen square sits across the north seam, one step
    # away by wrap: the scout steps north, not the long way around.
    visits: dict[Loc, int] = {}
    bot = _all_seen_bot(visits, skip={(19, 5)})
    orders = run_turn_with(bot, [(0, 5)], [])
    assert dict(orders).get((0, 5)) == "n"


def test_guard_beats_scout() -> None:
    # A threatened home hill plus an unseen square elsewhere: the
    # ant guards the hill (west), scout untouched.
    visits: dict[Loc, int] = {}
    bot = _all_seen_bot(visits, skip={(10, 14)})
    orders = run_turn_with(bot, [(5, 7)], [(5, 2)], None, None, [(5, 5)])
    assert dict(orders).get((5, 7)) == "w"


def test_scout_covers_maze_faster() -> None:
    # Comb maze, one ant, 60 turns: the scout's gap routing covers
    # strictly more ground than blinded least-visited greedy.
    water = set()
    for c in (4, 8, 12, 16):
        gap = 1 if (c // 4) % 2 == 0 else 18
        for r in range(ROWS):
            if r != gap:
                water.add((r, c))

    def run(blinded: bool) -> int:
        bot = TS5.Turnstile5()
        ant = [(10, 2)]
        orig = TS5.farsight_first_step
        if blinded:
            TS5.farsight_first_step = lambda *a, **k: (None, None)  # noqa: E731
        try:
            for _ in range(60):
                fake = FakeAnts(ant, [], [], set(water))
                bot.sit = {}
                bot.do_turn(fake)
                if not fake.orders:
                    break
                ant = [fake.destination(ant[0], fake.orders[0][1])]
        finally:
            TS5.farsight_first_step = orig
        return len(bot.visits)

    assert run(False) > run(True)


def test_scout_skipped_when_time_runs_low() -> None:
    # With almost no time left the scout is skipped, but greedy
    # explore still moves (north on the tie), never stranding ants.
    visits: dict[Loc, int] = {}
    bot = _all_seen_bot(visits, skip={(10, 14)})
    bot.sit = {}
    fake = FakeAnts([(10, 10)], [])
    fake._time_ms = 0
    bot.do_turn(fake)
    assert dict(fake.orders).get((10, 10)) == "n"


def test_scout_army_covers_maze_faster() -> None:
    # Comb maze, four ants, 80 turns: claim-splitting spreads the
    # army, so the scouts cover strictly more ground than blinded
    # least-visited greedy.
    water = set()
    for c in (4, 8, 12, 16):
        gap = 1 if (c // 4) % 2 == 0 else 18
        for r in range(ROWS):
            if r != gap:
                water.add((r, c))
    start = [(10, 0), (10, 1), (10, 2), (11, 0)]

    def run(blinded: bool) -> int:
        bot = TS5.Turnstile5()
        ants = list(start)
        orig = TS5.farsight_first_step
        if blinded:
            TS5.farsight_first_step = lambda *a, **k: (None, None)  # noqa: E731
        try:
            for _ in range(80):
                fake = FakeAnts(ants, [], [], set(water))
                bot.sit = {}
                bot.do_turn(fake)
                step = dict(fake.orders)
                ants = [fake.destination(m, step[m]) if m in step else m for m in ants]
        finally:
            TS5.farsight_first_step = orig
        return len(bot.visits)

    assert run(False) > run(True)


def _torus(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


def test_denial_economy_intact() -> None:
    # Three enemies contest a three-food cluster: exactly two ants
    # take two distinct cluster foods; the rest stays unclaimed.
    mine = [(8, 8), (8, 9), (12, 12), (13, 13)]
    foods = [(10, 10), (10, 11), (11, 10)]
    foes = [(10, 12), (11, 12), (12, 10)]
    target = TS5.assign_food_targets(mine, foods, foes, _torus, ROWS, COLS)
    assert len(target) == 2
    assert set(target.values()) <= set(foods)
    assert len(set(target.values())) == 2


def test_greedy_food_intact() -> None:
    # No enemies: greedy one-ant-per-food over the same cluster.
    mine = [(8, 8), (8, 9), (12, 12), (13, 13)]
    foods = [(10, 10), (10, 11), (11, 10)]
    target = TS5.assign_food_targets(mine, foods, [], _torus, ROWS, COLS)
    assert len(target) == 3
    assert set(target.values()) == set(foods)


def test_full_turn_under_half_second() -> None:
    import random

    rng = random.Random(11)
    locs = [(r, c) for r in range(ROWS) for c in range(COLS)]
    mine = rng.sample(locs, 150)
    foes = rng.sample(locs, 10)
    foods = rng.sample(locs, 20)
    bot = TS5.Turnstile5()
    bot.visits = {m: rng.randint(0, 9) for m in rng.sample(locs, 200)}
    fake = FakeAnts(mine, foes, foods)
    bot.sit = {}
    start = time.perf_counter()
    bot.do_turn(fake)
    assert time.perf_counter() - start < 0.5
