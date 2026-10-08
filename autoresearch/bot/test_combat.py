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

Leg 6 implements the RESEARCH.md row "Tandem: buddy-rally
pair-forming on refused seek": a seek step that is a friendless
1v1 contact (no friend in attack range of the step, exactly one
foe) with the grinder gate shut (visible army not ahead) rallies
to the nearest visible friend within combat.RALLY_RANGE (6)
via the existing first_step pathing with the normal safety
filter, instead of scattering to muster/reinforce/explore. The
pair meets next turn and the join fires. Safe-gated: no path,
distant buddy, or unsafe rally square falls through exactly as
champion. Joined ants, grinder-open duels, backed or crowded
contacts, and everything else match champion exactly.

Leg 7 implements the RESEARCH.md row "Tandem: pocket-free
explore": explore sorts dead-end pockets (3+ water neighbours,
combat.dead_end) after open squares, so idle ants stop donating
turns into dead ends. Food, guard, seek, muster, and reinforce
still enter pockets, and a lone pocket with no other safe step is
taken exactly as champion.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import combat as CX  # noqa: E402

# Leg 5: Tandem.py carries the same seek + join + grinder + screen
# wiring; OP now aliases Tandem. champion14_orders below patches the
# gate back to 14 to reproduce true champion Denial exactly.
import Tandem as GP  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], GP.Tandem]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = GP.Tandem()
    bot.do_turn(fake)
    return fake.orders, bot


def run_grinder_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], GP.Tandem]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = GP.Tandem()
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
    # No food, no hills: the idle ant at (5,5) with an enemy 5 steps
    # east must advance east instead of exploring north as champion.
    mine = [(5, 5)]
    enemies = [(5, 10)]
    orders, _ = run_turn(mine, enemies)
    assert orders == [((5, 5), "e")]
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


def test_muster_orders_unchanged_with_enemy_in_range() -> None:
    # Remembered hill musters while an enemy sits 7 steps away: the
    # muster step (east or south, both on a shortest path) matches
    # champion instead of chasing.
    mine = [(10, 10)]
    enemies = [(10, 17)]
    orders, _ = run_turn(mine, enemies, enemy_hills=[(15, 15)])
    champ = champion_orders(mine, enemies, enemy_hills=[(15, 15)])
    assert len(orders) == 1 and orders == champ
    assert orders[0][1] in ("e", "s")


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
    mine = [(5, 5), (5, 9)]
    enemies = [(5, 7)]
    orders, _ = run_turn(mine, enemies)
    assert orders == [((5, 5), "e"), ((5, 9), "w")]
    champ = champion_orders(mine, enemies)
    assert champ == [((5, 5), "w"), ((5, 9), "e")]
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
    # on the second foe holds exactly as champion. Even 3v3 army so
    # the Grinder gate stays shut for the loner; the join itself
    # ignores the army count.
    mine = [(5, 5), (5, 9), (15, 15)]
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
    # engages east where champion retreats west.
    mine = [(5, 5), (15, 15), (15, 16)]
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
    # foe, so both engage though the visible army trails 3v4.
    mine = [(5, 5), (5, 9), (0, 0)]
    enemies = [(5, 7), (0, 10), (0, 11), (0, 12)]
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
    # True champion Denial: Tandem differs from the staged champion
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
_ODDS_MINE_12 = [(5, 5), _ODDS_BACK] + _ODDS_FILLERS
_ODDS_MINE_9 = [(5, 5), _ODDS_BACK] + _ODDS_FILLERS[:8]


def test_equal_trade_gate_constant_is_ten() -> None:
    # (gate) The equal-trade near gate lives in combat as a named
    # constant: 10, down from champion's tuned 14.
    assert CX.EQUAL_TRADE_NEAR == 10


def test_twelve_near_accepts_equal_trade_champion_refuses() -> None:
    # (a) 12 near friends: Odds engages east onto (5, 6) while the
    # 14-gate champion refuses and explores north instead.
    orders, _ = run_turn(_ODDS_MINE_12, _ODDS_FOES, _ODDS_FOOD)
    assert orders[0] == ((5, 5), "e")
    champ = champion14_orders(_ODDS_MINE_12, _ODDS_FOES, _ODDS_FOOD)
    assert champ[0] == ((5, 5), "n")
    assert orders[0] != champ[0]


