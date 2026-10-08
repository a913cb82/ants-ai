#!/usr/bin/env python
"""Squire (sally defense) tests. No engine games.

One change over Understudy: when a home hill is threatened, nobody
sits on it. Sitting blocks our own spawns (spawn needs the hill
unoccupied) while buying nothing in combat: the engine resolves
attacks before razes, so an empty hill with a guard in attack range
cannot fall. The first guard therefore anchors on an adjacent
square in cover range, and every extra guard converges on the
raider itself for a clean 2v1+ instead of screening 1v1 while a
sitter idles. Everything else (denial, rotation, muster, explore)
matches Understudy exactly.
"""

import os
import sys
import time
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Squire as SQ  # noqa: E402
import Understudy as US  # noqa: E402

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
        foods: list[Loc],
        enemies: list[Loc],
        homes: list[Loc],
        hills: list[Loc],
    ) -> None:
        self._ants = list(ants)
        self._foods = list(foods)
        self._enemies = list(enemies)
        self._homes = list(homes)
        self._hills = list(hills)
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = 5
        self.turntime = 1000
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


def run_turn(
    bot: Any,
    ants: list[Loc],
    enemies: list[Loc],
    homes: list[Loc],
    hills: list[Loc] | None = None,
    foods: list[Loc] | None = None,
) -> FakeAnts:
    fake = FakeAnts(ants, foods or [], enemies, homes, hills or [])
    bot.do_turn(cast(Any, fake))
    return fake


def destinations_of(fake: FakeAnts) -> set[Loc]:
    return {fake.destination(o, d) for o, d in fake.orders}


def moved_to(fake: FakeAnts, origin: Loc) -> Loc:
    for o, d in fake.orders:
        if o == origin:
            return fake.destination(o, d)
    raise AssertionError(f"ant {origin} issued no order")


HOME: Loc = (10, 10)
H1: Loc = (10, 5)


def fresh_bot() -> Any:
    bot = SQ.Squire()
    bot.do_setup(cast(Any, FakeAnts([], [], [], [], [])))
    return bot


def test_anchor_holds_adjacent_cover() -> None:
    # Lone guard adjacent to a threatened home hill holds its
    # cover square: no order, and above all no step onto the hill.
    bot = fresh_bot()
    fake = run_turn(bot, [(10, 11)], [(10, 14)], [HOME])
    assert fake.orders == []
    assert HOME not in destinations_of(fake)


def test_guard_vacates_threatened_hill() -> None:
    # A guard caught standing on a threatened hill (fresh spawn)
    # steps off toward the raider instead of sitting out spawns.
    bot = fresh_bot()
    fake = run_turn(bot, [(10, 10)], [(10, 14)], [HOME])
    assert fake.orders == [((10, 10), "e")]
    assert HOME not in destinations_of(fake)


def test_extras_converge_on_raider() -> None:
    # Two guards, one raider: the anchor holds cover while the
    # second guard marches on the raider itself (2v1 setup),
    # not onto the hill and not 1v1 screening while a sitter idles.
    bot = fresh_bot()
    fake = run_turn(bot, [(10, 11), (10, 8)], [(10, 14)], [HOME])
    assert (10, 11) not in [o for o, _ in fake.orders]
    assert HOME not in destinations_of(fake)
    # The extra guard steps toward the raider along an optimal
    # detour (east hugs the hill it must not cross, north starts
    # the way around); either way it closes in off the hill.
    assert moved_to(fake, (10, 8)) in ((10, 9), (9, 8))


def test_distant_guard_closes_then_holds() -> None:
    # A far guard steps into cover range, then holds adjacent on
    # the next turn instead of walking onto the hill.
    bot = fresh_bot()
    turn1 = run_turn(bot, [(10, 5)], [(10, 14)], [HOME])
    assert turn1.orders == [((10, 5), "e")]
    turn2 = run_turn(bot, [(10, 6)], [(10, 14)], [HOME])
    assert turn2.orders == [((10, 6), "e")]
    turn3 = run_turn(bot, [(10, 9)], [(10, 14)], [HOME])
    assert turn3.orders == []
    assert HOME not in destinations_of(turn3)


def test_defense_never_ends_on_home_hill() -> None:
    # Three guards around a threatened hill plus food elsewhere:
    # every issued destination stays off the home hill, so the
    # spawn square stays open through the whole fight.
    bot = fresh_bot()
    fake = run_turn(
        bot,
        [(10, 11), (9, 10), (11, 12)],
        [(10, 14), (12, 10)],
        [HOME],
        foods=[(0, 0)],
    )
    assert HOME not in destinations_of(fake)
    assert len(fake.orders) >= 1


