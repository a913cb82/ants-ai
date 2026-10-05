#!/usr/bin/env python
"""Foe pursuit-projection tests (Influence7 entry).

Self-contained: FakeAnts plus the Influence6 and Influence7 entries
only, never the shared combat.py helpers. Influence7 keeps the whole
Influence6 tree and changes exactly one mechanism: the foe influence
field is stamped at each visible foe's PROJECTED tile -- one toroidal
step toward its nearest own ant -- instead of its snapshot tile, so
followers read where foes will be when they arrive. Own field, live
own stamps, verdicts, refinement, rear-first order, and every branch
are unchanged.

Consequences pinned here:

- projection unit: one step along the larger toroidal gap (ties go
  row-first), distance zero stays, wrap sides step across the seam,
  equidistant-foe ties break on coordinates (never list order);
- the approach discriminator: a hunter stepping east reads snapshot
  SAFE/KILL but projected DIE once two closing foes are counted at
  their arrival tiles -- base wanders east via explore, Influence7
  refuses east;
- 1v1 contact preserved: projection keeps the KILL trade, both ants
  still march (no new freeze);
- far-foe and no-enemy turns order byte-identical to Influence6;
- processing order stays canonical under permutation;
- the full turn stays under 1s crowded.

Pins (a) projection geometry, (b) the approach discriminator,
(c) contact-trade preservation, (d) far-foe byte-identity,
(e) no-enemy byte-identity, (f) canonical order, (g) cost, and
(h) entry self-containment.
"""

import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Influence6 as Base  # noqa: E402
import Influence7 as New  # noqa: E402

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
        dc = min(dc, self.rows - dc)
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
    """One fresh Influence6 turn."""
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    Base.Influence6().do_turn(fake)
    return fake.orders


def run_new(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    """One fresh Influence7 turn."""
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    New.Influence7().do_turn(fake)
    return fake.orders


def test_projection_geometry() -> None:
    # (a) One toroidal step toward the nearest own ant: larger gap
    # axis first, row on ties, zero distance stays, seam wraps,
    # equidistant ties break on ant coordinates.
    assert New.predict_foe((10, 15), [(10, 10)], ROWS, COLS) == (10, 14)
    assert New.predict_foe((8, 8), [(10, 10)], ROWS, COLS) == (9, 8)
    assert New.predict_foe((10, 10), [(10, 10)], ROWS, COLS) == (10, 10)
    assert New.predict_foe((0, 5), [(19, 5)], ROWS, COLS) == (19, 5)
    assert New.predict_foe((5, 0), [(5, 19)], ROWS, COLS) == (5, 19)
    # Foe at (10, 12) sits 2 from (10, 10) and 2 from (10, 14):
    # the smaller-coordinate ant wins regardless of list order.
    assert New.predict_foe((10, 12), [(10, 14), (10, 10)], ROWS, COLS) == (10, 11)
    assert New.predict_foe((10, 12), [(10, 10), (10, 14)], ROWS, COLS) == (10, 11)
    # Empty army: nothing to chase, the foe holds.
    assert New.predict_foe((7, 7), [], ROWS, COLS) == (7, 7)
    assert New.predict_foes([(10, 15), (7, 7)], [(10, 10)], ROWS, COLS) == [
        (10, 14),
        (8, 7),
    ]


# Approach discriminator: A=(10,10) hunts east; F1=(10,15) and
# F2=(10,14) close from the east. The east step lands on (10,11):
# snapshot counts ours 1 vs theirs 1 (F2 only) = KILL, so base
# refuses the seek but wanders east anyway through explore (KILL
# is explorable and no enemy sits within attack range). Projected
# foes stand on (10,14) and (10,13): both cover (10,11), so the
# step reads DIE and Influence7 never steps east.
APPROACH_MINE = [(10, 10)]
APPROACH_FOES = [(10, 15), (10, 14)]
# Water walls off every escape but east, so the explore fallback is
# forced through the contested step: base wanders east (KILL is
# explorable), Influence7 holds (projected DIE is not).
APPROACH_WATER = {(9, 10), (11, 10), (10, 9)}


def test_approach_discriminator() -> None:
    # (b) Base steps east; Influence7 refuses the east step.
    assert (
        dict(run_base(APPROACH_MINE, APPROACH_FOES, water=APPROACH_WATER))[(10, 10)]
        == "e"
    )
    new_orders = dict(run_new(APPROACH_MINE, APPROACH_FOES, water=APPROACH_WATER))
    assert (10, 10) not in new_orders


def test_contact_trade_preserved() -> None:
    # (c) 1v1 contact: projection keeps the KILL (foe (10,12) is
    # counted at (10,11), still one-for-one) so both bots march.
    mine = [(10, 10)]
    foes = [(10, 12)]
    assert dict(run_base(mine, foes))[(10, 10)] == "e"
    assert dict(run_new(mine, foes))[(10, 10)] == "e"


def test_far_foe_turns_byte_identical_to_base() -> None:
    # (d) Foes too far to cover our tiles: the shifted stamp lands
    # nowhere we read, so hunter, food, and hill turns match base.
    assert run_new([(5, 5)], [(15, 15)]) == run_base([(5, 5)], [(15, 15)])
    assert run_new([(5, 5)], [(15, 15)], foods=[(0, 0)]) == run_base(
        [(5, 5)], [(15, 15)], foods=[(0, 0)]
    )
    assert run_new([(5, 5)], [(15, 15)], enemy_hills=[(5, 12)]) == run_base(
        [(5, 5)], [(15, 15)], enemy_hills=[(5, 12)]
    )


def test_no_enemy_turns_byte_identical_to_base() -> None:
    # (e) No visible foes: projection is the identity, food plus
    # explore come out exactly as Influence6.
    boards: list[tuple[list[Loc], list[Loc] | None]] = [
        ([(5, 5), (9, 9)], None),
        ([(5, 5), (9, 9)], [(0, 0), (15, 15)]),
        ([(5, 5), (5, 6), (12, 3)], [(0, 0)]),
    ]
    for mine, foods in boards:
        assert run_new(list(mine), [], foods=foods) == run_base(
            list(mine), [], foods=foods
        )


def test_processing_order_canonical_under_permutation() -> None:
    # (f) Combat-only boards: reversing and shuffling the input
    # list never changes Influence7's orders (projection breaks
    # ties on coordinates, never list order).
    rng = random.Random(20260707)
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


def test_full_turn_costs_under_1s_on_crowded_board() -> None:
    # (g) A full crowded turn -- 30 ants a side plus food and two
    # contested hills -- finishes far inside one second; projection
    # is one linear pass of nearest-own keys.
    ours = [((i * 7 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(30)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [((i * 3 + 9) % ROWS, (i * 17 + 4) % COLS) for i in range(10)]
    start = time.perf_counter()
    orders = run_new(ours, foes, foods=foods, enemy_hills=[(10, 10), (10, 3)])
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert isinstance(orders, list)


def test_entry_is_self_contained() -> None:
    # (h) The entry carries its own combat core: stdlib plus ants.py
    # only, never the shared combat.py helpers.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Influence7.py")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert hasattr(New, "Influence7")
    assert hasattr(New, "influence_fields")
    assert hasattr(New, "predict_foe")
    assert hasattr(New, "predict_foes")
    assert hasattr(New, "classify_counts")
