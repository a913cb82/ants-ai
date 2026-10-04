#!/usr/bin/env python
"""Live-influence convergence tests (Influence4 entry).

Self-contained: FakeAnts plus the Influence3 (base) and Influence4
entries only, never the shared combat.py helpers. Influence4 keeps
the whole base tree and changes exactly one mechanism: the own
influence field follows our issued moves. Every issued order
re-stamps the mover's attack diamond off its old tile and onto its
new tile, so later ants in the same turn read converging (or
abandoned) support instead of the stale snapshot. The foe field
stays static; the thirds refinement and every verdict are unchanged.

Consequences pinned here:

- a second hunter joins a 2v1 it could not see statically: the
  leader's advance lifts its step from KILL to SAFE, so the pair
  converges instead of trickling one refusal at a time;
- a hunter left behind refuses a step the snapshot called SAFE:
  the leader's departure drops its step from SAFE to DIE, so it
  holds instead of marching into a fight its support just left;
- single-ant turns order byte-identical to base (nothing moves
  before the only verdict, so live and static agree everywhere).

Pins (a) the diamond re-stamp arithmetic on hand-computed tiles,
(b) the converge board where Influence4 marches two ants east while
base sends the second ant north, (c) the abandon board where base
marches east into a vacated fight while Influence4 refuses east,
(d) single-ant byte-identity, and (e) the full turn under 1s
crowded.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Influence3 as Base  # noqa: E402
import Influence4 as New  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
REACH = 3


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
    """Same fresh turn through base and Influence4; returns both orders."""
    fake_base = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    Base.Influence3().do_turn(fake_base)
    fake_new = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    New.Influence4().do_turn(fake_new)
    return fake_base.orders, fake_new.orders


def _manhattan(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


# (b) Converge board. A1=(10,9) and A2=(10,12) hunt E=(10,16).
# A2's east step D2=(10,13) reads static ours 1 (only A2: A1 sits
# at manhattan 4, outside the reach-3 diamond) vs theirs 1 (E at
# manhattan 3) -> KILL, refused with no contact and no hill push.
# A1 marches east first (SAFE: 2v0 at (10,10)); the live stamp puts
# A1 at manhattan 3 of D2, so D2 reads ours 2 vs theirs 1 -> thirds
# 5 > 3 -> SAFE, and A2 joins instead of wandering north.
A1 = (10, 9)
A2 = (10, 12)
FOE = (10, 16)
D2 = (10, 13)
CONVERGE_MINE = [A1, A2]
CONVERGE_FOES = [FOE]

# (c) Abandon board. A1=(10,10) eats at (10,5) and steps west;
# A2=(10,12) hunts E=(10,16). A2's east step D2=(10,13) reads
# static ours 2 (A1 at manhattan 3, A2 at 1) vs theirs 1 -> SAFE,
# so base marches east. Live, A1's west step drops it to manhattan
# 4 of D2: ours 1 vs theirs 1 -> KILL, refused with no contact and
# no hill push, so Influence4 holds east and explores instead.
AB_A1 = (10, 10)
AB_A2 = (10, 12)
ABANDON_MINE = [AB_A1, AB_A2]
ABANDON_FOES = [FOE]
ABANDON_FOODS = [(10, 5)]


def test_stamp_moves_exactly_one_diamond() -> None:
    # (a) Hand-computed: reach-3 diamond of (10,9) lifted onto
    # (10,10). (10,13) enters (4 -> 3), (10,6) leaves (3 -> 4),
    # (10,10) stays covered (1 -> 0 distance, still stamped).
    own, _ = New.influence_fields([(10, 9)], [], ROWS, COLS, REACH)
    assert own[D2[0]][D2[1]] == 0
    assert own[10][6] == 1
    assert own[10][10] == 1
    New.move_own_stamp(own, (10, 9), (10, 10), ROWS, COLS, REACH)
    assert own[D2[0]][D2[1]] == 1
    assert own[10][6] == 0
    assert own[10][10] == 1
    # Total stamped tiles are conserved: one diamond off, one on.
    assert sum(sum(row) for row in own) == (1 + 2 * REACH * (REACH + 1))


def test_second_hunter_joins_after_leader_advances() -> None:
    # (b) Unit level on the converge board: the east step reads
    # KILL from the snapshot but SAFE once A1 stands on (10,10).
    own, foe = New.influence_fields(CONVERGE_MINE, CONVERGE_FOES, ROWS, COLS, REACH)
    assert own[D2[0]][D2[1]] == 1
    assert foe[D2[0]][D2[1]] == 1
    assert New.rate_step(own, foe, D2) == New.KILL
    New.move_own_stamp(own, A1, (10, 10), ROWS, COLS, REACH)
    assert own[D2[0]][D2[1]] == 2
    assert New.rate_step(own, foe, D2) == New.SAFE


def test_converge_board_marches_pair_while_base_splits() -> None:
    # (b) Behavioral: A1 marches east in both bots, then base
    # refuses the static KILL and wanders north while Influence4
    # reads the live SAFE and converges east behind its leader.
    assert _manhattan(A1, D2) == 4
    assert _manhattan((10, 10), D2) == REACH
    base_orders, new_orders = run_both(CONVERGE_MINE, CONVERGE_FOES)
    assert dict(new_orders)[A1] == "e"
    assert dict(base_orders)[A1] == "e"
    assert dict(new_orders)[A2] == "e"
    assert dict(base_orders).get(A2) != "e"
    assert new_orders != base_orders


def test_abandoned_step_refused_where_snapshot_marches() -> None:
    # (c) Behavioral mirror: A1 eats west in both bots, then base
    # marches east onto the snapshot SAFE square while Influence4
    # reads the live KILL (support just left, no contact, no hill
    # push) and refuses east.
    base_orders, new_orders = run_both(ABANDON_MINE, ABANDON_FOES, foods=ABANDON_FOODS)
    assert dict(new_orders)[AB_A1] == "w"
    assert dict(base_orders)[AB_A1] == "w"
    assert dict(base_orders)[AB_A2] == "e"
    assert dict(new_orders).get(AB_A2) != "e"
    assert new_orders != base_orders


def test_single_ant_turns_byte_identical_to_base() -> None:
    # (d) One ant moves at most once and nothing precedes its
    # verdicts, so live and static fields agree on every tile:
    # lone hunter, 1v1 contact trade, food plus hill in play, and
    # a Hill-push KILL march all order exactly as base.
    sparse: list[tuple[list[Loc], list[Loc], list[Loc] | None, list[Loc] | None]] = [
        ([(5, 5)], [(5, 15)], None, None),
        ([(5, 5)], [(5, 7)], None, None),
        ([(5, 5)], [(5, 7)], [(0, 0)], [(15, 15)]),
        ([(5, 5)], [(5, 9)], None, [(5, 12)]),
    ]
    for mine, foes, foods, hills in sparse:
        base_orders, new_orders = run_both(mine, foes, foods=foods, enemy_hills=hills)
        assert new_orders == base_orders


def test_full_turn_costs_under_1s_on_crowded_board() -> None:
    # (e) A full crowded turn -- 30 ants a side plus food and two
    # contested hills -- finishes far inside one second; each
    # issued order re-stamps two small diamonds only.
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
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Influence4.py")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert hasattr(New, "Influence4")
    assert hasattr(New, "influence_fields")
    assert hasattr(New, "move_own_stamp")
    assert hasattr(New, "classify_counts")
