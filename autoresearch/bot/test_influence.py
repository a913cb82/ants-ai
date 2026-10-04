#!/usr/bin/env python
"""Memetix influence combat tests (faithful Influence entry).

Self-contained: FakeAnts plus the Influence entry only, never the
shared combat.py helpers. Pins (a) hand-computed two-field counts
on a fixed 3v3 diamond board, (b) the overcount refinement on a
stacked-attackers board, (c) KILL taken on a contested-hill turn
and in contact without a SAFE move, refused otherwise, (d) DIE
refused where the old majority filter accepts, and (e) the 5ms
precompute plus 1s turn budgets.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Influence as IP  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], IP.Influence]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = IP.Influence()
    bot.do_turn(fake)
    return fake.orders, bot


def _sq(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


def _manhattan(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


def old_majority_accepts(nloc: Loc, self_loc: Loc, mine: list[Loc]) -> bool:
    """Reference: the champion Crowd majority safety filter.

    Zero foes in attack range accepts; strict superiority
    accepts; equal trades need 10+ near friends (Odds gate).
    Mirrors Crowd.is_safe with attackradius2 5.
    """
    foes_here = [e for e in _DIE_FOES if _sq(nloc, e) <= 5]
    if not foes_here:
        return True
    friends = sum(1 for f in mine if f != self_loc and _sq(nloc, f) <= 5)
    if friends + 1 > len(foes_here):
        return True
    near = sum(1 for f in mine if f != self_loc and _manhattan(nloc, f) <= 10)
    return near >= 10 and friends + 1 >= len(foes_here)


# Fixed boards. The hunter (5, 5) holds no food claim and no guard
# duty, so the seek branch decides east onto (5, 6) first.
DIA_OURS = [(5, 4), (5, 5), (5, 6)]
DIA_FOES = [(12, 12), (12, 13), (12, 14)]
_DIE_MINE = [(5, 5), (5, 1), (5, 2), (6, 1)]
_DIE_FOES = [(5, 9), (2, 6), (8, 6), (2, 4), (8, 4), (6, 2)]
_KILL_MINE = [(5, 5), (5, 1), (5, 2), (6, 1)]
_KILL_FOES = [(5, 8), (15, 15), (15, 16), (16, 15), (0, 0)]
# In-contact deadlock: a lone foe at (5, 7) holds the hunter in
# contact while every neighbor refines to KILL (raw 1 v ours 1),
# so with no hill remembered no SAFE move exists anywhere.
CONTACT_MINE = [(5, 5)]
CONTACT_FOES = [(5, 7)]
# Control: two friends back the north escape, so (4, 5) refines to
# SAFE (ours 3 -> 2 beats theirs 2 -> 1) and the KILL must wait.
CONTACT_SAFE_MINE = [(5, 5), (4, 4), (4, 3)]


def test_threat_reach_derives_from_attack_radius() -> None:
    # The one-move threat radius for attackradius2 5 is manhattan 3:
    # attack reach 2 plus the step.
    assert IP.threat_reach(5) == 3


def test_influence_fields_count_both_sides_after_one_move() -> None:
    # (a) Hand-computed 3v3 diamond board, reach 3. Each side's
    # trio stamps its own field only; overlapping diamonds add.
    own, foe = IP.influence_fields(DIA_OURS, DIA_FOES, ROWS, COLS, 3)
    # Own trio row: center covered by all three, edges fall off.
    assert own[5][5] == 3
    assert own[5][8] == 2
    assert own[5][9] == 1
    assert own[5][10] == 0
    assert own[8][5] == 1
    assert own[9][5] == 0
    # Enemy trio is far: nothing leaks into our cluster.
    assert foe[5][5] == 0
    assert own[12][13] == 0
    # Enemy trio mirrors ours around (12, 13).
    assert foe[12][13] == 3
    assert foe[12][16] == 2
    assert foe[12][17] == 1
    assert foe[9][13] == 1
    assert foe[15][13] == 1
    assert foe[16][13] == 0


def test_influence_fields_single_ant_diamond_shape() -> None:
    # (a) One ant stamps exactly its manhattan-3 diamond: axis 3
    # in, axis 4 and far diagonals out.
    own, foe = IP.influence_fields([(5, 5)], [(15, 15)], ROWS, COLS, 3)
    assert own[5][5] == 1
    assert own[5][8] == 1
    assert own[8][5] == 1
    assert own[5][9] == 0
    assert own[9][5] == 0
    assert own[8][6] == 0
    assert own[0][0] == 0
    assert foe[15][15] == 1
    assert foe[15][18] == 1
    assert foe[15][19] == 0
    assert own[15][15] == 0
    assert foe[5][5] == 0
    empty_own, empty_foe = IP.influence_fields([], [], ROWS, COLS, 3)
    assert empty_own[5][5] == 0
    assert empty_foe[5][5] == 0


def test_refinement_discounts_stacked_attackers() -> None:
    # (b) First attacker counts fully, extras count half (floor):
    # 0 stays 0, 1 stays 1, pairs collapse to 1, triples to 2.
    assert IP.refine(0) == 0
    assert IP.refine(1) == 1
    assert IP.refine(2) == 1
    assert IP.refine(3) == 2
    assert IP.refine(4) == 2
    assert IP.refine(5) == 3
    # Stacked board: three foes all reach (5, 6) at manhattan
    # 1, 2, 3, so the raw count is 3 but the refined count is 2.
    _, foe = IP.influence_fields([], [(5, 7), (5, 8), (5, 9)], ROWS, COLS, 3)
    assert foe[5][6] == 3
    assert IP.refine(foe[5][6]) == 2


def test_classify_counts_refined_verdicts() -> None:
    # (b) Verdicts compare REFINED counts: raw 1v2 and raw 3v4
    # soften to KILL (the crude DIE-gate would refuse both), raw
    # 1v3 stays DIE, superiority stays SAFE, empty stays SAFE.
    assert IP.classify_counts(1, 2) == IP.KILL
    assert IP.classify_counts(3, 4) == IP.KILL
    assert IP.classify_counts(2, 2) == IP.KILL
    assert IP.classify_counts(1, 3) == IP.DIE
    assert IP.classify_counts(0, 3) == IP.DIE
    assert IP.classify_counts(5, 1) == IP.SAFE
    assert IP.classify_counts(1, 0) == IP.SAFE


def test_rate_step_reads_both_fields() -> None:
    # The step verdict is the refined comparison at the tile: the
    # stacked triple DIEs a lone ant, KILLs a backed one.
    own, foe = IP.influence_fields([(5, 5)], [(5, 7), (5, 8), (5, 9)], ROWS, COLS, 3)
    assert IP.rate_step(own, foe, (5, 6)) == IP.DIE
    own2, _ = IP.influence_fields(
        [(5, 5), (5, 4), (4, 5)], [(5, 7), (5, 8), (5, 9)], ROWS, COLS, 3
    )
    assert IP.rate_step(own2, foe, (5, 6)) == IP.KILL


def test_kill_square_taken_only_on_contested_hill_turn() -> None:
    # (c) One foe in reach, lone hunter: raw 1 v 1 refines to 1 v
    # 1, so the east step is KILL. With no hill remembered the
    # hunter refuses it (falls through to explore north); pushing
    # a remembered hill breaks the deadlock and steps east.
    own, foe = IP.influence_fields(_KILL_MINE, _KILL_FOES, ROWS, COLS, 3)
    assert foe[5][6] == 1
    assert IP.rate_step(own, foe, (5, 6)) == IP.KILL
    quiet, _ = run_turn(_KILL_MINE, _KILL_FOES)
    assert dict(quiet)[(5, 5)] == "n"
    pushed, _ = run_turn(_KILL_MINE, _KILL_FOES, enemy_hills=[(15, 15)])
    assert dict(pushed)[(5, 5)] == "e"
    assert pushed != quiet


def test_kill_square_taken_when_in_contact_without_safe_move() -> None:
    # (c) Second deadlock: the hunter stands in contact of (5, 7)
    # and every neighbor refines to KILL, so with no hill at all
    # the east KILL still issues instead of freezing in place.
    own, foe = IP.influence_fields(CONTACT_MINE, CONTACT_FOES, ROWS, COLS, 3)
    assert IP.rate_step(own, foe, (5, 6)) == IP.KILL
    orders, _ = run_turn(CONTACT_MINE, CONTACT_FOES)
    assert dict(orders)[(5, 5)] == "e"


def test_kill_square_refused_when_safe_move_exists() -> None:
    # (c) Same contact, but backed friends make the north escape
    # SAFE, so the east KILL is refused and the hunter steps out.
    own, foe = IP.influence_fields(CONTACT_SAFE_MINE, CONTACT_FOES, ROWS, COLS, 3)
    assert IP.rate_step(own, foe, (5, 6)) == IP.KILL
    assert IP.rate_step(own, foe, (4, 5)) == IP.SAFE
    orders, _ = run_turn(CONTACT_SAFE_MINE, CONTACT_FOES)
    assert dict(orders)[(5, 5)] == "n"


def test_refined_kill_taken_where_crude_die_gate_refuses() -> None:
    # The crude DIE-gate-only version (raw 2 > ours 1, no KILL
    # allowance) refused this step; the faithful refinement (raw 2
    # -> 1 v 1 KILL) plus the hill deadlock takes it east. The near
    # foe sits in attack range, so the old majority filter refuses
    # east too and the hill-less turn falls through to explore.
    foes = [(5, 8), (2, 6)]
    mine = [(5, 5), (5, 1), (5, 2), (6, 1)]
    _, raw_foe = IP.influence_fields(mine, foes, ROWS, COLS, 3)
    assert raw_foe[5][6] == 2
    assert IP.classify_counts(1, raw_foe[5][6]) == IP.KILL
    pushed, _ = run_turn(mine, foes, enemy_hills=[(15, 15)])
    assert dict(pushed)[(5, 5)] == "e"
    quiet, _ = run_turn(mine, foes)
    assert dict(quiet)[(5, 5)] != "e"
    assert pushed != quiet


def test_die_square_refused_where_majority_filter_accepts() -> None:
    # (d) Three lurkers sit at manhattan 3 of (5, 6) but outside
    # attack range, so the old majority filter sees zero foes and
    # accepts east -- while refined influence (3 -> 2 beats ours
    # 1) calls DIE and the hunter never steps east.
    assert old_majority_accepts((5, 6), (5, 5), _DIE_MINE) is True
    own, foe = IP.influence_fields(_DIE_MINE, _DIE_FOES, ROWS, COLS, 3)
    assert foe[5][6] == 3
    assert IP.rate_step(own, foe, (5, 6)) == IP.DIE
    orders, _ = run_turn(_DIE_MINE, _DIE_FOES)
    assert dict(orders).get((5, 5)) != "e"
    # Even pushing a hill cannot spend a DIE: deadlock-KILL never
    # covers losing fights.
    pushed, _ = run_turn(_DIE_MINE, _DIE_FOES, enemy_hills=[(15, 15)])
    assert dict(pushed).get((5, 5)) != "e"


def test_safe_squares_advance_as_champion() -> None:
    # Lone foe far off: the destination refines to SAFE (0 < 1),
    # so the packed hunter still advances east exactly as the old
    # filter orders.
    mine = [(5, 5), (5, 3), (5, 4), (6, 5)]
    own, foe = IP.influence_fields(mine, [(5, 10)], ROWS, COLS, 3)
    assert IP.rate_step(own, foe, (5, 6)) == IP.SAFE
    orders, _ = run_turn(mine, [(5, 10)])
    assert dict(orders)[(5, 5)] == "e"


def test_influence_fields_cost_under_5ms_on_crowded_board() -> None:
    # (e) Both fields -- 40 ants a side stamping diamonds on a
    # 20x20 board in one pass -- cost far under 5ms per turn.
    ours = [((i * 7 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(40)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(40)]
    reach = IP.threat_reach(5)
    reps = 20
    start = time.perf_counter()
    for _ in range(reps):
        own, foe = IP.influence_fields(ours, foes, ROWS, COLS, reach)
    elapsed = (time.perf_counter() - start) / reps
    assert elapsed < 0.005
    assert foe[foes[0][0]][foes[0][1]] >= 1
    assert own[ours[0][0]][ours[0][1]] >= 1


def test_full_turn_costs_under_1s_on_crowded_board() -> None:
    # (e) A full crowded turn -- 30 ants a side plus food and a
    # contested hill -- finishes far inside one second.
    ours = [((i * 7 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(30)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [((i * 3 + 9) % ROWS, (i * 17 + 4) % COLS) for i in range(10)]
    start = time.perf_counter()
    orders, _ = run_turn(ours, foes, foods=foods, enemy_hills=[(10, 10)])
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert isinstance(orders, list)


def test_entry_is_self_contained() -> None:
    # The entry carries its own combat core: stdlib plus ants.py
    # only, never the shared combat.py helpers.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Influence.py")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert hasattr(IP, "Influence")
    assert hasattr(IP, "influence_fields")
    assert hasattr(IP, "refine")
    assert hasattr(IP, "classify_counts")
