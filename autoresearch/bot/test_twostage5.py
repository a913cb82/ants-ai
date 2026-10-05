#!/usr/bin/env python
"""TwoStage5 safe-backup pricing tests.

ONE new mechanism over TwoStage4: support counts only from SAFE
friends -- allies outside threat reach of every threat. A
threatened "supporter" is itself about to die or flee, so its
backup is phantom: counting it prices losing advances as
backed trades and donates (TwoStage4's 38.4-to-18.9 collapse).
Gated backup reprices those advances as the losses they are,
and the joint search holds instead. Safe backup still spends:
a losing tie with strictly safer backing still advances, and
all-safe positions behave exactly like TwoStage4.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import TwoStage5 as TS  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
R2 = 5


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


def _sq(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


def _dist(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


def _safe_set(mine: list[Loc], foes: list[Loc]) -> set[Loc]:
    labels = TS.classify_static(mine, foes, _sq, R2)
    threats = [e for e in foes if labels.get(e) == TS.THREAT]
    reach = TS.threat_reach(R2)
    return {f for f in mine if not TS.is_threatened(f, threats, _dist, reach)}


def run_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], TS.TwoStage5]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = TS.TwoStage5()
    bot.do_turn(fake)
    return fake.orders, bot


def test_gated_support_counts_only_safe_friends() -> None:
    # (5, 8) backs the eastern step but sits next to foe (5, 7):
    # threatened, so the gate drops it. A safe friend still counts,
    # and safe=None keeps the old all-count behavior.
    east: Loc = (5, 6)
    ant: Loc = (5, 5)
    friends = [(5, 5), (5, 8)]
    assert TS.support_count(east, ant, friends, _sq, R2) == 1
    assert TS.support_count(east, ant, friends, _sq, R2, safe=lambda loc: False) == 0
    assert (
        TS.support_count(east, ant, friends, _sq, R2, safe={(5, 8)}.__contains__) == 1
    )


def test_donation_supporter_is_threatened() -> None:
    # Pins the diagnosis: in TwoStage4's donating contact both of
    # our ants sit inside threat reach, so the safe set is empty
    # and the "backed" trade was phantom-backed.
    mine = [(5, 5), (5, 8)]
    foes = [(5, 7), (5, 9), (6, 7)]
    assert _safe_set(mine, foes) == set()


def test_threatened_backing_holds_losing_tie_in_search() -> None:
    # Table-level discrimination: the TwoStage4 backing (1 vs 0)
    # advances the -2/-2 losing tie; the gated backing (0 vs 0)
    # holds it on fewest ants.
    east: Loc = (5, 6)
    ant: Loc = (5, 5)
    cands = {0: [east, ant]}
    vals = {(0, east): -2, (0, ant): -2}
    coms = {(0, east): 2, (0, ant): 0}
    base_plan, _ = TS.search_moves([0], cands, vals, coms, {(0, east): 1, (0, ant): 0})
    assert base_plan == {0: east}
    gated_plan, _ = TS.search_moves([0], cands, vals, coms, {(0, east): 0, (0, ant): 0})
    assert gated_plan == {0: ant}


def test_safe_backing_still_advances_losing_tie() -> None:
    # The gate reprices, not removes: safe backing (1 vs 0) on a
    # losing tie still advances, so real rescues survive.
    east: Loc = (5, 6)
    ant: Loc = (5, 5)
    cands = {0: [east, ant]}
    vals = {(0, east): -1, (0, ant): -1}
    coms = {(0, east): 2, (0, ant): 1}
    plan, _ = TS.search_moves([0], cands, vals, coms, {(0, east): 1, (0, ant): 0})
    assert plan == {0: east}


def test_donation_holds_full_turn() -> None:
    # TwoStage4's discriminating contact advances east; with the
    # phantom backup gated out the eastern step nets -3 against
    # the hold's -2, so the ant holds outright -- and every other
    # exit is walled by water, so no order issues at all.
    mine = [(5, 5), (5, 8)]
    foes = [(5, 7), (5, 9), (6, 7)]
    water = {(4, 5), (6, 5), (5, 4)}
    orders, _ = run_turn(mine, foes, water=water)
    assert ((5, 5), "e") not in orders
    assert orders == []


def test_threatened_backup_holds_full_turn() -> None:
    # (5, 5) + (5, 4) vs (5, 7): TwoStage4 advances east on the
    # buddy's backup, but the buddy sits 3 from the foe -- inside
    # threat reach, so the trade is phantom-backed and holds.
    orders, _ = run_turn([(5, 5), (5, 4)], [(5, 7)])
    assert ((5, 5), "e") not in orders


def test_safe_backup_advances_full_turn() -> None:
    # No-overcorrection pin: (7, 7) backs the (5, 6) step from 6
    # off the foe -- safe -- so the net win stands and the ant
    # advances north exactly as TwoStage4 does.
    mine = [(6, 6), (7, 7)]
    assert (7, 7) in _safe_set(mine, [(3, 5)])
    orders, _ = run_turn(mine, [(3, 5)])
    assert ((6, 6), "n") in orders


def test_lone_lurker_still_holds_full_turn() -> None:
    # Lone ant (5, 5) against lurker (5, 9): no backup anywhere,
    # the hold reads 0 against the step's -1, so the ant holds
    # the joint plan and explores north -- unchanged from base.
    orders, _ = run_turn([(5, 5)], [(5, 9)])
    assert ((5, 5), "e") not in orders
    assert orders == [((5, 5), "n")]


def test_choice_key_prefers_support_on_losing_ties() -> None:
    # Unchanged ordering: a losing tie runs toward support, lone
    # ties hold on fewest ants. The gate only changes what counts
    # as support, never the order itself.
    engage = TS.choice_key(-1, 1, 2)
    hold = TS.choice_key(-1, 0, 0)
    assert engage > hold
    lone_engage = TS.choice_key(-1, 0, 1)
    lone_hold = TS.choice_key(-1, 0, 0)
    assert lone_hold > lone_engage


def test_supported_pair_deterministic() -> None:
    # Same donating board twice: identical orders, no coin flips
    # in the safe set, the gate, or the search.
    mine = [(5, 5), (5, 8)]
    foes = [(5, 7), (5, 9), (6, 7)]
    water = {(4, 5), (6, 5), (5, 4)}
    first, _ = run_turn(mine, foes, water=water)
    second, _ = run_turn(mine, foes, water=water)
    assert first == second


def test_full_turn_under_1s_crowded() -> None:
    # 40 ants, 25 enemies, food, hills, and a threatened home
    # hill: a full do_turn stays far inside the 1000 ms budget.
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(40)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(25)]
    foods = [(3, 3), (4, 3), (15, 15)]
    start = time.perf_counter()
    orders, _ = run_turn(mine, foes, foods, enemy_hills=[(15, 15)], my_hills=[(2, 2)])
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert isinstance(orders, list)


def test_food_guard_matches_champion() -> None:
    # Champion economy/guard byte-identical: contested cluster
    # (3+ enemies near two foods) draws exactly two denial claims
    # on nearest pairs, and the claim-free ant guards its
    # threatened hill east -- the champion's orders move for move.
    mine = [(5, 5), (2, 2), (10, 10)]
    foods = [(5, 6), (2, 3)]
    enemies = [(5, 12), (2, 6), (5, 9), (10, 15)]
    orders, _ = run_turn(mine, enemies, foods, my_hills=[(10, 12)])
    assert orders == [((5, 5), "e"), ((2, 2), "e"), ((10, 10), "e")]
