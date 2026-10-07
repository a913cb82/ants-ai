#!/usr/bin/env python
"""Turnstile4 (champion combat + sitter rotation) tests.

No engine games.

Turnstile4 is champion Crowd's full combat chain (pack-gated seek,
committed-join packs, ahead-only 1v1 duels, off-hill screening,
10-gate equal trades, fearless small fights) plus Turnstile's
economy guard: an ant sitting on one square for 50+ consecutive
turns rotates off toward the nearest non-sitting ant instead of
idling. Threatened sitters stay; recent movers never rotate.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import combat as CB  # noqa: E402
import Turnstile4 as CS  # noqa: E402

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
        hills: list[Loc] | None = None,
        home: list[Loc] | None = None,
    ) -> None:
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = 5
        self._mine = list(mine)
        self._enemies = list(enemies)
        self._foods = list(foods or [])
        self._water = set(water or set())
        self._hills = list(hills or [])
        self._home = list(home or [])
        self.orders: list[tuple[Loc, str]] = []

    def food(self) -> list[Loc]:
        return list(self._foods)

    def my_ants(self) -> list[Loc]:
        return list(self._mine)

    def enemy_ants(self) -> list[tuple[Loc, int]]:
        return [(e, 1) for e in self._enemies]

    def enemy_hills(self) -> list[tuple[Loc, int]]:
        return [(h, 1) for h in self._hills]

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
    hills: list[Loc] | None = None,
    home: list[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], object]:
    fake = FakeAnts(mine, enemies, foods, water, hills, home)
    bot = CS.Turnstile4()
    bot.sit = dict(sit or {})
    bot.do_turn(fake)
    return fake.orders, bot


def step_to(fake: FakeAnts, loc: Loc, direction: str) -> Loc:
    return fake.destination(loc, direction)


def test_sitter_rotates_off_after_50() -> None:
    # (5,5) sat 50 turns; partner at (10,10). The sitter must vacate
    # toward its partner instead of idling.
    mine = [(5, 5), (10, 10)]
    orders, _ = run_turn(mine, [], {(5, 5): 50})
    assert (5, 5) in dict(orders)
    probe = FakeAnts(mine, [])
    moved = step_to(probe, (5, 5), dict(orders)[(5, 5)])
    assert probe.distance(moved, (10, 10)) < probe.distance((5, 5), (10, 10))


def test_threatened_sitter_stays() -> None:
    # Enemy adjacent to the 99-turn sitter: direct threat, so no
    # rotation entry and the sitter holds its square.
    mine = [(5, 5), (15, 15)]
    enemies = [(5, 6)]
    assert CS.turnstile_swaps({(5, 5): 99}, mine, enemies, 5, ROWS, COLS) == {}
    orders, _ = run_turn(mine, enemies, {(5, 5): 99})
    assert (5, 5) not in dict(orders)


def test_movers_never_rotate() -> None:
    # Squares below the limit -- including stale keys for squares no
    # ant occupies -- never produce a swap.
    mine = [(5, 5), (10, 10)]
    assert CS.turnstile_swaps({(5, 5): 49, (0, 0): 500}, mine, [], 5, ROWS, COLS) == {}
    assert CS.turnstile_swaps({}, mine, [], 5, ROWS, COLS) == {}
    # Full turns with all sits below the limit match rotation-off.
    import random

    rng = random.Random(39)
    locs = [(r, c) for r in range(ROWS) for c in range(COLS)]
    orig = CS.turnstile_swaps
    CS.turnstile_swaps = _no_swaps
    try:
        for _ in range(30):
            n_ants = rng.randint(1, 6)
            pick = rng.sample(locs, n_ants + rng.randint(0, 5))
            ants_here = pick[:n_ants]
            foes = pick[n_ants:]
            sit = {a: rng.randint(0, 49) for a in ants_here}
            assert run_turn(ants_here, foes, sit)[0] == run_turn(ants_here, foes)[0]
    finally:
        CS.turnstile_swaps = orig


def test_packed_seek_advances_on_near_enemy() -> None:
    # Champion leg 1+7: a packed ant (3+ friends within 10) with a
    # foe within seek range and no food/hills advances on the foe.
    mine = [(5, 5), (5, 6), (6, 5), (6, 6)]
    enemies = [(5, 9)]
    orders, _ = run_turn(mine, enemies)
    # At least the nearest hunter steps east toward (5,9).
    assert dict(orders).get((5, 6)) == "e"


def test_losing_solo_1v1_holds() -> None:
    # Grinder gate: a lone ant facing a 1v1 contact step while the
    # visible army trails must not donate.
    mine = [(5, 5)]
    enemies = [(5, 7), (10, 10), (11, 11)]
    orders, _ = run_turn(mine, enemies)
    assert dict(orders).get((5, 5)) != "e"


def test_sit_ages_and_resets() -> None:
    # Held squares age, moved squares reset, empty squares vanish.
    sit: dict[Loc, int] = {(5, 5): 10, (9, 9): 99}
    CS.age_sits(sit, [(5, 5), (6, 6)], {(6, 6)})
    assert sit == {(5, 5): 11}


def test_sit_accumulates_then_rotates_over_turns() -> None:
    # Open board, 60 turns: exploring ants never idle, so every
    # sit stays far below the fuse -- rotation is a deadlock guard
    # that fires only when ants truly cannot move.
    mine = [(5, 5), (10, 10)]
    bot = CS.Turnstile4()
    bot.sit = {}
    for _ in range(60):
        fake = FakeAnts(mine, [])
        bot.do_turn(fake)
        orders = dict(fake.orders)
        mine = [step_to(fake, m, orders[m]) if m in orders else m for m in mine]
    assert all(v < 50 for v in bot.sit.values()), dict(bot.sit)
    # Deadlock: a water-boxed ant cannot move, so its sit arms the
    # fuse across turns while the free partner keeps resetting.
    boxed = [(5, 5), (15, 15)]
    water = {(4, 5), (6, 5), (5, 4), (5, 6)}
    bot2 = CS.Turnstile4()
    bot2.sit = {}
    for _ in range(55):
        fake = FakeAnts(boxed, [], water=water)
        bot2.do_turn(fake)
        orders = dict(fake.orders)
        boxed = [step_to(fake, m, orders[m]) if m in orders else m for m in boxed]
    assert boxed[0] == (5, 5)  # still trapped
    assert bot2.sit.get((5, 5), 0) >= 55  # fuse armed, no escape square
    assert all(v < 50 for k, v in bot2.sit.items() if k != (5, 5))


def test_orders_always_legal_fuzz() -> None:
    # Random boards: every issued order targets a passable,
    # unoccupied, unclaimed square exactly once per ant.
    import random

    rng = random.Random(2026)
    for trial in range(60):
        rows = cols = 20
        locs = [(r, c) for r in range(rows) for c in range(cols)]
        mine = rng.sample(locs, rng.randint(1, 10))
        rest = [L for L in locs if L not in mine]
        foes = rng.sample(rest, rng.randint(0, 6))
        rest2 = [L for L in rest if L not in foes]
        foods = rng.sample(rest2, rng.randint(0, 8))
        water = set(rng.sample(rest2, rng.randint(0, 10)))
        foods = [f for f in foods if f not in water]
        hills = rng.sample(rest2, 1) if rng.random() < 0.3 else []
        fake = FakeAnts(mine, foes, foods, water, hills)
        bot = CS.Turnstile4()
        bot.sit = {m: rng.randint(0, 60) for m in mine}
        bot.do_turn(fake)
        seen: set[Loc] = set()
        for frm, d in fake.orders:
            assert frm in mine
            dst = step_to(fake, frm, d)
            assert dst not in seen, (trial, frm, d)
            seen.add(dst)
            assert fake.passable(dst), (trial, frm, d)
            assert dst not in mine and dst not in foes, (trial, frm, d)
    import random

    rng = random.Random(7)
    rows = cols = 100
    locs = [(r, c) for r in range(rows) for c in range(cols)]
    mine = rng.sample(locs, 300)
    foes = rng.sample(locs, 30)
    sit = {m: rng.randint(0, 49) for m in mine}
    for m in mine[:3]:
        sit[m] = 50 + rng.randint(0, 5)
    ordered = set(mine[::2])
    reps = 100
    start = time.perf_counter()
    for _ in range(reps):
        swaps = CS.turnstile_swaps(sit, mine, foes, 5, rows, cols)
        CS.age_sits(dict(sit), mine, ordered)
    elapsed = (time.perf_counter() - start) / reps
    assert len(swaps) == 3
    assert elapsed < 0.002


def test_full_turn_300_ants_under_second() -> None:
    # One do_turn with a crowd must finish deep inside 1000 ms.
    import random

    rng = random.Random(11)
    rows = cols = 60
    locs = [(r, c) for r in range(rows) for c in range(cols)]
    mine = rng.sample(locs, 300)
    foes = rng.sample(locs, 20)
    foods = rng.sample(locs, 40)
    fake = FakeAnts(mine, foes, foods)
    fake.rows = rows
    fake.cols = cols
    bot = CS.Turnstile4()
    start = time.perf_counter()
    bot.do_turn(fake)
    assert (time.perf_counter() - start) < 1.0
    assert CB.CROWD_LIMIT == 10


def test_pathfinding_routes_around_water() -> None:
    # Vertical water wall at col 6 with a single gap at (10,6):
    # food beyond the wall must pull the ant east through the gap,
    # never into the wall.
    water = {(r, 6) for r in range(ROWS)} - {(10, 6)}
    mine = [(10, 4)]
    foods = [(10, 8)]
    orders, _ = run_turn(mine, [], foods=foods, water=water)
    assert dict(orders).get((10, 4)) == "e"


def test_unreachable_food_falls_back_to_explore() -> None:
    # Food sealed in a water pocket: no path, so the ant must not
    # crash and must not step into water (explore or hold instead).
    water = {(9, 9), (9, 10), (9, 11), (10, 9), (10, 11), (11, 9), (11, 10), (11, 11)}
    mine = [(5, 5)]
    foods = [(10, 10)]
    fake = FakeAnts(mine, [], foods, water)
    bot = CS.Turnstile4()
    bot.do_turn(fake)
    for frm, d in fake.orders:
        assert step_to(fake, frm, d) not in water


def test_combat_constants_and_gates() -> None:
    # Pins the champion combat constants this entry depends on.
    assert CB.SEEK_RANGE == 8
    assert CB.EQUAL_TRADE_NEAR == 10
    assert CB.PACK_NEED == 3
    assert CB.PACK_RADIUS == 10
    assert CB.CROWD_LIMIT == 10
    assert CB.crowd_fearless(9) is True
    assert CB.crowd_fearless(10) is False
    # Grinder: friendless 1v1 engages only when the army leads.
    assert CB.grinder_release(0, 1, 11, 10) is True
    assert CB.grinder_release(0, 1, 10, 10) is False
    assert CB.grinder_release(0, 1, 9, 10) is False
    assert CB.grinder_release(1, 1, 11, 10) is False
    assert CB.grinder_release(0, 2, 11, 10) is False
    # Join: a foe needs 2+ commitments to release attackers.
    assert CB.joined_attackers({0: (1, 1), 1: (1, 1), 2: (3, 3)}) == {0, 1}
    assert CB.joined_attackers({0: (1, 1)}) == set()
    # Pack: 3+ friends within 10 steps.

    def dist(a: Loc, b: Loc) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    assert CB.has_pack((0, 0), [(0, 0), (0, 1), (0, 2), (0, 3)], dist) is True
    assert CB.has_pack((0, 0), [(0, 0), (0, 1), (0, 2)], dist) is False


def test_guard_answers_threatened_home_hill() -> None:
    # Enemy within 10 of a home hill, with backup nearby: the
    # nearest ant must step toward the hill, not wander. (A lone
    # ant correctly refuses the unsafe step under champion safety.)
    mine = [(2, 6), (2, 7), (2, 8), (3, 6)]
    enemies = [(2, 4)]
    orders, _ = run_turn(mine, enemies, home=[(2, 2)])
    assert (2, 6) in dict(orders)
    probe = FakeAnts(mine, enemies)
    moved = step_to(probe, (2, 6), dict(orders)[(2, 6)])
    assert probe.distance(moved, (2, 2)) < probe.distance((2, 6), (2, 2))


def test_denial_caps_contested_cluster_at_two() -> None:
    # Three enemies around one food cluster: exactly two ants take
    # the two nearest foods; the third food stays unclaimed.
    mine = [(0, 0), (0, 3), (0, 6), (15, 15)]
    foods = [(5, 5), (5, 6), (5, 7)]
    enemies = [(6, 5), (6, 6), (4, 6)]
    target = CS.assign_food_targets(
        mine, foods, enemies, FakeAnts(mine, enemies).distance, ROWS, COLS
    )
    assert len(target) == 2
    claimed = set(target.values())
    assert claimed <= set(foods) and len(claimed) == 2
    assert set(foods) - claimed  # one food deliberately left


def test_uncontested_food_goes_greedy() -> None:
    # No enemies: every food gets its nearest ant, champion greedy.
    mine = [(0, 0), (0, 10)]
    foods = [(0, 1), (0, 9)]
    target = CS.assign_food_targets(
        mine, foods, [], FakeAnts(mine, []).distance, ROWS, COLS
    )
    assert target == {0: (0, 1), 1: (0, 9)}