def test_failed_challenge_still_rotates() -> None:
    # Regression: the Understudy rotation survives the new guard
    # branch. Nearest ant A challenges H1; H1 still held next
    # turn, so B challenges instead.
    A: Loc = (10, 10)
    B: Loc = (0, 0)
    bot = fresh_bot()
    turn1 = run_turn(bot, [A, B], [], [(0, 10)], [H1])
    assert turn1.orders[0] == (A, "w")
    ants2 = [moved_to(turn1, A), moved_to(turn1, B)]
    assert ants2[0] == (10, 9)
    turn2 = run_turn(bot, ants2, [], [(0, 10)], [H1])
    assert (ants2[0], "w") not in turn2.orders
    assert (ants2[0], "n") in turn2.orders


def test_denial_still_draws_two() -> None:
    # Regression: contested clusters still draw exactly two ants.
    foods = [(5, 5), (5, 6), (5, 7)]
    enemies = [(5, 4), (5, 8), (6, 5)]
    ants = [(0, 0), (0, 1), (0, 2), (0, 3)]
    target = SQ.assign_food_targets(ants, foods, enemies, torus, ROWS, COLS)
    assert len(target) == 2
    assert len(set(target.values())) == 2


def test_matches_understudy_when_unthreatened() -> None:
    # Differential pin: with no threatened home hill (raiders far
    # away), every Squire order matches Understudy exactly -- the
    # sally changes defense only.
    ants = [(2, 2), (3, 3), (18, 18)]
    foods = [(5, 5), (15, 15)]
    enemies = [(10, 10)]
    homes = [(0, 0)]
    hills = [(19, 19)]
    squire = fresh_bot()
    us_bot = US.Understudy()
    us_bot.do_setup(cast(Any, FakeAnts([], [], [], [], [])))
    s_fake = FakeAnts(ants, foods, enemies, homes, hills)
    u_fake = FakeAnts(ants, foods, enemies, homes, hills)
    squire.do_turn(cast(Any, s_fake))
    us_bot.do_turn(cast(Any, u_fake))
    assert s_fake.orders == u_fake.orders
    assert len(s_fake.orders) == 3


def test_siege_converges_to_clean_kill_setup() -> None:
    # End-to-end siege: a raider walks onto the home hill over
    # four turns. The anchor holds cover throughout, the extra
    # converges, the hill square stays open every turn (spawns
    # flow), and both guards end in attack range of the raider on
    # the hill -- a clean 2v1 under focus rules (each guard sees
    # one enemy, the raider sees two, so only it dies).
    bot = fresh_bot()
    ants = [(9, 10), (8, 8)]
    raider: Loc = (10, 14)
    for _ in range(4):
        fake = run_turn(bot, ants, [raider], [HOME])
        assert HOME not in destinations_of(fake)
        next_ants = []
        for a in ants:
            moves = [d for o, d in fake.orders if o == a]
            next_ants.append(fake.destination(a, moves[0]) if moves else a)
        ants = next_ants
        stepped = (raider[0], raider[1] - 1)
        if stepped not in ants:
            raider = stepped
    assert raider == HOME
    assert sorted(ants) == [(9, 10), (9, 11)]
    for g in ants:
        assert (g[0] - raider[0]) ** 2 + (g[1] - raider[1]) ** 2 <= 5


def test_anchor_holds_against_adjacent_raider() -> None:
    # Raider breathing down the anchor's neck: the anchor still
    # holds cover (no fleeing, no suicidal step) -- the 1v1 trade
    # happens on the cover square with the hill open behind it.
    bot = fresh_bot()
    fake = run_turn(bot, [(10, 11)], [(10, 12)], [HOME])
    assert fake.orders == []
    assert HOME not in destinations_of(fake)


def test_claimed_guard_still_gathers() -> None:
    # Defense never starves the economy: a guard with a safe food
    # claim takes it first and only covers when unclaimed.
    bot = fresh_bot()
    fake = run_turn(bot, [(10, 11)], [(10, 14)], [HOME], foods=[(9, 11)])
    assert fake.orders == [((10, 11), "n")]


def test_guards_split_across_two_hills() -> None:
    # Two threatened hills, one nearby guard each: both anchor
    # in place instead of piling onto one hill, and both spawn
    # squares stay open.
    bot = fresh_bot()
    homes = [(10, 10), (0, 0)]
    fake = run_turn(bot, [(10, 11), (0, 1)], [(10, 14), (0, 5)], homes)
    assert fake.orders == []
    assert (10, 10) not in destinations_of(fake)
    assert (0, 0) not in destinations_of(fake)


