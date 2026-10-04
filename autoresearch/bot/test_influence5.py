#!/usr/bin/env python
"""Combat-only live stamps tests (Influence5 entry).

Self-contained: FakeAnts plus the Influence3 (snapshot), Influence4
(live-stamp-everything), and Influence5 entries only, never the
shared combat.py helpers. Influence5 keeps the whole Influence4 tree
and changes exactly one mechanism: only committed combat advances
(seek-branch hunter steps, muster, reinforce -- the try_free path)
re-stamp the own influence field. Non-combat moves (food claims,
guard screening, walk-off -- the try_step path; explore never
stamped) issue without re-stamping, so later ants in the same turn
keep reading the snapshot support a departing forager vacates.

Consequences pinned here:

- the converge board still converges: the leader's seek advance
  re-stamps, lifting the follower's step from KILL to SAFE, so
  Influence5 marches the pair east exactly like Influence4 while
  the snapshot base wanders the follower north;
- the abandon board stops abandoning: the forager's west step no
  longer withdraws its diamond, so the hunter still reads the
  snapshot SAFE and marches east exactly like the snapshot base,
  while Influence4 refuses east;
- single-ant turns order byte-identical to both base and
  Influence4 (nothing precedes the only verdict, and a lone food
  step stamps nothing either way that a later verdict could read);
- the full turn stays under 1s crowded.

Pins (a) the converge board where Influence5 matches Influence4
against the snapshot base, (b) the abandon board where Influence5
matches the snapshot base against Influence4, (c) single-ant
byte-identity against both, (d) the full turn under 1s crowded,
and (e) entry self-containment.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Influence3 as Snap  # noqa: E402
import Influence4 as Live  # noqa: E402
import Influence5 as New  # noqa: E402

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


def run_all(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], list[tuple[Loc, str]], list[tuple[Loc, str]]]:
    """Same fresh turn through snapshot, live-stamp, and Influence5."""
    fake_snap = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    Snap.Influence3().do_turn(fake_snap)
    fake_live = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    Live.Influence4().do_turn(fake_live)
    fake_new = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    New.Influence5().do_turn(fake_new)
    return fake_snap.orders, fake_live.orders, fake_new.orders


def _manhattan(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


# (a) Converge board. A1=(10,9) and A2=(10,12) hunt E=(10,16).
# A2's east step D2=(10,13) reads static ours 1 (only A2: A1 sits
# at manhattan 4, outside the reach-3 diamond) vs theirs 1 (E at
# manhattan 3) -> KILL, refused with no contact and no hill push.
# A1 marches east first (SAFE: 2v0 at (10,10)); the live stamp puts
# A1 at manhattan 3 of D2, so D2 reads ours 2 vs theirs 1 -> thirds
# 5 > 3 -> SAFE, and the follower joins instead of wandering north.
# A1's advance is a seek-branch combat step, so Influence5 keeps
# the re-stamp and converges exactly like Influence4.
A1 = (10, 9)
A2 = (10, 12)
FOE = (10, 16)
D2 = (10, 13)
CONVERGE_MINE = [A1, A2]
CONVERGE_FOES = [FOE]

# (b) Abandon board. A1=(10,10) eats at (10,5) and steps west;
# A2=(10,12) hunts E=(10,16). A2's east step D2=(10,13) reads
# static ours 2 (A1 at manhattan 3, A2 at 1) vs theirs 1 -> SAFE.
# Influence4's food step withdraws A1's diamond (manhattan 4 after
# the west step): ours 1 vs theirs 1 -> KILL, refused with no
# contact and no hill push. Influence5 does not re-stamp food
# steps, so the hunter still reads the snapshot SAFE and marches
# east exactly like the snapshot base.
AB_A1 = (10, 10)
AB_A2 = (10, 12)
ABANDON_MINE = [AB_A1, AB_A2]
ABANDON_FOES = [FOE]
ABANDON_FOODS = [(10, 5)]


def test_converge_board_matches_live_stamp_against_snapshot() -> None:
    # (a) Combat advances still re-stamp: A1 marches east in all
    # three bots, then the snapshot base refuses the static KILL
    # and wanders north while Influence4 and Influence5 read the
    # live SAFE and converge east behind the leader.
    assert _manhattan(A1, D2) == 4
    assert _manhattan((10, 10), D2) == REACH
    snap_orders, live_orders, new_orders = run_all(CONVERGE_MINE, CONVERGE_FOES)
    assert dict(new_orders)[A1] == "e"
    assert dict(live_orders)[A1] == "e"
    assert dict(snap_orders)[A1] == "e"
    assert dict(new_orders)[A2] == "e"
    assert dict(live_orders)[A2] == "e"
    assert dict(snap_orders).get(A2) != "e"
    assert new_orders == live_orders
    assert new_orders != snap_orders


def test_abandoned_step_marches_where_live_stamp_refuses() -> None:
    # (b) The discriminator: A1 eats west in all three bots, then
    # the snapshot base and Influence5 march east onto the snapshot
    # SAFE square while Influence4 reads the withdrawn KILL and
    # refuses east.
    snap_orders, live_orders, new_orders = run_all(
        ABANDON_MINE, ABANDON_FOES, foods=ABANDON_FOODS
    )
    assert dict(new_orders)[AB_A1] == "w"
    assert dict(live_orders)[AB_A1] == "w"
    assert dict(snap_orders)[AB_A1] == "w"
    assert dict(snap_orders)[AB_A2] == "e"
    assert dict(new_orders)[AB_A2] == "e"
    assert dict(live_orders).get(AB_A2) != "e"
    assert new_orders == snap_orders
    assert new_orders != live_orders


def test_single_ant_turns_byte_identical_to_both() -> None:
    # (c) One ant moves at most once and nothing precedes its
    # verdicts, so snapshot, live, and combat-only fields agree on
    # every tile: lone hunter, 1v1 contact trade, food plus hill
    # in play, and a hill-push KILL march all order exactly alike.
    sparse: list[tuple[list[Loc], list[Loc], list[Loc] | None, list[Loc] | None]] = [
        ([(5, 5)], [(5, 15)], None, None),
        ([(5, 5)], [(5, 7)], None, None),
        ([(5, 5)], [(5, 7)], [(0, 0)], [(15, 15)]),
        ([(5, 5)], [(5, 9)], None, [(5, 12)]),
    ]
    for mine, foes, foods, hills in sparse:
        snap_orders, live_orders, new_orders = run_all(
            mine, foes, foods=foods, enemy_hills=hills
        )
        assert new_orders == snap_orders
        assert new_orders == live_orders


def test_full_turn_costs_under_1s_on_crowded_board() -> None:
    # (d) A full crowded turn -- 30 ants a side plus food and two
    # contested hills -- finishes far inside one second; combat
    # steps re-stamp two small diamonds each and nothing else
    # touches the field.
    ours = [((i * 7 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(30)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [((i * 3 + 9) % ROWS, (i * 17 + 4) % COLS) for i in range(10)]
    start = time.perf_counter()
    snap_orders, live_orders, new_orders = run_all(
        ours, foes, foods=foods, enemy_hills=[(10, 10), (10, 3)]
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert isinstance(new_orders, list)
    assert isinstance(live_orders, list)
    assert isinstance(snap_orders, list)


def test_entry_is_self_contained() -> None:
    # (e) The entry carries its own combat core: stdlib plus ants.py
    # only, never the shared combat.py helpers.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Influence5.py")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert hasattr(New, "Influence5")
    assert hasattr(New, "influence_fields")
    assert hasattr(New, "move_own_stamp")
    assert hasattr(New, "classify_counts")