def test_nine_near_refuses_exactly_as_champion() -> None:
    # (b) 9 near friends: below both gates, so every order matches
    # the 14-gate champion and nobody steps east into the trade.
    orders, _ = run_turn(_ODDS_MINE_9, _ODDS_FOES, _ODDS_FOOD)
    champ = champion14_orders(_ODDS_MINE_9, _ODDS_FOES, _ODDS_FOOD)
    assert orders == champ
    assert orders[0] != ((5, 5), "e")


def test_strict_superiority_engages_under_both_gates() -> None:
    # (c1) 2 backing friends vs 1 foe: strict superiority accepts
    # under either gate, so Odds and champion agree east.
    mine = [(5, 5), (5, 4), (4, 6)]
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


# Leg 6 boards: A at (5, 5) eyes the step east onto (5, 6) against
# one foe (5, 8): friends 0, enemies 1 -- a friendless 1v1 the
# grinder refuses on an even 2v2 army. Buddy B stands south; the
# rally step south onto (6, 5) is contact-free (safe) while the
# champion explore branch prefers north (also contact-free, tried
# first in n/e/s/w visit order), so the two orders differ.
_TANDEM_MINE = [(5, 5), (9, 5)]
_TANDEM_FOES = [(5, 8), (0, 10)]


def test_rally_range_constant_is_six() -> None:
    # (gate) The buddy-rally range lives in combat as a named
    # constant: 6, local pair-forming in the same theater.
    assert CX.RALLY_RANGE == 6


def test_nearest_rally_buddy_picks_nearest_in_range() -> None:
    probe = FakeAnts([(5, 5)], [])
    assert CX.nearest_rally_buddy((5, 5), [], probe.distance) is None
    assert CX.nearest_rally_buddy((5, 5), [(5, 5)], probe.distance) is None
    found = CX.nearest_rally_buddy((5, 5), [(5, 5), (2, 5), (5, 9)], probe.distance)
    assert found == (2, 5)
    assert CX.nearest_rally_buddy((5, 5), [(5, 5), (5, 11)], probe.distance) == (
        5,
        11,
    )
    assert CX.nearest_rally_buddy((5, 5), [(5, 5), (5, 12)], probe.distance) is None
    tied = CX.nearest_rally_buddy((5, 5), [(5, 5), (5, 8), (5, 2)], probe.distance)
    assert tied == (5, 8)


def test_refused_seek_rallies_to_near_buddy() -> None:
    # (a) Even 2v2 army, buddy 4 south: Tandem steps south toward
    # the buddy to form next turn's pair; champion explores north.
    orders, _ = run_turn(_TANDEM_MINE, _TANDEM_FOES)
    assert orders[0] == ((5, 5), "s")
    champ = champion_orders(_TANDEM_MINE, _TANDEM_FOES)
    assert champ[0] == ((5, 5), "n")
    assert orders[0] != champ[0]


def test_distant_buddy_falls_through_as_champion() -> None:
    # (b) Buddy 8 south, beyond RALLY_RANGE: no rally, every order
    # matches champion, A explores north.
    mine = [(5, 5), (13, 5)]
    orders, _ = run_turn(mine, _TANDEM_FOES)
    champ = champion_orders(mine, _TANDEM_FOES)
    assert orders == champ
    assert orders[0] == ((5, 5), "n")


def test_ahead_duel_engages_instead_of_rally() -> None:
    # (c) 3v2 visible army: the grinder opens, so A engages east
    # with the join and never rallies south to the buddy.
    mine = [(5, 5), (9, 5), (9, 6)]
    orders, _ = run_turn(mine, _TANDEM_FOES)
    assert orders[0] == ((5, 5), "e")


def test_joined_pair_engages_instead_of_rally() -> None:
    # (d) The join ignores the rally: the flanking pair shares one
    # foe, so both engage though a buddy stands in rally range on
    # an even 3v3 army.
    mine = [(5, 5), (5, 9), (9, 5)]
    enemies = [(5, 7), (0, 10), (0, 11)]
    orders, _ = run_turn(mine, enemies)
    assert orders[0] == ((5, 5), "e")
    assert orders[1] == ((5, 9), "w")


def test_unreachable_buddy_falls_through_as_champion() -> None:
    # (e) Buddy in range but water-enclosed: no rally path, every
    # order matches champion, A explores north.
    mine = [(5, 5), (9, 5)]
    water = {(8, 5), (9, 4), (9, 6), (10, 5)}
    orders, _ = run_turn(mine, _TANDEM_FOES, water=water)
    champ = champion_orders(mine, _TANDEM_FOES, water=water)
    assert orders == champ
    assert orders[0] == ((5, 5), "n")


