#!/usr/bin/env python
"""Focus-geometry KILL tiebreak tests (Influence12 entry).

Self-contained: FakeAnts plus the Influence8 base and Influence12
entries only, never the shared combat.py helpers. Influence12 keeps
the whole Influence8 tree and changes exactly one mechanism: in the
seek branch, a mid-turn KILL (scaled influence tie) may also advance
outside deadlocks and hill pushes when the mover survives focus
resolution at its destination -- every foe covering the destination
is itself covered by strictly more own ants than the mover's own
weakness, i.e. min foe weakness > own weakness under the engine's
do_attack_focus rule. Unbacked geometry (a 1v1 trade) still refuses,
DIE always refuses, and the final-field veto still covers
focus-takes: a mid-KILL survives anything but final DIE. This is
NOT backup pricing (no manhattan-10 headcount, no PRICED_KILL_NEAR):
it reads attack-range geometry the way Dirichlet's sampler does,
where a supporter covering the foe -- but not the destination --
turns a 1-for-1 into a free kill.

Consequences pinned here:

- the angled-support board discriminates: H hunts east onto D
  where influence ties 1v1 (H covers D, one foe covers D, the
  supporter covers the foe but not D), focus reads the foe dead
  and both own alive (a 1-0 trade), so Influence12 marches H east
  while base holds H;
- the 1v1 board refuses in both: the foe covering D has weakness
  1, not strictly above the mover's weakness 1, so the trade stays
  a 1-for-1 and both bots hold;
- quiet boards stay byte-identical to base (no focus-win fires);
- the converge pair still marches identically;
- the full turn stays under 1s crowded.

Pins (a) the focus_survives helper on hand-computed geometry,
(b) the angled-support discriminator where Influence12 marches
while base holds, (c) the 1v1 refusal in both, (d) byte-identity
on quiet boards, (e) converge preservation, (f) cost, and
(g) self-containment.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Influence8 as Base  # noqa: E402
import Influence12 as New  # noqa: E402

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


def run_both(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], list[tuple[Loc, str]]]:
    """Same fresh turn through base and Influence12; returns both orders."""
    fake_base = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    Base.Influence8().do_turn(fake_base)
    fake_new = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    New.Influence12().do_turn(fake_new)
    return fake_base.orders, fake_new.orders


def sq(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


# (b) Angled-support board. H=(10,12) hunts F=(11,15) with water
# closing every lane but east, so the seek must step onto D=(10,13).
# D reads mid-turn ours 1 (only H covers D) vs theirs 1 (F covers D
# at squared distance 5) -> KILL; H stands outside contact range
# and pushes no hill, so base has no deadlock and, with D failing
# the champion safety filter and water elsewhere, holds H. Focus:
# the mover's weakness at D is 1 (F covers D) while F's weakness is
# 2 (H arrives at D and S=(12,16) already covers F),
# so the mover survives and Influence12 marches east into a 1-0
# trade -- the shape Dirichlet's sampler prices and Influence8's
# veto over-holds.
H = (10, 12)
S = (12, 16)
FOE = (11, 15)
D = (10, 13)
LANE_WATER = {(9, 12), (11, 12), (10, 11)}

# (c) 1v1 board. H hunts F=(10,15) onto D=(10,13) down the same
# water lane: influence ties 1v1 -> KILL, but F's weakness is 1
# (only the arriving H covers it), not strictly above the mover's
# weakness 1, so both hold.
SOLO_FOE = (10, 15)

# (e) Converge board (from the Influence8 suite). A1=(10,9) and
# A2=(10,12) hunt F=(10,16): the joined pair still reads SAFE and
# both bots march east identically.
A1 = (10, 9)
A2 = (10, 12)
BIG_FOE = (10, 16)


def test_focus_survives_reads_hand_computed_geometry() -> None:
    # (a) Angled support: mover weak 1, sole covering foe weak 2
    # -> survives. Lone 1v1: weaknesses 1 vs 1 -> dies. Empty
    # tile (no foe covers): survives vacuously.
    assert sq(S, D) > R2
    assert sq(S, FOE) <= R2
    assert sq(FOE, D) <= R2
    assert New.focus_survives(D, [H, S], H, [FOE], R2, ROWS, COLS) is True
    assert New.focus_survives(D, [H], H, [SOLO_FOE], R2, ROWS, COLS) is False
    assert New.focus_survives((0, 0), [H], H, [SOLO_FOE], R2, ROWS, COLS) is True
    # The weakest covering foe decides: two foes cover, one is
    # covered back only by the mover -> the trade dies with it.
    f2 = (9, 14)
    assert sq(f2, D) <= R2
    assert sq(S, f2) > R2
    assert New.focus_survives(D, [H, S], H, [FOE, f2], R2, ROWS, COLS) is False


def test_focus_take_marches_where_base_holds() -> None:
    # (b) Behavioral discriminator: the mid-turn verdict is KILL
    # (ours 1 vs theirs 1 at D), H stands outside contact with no
    # hill push, so base has no deadlock and holds H (D fails the
    # safety filter, water closes the other lanes) -- while focus
    # reads a 1-0 trade and Influence12 marches H east. The veto
    # must not claw it back: the final field still reads KILL at D.
    live, foe_field = New.influence_fields([H, S], [FOE], ROWS, COLS, 3)
    assert New.rate_step(live, foe_field, D) == New.KILL
    base_orders, new_orders = run_both([H, S], [FOE], water=LANE_WATER)
    assert H not in dict(base_orders)
    assert dict(new_orders)[H] == "e"
    assert new_orders != base_orders


def test_losing_trade_refuses_in_both() -> None:
    # (c) 1v1 geometry prices at exactly 1-for-1: both bots hold H.
    live, foe_field = New.influence_fields([H], [SOLO_FOE], ROWS, COLS, 3)
    assert New.rate_step(live, foe_field, D) == New.KILL
    base_orders, new_orders = run_both([H], [SOLO_FOE], water=LANE_WATER)
    assert H not in dict(base_orders)
    assert H not in dict(new_orders)
    assert new_orders == base_orders


def test_quiet_boards_byte_identical_to_base() -> None:
    # (d) Nothing focus-winning on quiet boards -- lone hunter,
    # 1v1 contact trade, food plus hill in play, and a hill-push
    # KILL march -- so every order matches base exactly.
    sparse: list[tuple[list[Loc], list[Loc], list[Loc] | None, list[Loc] | None]] = [
        ([(5, 5)], [(5, 15)], None, None),
        ([(5, 5)], [(5, 7)], None, None),
        ([(5, 5)], [(5, 7)], [(0, 0)], [(15, 15)]),
        ([(5, 5)], [(5, 9)], None, [(5, 12)]),
        ([(10, 12), (10, 10)], [(10, 16)], None, None),
    ]
    for mine, foes, foods, hills in sparse:
        base_orders, new_orders = run_both(mine, foes, foods=foods, enemy_hills=hills)
        assert new_orders == base_orders


def test_converge_board_still_marches_pair() -> None:
    # (e) The joined pair reads SAFE mid-turn and finally: both
    # bots march A1 and A2 east identically, no veto, no focus
    # needed.
    base_orders, new_orders = run_both([A1, A2], [BIG_FOE])
    assert dict(base_orders)[A1] == "e"
    assert dict(new_orders)[A1] == "e"
    assert dict(new_orders)[A2] == "e"
    assert new_orders == base_orders


def test_full_turn_costs_under_1s_on_crowded_board() -> None:
    # (f) A full crowded turn -- 30 ants a side plus food and two
    # contested hills -- finishes far inside one second; the focus
    # read is linear per KILL step.
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
    # ants.py only, never the shared combat.py helpers, and no
    # backup-priced KILL machinery.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Influence12.py")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert "PRICED_KILL_NEAR" not in source
    assert "BACKUP_RANGE" not in source
    assert "backup_count" not in source
    assert hasattr(New, "Influence12")
    assert hasattr(New, "influence_fields")
    assert hasattr(New, "move_own_stamp")
    assert hasattr(New, "classify_counts")
    assert hasattr(New, "project_final_field")
    assert hasattr(New, "focus_survives")
