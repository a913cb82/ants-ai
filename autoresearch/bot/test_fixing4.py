#!/usr/bin/env python
"""Standing-support commit (Fixing4): leaders fight with the line behind them.

Fixing2's threat-order pins contact ants first, but the support map
starts empty: the leader judges every square alone, so its forward
step reads KILL and it sidesteps while the rear routes around it --
the crowd collapses into piecemeal 1v1s. Fixing4 seeds the commit
with standing backing (every not-yet-pinned combat ant's current
attack disc) and ranks SAFE steps by most-backed first, pressing
toward the enemy only on ties. Population screen unchanged from
Fixing2 (claim-free ants with an enemy in SEEK_RANGE; no engage
gate, no who-fixes variants).

Self-contained: stdlib plus Fixing4 only.

  (a) leader advances backed where Fixing2 sidesteps: 2 own
      ((10,10),(10,11)) vs foe (10,14); Fixing2 pins the leader 'n',
      Fixing4 pins it 'e' (backed SAFE).
  (b) backed SAFE beats pressing SAFE: one ant, two SAFE steps, the
      farther-from-foe step backed -- Fixing4 takes the backed step,
      Fixing2 presses.
  (c) threat order kept: contact still fixes before rear.
  (d) no-contact boards byte-identical: distant enemies
      (>SEEK_RANGE) issue exactly the no-enemy orders.
  (e) full crowded turn under 1 s.
"""

import os
import sys
import time
from typing import cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Fixing2 as BASE  # noqa: E402
import Fixing4 as FX  # noqa: E402
import test_scenarios_fixing as SCN  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], FX.Fixing4]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = FX.Fixing4()
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


def _allow(loc: Loc) -> bool:
    return True


def test_entry_is_self_contained() -> None:
    assert FX.__name__ == "Fixing4"
    assert hasattr(FX, "Fixing4")
    with open(str(FX.__file__)) as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert "class Fixing4" in source
    bot_file = os.path.join(os.path.dirname(str(FX.__file__)), "Fixing4.bot")
    with open(bot_file) as handle:
        assert handle.read().strip() == "python Fixing4.py"


def test_leader_advances_backed_where_base_sidesteps() -> None:
    # (a) pair ((10,10),(10,11)) meets foe (10,14): the leader's
    # forward step (10,12) faces influence 1 with no pinned support,
    # so Fixing2 reads KILL and sidesteps 'n'; Fixing4 counts the
    # rear ant's standing disc and reads backed SAFE, pinning 'e'.
    mine = [(10, 10), (10, 11)]
    foes = [(10, 14)]
    base_plan = BASE.resolve_fight(
        mine, foes, [], ROWS, COLS, 5, [], _dist, _dest, _allow, _allow
    )
    assert base_plan[1] == "n", f"base must sidestep, got {base_plan}"
    plan = FX.resolve_fight(
        mine, foes, [], ROWS, COLS, 5, [], _dist, _dest, _allow, _allow
    )
    assert plan[1] == "e", f"standing backing must advance, got {plan}"


def test_backed_safe_beats_pressing_safe() -> None:
    # (b) ant (10,10), foe north (4,10): 'n'->(9,10) presses
    # (dist 5) while 'e'->(10,11) loiters (dist 7). Both far
    # outside influence (SAFE). Backing only on 'e'. Fixing2 must
    # press 'n'; Fixing4 must take backed 'e'.
    ant = (10, 10)
    foes = [(4, 10)]
    field = FX.influence_field(foes, ROWS, COLS, FX.threat_reach(5))
    support = {(10, 11): 1}
    assert FX.classify_step(field, (9, 10), 0) == "SAFE"
    assert FX.classify_step(field, (10, 11), 1) == "SAFE"
    assert _dist((9, 10), foes[0]) < _dist((10, 11), foes[0])
    base_move = BASE.best_move(
        ant, field, support, [], foes, _dist, _dest, _allow, _allow
    )
    assert base_move == "n", f"base must press, got {base_move}"
    move = FX.best_move(ant, field, support, [], foes, _dist, _dest, _allow, _allow)
    assert move == "e", f"backing must outrank press, got {move}"


def test_threat_order_kept_contact_before_rear() -> None:
    # (c) same pinned board as Fixing2: rear boxed to 1 move, contact
    # open; contact (dist 4) must still pin before rear (dist 16).
    mine = [(5, 5), (15, 15)]
    foes = [(5, 9)]
    blocked = {(14, 15), (15, 16), (16, 15)}
    allow = lambda loc: loc not in blocked  # noqa: E731
    trace: list[str] = []
    plan = FX.resolve_fight(
        mine, foes, [], ROWS, COLS, 5, [], _dist, _dest, allow, _allow, trace
    )
    assert set(plan) == {0, 1}
    fixes = [entry for entry in trace if entry.startswith("fix")]
    assert [int(entry.split()[1]) for entry in fixes] == [0, 1]


def test_no_contact_boards_byte_identical_to_base() -> None:
    # (d) enemies beyond SEEK_RANGE leave the fight plan empty, so
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


def test_full_turn_under_1s_crowded() -> (
    None
):  # (e) 48 ants, 30 enemies, food, hills, guards: full turn <1 s.
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


def test_line_battle_holds_line_better_than_base() -> None:
    # (f) end-to-end crowd: 5v5 head-on lines. Standing backing must
    # not regress below the Fixing2 line; measured Fixing4 +1 vs
    # Fixing2 0 (line steps together instead of diving piecemeal).
    base_score, _ = SCN.run_line_battle(BASE.Fixing2)
    score, elapsed = SCN.run_line_battle(FX.Fixing4)
    print(f"\nline-battle base={base_score} fixing4={score}")
    assert elapsed < 10.0
    assert score >= base_score
