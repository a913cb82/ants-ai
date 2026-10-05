#!/usr/bin/env python
"""TwoStage4 supported-trade tie-break tests.

The two-stage split stays: STAGE 1 static safe-target/threat
labels, STAGE 2 stay-or-advance search with net-disadvantage
scoring. The ONE new mechanism is a supported-trade tie-break:
when the desired advance TIES the hold on a LOSING net score
(value < 0 -- the even-trade refusal), the square with more
supporting friends wins instead of the one committing fewer
ants. Lone ties (no support either side) still hold, so the
emergent no-1v1 gate survives; winning advances (+1) and safe
holds (0) never tie, so crowds behave exactly as TwoStage2.
No new candidate squares, no retreat: the disengage idea from
TwoStage3 is untouched and absent here.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import TwoStage4 as TS  # noqa: E402

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


def run_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], TS.TwoStage4]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = TS.TwoStage4()
    bot.do_turn(fake)
    return fake.orders, bot


def test_choice_key_prefers_support_on_losing_ties() -> None:
    # Losing tie (both -1): the backed engage (-1, support 1)
    # outranks the hold (-1, support 0) even though the hold
    # commits fewer ants. Lone ties still hold: with no support
    # either side the fewer-ants square wins.
    engage = TS.choice_key(-1, 1, 2)
    hold = TS.choice_key(-1, 0, 0)
    assert engage > hold
    lone_engage = TS.choice_key(-1, 0, 1)
    lone_hold = TS.choice_key(-1, 0, 0)
    assert lone_hold > lone_engage


def test_choice_key_ignores_support_when_not_losing() -> None:
    # A winning advance (+1) needs no credit, and a safe hold
    # (0) must never invite one: support counts only below zero.
    assert TS.choice_key(1, 0, 1) > TS.choice_key(0, 9, 0)
    assert TS.choice_key(1, 5, 9) == (1, 0, -9)
    assert TS.choice_key(0, 3, 0) == (0, 0, 0)


def _even_trade_tables() -> tuple[
    dict[int, list[Loc]],
    dict[tuple[int, Loc], int],
    dict[tuple[int, Loc], int],
    dict[tuple[int, Loc], int],
]:
    # Ant (5, 5) + friend (5, 8) vs foes (5, 7) + (5, 9) +
    # (6, 7). The eastern step models 3 foes against 1 supporter
    # (net 2); holding models 2 foes with no supporter (net 2).
    # Tied at -2/-2 with support 1 vs 0 -- base holds on fewest
    # ants. Static foes on the step are 2 against 1 friend, so
    # the explore fallback (needs 10 near friends for an equal
    # trade) also refuses it: only the new rule advances.
    east: Loc = (5, 6)
    ant: Loc = (5, 5)
    friends = [(5, 5), (5, 8)]
    foes = [(5, 7), (5, 9), (6, 7)]
    assert TS.modeled_foes(east, foes, _sq, R2, ROWS, COLS) == 3
    assert TS.modeled_foes(ant, foes, _sq, R2, ROWS, COLS) == 2
    assert TS.static_foes(east, foes, _sq, R2) == 2
    assert TS.support_count(east, ant, friends, _sq, R2) == 1
    assert TS.support_count(ant, ant, friends, _sq, R2) == 0
    cands = {0: [east, ant]}
    vals = {(0, east): -2, (0, ant): -2}
    coms = {(0, east): 2, (0, ant): 0}
    backs = {(0, east): 1, (0, ant): 0}
    return cands, vals, coms, backs


def test_supported_even_trade_advances_where_base_holds() -> None:
    # Discriminating scenario: without the backing table the
    # joint search reproduces TwoStage2 (hold on fewest ants);
    # with it the supported advance wins the losing tie.
    cands, vals, coms, backs = _even_trade_tables()
    base_plan, _ = TS.search_moves([0], cands, vals, coms)
    assert base_plan == {0: (5, 5)}
    new_plan, _ = TS.search_moves([0], cands, vals, coms, backs)
    assert new_plan == {0: (5, 6)}


def test_lone_tie_still_holds_in_search() -> None:
    # Friendless losing tie: no support either side, so the
    # backing table changes nothing -- the hold still wins.
    east: Loc = (5, 6)
    ant: Loc = (5, 5)
    cands = {0: [east, ant]}
    vals = {(0, east): -1, (0, ant): -1}
    coms = {(0, east): 1, (0, ant): 0}
    backs = {(0, east): 0, (0, ant): 0}
    plan, _ = TS.search_moves([0], cands, vals, coms, backs)
    assert plan == {0: ant}


def test_winning_advance_unaffected_by_backing() -> None:
    # A backed win (+1 vs 0) already advances without the new
    # rule; the backing table must not change its pick.
    east: Loc = (5, 6)
    ant: Loc = (5, 5)
    cands = {0: [east, ant]}
    vals = {(0, east): 1, (0, ant): 0}
    coms = {(0, east): 2, (0, ant): 1}
    backs = {(0, east): 1, (0, ant): 1}
    plain, _ = TS.search_moves([0], cands, vals, coms)
    backed, _ = TS.search_moves([0], cands, vals, coms, backs)
    assert plain == backed == {0: east}


def test_supported_even_trade_full_turn() -> None:
    # Full-turn version of the discriminating contact: (5, 5)
    # + (5, 8) vs three foes is a triple stage-1 threat, and
    # the joint plan advances the supported hunter east -- base
    # holds here on the fewest-ants tie-break, and water on
    # the other three sides keeps the explore fallback from
    # masking the refusal (the step is unsafe for it).
    mine = [(5, 5), (5, 8)]
    foes = [(5, 7), (5, 9), (6, 7)]
    water = {(4, 5), (6, 5), (5, 4)}
    labels = TS.classify_static(mine, foes, _sq, R2)
    assert labels == {
        (5, 7): TS.THREAT,
        (5, 9): TS.THREAT,
        (6, 7): TS.THREAT,
    }
    orders, _ = run_turn(mine, foes, water=water)
    assert ((5, 5), "e") in orders


def test_equal_support_tie_still_holds_full_turn() -> None:
    # Scope limit, pinned: 2v2 head-on (ant (5, 5) + buddy
    # (6, 5) vs foes (5, 7) + (6, 7)) ties at -1/-1 with one
    # supporter on EACH square -- equal support, so the
    # fewest-ants tie-break still holds. The new rule only
    # fires when the advance is strictly better supported.
    mine = [(5, 5), (6, 5)]
    ant: Loc = (5, 5)
    east: Loc = (5, 6)
    assert TS.support_count(east, ant, mine, _sq, R2) == 1
    assert TS.support_count(ant, ant, mine, _sq, R2) == 1
    cands = {0: [east, ant]}
    vals = {(0, east): -1, (0, ant): -1}
    coms = {(0, east): 2, (0, ant): 1}
    backs = {(0, east): 1, (0, ant): 1}
    plan, _ = TS.search_moves([0], cands, vals, coms, backs)
    assert plan == {0: ant}


def test_lone_lurker_still_holds_full_turn() -> None:
    # Lone ant (5, 5) against lurker (5, 9): no backup anywhere,
    # the hold reads 0 against the step's -1, so the ant holds
    # the joint plan and explores north -- the no-1v1 gate, as
    # base.
    orders, _ = run_turn([(5, 5)], [(5, 9)])
    assert ((5, 5), "e") not in orders
    assert orders == [((5, 5), "n")]


def test_backed_threatened_ant_advances_full_turn() -> None:
    # No-regression case: (5, 5) + (5, 4) vs (5, 7) is a
    # stage-1 threat, but the backed step already wins outright
    # (+1 vs 0) -- the new tie-break never fires here.
    mine = [(5, 5), (5, 4)]
    labels = TS.classify_static(mine, [(5, 7)], _sq, R2)
    assert labels == {(5, 7): TS.THREAT}
    orders, _ = run_turn(mine, [(5, 7)])
    assert ((5, 5), "e") in orders


def test_supported_pair_deterministic() -> None:
    # Same supported-trade board twice: identical orders, no
    # coin flips in the backing count, the key, or the search.
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
