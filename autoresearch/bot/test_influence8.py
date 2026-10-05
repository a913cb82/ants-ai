#!/usr/bin/env python
"""Final-field veto tests (Influence8 entry).

Self-contained: FakeAnts plus the Influence4 (live-stamp base) and
Influence8 entries only, never the shared combat.py helpers.
Influence8 keeps the whole Influence4 tree and changes exactly one
mechanism: combat orders are PLANNED against the live field but
ISSUED only after re-verification against the final post-move
field -- every ant stamped where it will actually stand. A planned
combat step that read SAFE mid-turn but reads KILL or DIE finally
(support that was present at plan time leaves later in the turn)
is vetoed and the ant holds instead of marching into a vacated
fight. A step taken as a deadlock/hill-push KILL may only end at
KILL or better; DIE finally is always vetoed. Non-combat moves
(food, guard, walk-off, explore) are never vetoed.

Consequences pinned here:

- the late-leaver board discriminates: the hunter commits SAFE
  mid-turn while its supporter still covers, the supporter then
  leaves west for food, and the final field reads KILL -- base
  marches east into the vacated fight while Influence8 vetoes and
  holds (supporter still eats west in both);
- the converge board still converges: the leader arrives before
  the follower reads, the final field still reads SAFE, nothing
  is vetoed, and both bots march the pair east;
- quiet boards order byte-identical to base (nothing degrades
  finally, so the veto never fires);
- the full turn stays under 1s crowded.

Pins (a) the final-field projection helper on hand-computed
tiles, (b) the late-leaver discriminator where Influence8 holds
east while base marches, (c) converge preservation, (d)
byte-identity on quiet boards, (e) cost, and (f) self-containment.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Influence4 as Base  # noqa: E402
import Influence8 as New  # noqa: E402

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
    """Same fresh turn through base and Influence8; returns both orders."""
    fake_base = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    Base.Influence4().do_turn(fake_base)
    fake_new = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    New.Influence8().do_turn(fake_new)
    return fake_base.orders, fake_new.orders


def _manhattan(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


# (b) Late-leaver board. H=(10,12) hunts F=(10,16); S=(10,10) eats
# at (10,5) and steps west AFTER H commits (list order [H, S]).
# H's east step D=(10,13) reads mid-turn ours 2 (H at 1, S at 3)
# vs theirs 1 (F at 3) -> SAFE, so both bots plan east. S then
# steps west to (10,9), 4 from D, out of the diamond: the final
# field reads ours 1 vs theirs 1 -> KILL, so Influence8 vetoes
# east and H holds while base marches into the vacated fight.
H = (10, 12)
S = (10, 10)
FOE = (10, 16)
D = (10, 13)
LATE_MINE = [H, S]
LATE_FOES = [FOE]
LATE_FOODS = [(10, 5)]

# (c) Converge board (from the Influence4 suite). A1=(10,9) and
# A2=(10,12) hunt F=(10,16). The leader's advance lifts A2's step
# mid-turn KILL -> SAFE, and the final field (both ants east)
# still reads SAFE, so no veto fires and both bots march east.
A1 = (10, 9)
A2 = (10, 12)
D2 = (10, 13)
CONVERGE_MINE = [A1, A2]
CONVERGE_FOES = [FOE]


def test_final_field_stamps_planned_destinations() -> None:
    # (a) Hand-computed: H plans east to D, S plans west to
    # (10,9). The final field stamps both at their destinations:
    # D reads ours 1 (H covers its own tile), (10,9) reads ours 1
    # (S covers its own tile), and S's start (10,10) reads ours 2
    # (S at manhattan 1 and H at manhattan 3 both cover it).
    planned = [(H, D), (S, (10, 9))]
    final = New.project_final_field(LATE_MINE, planned, ROWS, COLS, REACH)
    assert final[D[0]][D[1]] == 1
    assert final[10][9] == 1
    assert final[10][10] == 2
    # D loses S's diamond: mid-turn live reads 2, final reads 1.
    live, _ = New.influence_fields(LATE_MINE, [], ROWS, COLS, REACH)
    assert live[D[0]][D[1]] == 2
    _, foe = New.influence_fields([], LATE_FOES, ROWS, COLS, REACH)
    assert New.rate_step(live, foe, D) == New.SAFE
    assert New.rate_step(final, foe, D) == New.KILL


def test_late_leaver_vetoes_where_base_marches() -> None:
    # (b) Behavioral discriminator: S eats west in both bots, base
    # marches H east into the vacated fight while Influence8 reads
    # the final KILL and holds H east.
    assert _manhattan(S, D) == REACH
    assert _manhattan((10, 9), D) == REACH + 1
    base_orders, new_orders = run_both(LATE_MINE, LATE_FOES, foods=LATE_FOODS)
    assert dict(new_orders)[S] == "w"
    assert dict(base_orders)[S] == "w"
    assert dict(base_orders)[H] == "e"
    assert dict(new_orders).get(H) != "e"
    assert new_orders != base_orders


def test_converge_board_still_marches_pair() -> None:
    # (c) The final field keeps the joined pair SAFE, so no veto
    # fires: both bots march A1 and A2 east identically.
    base_orders, new_orders = run_both(CONVERGE_MINE, CONVERGE_FOES)
    assert dict(base_orders)[A1] == "e"
    assert dict(new_orders)[A1] == "e"
    assert dict(new_orders)[A2] == "e"
    assert new_orders == base_orders


def test_quiet_boards_byte_identical_to_base() -> None:
    # (d) Nothing degrades finally on quiet boards -- lone
    # hunter, 1v1 contact trade, food plus hill in play, and a
    # hill-push KILL march -- so the veto never fires and every
    # order matches base exactly.
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


def test_full_turn_costs_under_1s_on_crowded_board() -> None:
    # (e) A full crowded turn -- 30 ants a side plus food and two
    # contested hills -- finishes far inside one second; the veto
    # adds one extra stamp pass plus one re-rate per combat plan.
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
    # (f) The entry carries its own combat core: stdlib plus
    # ants.py only, never the shared combat.py helpers.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Influence8.py")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert hasattr(New, "Influence8")
    assert hasattr(New, "influence_fields")
    assert hasattr(New, "move_own_stamp")
    assert hasattr(New, "classify_counts")
    assert hasattr(New, "project_final_field")
