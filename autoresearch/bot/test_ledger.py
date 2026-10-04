#!/usr/bin/env python
"""Ledger (spatial income bias) tests.

No engine games.

One change over champion Denial: food harvested per map quadrant is
counted over a trailing 100-turn window, and food-claim ties break
toward the richest quadrant. Distance still dominates: only
equal-distance claims reorder. With no harvest history the claim
order matches the champion exactly.
"""

import os
import sys
import time
from collections import deque
from collections.abc import Callable, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Ledger as LG  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20


def torus(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


def champion_assign(
    ants_list: list[Loc],
    foods: list[Loc],
    enemy_locs: list[Loc],
    distance: Callable[[Loc, Loc], int],
    rows: int,
    cols: int,
) -> dict[int, Loc]:
    """Pristine copy of champion Denial's greedy (no ledger tiebreak)."""
    target: dict[int, Loc] = {}
    if not foods or not ants_list:
        return target
    claimed: set[int] = set()
    denied: set[int] = set()
    for group in LG.denied_food_groups(foods, enemy_locs, distance, rows, cols):
        denied.update(group)
        picks = 0
        ordered = sorted(
            (distance(ant, foods[fi]), ai, fi)
            for ai, ant in enumerate(ants_list)
            for fi in group
        )
        for _, ai, fi in ordered:
            if picks >= LG.DENIAL_CLAIMS:
                break
            if ai not in target and fi not in claimed:
                target[ai] = foods[fi]
                claimed.add(fi)
                picks += 1
    pairs: list[tuple[int, int, int]] = []
    for ai, ant_loc in enumerate(ants_list):
        for fi, food_loc in enumerate(foods):
            pairs.append((distance(ant_loc, food_loc), ai, fi))
    pairs.sort()
    for _, ai, fi in pairs:
        if fi in denied:
            continue
        if ai not in target and fi not in claimed:
            target[ai] = foods[fi]
            claimed.add(fi)
    return target


def test_equal_distance_claims_prefer_richer_quadrant() -> None:
    ants = [(9, 9)]
    foods = [(9, 11), (9, 7)]  # both d=2; q1 vs q0
    assert torus(ants[0], foods[0]) == torus(ants[0], foods[1])
    assert LG.quadrant_of(foods[0], ROWS, COLS) == 1
    assert LG.quadrant_of(foods[1], ROWS, COLS) == 0
    rich_q1: list[int] = [0, 5, 0, 0]
    got = LG.assign_food_targets(ants, foods, [], torus, ROWS, COLS, rich_q1)
    assert got == {0: (9, 11)}
    rich_q0: list[int] = [5, 0, 0, 0]
    got = LG.assign_food_targets(ants, foods, [], torus, ROWS, COLS, rich_q0)
    assert got == {0: (9, 7)}


def test_denied_cluster_tiebreak_prefers_richer_quadrant() -> None:
    ants = [(9, 9)]
    foods = [(9, 11), (9, 7)]  # one cluster (d=4 <= 8)
    enemies = [(9, 9), (8, 10), (10, 10)]  # 3+ near -> contested
    assert LG.denied_food_groups(foods, enemies, torus, ROWS, COLS)
    rich_q1: list[int] = [0, 5, 0, 0]
    got = LG.assign_food_targets(ants, foods, enemies, torus, ROWS, COLS, rich_q1)
    assert got == {0: (9, 11)}


def test_nearer_food_in_poor_quadrant_still_wins() -> None:
    ants = [(9, 9)]
    foods = [(9, 8), (9, 13)]  # d=1 q0 (poor) vs d=4 q1 (rich)
    assert torus(ants[0], foods[0]) < torus(ants[0], foods[1])
    richness: list[int] = [0, 99, 0, 0]
    got = LG.assign_food_targets(ants, foods, [], torus, ROWS, COLS, richness)
    assert got == {0: (9, 8)}


def test_no_harvest_history_matches_champion_exactly() -> None:
    import random

    rng = random.Random(36)
    locs = [(r, c) for r in range(ROWS) for c in range(COLS)]
    for _ in range(300):
        n_ants = rng.randint(1, 6)
        n_food = rng.randint(1, 8)
        n_enemy = rng.randint(0, 5)
        pick = rng.sample(locs, n_ants + n_food + n_enemy)
        ants = pick[:n_ants]
        foods = pick[n_ants : n_ants + n_food]
        enemies = pick[n_ants + n_food :]
        ref = champion_assign(ants, foods, enemies, torus, ROWS, COLS)
        assert LG.assign_food_targets(ants, foods, enemies, torus, ROWS, COLS) == ref
        assert (
            LG.assign_food_targets(
                ants, foods, enemies, torus, ROWS, COLS, [0, 0, 0, 0]
            )
            == ref
        )
        assert (
            LG.assign_food_targets(ants, foods, enemies, torus, ROWS, COLS, None) == ref
        )


def test_quadrant_of_splits_map_into_four() -> None:
    assert LG.quadrant_of((0, 0), ROWS, COLS) == 0
    assert LG.quadrant_of((9, 9), ROWS, COLS) == 0
    assert LG.quadrant_of((0, 10), ROWS, COLS) == 1
    assert LG.quadrant_of((9, 19), ROWS, COLS) == 1
    assert LG.quadrant_of((10, 0), ROWS, COLS) == 2
    assert LG.quadrant_of((19, 9), ROWS, COLS) == 2
    assert LG.quadrant_of((10, 10), ROWS, COLS) == 3
    assert LG.quadrant_of((19, 19), ROWS, COLS) == 3


def test_ledger_counts_disappeared_food_per_quadrant() -> None:
    events: deque[tuple[int, int]] = deque()
    prev = {(1, 1), (1, 12), (15, 15)}
    cur = {(1, 12), (15, 15), (0, 0)}  # (1,1) harvested; (0,0) spawned
    LG.record_harvests(events, 1, prev, cur, ROWS, COLS)
    assert LG.quadrant_richness(events) == [1, 0, 0, 0]


def test_ledger_window_prunes_after_100_turns() -> None:
    events: deque[tuple[int, int]] = deque()
    LG.record_harvests(events, 5, {(1, 1)}, set(), ROWS, COLS)
    assert LG.quadrant_richness(events) == [1, 0, 0, 0]
    LG.record_harvests(events, 104, set(), set(), ROWS, COLS)
    assert LG.quadrant_richness(events) == [1, 0, 0, 0]
    LG.record_harvests(events, 105, set(), set(), ROWS, COLS)
    assert LG.quadrant_richness(events) == [0, 0, 0, 0]


def test_ledger_accumulates_across_turns() -> None:
    events: deque[tuple[int, int]] = deque()
    for turn in range(1, 6):
        food = (12 + turn, 12)  # quadrant 3, one per turn
        LG.record_harvests(events, turn, {food}, set(), ROWS, COLS)
    assert LG.quadrant_richness(events) == [0, 0, 0, 5]


def test_ledger_bookkeeping_costs_under_half_ms() -> None:
    events: deque[tuple[int, int]] = deque((t % 100, t % 4) for t in range(500))
    foods = [(r, c) for r in range(15) for c in range(10)]
    prev = set(foods[1:])
    cur = set(foods)
    richness: Sequence[int] | None = None
    start = time.perf_counter()
    reps = 200
    for t in range(reps):
        LG.record_harvests(events, 1000 + t, prev, cur, ROWS, COLS)
        richness = LG.quadrant_richness(events)
    elapsed = (time.perf_counter() - start) / reps
    assert richness is not None and sum(richness) >= 0
    assert elapsed < 0.0005
