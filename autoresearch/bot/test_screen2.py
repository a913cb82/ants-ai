#!/usr/bin/env python
"""Combat-program shared tests (leg 1 of 10: Seek).

No engine games. These tests persist across combat legs alongside
``combat.py``; entry bots stay thin and import the shared helpers.

Leg 1 implements the RESEARCH.md row "Approach forms fighting
lines" (xathis approaching enemies): an ant with no food move and
no guard move, whose nearest visible enemy is within SEEK_RANGE
steps, advances one step toward that enemy via the existing
first_step pathing with the normal safety filter. Everything else
matches champion Denial byte-for-byte.

Leg 2 implements the RESEARCH.md row "Committed-join pack attacks"
(pas11 potential_orders): a seek step landing in attack range of a
foe queues as a commitment, and when 2+ ants commit to the SAME foe
this turn both orders issue with equal trades allowed (no 14-near
gate). Lone unjoined contact steps fall back to champion safety.

Leg 3 implements the RESEARCH.md row "Focus battle: 1v1 is mutual
death, trade down": a friendless 1v1 contact step (no friend in
attack range of the step, exactly one foe) engages only when the
visible army strictly outnumbers theirs, via combat.grinder_release.
Behind or even lone ants hold exactly as champion; joined pairs
still engage regardless of the army count.

Leg 4 implements the RESEARCH.md row "Screen: intercept razers off
the hill": the first guard still holds the threatened hill, but
extra guards march to combat.intercept_square -- the passable
square halfway between the hill and its nearest enemy -- instead
of onto the hill, so the hill stays spawnable. Unthreatened
hills, first guards, and everything else match champion exactly.

Leg 5 implements the RESEARCH.md row "Odds: equal trades at 10"
(and "Aggression gate tuning: 14 is not gospel"): the safety
filter accepts equal trades (friends + 1 == enemies) with
combat.EQUAL_TRADE_NEAR (10) near friends instead of champion's
14. Strict superiority, grinder 1v1s, join packs, and everything
else match champion exactly.

Leg 6 implements the RESEARCH.md row "Gang: hunt only with a
pack": an ant advances on a nearby enemy only with 3+ friends
within 10 steps (combat.has_pack); a packless ant packs up one
step toward its nearest friend instead of advancing. Packed ants
seek exactly as leg 1; join, grinder, screen, and the 10-gate
stay as the legs defined them.

Leg 7 implements the RESEARCH.md row "Crowd: fearless under ten
enemies": hunters press small fights and survive big ones. When
fewer than combat.CROWD_LIMIT (10) enemies are visible, a packed
advancing move skips the safety filter (fearless ahead); with 10+
enemies visible the full champion safety applies. Food, guard,
muster, reinforce, and explore keep their existing filters.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import combat as CX  # noqa: E402

# Leg 7: Crowd.py carries the same seek + join + grinder + screen
# + odds + gang wiring; CP aliases the live Crowd entry.
import Screen2 as HP  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], HP.Screen2]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = HP.Screen2()
    bot.do_turn(fake)
    return fake.orders, bot


def run_grinder_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], HP.Screen2]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = HP.Screen2()
    bot.do_turn(fake)
    return fake.orders, bot


def _no_seek(ant_loc: Loc, enemy_locs: list[Loc], distance: CX.DistFn) -> Loc | None:
    # Champion stand-in: no enemy is ever worth chasing, so the seek
    # branch degrades to the champion fall-through exactly.
    return None


def champion_orders(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    orig = CX.nearest_seek_enemy
    CX.nearest_seek_enemy = _no_seek
    try:
        orders, _ = run_turn(mine, enemies, foods, water, enemy_hills, my_hills)
    finally:
        CX.nearest_seek_enemy = orig
    return orders


def test_nearest_seek_enemy_picks_nearest_in_range() -> None:
    probe = FakeAnts([(5, 5)], [])
    assert CX.SEEK_RANGE == 8
    found = CX.nearest_seek_enemy((5, 5), [(5, 10), (5, 7)], probe.distance)
    assert found == (5, 7)
    assert CX.nearest_seek_enemy((5, 5), [(5, 13)], probe.distance) == (5, 13)
    assert CX.nearest_seek_enemy((5, 5), [(5, 14)], probe.distance) is None
    assert CX.nearest_seek_enemy((5, 5), [], probe.distance) is None
    tied = CX.nearest_seek_enemy((5, 5), [(5, 8), (5, 2)], probe.distance)
    assert tied == (5, 8)


def test_idle_ant_near_enemy_steps_toward_it() -> None:
    # No food, no hills: the packed ant at (5, 5) with an enemy 5
    # steps east must advance east instead of exploring north as
    # champion. (Gang, leg 6: a lone ant no longer seeks, so this
    # leg-1 board carries three friends in range.)
    mine = [(5, 5), (5, 3), (5, 4), (6, 5)]
    enemies = [(5, 10)]
    orders, _ = run_turn(mine, enemies)
    assert orders[0] == ((5, 5), "e")
    probe = FakeAnts(mine, enemies)
    assert probe.distance((5, 5), (5, 10)) == 5
    moved = probe.destination((5, 5), orders[0][1])
    assert probe.distance(moved, (5, 10)) == 4


def test_idle_ant_far_enemy_explores_as_champion() -> None:
    # Enemy 9 steps out is beyond SEEK_RANGE: explore north exactly
    # as champion, with or without enemies on the board.
    mine = [(5, 5)]
    enemies = [(5, 14)]
    orders, _ = run_turn(mine, enemies)
    bare, _ = run_turn(mine, [])
    assert orders == bare == [((5, 5), "n")]
    assert orders == champion_orders(mine, enemies)


def test_food_guard_orders_unchanged_on_contested_board() -> None:
    # Contested cluster (3 enemies near two foods): two ants take
    # denial food steps, the third guards its threatened hill. All
    # three match champion even with enemies in seek range.
    mine = [(5, 5), (2, 2), (10, 10)]
    foods = [(5, 6), (2, 3)]
    enemies = [(5, 12), (2, 6), (5, 9), (10, 15)]
    orders, _ = run_turn(mine, enemies, foods, my_hills=[(10, 12)])
    assert orders == [((5, 5), "e"), ((2, 2), "e"), ((10, 10), "e")]
    champ = champion_orders(mine, enemies, foods, my_hills=[(10, 12)])
    assert orders == champ


def test_packed_group_musters_as_champion() -> None:
    # A packed group in muster range marches on the remembered
    # hill: every step shortens the road and every order matches
    # champion (seek out of range, no guards, roads resolve inside
    # the BFS budget). (Horde leg 8: muster needs the pack; a lone
    # ant here explores instead -- see
    # test_packless_ant_skips_muster_and_explores.)
    mine = [(10, 10), (10, 12), (12, 10), (12, 12)]
    enemies = [(2, 2)]
    orders, _ = run_turn(mine, enemies, enemy_hills=[(12, 14)])
    champ = champion_orders(mine, enemies, enemy_hills=[(12, 14)])
    assert len(orders) == 4 and orders == champ
    probe = FakeAnts(mine, enemies)
    for loc, direction in orders:
        assert probe.distance(
            probe.destination(loc, direction), (12, 14)
        ) < probe.distance(loc, (12, 14))


def test_seek_scan_under_1ms_on_crowded_board() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(10)]
    probe = FakeAnts(mine, foes)
    reps = 50
    start = time.perf_counter()
    for _ in range(reps):
        for ant in mine:
            CX.nearest_seek_enemy(ant, foes, probe.distance)
    elapsed = (time.perf_counter() - start) / reps
    assert elapsed < 0.001
    assert CX.nearest_seek_enemy(mine[0], foes, probe.distance) is not None


_SQ_R2 = 5


def _sq(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


def test_contact_foe_nearest_in_attack_range() -> None:
    assert CX.contact_foe((5, 6), [(5, 7), (5, 9)], _sq, _SQ_R2) == (5, 7)
    assert CX.contact_foe((5, 6), [(5, 12)], _sq, _SQ_R2) is None
    assert CX.contact_foe((5, 6), [], _sq, _SQ_R2) is None


def test_joined_attackers_releases_only_shared_foes() -> None:
    assert CX.joined_attackers({}) == set()
    assert CX.joined_attackers({0: (5, 7)}) == set()
    assert CX.joined_attackers({0: (5, 7), 1: (5, 7)}) == {0, 1}
    split = {0: (5, 7), 1: (5, 7), 2: (9, 9)}
    assert CX.joined_attackers(split) == {0, 1}
    trio = {0: (5, 7), 1: (5, 7), 2: (5, 7)}
    assert CX.joined_attackers(trio) == {0, 1, 2}


def test_committed_pair_engages_through_equal_trade_gate() -> None:
    # Two ants flank one foe: both seek steps land in attack range,
    # so the join releases both even though neither has 14 friends
    # near (champion demands 14 for equal trades, so both retreat).
    # (Gang, leg 6: the pair carries two packed fillers -- a lone
    # pair now packs up instead of seeking.)
    mine = [(5, 5), (5, 9), (5, 1), (5, 13)]
    enemies = [(5, 7)]
    orders, _ = run_turn(mine, enemies)
    assert orders[0] == ((5, 5), "e")
    assert orders[1] == ((5, 9), "w")
    champ = champion_orders(mine, enemies)
    assert champ[0] == ((5, 5), "w")
    assert champ[1] == ((5, 9), "e")
    assert orders != champ


def test_lone_ant_without_joiner_holds_as_champion() -> None:
    # One ant, one adjacent foe: no buddy commits, so the unsafe
    # contact step falls back to champion behavior exactly.
    mine = [(5, 5)]
    enemies = [(5, 7)]
    orders, _ = run_turn(mine, enemies)
    assert orders == champion_orders(mine, enemies) == [((5, 5), "w")]
    assert ((5, 5), "e") not in orders


def test_three_ants_split_across_two_foes() -> None:
    # The flanking pair joins on their shared foe while the lone ant
    # on the second foe holds exactly as champion. (Gang, leg 6: the
    # pair carries two packed fillers, and the packless loner's
    # pack-up step fails safety here, so it still explores exactly
    # as champion. The join itself ignores the army count.)
    mine = [(5, 5), (5, 9), (15, 15), (5, 3), (5, 11)]
    enemies = [(5, 7), (15, 17), (0, 0)]
    orders, _ = run_turn(mine, enemies)
    champ = champion_orders(mine, enemies)
    assert orders[0] == ((5, 5), "e")
    assert orders[1] == ((5, 9), "w")
    assert orders[2] == champ[2]
    assert orders != champ


def test_pairing_costs_under_1ms_on_crowded_board() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(10)]
    probe = FakeAnts(mine, foes)
    reps = 50
    start = time.perf_counter()
    for _ in range(reps):
        commitments: dict[int, Loc] = {}
        for ai, ant in enumerate(mine):
            foe = CX.nearest_seek_enemy(ant, foes, probe.distance)
            if foe is None:
                continue
            dest = probe.destination(ant, "e")
            contact = CX.contact_foe(dest, foes, _sq, _SQ_R2)
            if contact is not None:
                commitments[ai] = contact
        CX.joined_attackers(commitments)
    elapsed = (time.perf_counter() - start) / reps
    assert elapsed < 0.001


def test_grinder_release_only_ahead_lone_duels() -> None:
    # Ahead friendless 1v1 engages; even, behind, backed, crowded,
    # or contact-free steps refuse exactly as champion does today.
    assert CX.grinder_release(0, 1, 5, 3) is True
    assert CX.grinder_release(0, 1, 3, 3) is False
    assert CX.grinder_release(0, 1, 2, 4) is False
    assert CX.grinder_release(1, 1, 5, 3) is False
    assert CX.grinder_release(0, 2, 9, 3) is False
    assert CX.grinder_release(0, 0, 9, 3) is False


def test_ahead_lone_ant_engages_1v1() -> None:
    # 3v1 visible army: the contact ant at (5, 5) has no friend in
    # range of its step onto (5, 6), but the army leads, so Grinder
    # engages east where champion retreats west. (Gang, leg 6: the
    # duelist carries three packed friends outside contact range --
    # pals stays 0 so the gate still fires; a truly lone duelist
    # now packs up.)
    mine = [(5, 5), (15, 15), (15, 16), (5, 2), (5, 1), (5, 0)]
    enemies = [(5, 7)]
    orders, _ = run_grinder_turn(mine, enemies)
    assert orders[0] == ((5, 5), "e")
    champ = champion_orders(mine, enemies)
    assert champ[0] == ((5, 5), "w")
    assert orders != champ


def test_behind_lone_ant_holds_as_champion() -> None:
    # 1v3 visible army: the friendless contact refuses exactly as
    # champion, retreating west instead of engaging east.
    mine = [(5, 5)]
    enemies = [(5, 7), (10, 10), (10, 11)]
    orders, _ = run_grinder_turn(mine, enemies)
    assert orders == champion_orders(mine, enemies) == [((5, 5), "w")]
    assert ((5, 5), "e") not in orders


def test_even_lone_ant_holds_as_champion() -> None:
    # 1v1 visible army is not ahead: strictly-greater gate refuses,
    # so the lone ant holds exactly as champion.
    mine = [(5, 5)]
    enemies = [(5, 7)]
    orders, _ = run_grinder_turn(mine, enemies)
    assert orders == champion_orders(mine, enemies) == [((5, 5), "w")]
    assert ((5, 5), "e") not in orders


def test_joined_pair_engages_even_when_behind() -> None:
    # The join ignores the army gate: the flanking pair shares one
    # foe, so both engage though the visible army trails 5v6. (Gang,
    # leg 6: the pair carries two packed fillers, and two far enemies
    # hold the trail -- a lone pair now packs up.)
    mine = [(5, 5), (5, 9), (0, 0), (5, 3), (5, 11)]
    enemies = [(5, 7), (0, 10), (0, 11), (0, 12), (19, 19), (19, 18)]
    orders, _ = run_grinder_turn(mine, enemies)
    assert orders[0] == ((5, 5), "e")
    assert orders[1] == ((5, 9), "w")
    champ = champion_orders(mine, enemies)
    assert champ[0] != orders[0] and champ[1] != orders[1]


def test_food_guard_orders_unchanged_when_army_ahead() -> None:
    # Ahead 5v4 army on the contested cluster: claims and guards
    # resolve before the seek branch, so Grinder matches champion
    # on every order even with the gate open elsewhere. The extras
    # stand by the threatened hill, so their screen steps stay in
    # first_step range and never fall through to seek.
    mine = [(5, 5), (2, 2), (10, 10), (12, 12), (12, 14)]
    foods = [(5, 6), (2, 3)]
    enemies = [(5, 12), (2, 6), (5, 9), (10, 15)]
    orders, _ = run_grinder_turn(mine, enemies, foods, my_hills=[(10, 12)])
    champ = champion_orders(mine, enemies, foods, my_hills=[(10, 12)])
    assert orders == champ
    assert orders[0] == ((5, 5), "e")
    assert orders[1] == ((2, 2), "e")


def test_grinder_gate_under_half_ms_on_crowded_board() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(10)]
    reps = 50
    start = time.perf_counter()
    for _ in range(reps):
        for _ant in mine:
            CX.grinder_release(0, 1, len(mine), len(foes))
    elapsed = (time.perf_counter() - start) / reps
    assert elapsed < 0.0005


def test_intercept_square_is_halfway_to_nearest_foe() -> None:
    # The screen meets the razer off the hill: halfway between the
    # hill and its nearest enemy, on an open board the midpoint.
    probe = FakeAnts([], [])
    mid = CX.intercept_square(
        (10, 10), [(10, 16)], probe.distance, probe.passable, ROWS, COLS
    )
    assert mid == (10, 13)
    assert (
        CX.intercept_square((10, 10), [], probe.distance, probe.passable, ROWS, COLS)
        is None
    )
    # Nearest of several foes sets the approach, not the first foe.
    near = CX.intercept_square(
        (10, 10),
        [(10, 18), (10, 12)],
        probe.distance,
        probe.passable,
        ROWS,
        COLS,
    )
    assert near == (10, 11)


def test_intercept_square_skirts_water() -> None:
    # A flooded midpoint falls back to the nearest passable square,
    # one step away, never onto water.
    probe = FakeAnts([], [], water={(10, 13)})
    found = CX.intercept_square(
        (10, 10), [(10, 16)], probe.distance, probe.passable, ROWS, COLS
    )
    assert found is not None
    assert found != (10, 13)
    assert probe.passable(found)
    assert probe.distance(found, (10, 13)) == 1


def test_second_guard_screens_off_hill() -> None:
    # (a) The extra guard marches east to the (10, 13) intercept,
    # not west onto the (10, 10) hill it would pile onto.
    mine = [(10, 8), (10, 11)]
    enemies = [(10, 16)]
    hill = (10, 10)
    probe = FakeAnts(mine, enemies)
    inter = CX.intercept_square(
        hill, enemies, probe.distance, probe.passable, ROWS, COLS
    )
    assert inter == (10, 13) and inter != hill
    orders, _ = run_turn(mine, enemies, my_hills=[hill])
    assert orders[0] == ((10, 8), "e")
    assert orders[1] == ((10, 11), "e")
    assert orders[1] != ((10, 11), "w")


def test_first_guard_holds_hill_as_champion() -> None:
    # (b) The holder still steps onto the hill exactly as champion,
    # alone or ahead of a screener.
    mine = [(10, 8)]
    enemies = [(10, 16)]
    orders, _ = run_turn(mine, enemies, my_hills=[(10, 10)])
    assert orders == [((10, 8), "e")]
    assert orders == champion_orders(mine, enemies, my_hills=[(10, 10)])
    pair, _ = run_turn([(10, 8), (10, 11)], enemies, my_hills=[(10, 10)])
    assert pair[0] == orders[0]


def test_no_threat_turn_matches_champion() -> None:
    # (c) Unthreatened hill with a far enemy: Screen == champion.
    mine = [(10, 8), (10, 11), (5, 5)]
    enemies = [(0, 0)]
    orders, _ = run_turn(mine, enemies, my_hills=[(10, 10)])
    assert orders == champion_orders(mine, enemies, my_hills=[(10, 10)])


def test_intercept_costs_under_1ms_on_crowded_board() -> None:
    # (d) Three threatened hills screened against ten foes, well
    # under 1ms per intercept on average.
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(10)]
    hills = [(10, 10), (3, 17), (15, 4)]
    probe = FakeAnts([], foes)
    reps = 50
    start = time.perf_counter()
    for _ in range(reps):
        for hill in hills:
            CX.intercept_square(hill, foes, probe.distance, probe.passable, ROWS, COLS)
    elapsed = (time.perf_counter() - start) / (reps * len(hills))
    assert elapsed < 0.001


def champion14_orders(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    # True champion Denial: Odds differs from the staged champion
    # only in the equal-trade near gate, so patching
    # combat.EQUAL_TRADE_NEAR back to 14 reproduces the champion
    # safety filter exactly (unlike champion_orders, seek stays on).
    orig = CX.EQUAL_TRADE_NEAR
    CX.EQUAL_TRADE_NEAR = 14
    try:
        orders, _ = run_turn(mine, enemies, foods, water, enemy_hills, my_hills)
    finally:
        CX.EQUAL_TRADE_NEAR = orig
    return orders


# Leg 5 boards: ant (5, 5) eyes the step east onto (5, 6) against
# two foes (5, 7) and (5, 8): enemies 2, backing friend (5, 4) in
# attack range, so friends + 1 == enemies -- a pure equal trade.
# The backer holds a food claim on (5, 3) so the join pre-pass
# skips it and the step stays unjoined; fillers sit within 10
# steps (near) but outside attack range (sq > 5) of (5, 6).
_ODDS_FOES = [(5, 7), (5, 8)]
_ODDS_BACK = (5, 4)
_ODDS_FOOD = [(5, 3)]
_ODDS_FILLERS = [
    (5, 0),
    (5, 1),
    (5, 2),
    (4, 0),
    (4, 1),
    (4, 2),
    (4, 3),
    (6, 0),
    (6, 1),
    (6, 2),
    (6, 3),
]
# Leg 7: the odds boards carry 2 near foes, a small fight Crowd
# hunts fearlessly -- so they are padded to 10 visible enemies
# (crowd gate closed) to keep discriminating the 10-gate from the
# 14-gate. Every pad foe sits beyond SEEK_RANGE of each hunter,
# beyond CLUSTER_R of the food (claims unchanged), and outside
# attack range of every candidate step.
_ODDS_FAR = [
    (15, 15),
    (15, 16),
    (15, 14),
    (14, 15),
    (16, 15),
    (16, 16),
    (12, 12),
    (13, 13),
]
_ODDS_TEN = _ODDS_FOES + _ODDS_FAR
_ODDS_MINE_12 = [(5, 5), _ODDS_BACK] + _ODDS_FILLERS
_ODDS_MINE_9 = [(5, 5), _ODDS_BACK] + _ODDS_FILLERS[:8]


def test_equal_trade_gate_constant_is_ten() -> None:
    # (gate) The equal-trade near gate lives in combat as a named
    # constant: 10, down from champion's tuned 14.
    assert CX.EQUAL_TRADE_NEAR == 10


def test_twelve_near_accepts_equal_trade_champion_refuses() -> None:
    # (a) 12 near friends: Odds engages east onto (5, 6) while the
    # 14-gate champion refuses and explores north instead.
    orders, _ = run_turn(_ODDS_MINE_12, _ODDS_TEN, _ODDS_FOOD)
    assert orders[0] == ((5, 5), "e")
    champ = champion14_orders(_ODDS_MINE_12, _ODDS_TEN, _ODDS_FOOD)
    assert champ[0] == ((5, 5), "n")
    assert orders[0] != champ[0]


def test_nine_near_refuses_exactly_as_champion() -> None:
    # (b) 9 near friends: below both gates, so every order matches
    # the 14-gate champion and nobody steps east into the trade.
    orders, _ = run_turn(_ODDS_MINE_9, _ODDS_TEN, _ODDS_FOOD)
    champ = champion14_orders(_ODDS_MINE_9, _ODDS_TEN, _ODDS_FOOD)
    assert orders == champ
    assert orders[0] != ((5, 5), "e")


def test_strict_superiority_engages_under_both_gates() -> None:
    # (c1) 3 backing friends vs 1 foe: strict superiority accepts
    # under either gate, so Gang and champion agree east. (Gang,
    # leg 6: the third backer packs the trio, so the gate never
    # fires on this board.)
    mine = [(5, 5), (5, 4), (4, 6), (5, 3)]
    enemies = [(5, 7)]
    orders, _ = run_turn(mine, enemies)
    champ = champion14_orders(mine, enemies)
    assert orders == champ
    assert orders[0] == ((5, 5), "e")


def test_losing_trade_refuses_under_both_gates() -> None:
    # (c2) Friendless ant facing 3 foes: strictly losing, so Odds
    # and champion both refuse and agree on every order.
    mine = [(5, 5)]
    enemies = [(5, 7), (5, 8), (6, 7)]
    orders, _ = run_turn(mine, enemies)
    champ = champion14_orders(mine, enemies)
    assert orders == champ
    assert orders[0] != ((5, 5), "e")


def test_equal_trade_gate_costs_under_half_ms_on_crowded_board() -> None:
    # (d) The gate predicate itself -- the only new arithmetic --
    # costs far under 0.5ms per crowded-board pass.
    counts = [(i % 14, i % 3, (i * 7) % 3) for i in range(48)]
    reps = 2000
    start = time.perf_counter()
    for _ in range(reps):
        for near, friends, enemies in counts:
            _ = friends + 1 > enemies or (
                near >= CX.EQUAL_TRADE_NEAR and friends + 1 >= enemies
            )
    elapsed = (time.perf_counter() - start) / reps
    assert elapsed < 0.0005


def run_gang_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], object]:
    # The Gang entry files are gone; Crowd carries its wiring, so
    # the gang boards run on Crowd exactly.
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = HP.Screen2()
    bot.do_turn(fake)
    return fake.orders, bot


def test_has_pack_needs_three_friends_in_ten() -> None:
    # (pure) Solo and paired ants have no pack; three friends in
    # range do. The ant itself never counts, and friends past 10
    # steps do not count.
    probe = FakeAnts([(5, 5)], [])
    assert CX.has_pack((5, 5), [(5, 5)], probe.distance) is False
    assert CX.has_pack((5, 5), [(5, 5), (5, 2)], probe.distance) is False
    assert CX.has_pack((5, 5), [(5, 5), (5, 2), (5, 3)], probe.distance) is False
    three = [(5, 5), (5, 2), (5, 3), (6, 5)]
    assert CX.has_pack((5, 5), three, probe.distance) is True
    far = [(5, 5), (5, 2), (5, 3), (15, 15)]
    assert CX.has_pack((5, 5), far, probe.distance) is False
    edge = [(5, 5), (5, 2), (5, 3), (5, 15)]
    assert CX.has_pack((5, 5), edge, probe.distance) is True
    assert CX.has_pack((5, 5), three, probe.distance, need=3, radius=10) is True


def test_packless_ant_packs_up_toward_friend() -> None:
    # (a) One friend is no pack: the ant at (5, 5) eyes an enemy 5
    # steps east but steps west toward its friend at (5, 2) --
    # closer to the friend, farther from the enemy, never east.
    mine = [(5, 5), (5, 2)]
    enemies = [(5, 10)]
    orders, _ = run_gang_turn(mine, enemies)
    assert orders[0] == ((5, 5), "w")
    probe = FakeAnts(mine, enemies)
    moved = probe.destination((5, 5), orders[0][1])
    assert probe.distance(moved, (5, 2)) < probe.distance((5, 5), (5, 2))
    assert probe.distance(moved, (5, 10)) > probe.distance((5, 5), (5, 10))


def test_packed_ant_seeks_exactly_as_leg1() -> None:
    # (b) Three friends in range: the ant advances east onto (5, 6),
    # one step nearer the enemy, exactly the leg-1 seek order.
    mine = [(5, 5), (5, 3), (5, 4), (6, 5)]
    enemies = [(5, 10)]
    orders, _ = run_gang_turn(mine, enemies)
    assert orders[0] == ((5, 5), "e")
    probe = FakeAnts(mine, enemies)
    moved = probe.destination((5, 5), orders[0][1])
    assert probe.distance(moved, (5, 10)) == 4


def test_pack_boundary_three_seeks_two_packs_up() -> None:
    # (c) Exactly 3 friends in range seeks east; 2 packs up west
    # toward the nearest friend.
    enemies = [(5, 10)]
    three = [(5, 5), (5, 0), (5, 1), (5, 2)]
    orders, _ = run_gang_turn(three, enemies)
    assert orders[0] == ((5, 5), "e")
    two = [(5, 5), (5, 0), (5, 1)]
    orders2, _ = run_gang_turn(two, enemies)
    assert orders2[0] == ((5, 5), "w")


def test_pack_check_costs_under_1ms_on_crowded_board() -> None:
    # (d) The pack check over all 48 ants costs under 1ms per pass
    # on a crowded board.
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(10)]
    probe = FakeAnts(mine, foes)
    reps = 50
    start = time.perf_counter()
    for _ in range(reps):
        for ant in mine:
            CX.has_pack(ant, mine, probe.distance)
    elapsed = (time.perf_counter() - start) / reps
    assert elapsed < 0.001


def run_crowd_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], HP.Screen2]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = HP.Screen2()
    bot.do_turn(fake)
    return fake.orders, bot


def safe_orders(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    # Gang-equivalent baseline on the Crowd code: force the crowd
    # gate closed so the full champion safety filter applies to
    # every advancing move, exactly as legs 1-6 behave.
    orig = CX.CROWD_LIMIT
    CX.CROWD_LIMIT = 0
    try:
        orders, _ = run_crowd_turn(mine, enemies, foods, water, enemy_hills, my_hills)
    finally:
        CX.CROWD_LIMIT = orig
    return orders


# Leg 7 boards: packed ant (5, 5) with three friends at (5, 1),
# (5, 2), (5, 3) eyes the step east onto (5, 6) against two near
# foes (5, 7) and (5, 8): two enemies in attack range, no friend
# backing the step, only 3 near friends -- unsafe under every
# earlier leg (a lone commitment draws no join partner, two foes
# refuse the grinder 1v1 gate, 3 near friends refuse the 10-gate),
# so the safe baseline holds and explores north instead of
# engaging. Far foes pad the visible
# count without touching safety: all sit beyond SEEK_RANGE of the
# hunter and outside attack range of every candidate step.
_CROWD_MINE = [(5, 5), (5, 2), (5, 3), (5, 1)]
_CROWD_NEAR = [(5, 7), (5, 8)]
_CROWD_FAR_POOL = [
    (15, 15),
    (15, 16),
    (15, 14),
    (14, 15),
    (16, 15),
    (16, 16),
    (0, 0),
    (0, 1),
    (19, 19),
    (19, 18),
]


def test_crowd_limit_constant_is_ten() -> None:
    # (gate) The fearless horizon lives in combat as a named
    # constant: 10 visible enemies, from the RESEARCH.md row.
    assert CX.CROWD_LIMIT == 10


def test_crowd_fearless_boundary() -> None:
    # (pure) Fewer than 10 visible enemies is fearless; 10+ is
    # safe. The boundary sits between 9 and 10 exactly.
    assert CX.crowd_fearless(0) is True
    assert CX.crowd_fearless(3) is True
    assert CX.crowd_fearless(9) is True
    assert CX.crowd_fearless(10) is False
    assert CX.crowd_fearless(11) is False
    assert CX.crowd_fearless(12) is False


def test_three_enemies_advance_fearlessly_where_safe_holds() -> None:
    # (a) 3 enemies visible: the packed hunter steps east into the
    # 1v2 contact fearlessly, where the safe baseline refuses and
    # explores north instead.
    enemies = _CROWD_NEAR + _CROWD_FAR_POOL[:1]
    assert len(enemies) == 3
    orders, _ = run_crowd_turn(_CROWD_MINE, enemies)
    assert orders[0] == ((5, 5), "e")
    safe = safe_orders(_CROWD_MINE, enemies)
    assert safe[0] == ((5, 5), "n")
    assert orders != safe


def test_twelve_enemies_hold_exactly_as_safe() -> None:
    # (b) 12 enemies visible: the same hunter holds exactly as the
    # safe baseline -- full champion safety, never east.
    enemies = _CROWD_NEAR + _CROWD_FAR_POOL[:10]
    assert len(enemies) == 12
    orders, _ = run_crowd_turn(_CROWD_MINE, enemies)
    assert orders == safe_orders(_CROWD_MINE, enemies)
    assert orders[0] != ((5, 5), "e")


def test_crowd_boundary_nine_fearless_ten_safe() -> None:
    # (c) 9 visible enemies advance east; 10 hold exactly as safe.
    nine = _CROWD_NEAR + _CROWD_FAR_POOL[:7]
    assert len(nine) == 9
    orders9, _ = run_crowd_turn(_CROWD_MINE, nine)
    assert orders9[0] == ((5, 5), "e")
    assert orders9 != safe_orders(_CROWD_MINE, nine)
    ten = _CROWD_NEAR + _CROWD_FAR_POOL[:8]
    assert len(ten) == 10
    orders10, _ = run_crowd_turn(_CROWD_MINE, ten)
    assert orders10 == safe_orders(_CROWD_MINE, ten)
    assert orders10[0] != ((5, 5), "e")


def test_crowd_count_costs_under_half_ms_on_crowded_board() -> None:
    # (d) The visible-count check -- the only new arithmetic on the
    # seek path -- costs far under 0.5ms per crowded-board pass.
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(12)]
    reps = 2000
    start = time.perf_counter()
    for _ in range(reps):
        for _ in range(48):
            _ = CX.crowd_fearless(len(foes), CX.CROWD_LIMIT)
    elapsed = (time.perf_counter() - start) / reps
    assert elapsed < 0.0005


def test_crowd_food_guard_orders_unchanged_when_few_enemies() -> None:
    # (e) The gate touches the seek path only: with 4 enemies
    # visible (fearless elsewhere), food claims and hill guards
    # resolve exactly as the safe baseline on every order.
    mine = [(5, 5), (2, 2), (10, 10)]
    foods = [(5, 6), (2, 3)]
    enemies = [(5, 12), (2, 6), (5, 9), (10, 15)]
    orders, _ = run_crowd_turn(mine, enemies, foods, my_hills=[(10, 12)])
    assert orders == safe_orders(mine, enemies, foods, my_hills=[(10, 12)])
    assert orders == [((5, 5), "e"), ((2, 2), "e"), ((10, 10), "e")]


# Leg 8 (Horde): march only with a pack. A lone ant marching on a
# remembered hill donates across the map; the Flood muster and the
# reinforce branches therefore require combat.march_with_pack --
# 3+ friends within 10 steps, the same pack as the seek gate. A
# packless ant skips both hill branches and explores instead.
# Food, guard, seek, and walk-off are untouched.


def run_horde_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], HP.Screen2]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = HP.Screen2()
    bot.do_turn(fake)
    return fake.orders, bot


def test_march_with_pack_gate() -> None:
    # (a) The march gate pins the rule: packless ants hold, packed
    # ants march; near misses (2 friends, far friends) hold.
    probe = FakeAnts([(5, 5)], [])
    assert CX.march_with_pack((5, 5), [(5, 5)], probe.distance) is False
    packed = [(5, 5), (5, 7), (7, 5), (7, 7)]
    assert CX.march_with_pack((5, 5), packed, probe.distance) is True
    pair = [(5, 5), (5, 7), (7, 5)]
    assert CX.march_with_pack((5, 5), pair, probe.distance) is False
    far = [(5, 5), (5, 17), (17, 5), (17, 17)]
    assert CX.march_with_pack((5, 5), far, probe.distance) is False


def test_packless_ant_skips_muster_and_explores() -> None:
    # (b) A lone ant with a remembered hill east explores north
    # instead of marching east onto the hill road as champion.
    # Hill (5, 12) is 7 steps due east: the ungated muster step is
    # uniquely "e" (every detour is longer), so explore "n" proves
    # the gate fired.
    mine = [(5, 5)]
    orders, _ = run_horde_turn(mine, [], enemy_hills=[(5, 12)])
    assert orders == [((5, 5), "n")]
    probe = FakeAnts(mine, [])
    assert probe.distance((5, 5), (5, 12)) == 7
    moved = probe.destination((5, 5), orders[0][1])
    assert probe.distance(moved, (5, 12)) == 8


def test_packed_ants_march_on_hill() -> None:
    # (c) A packed group marches exactly as champion: every order
    # shortens the distance to the remembered hill.
    mine = [(5, 5), (5, 7), (7, 5), (7, 7)]
    hill = (5, 12)
    orders, _ = run_horde_turn(mine, [], enemy_hills=[hill])
    assert len(orders) == 4
    probe = FakeAnts(mine, [])
    for loc, direction in orders:
        assert probe.distance(probe.destination(loc, direction), hill) < probe.distance(
            loc, hill
        )


def test_packless_ant_still_takes_food_and_guards() -> None:
    # (d) The gate touches the hill branches only: a packless ant
    # still steps onto adjacent food and still holds a threatened
    # home hill exactly as champion.
    orders, _ = run_horde_turn([(5, 5)], [], foods=[(5, 6)])
    assert orders == [((5, 5), "e")]
    guard, _ = run_horde_turn([(10, 8)], [(10, 16)], my_hills=[(10, 10)])
    assert guard == [((10, 8), "e")]


def test_packless_ant_skips_reinforce_pair() -> None:
    # (e) Two remembered hills and no pack: the ant explores north
    # instead of mustering on one hill or reinforcing the other.
    mine = [(5, 5)]
    orders, _ = run_horde_turn(mine, [], enemy_hills=[(5, 12), (15, 15)])
    assert orders == [((5, 5), "n")]


def test_march_gate_costs_under_1ms_on_crowded_board() -> None:
    # (f) The march gate -- one pack scan per hill-branch ant --
    # costs far under 1ms per crowded-board pass.
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    probe = FakeAnts(mine, [])
    reps = 50
    start = time.perf_counter()
    for _ in range(reps):
        for ant in mine:
            CX.march_with_pack(ant, mine, probe.distance)
    elapsed = (time.perf_counter() - start) / reps
    assert elapsed < 0.001


def test_packless_pair_regroups_toward_friends() -> None:
    # (g) Horde regroup: two packless ants with a remembered hill
    # step toward each other instead of mustering alone or
    # wandering -- the pair converges while the lone ant explores.
    mine = [(5, 5), (5, 13)]
    orders, _ = run_horde_turn(mine, [], enemy_hills=[(15, 15)])
    assert orders == [((5, 5), "e"), ((5, 13), "w")]
    probe = FakeAnts(mine, [])
    assert probe.distance((5, 6), (5, 12)) < probe.distance((5, 5), (5, 13))


def test_packless_ant_prefers_food_over_hills() -> None:
    # (h) Economy first: a packless ant next to food takes it even
    # with remembered hills on the board -- the food branch runs
    # before the gated hill branches.
    orders, _ = run_horde_turn([(5, 5)], [], foods=[(5, 6)], enemy_hills=[(5, 12)])
    assert orders == [((5, 5), "e")]


def test_taken_hill_is_forgotten_next_turn() -> None:
    # (i) Hill lifecycle across turns: a remembered hill the army
    # steps onto is forgotten, so the march ends instead of
    # milling around a razed hill.
    fake = FakeAnts([(5, 5)], [], enemy_hills=[(5, 12)])
    bot = HP.Screen2()
    bot.do_turn(fake)
    assert bot.remembered_hills == {(5, 12)}
    taken = FakeAnts([(5, 12)], [], enemy_hills=[])
    bot.do_turn(taken)
    assert bot.remembered_hills == set()
    assert taken.orders == [((5, 12), "n")]
