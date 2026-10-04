#!/usr/bin/env python
"""Persistent benchmark scenarios for the Fixing line (stdlib only).

Two fixed-map, deterministic simulations that stay for later tuners.
Both drive the real Fixing2 entry's do_turn through a minimal Ants
surface, so every tuning idea is measured end to end:

- duel shape: 2 own vs 2 foes, symmetric meeting engagement.
  score = own alive - enemy alive after 40 turns.
- ffa shape: 6-way symmetric ring (own + 5 foe factions), one hill
  per faction. score = own hills held + own ants alive after
  60 turns (rank vs the 5 foe totals also reported).

Floors pin the Fixing2 scores: a later entry must not regress below
them. Runtimes must stay under 10 s each.
"""

import os
import sys
import time
from typing import TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Fixing2 as FX  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
R2 = 5
DUEL_TURNS = 40
FFA_TURNS = 60
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
DIRS = ("n", "e", "s", "w")

# Regression floors: measured Fixing2 scores on these exact setups.
DUEL_FLOOR = 0
FFA_FLOOR = 2
# 5v5 head-on line battle (see run_line_battle below).
LINE_FLOOR = 0


class World(TypedDict):
    own: list[Loc]
    enemies: list[Loc]
    own_hills: list[Loc]
    foe_hills: list[Loc]
    foods: list[Loc]


class SimAnts:
    """Minimal Ants surface over a mutable world."""

    def __init__(self, world: World) -> None:
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
        dr = abs(a[0] - b[0])
        dr = min(dr, self.rows - dr)
        dc = abs(a[1] - b[1])
        dc = min(dc, self.cols - dc)
        return dr + dc

    def destination(self, loc: Loc, direction: str) -> Loc:
        dr, dc = AIM[direction]
        return ((loc[0] + dr) % self.rows, (loc[1] + dc) % self.cols)

    def passable(self, loc: Loc) -> bool:
        return True

    def unoccupied(self, loc: Loc) -> bool:
        return loc not in self.world["own"] and loc not in self.world["enemies"]

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 100000