def test_corridor_through_hill_still_routes() -> None:
    # Only a one-wide corridor crosses the home hill (everything
    # else is water): the hill-free search fails, so the fallback
    # plain shortest path still moves the guard instead of idling.
    class CorridorAnts(FakeAnts):
        def passable(self, loc: Loc) -> bool:
            return loc[0] == 5

    bot = fresh_bot()
    fake = CorridorAnts([(5, 3)], [], [(5, 7)], [(5, 5)], [])
    bot.do_turn(cast(Any, fake))
    assert fake.orders == [((5, 3), "e")]


def test_hill_less_army_still_fights() -> None:
    # All home hills razed but ants alive: no crash, the army
    # still musters on the known enemy hill.
    bot = fresh_bot()
    fake = run_turn(bot, [(10, 5), (10, 6)], [], [], [H1])
    assert len(fake.orders) == 2
    assert fake.orders[0][0] == (10, 5)


def test_defense_takes_priority_over_muster() -> None:
    # Mid-game: an unclaimed ant with a known enemy hill marches
    # on the home raider first, not off to the muster hill.
    bot = fresh_bot()
    fake = run_turn(bot, [(10, 5)], [(10, 14)], [HOME], [H1])
    assert fake.orders == [((10, 5), "e")]


def test_maze_threatened_turn_stays_fast() -> None:
    # Water maze forces hill-avoiding BFS plus fallbacks all over;
    # 80 ants defending still finish well under 1000ms.
    class MazeAnts(FakeAnts):
        def passable(self, loc: Loc) -> bool:
            if loc in self._ants or loc in self._enemies:
                return True
            return (loc[0] + loc[1]) % 3 != 0

    bot = fresh_bot()
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(80)]
    enemies = [(10, 14), (0, 5)]
    fake = MazeAnts(ants, [], enemies, [HOME], [H1])
    start = time.perf_counter()
    bot.do_turn(cast(Any, fake))
    assert time.perf_counter() - start < 1.0


def test_broad_parity_with_understudy() -> None:
    # 60 seeded random unthreatened boards (water, 1-2 homes,
    # enemy hills, distant enemies): Squire matches Understudy
    # nearly everywhere -- food and muster keep the proven
    # shortest paths, so only rare spawn-friendly explore steps
    # near home hills differ.
    import random as _random

    import test_squire as _self

    class WaterAnts(FakeAnts):
        water: set[Loc] = set()

        def passable(self, loc: Loc) -> bool:
            return loc not in self.water

    old_rows, old_cols = _self.ROWS, _self.COLS
    try:
        _random.seed(1234)
        diffs = 0
        for _ in range(60):
            size = _random.choice([10, 15, 20, 25])
            _self.ROWS, _self.COLS = size, size
            cells = [(r, c) for r in range(size) for c in range(size)]
            WaterAnts.water = {x for x in cells if _random.random() < 0.15}
            free = [x for x in cells if x not in WaterAnts.water]
            ants = _random.sample(free, min(12, len(free)))
            foods = _random.sample(free, min(8, len(free)))
            homes = _random.sample(free, min(2, len(free)))
            hills = _random.sample(free, min(2, len(free)))
            enemies = [
                x
                for x in _random.sample(free, min(6, len(free)))
                if all(torus(x, h) > 16 for h in homes)
            ]
            squire = fresh_bot()
            plain = US.Understudy()
            plain.do_setup(cast(Any, FakeAnts([], [], [], [], [])))
            s_fake = WaterAnts(ants, foods, enemies, homes, hills)
            u_fake = WaterAnts(ants, foods, enemies, homes, hills)
            s_fake.rows = s_fake.cols = size
            u_fake.rows = u_fake.cols = size
            squire.do_turn(cast(Any, s_fake))
            plain.do_turn(cast(Any, u_fake))
            if s_fake.orders != u_fake.orders:
                diffs += 1
        assert diffs <= 3
    finally:
        _self.ROWS, _self.COLS = old_rows, old_cols


def test_crowded_threatened_turn_stays_fast() -> None:
    # 120 ants defending two threatened hills plus a failed hill
    # challenge: the full turn still finishes under 1000ms.
    bot = fresh_bot()
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(120)]
    run_turn(bot, ants, [(10, 14)], [HOME], [H1])
    start = time.perf_counter()
    run_turn(bot, ants, [(10, 14), (0, 0)], [HOME], [H1])
    assert time.perf_counter() - start < 1.0
