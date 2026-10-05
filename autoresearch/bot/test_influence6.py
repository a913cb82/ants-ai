#!/usr/bin/env python
"""Rear-first processing order tests (Influence6 entry).

Self-contained: FakeAnts plus the Influence5 and Influence6 entries
only, never the shared combat.py helpers. Influence6 keeps the whole
Influence5 tree and changes exactly one mechanism: the main loop
processes ants farthest from visible enemies first (stable, with a
coordinate tiebreak, so the order is canonical for a position set),
so rear supporters' combat stamps land before front-line followers
read. Verdicts, fields, refinement, and the foe field are unchanged.

Consequences pinned here:

- the reversed converge board still converges: list order
  [near, far] makes Influence5 wander the follower north (it reads
  the snapshot KILL before the leader advances), while Influence6
  marches both east exactly like list order [far, near];
- processing order is canonical: reversing or shuffling the input
  ant list never changes Influence6's orders on combat-only boards;
- no-enemy turns order byte-identical to Influence5 (all keys tie,
  the stable sort keeps list order, and explore never stamped);
- single-ant turns order byte-identical to Influence5;
- the full turn stays under 1s crowded.

Pins (a) the reversed-order discriminator where Influence6 matches
its own list-order result against Influence5, (b) canonical-order
invariance under permutation, (c) no-enemy byte-identity, (d)
single-ant byte-identity, (e) the full turn under 1s crowded, and
(f) entry self-containment.
"""

import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Influence5 as Base  # noqa: E402
import Influence6 as New  # noqa: E402

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


def run_base(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    """One fresh Influence5 turn."""
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    Base.Influence5().do_turn(fake)
    return fake.orders


def run_new(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    """One fresh Influence6 turn."""
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    New.Influence6().do_turn(fake)
    return fake.orders


def _manhattan(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


# Converge board (same geometry as the Influence5 converge pin).
# A1=(10,9) marches east SAFE; A2=(10,12) reads snapshot KILL until
# A1's stamp lands. List order [far, near] converges under both
# bots; the discriminator is the reversed list order [near, far].
A1 = (10, 9)
A2 = (10, 12)
FOE = (10, 16)
D2 = (10, 13)
NEAR_FIRST = [A2, A1]
FAR_FIRST = [A1, A2]
FOES = [FOE]


def test_reversed_converge_board_still_converges() -> None:
    # (a) The discriminator: with the follower listed first,
    # Influence5 reads the snapshot KILL and wanders north, while
    # Influence6 processes the rear supporter first and marches
    # both east -- the same orders it issues in list order.
    assert _manhattan(A1, D2) == 4
    assert _manhattan((10, 10), D2) == REACH
    base_reversed = run_base(NEAR_FIRST, FOES)
    assert dict(base_reversed)[A1] == "e"
    assert dict(base_reversed).get(A2) != "e"
    new_reversed = run_new(NEAR_FIRST, FOES)
    new_listed = run_new(FAR_FIRST, FOES)
    assert dict(new_reversed)[A1] == "e"
    assert dict(new_reversed)[A2] == "e"
    assert new_reversed == new_listed
    assert new_reversed != base_reversed


def test_processing_order_canonical_under_permutation() -> None:
    # (b) Combat-only boards (no food, no hills, so the ant index
    # feeds nothing but the loop): reversing and shuffling the
    # input list never changes Influence6's orders.
    rng = random.Random(20260612)
    for _ in range(20):
        n_ours = rng.randint(2, 4)
        n_foes = rng.randint(1, 3)
        mine = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(n_ours)]
        foes = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(n_foes)]
        if len(set(mine + foes)) < n_ours + n_foes:
            continue
        listed = run_new(list(mine), list(foes))
        assert run_new(list(reversed(mine)), list(foes)) == listed
        shuffled = list(mine)
        rng.shuffle(shuffled)
        assert run_new(shuffled, list(foes)) == listed


def test_no_enemy_turns_byte_identical_to_base() -> None:
    # (c) No visible enemies: every distance key ties, the stable
    # sort keeps list order, and nothing stamps -- food plus
    # explore come out exactly as Influence5.
    boards: list[tuple[list[Loc], list[Loc] | None]] = [
        ([(5, 5), (9, 9)], None),
        ([(5, 5), (9, 9)], [(0, 0), (15, 15)]),
        ([(5, 5), (5, 6), (12, 3)], [(0, 0)]),
    ]
    for mine, foods in boards:
        assert run_new(list(mine), [], foods=foods) == run_base(
            list(mine), [], foods=foods
        )


def test_single_ant_turns_byte_identical_to_base() -> None:
    # (d) One ant sorts alone: lone hunter, 1v1 contact trade, food
    # plus hill in play, and a hill-push KILL march all order
    # exactly like Influence5.
    assert run_new([(5, 5)], [(5, 15)]) == run_base([(5, 5)], [(5, 15)])
    assert run_new([(5, 5)], [(5, 7)]) == run_base([(5, 5)], [(5, 7)])
    assert run_new([(5, 5)], [(5, 7)], foods=[(0, 0)]) == run_base(
        [(5, 5)], [(5, 7)], foods=[(0, 0)]
    )
    assert run_new([(5, 5)], [(5, 9)], enemy_hills=[(5, 12)]) == run_base(
        [(5, 5)], [(5, 9)], enemy_hills=[(5, 12)]
    )


def test_full_turn_costs_under_1s_on_crowded_board() -> None:
    # (e) A full crowded turn -- 30 ants a side plus food and two
    # contested hills -- finishes far inside one second; the sort
    # is one linear pass of distance keys.
    ours = [((i * 7 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(30)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [((i * 3 + 9) % ROWS, (i * 17 + 4) % COLS) for i in range(10)]
    start = time.perf_counter()
    orders = run_new(ours, foes, foods=foods, enemy_hills=[(10, 10), (10, 3)])
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert isinstance(orders, list)


def test_entry_is_self_contained() -> None:
    # (f) The entry carries its own combat core: stdlib plus ants.py
    # only, never the shared combat.py helpers.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Influence6.py")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert hasattr(New, "Influence6")
    assert hasattr(New, "influence_fields")
    assert hasattr(New, "move_own_stamp")
    assert hasattr(New, "classify_counts")
