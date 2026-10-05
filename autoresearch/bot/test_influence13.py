#!/usr/bin/env python
"""Engaged-backup pricing tests (Influence13 entry).

Self-contained: FakeAnts plus the Influence10 and Influence13 entries
only, never the shared combat.py helpers. Influence13 keeps the whole
Influence10 tree and changes exactly one mechanism: in the seek
branch, a backup mate prices a KILL step (expect a 1-for-1) outside
deadlocks and hill pushes only when it is ENGAGED -- within
BACKUP_RANGE (10) steps of the destination AND within SEEK_RANGE (8)
steps of the hunted foe, so it can actually join the fight on the
follow-up. Mates trailing 7-10 steps behind the hunter (near the
destination, far from the foe) price nothing: they can never convert
the trade, and ceding that ground misprices the take. Engaged pairs
still march, unbacked KILLs still refuse, DIE always refuses, and
every other branch is unchanged.

Consequences pinned here:

- the far-backup discriminator: hunter H approaches foe F, the east
  step reads mid-turn KILL with two mates in backup range of the
  destination but 10+ from the foe -- base prices the trade and
  marches east while Influence13 refuses and walks north via explore
  (the final-field veto still covers it either way);
- the engaged mirror: the same hunter with two mates near both the
  destination and the foe reads the same KILL -- both bots march
  east, byte-identical (real reinforcements keep their price);
- the unbacked mirror: the same lone hunter reads the same KILL --
  both bots refuse and explore north, byte-identical;
- the engaged-DIE hold: two foes make the step DIE despite engaged
  backup -- both bots refuse, byte-identical (pricing never buys a
  losing fight);
- quiet boards order byte-identical to base;
- the full turn stays under 1s crowded;
- entry self-containment.

Pins (a) the engaged-count geometry unit, (b) the far-backup
discriminator where base marches east while Influence13 walks
north, (c) engaged-backup advance identity, (d) unbacked-KILL
refusal identity, (e) engaged-DIE refusal identity, (f)
quiet-board identity, (g) cost, and (h) self-containment.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Influence10 as Base  # noqa: E402
import Influence13 as New  # noqa: E402

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
    """Same fresh turn through base and Influence13; returns both orders."""
    fake_base = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    Base.Influence10().do_turn(fake_base)
    fake_new = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    New.Influence13().do_turn(fake_new)
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
# hill push either -- only pricing can march H.
H = (10, 12)
D = (10, 13)
F = (10, 16)
F2 = (10, 15)
# Far mates: 7 and 8 from D (in backup range, so base prices the
# trade) but 10 and 9 from F (beyond SEEK_RANGE 8 -- they can
# never join the fight). Outside the reach-3 diamond of D (so the
# verdict stays KILL) and 9+ from every foe (out of seek range,
# so they explore identically in both bots).
B1 = (10, 6)
B2 = (10, 5)
FAR_MINE = [H, B1, B2]
# Engaged mates: 5 and 4 from D (in backup range, outside the
# reach-3 diamond so the verdict stays KILL) and 8 and 7 from F
# (inside SEEK_RANGE 8 -- true reinforcements one wave behind the
# hunter). 7+ from F keeps them out of contact, so no deadlock in
# either bot; their own east steps read SAFE and march in both.
E1 = (10, 8)
E2 = (10, 9)
NEAR_MINE = [H, E1, E2]


def test_engaged_backup_count_geometry() -> None:
    # (a) Unit: the mover is excluded, both gates apply, and only
    # mates near the destination AND near the foe count.
    assert _manhattan(B1, D) == 7
    assert _manhattan(B2, D) == 8
    assert _manhattan(B1, F) == 10
    assert _manhattan(B2, F) == 9
    assert _manhattan(E1, D) == 5
    assert _manhattan(E2, D) == 4
    assert _manhattan(E1, F) == 8
    assert _manhattan(E2, F) == 7
    assert _manhattan(H, F) == 4
    # Far mates: backup-near but foe-far -- priced by base, not here.
    assert New.engaged_backup_count(D, FAR_MINE, H, F, _manhattan) == 0
    assert Base.backup_count(D, FAR_MINE, H, _manhattan) == 2
    # Engaged mates: both gates pass.
    assert New.engaged_backup_count(D, NEAR_MINE, H, F, _manhattan) == 2
    # The mover never counts itself; a foe-far destination counts none.
    assert New.engaged_backup_count(D, [H], H, F, _manhattan) == 0
    assert New.engaged_backup_count((0, 0), NEAR_MINE, H, F, _manhattan) == 0


def test_far_backup_refuses_where_base_advances() -> None:
    # (b) Mispriced-take discriminator: far backup outside any
    # deadlock or hill push. The step reads mid-turn KILL; base
    # prices the headcount and marches H east while Influence13
    # refuses and its explore walks H north (all neighbors
    # unvisited, n first, SAFE and safe).
    live, foe = New.influence_fields(FAR_MINE, [F], ROWS, COLS, 3)
    assert New.rate_step(live, foe, D) == New.KILL
    base_orders, new_orders = run_both(FAR_MINE, [F])
    assert dict(base_orders)[H] == "e"
    assert dict(new_orders)[H] == "n"
    assert new_orders != base_orders


def test_engaged_backup_advances_like_base() -> None:
    # (c) Real-reinforcement mirror: the same KILL with two engaged
    # mates -- both bots price the trade and march H east.
    live, foe = New.influence_fields(NEAR_MINE, [F], ROWS, COLS, 3)
    assert New.rate_step(live, foe, D) == New.KILL
    base_orders, new_orders = run_both(NEAR_MINE, [F])
    assert dict(new_orders)[H] == "e"
    assert new_orders == base_orders


def test_unbacked_kill_refuses_like_base() -> None:
    # (d) Lone-hunter mirror: the same KILL with no backup -- both
    # bots refuse and explore north.
    live, foe = New.influence_fields([H], [F], ROWS, COLS, 3)
    assert New.rate_step(live, foe, D) == New.KILL
    base_orders, new_orders = run_both([H], [F])
    assert new_orders == base_orders
    assert dict(new_orders)[H] == "n"


def test_engaged_die_still_refuses() -> None:
    # (e) Losing-fight hold: a second foe makes D DIE (theirs 2 vs
    # ours 1) despite engaged backup -- pricing never buys a losing
    # fight, so both bots refuse and explore north.
    live, foe = New.influence_fields(NEAR_MINE, [F, F2], ROWS, COLS, 3)
    assert New.rate_step(live, foe, D) == New.DIE
    base_orders, new_orders = run_both(NEAR_MINE, [F, F2])
    assert new_orders == base_orders
    assert dict(new_orders)[H] == "n"


def test_quiet_boards_byte_identical_to_base() -> None:
    # (f) Nothing repriced on quiet boards -- lone hunter SAFE
    # march, 1v1 contact trade, food plus hill in play, hill-push
    # KILL march, and the far-backed board (misprice removed but
    # covered here as the one known difference) excluded -- so
    # every order here matches base exactly.
    sparse: list[tuple[list[Loc], list[Loc], list[Loc] | None, list[Loc] | None]] = [
        ([(5, 5)], [(5, 15)], None, None),
        ([(5, 5)], [(5, 7)], None, None),
        ([(5, 5)], [(5, 7)], [(0, 0)], [(15, 15)]),
        ([(5, 5)], [(5, 9)], None, [(5, 12)]),
        ([H, E1], [F], None, None),
        (NEAR_MINE, [F, F2], None, None),
    ]
    for mine, foes, foods, hills in sparse:
        base_orders, new_orders = run_both(mine, foes, foods=foods, enemy_hills=hills)
        assert new_orders == base_orders


def test_full_turn_costs_under_1s_on_crowded_board() -> None:
    # (g) A full crowded turn -- 30 ants a side plus food and two
    # contested hills -- finishes far inside one second; engagement
    # adds one manhattan scan per KILL step only.
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
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Influence13.py")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert hasattr(New, "Influence13")
    assert hasattr(New, "influence_fields")
    assert hasattr(New, "move_own_stamp")
    assert hasattr(New, "classify_counts")
    assert hasattr(New, "project_final_field")
    assert hasattr(New, "engaged_backup_count")
