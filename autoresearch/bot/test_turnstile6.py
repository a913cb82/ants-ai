#!/usr/bin/env python
"""Turnstile6 (vigil raid discipline) tests.

No engine games.

New over Turnstile: remembered enemy hills carry a last-seen turn
(vigil) and expire after VIGIL_TURNS without re-seeing; ghosts that
are visible-but-empty drop immediately; and the Flood hill march
is pack-gated (lone ants without a pack hold economy/explore
instead of suicide-marching, unless the visible army leads).
Sitter rotation is unchanged.
"""

import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Turnstile6 as TS  # noqa: E402

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
        enemy_hills: list[Loc] | None = None,
        my_hills: list[Loc] | None = None,
        visible: set[Loc] | None = None,
    ) -> None:
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = 5
        self._mine = list(mine)
        self._enemies = list(enemies)
        self._foods = list(foods or [])
        self._water = set(water or set())
        self._enemy_hills = list(enemy_hills or [])
        self._my_hills = list(my_hills or [])
        self._visible = set(visible) if visible is not None else None
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

    def visible(self, loc: Loc) -> bool:
        if self._visible is None:
            return False
        return loc in self._visible

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


def _bot_class():
    return getattr(TS, "Turnstile6", TS.Turnstile)


def run_turn(
    mine: list[Loc],
    enemies: list[Loc],
    sit: dict[Loc, int] | None = None,
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
    visible: set[Loc] | None = None,
    bot: Any | None = None,
) -> tuple[list[tuple[Loc, str]], Any]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills, visible)
    b = bot if bot is not None else _bot_class()()
    if sit is not None:
        b.sit = dict(sit)
    b.do_turn(fake)
    return fake.orders, b


def step_to(fake: FakeAnts, loc: Loc, direction: str) -> Loc:
    return fake.destination(loc, direction)


# --- sitter rotation (unchanged from Turnstile) ---


def test_sitter_rotates_off_after_50() -> None:
    mine = [(5, 5), (10, 10)]
    orders, _ = run_turn(mine, [], {(5, 5): 50})
    assert (5, 5) in dict(orders)
    probe = FakeAnts(mine, [])
    moved = step_to(probe, (5, 5), dict(orders)[(5, 5)])
    assert probe.distance(moved, (10, 10)) < probe.distance((5, 5), (10, 10))


def test_threatened_sitter_stays() -> None:
    mine = [(5, 5), (15, 15)]
    enemies = [(5, 6)]
    assert TS.turnstile_swaps({(5, 5): 99}, mine, enemies, 5, ROWS, COLS) == {}
    orders, _ = run_turn(mine, enemies, {(5, 5): 99})
    assert (5, 5) not in dict(orders)


def test_movers_never_rotate() -> None:
    mine = [(5, 5), (10, 10)]
    assert TS.turnstile_swaps({(5, 5): 49, (0, 0): 500}, mine, [], 5, ROWS, COLS) == {}
    assert TS.turnstile_swaps({}, mine, [], 5, ROWS, COLS) == {}


# --- vigil: ghost expiry (new, must fail before fix) ---


def test_ghost_expires_without_reseeing() -> None:
    # One ghost hill at (2, 2); never re-seen. After VIGIL_TURNS it
    # must drop so the ant stops marching to it.
    assert hasattr(TS, "VIGIL_TURNS"), "Turnstile6 needs VIGIL_TURNS"
    bot = _bot_class()()
    mine = [(10, 10)]
    # turn 1: see the hill
    _, bot = run_turn(mine, [], enemy_hills=[(2, 2)], bot=bot)
    assert (2, 2) in bot.remembered_hills
    # run VIGIL_TURNS quiet turns (hill not visible, not re-seen)
    for _ in range(TS.VIGIL_TURNS):
        _, bot = run_turn(mine, [], bot=bot)
    assert (2, 2) not in bot.remembered_hills, "stale ghost must expire"


def test_reseen_ghost_refreshes() -> None:
    # Re-seeing the hill resets the clock; it must survive.
    bot = _bot_class()()
    mine = [(10, 10)]
    _, bot = run_turn(mine, [], enemy_hills=[(2, 2)], bot=bot)
    for _ in range(TS.VIGIL_TURNS - 1):
        _, bot = run_turn(mine, [], bot=bot)
    assert (2, 2) in bot.remembered_hills
    _, bot = run_turn(mine, [], enemy_hills=[(2, 2)], bot=bot)
    for _ in range(TS.VIGIL_TURNS - 1):
        _, bot = run_turn(mine, [], bot=bot)
    assert (2, 2) in bot.remembered_hills, "re-seen ghost must refresh"


def test_visible_empty_ghost_dropped() -> None:
    # Ghost at (2, 2) is currently visible but no hill stands there:
    # drop immediately even before the fuse burns.
    bot = _bot_class()()
    mine = [(10, 10)]
    _, bot = run_turn(mine, [], enemy_hills=[(2, 2)], bot=bot)
    assert (2, 2) in bot.remembered_hills
    orders, bot2 = run_turn(mine, [], enemy_hills=[], visible={(2, 2)}, bot=bot)
    assert (2, 2) not in bot2.remembered_hills
    _ = orders


