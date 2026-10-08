#!/usr/bin/env python
"""Rally tests: pack-gated centroid seekers press small fights.

Rally keeps the Odds spine (denial economy, join, ahead-only 1v1,
off-hill screen, equal trades at 10 near) and adds one new mix:

(a) pack gate: only ants with 3+ friends within 10 seek; packless
    ants step toward their nearest friend instead of chasing;
(b) rally mark: a packed seeker marches on the foe nearest the
    army centroid among foes in SEEK_RANGE of itself, so the pack
    converges instead of scattering into 1v1s;
(c) crowd press: the rally advance skips safety while fewer
    than CROWD_LIMIT foes show, ahead or behind; crowds keep
    full safety;
(d) grave check: a remembered hill seen empty is forgotten;
(e) stand-off harvest: paths never route through food squares
    (food gathers by adjacency);
(f) raid margin: hills march only at 2:1 over their campers;
(g) rotated explore: simultaneous explorers fan out;
(h) stand-off sitters: adjacent claimants hold their meal;
(i) deeper paths: BFS budgets run 500 expansions with a healthy
    clock (150 under 300 ms), so long raids route yet huge maps
    degrade instead of timing out.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import io  # noqa: E402
import random  # noqa: E402
from contextlib import redirect_stdout  # noqa: E402

import combat as CX  # noqa: E402
import Rally as RY  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}


class FakeAnts:
    def __init__(
        self,
        mine: list[Loc],
        enemies: list[Loc],
        foods: list[Loc] | None = None,
        water: set[Loc] | None = None,
        enemy_hills: list[Loc] | None = None,
        my_hills: list[Loc] | None = None,
        owners: list[int] | None = None,
    ) -> None:
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = 5
        self._mine = list(mine)
        self._enemies = list(enemies)
        self._owners = list(owners) if owners else [1] * len(enemies)
        self._foods = list(foods or [])
        self._water = set(water or set())
        self._enemy_hills = list(enemy_hills or [])
        self._my_hills = list(my_hills or [])
        self.orders: list[tuple[Loc, str]] = []
        self._seen: set[Loc] = set(mine) | set(enemies)
        self.clock = 100000

    def food(self) -> list[Loc]:
        return list(self._foods)

    def my_ants(self) -> list[Loc]:
        return list(self._mine)

    def enemy_ants(self) -> list[tuple[Loc, int]]:
        return list(zip(self._enemies, self._owners, strict=False))

    def enemy_hills(self) -> list[tuple[Loc, int]]:
        return [(h, 1) for h in self._enemy_hills]

    def my_hills(self) -> list[Loc]:
        return list(self._my_hills)

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

    def visible(self, loc: Loc) -> bool:
        return loc in self._seen

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return self.clock


def run_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
    owners: list[int] | None = None,
) -> tuple[list[tuple[Loc, str]], RY.Rally]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills, owners)
    bot = RY.Rally()
    bot.do_turn(fake)
    return fake.orders, bot


def test_pack_constants() -> None:
    assert CX.PACK_NEED == 3
    assert CX.PACK_RADIUS == 10
    assert CX.CROWD_LIMIT == 10


def test_has_pack_needs_three_friends() -> None:
    probe = FakeAnts([(5, 5)], [])
    assert CX.has_pack((5, 5), [(5, 5), (5, 6), (5, 7), (5, 8)], probe.distance) is True
    assert CX.has_pack((5, 5), [(5, 5), (5, 6), (5, 7)], probe.distance) is False
    assert CX.has_pack((5, 5), [(5, 5)], probe.distance) is False
    far = [(5, 5), (5, 6), (5, 7), (15, 15)]
    assert CX.has_pack((5, 5), far, probe.distance) is False


def test_crowd_fearless_under_limit() -> None:
    assert CX.crowd_fearless(9) is True
    assert CX.crowd_fearless(10) is False
    assert CX.crowd_fearless(0) is True


def test_rally_mark_picks_centroid_nearest_in_range() -> None:
    probe = FakeAnts([(5, 5)], [])
    mine = [(5, 5), (5, 6), (5, 7), (5, 8)]
    # Centroid (5,6); foe (5,14) is centroid-nearest but out of the
    # seeker's range, so the rally falls on (5,9).
    mark = CX.rally_mark((5, 5), mine, [(5, 9), (5, 14)], probe.distance)
    assert mark == (5, 9)
    # Both in range: self-nearest is (5,2) west (dist 3 vs 4) but
    # centroid-nearest is (5,9) east (dist 3 vs 4), so the rally
    # converges east instead of scattering west.
    mark2 = CX.rally_mark((5, 5), mine, [(5, 2), (5, 9)], probe.distance)
    assert mark2 == (5, 9)
    assert CX.rally_mark((5, 5), mine, [(5, 14)], probe.distance) is None
    assert CX.rally_mark((5, 5), mine, [], probe.distance) is None


def test_packless_ant_packs_up_instead_of_chasing() -> None:
    # Lone ant with a foe 5 east: Odds would chase east, Rally has
    # no pack so it must not step toward the foe.
    mine = [(5, 5)]
    enemies = [(5, 10)]
    orders, _ = run_turn(mine, enemies)
    assert orders != [((5, 5), "e")]
    assert len(orders) == 1


def test_packed_pair_converges_on_centroid_foe() -> None:
    # Spaced pack centroid (5,7): self-nearest is (5,2) west but
    # the rally mark is (5,10) east, so the lead ant steps east.
    mine = [(5, 5), (5, 8), (6, 8), (5, 9)]
    enemies = [(5, 2), (5, 10)]
    probe = FakeAnts(mine, enemies)
    assert probe.distance((5, 5), (5, 2)) < probe.distance((5, 5), (5, 10))
    assert CX.rally_mark((5, 5), mine, enemies, probe.distance) == (5, 10)
    orders, _ = run_turn(mine, enemies)
    assert ((5, 5), "e") in orders


def test_ahead_pack_presses_fearless_through_contact() -> None:
    # 4v1 army, 1 foe visible: the spaced pack makes exactly one
    # commitment, so the join stays shut and the contact step east
    # proves the fearless press itself (safety would refuse the
    # friendless equal trade with <10 near).
    mine = [(5, 5), (5, 0), (0, 5), (0, 0)]
    enemies = [(5, 7)]
    orders, _ = run_turn(mine, enemies)
    assert ((5, 5), "e") in orders


def test_behind_pack_presses_small_fight() -> None:
    # 4v6 (behind) but only 6 foes visible: the crowd press fires
    # anyway and the unjoined seeker takes the contact east. The
    # spaced pack makes exactly one commitment, so the join stays
    # shut and the order proves the fearless press itself.
    mine = [(5, 5), (5, 0), (0, 5), (0, 0)]
    enemies = [(5, 7), (15, 15), (15, 16), (15, 17), (0, 10), (0, 11)]
    orders, _ = run_turn(mine, enemies)
    assert ((5, 5), "e") in orders


def test_crowded_pack_holds_safe() -> None:
    # 10 foes visible: the crowd press shuts and the lone contact
    # seeker retreats west exactly as champion instead of pressing.
    mine = [(5, 5), (5, 0), (0, 5), (0, 0)]
    foes = [(5, 7), (15, 15), (15, 16), (15, 17), (0, 10), (0, 11)]
    foes += [(10, 10), (10, 11), (10, 12), (12, 12)]
    probe = FakeAnts(mine, foes)
    assert all(probe.distance((5, 5), e) > 8 or e == (5, 7) for e in foes)
    orders, _ = run_turn(mine, foes)
    assert ((5, 5), "e") not in orders
    assert orders[0] == ((5, 5), "w")


def test_grave_hill_seen_empty_is_forgotten() -> None:
    # Remembered hill visible but gone: no march, hill dropped.
    fake = FakeAnts([(10, 10)], [], enemy_hills=[])
    bot = RY.Rally()
    bot.hills = {(15, 15)}
    fake._seen.add((15, 15))
    bot.do_turn(fake)
    assert (15, 15) not in bot.hills


def test_live_hill_is_kept_and_mustered() -> None:
    mine = [(10, 10)]
    orders, bot = run_turn(mine, [], enemy_hills=[(15, 15)])
    assert (15, 15) in bot.hills
    assert len(orders) == 1


def test_paths_never_step_onto_food() -> None:
    # Food at (5,6) blocks the straight path: the ant must not
    # order onto the food square itself.
    mine = [(5, 5), (5, 4), (4, 5)]
    foods = [(5, 6)]
    enemies = [(5, 12)]
    orders, _ = run_turn(mine, enemies, foods)
    for loc, d in orders:
        assert FakeAnts(mine, enemies).destination(loc, d) not in set(foods)


def test_denial_claims_match_odds_spine() -> None:
    # Contested cluster still draws exactly two claimants.
    mine = [(5, 3), (2, 0), (10, 10)]
    foods = [(5, 6), (2, 3)]
    enemies = [(5, 12), (2, 6), (5, 9), (10, 15)]
    orders, _ = run_turn(mine, enemies, foods, my_hills=[(10, 12)])
    assert orders[0] == ((5, 3), "e") or orders[0][0] == (5, 3)
    assert len(orders) == 3


def test_explore_rotation_fans_out() -> None:
    assert CX.explore_order((5, 5)) != CX.explore_order((6, 6))
    assert sorted(CX.explore_order((5, 5))) == ["e", "n", "s", "w"]


def test_simultaneous_explorers_split() -> None:
    orders, _ = run_turn([(5, 5), (6, 6)], [])
    assert len(orders) == 2
    assert orders[0][1] != orders[1][1]


def test_camped_counts_foes_near_hill() -> None:
    probe = FakeAnts([], [])
    near = [(15, 15), (15, 14), (14, 15)]
    assert CX.camped_at((15, 15), near, probe.distance) == 3
    assert CX.camped_at((15, 15), near + [(5, 5)], probe.distance) == 3
    assert CX.camped_at((5, 5), near + [(5, 5)], probe.distance) == 1


def test_hill_takeable_needs_margin() -> None:
    assert CX.hill_takeable(4, 0) is True
    assert CX.hill_takeable(4, 2) is True
    assert CX.hill_takeable(3, 2) is False
    assert CX.hill_takeable(12, 5) is True
    assert CX.hill_takeable(9, 5) is False


def test_outnumbered_raid_holds_as_no_hill() -> None:
    # 4 ants stare at a hill camped by 3 (4 < 2x3): the raid gate
    # shuts, so the turn explores exactly as with no hill at all.
    # Geometry is forced: muster steps south, explore steps east.
    mine = [(10, 15), (10, 17), (10, 19), (8, 17)]
    camped = [(15, 10), (15, 11), (14, 10)]
    hill = (15, 15)
    probe = FakeAnts(mine, camped)
    assert all(probe.distance(a, e) > 8 for a in mine for e in camped)
    assert CX.camped_at(hill, camped, probe.distance) == 3
    assert not CX.hill_takeable(len(mine), 3)
    orders, _ = run_turn(mine, camped, enemy_hills=[hill])
    assert orders[0] == ((10, 15), "e")
    bare, _ = run_turn(mine, camped)
    assert orders == bare


def test_favored_raid_marches_on_hill() -> None:
    # 6 ants stare at a hill camped by 2 (6 >= 2x2): the raid
    # gate opens and the lead ant musters east onto the march.
    mine = [(8, 14), (8, 12), (8, 10), (6, 14), (6, 12), (6, 10)]
    camped = [(15, 18), (18, 15)]
    hill = (15, 15)
    probe = FakeAnts(mine, camped)
    assert all(probe.distance(a, e) > 8 for a in mine for e in camped)
    assert CX.camped_at(hill, camped, probe.distance) == 2
    assert CX.hill_takeable(len(mine), 2)
    orders, _ = run_turn(mine, camped, enemy_hills=[hill])
    assert orders[0] == ((8, 14), "e")


def test_sitter_holds_adjacent_meal() -> None:
    # Lone ant adjacent to its claim: gathering by adjacency, so
    # it holds instead of exploring off the meal.
    orders, _ = run_turn([(5, 5)], [], foods=[(5, 6)])
    assert orders == []


def test_far_claimant_still_approaches() -> None:
    orders, _ = run_turn([(5, 5)], [], foods=[(5, 9)])
    assert len(orders) == 1
    loc, d = orders[0]
    probe = FakeAnts([(5, 5)], [])
    assert probe.distance(probe.destination(loc, d), (5, 9)) < probe.distance(
        loc, (5, 9)
    )


def test_sitter_steps_off_home_hill() -> None:
    # A sitter parked on its own hill must still walk off so the
    # hill stays spawnable.
    orders, _ = run_turn([(5, 5)], [], foods=[(5, 6)], my_hills=[(5, 5)])
    assert len(orders) == 1
    assert orders[0][0] == (5, 5)
    assert orders[0][1] in ("n", "e", "s", "w")


def test_behind_join_still_engages_shared_foe() -> None:
    # 4v6 (behind): the pack shares foe (5,7), so the join fires
    # and both flankers engage through equal trades anyway.
    mine = [(5, 5), (5, 9), (5, 4), (5, 10)]
    foes = [(5, 7), (15, 15), (15, 16), (15, 17), (0, 0), (0, 1)]
    orders, _ = run_turn(mine, foes)
    assert ((5, 5), "e") in orders
    assert ((5, 9), "w") in orders


def test_reinforce_marches_when_muster_is_camped() -> None:
    # Muster hill H1 is camped (gate shut) but H2 stands empty:
    # the ant reinforces H2 instead of exploring.
    mine = [(6, 12), (6, 15), (8, 13), (8, 15)]
    camped = [(15, 10), (15, 11), (14, 10)]
    far, empty = (15, 15), (2, 2)
    probe = FakeAnts(mine, camped)
    assert all(probe.distance(a, e) > 8 for a in mine for e in camped)
    assert not CX.hill_takeable(len(mine), CX.camped_at(far, camped, probe.distance))
    assert CX.hill_takeable(len(mine), CX.camped_at(empty, camped, probe.distance))
    orders, _ = run_turn(mine, camped, enemy_hills=[far, empty])
    assert len(orders) > 0
    loc, d = orders[0]
    assert probe.distance(probe.destination(loc, d), empty) < probe.distance(loc, empty)


def test_packless_steps_toward_buddy() -> None:
    # No pack and no foe in range: the ant packs up toward its
    # nearest friend instead of exploring away.
    orders, _ = run_turn([(5, 5), (5, 9)], [(5, 15)])
    assert ((5, 5), "e") in orders


def test_second_guard_screens_off_hill() -> None:
    # Two ants, one threatened hill: the holder takes the hill
    # while the second ant screens east toward the razer instead
    # of piling west onto the hill.
    orders, _ = run_turn([(10, 8), (10, 11)], [(10, 16)], my_hills=[(10, 10)])
    assert ((10, 8), "e") in orders
    assert ((10, 11), "e") in orders


def test_guard_holds_threatened_hill() -> None:
    # Lone ant off its threatened hill steps back onto it.
    orders, _ = run_turn([(10, 8)], [(10, 16)], my_hills=[(10, 10)])
    assert orders == [((10, 8), "e")]


def test_nearest_ant_claims_open_food() -> None:
    # Two ants, one meal: the nearer ant takes the approach step.
    orders, _ = run_turn([(5, 5), (5, 0)], [], foods=[(5, 8)])
    assert orders[0][0] == (5, 5)
    loc, d = orders[0]
    probe = FakeAnts([(5, 5), (5, 0)], [])
    assert probe.distance(probe.destination(loc, d), (5, 8)) < probe.distance(
        loc, (5, 8)
    )


def test_real_ants_three_turn_raid_and_grave() -> None:
    # Drive the real ants.py protocol: remember a hill, then see
    # it razed and forget it, across turns with real vision.
    from ants import Ants as RealAnts

    real = RealAnts()
    real.setup(
        "cols 20\nrows 20\nturntime 1000\nturns 500\nviewradius2 77\n"
        "attackradius2 5\nspawnradius2 1\nplayer_seed 7\n"
    )
    bot = RY.Rally()
    bot.do_setup(real)
    real.update("a 5 5 0\na 5 6 0\na 5 7 0\na 5 8 0\nh 15 15 1\n")
    buf = io.StringIO()
    with redirect_stdout(buf):
        bot.do_turn(real)
    assert (15, 15) in bot.hills
    assert any(line.startswith("o ") for line in buf.getvalue().splitlines())
    real.update("a 15 10 0\na 15 11 0\na 14 10 0\na 14 11 0\n")
    with redirect_stdout(io.StringIO()):
        bot.do_turn(real)
    assert (15, 15) not in bot.hills


def test_fuzz_boards_hold_invariants() -> None:
    # Seeded scatter: never crash, never step onto food/water/
    # occupied, at most one order per ant, unique destinations,
    # every turn under a second.
    rng = random.Random(20261008)
    cells = [(r, c) for r in range(ROWS) for c in range(COLS)]
    for _ in range(15):
        spots = rng.sample(cells, rng.randint(2, 30))
        mine = sorted(spots[: rng.randint(1, 12)])
        foes = spots[len(mine) : len(mine) + rng.randint(0, 8)]
        rest = spots[len(mine) + len(foes) :]
        foods = rest[: rng.randint(0, 4)]
        rest = rest[len(foods) :]
        water = set(rest[: rng.randint(0, 6)])
        rest = rest[len(water) :]
        my_hills = rest[: rng.randint(0, 2)]
        rest = rest[len(my_hills) :]
        enemy_hills = rest[: rng.randint(0, 2)]
        owners = [rng.randint(1, 3) for _ in foes]
        start = time.perf_counter()
        orders, _ = run_turn(mine, foes, foods, water, enemy_hills, my_hills, owners)
        assert time.perf_counter() - start < 1.0
        probe = FakeAnts(mine, foes, foods, water)
        seen_ants: set[Loc] = set()
        seen_dest: set[Loc] = set()
        for loc, d in orders:
            assert loc in mine
            assert loc not in seen_ants
            seen_ants.add(loc)
            dest = probe.destination(loc, d)
            assert d in ("n", "e", "s", "w")
            assert probe.passable(dest)
            assert dest not in set(foods)
            assert dest not in seen_dest
            seen_dest.add(dest)
    corner = [(r, c) for r in range(6) for c in range(COLS)]
    for _ in range(10):
        mine = sorted(rng.sample(corner, rng.randint(1, 6)))
        foes = [rng.choice(corner) for _ in range(rng.randint(0, 6))]
        foods = [rng.choice(corner) for _ in range(rng.randint(0, 3))]
        wet = [c for c in corner if c not in mine]
        water = set(rng.sample(wet, min(len(wet), rng.randint(0, 6))))
        my_hills = [rng.choice(corner) for _ in range(rng.randint(0, 2))]
        enemy_hills = [rng.choice(corner) for _ in range(rng.randint(0, 2))]
        owners = [rng.randint(1, 3) for _ in foes]
        start = time.perf_counter()
        orders, _ = run_turn(mine, foes, foods, water, enemy_hills, my_hills, owners)
        assert time.perf_counter() - start < 1.0
        probe = FakeAnts(mine, foes, foods, water)
        seen_ants = set()
        for loc, d in orders:
            assert loc in mine
            assert loc not in seen_ants
            seen_ants.add(loc)
            assert probe.passable(probe.destination(loc, d))


def test_memories_persist_across_turns() -> None:
    # Hills and headings survive across turns on the same bot:
    # an unseen hill stays remembered and last-turn foes seed
    # the closing detector.
    bot = RY.Rally()
    first = FakeAnts([(5, 5)], [(5, 10)], enemy_hills=[(15, 15)])
    bot.do_turn(first)
    assert (15, 15) in bot.hills
    assert bot.prev_enemies == [(5, 10)]
    second = FakeAnts([(5, 5)], [(5, 11)])
    bot.do_turn(second)
    assert (15, 15) in bot.hills
    assert bot.prev_enemies == [(5, 11)]


def test_low_clock_degrades_long_marches_to_explore() -> None:
    # Same two-hill board twice: with a healthy clock the lead ant
    # reinforces toward (2, 2) 14 steps out, but with <300 ms left
    # the 150-budget search cannot route that far, so it explores
    # south instead of burning the clock down.
    mine = [(6, 12), (6, 15), (8, 13), (8, 15)]
    camped = [(15, 10), (15, 11), (14, 10)]
    hills = [(15, 15), (2, 2)]
    fresh, _ = run_turn(mine, camped, enemy_hills=hills)
    probe = FakeAnts(mine, camped)
    loc, d = fresh[0]
    assert probe.distance(probe.destination(loc, d), (2, 2)) < probe.distance(
        loc, (2, 2)
    )
    tired = FakeAnts(mine, camped, enemy_hills=hills)
    tired.clock = 299
    bot = RY.Rally()
    bot.do_turn(tired)
    assert tired.orders[0] == ((6, 12), "s")


def test_crowded_turn_under_one_second() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(10)]
    foods = [((i * 5 + 1) % ROWS, (i * 3 + 2) % COLS) for i in range(12)]
    start = time.perf_counter()
    orders, _ = run_turn(mine, foes, foods, my_hills=[(10, 10)], enemy_hills=[(15, 15)])
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(orders) > 0
