#!/usr/bin/env python
"""Softmax10 tests: threat-taxed harvest plus hill-ward explore (TDD).

Softmax10 keeps the proven Denial economy and the pack/join/grinder
combat chain, and adds two mechanisms no repo bot has:
(a) threat-taxed harvest: every visible enemy within THREAT_R of a
    food adds THREAT_TAX to that food's greedy distance, so a lone
    lurker (1-2 foes, below Denial's 3-foe hard gate) reroutes
    harvest to safer food instead of donating into ambush;
(b) hill-ward explore: the least-visited fallback tiebreaks toward
    the nearest remembered enemy hill, so idle ants drift toward
    future razes instead of wandering uniformly.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Softmax10 as SM10  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
R2 = 5


class FakeAnts:
    """Minimal ants.Ants surface used by Softmax10.do_turn."""

    def __init__(
        self,
        mine: list[Loc],
        enemies: list[Loc],
        foods: list[Loc] | None = None,
        water: set[Loc] | None = None,
        enemy_hills: list[Loc] | None = None,
        my_hills: list[Loc] | None = None,
    ) -> None:
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = R2
        self._mine = list(mine)
        self._enemies = list(enemies)
        self._foods = list(foods or [])
        self._water = set(water or set())
        self._enemy_hills = list(enemy_hills or [])
        self._my_hills = list(my_hills or [])
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


def run_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> FakeAnts:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = SM10.Softmax10()
    bot.do_turn(fake)
    return fake


def _dist(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


def test_threat_constants_positive() -> None:
    assert SM10.THREAT_R > 0
    assert SM10.THREAT_TAX > 0


def test_threat_count_zero_when_no_foes() -> None:
    assert SM10.threat_count((5, 5), [], _dist) == 0


def test_threat_count_counts_foes_in_radius() -> None:
    foes = [(5, 6), (5, 12), (15, 15)]
    assert SM10.threat_count((5, 5), foes, _dist) == 2


def test_taxed_distance_adds_per_foe() -> None:
    foes = [(5, 6), (5, 7)]
    base = _dist((0, 0), (5, 5))
    assert SM10.taxed_distance((0, 0), (5, 5), foes, _dist) == (
        base + 2 * SM10.THREAT_TAX
    )
    assert SM10.taxed_distance((0, 0), (15, 15), foes, _dist) == _dist((0, 0), (15, 15))


def test_lurker_reroutes_harvest_to_safe_food() -> None:
    # One ant centered between two foods; a lone lurker sits on the
    # east food (below Denial's 3-foe hard gate, so only the tax can
    # save the ant). The ant must claim the safe west food.
    mine = [(10, 10)]
    west = (10, 5)
    east = (10, 15)
    lurker = [(10, 15)]
    target = SM10.assign_food_targets(mine, [west, east], lurker, _dist, ROWS, COLS)
    assert target == {0: west}


def test_no_tax_without_enemies_matches_greedy() -> None:
    mine = [(10, 10), (0, 0)]
    foods = [(10, 11), (0, 1)]
    target = SM10.assign_food_targets(mine, foods, [], _dist, ROWS, COLS)
    assert target == {0: (10, 11), 1: (0, 1)}


def test_denial_cluster_still_draws_two_claims() -> None:
    # Three foes contest a two-food cluster: exactly two taxed
    # claims land on it, the rest of the army harvests elsewhere.
    mine = [(0, 0), (0, 1), (19, 19)]
    cluster = [(10, 10), (10, 11)]
    far = (0, 19)
    foes = [(10, 9), (9, 10), (11, 10)]
    target = SM10.assign_food_targets(mine, cluster + [far], foes, _dist, ROWS, COLS)
    assert target == {2: (10, 11), 1: (10, 10), 0: (0, 19)}


def test_explore_order_prefers_unvisited() -> None:
    order = SM10.explore_order((10, 10), {(9, 10): 5}, set(), _dist)
    assert order[0] == "e"


def test_explore_order_tiebreaks_toward_hill() -> None:
    # All four steps equally visited: the step toward the
    # remembered hill must come first.
    order = SM10.explore_order((10, 10), {}, {(10, 14)}, _dist)
    assert order[0] == "e"


def test_explore_order_no_hill_keeps_compass() -> None:
    order = SM10.explore_order((10, 10), {}, set(), _dist)
    assert order == ["n", "e", "s", "w"]


def test_idle_ant_drifts_hillward_without_food_or_foes() -> None:
    # No food, no foes, one remembered hill east: the ant explores
    # east toward it instead of north.
    bot = SM10.Softmax10()
    bot.remembered_hills = {(10, 14)}
    fake = FakeAnts([(10, 10)], [])
    bot.do_turn(fake)
    assert fake.orders == [((10, 10), "e")]


def test_pack_gate_holds_loner_and_releases_pack() -> None:
    assert SM10.has_pack((5, 5), [(5, 5)], _dist) is False
    pack = [(5, 5), (5, 6), (6, 5), (4, 5)]
    assert SM10.has_pack((5, 5), pack, _dist) is True


def test_join_needs_two_commitments() -> None:
    assert SM10.joined_attackers({0: (3, 3)}) == set()
    assert SM10.joined_attackers({0: (3, 3), 1: (3, 3)}) == {0, 1}


def test_grinder_only_friendless_duel_while_ahead() -> None:
    assert SM10.grinder_release(0, 1, 5, 3) is True
    assert SM10.grinder_release(0, 1, 3, 5) is False
    assert SM10.grinder_release(1, 1, 5, 3) is False
    assert SM10.grinder_release(0, 2, 5, 3) is False


def test_crowd_fearless_below_limit_only() -> None:
    assert SM10.crowd_fearless(SM10.CROWD_LIMIT - 1) is True
    assert SM10.crowd_fearless(SM10.CROWD_LIMIT) is False


def test_packed_hunter_presses_small_fight() -> None:
    # Four packed ants near one foe, few enemies visible: the pack
    # must advance (fearless), not sit.
    mine = [(5, 5), (5, 6), (6, 5), (6, 6)]
    fake = run_turn(mine, [(5, 9)])
    assert len(fake.orders) == len(mine)


def test_lone_hunter_packs_up_instead_of_dueling() -> None:
    # One ant 6 from a foe with no friends: it must step toward
    # safety/pack, never into contact range of the foe.
    mine = [(5, 5), (15, 15), (15, 16), (16, 15)]
    foes = [(5, 11)]
    fake = run_turn(mine, foes)
    first = [o for o in fake.orders if o[0] == (5, 5)]
    assert first, "lone hunter issued no order"
    dest = FakeAnts(mine, foes).destination((5, 5), first[0][1])
    assert _dist(dest, (5, 11)) > 2


def test_guard_holds_threatened_hill() -> None:
    fake = run_turn([(5, 6)], [(5, 12)], my_hills=[(5, 5)])
    assert fake.orders, "guard issued no order"


def test_first_guard_anchors_second_screens() -> None:
    # One threatened hill, two free ants: the first steps onto the
    # hill, the second screens at the halfway square, never piling
    # on where it blocks spawning.
    fake = run_turn([(10, 12), (10, 8)], [(10, 16)], my_hills=[(10, 10)])
    assert fake.orders == [((10, 12), "w"), ((10, 8), "e")]


def test_joined_pair_engages_together_in_crowds() -> None:
    # Ten visible foes switch off the fearless press; the pair
    # whose steps contact the same foe still engages jointly.
    mine = [(5, 6), (6, 7)]
    near = [(5, 9)]
    far = [(15, 15 + i) for i in range(9)]
    fake = run_turn(mine, near + far)
    assert ((5, 6), "e") in fake.orders
    assert len(fake.orders) == len(mine)


def test_screen_midpoint_truncates_toward_zero() -> None:
    # Negative-odd approach (hill (10,10), foe (7,9): dr=-3, dc=-1)
    # truncates toward zero to (9,10), never floors to (8,10).
    mid = SM10._midpoint_screen((10, 10), [(7, 9)], _dist, lambda loc: True, ROWS, COLS)
    assert mid == (9, 10)


def test_walk_off_home_hill() -> None:
    fake = run_turn([(5, 5)], [], my_hills=[(5, 5)])
    assert fake.orders, "sitter never stepped off"
    assert fake.orders[0][0] == (5, 5)


def test_full_turn_under_1s_crowded() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [(3, 3), (17, 17), (10, 2)]
    start = time.perf_counter()
    fake = run_turn(mine, foes, foods, enemy_hills=[(15, 15)], my_hills=[(10, 10)])
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(fake.orders) > 0


def test_water_maze_still_feeds_and_moves() -> None:
    # Vertical water wall with one gap: food behind the wall must
    # still draw the ant through the gap via BFS first steps.
    water = {(r, 10) for r in range(ROWS)} - {(10, 10)}
    fake = run_turn([(10, 5)], [], foods=[(10, 15)], water=water)
    assert fake.orders, "ant stuck before water wall"
    assert fake.orders[0][1] == "e"


def test_remembered_hill_clears_when_razed() -> None:
    bot = SM10.Softmax10()
    first = FakeAnts([(0, 0)], [], enemy_hills=[(5, 5)])
    bot.do_turn(first)
    assert (5, 5) in bot.remembered_hills
    # Ant stands on the hill: memory clears even without vision.
    second = FakeAnts([(5, 5)], [])
    bot.do_turn(second)
    assert (5, 5) not in bot.remembered_hills


def test_seam_neighbors_cluster_together() -> None:
    # Foods on opposite map edges are one step apart toroidally
    # and must share a denial cluster, not split in two.
    groups = SM10.denied_food_groups(
        [(0, 5), (ROWS - 1, 5)], [(0, 4), (0, 6), (ROWS - 1, 5)], _dist, ROWS, COLS
    )
    assert len(groups) == 1
    assert sorted(groups[0]) == [0, 1]


def test_press_refuses_two_for_one_donation() -> None:
    # Packed hunter (friends within PACK_RADIUS but out of attack
    # range) facing two foes: the fearless step would land in
    # 2-foe contact with no backup, so the press must not issue.
    mine = [(5, 6), (5, 0), (6, 0), (4, 0)]
    fake = run_turn(mine, [(5, 8), (5, 9)])
    assert ((5, 6), "e") not in fake.orders


def test_press_still_takes_single_contact() -> None:
    # Same pack against one foe: the fearless 1v1 press goes ahead.
    mine = [(5, 6), (5, 0), (6, 0), (4, 0)]
    fake = run_turn(mine, [(5, 8)])
    assert ((5, 6), "e") in fake.orders


def test_large_army_turn_stays_fast() -> None:
    import random

    rng = random.Random(7)
    free = [(r, c) for r in range(ROWS) for c in range(COLS)]
    mine = rng.sample(free, 150)
    foes = rng.sample([sq for sq in free if sq not in mine], 100)
    foods = rng.sample([sq for sq in free if sq not in mine and sq not in foes], 40)
    start = time.perf_counter()
    fake = run_turn(mine, foes, foods, enemy_hills=[(15, 15)])
    assert (time.perf_counter() - start) < 1.0
    assert len(fake.orders) > 0


def test_maze_scale_turn_stays_fast() -> None:
    import random

    class BigFake(FakeAnts):
        def __init__(self, mine, enemies, foods=None, water=None):
            super().__init__(mine, enemies, foods, water)
            self.rows = 60
            self.cols = 60

    rng = random.Random(11)
    water = {(r, 30) for r in range(60) if r % 4} | {
        (30, c) for c in range(60) if c % 4
    }
    free = [(r, c) for r in range(60) for c in range(60) if (r, c) not in water]
    mine = rng.sample(free, 100)
    foes = rng.sample([s for s in free if s not in mine], 60)
    foods = rng.sample([s for s in free if s not in mine and s not in foes], 25)
    bot = SM10.Softmax10()
    start = time.perf_counter()
    fake = BigFake(mine, foes, foods, water)
    bot.do_turn(fake)
    assert (time.perf_counter() - start) < 1.0
    assert len(fake.orders) > 0


def test_fuzz_random_maps_never_crash() -> None:
    import random

    rng = random.Random(20260613)
    for _trial in range(10):
        water = {(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(30)}
        free = [(r, c) for r in range(ROWS) for c in range(COLS) if (r, c) not in water]
        mine = rng.sample(free, 12)
        foes = rng.sample([sq for sq in free if sq not in mine], 8)
        foods = rng.sample([sq for sq in free if sq not in mine and sq not in foes], 6)
        hills = rng.sample(free, 2)
        bot = SM10.Softmax10()
        start = time.perf_counter()
        for _ in range(5):
            fake = FakeAnts(mine, foes, foods, water, hills[:1], hills[1:])
            bot.do_turn(fake)
            for loc, _ in fake.orders:
                assert loc in mine
            move_of = dict(fake.orders)
            mine = [
                fake.destination(loc, move_of[loc]) if loc in move_of else loc
                for loc in mine
            ]
            assert (time.perf_counter() - start) < 5.0
