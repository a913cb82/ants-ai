#!/usr/bin/env python
"""Fixing6: anthonyvh greedy sequential fixing plus second-wave muster.

Fresh entry: Fixing's guard, fixing combat, and explore byte-identical;
the economy and muster are new -- idle ants reinforce the pinned fight
line (second wave) instead of marching on distant remembered hills,
keeping one raze-cover ant per hill, and long treks to locally lost
meals toll out before claiming. No other bot redirects muster to fights:
Fixing5 rallied combat ants to friends, Crowd2 split muster across
hills, Maniple/Thicket gated presses on majorities. This moves the
muster population to fight destinations with per-hill raze coverage.

Self-contained: stdlib plus Fixing6 only. No combat.py import.

  (a) fight_anchor picks the pinned destination nearest the army.
  (b) raze_cover keeps the closest idle ant per remembered hill.
  (c) in-bot: idle ant near a fight marches fight-ward.
  (d) in-bot: the raze-cover ant still marches hill-ward.
  (e) in-bot: no fight pins -> champion muster unchanged.
  (f) in-bot: fight beyond SECOND_WAVE_RANGE -> muster unchanged.
  (g) wave beats explore for idle ants, guard beats wave.
  (h) hill_camped counts locals; camped flood holds, open marches.
  (i) reinforce_target walks past camps; integration pins hold.
  (j) trek toll cedes lost far meals, spares near and won ones.
  (k) wave holds off locally-lost fights.
  (l) differential: base-identical orders where no new rule fires.
  (m) water routing, multi-turn memory, fuzz, and perf budgets.
  (n) engine-protocol smoke through the real ants.py harness.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Fixing6 as FX  # noqa: E402

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
    visits: dict[Loc, int] | None = None,
) -> tuple[list[tuple[Loc, str]], FX.Fixing6]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = FX.Fixing6()
    if visits is not None:
        bot.visits = dict(visits)
    bot.do_turn(fake)
    return fake.orders, bot


def _dist(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


def test_fixing6_entry_is_self_contained() -> None:
    assert FX.__name__ == "Fixing6"
    assert hasattr(FX, "Fixing6")
    with open(str(FX.__file__)) as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    bot_file = os.path.join(os.path.dirname(str(FX.__file__)), "Fixing6.bot")
    with open(bot_file) as handle:
        assert handle.read().strip() == "python Fixing6.py"


def test_fight_anchor_picks_army_nearest_pin() -> None:
    # (a) dests (5, 6) and (15, 15); the army sits at rows 4-6,
    # so the anchor is (5, 6) -- the line the ants already hold.
    army = [(5, 5), (6, 5), (4, 5)]
    assert FX.fight_anchor([], army, _dist) is None
    assert FX.fight_anchor([(5, 6), (15, 15)], army, _dist) == (5, 6)
    assert FX.fight_anchor([(15, 15), (5, 6)], army, _dist) == (5, 6)


def test_raze_cover_breaks_ties_by_index() -> None:
    # Ants 0 and 1 stand equidistant from hill (0, 0): the cover
    # is ant 0 every run, never flipping with the hash seed.
    ants_list = [(0, 1), (1, 0), (10, 10)]
    assert _dist((0, 1), (0, 0)) == _dist((1, 0), (0, 0))
    assert FX.raze_cover(ants_list, {0, 1}, [(0, 0)], _dist) == {0}


def test_raze_cover_keeps_closest_idle_per_hill() -> None:
    # (b) ants 0 and 1 idle, ant 2 busy; hill (0, 0) is closest
    # to ant 1, hill (19, 19) to ant 0 -- both keep razing.
    ants_list = [(19, 19), (0, 1), (10, 10)]
    assert FX.raze_cover(ants_list, {0, 1}, [(0, 0)], _dist) == {1}
    assert FX.raze_cover(ants_list, {0, 1}, [(0, 0), (19, 19)], _dist) == {0, 1}
    assert FX.raze_cover(ants_list, set(), [(0, 0)], _dist) == set()
    assert FX.raze_cover(ants_list, {0, 1}, [], _dist) == set()


def _step_to(fake_orders: list[tuple[Loc, str]], ant: Loc) -> Loc | None:
    for loc, direction in fake_orders:
        if loc == ant:
            dr, dc = AIM[direction]
            return ((ant[0] + dr) % ROWS, (ant[1] + dc) % COLS)
    return None


def test_second_wave_marches_fight_not_hill() -> None:
    # (c) A (5, 5) fights foe (5, 8) with a hill on the books, so
    # a pin exists; C2 (12, 5) is idle (no food, 10 steps from the
    # foe -- out of seek range) while C1 (1, 1) covers the raze on
    # far hill (0, 0). Champion muster would march C2 hill-ward;
    # the second wave marches C2 toward the pinned fight line.
    # Seeded visits make explore step w (away from the fighter),
    # so only the wave closes on it.
    mine = [(5, 5), (12, 5), (1, 1)]
    foes = [(5, 8)]
    assert _dist((12, 5), (5, 8)) > FX.SEEK_RANGE
    orders, _ = run_turn(
        mine,
        foes,
        enemy_hills=[(0, 0)],
        visits={(11, 5): 9, (12, 6): 9, (13, 5): 9},
    )
    moved_c2 = _step_to(orders, (12, 5))
    assert moved_c2 is not None
    # C2 closes on the fighter instead of the hill.
    assert _dist(moved_c2, (5, 5)) < _dist((12, 5), (5, 5))


def test_raze_cover_ant_still_marches_hill() -> None:
    # (d) same board as (c): C1 (1, 1) is the closest idle ant to
    # hill (0, 0), so it keeps the raze and closes on the hill
    # while C2 reinforces the fight (seeded visits as in (c), so
    # only the wave closes C2 on the fighter).
    mine = [(5, 5), (12, 5), (1, 1)]
    foes = [(5, 8)]
    orders, _ = run_turn(
        mine,
        foes,
        enemy_hills=[(0, 0)],
        visits={(11, 5): 9, (12, 6): 9, (13, 5): 9},
    )
    moved_c1 = _step_to(orders, (1, 1))
    moved_c2 = _step_to(orders, (12, 5))
    assert moved_c1 is not None and moved_c2 is not None
    assert _dist(moved_c1, (0, 0)) < _dist((1, 1), (0, 0))
    assert _dist(moved_c2, (5, 5)) < _dist((12, 5), (5, 5))


def test_no_fight_champion_muster_unchanged() -> None:
    # (e) no enemies at all: idle C (8, 5) musters hill-ward as
    # the champion did, closing on (0, 0).
    mine = [(5, 5), (8, 5)]
    orders, _ = run_turn(mine, [], enemy_hills=[(0, 0)])
    moved_c = _step_to(orders, (8, 5))
    assert moved_c is not None
    assert _dist(moved_c, (0, 0)) < _dist((8, 5), (0, 0))


def test_far_fight_keeps_muster() -> None:
    # (f) the fight is across the board: C (15, 15) sits beyond
    # SECOND_WAVE_RANGE of the pinned line, so it musters
    # hill-ward instead of marching across the map.
    assert _dist((15, 15), (5, 8)) > FX.SEEK_RANGE
    assert _dist((15, 15), (5, 5)) > FX.SECOND_WAVE_RANGE
    mine = [(5, 5), (15, 15)]
    foes = [(5, 8)]
    orders, _ = run_turn(mine, foes, enemy_hills=[(0, 0)])
    moved_c = _step_to(orders, (15, 15))
    assert moved_c is not None
    assert _dist(moved_c, (0, 0)) < _dist((15, 15), (0, 0))


def _assert_legal(
    orders: list[tuple[Loc, str]],
    mine: list[Loc],
    water: set[Loc] | None = None,
    rows: int = ROWS,
    cols: int = COLS,
) -> None:
    # Every order comes from a live own ant, targets a passable
    # square, and claims each square once. Squares vacated by
    # fellow movers are fair game (simultaneous resolution).
    water = water or set()
    vacated = {loc for loc, _ in orders}
    seen: set[Loc] = set()
    for loc, direction in orders:
        assert loc in mine
        dr, dc = AIM[direction]
        dest = ((loc[0] + dr) % rows, (loc[1] + dc) % cols)
        assert dest not in water
        assert dest not in mine or dest in vacated
        assert dest not in seen
        seen.add(dest)


def test_water_routes_around_and_stays_legal() -> None:
    # A water wall at row 8 (gap at (8, 10)) stands between C2
    # and the fight: the march routes around it, and every order
    # on the board stays legal.
    water = {(8, c) for c in range(COLS) if c != 10}
    mine = [(5, 5), (12, 5), (1, 1)]
    foes = [(5, 8)]
    fake = FakeAnts(mine, foes, water=water, enemy_hills=[(0, 0)])
    bot = FX.Fixing6()
    bot.do_turn(fake)
    _assert_legal(fake.orders, mine, water)
    assert len(fake.orders) == 3


def test_multiturn_hill_memory_keeps_wave() -> None:
    # Turn 1 sees hill (0, 0); turn 2 it is out of sight but
    # remembered, and the foe steps to (5, 9) (heading readable,
    # not stationary). The second wave still fires: C2 closes on
    # the fighter while C1 covers the remembered raze.
    bot = FX.Fixing6()
    mine = [(5, 5), (12, 5), (1, 1)]
    fake1 = FakeAnts(mine, [(5, 8)], enemy_hills=[(0, 0)])
    bot.do_turn(fake1)
    assert (0, 0) in bot.remembered_hills
    fake2 = FakeAnts(mine, [(5, 9)])
    bot.do_turn(fake2)
    assert (0, 0) in bot.remembered_hills
    _assert_legal(fake2.orders, mine)
    moved_c2 = _step_to(fake2.orders, (12, 5))
    moved_c1 = _step_to(fake2.orders, (1, 1))
    assert moved_c2 is not None and moved_c1 is not None
    assert _dist(moved_c2, (5, 5)) < _dist((12, 5), (5, 5))
    assert _dist(moved_c1, (0, 0)) < _dist((1, 1), (0, 0))


def test_wave_beats_explore_for_idle_ant() -> None:
    # No hills on the books, fight on: A (5, 5) pins n onto (4, 5)
    # (SAFE needs no hill). C (12, 5) is idle 8 from the anchor --
    # in range. Seeded visits make explore prefer w, but the wave
    # fires first: C steps n toward the line.
    bot = FX.Fixing6()
    mine = [(5, 5), (12, 5)]
    bot.visits = {(11, 5): 5, (12, 6): 5, (13, 5): 5}
    fake = FakeAnts(mine, [(5, 8)])
    bot.do_turn(fake)
    assert ((12, 5), "n") in fake.orders


def test_guard_beats_wave_for_threatened_hill() -> None:
    # G (10, 8) guards threatened home hill (10, 10) while a fight
    # with pins runs elsewhere and hill (0, 0) is remembered: G
    # holds the hill (champion guard) instead of reinforcing.
    mine = [(5, 5), (12, 5), (1, 1), (10, 8)]
    foes = [(5, 8), (10, 16)]
    orders, _ = run_turn(mine, foes, enemy_hills=[(0, 0)], my_hills=[(10, 10)])
    assert ((10, 8), "e") in orders


def test_food_and_first_guard_untouched() -> None:
    # The denial pair still claims (5, 6) and (2, 3) east, and a
    # lone guard still holds its threatened hill east.
    mine = [(5, 5), (2, 2), (10, 10)]
    foods = [(5, 6), (2, 3)]
    enemies = [(5, 12), (2, 6), (5, 9), (10, 15)]
    orders, _ = run_turn(mine, enemies, foods, my_hills=[(10, 12)])
    assert orders == [((5, 5), "e"), ((2, 2), "e"), ((10, 10), "e")]
    guard, _ = run_turn([(10, 8)], [(10, 16)], my_hills=[(10, 10)])
    assert guard == [((10, 8), "e")]


def test_fixing6_suicide_iff_in_bot() -> None:
    # Pushing remembered hill (5, 10), the lone ant sacrifices
    # itself east; with no hill it holds -- every explore square
    # is unsafe, so no order issues at all.
    mine = [(5, 5)]
    foes = [(5, 7), (4, 4)]
    pushed, _ = run_turn(mine, foes, enemy_hills=[(5, 10)])
    assert pushed == [((5, 5), "e")]
    quiet, _ = run_turn(mine, foes)
    assert quiet == []


def test_hill_camped_counts_locals() -> None:
    # 3 campers vs 1 nearby friend holds; parity marches; an
    # empty hill always raids; distant armies do not count.
    hill = (0, 0)
    assert FX.hill_camped(hill, [(1, 1)], [(0, 2), (2, 0), (1, 3)], _dist) is True
    assert FX.hill_camped(hill, [(1, 1)], [(0, 2)], _dist) is False
    assert FX.hill_camped(hill, [(1, 1), (2, 2)], [(0, 2)], _dist) is False
    assert FX.hill_camped(hill, [(1, 1)], [], _dist) is False
    # (10, 10) sits 20 off -- beyond CAMP_RANGE -- so ten far
    # friends must not open the gate, nor ten far foes close it.
    far = [(10, 10)] * 10
    assert _dist((10, 10), hill) > FX.CAMP_RANGE
    assert FX.hill_camped(hill, [(1, 1)] + far, [(0, 2), (2, 0)], _dist) is True
    assert FX.hill_camped(hill, [(1, 1)], [(0, 2)] + far, _dist) is False


def test_camped_flood_holds_off() -> None:
    # Hill (0, 0) camps 3; only scout (10, 2) and far A (15, 15)
    # are near -- the flood holds. Seeded visits make explore step
    # s, which the flood would never pick (n/w close the 12-gap),
    # so the s order proves the gate fired.
    bot = FX.Fixing6()
    bot.visits = {(9, 2): 9, (10, 1): 9, (10, 3): 9}
    fake = FakeAnts([(10, 2), (15, 15)], [(0, 2), (2, 0), (1, 3)], enemy_hills=[(0, 0)])
    bot.do_turn(fake)
    assert ((10, 2), "s") in fake.orders


def test_uncamped_flood_marches_in() -> None:
    # Same board with one camper: 2 friends beat 1 camper, so the
    # flood marches -- first step n or w (both close the gap).
    bot = FX.Fixing6()
    bot.visits = {(9, 2): 9, (10, 1): 9, (10, 3): 9}
    fake = FakeAnts([(10, 2), (15, 15)], [(0, 2)], enemy_hills=[(0, 0)])
    bot.do_turn(fake)
    scout_orders = [d for loc, d in fake.orders if loc == (10, 2)]
    assert scout_orders and scout_orders[0] in ("n", "w")


def test_trek_toll_cedes_lost_far_meals() -> None:
    # Three foes sit on meal (5, 6) with no friend near: the army
    # at (15, 15) treks 19, so the meal is tolled and unclaimed.
    ants_list = [(15, 15), (15, 16)]
    foods = [(5, 6), (5, 7)]
    foes = [(5, 8), (6, 6), (4, 6)]
    assert FX.tolled_foods(foods, ants_list, foes, _dist) == {0, 1}
    assert FX.assign_food_targets(ants_list, foods, foes, _dist, ROWS, COLS) == {}


def test_trek_toll_spares_near_and_won_meals() -> None:
    # Lost contact but ant (5, 5) stands next to the meal: a short
    # grab is cheap, so the claim fires. A won meal claims too,
    # and meals with no foe near are never tolled.
    assert FX.tolled_foods([(5, 6)], [(5, 5)], [(5, 8)], _dist) == set()
    assert FX.assign_food_targets([(5, 5)], [(5, 6)], [(5, 8)], _dist, ROWS, COLS) == {
        0: (5, 6)
    }
    assert FX.tolled_foods([(5, 6)], [(5, 5), (15, 15)], [(5, 8)], _dist) == set()
    assert FX.tolled_foods([(5, 6)], [(15, 15)], [], _dist) == set()
    assert FX.tolled_foods([], [(15, 15)], [(5, 8)], _dist) == set()


def test_reinforce_target_walks_past_camps() -> None:
    # Pure walk: the flood owns ordered[0], so reinforce takes
    # the first open hill after it -- skipping a camped second
    # for an open third, stalling only when all are camped.
    h1, h2, h3 = (0, 0), (0, 10), (10, 10)
    assert FX.reinforce_target([h1, h2, h3], {h1: True, h2: True, h3: False}) == h3
    assert FX.reinforce_target([h1, h2], {h1: True, h2: False}) == h2
    assert FX.reinforce_target([h1], {h1: False}) == h1
    assert FX.reinforce_target([h1], {h1: True}) is None
    assert FX.reinforce_target([h1, h2, h3], {h1: True, h2: True, h3: True}) is None
    assert FX.reinforce_target([], {}) is None


def test_flood_takes_nearest_open_hill() -> None:
    # Hills (0, 0) and (0, 10) both camp 3-vs-nearby; (10, 10)
    # stands open and nearest the scout, so the flood marches
    # it directly, stepping e. (The reinforce walk past camps
    # is pinned purely above; here the flood owns the target.)
    mine = [(10, 2)]
    foes = [(0, 2), (2, 0), (1, 3)]
    hills = [(0, 0), (0, 10), (10, 10)]
    for foe in foes:
        assert _dist((10, 2), foe) > FX.SEEK_RANGE
    orders, _ = run_turn(mine, foes, enemy_hills=hills)
    assert orders == [((10, 2), "e")]


def test_wave_holds_off_lost_fight() -> None:
    # A (5, 5) pins w onto (5, 4) against four foes; C (13, 5)
    # is in wave range with C1 (19, 0) covering the raze -- but
    # the anchor counts 4 foes against 3 friends, so the wave
    # holds off and C musters hill-ward (s or w close the gap
    # to (0, 0); the wave would step n).
    mine = [(5, 5), (13, 5), (19, 0)]
    foes = [(5, 8), (6, 7), (4, 7), (4, 6)]
    for foe in foes:
        assert _dist((13, 5), foe) > FX.SEEK_RANGE
        assert _dist((19, 0), foe) > FX.SEEK_RANGE
    orders, _ = run_turn(mine, foes, enemy_hills=[(0, 0)])
    assert ((5, 5), "w") in orders
    scout_orders = [d for loc, d in orders if loc == (13, 5)]
    assert scout_orders and scout_orders[0] in ("s", "w")


def test_flood_skips_camped_for_open_second() -> None:
    # Camped (0, 0), open (10, 10) nearest the scout: the flood
    # skips the camp and marches the open second hill.
    mine = [(10, 2)]
    foes = [(0, 2), (2, 0), (1, 3)]
    hills = [(0, 0), (10, 10)]
    orders, _ = run_turn(mine, foes, enemy_hills=hills)
    assert orders == [((10, 2), "e")]


def test_two_fights_reinforce_army_nearest() -> None:
    # Two pinned lines: A1 (5, 5) holds (4, 5), A2 (15, 15)
    # holds (15, 14). The army sits north, so the anchor is
    # (4, 5); idle C (10, 2) reinforces it. Seeded visits make
    # explore step w (away from the anchor), so closing on the
    # anchor proves the wave picked the army-nearest line.
    mine = [(5, 5), (10, 2), (15, 15)]
    foes = [(5, 8), (15, 12)]
    for foe in foes:
        assert _dist((10, 2), foe) > FX.SEEK_RANGE
    orders, _ = run_turn(mine, foes, visits={(9, 2): 9, (10, 3): 9, (11, 2): 9})
    moved_c = _step_to(orders, (10, 2))
    assert moved_c is not None
    assert _dist(moved_c, (4, 5)) < _dist((10, 2), (4, 5))


def test_matches_base_outside_new_rules() -> None:
    # Differential lock: with no fights, no camps, and no lost
    # meals, Fixing6 issues exactly the base bot's orders -- the
    # entry only diverges where its rules fire.
    from typing import Any

    import Fixing as BASE

    scenarios: list[dict[str, Any]] = [
        {
            "mine": [(5, 5), (2, 2), (10, 10)],
            "enemies": [(5, 12), (2, 6), (5, 9), (10, 15)],
            "foods": [(5, 6), (2, 3)],
            "my_hills": [(10, 12)],
        },
        {
            "mine": [(5, 5), (8, 5)],
            "enemies": [],
            "enemy_hills": [(0, 0)],
        },
        {
            "mine": [(5, 5), (12, 12)],
            "enemies": [(0, 10)],
            "foods": [(5, 6)],
            "water": {(8, c) for c in range(COLS) if c != 10},
        },
        {
            "mine": [(10, 8), (12, 5)],
            "enemies": [(10, 16)],
            "enemy_hills": [(0, 0)],
            "my_hills": [(10, 10)],
        },
        {
            "mine": [(5, 5)],
            "enemies": [(15, 15)],
            "foods": [(5, 6)],
        },
        {
            "mine": [(10, 2)],
            "enemies": [],
            "enemy_hills": [(0, 0), (0, 10), (10, 10)],
        },
    ]
    for kwargs in scenarios:
        base_fake = FakeAnts(
            kwargs.get("mine", []),
            kwargs.get("enemies", []),
            kwargs.get("foods"),
            kwargs.get("water"),
            kwargs.get("enemy_hills"),
            kwargs.get("my_hills"),
        )
        BASE.Fixing().do_turn(base_fake)
        new_fake = FakeAnts(
            kwargs.get("mine", []),
            kwargs.get("enemies", []),
            kwargs.get("foods"),
            kwargs.get("water"),
            kwargs.get("enemy_hills"),
            kwargs.get("my_hills"),
        )
        FX.Fixing6().do_turn(new_fake)
        assert new_fake.orders == base_fake.orders


def test_varied_attack_radii_stay_legal() -> None:
    # Engine attack radii other than 5 rescale threat reach and
    # support discs: every variant stays legal with a live wave.
    for radius in (1, 2, 9, 25):
        mine = [(5, 5), (12, 5), (1, 1)]
        fake = FakeAnts(mine, [(5, 8)], enemy_hills=[(0, 0)])
        fake.attackradius2 = radius
        bot = FX.Fixing6()
        bot.do_turn(fake)
        _assert_legal(fake.orders, mine)
        assert len(fake.orders) == 3


def test_zero_ants_stays_quiet() -> None:
    # Elimination turn: no ants, enemies about -- no crash, no
    # orders, memory updates harmlessly.
    orders, bot = run_turn([], [(5, 5)], [(5, 6)], enemy_hills=[(0, 0)])
    assert orders == []
    assert bot.remembered_hills == {(0, 0)}


def test_engine_protocol_smoke() -> None:
    # End-to-end through the real ants.py harness: setup plus three
    # turns over a pipe (fight, hill memory, water, guards). Every
    # turn ends with go, orders stay well-formed, stderr stays
    # traceback-free. The harness never EOF-exits, so read four
    # go lines under a select-guarded deadline, then terminate.
    # Raw fd reads: select plus a buffered text stream can park
    # lines in the wrapper buffer where select never sees them.
    import os
    import select
    import subprocess

    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Fixing6.py")
    proc = subprocess.Popen(
        [sys.executable, script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None and proc.stdout is not None
    out_fd = proc.stdout.fileno()
    setup = (
        "turn 0\nloadtime 3000\nturntime 1000\nrows 20\ncols 20\n"
        "turns 500\nviewradius2 77\nattackradius2 5\nspawnradius2 1\n"
        "player_seed 42\nready\n"
    )
    turns = [
        "turn 1\nf 5 6\na 5 5 0\na 12 5 0\na 1 1 0\na 5 8 1\nh 0 0 1\nh 10 10 0\ngo\n",
        "turn 2\nf 5 6\nw 8 5\na 5 5 0\na 12 5 0\na 1 1 0\n"
        "a 5 9 1\nh 0 0 1\nh 10 10 0\ngo\n",
        "turn 3\nw 8 5\na 4 5 0\na 11 5 0\na 0 1 0\na 5 9 1\nh 0 0 1\nh 10 11 0\ngo\n",
    ]
    proc.stdin.write((setup + "".join(turns)).encode())
    proc.stdin.flush()
    pending = b""
    gos = 0
    orders = 0
    deadline = time.perf_counter() + 20.0
    while gos < 4:
        remaining = deadline - time.perf_counter()
        if remaining <= 0 or proc.poll() is not None:
            break
        ready, _, _ = select.select([out_fd], [], [], remaining)
        if not ready:
            break
        chunk = os.read(out_fd, 65536)
        if not chunk:
            break
        pending += chunk
        while b"\n" in pending:
            raw, pending = pending.split(b"\n", 1)
            line = raw.decode().strip()
            if line == "go":
                gos += 1
            elif line.startswith("o "):
                parts = line.split()
                assert len(parts) == 4 and parts[3] in ("n", "e", "s", "w")
                orders += 1
    proc.terminate()
    _, err = proc.communicate(timeout=10)
    assert gos == 4
    assert orders > 0
    assert b"Traceback" not in err


def test_random_boards_stay_legal_and_fast() -> None:
    # Seeded fuzz across ant/food/water/hill layouts: no crash,
    # every order legal, 60 crowded turns inside 6 s (10x margin
    # on the 1 s budget with the wave scan active).
    import random

    rng = random.Random(1627)
    start = time.perf_counter()
    for _ in range(60):
        spots = [(r, c) for r in range(ROWS) for c in range(COLS)]
        rng.shuffle(spots)
        mine = spots[: rng.randint(1, 30)]
        foes = spots[30 : 30 + rng.randint(0, 20)]
        foods = spots[50 : 50 + rng.randint(0, 8)]
        water = set(spots[58 : 58 + rng.randint(0, 40)])
        hills = [spots[100]] if rng.random() < 0.5 else []
        mine = [m for m in mine if m not in water]
        foes = [f for f in foes if f not in water]
        if not mine:
            continue
        fake = FakeAnts(mine, foes, foods, water, enemy_hills=hills)
        bot = FX.Fixing6()
        bot.do_turn(fake)
        _assert_legal(fake.orders, mine, water)
    assert (time.perf_counter() - start) < 6.0


def test_persistent_bot_fuzz_stays_legal() -> None:
    # One bot lives 25 turns on a shifting board, three seeds:
    # hill memory, headings, stationary pins, and visits all
    # carry over. No crash, every order legal, memory stays
    # bounded to seen squares and hills.
    import random

    for seed in (99, 1001, 4242):
        rng = random.Random(seed)
        bot = FX.Fixing6()
        mine = [(10, 10 + i) for i in range(12)]
        foes = [(12, 10 + i) for i in range(8)]
        for turn in range(25):
            foods = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(4)]
            hills = [(0, 0)] if turn % 3 else [(0, 0), (19, 19)]
            my_hills = [(19, 0)] if turn % 2 else []
            fake = FakeAnts(mine, foes, foods, enemy_hills=hills, my_hills=my_hills)
            bot.do_turn(fake)
            _assert_legal(fake.orders, mine)
            # armies drift: survivors step east, stragglers appear
            mine = [
                ((r + rng.choice([0, 0, 1])) % ROWS, (c + 1) % COLS) for r, c in mine
            ]
            foes = [((r + rng.choice([0, -1])) % ROWS, (c - 1) % COLS) for r, c in foes]
        assert len(bot.remembered_hills) <= 2
        assert len(bot.prev_enemies) <= 8


def test_big_map_turn_under_1s() -> None:
    # 60x60 water-maze, 150 ants, 60 foes, food, hills, guards:
    # the full stack (fixing + wave + camp + toll) finishes far
    # inside the 1 s turn budget.
    import random

    big_rows, big_cols = 60, 60
    rng = random.Random(5)
    mine = [(rng.randrange(big_rows), rng.randrange(big_cols)) for _ in range(150)]
    foes = [(rng.randrange(big_rows), rng.randrange(big_cols)) for _ in range(60)]
    foods = [(rng.randrange(big_rows), rng.randrange(big_cols)) for _ in range(20)]
    water = {
        (r, c) for r in range(big_rows) for c in range(big_cols) if (r + c) % 17 == 0
    }
    mine = [m for m in mine if m not in water]
    foes = [f for f in foes if f not in water]

    class BigAnts(FakeAnts):
        def __init__(self):
            self.rows = big_rows
            self.cols = big_cols
            self.attackradius2 = 5
            self._mine = list(mine)
            self._enemies = list(foes)
            self._foods = list(foods)
            self._water = set(water)
            self._enemy_hills = [(0, 0), (59, 59)]
            self._my_hills = [(30, 30)]
            self.orders = []

    fake = BigAnts()
    bot = FX.Fixing6()
    start = time.perf_counter()
    bot.do_turn(fake)
    assert (time.perf_counter() - start) < 1.0
    _assert_legal(fake.orders, list(mine), water, big_rows, big_cols)
    assert len(fake.orders) > 0


def test_fixing6_fight_under_10ms_and_turn_under_1s() -> None:
    # A 24v24 pile-up resolves far inside 10 ms, and a full
    # crowded turn (48 ants, food, hills, guards) finishes far
    # inside 1 s -- the new rules add only linear scans.
    ours = [(i % ROWS, (i * 7) % COLS) for i in range(24)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(24)]

    def _dest(loc: Loc, direction: str) -> Loc:
        dr, dc = AIM[direction]
        return ((loc[0] + dr) % ROWS, (loc[1] + dc) % COLS)

    def _allow(loc: Loc) -> bool:
        return True

    start = time.perf_counter()
    plan = FX.resolve_fight(
        ours,
        foes,
        [],
        ROWS,
        COLS,
        5,
        [(0, 0)],
        _dist,
        _dest,
        _allow,
        _allow,
        None,
    )
    assert (time.perf_counter() - start) < 0.010
    assert isinstance(plan, dict)
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    many = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [((i * 3 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(12)]
    start = time.perf_counter()
    orders, _ = run_turn(
        mine,
        many,
        foods,
        enemy_hills=[(0, 0), (19, 19)],
        my_hills=[(10, 10), (3, 3)],
    )
    assert (time.perf_counter() - start) < 1.0
    assert len(orders) > 0
