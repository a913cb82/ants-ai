#!/usr/bin/env python
"""Xathis2 small-fight aggression tests (test-first).

Xathis2 == base Xathis except the AGGRESSIVE gate also counts
enemies: aggressive 1-ply only with 14+ friends near AND fewer
than 10 enemies visible; otherwise PASSIVE (strict superiority).

Self-contained: FakeAnts + Xathis2 only for behavior, plus Xathis
(same dir, main-tree entry) as the byte-identical base reference
for passive boards. No engine games, no combat.py, no staging
files.

Boards hand-compute deaths and evals; attackradius2 is 5 on every
FakeAnts board, so attack reach is 2 and one-move threat is
manhattan 3. Squared distances use the toroidal board 20x20.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Xathis as BASE  # noqa: E402
import Xathis2 as XB  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], XB.Xathis2]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = XB.Xathis2()
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
    bot = BASE.Xathis()
    bot.do_turn(fake)
    return fake.orders


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


def _dest(loc: Loc, direction: str) -> Loc:
    dr, dc = AIM[direction]
    return ((loc[0] + dr) % ROWS, (loc[1] + dc) % COLS)


def deeply_passable(loc: Loc) -> bool:
    return True


# Fourteen friends within 10 manhattan of (5, 5), every one of them
# outside squared attack range (5) of each candidate dest of (5, 5)
# -- (5, 5), (5, 6), (5, 4), (4, 5), (6, 5) -- so the 1v1 clash is a
# lone mutual trade and only the aggression gate decides it.
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
_GATE_FRIENDS_13 = _GATE_FRIENDS_14[:13]

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
    assert XB.AGGRO_NEED == 14
    assert XB.AGGRO_RADIUS == 10
    assert XB.AGGRO_MAX_ENEMIES == 10


def test_gate_unit_friends_and_enemies() -> None:
    mine = [(5, 5)] + _GATE_FRIENDS_14
    assert XB.count_near((5, 5), mine, _dist) == 14
    # Few enemies: aggressive, exactly like the base gate.
    assert XB.is_aggressive((5, 5), mine, _dist, n_enemies=5) is True
    assert XB.is_aggressive((5, 5), mine, _dist, n_enemies=0) is True
    assert XB.is_aggressive((5, 5), mine, _dist, n_enemies=9) is True
    # Crowded census: passive however many friends stand near.
    assert XB.is_aggressive((5, 5), mine, _dist, n_enemies=10) is False
    assert XB.is_aggressive((5, 5), mine, _dist, n_enemies=12) is False
    # Too few friends: passive however few enemies show.
    short = [(5, 5)] + _GATE_FRIENDS_13
    assert XB.is_aggressive((5, 5), short, _dist, n_enemies=5) is False
    assert XB.is_aggressive((5, 5), short, _dist, n_enemies=0) is False


def test_14_near_12_visible_holds_passive_where_base_engages() -> None:
    # The base 1v1 trade: stepping east onto (5, 6) draws the foe's
    # best reply west onto (5, 8) -- in range, 1-vs-1 mutual,
    # enemyDead 1, myDead 1, dist 2 -> 118 -- over a bloodless hold
    # at dist 3 (-3), so base Xathis steps east. Xathis2 sees 12
    # visible enemies (1 near + 11 far) and holds passive: east is
    # contact-unsafe, so the escape retreats west, never east.
    mine = [(5, 5)] + _GATE_FRIENDS_14
    enemies = [(5, 7)] + _FAR_FOES_11
    assert len(enemies) == 12
    eye, mye = XB.clash_deaths(0, 1)
    assert (eye, mye) == (1, 1)
    assert XB.combat_eval(eye, mye, 2) == 118
    assert XB.combat_eval(0, 0, 3) == -3
    base_orders = run_base_turn(mine, [(5, 7)])
    assert base_orders[0] == ((5, 5), "e")
    orders, _ = run_turn(mine, enemies)
    assert orders[0] == ((5, 5), "w")
    assert ((5, 5), "e") not in orders


def test_14_near_5_visible_engages_exactly_as_base() -> None:
    # Same fight with 5 visible (1 near + 4 far): under the enemy
    # cap, so Xathis2 runs the aggressive 1-ply and steps east into
    # the 1-for-1 -- byte-identical to base on this board.
    mine = [(5, 5)] + _GATE_FRIENDS_14
    enemies = [(5, 7)] + _FAR_FOES_4
    assert len(enemies) == 5
    orders, _ = run_turn(mine, enemies)
    assert orders[0] == ((5, 5), "e")
    assert orders == run_base_turn(mine, enemies)


def test_boundary_9_engages_10_holds() -> None:
    # Fewer than 10 visible means aggressive; 10 means passive.
    mine = [(5, 5)] + _GATE_FRIENDS_14
    nine = [(5, 7)] + _FAR_FOES_11[:8]
    ten = [(5, 7)] + _FAR_FOES_11[:9]
    assert len(nine) == 9
    assert len(ten) == 10
    orders9, _ = run_turn(mine, nine)
    assert orders9[0] == ((5, 5), "e")
    orders10, _ = run_turn(mine, ten)
    assert orders10[0] == ((5, 5), "w")
    assert ((5, 5), "e") not in orders10


def test_passive_boards_byte_identical_to_base() -> None:
    # Every board here is passive for both bots (base never sees
    # 14 near friends, or the verdict is a hold), so the small-fight
    # gate cannot fire and Xathis2 must match base order for order.
    mine13 = [(5, 5)] + _GATE_FRIENDS_13
    boards: list[tuple[list[Loc], list[Loc], set[Loc] | None]] = [
        ([(5, 5)], [(5, 7), (5, 8)], None),
        (mine13, [(5, 7)], None),
        ([(5, 5)], [(5, 10)], None),
        ([(10, 10)], [(10, 7)], {(7, 10), (6, 10), (7, 9), (8, 9)}),
        ([(5, 5)], [(5, 9), (7, 8)], None),
    ]
    for mine, foes, water in boards:
        orders, _ = run_turn(mine, foes, water=water)
        assert orders == run_base_turn(mine, foes, water=water)


def test_eval_weights_accept_1for1_and_3for2_never_2for1() -> None:
    assert XB.combat_eval(1, 1, 0) - XB.combat_eval(0, 0, 0) == 120
    assert XB.combat_eval(2, 3, 0) - XB.combat_eval(0, 0, 0) == 60
    assert XB.combat_eval(1, 2, 0) - XB.combat_eval(0, 0, 0) == -60
    assert XB.combat_eval(1, 1, 5) == 300 - 180 - 5


def test_aggressive_3v2_small_fight_engages() -> None:
    # Hand-computed 3v2 under the enemy cap: ant (5, 5) backed by
    # (5, 4) and (4, 6) steps east onto (5, 6) against foes (5, 7)
    # and (5, 8). Both best-reply into range: attackers 2,
    # supporters 2, ours 3 > 2, enemyDead 2, myDead 0, dist 0 ->
    # 600 over the 599 hold. Max eval advances east.
    foes = [(5, 7), (5, 8)]
    backers = [(5, 4), (4, 6)]
    fillers = [
        (14, 4),
        (14, 5),
        (14, 6),
        (15, 5),
        (13, 4),
        (13, 5),
        (13, 6),
        (12, 4),
        (12, 5),
        (12, 6),
        (11, 4),
        (11, 5),
    ]
    mine = [(5, 5)] + backers + fillers
    assert XB.count_near((5, 5), mine, _dist) == 14
    eye, mye = XB.clash_deaths(2, 2)
    assert (eye, mye) == (2, 0)
    assert XB.combat_eval(eye, mye, 0) == 600
    assert XB.combat_eval(eye, mye, 1) == 599
    orders, _ = run_turn(mine, foes)
    assert orders[0] == ((5, 5), "e")
    assert orders == run_base_turn(mine, foes)


def test_lone_ant_vs_two_holds_never_2for1() -> None:
    mine = [(5, 5)]
    foes = [(5, 7), (5, 8)]
    eye, mye = XB.clash_deaths(0, 2)
    assert (eye, mye) == (0, 1)
    assert XB.combat_eval(eye, mye, 0) < XB.combat_eval(0, 0, 1)
    orders, _ = run_turn(mine, foes)
    assert ((5, 5), "e") not in orders
    assert orders == run_base_turn(mine, foes)


def test_enemy_best_reply_closes_distance() -> None:
    assert _sq((5, 6), (5, 9)) > 5
    reply = XB.best_enemy_reply((5, 6), (5, 9), _dest, deeply_passable, _dist)
    assert reply == (5, 8)
    assert _sq((5, 6), reply) <= 5


def test_escape_picks_opener_safe_square() -> None:
    water = {(7, 10), (6, 10), (7, 9), (8, 9)}

    def gated(loc: Loc) -> bool:
        return loc not in water

    assert XB.openness((9, 10), gated, ROWS, COLS) == 21
    assert XB.openness((10, 11), gated, ROWS, COLS) == 25
    assert XB.openness((11, 10), gated, ROWS, COLS) == 25
    orders, _ = run_turn([(10, 10)], [(10, 7)], water=water)
    assert orders[0] == ((10, 10), "e")
    assert orders[0] != ((10, 10), "n")


def test_approach_advances_toward_nearest_enemy() -> None:
    mine = [(5, 5)]
    enemies = [(5, 10)]
    probe = FakeAnts(mine, enemies)
    assert probe.distance((5, 5), (5, 10)) == 5
    assert XB.nearest_approach_enemy((5, 5), enemies, probe.distance) == (5, 10)
    assert XB.nearest_approach_enemy((5, 5), [(5, 14)], probe.distance) is None
    orders, _ = run_turn(mine, enemies)
    assert orders[0] == ((5, 5), "e")
    moved = probe.destination((5, 5), orders[0][1])
    assert probe.distance(moved, (5, 10)) == 4


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


def test_per_fight_search_under_50ms() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(10)]
    claimed: set[Loc] = set()
    reps = 20
    start = time.perf_counter()
    for _ in range(reps):
        XB.search_best_move(
            mine[0],
            mine,
            foes,
            _dest,
            deeply_passable,
            _dist,
            _sq,
            ROWS,
            COLS,
            5,
            claimed,
        )
    elapsed = (time.perf_counter() - start) / reps
    assert elapsed < 0.05
