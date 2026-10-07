#!/usr/bin/env python
"""Backup-priced KILL tests (Influence10 entry).

Self-contained: FakeAnts plus the Influence8 and Influence10 entries
only, never the shared combat.py helpers. Influence10 keeps the whole
Influence8 tree and changes exactly one mechanism: in the seek branch,
a KILL step (expect a 1-for-1) may also advance outside deadlocks and
hill pushes when it is PRICED -- at least PRICED_KILL_NEAR (2) other
own ants stand within BACKUP_RANGE (10) steps of the destination, so
reinforcements convert the trade on the follow-up. Unbacked KILLs
still refuse, DIE always refuses (even backed), and every other
branch -- verdicts, refinement, veto, economy, guard, muster,
reinforce, explore, walk-off -- is unchanged.

Consequences pinned here:

- the backed-KILL discriminator: hunter H approaches foe F, the east
  step reads mid-turn KILL with two mates in backup range but H is
  not in contact and no hill is remembered -- base refuses and walks
  north via explore while Influence10 prices the trade and marches
  east (the final-field veto still covers it: final reads KILL, a
  mid-KILL survives anything but DIE);
- the unbacked mirror: the same lone hunter reads the same KILL with
  no backup -- both bots refuse and explore north, byte-identical;
- the backed-DIE hold: two foes make the step DIE despite backup --
  both bots refuse, byte-identical (pricing never buys a losing
  fight);
- quiet boards order byte-identical to base (SAFE marches, food,
  hills, contact trades);
- the full turn stays under 1s crowded;
- entry self-containment.

Pins (a) the backup-count geometry unit, (b) the backed-KILL
discriminator where Influence10 marches east while base walks
north, (c) unbacked-KILL refusal identity, (d) backed-DIE refusal
identity, (e) quiet-board identity, (f) cost, and (g)
self-containment.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Influence8 as Base  # noqa: E402
import Influence10 as New  # noqa: E402

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
    """Same fresh turn through base and Influence10; returns both orders."""
    fake_base = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    Base.Influence8().do_turn(fake_base)
    fake_new = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    New.Influence10().do_turn(fake_new)
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
# hill push either -- base must refuse. Mates B1=(10,6) and
# B2=(10,3) sit 7 and 10 from D (in backup range) but 4+ from D
# (outside the reach-3 diamond, so the verdict stays KILL) and
# 9+ from every foe (out of seek range, so they explore
# identically in both bots).
H = (10, 12)
B1 = (10, 6)
B2 = (10, 3)
F = (10, 16)
F2 = (10, 15)
D = (10, 13)
BACKED_MINE = [H, B1, B2]


def test_backup_count_geometry() -> None:
    # (a) Unit: the mover is excluded, range 10 is inclusive, and
    # only mates near the destination count.
    assert _manhattan(B1, D) == 7
    assert _manhattan(B2, D) == 10
    assert _manhattan(H, F) == 4
    assert New.backup_count(D, BACKED_MINE, H, _manhattan) == 2
    assert New.backup_count(D, [H], H, _manhattan) == 0
    assert New.backup_count(D, BACKED_MINE, B1, _manhattan) == 2
    # Far mates drop out (toroidal distances 16 and 13 > 10).
    assert New.backup_count((0, 0), BACKED_MINE, H, _manhattan) == 0


def test_backed_kill_advances_where_base_walks_off() -> None:
    # (b) Dirichlet-like pressure discriminator: backed KILL outside
    # any deadlock or hill push. Base refuses and its explore walks
    # H north (all neighbors unvisited, n first, SAFE and safe);
    # Influence10 prices the trade and marches H east.
    live, foe = New.influence_fields(BACKED_MINE, [F], ROWS, COLS, 3)
    assert New.rate_step(live, foe, D) == New.KILL
    base_orders, new_orders = run_both(BACKED_MINE, [F])
    assert dict(base_orders)[H] == "n"
    assert dict(new_orders)[H] == "e"
    assert new_orders != base_orders


def test_unbacked_kill_refuses_like_base() -> None:
    # (c) Crowd hold mirror: the same lone hunter reads the same
    # KILL with no backup -- both bots refuse and explore north.
    live, foe = New.influence_fields([H], [F], ROWS, COLS, 3)
    assert New.rate_step(live, foe, D) == New.KILL
    base_orders, new_orders = run_both([H], [F])
    assert new_orders == base_orders
    assert dict(new_orders)[H] == "n"


def test_backed_die_still_refuses() -> None:
    # (d) Crowd hold: a second foe makes D DIE (theirs 2 vs ours 1)
    # despite full backup -- pricing never buys a losing fight, so
    # both bots refuse and explore north.
    live, foe = New.influence_fields(BACKED_MINE, [F, F2], ROWS, COLS, 3)
    assert New.rate_step(live, foe, D) == New.DIE
    base_orders, new_orders = run_both(BACKED_MINE, [F, F2])
    assert new_orders == base_orders
    assert dict(new_orders)[H] == "n"


def test_quiet_boards_byte_identical_to_base() -> None:
    # (e) Nothing priced on quiet boards -- lone hunter SAFE march,
    # 1v1 contact trade, food plus hill in play, hill-push KILL
    # march, and the backed board minus one mate (1 backup < 2) --
    # so every order matches base exactly.
    sparse: list[tuple[list[Loc], list[Loc], list[Loc] | None, list[Loc] | None]] = [
        ([(5, 5)], [(5, 15)], None, None),
        ([(5, 5)], [(5, 7)], None, None),
        ([(5, 5)], [(5, 7)], [(0, 0)], [(15, 15)]),
        ([(5, 5)], [(5, 9)], None, [(5, 12)]),
        ([H, B1], [F], None, None),
        (BACKED_MINE, [F, F2], None, None),
    ]
    for mine, foes, foods, hills in sparse:
        base_orders, new_orders = run_both(mine, foes, foods=foods, enemy_hills=hills)
        assert new_orders == base_orders


def test_full_turn_costs_under_1s_on_crowded_board() -> None:
    # (f) A full crowded turn -- 30 ants a side plus food and two
    # contested hills -- finishes far inside one second; pricing
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
    # (g) The entry carries its own combat core: stdlib plus
    # ants.py only, never the shared combat.py helpers.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Influence10.py")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert hasattr(New, "Influence10")
    assert hasattr(New, "influence_fields")
    assert hasattr(New, "move_own_stamp")
    assert hasattr(New, "classify_counts")
    assert hasattr(New, "project_final_field")
    assert hasattr(New, "backup_count")
