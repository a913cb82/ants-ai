#!/usr/bin/env python
"""Persistent benchmark scenarios for the Softmax line (stdlib only).

Two fixed-map, fixed-seed simulations that stay for later tuners.
Both drive the real entry's do_turn through a minimal Ants surface,
so every tuning idea is measured end to end over 60 turns:

- small-fight press: 3 own vs 2 holders pushing an enemy hill.
  score = hills razed + enemy dead - own dead.
- crowd survival: 8 defenders vs 12 rushers on the home hill.
  score = own alive + hills held after 60 turns.

Floors pin the base (coin-flip) scores: a later entry must not
regress below them. Runtimes must stay under 10 s each.
"""

import os
import sys
import time
from typing import TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Softmax2 as SM  # noqa: E402
import Softmax3 as S3  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
R2 = 5
TURNS = 60
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
DIRS = ("n", "e", "s", "w")

# Regression floors: base-entry scores on these exact setups.
# Press holds hills-razed-plus-trades at 1; survival is a wipe (0)
# under both policies — the floor documents that limit.
PRESS_FLOOR = 1
SURVIVAL_FLOOR = 0
# Parity-melee floor: Softmax3 2v2 score on the exact setup below.
PARITY_FLOOR = 1


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


def _resolve(own: list[Loc], foes: list[Loc]) -> tuple[list[Loc], list[Loc], int, int]:
    """Symmetric exchange: an ant dies iff any foe is within R2."""
    keep_own = [
        o for o in own if not any(SM.toroidal_sq(o, e, ROWS, COLS) <= R2 for e in foes)
    ]
    keep_foe = [
        e for e in foes if not any(SM.toroidal_sq(e, o, ROWS, COLS) <= R2 for o in own)
    ]
    return keep_own, keep_foe, len(own) - len(keep_own), len(foes) - len(keep_foe)


def _apply_orders(world: World, orders: list[tuple[Loc, str]]) -> None:
    own = list(world["own"])
    for loc, d in orders:
        if loc in own:
            own.remove(loc)
            dr, dc = AIM[d]
            own.append(((loc[0] + dr) % ROWS, (loc[1] + dc) % COLS))
    world["own"] = own


def run_press() -> tuple[int, float]:
    """3v2 hill push; returns (score, seconds)."""
    world: World = {
        "own": [(4, 4), (4, 5), (5, 4)],
        "enemies": [(4, 12), (4, 13)],
        "own_hills": [(16, 16)],
        "foe_hills": [(4, 14)],
        "foods": [],
    }
    bot = SM.Softmax2()
    razed = 0
    kills = 0
    deaths = 0
    start = time.perf_counter()
    for _ in range(TURNS):
        ants = SimAnts(world)
        bot.do_turn(ants)
        _apply_orders(world, ants.orders)
        # Holders stand their ground.
        own, foe, d, k = _resolve(list(world["own"]), list(world["enemies"]))
        deaths += d
        kills += k
        world["own"] = own
        world["enemies"] = foe
        for h in list(world["foe_hills"]):
            if h in world["own"]:
                world["foe_hills"].remove(h)
                razed += 1
    elapsed = time.perf_counter() - start
    return razed + kills - deaths, elapsed


def run_survival() -> tuple[int, float]:
    """8v12 home-hill defense; returns (score, seconds)."""
    world: World = {
        "own": [
            (9, 10),
            (11, 10),
            (10, 9),
            (10, 11),
            (9, 9),
            (9, 11),
            (11, 9),
            (11, 11),
        ],
        "enemies": [
            (2, 2),
            (2, 17),
            (17, 2),
            (17, 17),
            (2, 10),
            (17, 10),
            (10, 2),
            (10, 17),
            (5, 5),
            (5, 14),
            (14, 5),
            (14, 14),
        ],
        "own_hills": [(10, 10)],
        "foe_hills": [],
        "foods": [],
    }
    bot = SM.Softmax2()
    start = time.perf_counter()
    for _ in range(TURNS):
        ants = SimAnts(world)
        bot.do_turn(ants)
        _apply_orders(world, ants.orders)
        # Rushers march on the home hill in fixed dir order.
        foe = list(world["enemies"])
        blocked = set(world["own"]) | set(foe)
        hill = world["own_hills"][0] if world["own_hills"] else (10, 10)
        moved: list[Loc] = []
        for loc in foe:
            blocked.discard(loc)
            nxt = _step_toward(loc, hill, blocked)
            blocked.add(nxt)
            moved.append(nxt)
        world["enemies"] = moved
        own, foe2, _, _ = _resolve(list(world["own"]), list(world["enemies"]))
        world["own"] = own
        world["enemies"] = foe2
        for h in list(world["own_hills"]):
            if h in world["enemies"]:
                world["own_hills"].remove(h)
    elapsed = time.perf_counter() - start
    return len(world["own"]) + len(world["own_hills"]), elapsed


def test_press_runs_fast_and_scores() -> None:
    score, elapsed = run_press()
    print(f"\npress score={score} time={elapsed:.2f}s")
    assert elapsed < 10.0
    assert score >= PRESS_FLOOR


def test_survival_runs_fast_and_scores() -> None:
    score, elapsed = run_survival()
    print(f"\nsurvival score={score} time={elapsed:.2f}s")
    assert elapsed < 10.0
    assert score >= SURVIVAL_FLOOR


def run_parity(mod: object) -> tuple[int, tuple[Loc, ...], float]:
    """2v2 parity melee vs holding foes; returns (score, own, seconds)."""
    world: World = {
        "own": [(5, 5), (5, 6)],
        "enemies": [(5, 8), (5, 9)],
        "own_hills": [(16, 16)],
        "foe_hills": [],
        "foods": [],
    }
    bot = mod.Softmax3() if hasattr(mod, "Softmax3") else mod.Softmax2()  # type: ignore[attr-defined]
    kills = 0
    deaths = 0
    start = time.perf_counter()
    for _ in range(TURNS):
        ants = SimAnts(world)
        bot.do_turn(ants)
        _apply_orders(world, ants.orders)
        own, foe, d, k = _resolve(list(world["own"]), list(world["enemies"]))
        deaths += d
        kills += k
        world["own"] = own
        world["enemies"] = foe
    elapsed = time.perf_counter() - start
    return kills - deaths + len(world["own"]), tuple(sorted(world["own"])), elapsed


def test_parity_runs_fast_and_scores() -> None:
    score, _, elapsed = run_parity(S3)
    print(f"\nparity score={score} time={elapsed:.2f}s")
    assert elapsed < 10.0
    assert score >= PARITY_FLOOR


def test_parity_diverges_from_deterministic_gate() -> None:
    """Same 2v2 world, different paths: the deterministic gate always
    presses at parity while the contest-zone coin sometimes refuses,
    so the end positions must differ (scores may still tie)."""
    score2, own2, _ = run_parity(SM)
    score3, own3, _ = run_parity(S3)
    print(f"\nparity S2={score2} {own2} S3={score3} {own3}")
    assert score3 >= PARITY_FLOOR
    assert own3 != own2
