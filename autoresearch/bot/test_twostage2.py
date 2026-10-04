#!/usr/bin/env python
"""TwoStage2 support-adjusted contact evaluation tests.

The two-stage split stays: STAGE 1 static safe-target/threat
labels, STAGE 2 stay-or-advance search with the fewest-ants
tie-break. The ONE new mechanism is support-adjusted contact
evaluation: stage-2 squares score the NET disadvantage (modeled
foes minus supporting friends in range of the destination), so
backed advances read as wins and proceed, while lone advances
still read as losses and hold. Base priced raw foe counts and
held both -- it placed where the ports won.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import TwoStage2 as TS  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], TS.TwoStage2]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = TS.TwoStage2()
    bot.do_turn(fake)
    return fake.orders, bot


def test_support_counts_backup_in_range() -> None:
    # Friend (5, 4) sits sq 1 from the eastern step (5, 6): it
    # backs the step. Friend (0, 0) is far away: it backs
    # nothing. The mover itself never counts.
    assert TS.support_count((5, 6), (5, 5), [(5, 5), (5, 4)], _sq, R2) == 1
    assert TS.support_count((5, 6), (5, 5), [(5, 5), (0, 0)], _sq, R2) == 0
    assert TS.support_count((5, 5), (5, 5), [(5, 4)], _sq, R2) == 1


def test_net_value_credits_backup() -> None:
    # Same foe count (1), different backup: the backed step
    # reads as a win (+1 moved, net 0), the lone step as a loss
    # (-1). Raw move_value prices both at -1 -- the base blind
    # spot this entry fixes.
    east: Loc = (5, 6)
    ant: Loc = (5, 5)
    assert TS.move_value(east, ant, 1) == -1
    assert TS.net_value(east, ant, 1, 1) == 1
    assert TS.net_value(east, ant, 1, 0) == -1
    assert TS.net_value(ant, ant, 1, 0) == -1
    assert TS.net_value(ant, ant, 1, 1) == 0


def test_backed_advance_beats_hold_where_base_holds() -> None:
    # Discriminating contact: ant (5, 5) + friend (5, 4) vs foe
    # (5, 7). Stage-2 models 1 foe on both squares. Base scores
    # engage -1 vs hold -1 and the fewest-ants tie-break holds.
    # Net evaluation credits the friend backing the step
    # (sq 1 from (5, 6)): engage +1 vs hold 0, so the ant
    # advances -- the port behavior in the same crowd.
    ant: Loc = (5, 5)
    east: Loc = (5, 6)
    friends = [(5, 5), (5, 4)]
    foes = [(5, 7)]
    modeled = {sq: TS.modeled_foes(sq, foes, _sq, R2, ROWS, COLS) for sq in (east, ant)}
    assert modeled == {east: 1, ant: 1}
    assert TS.pick_best(ant, [east, ant], modeled, friends, _sq, R2) == ant
    net = {
        sq: TS.net_value(
            sq, ant, modeled[sq], TS.support_count(sq, ant, friends, _sq, R2)
        )
        for sq in (east, ant)
    }
    assert net == {east: 1, ant: 0}
    # Same tie-break as the joint search (top net score, then
    # fewest committed ants): engage (1, -2) beats hold (0, -1).
    assert (net[east], -TS.commit_count(east, ant, friends, _sq, R2)) > (
        net[ant],
        -TS.commit_count(ant, ant, friends, _sq, R2),
    )


def test_lone_duel_still_holds_under_net() -> None:
    # Friendless ant (5, 5) vs lone foe (5, 7): no backup on
    # either square, so net equals raw on both -- engage -1 vs
    # hold -1 -- and the fewest-ants tie-break still holds. The
    # emergent no-1v1 gate survives the new evaluation.
    ant: Loc = (5, 5)
    east: Loc = (5, 6)
    foes = [(5, 7)]
    modeled = {sq: TS.modeled_foes(sq, foes, _sq, R2, ROWS, COLS) for sq in (east, ant)}
    assert modeled == {east: 1, ant: 1}
    net = {sq: TS.net_value(sq, ant, modeled[sq], 0) for sq in (east, ant)}
    assert net == {east: -1, ant: -1}
    assert TS.pick_best(ant, [east, ant], net, [], _sq, R2) == ant


def test_even_fight_holds_under_net() -> None:
    # 2v2 head-on: ant (5, 5) + buddy (6, 5) vs foes (5, 7) +
    # (6, 7). The eastern step draws 2 modeled foes against 1
    # supporter (net 1, value -1); holding faces 2 with the same
    # supporter (net 1, value -1). Tied scores hold on fewest
    # ants -- even fights still refuse the trade.
    ant: Loc = (5, 5)
    east: Loc = (5, 6)
    mine = [(5, 5), (6, 5)]
    foes = [(5, 7), (6, 7)]
    modeled = {sq: TS.modeled_foes(sq, foes, _sq, R2, ROWS, COLS) for sq in (east, ant)}
    assert modeled[east] == 2
    net = {
        sq: TS.net_value(sq, ant, modeled[sq], TS.support_count(sq, ant, mine, _sq, R2))
        for sq in (east, ant)
    }
    assert net[east] == net[ant] == -1
    assert TS.pick_best(ant, [east, ant], net, mine, _sq, R2) == ant


def test_backed_threatened_ant_advances_full_turn() -> None:
    # Full-turn version of the discriminating contact: (5, 5) +
    # (5, 4) vs (5, 7) is a stage-1 threat (1 of ours vs 1 of
    # theirs in range), but the net evaluation advances the
    # backed hunter east -- base holds here.
    mine = [(5, 5), (5, 4)]
    labels = TS.classify_static(mine, [(5, 7)], _sq, R2)
    assert labels == {(5, 7): TS.THREAT}
    orders, _ = run_turn(mine, [(5, 7)])
    assert ((5, 5), "e") in orders


def test_lone_lurker_still_holds_full_turn() -> None:
    # Lone ant (5, 5) against lurker (5, 9): no backup anywhere,
    # net equals raw, the ant holds the joint plan and explores
    # north -- never east into the modeled contact, as base.
    orders, _ = run_turn([(5, 5)], [(5, 9)])
    assert ((5, 5), "e") not in orders
    assert orders == [((5, 5), "n")]


def test_backed_pair_deterministic() -> None:
    # Same backed-threat board twice: identical orders, no coin
    # flips in the support count, the net score, or the search.
    mine = [(5, 5), (5, 4)]
    foes = [(5, 7)]
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
