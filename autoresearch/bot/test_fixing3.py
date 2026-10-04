#!/usr/bin/env python
"""Engage-gated sequential fixing (Fixing3): rear holds, contact fixes.

Fixing2 threat-orders the whole SEEK_RANGE population, so rear ants
press across the map into the scrum (best_move's press tiebreak) and
donate the crowd, and the hill rush starves because muster sits below
the fight plan. Fixing3 keeps threat-ordering but gates the fixing
population to engaged ants (nearest-enemy distance <= threat reach +
1): contact still commits first with full freedom, rear holds for
food / muster / explore instead of pressing into contact.

Self-contained: stdlib plus Fixing3 only. No combat.py import.

  (a) mid-range ants (inside SEEK_RANGE, outside engage range) are
      excluded from the fix plan, so the economy/muster keeps them.
  (b) contact-first order retained among engaged ants.
  (c) do_turn: a mid-range ant musters to the hill instead of
      pressing the foe.
  (d) no-contact boards byte-identical: distant enemies
      (>SEEK_RANGE) issue exactly the no-enemy orders.
  (e) duel shape still fights; crowd shape rear musters (sims).
  (f) full crowded turn under 1 s.
"""

import os
import sys
import time
from typing import cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Fixing3 as FX  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
R2 = 5
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
DIRS = ("n", "e", "s", "w")

# Engage range at R2=5: threat_reach (3) + 1.
ENGAGE = 4
MID = [(5, 5)]
MID_FOE = [(5, 10)]  # dist 5: inside SEEK_RANGE, outside engage


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


def run_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], FX.Fixing3]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = FX.Fixing3()
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


def _free_target(n: int) -> dict[int, Loc]:
    return cast(dict[int, Loc], dict.fromkeys(range(n)))


def test_entry_is_self_contained() -> None:
    assert FX.__name__ == "Fixing3"
    assert hasattr(FX, "Fixing3")
    with open(str(FX.__file__)) as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert "class Fixing3" in source
    bot_file = os.path.join(os.path.dirname(str(FX.__file__)), "Fixing3.bot")
    with open(bot_file) as handle:
        assert handle.read().strip() == "python Fixing3.py"


def test_mid_range_ants_excluded_from_fixing() -> None:
    # (a) dist 5 sits inside SEEK_RANGE but outside engage range:
    # the fixing population must hold the ant for economy/muster.
    assert _dist(MID[0], MID_FOE[0]) == 5
    assert _dist(MID[0], MID_FOE[0]) <= FX.SEEK_RANGE
    plan = FX.plan_fixing(
        MID,
        _free_target(1),
        MID_FOE,
        [],
        ROWS,
        COLS,
        R2,
        [],
        _dist,
        _dest,
        _allow,
        _allow,
    )
    assert plan == {}


def test_mixed_board_pins_contact_and_holds_rear() -> None:
    # Contact (dist 4, engaged) pins; rear (dist 16, mid-range)
    # holds out instead of pressing into the scrum.
    mine = [(5, 5), (15, 15)]
    foes = [(5, 9)]
    assert [_dist(a, foes[0]) for a in mine] == [4, 16]
    trace: list[str] = []
    plan = FX.resolve_fight(
        mine,
        foes,
        [],
        ROWS,
        COLS,
        R2,
        [],
        _dist,
        _dest,
        _allow,
        _allow,
        trace,
    )
    # resolve_fight is the unordered core; the gate lives in
    # plan_fixing, which is what do_turn uses.
    gated = FX.plan_fixing(
        mine,
        _free_target(2),
        foes,
        [],
        ROWS,
        COLS,
        R2,
        [],
        _dist,
        _dest,
        _allow,
        _allow,
        trace,
    )
    assert set(gated) == {0}
    assert plan  # core still threat-orders when asked directly


def test_contact_first_retained_among_engaged() -> None:
    # (b) two engaged ants (dists 3 and 4) still pin contact-first.
    mine = [(5, 6), (5, 13)]
    foes = [(5, 9)]
    assert [_dist(a, foes[0]) for a in mine] == [3, 4]
    assert all(d <= ENGAGE for d in (3, 4))
    trace: list[str] = []
    plan = FX.plan_fixing(
        mine,
        _free_target(2),
        foes,
        [],
        ROWS,
        COLS,
        R2,
        [],
        _dist,
        _dest,
        _allow,
        _allow,
        trace,
    )
    assert set(plan) == {0, 1}
    fixes = [entry for entry in trace if entry.startswith("fix")]
    assert [int(entry.split()[1]) for entry in fixes] == [0, 1]


def test_mid_range_ant_musters_to_hill() -> None:
    # (c) no food, hill west, foe east at dist 5: the ant musters
    # west instead of pressing east into the foe.
    orders, _ = run_turn(
        [(10, 10)],
        [(10, 15)],
        enemy_hills=[(10, 2)],
        my_hills=[],
    )
    assert orders == [((10, 10), "w")]


def test_no_contact_boards_byte_identical() -> None:
    # (d) enemies beyond SEEK_RANGE leave the turn pure
    # economy/explore: distant-enemy orders byte-match no-enemy.
    mine = [(5, 5), (5, 8), (12, 12)]
    foods = [(5, 6), (11, 11)]
    far = [(19, 19)]
    assert all(_dist(a, e) > FX.SEEK_RANGE for a in mine for e in far)
    quiet, _ = run_turn(mine, [], foods)
    with_far, _ = run_turn(mine, far, foods)
    assert with_far == quiet
    assert (
        FX.plan_fixing(
            mine,
            _free_target(len(mine)),
            far,
            [],
            ROWS,
            COLS,
            R2,
            [],
            _dist,
            _dest,
            _allow,
            _allow,
        )
        == {}
    )


