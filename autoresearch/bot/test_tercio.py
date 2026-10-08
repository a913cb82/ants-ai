#!/usr/bin/env python
"""Tests for the Tercio bot: assault in company.

TDD: these fail until Tercio.py exists with the company mechanism.
A stub Ants world (torus, water, no engine) drives do_turn.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Tercio import Tercio, assign_food_targets, company_hills


class StubAnts:
    """Minimal torus world mirroring the ants.Ants API used by Tercio."""

    def __init__(self, rows=20, cols=20, water=()):
        self.rows = rows
        self.cols = cols
        self.water = set(water)
        self.my_ants_list = []
        self.enemy_list = []  # [(loc, owner)]
        self.foods = []
        self.my_hills_list = []
        self.enemy_hills_list = []  # [(loc, owner)]
        self.attackradius2 = 5
        self.orders = []  # [((r, c), dir)]

    # world builders
    def set_my_ants(self, ants):
        self.my_ants_list = list(ants)

    def set_enemies(self, foes, owner=1):
        self.enemy_list = [(f, owner) for f in foes]

    def set_food(self, foods):
        self.foods = list(foods)

    def set_my_hills(self, hills):
        self.my_hills_list = list(hills)

    def set_enemy_hills(self, hills, owner=1):
        self.enemy_hills_list = [(h, owner) for h in hills]

    # ants.Ants API
    def my_ants(self):
        return self.my_ants_list[:]

    def enemy_ants(self):
        return self.enemy_list[:]

    def food(self):
        return self.foods[:]

    def my_hills(self):
        return self.my_hills_list[:]

    def enemy_hills(self):
        return self.enemy_hills_list[:]

    def passable(self, loc):
        return loc not in self.water

    def unoccupied(self, loc):
        # mirrors ants.Ants: food squares read as occupied (gather by
        # proximity; never step onto the meal).
        mine = set(self.my_ants_list)
        theirs = {loc for loc, _ in self.enemy_list}
        return loc not in mine and loc not in theirs and loc not in self.foods

    def destination(self, loc, direction):
        r, c = loc
        dr, dc = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}[direction]
        return ((r + dr) % self.rows, (c + dc) % self.cols)

    def distance(self, a, b):
        dr = abs(a[0] - b[0])
        dr = min(dr, self.rows - dr)
        dc = abs(a[1] - b[1])
        dc = min(dc, self.cols - dc)
        return dr + dc

    def direction(self, a, b):
        d = []
        h2 = self.rows // 2
        w2 = self.cols // 2
        if a[0] < b[0]:
            if b[0] - a[0] >= h2:
                d.append("n")
            if b[0] - a[0] <= h2:
                d.append("s")
        if b[0] < a[0]:
            if a[0] - b[0] >= h2:
                d.append("s")
            if a[0] - b[0] <= h2:
                d.append("n")
        if a[1] < b[1]:
            if b[1] - a[1] >= w2:
                d.append("w")
            if b[1] - a[1] <= w2:
                d.append("e")
        if b[1] < a[1]:
            if a[1] - b[1] >= w2:
                d.append("e")
            if a[1] - b[1] <= w2:
                d.append("w")
        return d

    def time_remaining(self):
        return 1000

    def issue_order(self, order):
        self.orders.append(order)

    def visible(self, loc):
        return True


def run_bot(ants):
    bot = Tercio()
    bot.do_setup(ants)
    bot.do_turn(ants)
    return ants.orders


def test_manifest_matches_entry():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "Tercio.bot")) as f:
        content = f.read()
    assert content == "python Tercio.py\n", repr(content)


def test_company_pair_marches_hill():
    # Two ants voting the same hill: both step toward it.
    ants = StubAnts()
    ants.set_my_ants([(5, 5), (5, 7)])
    ants.set_enemy_hills([(5, 15)])
    orders = run_bot(ants)
    assert len(orders) == 2, orders
    # both orders must reduce distance to the hill
    for loc, d in orders:
        assert loc in [(5, 5), (5, 7)]
        nxt = ants.destination(loc, d)
        assert ants.distance(nxt, (5, 15)) < ants.distance(loc, (5, 15)), orders


def test_company_solo_ant_harvests_not_raids():
    # One ant, one far hill, one near food: the ant harvests, never raids solo.
    ants = StubAnts()
    ants.set_my_ants([(5, 5)])
    ants.set_food([(5, 8)])
    ants.set_enemy_hills([(15, 5)])
    orders = run_bot(ants)
    assert len(orders) == 1, orders
    (loc, d) = orders[0]
    nxt = ants.destination(loc, d)
    assert ants.distance(nxt, (5, 8)) < ants.distance(loc, (5, 8)), orders
    assert ants.distance(nxt, (15, 5)) >= ants.distance(loc, (15, 5)), orders


def test_company_solo_ant_ignores_hill_without_food():
    # One ant, one hill, no food: exploring beats a solo suicide raid.
    ants = StubAnts()
    ants.set_my_ants([(5, 5)])
    ants.set_enemy_hills([(15, 5)])
    orders = run_bot(ants)
    assert len(orders) == 1, orders
    (loc, d) = orders[0]
    nxt = ants.destination(loc, d)
    assert ants.distance(nxt, (15, 5)) >= ants.distance(loc, (15, 5)), orders


def test_company_split_votes_each_company_marches():
    # Two hills, two pairs: each company marches its own hill.
    ants = StubAnts()
    ants.set_my_ants([(2, 2), (2, 4), (17, 17), (17, 15)])
    ants.set_enemy_hills([(2, 10), (17, 8)])
    orders = run_bot(ants)
    assert len(orders) == 4, orders
    for loc, d in orders:
        nxt = ants.destination(loc, d)
        before = min(ants.distance(loc, h) for h in [(2, 10), (17, 8)])
        after = min(ants.distance(nxt, h) for h in [(2, 10), (17, 8)])
        assert after < before, orders


def test_company_hills_counts_votes():
    ants = StubAnts(rows=20, cols=20)
    mine = [(2, 2), (2, 4), (17, 17)]
    hills = [(2, 10), (17, 8)]

    def dist(a, b):
        return ants.distance(a, b)

    companies = company_hills(mine, hills, dist)
    # (2,2) and (2,4) vote (2,10); (17,17) votes (17,8) alone -> solo, no company
    assert companies == {(2, 10): [(2, 2), (2, 4)]}, companies


def test_food_never_ceded_under_threat():
    # Enemies camping the food: every ant still harvests (no denial ceding).
    ants = StubAnts()
    mine = [(5, 5), (6, 6), (4, 4), (7, 7)]
    foods = [(10, 10), (11, 11), (12, 12), (10, 12)]
    foes = [(10, 11), (11, 10), (9, 10)]

    def dist(a, b):
        return ants.distance(a, b)

    target = assign_food_targets(mine, foods, foes, dist, 20, 20)
    assert len(target) == 4, target
    assert set(target.values()) == set(foods), target


def test_join_pair_engages_equal_trade():
    # Two ants stepping into contact with the same foe: both engage.
    ants = StubAnts()
    ants.set_my_ants([(5, 4), (5, 8)])
    ants.set_enemies([(5, 6)])
    ants.attackradius2 = 2
    orders = run_bot(ants)
    # both ants must move (join releases the equal trade)
    assert len(orders) == 2, orders


def test_grinder_ahead_engages_lone_duel():
    # Friendless 1v1 contact while ahead 5v2: the duel is taken.
    ants = StubAnts(rows=30, cols=30)
    ants.set_my_ants([(5, 5), (20, 20), (21, 21), (22, 22), (23, 23)])
    ants.set_enemies([(5, 7), (25, 25)])
    ants.attackradius2 = 2  # contact only when adjacent-ish
    orders = run_bot(ants)
    first = [o for o in orders if o[0] == (5, 5)]
    assert len(first) == 1, orders
    nxt = ants.destination((5, 5), first[0][1])
    assert ants.distance(nxt, (5, 7)) < ants.distance((5, 5), (5, 7)), orders


def test_grinder_behind_refuses_lone_duel():
    # Friendless 1v1 contact while behind 1v3: no step into contact.
    ants = StubAnts(rows=30, cols=30)
    ants.set_my_ants([(5, 5)])
    ants.set_enemies([(5, 7), (25, 25), (24, 24)])
    ants.attackradius2 = 2
    orders = run_bot(ants)
    assert [loc for (loc, _) in orders if loc == (5, 5)] != [], orders
    for loc, d in orders:
        if loc == (5, 5):
            nxt = ants.destination(loc, d)
            # must not step adjacent (into contact) with the foe
            assert ants.distance(nxt, (5, 7)) > 1, orders


def test_safety_refuses_suicide_step():
    # One ant facing two adjacent foes: it must not step between them.
    ants = StubAnts()
    ants.set_my_ants([(10, 10)])
    ants.set_enemies([(10, 12), (12, 10)])
    ants.set_food([(10, 11)])  # bait between the foes
    ants.attackradius2 = 5
    orders = run_bot(ants)
    # already in contact: holds the line instead of stepping onto the meal
    assert orders == [], orders


def test_guard_holds_threatened_hill():
    ants = StubAnts()
    ants.set_my_ants([(5, 5), (8, 8)])
    ants.set_my_hills([(5, 5)])
    ants.set_enemies([(5, 9)])
    orders = run_bot(ants)
    by_ant = dict(orders)
    # hill ant (5,5) must not abandon the hill area: no order, or a step back
    if (5, 5) in by_ant:
        nxt = ants.destination((5, 5), by_ant[(5, 5)])
        assert ants.distance(nxt, (5, 5)) <= 2, orders


def test_walk_off_home_hill():
    # Held ant sitting on a home hill with nothing to do must step off.
    ants = StubAnts()
    ants.set_my_ants([(5, 5)])
    ants.set_my_hills([(5, 5)])
    orders = run_bot(ants)
    assert orders, "ant must walk off its hill"
    (loc, d) = orders[0]
    assert loc == (5, 5)
    assert ants.destination(loc, d) != (5, 5)


def test_explore_rotation_spreads_ants():
    # Two ants, empty world: simultaneous explorers must not march in a column.
    ants = StubAnts(rows=30, cols=30)
    ants.set_my_ants([(10, 10), (10, 12)])
    orders = run_bot(ants)
    assert len(orders) == 2, orders
    dirs = sorted(d for (_, d) in orders)
    assert dirs[0] != dirs[1], orders


def test_turn_finishes_fast_with_big_army():
    ants = StubAnts(rows=60, cols=60)
    mine = [(r % 60, (r * 7) % 60) for r in range(150)]
    ants.set_my_ants(mine)
    ants.set_food([(i % 60, (i * 13) % 60) for i in range(60)])
    ants.set_enemies([(i % 60, (i * 29) % 60) for i in range(40)])
    ants.set_enemy_hills([(30, 30), (10, 50)])
    ants.set_my_hills([(0, 0)])
    bot = Tercio()
    bot.do_setup(ants)
    start = time.perf_counter()
    bot.do_turn(ants)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, elapsed


def step_world(ants, orders):
    moved = dict(orders)
    ants.set_my_ants(
        [
            ants.destination(loc, moved[loc]) if loc in moved else loc
            for loc in ants.my_ants()
        ]
    )
    ants.orders = []


def test_ghost_hill_forgotten_when_visible_empty():
    ants = StubAnts()
    ants.set_my_ants([(5, 5), (5, 7)])
    ants.set_enemy_hills([(5, 15)])
    bot = Tercio()
    bot.do_setup(ants)
    bot.do_turn(ants)
    assert bot.remembered_hills == {(5, 15)}, bot.remembered_hills
    # hill razed: visible but gone -> forgotten, company dissolves
    ants.set_enemy_hills([])
    step_world(ants, ants.orders)
    bot.do_turn(ants)
    assert bot.remembered_hills == set(), bot.remembered_hills


def test_company_converges_on_hill_over_turns():
    ants = StubAnts()
    ants.set_my_ants([(5, 5), (8, 5)])
    ants.set_enemy_hills([(5, 15)])
    bot = Tercio()
    bot.do_setup(ants)
    for _ in range(12):
        bot.do_turn(ants)
        step_world(ants, ants.orders)
    # the company reaches the hill; the leader standing on it razes it.
    assert (5, 15) in ants.my_ants(), ants.my_ants()
    for a in ants.my_ants():
        assert ants.distance(a, (5, 15)) <= 4, ants.my_ants()


def test_solo_never_raids_over_turns():
    ants = StubAnts()
    ants.set_my_ants([(5, 5)])
    ants.set_enemy_hills([(15, 5)])
    bot = Tercio()
    bot.do_setup(ants)
    start = ants.distance((5, 5), (15, 5))
    for _ in range(6):
        bot.do_turn(ants)
        step_world(ants, ants.orders)
    end = min(ants.distance(a, (15, 5)) for a in ants.my_ants())
    assert end >= start - 2, (start, end, ants.my_ants())


def test_pair_holds_contact_instead_of_wandering():
    # Adjacent to a lone foe with backup: the pair stays in contact.
    ants = StubAnts()
    ants.set_my_ants([(5, 5), (6, 6)])
    ants.set_enemies([(5, 6)])
    ants.attackradius2 = 5
    bot = Tercio()
    bot.do_setup(ants)
    bot.do_turn(ants)
    for loc, d in ants.orders:
        nxt = ants.destination(loc, d)
        assert ants.distance(nxt, (5, 6)) <= ants.distance(loc, (5, 6)) + 1, ants.orders


def test_company_sieges_blocked_hill():
    # A company outside contact of a defended hill holds the siege: the
    # voter at (5, 11) must issue no order instead of exploring away.
    ants = StubAnts()
    ants.set_my_ants([(5, 11), (5, 12)])
    ants.set_enemy_hills([(5, 15)])
    ants.set_enemies([(5, 15), (5, 14), (6, 15)])
    ants.attackradius2 = 5
    orders = run_bot(ants)
    assert [loc for (loc, _) in orders if loc == (5, 11)] == [], orders


def test_join_never_engages_outnumbered_pair():
    # A joined pair facing 3 foes with 1 backup must not step in:
    # capped counts must never read 3 foes as 2.
    ants = StubAnts()
    ants.set_my_ants([(5, 11), (5, 12)])
    ants.set_enemy_hills([(5, 15)])
    ants.set_enemies([(5, 15), (5, 14), (6, 15)])
    ants.attackradius2 = 5
    orders = run_bot(ants)
    assert ((5, 12), "e") not in orders, orders


def test_sitter_holds_adjacent_food():
    # Ant adjacent to its claim holds the meal instead of exploring off it.
    ants = StubAnts()
    ants.set_my_ants([(5, 5)])
    ants.set_food([(5, 6)])
    orders = run_bot(ants)
    assert orders == [], orders


def test_food_path_routes_around_water():
    # A wall of water between ant and food: the ant still advances (BFS).
    water = [(5, c) for c in range(0, 19)] + [(7, c) for c in range(1, 20)]
    ants = StubAnts(rows=20, cols=20, water=water)
    ants.set_my_ants([(6, 0)])
    ants.set_food([(6, 10)])
    orders = run_bot(ants)
    assert len(orders) == 1, orders
    (loc, d) = orders[0]
    nxt = ants.destination(loc, d)
    assert nxt not in water, orders
    assert ants.distance(nxt, (6, 10)) < ants.distance(loc, (6, 10)), orders


def test_economy_clears_foods_over_turns():
    # 5 ants, 8 foods, no enemies: proximity gathering clears the board.
    ants = StubAnts(rows=30, cols=30)
    ants.set_my_ants([(2, 2), (2, 27), (27, 2), (27, 27), (15, 15)])
    ants.set_food(
        [(5, 5), (5, 25), (25, 5), (25, 25), (10, 15), (15, 10), (20, 15), (15, 20)]
    )
    bot = Tercio()
    bot.do_setup(ants)
    for _ in range(40):
        if not ants.foods:
            break
        bot.do_turn(ants)
        step_world(ants, ants.orders)
        # gather: single owner within 2 of a food takes it
        taken = [
            f
            for f in ants.foods
            if any(ants.distance(a, f) <= 2 for a in ants.my_ants())
        ]
        for f in taken:
            ants.foods.remove(f)
    assert ants.foods == [], ants.foods


def test_guard_contains_razer_over_turns():
    # A razer marching on our hill: guards stay home and meet it.
    ants = StubAnts(rows=30, cols=30)
    ants.set_my_ants([(5, 5), (7, 7), (20, 20)])
    ants.set_my_hills([(5, 5)])
    foes = [(5, 12)]
    bot = Tercio()
    bot.do_setup(ants)
    home_guard = False
    for _ in range(8):
        ants.set_enemies(foes)
        bot.do_turn(ants)
        step_world(ants, ants.orders)
        # razer advances one step toward the hill each turn
        fr, fc = foes[0]
        foes = [(fr, fc - 1) if fc > 5 else (fr, fc)]
        if any(ants.distance(a, (5, 5)) <= 6 for a in ants.my_ants()):
            home_guard = True
        ants.set_enemies(foes)
    assert home_guard, ants.my_ants()
    # guards meet the razer instead of leaving it a free run home
    assert min(ants.distance(a, foes[0]) for a in ants.my_ants()) <= 3, (
        ants.my_ants(),
        foes,
    )


def test_empty_army_no_crash():
    ants = StubAnts()
    ants.set_my_ants([])
    ants.set_food([(5, 5)])
    ants.set_enemies([(3, 3)])
    assert run_bot(ants) == []


class FrozenAnts(StubAnts):
    def time_remaining(self):
        return 0


def test_no_time_no_crash():
    ants = FrozenAnts()
    ants.set_my_ants([(5, 5), (6, 6)])
    ants.set_food([(5, 8)])
    run_bot(ants)  # must not raise


def test_surrounded_ant_holds_without_orders():
    ants = StubAnts(rows=5, cols=5)
    water = [(0, 1), (1, 0), (1, 2), (2, 1)]
    ants.water = set(water)
    ants.set_my_ants([(1, 1)])
    assert run_bot(ants) == []


def test_ghost_guard_holds_after_razer_blinks():
    # A razer seen near home then vanishing: the guard still holds 3 turns.
    ants = StubAnts()
    ants.set_my_ants([(8, 8)])
    ants.set_my_hills([(5, 5)])
    ants.set_enemies([(5, 9)])
    bot = Tercio()
    bot.do_setup(ants)
    bot.do_turn(ants)
    assert (5, 9) in bot.ghosts, bot.ghosts
    ants.set_enemies([])
    step_world(ants, ants.orders)
    for _ in range(3):
        bot.do_turn(ants)
        step_world(ants, ants.orders)
    # ghosts expire after TTL turns without a sighting
    assert bot.ghosts == {}, bot.ghosts


def test_ghost_keeps_guard_posted():
    # Vanished razer within guard range: guard still steps home, not explores.
    ants = StubAnts()
    ants.set_my_ants([(8, 8)])
    ants.set_my_hills([(5, 5)])
    ants.set_enemies([(5, 9)])
    bot = Tercio()
    bot.do_setup(ants)
    bot.do_turn(ants)
    ants.set_enemies([])
    ants.orders = []
    bot.do_turn(ants)
    assert ants.orders, "guard must still answer the ghost"
    (loc, d) = ants.orders[0]
    assert ants.distance(ants.destination(loc, d), (5, 5)) < ants.distance(loc, (5, 5))


def test_turn_finishes_fast_in_crowd():
    ants = StubAnts(rows=50, cols=50)
    mine = [(r % 50, (r * 7) % 50) for r in range(200)]
    ants.set_my_ants(mine)
    ants.set_food([(i % 50, (i * 13) % 50) for i in range(80)])
    ants.set_enemies([(i % 50, (i * 29) % 50) for i in range(120)])
    ants.set_enemy_hills([(30, 30), (10, 0)])
    ants.set_my_hills([(0, 0)])
    bot = Tercio()
    bot.do_setup(ants)
    start = time.perf_counter()
    bot.do_turn(ants)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, elapsed


def test_lone_arrival_holds_defended_hill():
    # Claim-free ant at a defended hill holds its siege, not explores.
    ants = StubAnts()
    ants.set_my_ants([(5, 13)])
    ants.set_enemy_hills([(5, 15)])
    ants.set_enemies([(5, 15), (5, 16), (6, 15)])
    ants.attackradius2 = 5
    orders = run_bot(ants)
    assert orders == [], orders


def test_lone_arrival_razes_empty_hill():
    # Claim-free ant two from an empty hill steps in and razes for free.
    ants = StubAnts()
    ants.set_my_ants([(5, 13)])
    ants.set_enemy_hills([(5, 15)])
    bot = Tercio()
    bot.do_setup(ants)
    bot.do_turn(ants)
    step_world(ants, ants.orders)
    assert ants.distance(ants.my_ants()[0], (5, 15)) < 2, ants.my_ants()


def test_same_turn_same_orders():
    # No RNG: identical turns give identical orders.
    def build():
        ants = StubAnts(rows=40, cols=40)
        ants.set_my_ants([(r % 40, (r * 7) % 40) for r in range(60)])
        ants.set_food([(i % 40, (i * 13) % 40) for i in range(30)])
        ants.set_enemies([(i % 40, (i * 29) % 40) for i in range(25)])
        ants.set_enemy_hills([(30, 30)])
        ants.set_my_hills([(0, 0)])
        return ants

    a1, a2 = build(), build()
    b1, b2 = Tercio(), Tercio()
    for b, a in ((b1, a1), (b2, a2)):
        b.do_setup(a)
        b.do_turn(a)
    assert a1.orders == a2.orders


def test_real_ants_single_turn():
    # Integration: drive Tercio through the real ants.Ants input pipeline.
    import io
    from contextlib import redirect_stdout

    from ants import Ants

    real = Ants()
    real.setup(
        "rows 20\ncols 20\nturntime 1000\nloadtime 1000\n"
        "viewradius2 55\nattackradius2 5\nspawnradius2 2\nturns 100\n"
    )
    real.update("a 5 4 0\na 5 8 0\na 5 6 1\nh 15 15 1\nh 0 0 0\n")
    assert real.passable((5, 5)) is True
    assert real.unoccupied((5, 6)) is False  # foe-occupied: never step onto it
    bot = Tercio()
    bot.do_setup(real)
    buf = io.StringIO()
    with redirect_stdout(buf):
        bot.do_turn(real)
    orders = [ln for ln in buf.getvalue().split("\n") if ln.startswith("o ")]
    # joined pair steps into contact from both sides
    assert sorted(orders) == ["o 5 4 e", "o 5 8 w"], orders


def test_fearless_pack_presses_small_fight():
    # Packed (3+ buddies) with 3 foes in sight: the hunter steps in
    # although the safety filter refuses the trade.
    ants = StubAnts()
    ants.set_my_ants([(5, 8), (5, 5), (5, 6), (5, 7)])
    ants.set_enemies([(5, 10), (4, 10), (6, 10)])
    ants.attackradius2 = 5
    orders = run_bot(ants)
    assert ((5, 8), "e") in orders, orders


def test_fearless_needs_pack():
    # Same fight, lone hunter: no fearless step into the trade.
    ants = StubAnts()
    ants.set_my_ants([(5, 8)])
    ants.set_enemies([(5, 10), (4, 10), (6, 10)])
    ants.attackradius2 = 5
    orders = run_bot(ants)
    assert [o for o in orders if o[0] == (5, 8)] == [], orders


def test_fearless_needs_small_fight():
    # Packed but 10+ foes in sight: full safety applies, no advance.
    ants = StubAnts(rows=40, cols=40)
    ants.set_my_ants([(5, 8), (5, 5), (5, 6), (5, 7)])
    ants.set_enemies(
        [
            (5, 10),
            (4, 10),
            (6, 10),
            (20, 20),
            (21, 21),
            (22, 22),
            (23, 23),
            (24, 24),
            (25, 25),
            (26, 26),
            (27, 27),
        ]
    )
    ants.attackradius2 = 5
    orders = run_bot(ants)
    # no fearless advance into the teeth; other safe moves may issue
    assert ((5, 8), "e") not in orders, orders


def test_company_marches_fearless_ahead_on_hills():
    # Ahead 2-1 on hills: the company steps into an unsafe approach.
    ants = StubAnts()
    ants.set_my_ants([(5, 11), (6, 10)])
    ants.set_my_hills([(15, 5), (15, 6)])
    ants.set_enemy_hills([(5, 15)])
    ants.set_enemies([(5, 14), (5, 15), (4, 14)])
    ants.attackradius2 = 5
    orders = run_bot(ants)
    assert ((5, 11), "e") in orders, orders


def test_company_marches_safe_behind_on_hills():
    # Same approach with no hills of our own: safety holds, no step in.
    ants = StubAnts()
    ants.set_my_ants([(5, 11), (6, 10)])
    ants.set_enemy_hills([(5, 15)])
    ants.set_enemies([(5, 14), (5, 15), (4, 14)])
    ants.attackradius2 = 5
    orders = run_bot(ants)
    assert [o for o in orders if o[0] == (5, 11)] == [], orders


def test_guard_extra_screens_midpoint():
    # Second guard meets the razer at the midpoint, not piled on the hill.
    ants = StubAnts(rows=30, cols=30)
    ants.set_my_ants([(5, 5), (9, 9)])
    ants.set_my_hills([(5, 5)])
    ants.set_enemies([(5, 12)])
    orders = run_bot(ants)
    second = [d for (loc, d) in orders if loc == (9, 9)]
    assert len(second) == 1, orders
    nxt = ants.destination((9, 9), second[0])
    assert ants.distance(nxt, (5, 8)) < ants.distance((9, 9), (5, 8)), orders


def test_closing_razer_threatens_from_afar():
    # A razer closing 14->13 threatens the hill before range 10.
    ants = StubAnts(rows=30, cols=30)
    ants.set_my_ants([(18, 18)])
    ants.set_my_hills([(15, 15)])
    bot = Tercio()
    bot.do_setup(ants)
    ants.set_enemies([(15, 1)])
    bot.do_turn(ants)
    step_world(ants, ants.orders)
    ants.set_enemies([(15, 2)])
    ants.orders = []
    bot.do_turn(ants)
    assert ants.orders, "closing razer must threaten the hill"
    (loc, d) = ants.orders[0]
    assert ants.distance(ants.destination(loc, d), (15, 15)) < ants.distance(
        loc, (15, 15)
    )


def test_hill_sitter_walks_off():
    # An ant on its home hill with adjacent food still leaves the hill.
    ants = StubAnts()
    ants.set_my_ants([(5, 5)])
    ants.set_my_hills([(5, 5)])
    ants.set_food([(5, 6)])
    orders = run_bot(ants)
    assert orders, "ant must not squat its hill"
    (loc, d) = orders[0]
    assert ants.destination(loc, d) != (5, 5), orders


def test_mixed_owners_treated_as_foes():
    ants = StubAnts()
    ants.set_my_ants([(5, 5), (5, 7)])
    ants.enemy_list = [((5, 6), 1), ((10, 10), 2), ((12, 12), 3)]
    ants.set_food([(6, 6)])
    orders = run_bot(ants)
    # nobody steps onto the foe-occupied square, whatever its owner
    assert all(ants.destination(loc, d) != (5, 6) for (loc, d) in orders), orders


def test_receding_razer_stands_down_guard():
    # A razer moving away (15->16, out of 10) releases the guard to explore.
    ants = StubAnts(rows=30, cols=30)
    ants.set_my_ants([(18, 18)])
    ants.set_my_hills([(15, 15)])
    bot = Tercio()
    bot.do_setup(ants)
    ants.set_enemies([(15, 1)])
    bot.do_turn(ants)
    step_world(ants, ants.orders)
    ants.set_enemies([(15, 0)])
    ants.orders = []
    bot.do_turn(ants)
    # foe at 15 from the hill and receding: no guard march onto the hill
    for loc, d in ants.orders:
        nxt = ants.destination(loc, d)
        assert not (
            ants.distance(nxt, (15, 15)) < ants.distance(loc, (15, 15))
            and ants.distance(loc, (15, 15)) <= 4
        ), ants.orders


def test_screen_routes_around_water():
    # The off-hill screen still posts when water floods the midpoint.
    ants = StubAnts(rows=30, cols=30, water=[(5, 8), (6, 8), (4, 8)])
    ants.set_my_ants([(5, 5), (9, 9)])
    ants.set_my_hills([(5, 5)])
    ants.set_enemies([(5, 12)])
    orders = run_bot(ants)
    second = [d for (loc, d) in orders if loc == (9, 9)]
    assert len(second) == 1, orders
    assert ants.destination((9, 9), second[0]) not in {(5, 8), (6, 8), (4, 8)}


def test_real_map_single_turn():
    # Scenario: one turn on the real tutorial map through ants.Ants.
    import io
    from contextlib import redirect_stdout

    from ants import Ants

    here = os.path.dirname(os.path.abspath(__file__))
    map_path = os.path.join(
        here, "..", "..", "tools", "maps", "example", "tutorial1.map"
    )
    rows = []
    with open(map_path) as f:
        nrows = ncols = 0
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("rows"):
                nrows = int(line.split()[1])
            elif line.startswith("cols"):
                ncols = int(line.split()[1])
            elif line.startswith("m "):
                rows.append(line[2:])
    assert (len(rows), len(rows[0])) == (nrows, ncols)
    real = Ants()
    real.setup(
        f"rows {nrows}\ncols {ncols}\nturntime 1000\nloadtime 1000\n"
        "viewradius2 55\nattackradius2 5\nspawnradius2 2\nturns 100\n"
    )
    turn = []
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == "%":
                turn.append(f"w {r} {c}")
            elif ch == "*":
                turn.append(f"f {r} {c}")
            elif ch == "A":
                turn.append(f"a {r} {c} 0")
                turn.append(f"h {r} {c} 0")
            elif ch == "B":
                turn.append(f"a {r} {c} 1")
                turn.append(f"h {r} {c} 1")
    real.update("\n".join(turn) + "\n")
    assert real.my_ants() and real.food()
    bot = Tercio()
    bot.do_setup(real)
    buf = io.StringIO()
    with redirect_stdout(buf):
        start = time.perf_counter()
        bot.do_turn(real)
        elapsed = time.perf_counter() - start
    orders = [ln for ln in buf.getvalue().split("\n") if ln.startswith("o ")]
    assert elapsed < 1.0, elapsed
    assert orders, "the opening must move"


def test_fuzz_random_worlds_hold_invariants():
    # 60 random torus worlds: orders stay legal, destinations unique, fast.
    import random

    rng = random.Random(20261008)
    dirs = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
    for _ in range(60):
        rows, cols = rng.choice([(20, 20), (30, 40), (50, 30)])
        ants = StubAnts(rows=rows, cols=cols)
        water = {
            (rng.randrange(rows), rng.randrange(cols))
            for _ in range(rng.randint(0, 40))
        }
        ants.water = set(water)
        free = [(r, c) for r in range(rows) for c in range(cols) if (r, c) not in water]
        rng.shuffle(free)
        n_mine = rng.randint(0, 12)
        mine = free[:n_mine]
        foes = free[n_mine : n_mine + rng.randint(0, 8)]
        foods = free[n_mine + len(foes) : n_mine + len(foes) + rng.randint(0, 10)]
        ants.set_my_ants(mine)
        ants.set_enemies(foes)
        ants.set_food(foods)
        ants.set_my_hills(rng.sample(mine, min(len(mine), rng.randint(0, 2))))
        ants.set_enemy_hills(
            rng.sample(foes, min(len(foes), rng.randint(0, 2))) if foes else []
        )
        ants.attackradius2 = rng.choice([2, 5, 9])
        bot = Tercio()
        bot.do_setup(ants)
        start = time.perf_counter()
        bot.do_turn(ants)
        assert time.perf_counter() - start < 1.0
        # replay in issue order: destinations unique, passable, and
        # free (turn-start occupancy minus squares earlier ants vacated).
        occupied = set(mine) | set(foes) | set(foods)
        vacated_replay: set = set()
        seen = set()
        for loc, d in ants.orders:
            assert loc in mine, ants.orders
            dr, dc = dirs[d]
            nxt = ((loc[0] + dr) % rows, (loc[1] + dc) % cols)
            assert nxt not in water, ants.orders
            assert nxt not in seen, ants.orders
            assert nxt not in occupied - vacated_replay, ants.orders
            seen.add(nxt)
            occupied.add(nxt)
            vacated_replay.add(loc)


def test_mega_melee_stays_fast_and_guarded():
    ants = StubAnts(rows=60, cols=60)
    ants.set_my_ants([(5, 5), (6, 6)])
    ants.set_my_hills([(5, 5)])
    ants.set_enemies([(r % 60, (r * 7) % 60) for r in range(150)])
    bot = Tercio()
    bot.do_setup(ants)
    bot.prev_enemies = [(r % 60, (r * 11) % 60) for r in range(150)]
    start = time.perf_counter()
    bot.do_turn(ants)
    assert time.perf_counter() - start < 1.0


def test_company_never_donates_over_siege():
    # 10 turns vs a camped hill: no order ever steps into a losing fight.
    ants = StubAnts(rows=30, cols=30)
    ants.set_my_ants([(5, 5), (6, 6), (20, 20), (21, 21)])
    ants.set_enemy_hills([(5, 25)])
    ants.set_enemies([(5, 25), (5, 24), (6, 25), (4, 25), (15, 15)])
    ants.attackradius2 = 5
    bot = Tercio()
    bot.do_setup(ants)

    def sq(a, b):
        dr = min(abs(a[0] - b[0]), ants.rows - abs(a[0] - b[0]))
        dc = min(abs(a[1] - b[1]), ants.cols - abs(a[1] - b[1]))
        return dr * dr + dc * dc

    for _ in range(10):
        bot.do_turn(ants)
        mine = set(ants.my_ants())
        foes = [loc for loc, _ in ants.enemy_list]
        for loc, d in ants.orders:
            nxt = ants.destination(loc, d)
            n_foes = sum(1 for e in foes if sq(nxt, e) <= ants.attackradius2)
            n_pals = sum(
                1 for f in mine if f != loc and sq(nxt, f) <= ants.attackradius2
            )
            assert n_foes <= n_pals + 1, ((loc, d), n_foes, n_pals)
        step_world(ants, ants.orders)


def test_maze_map_big_armies_single_turn():
    # Scenario: 150v100 scattered on a real maze through ants.Ants.
    import io
    import random
    from contextlib import redirect_stdout

    from ants import Ants

    here = os.path.dirname(os.path.abspath(__file__))
    map_path = os.path.join(
        here, "..", "..", "tools", "maps", "maze", "maze_p02_17.map"
    )
    rows = []
    nrows = ncols = 0
    with open(map_path) as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("rows"):
                nrows = int(line.split()[1])
            elif line.startswith("cols"):
                ncols = int(line.split()[1])
            elif line.startswith("m "):
                rows.append(line[2:])
    rng = random.Random(7)
    land = [
        (r, c) for r, row in enumerate(rows) for c, ch in enumerate(row) if ch != "%"
    ]
    assert len(land) > 400, len(land)
    rng.shuffle(land)
    mine = land[:150]
    foes = land[150:250]
    foods = land[250:300]
    real = Ants()
    real.setup(
        f"rows {nrows}\ncols {ncols}\nturntime 1000\nloadtime 1000\n"
        "viewradius2 55\nattackradius2 5\nspawnradius2 2\nturns 100\n"
    )
    turn = (
        [
            f"w {r} {c}"
            for r, row in enumerate(rows)
            for c, ch in enumerate(row)
            if ch == "%"
        ]
        + [f"a {r} {c} 0" for (r, c) in mine]
        + [f"a {r} {c} 1" for (r, c) in foes]
        + [f"f {r} {c}" for (r, c) in foods]
        + [f"h {mine[0][0]} {mine[0][1]} 0", f"h {foes[0][0]} {foes[0][1]} 1"]
    )
    real.update("\n".join(turn) + "\n")
    assert len(real.my_ants()) == 150
    bot = Tercio()
    bot.do_setup(real)
    buf = io.StringIO()
    with redirect_stdout(buf):
        start = time.perf_counter()
        bot.do_turn(real)
        elapsed = time.perf_counter() - start
    assert elapsed < 1.0, elapsed


def test_company_ignores_solo_hills_beside_company():
    # Votes 2-1-1: only the pair's hill draws a march; solos farm.
    ants = StubAnts(rows=40, cols=40)
    ants.set_my_ants([(2, 2), (2, 4), (30, 30), (10, 30)])
    ants.set_enemy_hills([(2, 10), (30, 20), (10, 20)])
    ants.set_food([(30, 31)])
    orders = run_bot(ants)
    by_ant = dict(orders)
    # pair voters march their hill
    for loc in [(2, 2), (2, 4)]:
        assert loc in by_ant, orders
        nxt = ants.destination(loc, by_ant[loc])
        assert ants.distance(nxt, (2, 10)) < ants.distance(loc, (2, 10)), orders
    # solo voter sitting on adjacent food holds its meal, never raids
    assert (30, 30) not in by_ant, orders


def test_contested_food_mutual_denial_stance():
    # Racing a foe to one food: ours advances, then holds adjacent --
    # contesting the field -- instead of stepping onto the foe.
    ants = StubAnts(rows=20, cols=20)
    ants.set_my_ants([(5, 5)])
    ants.set_food([(5, 7)])
    ants.set_enemies([(5, 9)])
    bot = Tercio()
    bot.do_setup(ants)
    bot.do_turn(ants)
    step_world(ants, ants.orders)
    assert ants.my_ants() == [(5, 6)], ants.my_ants()
    ants.set_enemies([(5, 7)])
    for _ in range(3):
        ants.orders = []
        bot.do_turn(ants)
        assert [o for o in ants.orders if o[0] == (5, 6)] == [], ants.orders
        step_world(ants, ants.orders)
    assert ants.my_ants() == [(5, 6)], ants.my_ants()


def test_file_march_flows_through_vacated_squares():
    # Three voters marching north in file: each steps into the square
    # the ant ahead just vacated instead of stalling or holding.
    ants = StubAnts(rows=20, cols=20)
    ants.set_my_ants([(7, 5), (8, 5), (9, 5)])
    ants.set_enemy_hills([(5, 5)])
    orders = run_bot(ants)
    assert len(orders) == 3, orders
    for loc, d in orders:
        nxt = ants.destination(loc, d)
        assert ants.distance(nxt, (5, 5)) < ants.distance(loc, (5, 5)), orders


def test_guard_covers_two_hills():
    # Two threatened hills: each draws coverage, the spare screens.
    ants = StubAnts(rows=30, cols=30)
    ants.set_my_ants([(5, 5), (20, 20), (12, 12)])
    ants.set_my_hills([(5, 5), (20, 20)])
    ants.set_enemies([(5, 9), (20, 24)])
    orders = run_bot(ants)
    assert len(orders) == 3, orders
    by_ant = dict(orders)
    assert ants.distance(ants.destination((5, 5), by_ant[(5, 5)]), (5, 5)) <= 2
    assert ants.distance(ants.destination((20, 20), by_ant[(20, 20)]), (20, 20)) <= 2
    nxt = ants.destination((12, 12), by_ant[(12, 12)])
    assert ants.distance(nxt, (5, 7)) < ants.distance((12, 12), (5, 7)), orders


def test_food_holder_sits_while_pack_presses():
    # Packed hunters press the small fight; the ant on the meal sits it.
    ants = StubAnts()
    ants.set_my_ants([(5, 8), (5, 5), (5, 6), (5, 7)])
    ants.set_food([(5, 4)])
    ants.set_enemies([(5, 10), (4, 10), (6, 10)])
    ants.attackradius2 = 5
    orders = run_bot(ants)
    by_ant = dict(orders)
    assert (5, 5) not in by_ant, orders  # sits its meal
    assert by_ant.get((5, 8)) == "e", orders  # presses the fight


def test_grinder_even_armies_refuse_duel():
    # Friendless 1v1 at even 2v2: no engage; the ant must not close.
    ants = StubAnts(rows=30, cols=30)
    ants.set_my_ants([(5, 5), (20, 20)])
    ants.set_enemies([(5, 7), (25, 25)])
    ants.attackradius2 = 2
    orders = run_bot(ants)
    for loc, d in orders:
        if loc == (5, 5):
            nxt = ants.destination(loc, d)
            assert ants.distance(nxt, (5, 7)) >= ants.distance(loc, (5, 7)), orders


def test_split_foes_no_join():
    # Two separate 1v1s draw no join; even armies refuse both duels.
    ants = StubAnts(rows=30, cols=30)
    ants.set_my_ants([(5, 4), (25, 24)])
    ants.set_enemies([(5, 6), (25, 26)])
    ants.attackradius2 = 2
    orders = run_bot(ants)
    assert len(orders) == 2, orders
    pairs = {loc: ants.destination(loc, d) for (loc, d) in orders}
    assert ants.distance(pairs[(5, 4)], (5, 6)) > 1, orders
    assert ants.distance(pairs[(25, 24)], (25, 26)) > 1, orders


def test_food_outranks_guard_for_lone_ant():
    # One ant, threatened hill, distant food: it harvests (food first).
    ants = StubAnts(rows=30, cols=30)
    ants.set_my_ants([(5, 5)])
    ants.set_my_hills([(5, 5)])
    ants.set_food([(5, 25)])
    ants.set_enemies([(5, 9)])
    orders = run_bot(ants)
    assert len(orders) == 1, orders
    (loc, d) = orders[0]
    nxt = ants.destination(loc, d)
    assert ants.distance(nxt, (5, 25)) < ants.distance(loc, (5, 25)), orders


def test_one_ant_per_food_no_doubling():
    # Two ants, one food: only the closest harvests; no doubling up.
    ants = StubAnts(rows=30, cols=30)
    ants.set_my_ants([(5, 5), (5, 20)])
    ants.set_food([(5, 10)])
    orders = run_bot(ants)
    by_ant = dict(orders)
    nxt = ants.destination((5, 5), by_ant[(5, 5)])
    assert ants.distance(nxt, (5, 10)) < ants.distance((5, 5), (5, 10)), orders
    if (5, 20) in by_ant:
        nxt2 = ants.destination((5, 20), by_ant[(5, 20)])
        assert ants.distance(nxt2, (5, 10)) >= ants.distance((5, 20), (5, 10)), orders


def test_fearless_boundary_at_ten_foes():
    # 9 visible foes: packed hunter presses; 10: the advance stays safe.
    def orders_with(n_far):
        ants = StubAnts(rows=40, cols=40)
        ants.set_my_ants([(5, 8), (5, 5), (5, 6), (5, 7)])
        far = [(20 + i, 20 + i) for i in range(n_far)]
        ants.set_enemies([(5, 10), (4, 10), (6, 10)] + far)
        ants.attackradius2 = 5
        return run_bot(ants)

    assert ((5, 8), "e") in orders_with(6)  # 9 foes: fearless
    assert ((5, 8), "e") not in orders_with(7)  # 10 foes: filtered


def test_pack_boundary_at_three_friends():
    # 2 friends: no fearless; 3 friends: the hunter presses.
    def orders_with(friends):
        ants = StubAnts()
        ants.set_my_ants([(5, 8)] + friends)
        ants.set_enemies([(5, 10), (4, 10), (6, 10)])
        ants.attackradius2 = 5
        return run_bot(ants)

    assert [o for o in orders_with([(5, 5), (5, 6)]) if o[0] == (5, 8)] == []
    assert ((5, 8), "e") in orders_with([(5, 5), (5, 6), (5, 7)])


def test_sitter_needs_path_to_meal():
    # Food sealed behind water: the ant explores instead of sitting forever.
    ants = StubAnts(
        rows=10,
        cols=10,
        water=[(5, 6), (4, 6), (6, 6), (4, 5), (6, 5), (4, 7), (6, 7), (5, 8)],
    )
    ants.set_my_ants([(5, 5)])
    ants.set_food([(5, 7)])
    orders = run_bot(ants)
    assert len(orders) == 1, orders


def test_explorer_covers_ground_without_revisits():
    # Lone explorer on an empty map: 20 turns, 20 distinct squares.
    ants = StubAnts(rows=30, cols=30)
    ants.set_my_ants([(15, 15)])
    bot = Tercio()
    bot.do_setup(ants)
    seen = set()
    for _ in range(20):
        bot.do_turn(ants)
        seen.update(ants.my_ants())
        step_world(ants, ants.orders)
    assert len(seen) == 20, seen


def test_guard_converges_on_hill_razer():
    # Razer sitting on the home hill: guards converge on it.
    ants = StubAnts(rows=20, cols=20)
    ants.set_my_ants([(5, 7), (9, 9)])
    ants.set_my_hills([(5, 5)])
    ants.set_enemies([(5, 5)])
    orders = run_bot(ants)
    assert len(orders) == 2, orders
    for loc, d in orders:
        nxt = ants.destination(loc, d)
        assert ants.distance(nxt, (5, 5)) < ants.distance(loc, (5, 5)), orders


def test_far_food_still_draws_harvester():
    # Food beyond the BFS horizon: greedy direction steps still advance.
    ants = StubAnts(rows=60, cols=60)
    ants.set_my_ants([(5, 5)])
    ants.set_food([(45, 45)])
    orders = run_bot(ants)
    assert len(orders) == 1, orders
    (loc, d) = orders[0]
    nxt = ants.destination(loc, d)
    assert ants.distance(nxt, (45, 45)) < ants.distance(loc, (45, 45)), orders
