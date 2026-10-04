#!/usr/bin/env python
"""Threat-ordered sequential fixing (Fixing2): contact ants commit first.

Base Fixing pins most-constrained-first, so a boxed rear ant can
commit before the contact ant sees the fight; Xathis outmaneuvers
the early commitment in duels. Fixing2 sorts the free ants by enemy
proximity (closest enemy distance ascending) before the sequential
fixing pass: contact ants commit with full freedom, rear ants route
around them.

Self-contained: stdlib plus Fixing2 only. No combat.py import.

  (a) contact ant fixes before rear ant on a pinned board where the
      base constraint order goes rear-first (rear boxed to 1 move,
      contact open with 3).
  (b) no-contact boards byte-identical: distant enemies
      (>SEEK_RANGE) issue exactly the no-enemy orders.
  (d) full crowded turn under 1 s.
"""

import os
import sys
import time
from typing import cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Fixing2 as FX  # noqa: E402

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


def run_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], FX.Fixing2]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = FX.Fixing2()
    bot.do_turn(fake)
    return fake.orders, bot


def _dist(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


def _dest(loc: Loc, direction: str) -> Loc:
    dr, dc = AIM[direction]
    return ((loc[0] + dr) % ROWS, (loc[1] + dc) % COLS)


def test_entry_is_self_contained() -> None:
    assert FX.__name__ == "Fixing2"
    assert hasattr(FX, "Fixing2")
    with open(str(FX.__file__)) as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert "class Fixing2" in source
    bot_file = os.path.join(os.path.dirname(str(FX.__file__)), "Fixing2.bot")
    with open(bot_file) as handle:
        assert handle.read().strip() == "python Fixing2.py"


def _pinned_passable(blocked: set[Loc]):
    def allow(loc: Loc) -> bool:
        return loc not in blocked

    return allow


def _allow(loc: Loc) -> bool:
    return True


# (a) pinned board: contact C=(5,5) vs foe (5,9) has 3 acceptable
# (n/s/w SAFE, e KILL refused with no hills); rear R=(15,15) is
# boxed to 1 legal move (w) far from the foe (all SAFE). Base
# most-constrained-first pins R(1) before C(3); threat order must
# pin C (dist 4) before R (dist 16).
_PIN_MINE = [(5, 5), (15, 15)]
_PIN_FOES = [(5, 9)]
_PIN_BLOCKED = {(14, 15), (15, 16), (16, 15)}


def test_contact_ant_fixes_before_rear_ant() -> None:
    field = FX.influence_field(_PIN_FOES, ROWS, COLS, FX.threat_reach(5))
    support: dict[Loc, int] = {}
    counts = [
        len(
            FX.acceptable_moves(
                ant,
                field,
                support,
                [],
                _dist,
                _dest,
                _pinned_passable(_PIN_BLOCKED),
                _allow,
            )
        )
        for ant in _PIN_MINE
    ]
    assert counts == [3, 1], f"board must be rear-constrained-first, got {counts}"
    dists = [min(_dist(ant, foe) for foe in _PIN_FOES) for ant in _PIN_MINE]
    assert dists == [4, 16]
    assert dists[0] < dists[1]
    trace: list[str] = []
    plan = FX.resolve_fight(
        _PIN_MINE,
        _PIN_FOES,
        [],
        ROWS,
        COLS,
        5,
        [],
        _dist,
        _dest,
        _pinned_passable(_PIN_BLOCKED),
        _allow,
        trace,
    )
    assert set(plan) == {0, 1}
    fixes = [entry for entry in trace if entry.startswith("fix")]
    assert [int(entry.split()[1]) for entry in fixes] == [0, 1]


def test_threat_order_tiebreak_is_stable() -> None:
    # Equal threat distances keep input order: two ants symmetric
    # about one foe pin 0 then 1.
    mine = [(5, 5), (5, 13)]
    foes = [(5, 9)]
    assert _dist(mine[0], foes[0]) == _dist(mine[1], foes[0]) == 4
    trace: list[str] = []
    plan = FX.resolve_fight(
        mine, foes, [], ROWS, COLS, 5, [], _dist, _dest, _allow, _allow, trace
    )
    assert set(plan) == {0, 1}
    fixes = [entry for entry in trace if entry.startswith("fix")]
    assert [int(entry.split()[1]) for entry in fixes] == [0, 1]


def test_no_contact_boards_byte_identical_to_base() -> None:
    # (b) enemies beyond SEEK_RANGE leave the fight plan empty, so
    # the turn is pure economy/explore: distant-enemy orders must
    # byte-match the no-enemy orders (and a second distant layout).
    mine = [(5, 5), (5, 8), (12, 12)]
    foods = [(5, 6), (11, 11)]
    far = [(19, 19)]
    assert all(_dist(a, e) > FX.SEEK_RANGE for a in mine for e in far)
    quiet, _ = run_turn(mine, [], foods)
    with_far, _ = run_turn(mine, far, foods)
    assert with_far == quiet
    farther, _ = run_turn(mine, [(0, 0)], foods)
    assert farther == quiet
    claim_free = cast(dict[int, Loc], dict.fromkeys(range(len(mine))))
    assert (
        FX.plan_fixing(
            mine,
            claim_free,
            far,
            [],
            ROWS,
            COLS,
            5,
            [],
            _dist,
            _dest,
            _allow,
            _allow,
        )
        == {}
    )


def test_full_turn_under_1s_crowded() -> None:
    # (d) 48 ants, 30 enemies, food, hills, guards: full turn <1 s.
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    many = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [((i * 3 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(12)]
    start = time.perf_counter()
    orders, _ = run_turn(
        mine,
        many,
        foods,
        enemy_hills=[(0, 0), (19, 19)],
        my_hills=[(10, 10), (3, 3)],
    )
    assert (time.perf_counter() - start) < 1.0
    assert len(orders) > 0