def test_expired_ghost_stops_march() -> None:
    # With only an expired ghost on the board, the ant must explore
    # (north, least-visited tie-break) instead of marching south
    # toward the old hill.
    bot = _bot_class()()
    mine = [(10, 10)]
    _, bot = run_turn(mine, [], enemy_hills=[(15, 10)], bot=bot)
    for _ in range(TS.VIGIL_TURNS):
        _, bot = run_turn(mine, [], bot=bot)
    orders, _ = run_turn(mine, [], bot=bot)
    assert dict(orders).get((10, 10)) == "n"


# --- raid gate: pack-gated hill march (new, must fail before fix) ---


def test_lone_ant_holds_without_pack() -> None:
    # Lone ant at (10, 10), fresh ghost at (15, 10) (south), no
    # enemies visible, no pack: it must NOT march south to the hill.
    # Champion explore from a fresh visit map goes north.
    assert hasattr(TS, "has_raid_pack"), "Turnstile6 needs has_raid_pack"
    orders, _ = run_turn([(10, 10)], [], enemy_hills=[(15, 10)])
    assert dict(orders).get((10, 10)) == "n", "lone ant must hold economy, not raid"


def test_packed_ants_raid() -> None:
    # Three ants together hold a pack: the group still marches on
    # the ghost hill (south toward (15, 10)).
    mine = [(10, 10), (10, 11), (10, 9)]
    orders, _ = run_turn(mine, [], enemy_hills=[(15, 10)])
    got = dict(orders).get((10, 10))
    probe = FakeAnts(mine, [])
    assert got is not None
    moved = step_to(probe, (10, 10), got)
    assert probe.distance(moved, (15, 10)) < probe.distance((10, 10), (15, 10))


def test_ahead_army_raids_lone() -> None:
    # Lone ant but army ahead (3 vs 1 visible enemy): the raid goes
    # through despite no pack.
    mine = [(10, 10), (0, 0), (0, 1)]
    enemies = [(5, 5)]
    orders, _ = run_turn(mine, enemies, enemy_hills=[(15, 10)])
    got = dict(orders).get((10, 10))
    probe = FakeAnts(mine, enemies)
    assert got is not None
    moved = step_to(probe, (10, 10), got)
    assert probe.distance(moved, (15, 10)) < probe.distance((10, 10), (15, 10))


def test_has_raid_pack_pure() -> None:
    def dist(a: Loc, b: Loc) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    assert TS.has_raid_pack((0, 0), [(0, 0), (0, 1), (0, 2)], dist) is True
    assert TS.has_raid_pack((0, 0), [(0, 0)], dist) is False
    assert TS.has_raid_pack((10, 10), [(10, 10), (0, 0), (0, 1)], dist) is False


def test_raid_gate_cost_under_half_ms() -> None:
    import random

    rng = random.Random(11)
    locs = [(r, c) for r in range(ROWS) for c in range(COLS)]
    mine = rng.sample(locs, 60)

    def dist(a: Loc, b: Loc) -> int:
        dr = abs(a[0] - b[0])
        dr = min(dr, ROWS - dr)
        dc = abs(a[1] - b[1])
        dc = min(dc, COLS - dc)
        return dr + dc

    reps = 300
    start = time.perf_counter()
    for _ in range(reps):
        for m in mine[:10]:
            TS.has_raid_pack(m, mine, dist)
    elapsed = (time.perf_counter() - start) / reps
    assert elapsed < 0.0005


def test_no_hill_matches_champion_economy() -> None:
    # Without hills, Turnstile6 is stable and self-consistent:
    # denial economy, sitter rotation, defense, and explore run
    # deterministically with legal, unique orders (the base file
    # this once diffed against no longer ships with the entry).
    import random

    rng = random.Random(99)
    locs = [(r, c) for r in range(ROWS) for c in range(COLS)]
    for _ in range(30):
        n = rng.randint(1, 6)
        pick = rng.sample(locs, n + rng.randint(0, 4))
        mine = pick[:n]
        foes = pick[n : n + 2]
        foods = rng.sample(locs, rng.randint(0, 4))
        f1 = FakeAnts(mine, foes, foods)
        b1 = _bot_class()()
        b1.do_turn(f1)
        f2 = FakeAnts(mine, foes, foods)
        b2 = _bot_class()()
        b2.do_turn(f2)
        assert f1.orders == f2.orders
        srcs = [loc for loc, _ in f1.orders]
        assert len(srcs) == len(set(srcs))
        dests = [f1.destination(loc, d) for loc, d in f1.orders]
        assert len(dests) == len(set(dests))


def test_defense_still_fires_without_pack() -> None:
    # An ant beside a threatened home hill must step toward it even
    # with no raid pack and even when a far ghost hill exists:
    # defense is never pack-gated, only the hill hunt.
    mine = [(10, 11)]
    my_hills = [(10, 10)]
    enemies = [(10, 13)]
    orders, _ = run_turn(mine, enemies, my_hills=my_hills)
    assert dict(orders).get((10, 11)) == "w"
    orders2, _ = run_turn(mine, enemies, my_hills=my_hills, enemy_hills=[(2, 2)])
    assert dict(orders2).get((10, 11)) == "w"


