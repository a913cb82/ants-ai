#!/usr/bin/env python
"""Michigan two-stage combat tests (self-contained: TwoStage only).

Faithful to the RESEARCH.md row "Michigan battle resolution"
(claimed top 25): STAGE 1 classifies each nearby enemy as
safe-target or threat from current positions only (no enemy moves
assumed); STAGE 2 models enemies as stay-or-advance for threatened
ants (two options each, no deeper model); among equal-scoring
moves the one committing fewer ants wins (the no-1v1 gate emerges
here); a recursive per-ant search scores +1 moved / -1 new enemy
drawn in, exits early when the score gap exceeds a threshold, and
caps the recursion so boards past 20 ants a side stay stable
where the original crashed.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import TwoStage as TS  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], TS.TwoStage]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = TS.TwoStage()
    bot.do_turn(fake)
    return fake.orders, bot


def test_stage1_classifies_safe_vs_threat() -> None:
    # Hand-verified on attackradius2 5 (sq <= 5 is contact).
    # Foe (5, 7): ours in range are (5, 5) [sq 4] and (5, 6)
    # [sq 1] = 2; theirs in range is itself only [(10, 10) is
    # sq 34 away] = 1. 2 > 1, so safe-target -- even though the
    # foe stands adjacent: static analysis assumes no moves.
    # Foe (10, 10): ours in range 0 [(5, 5) sq 50, (5, 6) sq 41];
    # theirs 1. 0 > 1 is false, so threat.
    ours = [(5, 5), (5, 6)]
    foes = [(5, 7), (10, 10)]
    labels = TS.classify_static(ours, foes, _sq, R2)
    assert labels == {(5, 7): TS.SAFE_TARGET, (10, 10): TS.THREAT}


def test_stage1_uses_current_positions_only() -> None:
    # Foe (5, 8) could step to (5, 7) and contact both hunters,
    # but static analysis assumes no enemy moves: ours in range
    # of (5, 8) is (5, 6) [sq 4] only = 1, theirs is itself = 1,
    # so 1 > 1 is false and the label stays threat. The label
    # reads today's board, never tomorrow's.
    ours = [(5, 5), (5, 6)]
    labels = TS.classify_static(ours, [(5, 8)], _sq, R2)
    assert labels == {(5, 8): TS.THREAT}
    assert TS.threat_reach(R2) == 3


def test_stay_advance_flips_decision_vs_static() -> None:
    # Lone ant (5, 5), lurker (5, 9). Static analysis sees no foe
    # in range of the eastern step (sq 9 > 5), scores it +1 moved,
    # and advances east. The stay-or-advance model sees the foe
    # step to (5, 8) -- sq 4 from (5, 6) -- scores the step -1,
    # and holds. Same ant, same foe: the coarse enemy model flips
    # the decision from engage to hold.
    ant: Loc = (5, 5)
    east: Loc = (5, 6)
    options = [east, ant]
    static = {east: TS.static_foes(east, [(5, 9)], _sq, R2), ant: 0}
    assert static[east] == 0
    static_pick = TS.pick_best(ant, options, static, [], _sq, R2)
    assert static_pick == east
    modeled = {
        east: TS.modeled_foes(east, [(5, 9)], _sq, R2, ROWS, COLS),
        ant: TS.modeled_foes(ant, [(5, 9)], _sq, R2, ROWS, COLS),
    }
    assert modeled[east] == 1
    assert modeled[ant] == 0
    stage2_pick = TS.pick_best(ant, options, modeled, [], _sq, R2)
    assert stage2_pick == ant
    assert stage2_pick != static_pick


def test_fewest_ants_breaks_ties() -> None:
    # Both steps face exactly one foe (value -1 each), so combat
    # score ties. East commits only the mover (friend (5, 3) is
    # sq 9 from (5, 6), out of range): 1 ant. West draws the
    # friend in (sq 1 from (5, 4)): 2 ants. Fewest-ants prefers
    # east -- 1 ant beats 2 on a tied move.
    ant: Loc = (5, 5)
    east: Loc = (5, 6)
    west: Loc = (5, 4)
    foes = {east: 1, west: 1}
    assert TS.move_value(east, ant, 1) == TS.move_value(west, ant, 1)
    assert TS.commit_count(east, ant, [(5, 3)], _sq, R2) == 1
    assert TS.commit_count(west, ant, [(5, 3)], _sq, R2) == 2
    assert TS.pick_best(ant, [east, west], foes, [(5, 3)], _sq, R2) == east


def test_lone_duel_holds_as_emergent_no_1v1_gate() -> None:
    # Friendless ant (5, 5) against lone foe (5, 7). Engaging east
    # scores 0 moved-and-drawn (1 - 1) and holding scores -1, yet
    # both read -1 under the stay-or-advance worst case (the foe
    # answers the hold by stepping to (5, 6), sq 1 from home).
    # Equal scores, and the hold commits 0 ants against the
    # engage's 1 -- so the ant holds. No explicit 1v1 rule exists;
    # the gate emerges from the fewest-ants preference.
    ant: Loc = (5, 5)
    east: Loc = (5, 6)
    foes = {
        east: TS.modeled_foes(east, [(5, 7)], _sq, R2, ROWS, COLS),
        ant: TS.modeled_foes(ant, [(5, 7)], _sq, R2, ROWS, COLS),
    }
    assert foes == {east: 1, ant: 1}
    assert TS.move_value(east, ant, 1) == TS.move_value(ant, ant, 1) == -1
    assert TS.commit_count(east, ant, [], _sq, R2) == 1
    assert TS.commit_count(ant, ant, [], _sq, R2) == 0
    assert TS.pick_best(ant, [east, ant], foes, [], _sq, R2) == ant


def test_early_exit_fires_on_trailing_branch() -> None:
    # Six ants, each with a good square (value +1, listed first)
    # and a bad one (value -2). Depth-first search finds the
    # all-good plan (total 6) first; every branch that starts
    # with a bad square then trails by more than EARLY_EXIT_GAP
    # (ceiling 3 vs leader 6) and prunes instead of recursing.
    # The instrumented counter proves the exit fired.
    assert TS.EARLY_EXIT_GAP == 2
    order = list(range(6))
    candidates: dict[int, list[Loc]] = {}
    values: dict[tuple[int, Loc], int] = {}
    committed: dict[tuple[int, Loc], int] = {}
    for ai in order:
        good: Loc = (0, ai)
        bad: Loc = (1, ai)
        candidates[ai] = [good, bad]
        values[(ai, good)] = 1
        values[(ai, bad)] = -2
        committed[(ai, good)] = 0
        committed[(ai, bad)] = 1
    plan, stats = TS.search_moves(order, candidates, values, committed)
    assert stats["early_exits"] > 0
    assert stats["nodes"] < 2**6
    assert plan == {ai: (0, ai) for ai in order}


def test_25v25_search_stable_under_1s() -> None:
    # Where the original crashed past 20 ants a side, the capped
    # recursion returns a full 25-ant plan in milliseconds: the
    # first MAX_COMBAT_ANTS ants search jointly under a node
    # budget and the rest fall back to greedy singles.
    assert TS.MAX_COMBAT_ANTS == 20
    ours = [(i % ROWS, (i * 7) % COLS) for i in range(25)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(25)]
    order = list(range(25))
    candidates = {
        ai: [((ant[0] + 1) % ROWS, ant[1]), ant] for ai, ant in enumerate(ours)
    }
    values = {}
    committed = {}
    for ai, ant in enumerate(ours):
        for dest in candidates[ai]:
            values[(ai, dest)] = TS.move_value(
                dest, ant, TS.modeled_foes(dest, foes, _sq, R2, ROWS, COLS)
            )
            committed[(ai, dest)] = TS.commit_count(dest, ant, ours, _sq, R2)
    start = time.perf_counter()
    plan, stats = TS.search_moves(order, candidates, values, committed)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(plan) == 25
    assert stats["capped"] == 1
    assert stats["nodes"] <= TS.SEARCH_BUDGET + TS.MAX_COMBAT_ANTS


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


def test_safe_target_advances() -> None:
    # Packed hunters (5, 5) + (5, 4) + (4, 6) + (5, 3) face one
    # foe (5, 7): stage 1 counts 2 of ours in range against 1 of
    # theirs, labels it safe-target, no threat exists, so the
    # unthreatened hunter steps east onto (5, 6) exactly as the
    # champion's approach would.
    mine = [(5, 5), (5, 4), (4, 6), (5, 3)]
    orders, _ = run_turn(mine, [(5, 7)])
    assert orders[0] == ((5, 5), "e")


def test_threatened_hold_falls_back_to_explore() -> None:
    # Lone ant (5, 5) against lurker (5, 9): stage 1 labels the
    # foe a threat (0 of ours in range vs 1), stage 2 holds
    # against the stay-or-advance model, and the ant explores
    # north -- never east into the modeled contact.
    orders, _ = run_turn([(5, 5)], [(5, 9)])
    assert orders == [((5, 5), "n")]
    assert ((5, 5), "e") not in orders


def test_safe_target_pincer_advances() -> None:
    # Two unthreatened ants flank one safe-target foe (2 of ours
    # in range vs 1 of theirs): both keep their desired squares
    # and pinch east plus west onto (5, 6) and (5, 8) together.
    orders, _ = run_turn([(5, 5), (5, 9)], [(5, 7)])
    assert orders == [((5, 5), "e"), ((5, 9), "w")]


def test_threatened_pair_holds_jointly() -> None:
    # Two threatened ants against three threats: every threat
    # label holds (2 of ours vs 3 of theirs), the stay-or-advance
    # worst case prices 3 foes on each desired square, and the
    # joint search holds both ants -- neither steps east into
    # the modeled contact, and neither donates alone.
    mine = [(5, 5), (6, 5)]
    foes = [(5, 7), (6, 7), (5, 8)]
    labels = TS.classify_static(mine, foes, _sq, R2)
    assert set(labels.values()) == {TS.THREAT}
    orders, _ = run_turn(mine, foes)
    assert ((5, 5), "e") not in orders
    assert ((6, 5), "e") not in orders


def test_joint_plan_is_deterministic() -> None:
    # Same threatened board twice: identical orders, no coin
    # flips anywhere in the two stages or the search.
    mine = [(5, 5), (6, 5)]
    foes = [(5, 7), (6, 7), (5, 8)]
    first, _ = run_turn(mine, foes)
    second, _ = run_turn(mine, foes)
    assert first == second


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
