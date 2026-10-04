#!/usr/bin/env python
"""Clock (optimal food assignment) tests. No engine games.

The one change over champion Denial: the greedy closest-pair-first
food assignment becomes the optimal min-total-distance assignment
(Hungarian over the ant-food cost matrix) whenever ants x foods <=
400 cells, else the exact legacy greedy; the solver is capped at
50ms with greedy fallback on timeout.
"""

import os
import sys
import time
from collections.abc import Callable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Clock  # noqa: E402
from Clock import _CLOCK_BUDGET_S as BUDGET  # noqa: E402
from Clock import _GATE_CELLS as GATE  # noqa: E402
from Clock import assign_food_targets  # noqa: E402

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]


def _torus(rows: int, cols: int) -> DistFn:
    def dist(a: Loc, b: Loc) -> int:
        return min(abs(a[0] - b[0]), rows - abs(a[0] - b[0])) + min(
            abs(a[1] - b[1]), cols - abs(a[1] - b[1])
        )

    return dist


def _legacy_greedy(
    ants_list: list[Loc], foods: list[Loc], dist: DistFn
) -> dict[int, Loc]:
    # Byte-exact copy of the champion's greedy loop (no denial: tests
    # pass no enemies, so the denied set is empty).
    pairs: list[tuple[int, int, int]] = []
    for ai, ant_loc in enumerate(ants_list):
        for fi, food_loc in enumerate(foods):
            pairs.append((dist(ant_loc, food_loc), ai, fi))
    pairs.sort()
    target: dict[int, Loc] = {}
    claimed: set[int] = set()
    for _, ai, fi in pairs:
        if ai not in target and fi not in claimed:
            target[ai] = foods[fi]
            claimed.add(fi)
    return target


def _total(target: dict[int, Loc], ants_list: list[Loc], dist: DistFn) -> int:
    inv = {v: k for k, v in target.items()}
    s = 0
    for ai, food in target.items():
        s += dist(ants_list[ai], food)
    assert len(inv) == len(target)
    return s


def test_gate_is_400_cells_and_budget_is_50ms():
    assert GATE == 400
    assert BUDGET == 0.05


def test_optimal_beats_greedy_on_crossover_layout():
    # 3v3 cost crossover: greedy grabs the cheap (ant0, food0)=1,
    # stranding ant1 on food1=100 (total 103); optimal is 2+2+2=6.
    costs = {
        (0, 0): 1,
        (0, 1): 2,
        (0, 2): 100,
        (1, 0): 2,
        (1, 1): 100,
        (1, 2): 3,
        (2, 0): 100,
        (2, 1): 3,
        (2, 2): 2,
    }
    ants_list: list[Loc] = [(0, 0), (0, 1), (0, 2)]
    foods: list[Loc] = [(1, 0), (1, 1), (1, 2)]

    def dist(a: Loc, b: Loc) -> int:
        return costs[(ants_list.index(a), foods.index(b))]

    got = assign_food_targets(ants_list, foods, [], dist, 10, 10)
    greedy = _legacy_greedy(ants_list, foods, dist)
    assert _total(greedy, ants_list, dist) == 103
    assert _total(got, ants_list, dist) == 6
    assert _total(got, ants_list, dist) < _total(greedy, ants_list, dist)


def test_big_board_routes_to_greedy_byte_identical():
    # 21 ants x 20 foods = 420 cells > 400 gate: exact legacy orders.
    rows, cols = 30, 30
    dist = _torus(rows, cols)
    ants_list = [(i, 0) for i in range(21)]
    foods = [(i, 15) for i in range(20)]
    got = assign_food_targets(ants_list, foods, [], dist, rows, cols)
    assert got == _legacy_greedy(ants_list, foods, dist)


def test_timeout_fallback_preserves_greedy_orders():
    # Small board (under gate) but zero budget forces the solver to
    # time out: orders must equal the legacy greedy exactly.
    costs = {
        (0, 0): 1,
        (0, 1): 2,
        (0, 2): 100,
        (1, 0): 2,
        (1, 1): 100,
        (1, 2): 3,
        (2, 0): 100,
        (2, 1): 3,
        (2, 2): 2,
    }
    ants_list: list[Loc] = [(0, 0), (0, 1), (0, 2)]
    foods: list[Loc] = [(1, 0), (1, 1), (1, 2)]

    def dist(a: Loc, b: Loc) -> int:
        return costs[(ants_list.index(a), foods.index(b))]

    old = Clock._CLOCK_BUDGET_S
    Clock._CLOCK_BUDGET_S = 0.0
    try:
        got = assign_food_targets(ants_list, foods, [], dist, 10, 10)
    finally:
        Clock._CLOCK_BUDGET_S = old
    assert got == _legacy_greedy(ants_list, foods, dist)


def test_solver_stays_under_50ms_on_20v20():
    # 20 ants x 20 foods = 400 cells: inside the gate, optimal path,
    # still under the 50ms solver cap end to end.
    rows, cols = 40, 40
    dist = _torus(rows, cols)
    ants_list = [(i, i) for i in range(20)]
    foods = [(i, 39 - i) for i in range(20)]
    start = time.perf_counter()
    got = assign_food_targets(ants_list, foods, [], dist, rows, cols)
    elapsed = time.perf_counter() - start
    assert len(got) == 20
    assert elapsed < 0.05
