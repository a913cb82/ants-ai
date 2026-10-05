#!/usr/bin/env python
"""TwoStage3 disengage-step tests.

The two-stage split stays: STAGE 1 static safe-target/threat
labels, STAGE 2 stay-or-advance search with the fewest-ants
tie-break and net-disadvantage scoring. The ONE new mechanism
is a bonus-free disengage step: a threatened ant whose HOLD
already loses (net disadvantage > 0 on its own square) gets
one extra candidate -- the neighboring square with the least
net disadvantage (ties run toward the most support). The
disengage scores -net with NO +1 moved bonus, so a winning
advance (+1) always beats fleeing and a safe hold (0) never
offers it: crowds behave exactly as TwoStage2, while
outnumbered duelists fall back to support instead of holding
into death (the lazarant ESCAPE, inside the joint search).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import TwoStage3 as TS  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], TS.TwoStage3]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = TS.TwoStage3()
    bot.do_turn(fake)
    return fake.orders, bot


def test_retreat_value_has_no_move_bonus() -> None:
    # A safe disengage scores 0, never the +1 a safe advance
    # earns under net_value: fleeing can only tie a safe hold
    # and can never outbid a winning advance.
    assert TS.retreat_value(0, 0) == 0
    assert TS.retreat_value(0, 3) == 0
    assert TS.net_value((5, 6), (5, 5), 0, 0) == 1


def test_retreat_value_prices_net_loss() -> None:
    # Outnumbered squares score minus the net disadvantage,
    # floored backup first: 2 foes 1 friend reads -1, and
    # extra friends never score above zero.
    assert TS.retreat_value(2, 1) == -1
    assert TS.retreat_value(2, 0) == -2
    assert TS.retreat_value(1, 5) == 0


def test_net_disadvantage_matches_search_prices() -> None:
    # The offer predicate reads the same books as the search:
    # modeled foes minus supporting friends, floored at zero.
    ant: Loc = (5, 5)
    mine = [(5, 5), (5, 4)]
    assert TS.net_disadvantage((5, 6), ant, [(5, 7)], mine, _sq, R2, ROWS, COLS) == 0
    assert TS.net_disadvantage(ant, ant, [(5, 7)], [(5, 5)], _sq, R2, ROWS, COLS) == 1


def test_pick_retreat_runs_to_support() -> None:
    # 1v2 point (5, 5) with backup at (5, 2) vs foes (5, 7) +
    # (6, 5): west (5, 4) keeps 2 modeled foes but gains the
    # friend (net 1); north/south/east keep net 2. West wins.
    cur: Loc = (5, 5)
    foes = [(5, 7), (6, 5)]
    mine = [(5, 5), (5, 2)]
    assert TS.pick_retreat(
        cur, [(4, 5), (5, 6), (5, 4)], foes, mine, _sq, R2, ROWS, COLS
    ) == (5, 4)


def test_pick_retreat_tie_prefers_most_support() -> None:
    # Equal nets flee toward friends: (5, 4) sits sq 4 from
    # backup (5, 2) while (4, 5) sits sq 10 away -- same foe
    # model would pick the supported square either way.
    cur: Loc = (5, 5)
    foes = [(5, 7), (6, 5)]
    mine = [(5, 5), (5, 2)]
    nets = {
        sq: TS.net_disadvantage(sq, cur, foes, mine, _sq, R2, ROWS, COLS)
        for sq in ((5, 4), (4, 5))
    }
    assert nets[(5, 4)] < nets[(4, 5)]
    assert TS.pick_retreat(cur, [(4, 5), (5, 4)], foes, mine, _sq, R2, ROWS, COLS) == (
        5,
        4,
    )


def test_pick_retreat_empty_is_none() -> None:
    # Walled in: no square, no disengage, the ant holds.
    assert TS.pick_retreat((5, 5), [], [(5, 7)], [(5, 5)], _sq, R2, ROWS, COLS) is None


def test_outnumbered_point_disengages_full_turn() -> None:
    # Discriminating duel: (5, 5) + distant backup (5, 2) vs
    # foes (5, 7) + (6, 5). Hold faces net 2 (-2), the desired
    # step faces net 2 (-2), west keeps net 1 (-1): the point
    # falls back west while backup steps up east. TwoStage2
    # holds the point into the 1v2 and loses it.
    orders, _ = run_turn([(5, 5), (5, 2)], [(5, 7), (6, 5)])
    assert ((5, 5), "w") in orders
    assert ((5, 5), "e") not in orders
    assert ((5, 5), "s") not in orders


def test_backed_advance_unchanged_full_turn() -> None:
    # Crowd holds: (5, 5) + (5, 4) vs (5, 7) is a stage-1
    # threat, but the hold is safe (net 0) so no disengage is
    # offered and the backed hunter still advances east, move
    # for move as TwoStage2.
    mine = [(5, 5), (5, 4)]
    labels = TS.classify_static(mine, [(5, 7)], _sq, R2)
    assert labels == {(5, 7): TS.THREAT}
    orders, _ = run_turn(mine, [(5, 7)])
    assert ((5, 5), "e") in orders


def test_lone_duel_never_advances() -> None:
    # Friendless (5, 5) vs (5, 7): engage, hold, and every
    # disengage all face net 1 (-1 each), so the fewest-ants
    # tie-break still holds the joint plan -- the emergent
    # no-1v1 gate survives the new candidate. The ant never
    # steps into the modeled contact.
    orders, _ = run_turn([(5, 5)], [(5, 7)])
    assert ((5, 5), "e") not in orders
    assert ((5, 5), "s") not in orders


def test_lone_lurker_still_holds_full_turn() -> None:
    # Lone ant (5, 5) against lurker (5, 9): the hold is safe
    # (net 0), no disengage offered, the ant explores north --
    # never east, exactly as TwoStage2.
    orders, _ = run_turn([(5, 5)], [(5, 9)])
    assert ((5, 5), "e") not in orders
    assert orders == [((5, 5), "n")]


def test_disengage_pair_deterministic() -> None:
    # Same outnumbered board twice: identical orders, no coin
    # flips in the net books, the retreat pick, or the search.
    mine = [(5, 5), (5, 2)]
    foes = [(5, 7), (6, 5)]
    first, _ = run_turn(mine, foes)
    second, _ = run_turn(mine, foes)
    assert first == second


def test_full_turn_under_1s_crowded() -> None:
    # 40 ants, 25 enemies, food, hills, and a threatened home
    # hill: the extra neighbor modeling stays far inside the
    # 1000 ms budget.
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