def _sq(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


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


def _resolve(own: list[Loc], foes: list[Loc]) -> tuple[list[Loc], list[Loc]]:
    """Symmetric exchange: an ant dies iff any foe is within R2."""
    keep_own = [o for o in own if not any(_sq(o, e) <= R2 for e in foes)]
    keep_foe = [e for e in foes if not any(_sq(e, o) <= R2 for o in own)]
    return keep_own, keep_foe


def _apply_orders(world: World, orders: list[tuple[Loc, str]]) -> None:
    own = list(world["own"])
    for loc, d in orders:
        if loc in own:
            own.remove(loc)
            dr, dc = AIM[d]
            own.append(((loc[0] + dr) % ROWS, (loc[1] + dc) % COLS))
    world["own"] = own


def _move_foes(world: World) -> None:
    foe = list(world["enemies"])
    blocked = set(world["own"]) | set(foe)
    moved: list[Loc] = []
    for loc in foe:
        blocked.discard(loc)
        if world["own"]:
            goal = min(
                world["own"], key=lambda o: abs(o[0] - loc[0]) + abs(o[1] - loc[1])
            )
        else:
            goal = world["own_hills"][0] if world["own_hills"] else (10, 10)
        nxt = _step_toward(loc, goal, blocked)
        blocked.add(nxt)
        moved.append(nxt)
    world["enemies"] = moved


def run_duel() -> tuple[int, float]:
    """2v2 symmetric meeting engagement; returns (score, seconds)."""
    world: World = {
        "own": [(9, 6), (10, 6)],
        "enemies": [(9, 13), (10, 13)],
        "own_hills": [(10, 2)],
        "foe_hills": [(10, 17)],
        "foods": [],
    }
    bot = FX.Fixing2()
    start = time.perf_counter()
    for _ in range(DUEL_TURNS):
        ants = SimAnts(world)
        bot.do_turn(ants)
        _apply_orders(world, ants.orders)
        _move_foes(world)
        own, foe = _resolve(list(world["own"]), list(world["enemies"]))
        world["own"] = own
        world["enemies"] = foe
        for h in list(world["foe_hills"]):
            if h in world["own"]:
                world["foe_hills"].remove(h)
        for h in list(world["own_hills"]):
            if h in world["enemies"]:
                world["own_hills"].remove(h)
    elapsed = time.perf_counter() - start
    return len(world["own"]) - len(world["enemies"]), elapsed


def run_ffa() -> tuple[int, int, float]:
    """6-way symmetric ring; returns (score, rank, seconds).

    Score is own hills held + own ants alive; rank orders own total
    against the 5 foe faction totals (1 is best).
    """
    starts = [(10, 3), (10, 16), (3, 10), (16, 10), (4, 4), (15, 15)]
    hills = [(10, 2), (10, 17), (2, 10), (17, 10), (3, 3), (16, 16)]
    factions: list[list[Loc]] = [[s, ((s[0] + 1) % ROWS, s[1])] for s in starts]
    faction_hills: list[Loc] = list(hills)
    world: World = {
        "own": list(factions[0]),
        "enemies": [a for f in factions[1:] for a in f],
        "own_hills": [faction_hills[0]],
        "foe_hills": list(faction_hills[1:]),
        "foods": [],
    }
    foe_factions: list[list[Loc]] = [list(f) for f in factions[1:]]
    bot = FX.Fixing2()
    start = time.perf_counter()
    for _ in range(FFA_TURNS):
        ants = SimAnts(world)
        bot.do_turn(ants)
        _apply_orders(world, ants.orders)
        # Each foe faction steps its ants toward the nearest non-self ant.
        all_ants = [world["own"]] + foe_factions
        flat = [a for f in all_ants for a in f]
        blocked = set(flat)
        for fi, fac in enumerate(foe_factions):
            moved: list[Loc] = []
            for loc in fac:
                blocked.discard(loc)
                others = [a for a in flat if a not in fac]
                goal = (
                    min(others, key=lambda o: abs(o[0] - loc[0]) + abs(o[1] - loc[1]))
                    if others
                    else (10, 10)
                )
                nxt = _step_toward(loc, goal, blocked)
                blocked.add(nxt)
                moved.append(nxt)
            foe_factions[fi] = moved
        world["enemies"] = [a for f in foe_factions for a in f]
        # Symmetric combat across all factions.
        flat_now = [world["own"]] + foe_factions
        flat_all = [a for f in flat_now for a in f]
        survivors: list[list[Loc]] = []
        for fac in flat_now:
            keep = [
                a
                for a in fac
                if not any(o not in fac and _sq(a, o) <= R2 for o in flat_all)
            ]
            survivors.append(keep)
        world["own"] = survivors[0]
        foe_factions = survivors[1:]
        world["enemies"] = [a for f in foe_factions for a in f]
        for h in list(world["foe_hills"]):
            if h in world["own"]:
                world["foe_hills"].remove(h)
        if world["own_hills"] and world["own_hills"][0] in world["enemies"]:
            world["own_hills"] = []
    elapsed = time.perf_counter() - start
    score = len(world["own"]) + len(world["own_hills"])
    foe_totals = [len(f) for f in foe_factions]
    # Foe hills: survivors standing on a foe hill count as held by
    # that faction; approximate with ants only (hills razed when
    # overrun are gone from the board, same as duel).
    rank = 1 + sum(1 for t in foe_totals if t > score)
    return score, rank, elapsed


def test_duel_runs_fast_and_scores() -> None:
    score, elapsed = run_duel()
    print(f"\nduel score={score} time={elapsed:.2f}s")
    assert elapsed < 10.0
    assert score >= DUEL_FLOOR


def test_ffa_runs_fast_and_scores() -> None:
    score, rank, elapsed = run_ffa()
    print(f"\nffa score={score} rank={rank} time={elapsed:.2f}s")
    assert elapsed < 10.0
    assert score >= FFA_FLOOR


def run_line_battle(bot_cls: type, turns: int = 40) -> tuple[int, float]:
    """5v5 head-on line battle; returns (own-alive minus foe-alive, seconds).

    Takes any bot class with a no-arg constructor and do_turn, so
    later entries compare against the Fixing2 floor without copying
    this file. Crowd shape: two full lines meet head-on, which
    stresses whether the commit step keeps the line together
    (backed SAFE) or collapses into piecemeal 1v1s (press-only).
    """
    world: World = {
        "own": [(r, 6) for r in range(8, 13)],
        "enemies": [(r, 13) for r in range(8, 13)],
        "own_hills": [(10, 2)],
        "foe_hills": [(10, 17)],
        "foods": [],
    }
    bot = bot_cls()
    start = time.perf_counter()
    for _ in range(turns):
        ants = SimAnts(world)
        bot.do_turn(ants)
        _apply_orders(world, ants.orders)
        _move_foes(world)
        own, foe = _resolve(list(world["own"]), list(world["enemies"]))
        world["own"] = own
        world["enemies"] = foe
        for h in list(world["foe_hills"]):
            if h in world["own"]:
                world["foe_hills"].remove(h)
        for h in list(world["own_hills"]):
            if h in world["enemies"]:
                world["own_hills"].remove(h)
    elapsed = time.perf_counter() - start
    return len(world["own"]) - len(world["enemies"]), elapsed


def test_line_battle_runs_fast_and_scores() -> None:
    score, elapsed = run_line_battle(FX.Fixing2)
    print(f"\nline-battle score={score} time={elapsed:.2f}s")
    assert elapsed < 10.0
    assert score >= LINE_FLOOR
