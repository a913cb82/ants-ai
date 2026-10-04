#!/usr/bin/env python
"""Xathis4 cheaper-deaths tests (test-first).

Xathis4 == Xathis3 except DEATH_COST 180 -> 120: the aggressive
eval prices own deaths at 120 instead of 180
(enemyDead*300 - myDead*120 - dist), accepting bloodier trades.
Gate, passive path, and clash are untouched.

Self-contained: FakeAnts + Xathis4 for behavior, plus Xathis3
(same dir, base entry) as the byte-identical reference. No engine
games, no staging files.

Boards hand-compute deaths and evals; attackradius2 is 5 on every
FakeAnts board, so attack reach is squared 5 and one-move threat
is manhattan 11 (APPROACH_RANGE 8 + threat_reach 3). Squared
distances use the toroidal board 20x20.

Board A (the flip): M=(5,5) with 10 friends near (F_N=(2,4),
F_E=(7,7), eight far) and foes E1=(5,8), E2=(4,8). Replies are
single steps, strict improvement, n/e/s/w order:
- east (5,6): E1->(5,7) sq1, E2->(5,8) sq4: 2 attackers;
  F_E sq5: 1 supporter -> (2,2), near 1.
  base: 600-360-1=239; new: 600-240-1=359.
- north (4,5): E1->(4,8) sq9, E2->(4,7) sq4: 1 attacker;
  F_N sq5: 1 supporter -> (1,0), near 2: 298 both.
- hold: E1->(5,7) sq4, E2->(5,8) sq9: 1 attacker, 0 support
  -> (1,1), near 2: base 118, new 178.
- south (6,5): replies (6,8)/(5,8), both out of range: (0,0),
  near 3: -3 both. west (5,4): (0,0), near 3: -3 both.
Base ranks north 298 first (holds off the bloody square); new
ranks east 359 first (takes the profitable 2-for-2).

Board B (overrun refused): M=(5,5) with 10 far friends and foes
E1=(5,8), E2=(3,8). East (5,6): E1->(5,7) sq1, E2->(4,8) sq5:
2 attackers, 0 support -> (0,1), near 1: base -181, new -121.
Hold: E1->(5,7) sq4, E2->(4,8) sq10: 1 attacker -> (1,1),
near 2: base 118, new 178. North/south/west are (0,0) at -3.
Both hold; the overrun square loses under both weights.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Xathis3 as BASE  # noqa: E402
import Xathis4 as XB  # noqa: E402

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


def _dist(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


def _sq_dist(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


def run_new_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = XB.Xathis4()
    bot.do_turn(fake)
    return fake.orders


def run_base_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = BASE.Xathis3()
    bot.do_turn(fake)
    return fake.orders


def search_new(mine: list[Loc], enemies: list[Loc]):
    fake = FakeAnts(mine, enemies)
    return XB.search_best_move(
        mine[0],
        mine,
        enemies,
        fake.destination,
        fake.passable,
        fake.distance,
        _sq_dist,
        ROWS,
        COLS,
        5,
        set(),
    )


def search_base(mine: list[Loc], enemies: list[Loc]):
    fake = FakeAnts(mine, enemies)
    return BASE.search_best_move(
        mine[0],
        mine,
        enemies,
        fake.destination,
        fake.passable,
        fake.distance,
        _sq_dist,
        ROWS,
        COLS,
        5,
        set(),
    )


# Ten far friends: each within 10 manhattan of (5, 5) (gate counts
# them) but outside squared attack range (5) of every candidate
# dest of (5, 5), so they pad the gate without touching a clash.
_FAR10 = [
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
]

# Board A friends: two clash shapers plus the first eight far pads.
_BOARD_A_MINE = [(5, 5), (2, 4), (7, 7)] + _FAR10[:8]
_BOARD_A_FOES = [(5, 8), (4, 8)]

# Board B: ten far friends plus a higher enemy pair.
_BOARD_B_MINE = [(5, 5)] + _FAR10
_BOARD_B_FOES = [(5, 8), (3, 8)]

# Far foes around (15, 15): outside approach range of (5, 5) and
# outside attack range of its dests; they pad the visible-enemy
# count without moving any clash or eval.
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


def test_constants() -> None:
    assert XB.KILL_SCORE == 300
    assert XB.DEATH_COST == 120
    # The base reference really is the 180-weight champion.
    assert BASE.KILL_SCORE == 300
    assert BASE.DEATH_COST == 180
    # Everything else identical: same gate, same ranges.
    assert XB.AGGRO_NEED == BASE.AGGRO_NEED == 10
    assert XB.AGGRO_RADIUS == BASE.AGGRO_RADIUS == 10
    assert XB.AGGRO_MAX_ENEMIES == BASE.AGGRO_MAX_ENEMIES == 10
    assert XB.APPROACH_RANGE == BASE.APPROACH_RANGE == 8
    assert XB.ESCAPE_RADIUS == BASE.ESCAPE_RADIUS == 3


def test_eval_hand_values() -> None:
    # The flip pair: bloody 2-for-2 vs safe 1-for-0 wipe.
    assert XB.combat_eval(2, 2, 1) == 600 - 240 - 1 == 359
    assert BASE.combat_eval(2, 2, 1) == 600 - 360 - 1 == 239
    assert XB.combat_eval(1, 0, 2) == 300 - 2 == 298
    assert BASE.combat_eval(1, 0, 2) == 298
    # Overrun still refused: below any bloodless move.
    assert XB.combat_eval(0, 1, 1) == -121 < XB.combat_eval(0, 0, 3) == -3
    assert BASE.combat_eval(0, 1, 1) == -181
    # 1-for-1 taken under both (nearer hold loses by 1).
    assert XB.combat_eval(1, 1, 1) == 179 > XB.combat_eval(1, 1, 2) == 178
    assert BASE.combat_eval(1, 1, 1) == 119 > BASE.combat_eval(1, 1, 2) == 118
    # Eval-level 2-for-1 flips sign on paper (60 vs -60) but the
    # clash below never emits it, so behavior cannot take it.
    assert XB.combat_eval(1, 2, 0) == 60
    assert BASE.combat_eval(1, 2, 0) == -60


def test_clash_never_emits_2for1() -> None:
    # Sweep every local force ratio: a kill never costs more ants
    # than it kills (superiority wipes free, equals trade evenly,
    # outnumbered dies for nothing). Both bots share this clash.
    for supporters in range(6):
        for attackers in range(6):
            for clash in (XB.clash_deaths, BASE.clash_deaths):
                killed, lost = clash(supporters, attackers)
                assert not (killed > 0 and lost > killed)
    assert XB.clash_deaths(1, 2) == (2, 2)
    assert XB.clash_deaths(1, 1) == (1, 0)
    assert XB.clash_deaths(0, 2) == (0, 1)
    assert XB.clash_deaths(1, 0) == (0, 0)


def test_flip_board_gate() -> None:
    assert XB.count_near((5, 5), _BOARD_A_MINE, _dist) == 10
    assert XB.is_aggressive((5, 5), _BOARD_A_MINE, _dist, n_enemies=2) is True
    # Base sees the same crowd but prices deaths at 180.
    assert BASE.count_near((5, 5), _BOARD_A_MINE, _dist) == 10
    assert BASE.is_aggressive((5, 5), _BOARD_A_MINE, _dist, n_enemies=2) is True


def test_flip_board_search_verdicts() -> None:
    # Hand-computed above: base takes the safe wipe north at 298
    # (the bloody east square only scores 239); new takes the
    # bloody 2-for-2 east at 359 (over the same 298 wipe).
    assert search_base(_BOARD_A_MINE, _BOARD_A_FOES) == ("n", (4, 5), 298)
    assert search_new(_BOARD_A_MINE, _BOARD_A_FOES) == ("e", (5, 6), 359)


def test_flip_board_behavior() -> None:
    orders = run_new_turn(_BOARD_A_MINE, _BOARD_A_FOES)
    assert orders[0] == ((5, 5), "e")
    base_orders = run_base_turn(_BOARD_A_MINE, _BOARD_A_FOES)
    assert base_orders[0] == ((5, 5), "n")
    assert ((5, 5), "e") not in base_orders


def test_overrun_refused_search() -> None:
    # Hand-computed above: the east overrun square scores -181 at
    # base weights and -121 at new weights, both below the hold
    # verdict (118 / 178), so both hold at (5, 5).
    assert search_base(_BOARD_B_MINE, _BOARD_B_FOES) == (None, (5, 5), 118)
    assert search_new(_BOARD_B_MINE, _BOARD_B_FOES) == (None, (5, 5), 178)


def test_overrun_refused_behavior() -> None:
    orders = run_new_turn(_BOARD_B_MINE, _BOARD_B_FOES)
    assert orders == run_base_turn(_BOARD_B_MINE, _BOARD_B_FOES)
    assert not any(origin == (5, 5) for origin, _ in orders)


def test_lone_ant_vs_two_byte_identical() -> None:
    # Passive (no friends near): strict superiority refuses the
    # 1-vs-2 no matter the death price; never a 2-for-1.
    mine = [(5, 5)]
    foes = [(5, 7), (5, 8)]
    assert XB.clash_deaths(0, 2) == (0, 1)
    orders = run_new_turn(mine, foes)
    assert orders == run_base_turn(mine, foes)
    assert ((5, 5), "e") not in orders


def test_aggressive_1for1_byte_identical() -> None:
    # One foe: east is a 1-for-1 at near 1 (119 / 179) over hold at
    # near 2 (118 / 178), so both step east. A single foe means no
    # dest can lose more than it kills, so every option scores
    # weight-independently except the shared +60/death shift, which
    # preserves the ranking: full orders match.
    mine = [(5, 5)] + _FAR10
    foes = [(5, 8)]
    assert search_base(mine, foes) == ("e", (5, 6), 119)
    assert search_new(mine, foes) == ("e", (5, 6), 179)
    orders = run_new_turn(mine, foes)
    assert orders == run_base_turn(mine, foes)
    assert orders[0] == ((5, 5), "e")


def test_passive_boards_byte_identical() -> None:
    # Passive for both bots (under 10 near, or 10+ enemies
    # visible): the death price never fires, so every board below
    # matches order for order.
    mine9 = [(5, 5)] + _FAR10[:9]
    mine15 = [(5, 5)] + _FAR10 + [(4, 19), (6, 19), (6, 0), (6, 1), (4, 1)]
    boards: list[tuple[list[Loc], list[Loc], set[Loc] | None]] = [
        ([(5, 5)], [(5, 7)], None),
        (mine9, [(5, 7)], None),
        ([(5, 5)], [(5, 7)] + _FAR_FOES_11, None),
        (mine15, [(5, 7)] + _FAR_FOES_11, None),
        (mine9, [(5, 7)] + _FAR_FOES_11[:4], None),
        ([(10, 10)], [(10, 7)], {(7, 10), (6, 10), (7, 9), (8, 9)}),
        ([(5, 5)], [(5, 10)], None),
    ]
    for mine, foes, water in boards:
        orders = run_new_turn(mine, foes, water=water)
        assert orders == run_base_turn(mine, foes, water=water)


def test_economy_board_byte_identical() -> None:
    # No combat on this board (foes far): food, hills, and water
    # paths are untouched, so orders match exactly.
    mine = [(5, 5), (10, 10), (10, 11)]
    foods = [(5, 8), (12, 12)]
    water = {(6, 5), (6, 6), (11, 10)}
    orders = run_new_turn(
        mine, [(15, 15)], foods=foods, water=water, enemy_hills=[(15, 15)]
    )
    assert orders == run_base_turn(
        mine, [(15, 15)], foods=foods, water=water, enemy_hills=[(15, 15)]
    )
    assert len(orders) > 0


def test_gate_check_under_half_ms_crowded() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    reps = 2000
    start = time.perf_counter()
    for _ in range(reps):
        XB.is_aggressive(mine[0], mine, _dist, n_enemies=12)
    elapsed = (time.perf_counter() - start) / reps
    assert elapsed < 0.0005


def test_per_fight_under_50ms_crowded() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(12)]
    fake = FakeAnts(mine, foes)
    start = time.perf_counter()
    direction, dest, score = XB.search_best_move(
        mine[0],
        mine,
        foes,
        fake.destination,
        fake.passable,
        fake.distance,
        _sq_dist,
        ROWS,
        COLS,
        5,
        set(),
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 0.05
    assert isinstance(direction, (str, type(None)))
    assert isinstance(score, int)
    assert dest in [mine[0]] + [fake.destination(mine[0], d) for d in "nesw"]


def test_full_turn_under_1s_on_crowded_board() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(10)]
    start = time.perf_counter()
    orders = run_new_turn(mine, foes)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(orders) > 0
