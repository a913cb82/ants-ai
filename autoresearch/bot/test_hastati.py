#!/usr/bin/env python
"""Hastati tests: straggler-cut targeting + predictive screen.

No engine games. Hastati seekers converge on the most isolated
visible enemy (fewest enemy neighbours in attack range of the
foe; ties go to the foe nearest any ant) instead of each chasing
its own nearest foe, so the pack cuts stragglers instead of
feeding the enemy's main stack. The pin is sticky while nothing
strictly lonelier appears, and a walled-off pin falls back to
the nearest reachable foe. Extra guards screen the razer's
predicted next square (heading extrapolation) instead of the
static midpoint, so the screen leads the target. Idle ants push
the unseen edge by BFS before diffusing over visited ground.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Hastati as HP  # noqa: E402

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

    def visible(self, loc: Loc) -> bool:
        return any(self.distance(loc, a) <= 5 for a in self._mine)

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
) -> tuple[list[tuple[Loc, str]], HP.Hastati]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = HP.Hastati()
    bot.do_turn(fake)
    return fake.orders, bot


def _sq(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


# --- straggler selection (pure) ---


def test_straggler_prefers_isolated_foe_over_near_supported_stack() -> None:
    # Near foe (5, 7) stands with two buddies; far foe (5, 12) is
    # alone. The pack must cut the loner, not feed the stack.
    mine = [(5, 5), (5, 3), (5, 4), (6, 5)]
    foes = [(5, 7), (5, 8), (6, 7), (5, 12)]
    probe = FakeAnts(mine, foes)
    assert HP.pick_straggler(foes, mine, probe.distance, _sq, probe.attackradius2) == (
        5,
        12,
    )


def test_straggler_tie_goes_to_nearest_foe() -> None:
    # Both foes unsupported: nearest to any ant wins.
    mine = [(5, 5), (5, 3), (5, 4), (6, 5)]
    foes = [(5, 12), (5, 8)]
    probe = FakeAnts(mine, foes)
    assert HP.pick_straggler(foes, mine, probe.distance, _sq, probe.attackradius2) == (
        5,
        8,
    )


def test_straggler_ignores_foes_beyond_seek_range() -> None:
    mine = [(5, 5), (5, 3), (5, 4), (6, 5)]
    foes = [(5, 14), (15, 15)]
    probe = FakeAnts(mine, foes)
    assert probe.distance((5, 5), (5, 14)) == 9
    assert (
        HP.pick_straggler(foes, mine, probe.distance, _sq, probe.attackradius2) is None
    )
    assert HP.pick_straggler([], mine, probe.distance, _sq, 5) is None


def test_straggler_counts_only_enemy_support() -> None:
    # My own ants crowded around a foe must not count as its
    # support: support is enemies within attack range of the foe.
    mine = [(5, 6), (6, 6), (4, 6), (5, 5)]
    foes = [(5, 7), (15, 15)]
    probe = FakeAnts(mine, foes)
    assert HP.pick_straggler(foes, mine, probe.distance, _sq, probe.attackradius2) == (
        5,
        7,
    )


def test_sticky_holds_equal_loner_against_nearer_rival() -> None:
    # Both loners unsupported; (5, 8) is nearer, but last turn's
    # pin on (5, 12) holds -- no flapping between equal kills.
    mine = [(5, 5), (5, 3), (5, 4), (6, 5)]
    foes = [(5, 8), (5, 12)]
    probe = FakeAnts(mine, foes)
    assert HP.pick_straggler(
        foes, mine, probe.distance, _sq, probe.attackradius2, sticky=(5, 12)
    ) == (5, 12)


def test_sticky_releases_to_strictly_lonelier_foe() -> None:
    # The pin drew a buddy (support 1); the untouched loner
    # (support 0) takes the pin.
    mine = [(5, 5), (5, 3), (5, 4), (6, 5)]
    foes = [(5, 8), (5, 9), (5, 12)]
    probe = FakeAnts(mine, foes)
    assert HP.pick_straggler(
        foes, mine, probe.distance, _sq, probe.attackradius2, sticky=(5, 8)
    ) == (5, 12)


def test_sticky_releases_when_gone_or_out_of_range() -> None:
    mine = [(5, 5), (5, 3), (5, 4), (6, 5)]
    foes = [(5, 8)]
    probe = FakeAnts(mine, foes)
    assert HP.pick_straggler(
        foes, mine, probe.distance, _sq, probe.attackradius2, sticky=(15, 15)
    ) == (5, 8)
    assert HP.pick_straggler([], mine, probe.distance, _sq, 5, sticky=(5, 8)) is None


def test_pin_persists_across_turns_then_switches() -> None:
    # Turn 1 pins the nearer loner; turn 2 it draws a buddy while
    # the far loner stays clean -- the pin switches to the clean kill.
    mine = [(10, 10), (10, 8), (10, 9), (9, 10)]
    _, bot = run_turn(mine, [(14, 10), (10, 13)])
    assert bot.pin == (10, 13)
    fake2 = FakeAnts(mine, [(14, 10), (10, 13), (10, 14)])
    bot.do_turn(fake2)
    assert bot.pin == (14, 10)


# --- heading prediction (pure) ---


def test_predict_extrapolates_one_step_along_heading() -> None:
    assert HP.predict_square((5, 7), (5, 6), ROWS, COLS) == (5, 8)
    assert HP.predict_square((5, 7), (5, 7), ROWS, COLS) == (5, 7)
    assert HP.predict_square((5, 7), None, ROWS, COLS) == (5, 7)


def test_predict_wraps_toroidally() -> None:
    assert HP.predict_square((0, 0), (1, 0), ROWS, COLS) == (ROWS - 1, 0)
    assert HP.predict_square((5, COLS - 1), (5, COLS - 2), ROWS, COLS) == (5, 0)


def test_predict_reaches_only_one_step() -> None:
    probe = FakeAnts([], [])
    got = HP.predict_square((10, 10), (8, 10), ROWS, COLS)
    assert probe.distance(got, (10, 10)) == 1


# --- bot: pack converges on the straggler ---


def test_walled_straggler_falls_back_to_nearest_foe() -> None:
    # The lonely (5, 12) pins, but a water ring seals it off: the
    # packed hunter falls back to the reachable (5, 7) stack and
    # steps east instead of idling at the wall.
    ring = {
        (4, 11),
        (4, 12),
        (4, 13),
        (5, 11),
        (5, 13),
        (6, 11),
        (6, 12),
        (6, 13),
    }
    mine = [(5, 5), (5, 3), (5, 4), (6, 5)]
    foes = [(5, 7), (5, 8), (5, 12)]
    orders, bot = run_turn(mine, foes, water=ring)
    assert bot.pin == (5, 12)
    assert orders[0] == ((5, 5), "e")


def test_pack_converges_on_straggler_not_nearest() -> None:
    # Nearest-seek would send the (10, 10) hunter east at the (10, 13)
    # stack; Hastati cuts the lone (14, 10) southerner instead. Both
    # hunters must step toward the loner.
    mine = [(10, 10), (10, 8), (10, 9), (9, 10)]
    foes = [(10, 13), (10, 14), (11, 13), (14, 10)]
    probe = FakeAnts(mine, foes)
    assert probe.distance((10, 10), (14, 10)) <= 8
    orders, _ = run_turn(mine, foes)
    assert orders[0] == ((10, 10), "s")
    moved = probe.destination((10, 10), orders[0][1])
    assert probe.distance(moved, (14, 10)) < probe.distance((10, 10), (14, 10))


def test_no_foe_in_range_explores_safely() -> None:
    mine = [(5, 5)]
    foes = [(5, 14)]
    orders, _ = run_turn(mine, foes)
    assert orders == [((5, 5), "n")]


# --- bot: no suicide steps ---


def test_packed_ant_refuses_1v2_contact() -> None:
    # Hunter (5, 5) with three pack friends eyes the step east
    # onto (5, 6) against two foes: strictly losing, so it must
    # never step east -- no fearless donation.
    mine = [(5, 5), (5, 1), (5, 2), (5, 3)]
    foes = [(5, 7), (5, 8)]
    orders, _ = run_turn(mine, foes)
    assert orders[0] != ((5, 5), "e")


def test_supported_advance_still_engages() -> None:
    # Strict superiority at the step (two friends in attack range
    # of (5, 6) vs one foe): the hunter presses east.
    mine = [(5, 5), (5, 4), (4, 6), (5, 3)]
    foes = [(5, 7)]
    orders, _ = run_turn(mine, foes)
    assert orders[0] == ((5, 5), "e")


def test_committed_pair_still_joins_on_shared_foe() -> None:
    # The flanking pair shares one foe: both engage together even
    # though each step is only an equal trade.
    mine = [(5, 5), (5, 9), (5, 1), (5, 13)]
    foes = [(5, 7)]
    orders, _ = run_turn(mine, foes)
    assert orders[0] == ((5, 5), "e")
    assert orders[1] == ((5, 9), "w")


# --- bot: predictive screen ---


def test_second_guard_leads_the_razer() -> None:
    # Hill (10, 10), razer at (10, 16) heading east (prev (10,
    # 15)): the extra guard screens east toward the intercept,
    # never west onto the held hill. (The lead itself shows in
    # the pure-aim test below: prediction shifts the intercept.)
    mine = [(10, 8), (10, 11)]
    hill = (10, 10)
    bot = HP.Hastati()
    first = FakeAnts(mine, [(10, 15)], my_hills=[hill])
    bot.do_turn(first)
    second = FakeAnts(mine, [(10, 16)], my_hills=[hill])
    bot.do_turn(second)
    assert second.orders[1] == ((10, 11), "e")
    assert second.orders[1] != ((10, 11), "w")


def test_intercept_aims_at_predicted_square() -> None:
    # Odd-distance approach: the predicted square moves the
    # intercept one step past the static midpoint, leading the
    # razer instead of meeting where it was.
    probe = FakeAnts([], [])
    static = HP.intercept_square((10, 10), (10, 15), probe.passable, ROWS, COLS)
    assert static == (10, 12)
    aim = HP.predict_square((10, 15), (10, 14), ROWS, COLS)
    assert aim == (10, 16)
    led = HP.intercept_square((10, 10), aim, probe.passable, ROWS, COLS)
    assert led == (10, 13)
    assert led != static


def test_first_guard_holds_hill() -> None:
    mine = [(10, 8)]
    orders, _ = run_turn(mine, [(10, 16)], my_hills=[(10, 10)])
    assert orders == [((10, 8), "e")]


# --- economy / regression ---


def test_food_claims_still_greedy_champion() -> None:
    mine = [(5, 5), (2, 2)]
    foods = [(5, 6), (2, 3)]
    orders, _ = run_turn(mine, [], foods)
    assert orders == [((5, 5), "e"), ((2, 2), "e")]


def test_contested_cluster_draws_two_claimants_then_guard() -> None:
    # Three enemies contest the two-food cluster: two ants take
    # denial food steps east, the third holds its threatened hill.
    mine = [(5, 5), (2, 2), (10, 10)]
    foods = [(5, 6), (2, 3)]
    enemies = [(5, 12), (2, 6), (5, 9), (10, 15)]
    orders, _ = run_turn(mine, enemies, foods, my_hills=[(10, 12)])
    assert orders == [((5, 5), "e"), ((2, 2), "e"), ((10, 10), "e")]


def test_muster_marches_remembered_hill_then_forgets_razed() -> None:
    # Turn 1: the lone ant marches on the remembered hill (each
    # step shortens the distance). Turn 2: our ant stands on it,
    # so the hill is forgotten and no muster follows.
    bot = HP.Hastati()
    fake1 = FakeAnts([(10, 10)], [], enemy_hills=[(15, 15)])
    bot.do_turn(fake1)
    assert bot.remembered_hills == {(15, 15)}
    assert len(fake1.orders) == 1
    origin, direction = fake1.orders[0]
    moved = fake1.destination(origin, direction)
    assert fake1.distance(moved, (15, 15)) < fake1.distance(origin, (15, 15))
    fake2 = FakeAnts([(15, 15)], [], enemy_hills=[(15, 15)])
    bot.do_turn(fake2)
    assert bot.remembered_hills == set()


def test_full_turn_under_1s_on_crowded_board() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(12)]
    foods = [((i * 3 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(20)]
    start = time.perf_counter()
    fake = FakeAnts(mine, foes, foods, my_hills=[(0, 0)])
    bot = HP.Hastati()
    bot.do_turn(fake)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(fake.orders) > 0


def test_straggler_scan_under_1ms() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(12)]
    probe = FakeAnts(mine, foes)
    reps = 50
    start = time.perf_counter()
    for _ in range(reps):
        HP.pick_straggler(foes, mine, probe.distance, _sq, probe.attackradius2)
    assert (time.perf_counter() - start) / reps < 0.001


# --- unseen-edge scouting ---


def _all_seen_minus(pocket: set[Loc]) -> set[Loc]:
    return {(r, c) for r in range(ROWS) for c in range(COLS)} - pocket


def test_do_setup_resets_all_memory() -> None:
    mine = [(10, 10), (10, 8), (10, 9), (9, 10)]
    _, bot = run_turn(mine, [(14, 10), (10, 13)], enemy_hills=[(0, 0)])
    assert bot.pin is not None and bot.seen and bot.visits
    bot.do_setup(FakeAnts(mine, []))
    assert bot.pin is None
    assert bot.seen == set()
    assert bot.visits == {}
    assert bot.remembered_hills == set()
    assert bot.prev_enemies == []


def test_seen_memory_marks_visible_disc() -> None:
    _, bot = run_turn([(5, 5)], [])
    assert (5, 5) in bot.seen
    assert (5, 10) in bot.seen
    assert (5, 11) not in bot.seen


def test_edge_step_finds_unseen_pocket() -> None:
    probe = FakeAnts([(5, 5)], [])
    seen = _all_seen_minus({(5, 8)})
    assert HP.edge_step((5, 5), seen, probe.passable, probe.destination) == "e"


def test_edge_step_none_when_fully_explored() -> None:
    probe = FakeAnts([(5, 5)], [])
    seen = {(r, c) for r in range(ROWS) for c in range(COLS)}
    assert HP.edge_step((5, 5), seen, probe.passable, probe.destination) is None


def test_edge_step_respects_budget() -> None:
    probe = FakeAnts([(5, 5)], [])
    seen = _all_seen_minus({(5, 8)})
    assert (
        HP.edge_step((5, 5), seen, probe.passable, probe.destination, budget=1) is None
    )


def test_edge_step_skirts_water() -> None:
    probe = FakeAnts([(5, 5)], [], water={(5, 6)})
    seen = _all_seen_minus({(5, 8)})
    assert HP.edge_step((5, 5), seen, probe.passable, probe.destination) == "n"


def test_scout_pushes_unseen_edge_over_visited_ground() -> None:
    # North blocked by water; east is over-visited (fallback would go
    # south) but the unseen edge lies east -- the scout must step east.
    water = {(4, 5)}
    bot = HP.Hastati()
    first = FakeAnts([(5, 5)], [], water=water)
    bot.do_turn(first)
    assert first.orders == [((5, 5), "e")]
    bot.visits[(5, 6)] = 50
    second = FakeAnts([(5, 5)], [], water=water)
    bot.do_turn(second)
    assert second.orders == [((5, 5), "e")]


def test_robust_small_board_and_radii() -> None:
    # 8x8 torus (seam bands overlap), tiny and huge attack radii:
    # every turn completes with legal orders.
    class Small(FakeAnts):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.rows = 8
            self.cols = 8

    mine = [(1, 1), (1, 5), (5, 1), (5, 5), (3, 3)]
    foes = [(1, 3), (6, 6)]
    foods = [(2, 2), (4, 4)]
    for radius in (1, 5, 25):
        bot = HP.Hastati()
        for _ in range(3):
            fake = Small(mine, foes, foods, my_hills=[(0, 0)])
            fake.attackradius2 = radius
            bot.do_turn(fake)
            origins = [o for o, _ in fake.orders]
            assert len(set(origins)) == len(origins)
            dests = set()
            for origin, direction in fake.orders:
                assert origin in mine
                dest = fake.destination(origin, direction)
                assert dest not in dests
                dests.add(dest)
                assert fake.passable(dest)
                assert dest not in mine
                assert dest not in foes


def test_fuzz_orders_legal_and_fast() -> None:
    # Seeded soup: five turns per board so headings/seen/memory all
    # engage. Every order must come from a live ant exactly once,
    # land on a unique passable unoccupied square, and each turn
    # must finish far inside the 1000ms budget.
    import random

    rng = random.Random(1234)
    squares = [(r, c) for r in range(ROWS) for c in range(COLS)]
    for board in range(16):
        # Even boards are open ground; odd boards are dense maze
        # (40% water) so BFS budgets exhaust and fallbacks engage.
        if board % 2:
            water = set(rng.sample(squares, rng.randint(100, 160)))
        else:
            water = set(rng.sample(squares, rng.randint(0, 30)))
        free = [s for s in squares if s not in water]
        mine = rng.sample(free, rng.randint(1, 40))
        foes = rng.sample(free, rng.randint(0, 12))
        foods = rng.sample(free, rng.randint(0, 10))
        hills = rng.sample(free, rng.randint(0, 2))
        bot = HP.Hastati()
        for _turn in range(5):
            fake = FakeAnts(mine, foes, foods, water, my_hills=hills)
            start = time.perf_counter()
            bot.do_turn(fake)
            assert time.perf_counter() - start < 1.0
            origins = [o for o, _ in fake.orders]
            assert len(set(origins)) == len(origins)
            dests = set()
            for origin, direction in fake.orders:
                assert origin in mine
                assert direction in ("n", "e", "s", "w")
                dest = fake.destination(origin, direction)
                assert dest not in dests
                dests.add(dest)
                assert fake.passable(dest)
                assert dest not in mine
                assert dest not in foes
