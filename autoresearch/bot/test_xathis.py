#!/usr/bin/env python
"""Xathis two-mode 1-ply combat tests (faithful 2011-winner approach).

Self-contained: FakeAnts + Xathis only, no engine games, no combat.py.

Xathis replaces the champion combat core with the RESEARCH.md rows
"Combat eval trades ants for position" (aggressive 1-ply
enemyDead*300 - myDead*180 - dist with enemy best-reply when 14+
friends are within 10 steps, else strict passive), "Approach forms
fighting lines" (enemy in range -> advance via first_step), and
"Escape picks max space" (safest retreat is the most open square).

Boards below hand-compute deaths and evals; attackradius2 is 5 on
every FakeAnts board, so attack reach is 2 and one-move threat is
manhattan 3. Squared distances use the toroidal board 20x20.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Xathis as XB  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], XB.Xathis]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = XB.Xathis()
    bot.do_turn(fake)
    return fake.orders, bot


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


def test_aggro_gate_constant_is_fourteen() -> None:
    assert XB.AGGRO_NEED == 14
    assert XB.AGGRO_RADIUS == 10


def test_eval_weights_accept_1for1_and_3for2_never_2for1() -> None:
    # Pure arithmetic of enemyDead*300 - myDead*180 - dist: a 1-for-1
    # scores +120 over a bloodless hold at the same distance, a
    # 3-for-2 still scores +60, and a 2-for-1 (lose 2, kill 1)
    # scores -60, so the search takes the first two and never the
    # third however close it steps.
    assert XB.combat_eval(1, 1, 0) - XB.combat_eval(0, 0, 0) == 120
    assert XB.combat_eval(2, 3, 0) - XB.combat_eval(0, 0, 0) == 60
    assert XB.combat_eval(1, 2, 0) - XB.combat_eval(0, 0, 0) == -60
    assert XB.combat_eval(1, 1, 5) == 300 - 180 - 5


def test_14_near_1v1_engages() -> None:
    # Aggressive: ant (5, 5) faces one foe on (5, 7). Stepping east
    # onto (5, 6) draws the foe's best reply west onto (5, 8): in
    # range, so 1-vs-1 mutual, enemyDead 1, myDead 1, dist 2 ->
    # 118. Holding draws the same reply, out of range there:
    # bloodless at dist 3 -> -3. Other steps score -4. Max eval
    # steps east (1-for-1).
    mine = [(5, 5)] + _GATE_FRIENDS_14
    assert XB.count_near((5, 5), mine, _dist) == 14
    assert XB.is_aggressive((5, 5), mine, _dist) is True
    eye, mye = XB.clash_deaths(0, 1)
    assert (eye, mye) == (1, 1)
    assert XB.combat_eval(eye, mye, 2) == 118
    assert XB.combat_eval(0, 0, 3) == -3
    orders, _ = run_turn(mine, [(5, 7)])
    assert orders[0] == ((5, 5), "e")


def test_13_near_1v1_holds() -> None:
    # Passive: the same 1v1 with 13 near friends refuses the equal
    # trade (strict superiority only). East, north, and south are
    # all contact-unsafe, so the escape retreats west -- the only
    # safe square -- and never steps east into the trade.
    mine = [(5, 5)] + _GATE_FRIENDS_13
    assert XB.count_near((5, 5), mine, _dist) == 13
    assert XB.is_aggressive((5, 5), mine, _dist) is False
    orders, _ = run_turn(mine, [(5, 7)])
    assert orders[0] == ((5, 5), "w")
    assert ((5, 5), "e") not in orders


def test_aggressive_3v2_engages() -> None:
    # Hand-computed 3v2: ant (5, 5) backed by (5, 4) and (4, 6)
    # steps east onto (5, 6) against foes (5, 7) and (5, 8). Both
    # foes best-reply into range (5, 6) and (5, 7): attackers 2,
    # supporters 2, ours 3 > 2, so enemyDead 2, myDead 0, dist 0 ->
    # 600. Holding scores 599 (dist 1). Max eval advances east.
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


def test_lone_ant_vs_two_holds_never_2for1() -> None:
    # One ant facing two foes: every contact outcome loses without
    # killing (attackers 2 > ours 1 -> enemyDead 0, myDead 1), so
    # the passive ant never steps east into the 2-for-1 loss. The
    # only escape is west; east never issues.
    mine = [(5, 5)]
    foes = [(5, 7), (5, 8)]
    eye, mye = XB.clash_deaths(0, 2)
    assert (eye, mye) == (0, 1)
    assert XB.combat_eval(eye, mye, 0) < XB.combat_eval(0, 0, 1)
    orders, _ = run_turn(mine, foes)
    assert ((5, 5), "e") not in orders


def test_enemy_best_reply_closes_distance() -> None:
    # Pure: a foe on (5, 9) answering our step onto (5, 6) moves
    # west to (5, 8) -- the passable reply nearest our dest -- not
    # holding on (5, 9) where static-range math would leave it.
    assert _sq((5, 6), (5, 9)) > 5
    reply = XB.best_enemy_reply((5, 6), (5, 9), _dest, deeply_passable, _dist)
    assert reply == (5, 8)
    assert _sq((5, 6), reply) <= 5


def test_best_reply_refuses_static_safe_advance() -> None:
    # Foes (5, 9) and (7, 8) both sit outside static attack range
    # of east onto (5, 6) (sq 9 and 8 > 5), so static math calls
    # east bloodless-safe; but both foes best-reply into range --
    # (5, 8) and (6, 8) -- turning east into a doomed 0-for-1
    # (-182). Holding stays bloodless (-3) and beats every step,
    # so the aggressive ant holds and issues no order from it.
    mine = [(5, 5)] + _GATE_FRIENDS_14
    assert _sq((5, 6), (5, 9)) > 5
    assert _sq((5, 6), (7, 8)) > 5
    eye, mye = XB.clash_deaths(0, 2)
    assert (eye, mye) == (0, 1)
    assert XB.combat_eval(eye, mye, 2) == -182
    assert XB.combat_eval(0, 0, 3) == -3
    orders, _ = run_turn(mine, [(5, 9), (7, 8)])
    assert [o for o in orders if o[0] == (5, 5)] == []


def test_escape_picks_opener_safe_square() -> None:
    # Passive ant (10, 10), foe (10, 7): first_step west onto
    # (10, 9) is contact-unsafe (sq 4), so the escape compares the
    # safe retreats. Northern water leaves (9, 10) at openness 21
    # while (10, 11) and (11, 10) stand at 25; it steps east.
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
    # No food, no hills: a passive ant with a foe 5 steps east
    # advances east via first_step pathing -- one step nearer the
    # enemy -- instead of exploring empty ground.
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