def test_crowded_contact_never_rallies() -> None:
    # (f) Friendless 1v2 contact (two foes on the step): outside
    # the 1v1 rally shape, so every order matches champion and A
    # retreats west instead of rallying south.
    mine = [(5, 5), (9, 5)]
    enemies = [(5, 7), (5, 8), (0, 10)]
    orders, _ = run_turn(mine, enemies)
    champ = champion_orders(mine, enemies)
    assert orders == champ
    assert orders[0] == ((5, 5), "w")


def test_full_turn_finishes_under_1s_on_crowded_board() -> None:
    # (g) One turn must finish in 1000 ms: 48 ants, 24 foes, food,
    # hills, and water on a 20x20 board, single pass.
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(24)]
    foods = [(3, 3), (3, 4), (15, 15), (16, 15), (10, 2)]
    water = {(7, 7), (7, 8), (8, 7)}
    start = time.perf_counter()
    orders, _ = run_turn(
        mine, foes, foods, water=water, enemy_hills=[(15, 15)], my_hills=[(2, 2)]
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(orders) > 0


def test_rally_closes_distance_while_champion_opens_it() -> None:
    # (h) Purpose pin: the rally step shortens the A-B gap (4 to
    # 3) so next turn's join can fire, while the champion explore
    # step lengthens it (4 to 5), scattering the pair.
    probe = FakeAnts([(5, 5)], [])
    orders, _ = run_turn(_TANDEM_MINE, _TANDEM_FOES)
    champ = champion_orders(_TANDEM_MINE, _TANDEM_FOES)
    rallied = probe.destination((5, 5), orders[0][1])
    scattered = probe.destination((5, 5), champ[0][1])
    assert probe.distance(rallied, (9, 5)) == 3
    assert probe.distance(scattered, (9, 5)) == 5


def test_rally_forms_pair_that_engages_within_three_turns() -> None:
    # (i) End-to-end across four turns on one bot: the refused
    # duel rallies south (t1), the pair converges north (t2), the
    # backed pair engages east (t3) and presses east again (t4).
    # Champion explores north away from the foe on the same
    # boards instead (contrast simulation).
    mine = [(5, 5), (9, 5)]
    foes = [(5, 8), (0, 10)]
    bot = GP.Tandem()
    seen: list[list[tuple[Loc, str]]] = []
    for _ in range(4):
        fake = FakeAnts(list(mine), list(foes))
        bot.do_turn(fake)
        seen.append(list(fake.orders))
        moved = {loc for loc, _ in fake.orders}
        mine = sorted(
            [fake.destination(loc, d) for loc, d in fake.orders]
            + [m for m in mine if m not in moved]
        )
    assert seen[0] == [((5, 5), "s"), ((9, 5), "n")]
    assert seen[1] == [((6, 5), "n"), ((8, 5), "n")]
    assert seen[2][0] == ((5, 5), "e")
    assert seen[3][0] == ((5, 6), "e")


def test_guard_takes_precedence_over_rally() -> None:
    # (j) A threatened home hill west holds precedence: A guards
    # west onto the safe hill instead of rallying south, exactly
    # as champion.
    mine = [(5, 5), (9, 5)]
    orders, _ = run_turn(mine, _TANDEM_FOES, my_hills=[(5, 4)])
    champ = champion_orders(mine, _TANDEM_FOES, my_hills=[(5, 4)])
    assert orders == champ
    assert orders[0] == ((5, 5), "w")


def test_danger_blocked_harvester_rallies() -> None:
    # (k) A's food claim east is danger-blocked (unsafe contact),
    # so the claim fails and A rallies south to the buddy instead
    # of suiciding onto the food or scattering as champion.
    mine = [(5, 5), (9, 5)]
    orders, _ = run_turn(mine, _TANDEM_FOES, foods=[(5, 6)])
    assert orders[0] == ((5, 5), "s")
    champ = champion_orders(mine, _TANDEM_FOES, foods=[(5, 6)])
    assert champ[0] == ((5, 5), "n")
    assert orders[0] != champ[0]


def test_seeded_fuzz_never_crashes_and_orders_stay_valid() -> None:
    # (l) Hardening: 200 seeded boards (ants, foes, food, water,
    # hills) -- every turn completes, every order starts from a
    # real ant, targets a passable square, and claims each
    # destination once. Tandem and champion both survive.
    import random

    rng = random.Random(20261008)
    boards = 200
    start = time.perf_counter()
    for _ in range(boards):
        n_mine = rng.randint(1, 8)
        n_foes = rng.randint(0, 6)
        mine = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(n_mine)]
        foes = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(n_foes)]
        foods = [
            (rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(rng.randint(0, 4))
        ]
        water = {
            (rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(rng.randint(0, 6))
        }
        mine = [m for m in mine if m not in water]
        if not mine:
            mine = [(0, 0)]
        foes = [f for f in foes if f not in water]
        my_hills = (
            [(rng.randrange(ROWS), rng.randrange(COLS))] if rng.random() < 0.3 else []
        )
        enemy_hills = (
            [(rng.randrange(ROWS), rng.randrange(COLS))] if rng.random() < 0.3 else []
        )
        for run in (run_turn, champion_orders):
            if run is run_turn:
                orders, _ = run(
                    mine,
                    foes,
                    foods,
                    water=water,
                    enemy_hills=enemy_hills,
                    my_hills=my_hills,
                )
            else:
                orders = run(
                    mine,
                    foes,
                    foods,
                    water=water,
                    enemy_hills=enemy_hills,
                    my_hills=my_hills,
                )
            probe = FakeAnts(mine, foes, foods, water)
            seen_dest: set[Loc] = set()
            for loc, direction in orders:
                assert direction in ("n", "e", "s", "w")
                assert loc in mine
                dest = probe.destination(loc, direction)
                assert probe.passable(dest)
                assert dest not in seen_dest
                seen_dest.add(dest)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0


def test_mutual_rally_converges_from_both_sides() -> None:
    # (m) Both ants refuse mirrored 1v1s on an even 2v2 army and
    # rally toward each other (east meets west), forming the pair
    # between the foes. Champion scatters both north instead.
    mine = [(5, 5), (5, 9)]
    enemies = [(5, 2), (5, 12)]
    orders, _ = run_turn(mine, enemies)
    assert orders == [((5, 5), "e"), ((5, 9), "w")]
    champ = champion_orders(mine, enemies)
    assert champ == [((5, 5), "n"), ((5, 9), "n")]
    assert orders != champ


def test_dead_end_needs_three_water_neighbours() -> None:
    # (pocket-helper) A square is a dead-end pocket only with 3+
    # water neighbours; corridors (2 walls) stay open ground.
    probe = FakeAnts([], [], water={(3, 5), (4, 4), (4, 6)})
    neighbours = [probe.destination((4, 5), d) for d in ("n", "e", "s", "w")]
    assert CX.dead_end(neighbours, probe.passable) is True
    open_probe = FakeAnts([], [], water={(3, 5), (4, 4)})
    open_neighbours = [open_probe.destination((4, 5), d) for d in ("n", "e", "s", "w")]
    assert CX.dead_end(open_neighbours, open_probe.passable) is False
    assert CX.dead_end([], probe.passable) is False


def no_pocket_orders(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    # True champion explore: Tandem differs from the staged
    # champion only in pocket avoidance, so patching
    # combat.dead_end to always-False reproduces the champion
    # least-visited explore exactly (unlike champion_orders, the
    # pocket filter stays on there).
    orig = CX.dead_end
    CX.dead_end = lambda neighbours, passable: False  # noqa: E731
    try:
        orders, _ = run_turn(
            mine,
            enemies,
            foods,
            water=water,
            enemy_hills=enemy_hills,
            my_hills=my_hills,
        )
    finally:
        CX.dead_end = orig
    return orders


def test_explore_skirts_dead_end_pocket() -> None:
    # (n) Idle ant with a pocket north (3 water neighbours) and
    # open east: Tandem explores east around the pocket while
    # champion walks north straight into it.
    mine = [(5, 5)]
    water = {(3, 5), (4, 4), (4, 6)}
    orders, _ = run_turn(mine, [], water=water)
    assert orders == [((5, 5), "e")]
    champ = no_pocket_orders(mine, [], water=water)
    assert champ == [((5, 5), "n")]
    assert orders != champ


def test_explore_takes_pocket_when_it_is_the_only_square() -> None:
    # (o) Pocket fallback: with water north/east/south, the only
    # open square west is itself a pocket -- Tandem takes it
    # exactly as champion rather than holding.
    mine = [(5, 5)]
    water = {(4, 5), (5, 6), (6, 5), (5, 3), (4, 4), (6, 4)}
    orders, _ = run_turn(mine, [], water=water)
    champ = champion_orders(mine, [], water=water)
    assert orders == champ == [((5, 5), "w")]
