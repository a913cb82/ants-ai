#!/usr/bin/env python
"""Maniple tests: no attack without a majority (TDD, failing first).

Risky part: the testudo switch -- reserve ants flood a remembered
enemy hill only with a global visible majority, else they fall back
toward home (testudo) instead of marching across the map to die.
Second risk: no fearless steps -- an unsafe advance is refused even
with a big army and few enemies visible.

The fake engine mirrors the real one's move physics: steps onto
food squares are blocked ("move blocked"), gathering works by
orthogonal proximity, so the bot must hold adjacent. Every test
pins behavior under those exact rules.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Maniple as MP  # noqa: E402

ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}


class FakeAnts:
    def __init__(
        self,
        mine,
        enemies,
        foods=None,
        water=None,
        enemy_hills=None,
        my_hills=None,
        owners=None,
    ):
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = 5
        self._mine = list(mine)
        self._enemies = list(enemies)
        self._owners = list(owners) if owners else [1] * len(self._enemies)
        self._foods = list(foods or [])
        self._water = set(water or set())
        self._enemy_hills = list(enemy_hills or [])
        self._my_hills = list(my_hills or [])
        self.orders = []

    def food(self):
        return list(self._foods)

    def my_ants(self):
        return list(self._mine)

    def enemy_ants(self):
        return [(e, o) for e, o in zip(self._enemies, self._owners, strict=True)]

    def enemy_hills(self):
        return [(h, 1) for h in self._enemy_hills]

    def my_hills(self):
        return list(self._my_hills)

    def distance(self, a, b):
        dr = abs(a[0] - b[0])
        dr = min(dr, self.rows - dr)
        dc = abs(a[1] - b[1])
        dc = min(dc, self.cols - dc)
        return dr + dc

    def destination(self, loc, direction):
        dr, dc = AIM[direction]
        return ((loc[0] + dr) % self.rows, (loc[1] + dc) % self.cols)

    def passable(self, loc):
        return loc not in self._water

    def unoccupied(self, loc):
        # Engine-faithful: moves onto FOOD are ignored ("move
        # blocked"), like water. Gathering works by proximity, so
        # bots must hold adjacent, never step on.
        return (
            loc not in self._water
            and loc not in self._mine
            and loc not in self._enemies
            and loc not in self._foods
        )

    def issue_order(self, order):
        self.orders.append(order)

    def time_remaining(self):
        return 100000


def run_turn(
    mine, enemies, foods=None, water=None, enemy_hills=None, my_hills=None, owners=None
):
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills, owners)
    bot = MP.Maniple()
    bot.do_turn(fake)
    return fake.orders, bot


def test_majority_gate_pure() -> None:
    assert MP.has_majority(5, 2) is True
    assert MP.has_majority(3, 3) is False
    assert MP.has_majority(2, 5) is False
    assert MP.has_majority(1, 0) is True
    assert MP.has_majority(0, 0) is False


def test_flood_when_ahead() -> None:
    # 5v2: reserves march on the remembered hill -- every order
    # lands closer to (15, 15) than its start.
    mine = [(5, 5), (5, 6), (6, 5), (6, 6), (4, 4)]
    enemies = [(19, 19), (19, 18)]
    probe = FakeAnts(mine, enemies)
    orders, _ = run_turn(mine, enemies, enemy_hills=[(15, 15)])
    assert len(orders) == len(mine)
    for loc, d in orders:
        dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
        assert probe.distance(dest, (15, 15)) < probe.distance(loc, (15, 15))


def test_testudo_when_behind() -> None:
    # 2v5: no march on the far hill -- both ants step toward the
    # home hill (5, 5): first steps north, never toward (15, 15).
    mine = [(6, 6), (6, 7)]
    enemies = [(15, 14), (15, 16), (14, 15), (16, 15), (16, 16)]
    probe = FakeAnts(mine, enemies)
    orders, _ = run_turn(mine, enemies, enemy_hills=[(15, 15)], my_hills=[(5, 5)])
    assert orders == [((6, 6), "n"), ((6, 7), "n")]
    for loc, d in orders:
        dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
        assert probe.distance(dest, (15, 15)) > probe.distance(loc, (15, 15))


def test_even_army_testudos() -> None:
    # 3v3 is not a majority: the reserve holds home instead of
    # flooding, exactly as when behind.
    mine = [(6, 6), (6, 7), (6, 8)]
    enemies = [(15, 14), (15, 16), (14, 15)]
    probe = FakeAnts(mine, enemies)
    orders, _ = run_turn(mine, enemies, enemy_hills=[(15, 15)], my_hills=[(5, 5)])
    by_ant = dict(orders)
    assert by_ant[(6, 6)] == "n"
    for loc, d in orders:
        dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
        assert probe.distance(dest, (15, 15)) >= probe.distance(loc, (15, 15))


def test_no_fearless_step_even_with_big_army() -> None:
    # Packed hunter (5, 5) eyes (5, 6) against two foes with no
    # backup: unsafe under every gate, so it refuses east and
    # explores south -- even with 12 own ants and 3 enemies.
    mine = [
        (5, 5),
        (5, 1),
        (5, 2),
        (5, 3),
        (15, 15),
        (15, 16),
        (15, 14),
        (14, 15),
        (16, 15),
        (16, 16),
        (14, 14),
        (13, 13),
    ]
    enemies = [(5, 7), (5, 8), (0, 0)]
    orders, _ = run_turn(mine, enemies)
    assert orders[0] == ((5, 5), "s")
    assert ((5, 5), "e") not in orders


def test_joined_pair_still_engages() -> None:
    # Local majority needs no global lead: the flanking pair
    # shares one foe, so both engage though outnumbered overall.
    mine = [(5, 5), (5, 9), (0, 0), (5, 3), (5, 11)]
    enemies = [(5, 7), (0, 10), (0, 11), (0, 12), (19, 19), (19, 18)]
    orders, _ = run_turn(mine, enemies)
    assert orders[0] == ((5, 5), "e")
    assert orders[1] == ((5, 9), "w")


def test_food_claims_approach_from_range() -> None:
    # Economy sanity: closest ant takes the food and steps
    # toward it, stopping at stand-off range, one ant per food.
    mine = [(5, 5), (10, 10)]
    foods = [(5, 8), (10, 13)]
    orders, _ = run_turn(mine, [], foods)
    assert orders[0] == ((5, 5), "e")
    assert orders[1] == ((10, 10), "e")


def test_adjacent_ant_holds_instead_of_stepping_on() -> None:
    # Stand-off: one step from the meal the ant holds (the engine
    # would ignore a move onto food), so no order issues at all.
    mine = [(5, 5)]
    orders, _ = run_turn(mine, [], [(5, 6)])
    assert orders == []


def test_cede_contested_food_when_behind() -> None:
    # 2v3: the (5, 6) food sits in a hot cluster (3 foes near),
    # so no denial claim fires -- (5, 5) never steps east into
    # the teeth, while (0, 0) holds adjacent to safe food (0, 1)
    # and issues nothing.
    mine = [(5, 5), (0, 0)]
    foods = [(5, 6), (0, 1)]
    enemies = [(5, 12), (5, 9), (6, 9)]
    orders, _ = run_turn(mine, enemies, foods)
    assert orders == [((5, 5), "n")]


def test_contest_food_when_ahead() -> None:
    # Same cluster, but 6v3: the denial claim fires and (5, 5)
    # approaches east toward (5, 7) exactly as the economy
    # demands, while (0, 0) holds on safe food (0, 1).
    mine = [(5, 5), (0, 0), (19, 19), (19, 18), (18, 19), (18, 18)]
    foods = [(5, 7), (0, 1)]
    enemies = [(5, 12), (5, 9), (6, 9)]
    orders, _ = run_turn(mine, enemies, foods)
    assert ((5, 5), "e") in orders
    assert ((0, 0), "e") not in orders


def test_post_holder_stays_adjacent() -> None:
    # Threatened hill (5, 5), ant already adjacent at (5, 6):
    # it stands its post -- no order, hill stays spawnable.
    mine = [(5, 6)]
    enemies = [(5, 12)]
    orders, _ = run_turn(mine, enemies, my_hills=[(5, 5)])
    assert orders == []


def test_post_ring_forms_instead_of_pile() -> None:
    # Two adjacent ants both stand; neither piles onto the hill.
    mine = [(5, 6), (4, 5)]
    enemies = [(5, 12)]
    orders, _ = run_turn(mine, enemies, my_hills=[(5, 5)])
    assert orders == []


def test_far_guard_still_approaches() -> None:
    # Three steps out, the guard still marches west onto the post.
    mine = [(5, 8)]
    enemies = [(5, 12)]
    orders, _ = run_turn(mine, enemies, my_hills=[(5, 5)])
    assert orders == [((5, 8), "w")]


def test_skips_defended_hill_for_empty() -> None:
    # 7v6 ahead. Near hill A=(10, 10) camps all 6 foes: 7 < 12,
    # no assault. Far empty hill B=(1, 1) still draws the march:
    # identical orders to a board where only B is remembered,
    # every step nearer B.
    mine = [(5, 5), (10, 2), (2, 10), (12, 7), (7, 12), (0, 9), (0, 0)]
    foes = [(14, 14), (14, 15), (15, 14), (15, 15), (16, 14), (16, 15)]
    probe = FakeAnts(mine, foes)
    for ant in mine:
        assert min(probe.distance(ant, e) for e in foes) > 8
    both, _ = run_turn(mine, foes, enemy_hills=[(10, 10), (1, 1)])
    only_b, _ = run_turn(mine, foes, enemy_hills=[(1, 1)])
    assert both == only_b
    assert len(both) == len(mine)
    for loc, d in both:
        dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
        assert probe.distance(dest, (1, 1)) < probe.distance(loc, (1, 1))


def test_closing_memory_spots_razer_early() -> None:
    # Same bot, two turns. Turn 1 the foe lurks at 16 steps:
    # no guard, plain explore south. Turn 2 it closes to 15:
    # the heading memory reads the approach and the guard
    # marches west onto the post.
    bot = MP.Maniple()
    f1 = FakeAnts([(10, 12)], [(2, 2)], my_hills=[(10, 10)])
    bot.do_turn(f1)
    assert f1.orders == [((10, 12), "s")]
    f2 = FakeAnts([(10, 12)], [(2, 3)], my_hills=[(10, 10)])
    bot.do_turn(f2)
    assert f2.orders == [((10, 12), "w")]


def test_remembered_hill_draws_muster_next_turn() -> None:
    # Turn 1 sees the hill; turn 2 it is out of sight, yet the
    # reserve still marches it: identical orders, every step
    # closer to the remembered hill.
    bot = MP.Maniple()
    mine = [(5, 5), (5, 6)]
    probe = FakeAnts(mine, [])
    f1 = FakeAnts(mine, [], enemy_hills=[(15, 15)])
    bot.do_turn(f1)
    f2 = FakeAnts(mine, [])
    bot.do_turn(f2)
    assert f2.orders == f1.orders
    assert len(f2.orders) == len(mine)
    for loc, d in f2.orders:
        dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
        assert probe.distance(dest, (15, 15)) < probe.distance(loc, (15, 15))


def test_explore_fans_out_per_ant() -> None:
    # No food, foes, or hills: simultaneous explorers take
    # different headings from their per-ant rotation -- (5, 5)
    # south, (5, 6) north -- instead of queueing north together.
    orders, _ = run_turn([(5, 5), (5, 6)], [])
    assert orders == [((5, 5), "s"), ((5, 6), "n")]


def test_water_wall_routes_through_gap() -> None:
    # A full-height water wall with one gap: the forager must
    # walk around through (10, 6) and hold adjacent to the meal,
    # never entering water, within 15 turns.
    water = {(r, 6) for r in range(ROWS) if r != 10}
    bot = MP.Maniple()
    ant = (5, 5)
    meal = (5, 8)
    for _ in range(15):
        fake = FakeAnts([ant], [], [meal], water)
        bot.do_turn(fake)
        assert len(fake.orders) <= 1
        for loc, d in fake.orders:
            assert loc == ant
            ant = ((ant[0] + AIM[d][0]) % ROWS, (ant[1] + AIM[d][1]) % COLS)
            assert ant not in water
    probe = FakeAnts([ant], [], [])
    assert probe.distance(ant, meal) <= 1


def test_opening_ant_forages() -> None:
    # Turn-one single ant: food two steps out draws an approach,
    # and the ant never ends on the food square itself.
    mine = [(5, 5)]
    orders, _ = run_turn(mine, [], [(5, 7)], my_hills=[(5, 5)])
    assert len(orders) == 1
    loc, d = orders[0]
    dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
    assert dest != (5, 7)
    probe = FakeAnts(mine, [], [])
    assert probe.distance(dest, (5, 7)) < probe.distance(loc, (5, 7))


def test_fuzz_orders_legal_and_fast() -> None:
    import random

    rng = random.Random(20261008)
    start = time.perf_counter()
    for _ in range(40):
        mine = list({(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(30)})
        foes = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(8)]
        owners = [rng.randrange(4) for _ in foes]
        foods = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(20)]
        water = {(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(10)}
        mine = [m for m in mine if m not in water]
        fake = FakeAnts(
            mine,
            foes,
            foods,
            water,
            enemy_hills=[(15, 15)],
            my_hills=[(0, 0)],
            owners=owners,
        )
        bot = MP.Maniple()
        bot.do_turn(fake)
        seen_locs: set = set()
        seen_ants: set = set()
        for loc, d in fake.orders:
            assert loc in mine and loc not in seen_ants
            seen_ants.add(loc)
            dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
            assert dest not in seen_locs
            seen_locs.add(dest)
            assert fake.passable(dest)
            assert fake.unoccupied(dest)
    assert time.perf_counter() - start < 3.0


def test_assault_margin_denied_equals_forgotten() -> None:
    # 5v3 globally ahead, but all 3 foes camp the muster hill:
    # 5 < 2*3, so no assault marches -- the turn plays exactly
    # as if the hill were forgotten (explore), never toward it.
    mine = [(5, 5), (10, 2), (2, 10), (12, 7), (7, 12)]
    foes = [(14, 15), (16, 15), (15, 14)]
    denied, _ = run_turn(mine, foes, enemy_hills=[(15, 15)])
    blank, _ = run_turn(mine, foes)
    assert denied == blank
    for loc, d in denied:
        dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
        assert dest != (15, 15)


def test_assault_margin_attacks_at_two_to_one() -> None:
    # Same camp, but 8v3: 8 >= 2*3, so the reserve floods --
    # every order lands closer to the hill than its start.
    mine = [(5, 5), (10, 2), (2, 10), (12, 7), (7, 12), (3, 3), (8, 8), (0, 5)]
    foes = [(14, 15), (16, 15), (15, 14)]
    probe = FakeAnts(mine, foes)
    for ant in mine:
        assert probe.distance(ant, (14, 15)) > 8
    orders, _ = run_turn(mine, foes, enemy_hills=[(15, 15)])
    assert len(orders) == len(mine)
    for loc, d in orders:
        dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
        assert probe.distance(dest, (15, 15)) < probe.distance(loc, (15, 15))


def test_strongest_rival_pure() -> None:
    assert MP.strongest_rival([]) == 0
    assert MP.strongest_rival([((0, 0), 0)]) == 1
    ants = [((0, 0), 0), ((1, 1), 1), ((2, 2), 0), ((3, 3), 1), ((4, 4), 2)]
    assert MP.strongest_rival(ants) == 2


def test_majority_counts_strongest_rival_not_sum() -> None:
    # 3v(2+2): outnumbered by the sum, ahead of every rival.
    # The hot (5, 8) food still draws its denial claim, and
    # (5, 6) approaches east to stand-off range.
    mine = [(5, 5), (5, 6), (6, 5)]
    foods = [(5, 8)]
    foes = [(5, 12), (5, 9), (2, 6), (6, 9)]
    owners = [0, 0, 1, 1]
    orders, _ = run_turn(mine, foes, foods, owners=owners)
    assert ((5, 6), "e") in orders


def test_soak_thirty_turns_mixed_board() -> None:
    # Thirty turns against drifting foes with hills blinking in
    # and out of sight: every turn stays legal (engine rule:
    # passable, and unoccupied-or-vacated) and fast overall.
    bot = MP.Maniple()
    mine = [(5, 5), (5, 6), (6, 5)]
    foods = [(5, 8), (2, 2), (15, 15)]
    foes = [(5, 12), (14, 14)]
    start = time.perf_counter()
    for t in range(30):
        hills = [(15, 15)] if t % 3 else []
        fake = FakeAnts(mine, foes, foods, enemy_hills=hills, my_hills=[(0, 0)])
        bot.do_turn(fake)
        starts = set(mine)
        seen_locs: set = set()
        moves: dict = {}
        for loc, d in fake.orders:
            dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
            assert dest not in seen_locs
            seen_locs.add(dest)
            assert fake.passable(dest)
            assert fake.unoccupied(dest) or dest in starts
            moves[loc] = dest
        mine = [moves.get(m, m) for m in mine]
        foes = [((f[0] + 1) % ROWS, f[1]) for f in foes]
    assert time.perf_counter() - start < 1.0


def test_same_board_same_orders() -> None:
    # Deterministic: two fresh bots issue identical orders.
    mine = [(5, 5), (5, 6), (6, 5)]
    foes = [(5, 12), (14, 14)]
    foods = [(5, 8), (2, 2)]
    first, _ = run_turn(mine, foes, foods, enemy_hills=[(15, 15)], my_hills=[(0, 0)])
    second, _ = run_turn(mine, foes, foods, enemy_hills=[(15, 15)], my_hills=[(0, 0)])
    assert first == second


def test_setup_resets_memory() -> None:
    # A reused bot starts the next game clean: post-setup
    # orders match a fresh bot exactly.
    bot = MP.Maniple()
    mine = [(5, 5)]
    f1 = FakeAnts(mine, [(5, 12)], [(5, 8)], enemy_hills=[(15, 15)], my_hills=[(0, 0)])
    bot.do_turn(f1)
    bot.do_setup(FakeAnts(mine, [], []))
    f2 = FakeAnts(mine, [(5, 12)], [(5, 8)], enemy_hills=[(15, 15)], my_hills=[(0, 0)])
    bot.do_turn(f2)
    fresh, _ = run_turn(
        mine, [(5, 12)], [(5, 8)], enemy_hills=[(15, 15)], my_hills=[(0, 0)]
    )
    assert f2.orders == fresh


def test_winning_posture_marches_safe() -> None:
    # Two home hills to one remembered hill: ahead 3v2, but the
    # muster exit (4, 5) faces two foes with no backup. The march
    # must refuse the step -- no posture marches suicidally.
    mine = [(5, 5), (0, 0), (0, 1)]
    foes = [(4, 6), (4, 7)]
    orders, _ = run_turn(
        mine, foes, enemy_hills=[(15, 15)], my_hills=[(19, 19), (19, 18)]
    )
    assert ((5, 5), "n") not in orders


def test_arriving_clears_remembered_hill() -> None:
    # The reserve walks onto the remembered hill over two turns;
    # standing on it clears the memory, so turn 3 explores.
    bot = MP.Maniple()
    ant = (14, 14)
    for _ in range(2):
        fake = FakeAnts([ant], [], enemy_hills=[(15, 15)])
        bot.do_turn(fake)
        assert len(fake.orders) == 1
        loc, d = fake.orders[0]
        ant = ((ant[0] + AIM[d][0]) % ROWS, (ant[1] + AIM[d][1]) % COLS)
    assert ant == (15, 15)
    assert bot.hills == {(15, 15)}
    third = FakeAnts([ant], [])
    bot.do_turn(third)
    assert bot.hills == set()


def test_foraging_loop_eats_over_turns() -> None:
    # The economy loop end to end: approach, hold adjacent, the
    # driver gathers orthogonally-adjacent food like the engine,
    # claims recompute, and at least two foods are eaten in 12.
    bot = MP.Maniple()
    mine = [(5, 5), (5, 6), (6, 5)]
    foods = [(5, 8), (8, 5), (10, 10), (2, 2)]
    eaten = 0
    for _ in range(12):
        fake = FakeAnts(mine, [], foods)
        bot.do_turn(fake)
        moves: dict = {}
        for loc, d in fake.orders:
            dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
            assert dest not in foods
            moves[loc] = dest
        mine = [moves.get(m, m) for m in mine]
        left = []
        for f in foods:
            gathered = any((a[0] - f[0]) ** 2 + (a[1] - f[1]) ** 2 == 1 for a in mine)
            if gathered:
                eaten += 1
            else:
                left.append(f)
        foods = left
    assert eaten >= 2


def test_surrounded_ant_holds_legally() -> None:
    # Eight foes around one ant: every neighboring square is
    # enemy-held, so no order issues -- the ant holds in place.
    mine = [(5, 5)]
    foes = [(4, 5), (6, 5), (5, 4), (5, 6), (4, 4), (4, 6), (6, 4), (6, 6)]
    orders, _ = run_turn(mine, foes)
    assert orders == []


def test_unsafe_holder_abandons_bait_food() -> None:
    # Packed (5, 5) holds adjacent to hot food with two foes
    # glaring: staying is unsafe, so it retreats south instead
    # of sitting still, and nobody steps onto the food.
    mine = [(5, 5), (5, 1), (5, 2), (5, 3)]
    foods = [(5, 6)]
    foes = [(5, 7), (5, 8), (4, 7)]
    orders, _ = run_turn(mine, foes, foods)
    assert orders[0] == ((5, 5), "s")
    for loc, d in orders:
        dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
        assert dest not in foods


def test_far_testudo_forages_instead() -> None:
    # 30x30 board, behind with home 24 steps out: no cross-map
    # trek -- the turn plays exactly as with no hills at all.
    mine = [(12, 12)]
    foes = [(5, 5), (5, 6), (6, 5), (6, 6), (7, 7)]

    def big(mine, foes, hills=None, home=None):
        fake = FakeAnts(mine, foes, enemy_hills=hills or [], my_hills=home or [])
        fake.rows = fake.cols = 30
        bot = MP.Maniple()
        bot.do_turn(fake)
        return fake.orders

    far = big(mine, foes, [(28, 28)], [(20, 25)])
    blank = big(mine, foes)
    assert far == blank == [((12, 12), "n")]


def test_no_ants_no_orders_no_crash() -> None:
    orders, _ = run_turn(
        [], [(0, 0)], [(1, 1)], enemy_hills=[(2, 2)], my_hills=[(3, 3)]
    )
    assert orders == []


def test_ahead_lone_duel_engages() -> None:
    # Packed but friendless at the contact square, 4v1 visible:
    # the duel engages east where retreat would go west.
    mine = [(5, 5), (5, 0), (5, 1), (5, 2)]
    orders, _ = run_turn(mine, [(5, 7)])
    assert orders[0] == ((5, 5), "e")


def test_even_lone_duel_retreats() -> None:
    # Same contact at 1v1 even: no duel, the ant retreats west.
    orders, _ = run_turn([(5, 5)], [(5, 7)])
    assert orders == [((5, 5), "w")]


def test_second_guard_screens_halfway() -> None:
    # First guard anchors toward the hill, the extra screens the
    # razer at the (10, 13) halfway square instead of piling on.
    mine = [(10, 8), (10, 14)]
    orders, _ = run_turn(mine, [(10, 16)], my_hills=[(10, 10)])
    assert orders == [((10, 8), "e"), ((10, 14), "w")]


def test_hill_trap_holds_legally() -> None:
    # Ant on its hill boxed in by water: nothing issues, no
    # crash, the ant simply holds its (blocked) hill.
    mine = [(5, 5)]
    water = {(4, 5), (6, 5), (5, 4), (5, 6)}
    orders, _ = run_turn(mine, [], water=water, my_hills=[(5, 5)])
    assert orders == []


def test_sealed_food_falls_back_to_explore() -> None:
    # The meal sits inside a water moat: approach finds nothing,
    # so the ant explores instead of freezing -- legally.
    water = {(4, 6), (4, 7), (4, 8), (5, 8), (6, 8), (6, 7), (6, 6), (5, 6)}
    orders, _ = run_turn([(5, 5)], [], [(5, 7)], water)
    assert len(orders) == 1
    loc, d = orders[0]
    dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
    assert dest not in water


def test_denied_assault_testudos_home() -> None:
    # Denied assault with home in reach: every reserve steps one
    # nearer home, none nearer the defended hill.
    mine = [(5, 5), (10, 2), (2, 10), (12, 7), (7, 12)]
    foes = [(14, 15), (16, 15), (15, 14)]
    orders, _ = run_turn(mine, foes, enemy_hills=[(15, 15)], my_hills=[(0, 0)])
    probe = FakeAnts(mine, foes)
    assert len(orders) == len(mine)
    for loc, d in orders:
        dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
        assert probe.distance(dest, (0, 0)) < probe.distance(loc, (0, 0))


def test_parity_contests_hot_food() -> None:
    # 3v3 is not behind: the hot (5, 6) food draws its claim and
    # (5, 5) holds on it silently instead of packing up away.
    mine = [(5, 5), (0, 0), (0, 1)]
    foods = [(5, 6)]
    foes = [(5, 12), (5, 9), (6, 9)]
    orders, _ = run_turn(mine, foes, foods)
    assert all(loc != (5, 5) for loc, _ in orders)


def test_even_empty_hill_raids() -> None:
    # 3v3 with an empty muster hill: no defenders, so the raid
    # marches -- every order lands closer to (15, 15).
    mine = [(5, 15), (10, 5), (15, 5)]
    foes = [(12, 12), (12, 13), (13, 12)]
    probe = FakeAnts(mine, foes)
    for ant in mine:
        assert min(probe.distance(ant, e) for e in foes) > 8
    orders, _ = run_turn(mine, foes, enemy_hills=[(0, 0)])
    blank, _ = run_turn(mine, foes)
    assert orders != blank
    assert len(orders) == len(mine)
    for loc, d in orders:
        dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
        assert probe.distance(dest, (0, 0)) < probe.distance(loc, (0, 0))


def test_full_turn_under_half_second_crowded() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(10)]
    foods = [((i * 3 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(30)]
    start = time.perf_counter()
    run_turn(mine, foes, foods, enemy_hills=[(15, 15)], my_hills=[(0, 0)])
    assert time.perf_counter() - start < 0.5
