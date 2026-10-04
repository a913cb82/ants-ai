#!/usr/bin/env python
"""Softer-refinement tuning tests (Influence3 entry).

Self-contained: FakeAnts plus the Influence2 (base) and Influence3
entries only, never the shared combat.py helpers. Influence3 keeps
the whole base tree and changes exactly one rule: extra attackers
beyond the first count at 2/3 weight instead of 1/2, applied to BOTH
sides symmetrically. Compared exactly in thirds: scaled(k) = 0 when
k == 0, else 2*k + 1, so refine(k) = scaled(k)/3 = 1 + (k-1)*2/3.

Consequences pinned here (hand-computed in thirds):

- base DIE stays DIE and base SAFE stays SAFE (both orders are
  monotone, so strict majorities survive the reweighting);
- base-KILL ties with unequal raw counts split on the raw majority:
  ours ahead (2v1) refines to SAFE (5 > 3 in thirds), theirs ahead
  (1v2) refines to DIE (3 < 5 in thirds). Equal raw counts stay KILL.

Pins (a) our stacked-attackers board flips base-KILL to refined
SAFE (hand-computed in thirds) so the winnable fight marches with
no deadlock and no hill push, while base refuses the same step,
(b) single-attacker boards order byte-identical to base, (c) the
reweighting applies to both sides symmetrically (exhaustive small
table plus their-stacked board), and (d) the full turn under 1s
crowded.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Influence2 as Base  # noqa: E402
import Influence3 as New  # noqa: E402

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


def run_both(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], list[tuple[Loc, str]]]:
    """Same fresh turn through base and Influence3; returns both orders."""
    fake_base = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    Base.Influence2().do_turn(fake_base)
    fake_new = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    New.Influence3().do_turn(fake_new)
    return fake_base.orders, fake_new.orders


def _sq(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


def _in_contact(ant: Loc, foes: list[Loc]) -> bool:
    return any(_sq(ant, e) <= 5 for e in foes)


# (a) Our-stacked board. A=(10,10) hunts E=(10,14) with friend
# F=(10,13) stamping the east step D=(10,11) a second time. D reads
# raw ours 2 (A at manhattan 1, F at manhattan 2) vs theirs 1 (E at
# manhattan 3). Base refines 1 vs 1 -> KILL; thirds refine 5 vs 3
# -> SAFE. A stands outside every attack range (sq 16 > 5), no hill
# is remembered, so no deadlock and no hill push: base refuses the
# step, Influence3 marches it with no gating at all.
A = (10, 10)
FRIEND = (10, 13)
LONE_FOE = (10, 14)
STACKED_MINE = [A, FRIEND]
STACKED_FOES = [LONE_FOE]
STEP_EAST = (10, 11)

# Their-stacked mirror. A=(10,10) faces E1=(10,12) and E2=(10,14);
# D=(10,11) reads raw ours 1 (A at manhattan 1) vs theirs 2 (E1 at
# manhattan 1, E2 at manhattan 3). Base refines 1 vs 1 -> KILL;
# thirds refine 3 vs 5 -> DIE. Same symmetric 2/3 weight, opposite
# side: the extra THEIR attacker now counts, so the step refuses.
FOE1 = (10, 12)
FOE2 = (10, 14)
MIRROR_FOES = [FOE1, FOE2]


def test_our_extra_attacker_flips_kill_to_safe_in_thirds() -> None:
    # (a) Unit level, hand-computed in thirds: ours raw 2 scales to
    # 2*2+1 = 5, theirs raw 1 scales to 2*1+1 = 3, 5 > 3 -> SAFE;
    # base floors to 1 vs 1 -> KILL.
    own, foe = New.influence_fields(STACKED_MINE, STACKED_FOES, ROWS, COLS, 3)
    assert own[STEP_EAST[0]][STEP_EAST[1]] == 2
    assert foe[STEP_EAST[0]][STEP_EAST[1]] == 1
    assert New.refine_scaled(2) == 5
    assert New.refine_scaled(1) == 3
    assert New.rate_step(own, foe, STEP_EAST) == New.SAFE
    base_own, base_foe = Base.influence_fields(
        STACKED_MINE, STACKED_FOES, ROWS, COLS, 3
    )
    assert Base.rate_step(base_own, base_foe, STEP_EAST) == Base.KILL


def test_winnable_fight_marches_without_deadlock_or_hill_push() -> None:
    # (a) Behavioral: no contact (no deadlock), no remembered hill
    # (no hill push) -- Influence3 still steps east onto the refined
    # SAFE square while base refuses east and explores instead.
    assert not _in_contact(A, STACKED_FOES)
    base_orders, new_orders = run_both(STACKED_MINE, STACKED_FOES)
    assert dict(new_orders)[A] == "e"
    assert dict(base_orders).get(A) != "e"
    assert new_orders != base_orders


def test_single_attacker_boards_byte_identical_to_base() -> None:
    # (b) Raw counts never exceed 1 on either side, so 1/2 and 2/3
    # weights agree everywhere: whole turns match base exactly.
    # Lone hunter vs far foe (SAFE explore), 1v1 contact (deadlock
    # KILL trade), and 1v1 even trade with food and a hill in play.
    sparse: list[tuple[list[Loc], list[Loc], list[Loc] | None, list[Loc] | None]] = [
        ([(5, 5)], [(5, 15)], None, None),
        ([(5, 5)], [(5, 7)], None, None),
        ([(5, 5)], [(5, 7)], [(0, 0)], [(15, 15)]),
        ([(5, 5), (15, 15)], [(5, 7), (15, 13)], [(0, 0)], None),
    ]
    for mine, foes, foods, hills in sparse:
        base_orders, new_orders = run_both(mine, foes, foods=foods, enemy_hills=hills)
        assert new_orders == base_orders
    # The contact trade itself is KILL under both weights (1 vs 1
    # refines to 3 vs 3 in thirds) and both bots spend it identically.
    own, foe = New.influence_fields([(5, 5)], [(5, 7)], ROWS, COLS, 3)
    assert New.rate_step(own, foe, (5, 6)) == New.KILL
    base_orders, new_orders = run_both([(5, 5)], [(5, 7)])
    assert dict(new_orders)[(5, 5)] == "e"
    assert new_orders == base_orders


def test_reweighting_applies_to_both_sides_symmetrically() -> None:
    # (c) Their extra attacker mirrors ours: raw 1 vs 2 scales to
    # 3 vs 5 in thirds -> DIE, where base floors to 1 vs 1 -> KILL.
    own, foe = New.influence_fields([A], MIRROR_FOES, ROWS, COLS, 3)
    assert own[STEP_EAST[0]][STEP_EAST[1]] == 1
    assert foe[STEP_EAST[0]][STEP_EAST[1]] == 2
    assert New.rate_step(own, foe, STEP_EAST) == New.DIE
    base_own, base_foe = Base.influence_fields([A], MIRROR_FOES, ROWS, COLS, 3)
    assert Base.rate_step(base_own, base_foe, STEP_EAST) == Base.KILL
    # Symmetry is exact: swapping the raw counts swaps the verdict.
    assert New.classify_counts(2, 1) == New.SAFE
    assert New.classify_counts(1, 2) == New.DIE
    assert New.classify_counts(1, 1) == New.KILL
    assert New.classify_counts(0, 0) == New.KILL
    assert New.classify_counts(0, 1) == New.DIE
    assert New.classify_counts(1, 0) == New.SAFE


def test_small_count_table_matches_thirds_arithmetic() -> None:
    # (c) Exhaustive: for raw counts 0..6 the verdict equals the
    # thirds comparison (scaled(k) = 0 else 2*k+1), base DIE/SAFE
    # regions survive, and only unequal base-KILL ties split.
    for ours in range(7):
        for theirs in range(7):
            scaled_o = 0 if ours == 0 else 2 * ours + 1
            scaled_t = 0 if theirs == 0 else 2 * theirs + 1
            assert New.refine_scaled(ours) == scaled_o
            want = (
                New.DIE
                if scaled_t > scaled_o
                else New.KILL
                if scaled_t == scaled_o
                else New.SAFE
            )
            assert New.classify_counts(ours, theirs) == want
            base = Base.classify_counts(ours, theirs)
            if base == Base.DIE:
                assert want == New.DIE
            elif base == Base.SAFE:
                assert want == New.SAFE
            else:
                assert base == Base.KILL
                if ours == theirs:
                    assert want == New.KILL
                elif ours > theirs:
                    assert want == New.SAFE
                else:
                    assert want == New.DIE


def test_their_stacked_step_refused_where_base_trades() -> None:
    # (c) Behavioral mirror: in contact with no SAFE square anywhere
    # (every neighbor also reads raw 1v1+), base spends the deadlock
    # KILL east while Influence3 refuses the refined DIE and holds.
    base_orders, new_orders = run_both([A], MIRROR_FOES)
    assert dict(base_orders)[A] == "e"
    assert dict(new_orders).get(A) != "e"
    assert new_orders != base_orders


def test_full_turn_costs_under_1s_on_crowded_board() -> None:
    # (d) A full crowded turn -- 30 ants a side plus food and two
    # contested hills -- finishes far inside one second.
    ours = [((i * 7 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(30)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [((i * 3 + 9) % ROWS, (i * 17 + 4) % COLS) for i in range(10)]
    start = time.perf_counter()
    base_orders, new_orders = run_both(
        ours, foes, foods=foods, enemy_hills=[(10, 10), (10, 3)]
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert isinstance(new_orders, list)
    assert isinstance(base_orders, list)


def test_entry_is_self_contained() -> None:
    # The entry carries its own combat core: stdlib plus ants.py
    # only, never the shared combat.py helpers.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Influence3.py")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert hasattr(New, "Influence3")
    assert hasattr(New, "influence_fields")
    assert hasattr(New, "refine_scaled")
    assert hasattr(New, "classify_counts")
