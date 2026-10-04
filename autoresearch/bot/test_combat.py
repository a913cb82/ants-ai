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
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import combat as CX  # noqa: E402
import Wolfpack as WP  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], WP.Wolfpack]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = WP.Wolfpack()
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
    # on the second foe holds exactly as champion.
    mine = [(5, 5), (5, 9), (15, 15)]
    enemies = [(5, 7), (15, 17)]
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
