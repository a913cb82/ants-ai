#!/usr/bin/env python
"""Xathis3 cheaper-aggression tests (test-first).

Xathis3 == base Xathis2 except AGGRO_NEED 14 -> 10: aggressive
1-ply with 10+ friends near AND fewer than 10 enemies visible;
otherwise PASSIVE (strict superiority).

Self-contained: FakeAnts + Xathis3 only for behavior, plus
Xathis2 (same dir, champion entry) as the byte-identical base
reference. No engine games, no staging files.

Boards hand-compute deaths and evals; attackradius2 is 5 on every
FakeAnts board, so attack reach is 2 and one-move threat is
manhattan 3. Squared distances use the toroidal board 20x20.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Xathis2 as BASE  # noqa: E402
import Xathis3 as XB  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], XB.Xathis3]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = XB.Xathis3()
    bot.do_turn(fake)
    return fake.orders, bot


def run_base_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = BASE.Xathis2()
    bot.do_turn(fake)
    return fake.orders


def _dist(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


# Fourteen friends within 10 manhattan of (5, 5), every one of them
# outside squared attack range (5) of each candidate dest of (5, 5)
# -- (5, 5), (5, 6), (5, 4), (4, 5), (6, 5) -- so the 1v1 clash is a
# lone mutual trade and only the aggression gate decides it.
# Prefixes give the smaller crowds: [:10], [:11], [:12], [:13], [:9].
_GATE_FRIENDS_14 = [
    (5, 0),
    (5, 1),
    (5, 14),
    (5, 15),
    (5, 16),
    (5, 17),
    (5, 18),
    (5, 19),
    (4, 0),
    (4, 1),
    (6, 0),
    (6, 1),
    (4, 19),
    (6, 19),
]

# Far foes sit around (15, 15): outside approach range of (5, 5)
# and outside attack range of every candidate dest, so they pad
# the visible-enemy count without moving any clash or eval.
_FAR_FOES_11 = [
    (15, 15),
    (15, 16),
    (15, 14),
    (16, 15),
    (14, 15),
    (16, 16),
    (14, 14),
    (16, 14),
    (14, 16),
    (15, 13),
    (13, 15),
]
_FAR_FOES_4 = _FAR_FOES_11[:4]


def test_gate_constants() -> None:
    assert XB.AGGRO_NEED == 10
    assert XB.AGGRO_RADIUS == 10
    assert XB.AGGRO_MAX_ENEMIES == 10
    # The base reference really is the 14-gate champion.
    assert BASE.AGGRO_NEED == 14
    assert BASE.AGGRO_RADIUS == 10
    assert BASE.AGGRO_MAX_ENEMIES == 10


def test_gate_unit_new_threshold() -> None:
    mine10 = [(5, 5)] + _GATE_FRIENDS_14[:10]
    assert XB.count_near((5, 5), mine10, _dist) == 10
    # Exactly at the new gate with few visible: aggressive.
    assert XB.is_aggressive((5, 5), mine10, _dist, n_enemies=0) is True
    assert XB.is_aggressive((5, 5), mine10, _dist, n_enemies=5) is True
    assert XB.is_aggressive((5, 5), mine10, _dist, n_enemies=9) is True
    # Crowded census: passive however many friends stand near.
    assert XB.is_aggressive((5, 5), mine10, _dist, n_enemies=10) is False
    assert XB.is_aggressive((5, 5), mine10, _dist, n_enemies=12) is False
    # One short of the new gate: passive however few enemies show.
    mine9 = [(5, 5)] + _GATE_FRIENDS_14[:9]
    assert XB.count_near((5, 5), mine9, _dist) == 9
    assert XB.is_aggressive((5, 5), mine9, _dist, n_enemies=0) is False
    assert XB.is_aggressive((5, 5), mine9, _dist, n_enemies=5) is False
    # Base still holds the 10-13 crowds: its gate needs 14.
    for n in (10, 11, 12, 13):
        mine = [(5, 5)] + _GATE_FRIENDS_14[:n]
        assert XB.count_near((5, 5), mine, _dist) == n
        assert BASE.is_aggressive((5, 5), mine, _dist, n_enemies=1) is False
        assert XB.is_aggressive((5, 5), mine, _dist, n_enemies=1) is True


def test_10_to_13_near_engage_where_base_holds() -> None:
    # The base 1v1 trade: stepping east onto (5, 6) draws the foe's
    # best reply west onto (5, 8) -- in range, 1-vs-1 mutual,
    # enemyDead 1, myDead 1, dist 2 -> 118 -- over a bloodless hold
    # at dist 3 (-3), so the aggressive 1-ply steps east. Base sees
    # only 10-13 near friends and holds passive (escapes west);
    # Xathis3 clears its 10-gate and steps east into the 1-for-1.
    eye, mye = XB.clash_deaths(0, 1)
    assert (eye, mye) == (1, 1)
    assert XB.combat_eval(eye, mye, 2) == 118
    assert XB.combat_eval(0, 0, 3) == -3
    for n in (10, 11, 12, 13):
        mine = [(5, 5)] + _GATE_FRIENDS_14[:n]
        enemies = [(5, 7)]
        orders, _ = run_turn(mine, enemies)
        assert orders[0] == ((5, 5), "e")
        base_orders = run_base_turn(mine, enemies)
        assert base_orders[0] == ((5, 5), "w")
        assert ((5, 5), "e") not in base_orders


def test_10_near_5_visible_engages() -> None:
    # Padding with 4 far foes (5 visible total) stays under the
    # enemy cap, so the 10-crowd still runs the aggressive 1-ply.
    mine = [(5, 5)] + _GATE_FRIENDS_14[:10]
    enemies = [(5, 7)] + _FAR_FOES_4
    assert len(enemies) == 5
    orders, _ = run_turn(mine, enemies)
    assert orders[0] == ((5, 5), "e")
    base_orders = run_base_turn(mine, enemies)
    assert ((5, 5), "e") not in base_orders


def test_9_near_holds_exactly_as_base() -> None:
    # One short of the new gate: Xathis3 stays passive and matches
    # base order for order -- the escape retreats west, never east.
    mine = [(5, 5)] + _GATE_FRIENDS_14[:9]
    enemies = [(5, 7)]
    orders, _ = run_turn(mine, enemies)
    assert ((5, 5), "e") not in orders
    assert orders == run_base_turn(mine, enemies)
    assert orders[0] == ((5, 5), "w")
    # Same with a few far foes padding the census: still passive.
    enemies5 = [(5, 7)] + _FAR_FOES_4
    orders5, _ = run_turn(mine, enemies5)
    assert orders5 == run_base_turn(mine, enemies5)
    assert ((5, 5), "e") not in orders5


def test_low_friend_boards_byte_identical_to_base() -> None:
    # Every board here is passive for both bots (under 10 near, so
    # under both gates), so the cheaper gate cannot fire and
    # Xathis3 must match base order for order.
    mine9 = [(5, 5)] + _GATE_FRIENDS_14[:9]
    boards: list[tuple[list[Loc], list[Loc], set[Loc] | None]] = [
        ([(5, 5)], [(5, 7), (5, 8)], None),
        (mine9, [(5, 7)], None),
        ([(5, 5)], [(5, 10)], None),
        ([(5, 5)], [(5, 9), (7, 8)], None),
        ([(10, 10)], [(10, 7)], {(7, 10), (6, 10), (7, 9), (8, 9)}),
        ([(5, 5)] + _GATE_FRIENDS_14[:5], [(5, 7)] + _FAR_FOES_4, None),
    ]
    for mine, foes, water in boards:
        orders, _ = run_turn(mine, foes, water=water)
        assert orders == run_base_turn(mine, foes, water=water)


def test_crowded_boards_byte_identical_to_base() -> None:
    # Ten or more enemies visible means passive for both bots even
    # where Xathis3 clears its friend gate, so the boards below
    # must match base order for order (hold the hill of the
    # escape: west, never east).
    mine14 = [(5, 5)] + _GATE_FRIENDS_14
    mine10 = [(5, 5)] + _GATE_FRIENDS_14[:10]
    crowded: list[tuple[list[Loc], list[Loc]]] = [
        (mine14, [(5, 7)] + _FAR_FOES_11),
        (mine14, [(5, 7)] + _FAR_FOES_11[:9]),
        (mine10, [(5, 7)] + _FAR_FOES_11[:9]),
        (mine10, [(5, 7)] + _FAR_FOES_11),
    ]
    for mine, foes in crowded:
        assert len(foes) >= 10
        orders, _ = run_turn(mine, foes)
        assert orders == run_base_turn(mine, foes)
        assert ((5, 5), "e") not in orders


def test_boundary_9_engages_10_holds_at_10_near() -> None:
    # Fewer than 10 visible means aggressive; 10 means passive --
    # now with a 10-crowd instead of the base 14-crowd.
    mine = [(5, 5)] + _GATE_FRIENDS_14[:10]
    nine = [(5, 7)] + _FAR_FOES_11[:8]
    ten = [(5, 7)] + _FAR_FOES_11[:9]
    assert len(nine) == 9
    assert len(ten) == 10
    orders9, _ = run_turn(mine, nine)
    assert orders9[0] == ((5, 5), "e")
    orders10, _ = run_turn(mine, ten)
    assert orders10[0] == ((5, 5), "w")
    assert ((5, 5), "e") not in orders10
    assert orders10 == run_base_turn(mine, ten)


def test_eval_weights_accept_1for1_and_3for2_never_2for1() -> None:
    # The eval is untouched: only the gate moved.
    assert XB.combat_eval(1, 1, 0) - XB.combat_eval(0, 0, 0) == 120
    assert XB.combat_eval(2, 3, 0) - XB.combat_eval(0, 0, 0) == 60
    assert XB.combat_eval(1, 2, 0) - XB.combat_eval(0, 0, 0) == -60
    assert XB.combat_eval(1, 1, 5) == 300 - 180 - 5


def test_lone_ant_vs_two_holds_never_2for1() -> None:
    mine = [(5, 5)]
    foes = [(5, 7), (5, 8)]
    eye, mye = XB.clash_deaths(0, 2)
    assert (eye, mye) == (0, 1)
    assert XB.combat_eval(eye, mye, 0) < XB.combat_eval(0, 0, 1)
    orders, _ = run_turn(mine, foes)
    assert ((5, 5), "e") not in orders
    assert orders == run_base_turn(mine, foes)


def test_gate_check_under_half_ms_crowded() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    reps = 2000
    start = time.perf_counter()
    for _ in range(reps):
        XB.is_aggressive(mine[0], mine, _dist, n_enemies=12)
    elapsed = (time.perf_counter() - start) / reps
    assert elapsed < 0.0005


def test_full_turn_under_1s_on_crowded_board() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(10)]
    start = time.perf_counter()
    orders, _ = run_turn(mine, foes)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(orders) > 0
