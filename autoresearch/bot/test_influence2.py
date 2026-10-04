#!/usr/bin/env python
"""KILL on hill-push tuning tests (Influence2 entry).

Self-contained: FakeAnts plus the Influence (base) and Influence2
entries only, never the shared combat.py helpers. Influence2 keeps
the whole base tree and widens exactly one gate: hill-advance steps
(muster, reinforce) on a hill-push turn take refined SAFE or KILL
(1-for-1) and refuse only DIE, instead of the champion majority
filter that refuses winnable even fights. Seek (SAFE / hill-push
or deadlock KILL / DIE-refused), guard, food, explore, and
walk-off stay byte-identical in behavior.

Pins (a) muster-KILL taken on a hill-push turn without deadlock
where base refuses the same step, (b) KILL still refused with no
hill-push and no deadlock with orders exactly equal to base, (c)
DIE refused everywhere exactly as base, and (d) the full turn
under 1s crowded.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Influence as Base  # noqa: E402
import Influence2 as New  # noqa: E402

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
    """Same fresh turn through base and Influence2; returns both orders."""
    fake_base = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    Base.Influence().do_turn(fake_base)
    fake_new = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    New.Influence2().do_turn(fake_new)
    return fake_base.orders, fake_new.orders


def _sq(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


def _in_contact(ant: Loc, foes: list[Loc]) -> bool:
    return any(_sq(ant, e) <= 5 for e in foes)


# (a) Muster board. Hunter A=(10,10) holds no food claim and no
# guard duty. The west pack (raw 3 -> refined 2 vs ours 1) makes the
# seek step onto (10,9) DIE, so both bots refuse it; the nearest foe
# (10,7) keeps the seek looking west. The remembered hill H=(10,16)
# marches the muster east onto (10,11): raw 1 v 1 refines to KILL,
# while the old majority filter sees one foe in range (8,12) with
# no friends near and refuses. No foe stands within attack range of
# A itself, so there is no deadlock -- only the hill-push KILL.
A = (10, 10)
WEST_PACK = [(10, 7), (9, 7), (11, 7)]
EAST_STAMPER = (8, 12)
HILL_EAST = (10, 16)
MUSTER_FOES = [*WEST_PACK, EAST_STAMPER]

# Reinforce board: a second hill H2=(10,3) waits behind. The east
# pack also covers the muster step (10,11) at raw 3 -> DIE, so both
# bots refuse the muster; the reinforce step west onto (10,9) is
# KILL (stamper (8,8) at manhattan 3, square-distance 5) with no
# friends near, so base refuses it and Influence2 marches.
EAST_PACK = [(10, 13), (9, 13), (11, 13)]
WEST_STAMPER = (8, 8)
HILL_WEST = (10, 3)
REINFORCE_FOES = [*EAST_PACK, WEST_STAMPER]
REINFORCE_HILLS = [HILL_EAST, HILL_WEST]

# Shared base boards: lone-hunter KILL refused hill-less, contact
# deadlock, backed contact with a SAFE escape, and the DIE wall.
_KILL_MINE = [(5, 5), (5, 1), (5, 2), (6, 1)]
_KILL_FOES = [(5, 8), (15, 15), (15, 16), (16, 15), (0, 0)]
CONTACT_MINE = [(5, 5)]
CONTACT_FOES = [(5, 7)]
CONTACT_SAFE_MINE = [(5, 5), (4, 4), (4, 3)]
_DIE_MINE = [(5, 5), (5, 1), (5, 2), (6, 1)]
_DIE_FOES = [(5, 9), (2, 6), (8, 6), (2, 4), (8, 4), (6, 2)]


def test_muster_kill_taken_on_hill_push_without_deadlock() -> None:
    # (a) The muster square refines to KILL, the hunter stands
    # outside every attack range (no deadlock), and the hill push
    # is on: Influence2 steps east while base refuses east.
    assert not _in_contact(A, MUSTER_FOES)
    own, foe = New.influence_fields([A], MUSTER_FOES, ROWS, COLS, 3)
    assert New.rate_step(own, foe, (10, 11)) == New.KILL
    assert New.rate_step(own, foe, (10, 9)) == New.DIE
    base_orders, new_orders = run_both([A], MUSTER_FOES, enemy_hills=[HILL_EAST])
    assert dict(new_orders)[A] == "e"
    assert dict(base_orders).get(A) != "e"
    assert new_orders != base_orders


def test_reinforce_kill_taken_on_hill_push_without_deadlock() -> None:
    # (a) The muster square is DIE (both refuse it); the reinforce
    # square refines to KILL with no deadlock: Influence2 marches
    # west while base wanders elsewhere.
    assert not _in_contact(A, REINFORCE_FOES)
    own, foe = New.influence_fields([A], REINFORCE_FOES, ROWS, COLS, 3)
    assert New.rate_step(own, foe, (10, 11)) == New.DIE
    assert New.rate_step(own, foe, (10, 9)) == New.KILL
    base_orders, new_orders = run_both([A], REINFORCE_FOES, enemy_hills=REINFORCE_HILLS)
    assert dict(new_orders)[A] == "w"
    assert dict(base_orders).get(A) != "w"
    assert new_orders != base_orders


def test_kill_refused_without_hill_push_exactly_as_base() -> None:
    # (b) No hill remembered, no contact, KILL refused: the whole
    # order list matches base exactly (seek, muster-skipped,
    # reinforce-skipped, explore, walk-off all identical).
    base_orders, new_orders = run_both(_KILL_MINE, _KILL_FOES)
    assert dict(base_orders)[(5, 5)] == "n"
    assert new_orders == base_orders
    safe_base, safe_new = run_both(CONTACT_SAFE_MINE, CONTACT_FOES)
    assert dict(safe_base)[(5, 5)] == "n"
    assert safe_new == safe_base


def test_deadlock_kill_stays() -> None:
    # Deadlock-KILL is untouched: in contact with no SAFE move, both
    # bots still trade east with no hill anywhere.
    own, foe = New.influence_fields(CONTACT_MINE, CONTACT_FOES, ROWS, COLS, 3)
    assert New.rate_step(own, foe, (5, 6)) == New.KILL
    base_orders, new_orders = run_both(CONTACT_MINE, CONTACT_FOES)
    assert dict(base_orders)[(5, 5)] == "e"
    assert new_orders == base_orders


def test_hill_push_seek_kill_stays() -> None:
    # The base hill-push seek KILL is untouched: both bots step
    # east onto the KILL square when the hill push is on.
    base_orders, new_orders = run_both(_KILL_MINE, _KILL_FOES, enemy_hills=[(15, 15)])
    assert dict(base_orders)[(5, 5)] == "e"
    assert new_orders == base_orders


def test_die_refused_everywhere_exactly_as_base() -> None:
    # (c) The DIE wall: the east step refines to DIE (raw 3 -> 2
    # beats ours 1), so neither bot steps east hill-less, and the
    # whole hill-less turn matches base exactly.
    own, foe = New.influence_fields(_DIE_MINE, _DIE_FOES, ROWS, COLS, 3)
    assert New.rate_step(own, foe, (5, 6)) == New.DIE
    base_orders, new_orders = run_both(_DIE_MINE, _DIE_FOES)
    assert dict(base_orders).get((5, 5)) != "e"
    assert new_orders == base_orders
    # Even pushing a hill cannot spend a DIE on the muster square:
    # both bots refuse the east DIE and agree on the whole turn.
    die_base, die_new = run_both(
        [A], REINFORCE_FOES[:3] + [EAST_STAMPER], enemy_hills=[HILL_EAST]
    )
    assert dict(die_new).get(A) != "e"
    assert die_new == die_base


def test_safe_squares_advance_as_base() -> None:
    # SAFE play is untouched: a lone far foe leaves the east step
    # SAFE and both bots advance identically, hills or not.
    mine = [(5, 5), (5, 3), (5, 4), (6, 5)]
    own, foe = New.influence_fields(mine, [(5, 10)], ROWS, COLS, 3)
    assert New.rate_step(own, foe, (5, 6)) == New.SAFE
    base_orders, new_orders = run_both(mine, [(5, 10)])
    assert dict(new_orders)[(5, 5)] == "e"
    assert new_orders == base_orders
    hill_base, hill_new = run_both(mine, [(5, 10)], enemy_hills=[HILL_EAST])
    assert hill_new == hill_base


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
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Influence2.py")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert hasattr(New, "Influence2")
    assert hasattr(New, "influence_fields")
    assert hasattr(New, "refine")
    assert hasattr(New, "classify_counts")
