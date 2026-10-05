#!/usr/bin/env python
"""Safe-alternative gate tests (Influence14 entry).

Self-contained: FakeAnts plus the Influence10 and Influence14 entries
only, never the shared combat.py helpers. Influence14 keeps the whole
Influence10 tree and changes exactly one mechanism: in the seek branch,
a PRICED (backed) KILL outside deadlocks and hill pushes advances only
as a LAST RESORT -- when no SAFE step exists. When a SAFE advance is
available the ant refuses the trade and falls through to
muster/reinforce/explore instead. Backup counting, verdicts,
refinement, veto, economy, guard, muster, reinforce, explore, and
walk-off are unchanged (no backup-count variants).

Consequences pinned here:

- the safe-alternative discriminator: hunter H approaches foe F, the
  east step reads mid-turn KILL with two mates in backup range, but a
  SAFE sidestep north exists -- base prices the trade and marches
  east while Influence14 refuses and explores north;
- the last-resort mirror: the same backed KILL with every neighbor
  reading KILL (north blocked by water, lurkers covering south and
  west) and idle mates far from every foe -- both bots march east,
  byte-identical;
- the unbacked mirror: the same lone hunter reads the same KILL with
  no backup -- both bots refuse and explore north, byte-identical;
- the backed-DIE hold: two foes make the step DIE despite backup --
  both bots refuse, byte-identical;
- quiet boards order byte-identical to base (SAFE march, contact
  trade, food plus hill, hill-push KILL march, one-backup shortfall);
- the full turn stays under 1s crowded;
- entry self-containment.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Influence10 as Base  # noqa: E402
import Influence14 as New  # noqa: E402

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
    """Same fresh turn through base and Influence14; returns both orders."""
    fake_base = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    Base.Influence10().do_turn(fake_base)
    fake_new = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    New.Influence14().do_turn(fake_new)
    return fake_base.orders, fake_new.orders


def _manhattan(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


# Shared geometry. H=(10,12) hunts F=(10,16); the east step
# D=(10,13) sits 3 from F (their diamond edge) and 1 from H (own
# diamond), so mid-turn reads ours 1 vs theirs 1 -> KILL. H is 4
# from F: out of attack range (attackradius2 5, squared distance
# 16), so no contact-deadlock; no hills are remembered, so no
# hill push either -- only pricing can take the step.
H = (10, 12)
D = (10, 13)
NORTH = (9, 12)
F = (10, 16)
F2 = (10, 15)

# Discriminator board: mates B1=(7,12) and B2=(7,11) sit 4 and 5
# from D (in backup range, outside the reach-3 diamond, so the
# verdict stays KILL) while covering the north sidestep (each
# within 3 of NORTH), which reads ours 3 vs theirs 0 -> SAFE.
B1 = (7, 12)
B2 = (7, 11)
BACKED_SAFE_MINE = [H, B1, B2]

# Last-resort board: north is water, lurkers FS=(14,12) and
# FW=(10,8) cover south and west 1v1 (KILL, never SAFE), and idle
# mates M1=(4,13), M2=(3,13) sit 6 and 7 from D (priced) but 9+
# from every foe (no hunt of their own) and outside every
# reach-3 diamond (no verdict flipped).
M1 = (4, 13)
M2 = (3, 13)
FS = (14, 12)
FW = (10, 8)
LAST_RESORT_MINE = [H, M1, M2]
LAST_RESORT_FOES = [F, FS, FW]
LAST_RESORT_WATER = {NORTH}


def test_pricing_preconditions_and_verdicts() -> None:
    # (a) Units: both boards price the east step (2 backups), the
    # lone hunter prices nothing, and the verdicts read as designed
    # (east KILL; discriminator north SAFE; last-resort neighbors
    # never SAFE).
    assert _manhattan(B1, D) == 4
    assert _manhattan(B2, D) == 5
    assert _manhattan(H, F) == 4
    assert _manhattan(M1, D) == 6
    assert _manhattan(M2, D) == 7
    assert New.backup_count(D, BACKED_SAFE_MINE, H, _manhattan) == 2
    assert New.backup_count(D, LAST_RESORT_MINE, H, _manhattan) == 2
    assert New.backup_count(D, [H], H, _manhattan) == 0
    live, foe = New.influence_fields(BACKED_SAFE_MINE, [F], ROWS, COLS, 3)
    assert New.rate_step(live, foe, D) == New.KILL
    assert New.rate_step(live, foe, NORTH) == New.SAFE
    live2, foe2 = New.influence_fields(
        LAST_RESORT_MINE, LAST_RESORT_FOES, ROWS, COLS, 3
    )
    assert New.rate_step(live2, foe2, D) == New.KILL
    for nbr in ((11, 12), (10, 11)):
        assert New.rate_step(live2, foe2, nbr) == New.KILL


def test_backed_kill_with_safe_sidesteps_to_safety() -> None:
    # (b) Safe-play discriminator: backed KILL east with SAFE north
    # available. Base prices the trade and marches east;
    # Influence14 refuses and explores north (all squares unvisited,
    # n first, SAFE and champion-safe).
    base_orders, new_orders = run_both(BACKED_SAFE_MINE, [F])
    assert dict(base_orders)[H] == "e"
    assert dict(new_orders)[H] == "n"
    assert new_orders != base_orders


def test_backed_kill_without_safe_move_marches_like_base() -> None:
    # (c) Last-resort mirror: the same backed KILL with no SAFE
    # neighbor (water north, lurker-covered south/west read KILL) --
    # pricing is the only safe-ish play, so both bots march east,
    # mates idle-explore identically, orders byte-identical.
    base_orders, new_orders = run_both(
        LAST_RESORT_MINE, LAST_RESORT_FOES, water=LAST_RESORT_WATER
    )
    assert dict(base_orders)[H] == "e"
    assert new_orders == base_orders
    assert dict(new_orders)[H] == "e"


def test_unbacked_kill_refuses_like_base() -> None:
    # (d) Lone-hunter mirror: the same east KILL with no backup --
    # pricing never engages (with or without the gate), both bots
    # refuse and explore north.
    live, foe = New.influence_fields([H], [F], ROWS, COLS, 3)
    assert New.rate_step(live, foe, D) == New.KILL
    base_orders, new_orders = run_both([H], [F])
    assert new_orders == base_orders
    assert dict(new_orders)[H] == "n"


def test_backed_die_still_refuses() -> None:
    # (e) Losing-fight hold: a second foe makes D DIE (theirs 2 vs
    # ours 1) despite full backup -- neither pricing nor the gate
    # buys it, so both bots refuse and explore north.
    live, foe = New.influence_fields(BACKED_SAFE_MINE, [F, F2], ROWS, COLS, 3)
    assert New.rate_step(live, foe, D) == New.DIE
    base_orders, new_orders = run_both(BACKED_SAFE_MINE, [F, F2])
    assert new_orders == base_orders
    assert dict(new_orders)[H] == "n"


def test_quiet_boards_byte_identical_to_base() -> None:
    # (f) Nothing gated on quiet boards: lone-hunter SAFE march, 1v1
    # contact trade, food plus hill in play, hill-push KILL march
    # (hill_push short-circuits before pricing), the last-resort
    # board, and the one-backup shortfall -- every order matches
    # base exactly.
    sparse: list[
        tuple[
            list[Loc],
            list[Loc],
            list[Loc] | None,
            set[Loc] | None,
            list[Loc] | None,
        ]
    ] = [
        ([(5, 5)], [(5, 15)], None, None, None),
        ([(5, 5)], [(5, 7)], None, None, None),
        ([(5, 5)], [(5, 7)], [(0, 0)], None, [(15, 15)]),
        ([(5, 5)], [(5, 9)], None, None, [(5, 12)]),
        (LAST_RESORT_MINE, LAST_RESORT_FOES, None, LAST_RESORT_WATER, None),
        ([H, B1], [F], None, None, None),
        (BACKED_SAFE_MINE, [F, F2], None, None, None),
    ]
    for mine, foes, foods, water, hills in sparse:
        base_orders, new_orders = run_both(
            mine, foes, foods=foods, water=water, enemy_hills=hills
        )
        assert new_orders == base_orders


def test_full_turn_costs_under_1s_on_crowded_board() -> None:
    # (g) A full crowded turn -- 30 ants a side plus food and two
    # contested hills -- finishes far inside one second; the gate
    # reuses the deadlock helper (one neighbor scan per priced KILL
    # only).
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
    # (h) The entry carries its own combat core: stdlib plus
    # ants.py only, never the shared combat.py helpers.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Influence14.py")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert hasattr(New, "Influence14")
    assert hasattr(New, "influence_fields")
    assert hasattr(New, "move_own_stamp")
    assert hasattr(New, "classify_counts")
    assert hasattr(New, "project_final_field")
    assert hasattr(New, "backup_count")
