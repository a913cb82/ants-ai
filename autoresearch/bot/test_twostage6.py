#!/usr/bin/env python
"""TwoStage6 surplus-only advance bonus tests.

The two-stage split stays: STAGE 1 static safe-target/threat
labels, STAGE 2 stay-or-advance search with net-disadvantage
scoring and TwoStage4's supported-trade tie-break. The ONE new
mechanism is a surplus-only movement bonus: the +1 for stepping
pays only when the destination is TRULY safe (no modeled foes)
or STRICTLY winning (more supporting friends than modeled
foes). An even trade -- friends cancel foes exactly, net zero
through backup rather than through safety -- scores 0 with no
bonus, so it ties the safe hold and the fewest-ants tie-break
holds instead of donating into mutual annihilation. TwoStage4
paid +1 for every net-zero step, pricing a 2v2 the same as a
walk into empty ground. No support-count change (TwoStage5's
gate is untouched and absent here); no new candidates, no
retreat: the disengage idea from TwoStage3 stays absent.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import TwoStage6 as TS  # noqa: E402

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


def run_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], TS.TwoStage6]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = TS.TwoStage6()
    bot.do_turn(fake)
    return fake.orders, bot


def test_even_trade_earns_no_bonus() -> None:
    # Discriminating unit: friends cancel foes exactly (2v2) --
    # TwoStage4 prices the step +1 (net zero reads as safe), the
    # new rule prices it 0 (even contact is not safety). Holds
    # never earn the bonus either way.
    ant: Loc = (5, 5)
    east: Loc = (5, 6)
    assert TS.net_value(east, ant, 2, 2) == 0
    assert TS.net_value(east, ant, 1, 1) == 0
    assert TS.net_value(ant, ant, 2, 2) == 0
    assert TS.net_value(ant, ant, 0, 0) == 0


def test_safe_and_surplus_steps_keep_bonus() -> None:
    # No-regression units: empty steps and strictly winning
    # steps still pay +1, lone losing steps still read the loss.
    ant: Loc = (5, 5)
    east: Loc = (5, 6)
    assert TS.net_value(east, ant, 0, 0) == 1
    assert TS.net_value(east, ant, 0, 2) == 1
    assert TS.net_value(east, ant, 1, 2) == 1
    assert TS.net_value(east, ant, 2, 3) == 1
    assert TS.net_value(east, ant, 2, 1) == -1
    assert TS.net_value(east, ant, 2, 0) == -2
    assert TS.net_value(ant, ant, 1, 0) == -1


def test_search_holds_even_trade_where_base_advances() -> None:
    # Discriminating scenario at search level: under TwoStage4
    # pricing the backed-even step reads +1 against a safe hold
    # (0) and advances; under the new pricing both read 0 and
    # the fewest-ants tie-break holds.
    east: Loc = (5, 6)
    ant: Loc = (5, 5)
    cands = {0: [east, ant]}
    base_vals = {(0, east): 1, (0, ant): 0}
    new_vals = {(0, east): 0, (0, ant): 0}
    coms = {(0, east): 3, (0, ant): 2}
    backs = {(0, east): 2, (0, ant): 2}
    base_plan, _ = TS.search_moves([0], cands, base_vals, coms, backs)
    assert base_plan == {0: east}
    new_plan, _ = TS.search_moves([0], cands, new_vals, coms, backs)
    assert new_plan == {0: ant}


def test_search_still_advances_strict_surplus() -> None:
    # Scope limit: a strictly winning step (+1 vs 0) advances
    # under the new pricing exactly as base -- only even trades
    # flip.
    east: Loc = (5, 6)
    ant: Loc = (5, 5)
    cands = {0: [east, ant]}
    vals = {(0, east): 1, (0, ant): 0}
    coms = {(0, east): 2, (0, ant): 1}
    backs = {(0, east): 2, (0, ant): 0}
    plan, _ = TS.search_moves([0], cands, vals, coms, backs)
    assert plan == {0: east}


def test_even_contact_holds_full_turn() -> None:
    # Full-turn version of the even trade: (5, 5) + (4, 6) +
    # (6, 6) vs (5, 8) + (4, 8). Both foes are stage-1 threats,
    # the eastern step models 2 foes against 2 supporters (even,
    # now 0) while the hold models 2 against 2 (0) -- so the ant
    # holds on fewest ants. TwoStage4 prices the step +1 here
    # and advances east into the 2v2.
    mine = [(5, 5), (4, 6), (6, 6)]
    foes = [(5, 8), (4, 8)]
    ant: Loc = (5, 5)
    east: Loc = (5, 6)
    labels = TS.classify_static(mine, foes, _sq, R2)
    assert labels == {(5, 8): TS.THREAT, (4, 8): TS.THREAT}
    assert TS.modeled_foes(east, foes, _sq, R2, ROWS, COLS) == 2
    assert TS.modeled_foes(ant, foes, _sq, R2, ROWS, COLS) == 2
    assert TS.support_count(east, ant, mine, _sq, R2) == 2
    assert TS.support_count(ant, ant, mine, _sq, R2) == 2
    orders, _ = run_turn(mine, foes)
    assert ((5, 5), "e") not in orders


def test_lone_lurker_still_holds_full_turn() -> None:
    # Lone ant (5, 5) against lurker (5, 9): no backup anywhere,
    # the hold reads 0 against the step's -1, so the ant holds
    # the joint plan and explores north -- the no-1v1 gate, as
    # base.
    orders, _ = run_turn([(5, 5)], [(5, 9)])
    assert ((5, 5), "e") not in orders
    assert orders == [((5, 5), "n")]


def test_safe_chase_advances_full_turn() -> None:
    # No-regression case: lone (5, 5) vs distant (5, 12) is a
    # stage-1 threat but outside threat reach, so static analysis
    # clears the chase and the ant steps east -- safe advances
    # never touch the new gate.
    labels = TS.classify_static([(5, 5)], [(5, 12)], _sq, R2)
    assert labels == {(5, 12): TS.THREAT}
    orders, _ = run_turn([(5, 5)], [(5, 12)])
    assert orders == [((5, 5), "e")]


def test_supported_pair_deterministic() -> None:
    # Same even-trade board twice: identical orders, no coin
    # flips in the net, the key, or the search.
    mine = [(5, 5), (4, 6), (6, 6)]
    foes = [(5, 8), (4, 8)]
    first, _ = run_turn(mine, foes)
    second, _ = run_turn(mine, foes)
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