def test_full_turn_under_500ms() -> None:
    import random

    rng = random.Random(3)
    locs = [(r, c) for r in range(ROWS) for c in range(COLS)]
    mine = rng.sample(locs, 120)
    foes = rng.sample(locs, 20)
    foods = rng.sample(locs, 30)
    fake = FakeAnts(mine, foes, foods, enemy_hills=[(2, 2), (17, 17)])
    bot = _bot_class()()
    start = time.perf_counter()
    bot.do_turn(fake)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.500


def test_denial_economy_preserved() -> None:
    # Contested cluster (3 enemies near two foods): exactly two ants
    # claim, on the two nearest foods; other foods stay unclaimed.
    import Turnstile6 as T6

    def dist(a: Loc, b: Loc) -> int:
        dr = abs(a[0] - b[0])
        dr = min(dr, ROWS - dr)
        dc = abs(a[1] - b[1])
        dc = min(dc, COLS - dc)
        return dr + dc

    ants_list = [(5, 5), (5, 6), (5, 7), (15, 15), (15, 14)]
    foods = [(6, 5), (6, 6), (6, 7), (0, 0)]
    enemies = [(6, 5), (6, 6), (7, 5)]
    target = T6.assign_food_targets(ants_list, foods, enemies, dist, ROWS, COLS)
    claimed = {foods.index(v) for v in target.values()}
    # Contested triple draws exactly two claims; the far food still
    # draws one greedy claim.
    assert len([c for c in claimed if c in (0, 1, 2)]) == 2
    assert 3 in claimed


def test_stand_on_ghost_discards() -> None:
    # Standing on a remembered hill razes it from memory.
    bot = _bot_class()()
    mine = [(10, 10)]
    _, bot = run_turn(mine, [], enemy_hills=[(2, 2)], bot=bot)
    assert (2, 2) in bot.remembered_hills
    _, bot = run_turn([(2, 2)], [], bot=bot)
    assert (2, 2) not in bot.remembered_hills


def test_packed_group_musters_army_nearest() -> None:
    # Packed group with two ghosts marches toward the army-nearest
    # hill (Flood muster preserved when pack holds).
    mine = [(10, 10), (10, 11), (10, 9)]
    ghosts = [(2, 2), (15, 10)]
    orders, _ = run_turn(mine, [], enemy_hills=ghosts)
    got = dict(orders).get((10, 10))
    assert got is not None
    probe = FakeAnts(mine, [])
    moved = step_to(probe, (10, 10), got)
    # (15, 10) is army-nearest (sum distances smaller than (2, 2)).
    assert probe.distance(moved, (15, 10)) < probe.distance((10, 10), (15, 10))


def test_sitter_rotation_beats_ghost_hill() -> None:
    # A 50-turn sitter with a fresh ghost hill still rotates toward
    # its partner instead of marching to the hill: rotation runs
    # before food/hill branches.
    mine = [(5, 5), (10, 10)]
    orders, _ = run_turn(mine, [], sit={(5, 5): 50}, enemy_hills=[(15, 15)])
    assert (5, 5) in dict(orders)
    probe = FakeAnts(mine, [])
    moved = step_to(probe, (5, 5), dict(orders)[(5, 5)])
    assert probe.distance(moved, (10, 10)) < probe.distance((5, 5), (10, 10))


def test_constants_sane() -> None:
    # Lock the tuned knobs: vigil fuse generous but bounded, raid
    # pack loose (pair+1) with a wide radius, all well under the
    # 1000 ms turn budget regime.
    assert TS.VIGIL_TURNS == 75
    assert TS.RAID_NEED == 2
    assert TS.RAID_RADIUS == 12


def test_orders_legal_unique() -> None:
    # Every order starts from a live ant, targets a passable square,
    # and no two orders share a source or a destination.
    import random

    rng = random.Random(4242)
    locs = [(r, c) for r in range(ROWS) for c in range(COLS)]
    for _ in range(40):
        n = rng.randint(1, 10)
        pick = rng.sample(locs, n + rng.randint(0, 6))
        mine = pick[:n]
        foes = pick[n : n + 3]
        foods = rng.sample(locs, rng.randint(0, 5))
        water = set(rng.sample(locs, rng.randint(0, 10)))
        water -= set(mine) | set(foes) | set(foods)
        fake = FakeAnts(mine, foes, foods, water, rng.sample(locs, 1))
        bot = _bot_class()()
        bot.do_turn(fake)
        srcs = [loc for loc, _ in fake.orders]
        assert len(srcs) == len(set(srcs))
        assert all(s in mine for s in srcs)
        dests = [fake.destination(loc, d) for loc, d in fake.orders]
        assert len(dests) == len(set(dests))
        assert all(fake.passable(d) for d in dests)