# --- shape scenarios: crowd holds the rear, duel keeps the edge ---


def _sq(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


class SimAnts:
    """Minimal Ants surface over a mutable world."""

    def __init__(self, world: dict[str, list[Loc]]) -> None:
        self.world = world
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = R2
        self.orders: list[tuple[Loc, str]] = []

    def food(self) -> list[Loc]:
        return list(self.world["foods"])

    def my_ants(self) -> list[Loc]:
        return list(self.world["own"])

    def enemy_ants(self) -> list[tuple[Loc, int]]:
        return [(e, 1) for e in self.world["enemies"]]

    def enemy_hills(self) -> list[tuple[Loc, int]]:
        return [(h, 1) for h in self.world["foe_hills"]]

    def my_hills(self) -> list[Loc]:
        return list(self.world["own_hills"])

    def distance(self, a: Loc, b: Loc) -> int:
        return _dist(a, b)

    def destination(self, loc: Loc, direction: str) -> Loc:
        return _dest(loc, direction)

    def passable(self, loc: Loc) -> bool:
        return True

    def unoccupied(self, loc: Loc) -> bool:
        return loc not in self.world["own"] and loc not in self.world["enemies"]

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 100000


def _step_toward(loc: Loc, goal: Loc, blocked: set[Loc]) -> Loc:
    best = loc
    best_d: int | None = None
    for d in DIRS:
        dr, dc = AIM[d]
        nxt = ((loc[0] + dr) % ROWS, (loc[1] + dc) % COLS)
        if nxt in blocked:
            continue
        dd = abs(nxt[0] - goal[0]) + abs(nxt[1] - goal[1])
        if best_d is None or dd < best_d:
            best_d = dd
            best = nxt
    return best


def _run_world(world: dict[str, list[Loc]], turns: int) -> dict[str, list[Loc]]:
    bot = FX.Fixing3()
    for _ in range(turns):
        ants = SimAnts(world)
        bot.do_turn(ants)
        own = list(world["own"])
        for loc, d in ants.orders:
            if loc in own:
                own.remove(loc)
                dr, dc = AIM[d]
                own.append(((loc[0] + dr) % ROWS, (loc[1] + dc) % COLS))
        world["own"] = own
        blocked = set(world["own"]) | set(world["enemies"])
        moved: list[Loc] = []
        for loc in world["enemies"]:
            blocked.discard(loc)
            if world["own"]:
                goal = min(
                    world["own"],
                    key=lambda o: abs(o[0] - loc[0]) + abs(o[1] - loc[1]),
                )
            else:
                goal = world["own_hills"][0] if world["own_hills"] else (10, 10)
            nxt = _step_toward(loc, goal, blocked)
            blocked.add(nxt)
            moved.append(nxt)
        world["enemies"] = moved
        own, foe = (
            [
                o
                for o in world["own"]
                if not any(_sq(o, e) <= R2 for e in world["enemies"])
            ],
            [
                e
                for e in world["enemies"]
                if not any(_sq(e, o) <= R2 for o in world["own"])
            ],
        )
        world["own"] = own
        world["enemies"] = foe
        for h in list(world["foe_hills"]):
            if h in world["own"]:
                world["foe_hills"].remove(h)
        for h in list(world["own_hills"]):
            if h in world["enemies"]:
                world["own_hills"].remove(h)
    return world


def test_duel_shape_still_fights() -> None:
    # (e) 2v2 meeting engagement: engaged ants fix contact-first,
    # so the duel edge survives the gate. Floor measured on this
    # exact setup; must not regress.
    world = {
        "own": [(9, 6), (10, 6)],
        "enemies": [(9, 13), (10, 13)],
        "own_hills": [(10, 2)],
        "foe_hills": [(10, 17)],
        "foods": [],
    }
    start = time.perf_counter()
    end = _run_world(world, 40)
    elapsed = time.perf_counter() - start
    score = len(end["own"]) - len(end["enemies"])
    print(f"\nduel score={score} time={elapsed:.2f}s")
    assert elapsed < 10.0
    assert score >= 0


def test_crowd_shape_rear_musters_not_donates() -> None:
    # (e) contact plus two rear ants vs a 3-foe scrum with a far
    # foe hill and no home hill (no guard duty): the rear marches
    # on the hill (muster) instead of pressing into the scrum, so
    # the hill falls by turn 10. Base threat-ordering only gets
    # there by turn 12: its rear detours through the fight first.
    # Score = own alive + 2 per hill razed. Floors measured here.
    world = {
        "own": [(9, 6), (2, 2), (3, 2)],
        "enemies": [(9, 13), (10, 13), (8, 13)],
        "own_hills": [],
        "foe_hills": [(10, 17)],
        "foods": [],
    }
    start = time.perf_counter()
    end = _run_world(world, 10)
    elapsed = time.perf_counter() - start
    score = len(end["own"]) + 2 * (1 - len(end["foe_hills"]))
    print(
        f"\ncrowd score={score} own={len(end['own'])} hills={end['foe_hills']} time={elapsed:.2f}s"
    )
    assert elapsed < 10.0
    assert end["foe_hills"] == []
    assert score >= 5


def test_full_turn_under_1s_crowded() -> None:
    # (f) 48 ants, 30 enemies, food, hills, guards: full turn <1 s.
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
