#!/usr/bin/env python
"""Quartermaster food-triage tests. No engine games.

One change over champion Denial: triage by ant/food ratio. Food-rich
(visible food >= 2x ants) claims only foods within TRIAGE_RANGE steps;
ant-rich (ants > foods) sends unassigned extras to contest the nearest
enemy-held food instead of idling. At parity the code path is the
champion greedy untouched, so the oracle below (a verbatim copy of the
champion assignment) must match exactly.
"""

import os
import sys
import time
from collections.abc import Callable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Quartermaster  # noqa: E402

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]

ROWS = 100
COLS = 100


def make_distance(rows: int, cols: int) -> DistFn:
    def distance(a: Loc, b: Loc) -> int:
        dr = abs(a[0] - b[0])
        dr = min(dr, rows - dr)
        dc = abs(a[1] - b[1])
        dc = min(dc, cols - dc)
        return dr + dc

    return distance


DIST = make_distance(ROWS, COLS)

# Verbatim champion oracle (base assign_food_targets plus its helpers).
_CHAMP_R = 8
_CHAMP_ENEMIES = 3
_CHAMP_CLAIMS = 2
_CHAMP_CELL = _CHAMP_R + 1


def _champ_scan(
    foods: list[Loc], enemy_locs: list[Loc], rows: int, cols: int
) -> tuple[list[int], dict[int, int]]:
    n = len(foods)
    cell = _CHAMP_CELL
    fr = [f[0] for f in foods]
    fc = [f[1] for f in foods]
    buckets: dict[tuple[int, int], list[int]] = {}
    for i in range(n):
        buckets.setdefault((fr[i] // cell, fc[i] // cell), []).append(i)
    parent = list(range(n))

    def union(a: int, b: int) -> None:
        ra, rb = a, b
        while parent[ra] != ra:
            parent[ra] = parent[parent[ra]]
            ra = parent[ra]
        while parent[rb] != rb:
            parent[rb] = parent[parent[rb]]
            rb = parent[rb]
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    R = _CHAMP_R
    for key, members in buckets.items():
        br, bc = key
        for dbr, dbc in ((0, 0), (0, 1), (1, -1), (1, 0), (1, 1)):
            others = buckets.get((br + dbr, bc + dbc))
            if not others:
                continue
            inner = dbr == 0 and dbc == 0
            for ii, i in enumerate(members):
                ri = fr[i]
                ci = fc[i]
                group_b = members[ii + 1 :] if inner else others
                for j in group_b:
                    dr = ri - fr[j]
                    if dr < 0:
                        dr = -dr
                    if dr > R:
                        continue
                    dc = ci - fc[j]
                    if dc < 0:
                        dc = -dc
                    if dc > R:
                        continue
                    if dr + dc <= R:
                        union(i, j)
    row_top = [i for i in range(n) if fr[i] <= _CHAMP_R]
    row_bot = [i for i in range(n) if fr[i] >= rows - _CHAMP_R]
    for i in row_top:
        for j in row_bot:
            if i == j:
                continue
            dr = fr[i] - fr[j]
            if dr < 0:
                dr = -dr
            if dr > rows - dr:
                dr = rows - dr
            if dr > R:
                continue
            dc = fc[i] - fc[j]
            if dc < 0:
                dc = -dc
            if dc > cols - dc:
                dc = cols - dc
            if dr + dc <= R:
                union(i, j)
    col_left = [i for i in range(n) if fc[i] <= _CHAMP_R]
    col_right = [i for i in range(n) if fc[i] >= cols - _CHAMP_R]
    for i in col_left:
        for j in col_right:
            if i == j:
                continue
            dr = fr[i] - fr[j]
            if dr < 0:
                dr = -dr
            if dr > rows - dr:
                dr = rows - dr
            if dr > R:
                continue
            dc = fc[i] - fc[j]
            if dc < 0:
                dc = -dc
            if dc > cols - dc:
                dc = cols - dc
            if dr + dc <= R:
                union(i, j)
    roots = [0] * n
    for i in range(n):
        a = i
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        roots[i] = a
    counts: dict[int, int] = {}
    for e in enemy_locs:
        er = e[0]
        ec = e[1]
        br, bc = er // cell, ec // cell
        hit: set[int] = set()
        for dbr in (-1, 0, 1):
            for dbc in (-1, 0, 1):
                nearby = buckets.get((br + dbr, bc + dbc))
                if not nearby:
                    continue
                for j in nearby:
                    dr = er - fr[j]
                    if dr < 0:
                        dr = -dr
                    if dr > rows - dr:
                        dr = rows - dr
                    if dr > R:
                        continue
                    dc = ec - fc[j]
                    if dc < 0:
                        dc = -dc
                    if dc > cols - dc:
                        dc = cols - dc
                    if dr + dc <= R:
                        hit.add(roots[j])
        if er <= R or er >= rows - R:
            for j in row_top + row_bot:
                dr = er - fr[j]
                if dr < 0:
                    dr = -dr
                if dr > rows - dr:
                    dr = rows - dr
                if dr > R:
                    continue
                dc = ec - fc[j]
                if dc < 0:
                    dc = -dc
                if dc > cols - dc:
                    dc = cols - dc
                if dr + dc <= R:
                    hit.add(roots[j])
        if ec <= R or ec >= cols - R:
            for j in col_left + col_right:
                dr = er - fr[j]
                if dr < 0:
                    dr = -dr
                if dr > rows - dr:
                    dr = rows - dr
                if dr > R:
                    continue
                dc = ec - fc[j]
                if dc < 0:
                    dc = -dc
                if dc > cols - dc:
                    dc = cols - dc
                if dr + dc <= R:
                    hit.add(roots[j])
        for root in hit:
            counts[root] = counts.get(root, 0) + 1
    return roots, counts


def _champ_groups(
    foods: list[Loc],
    enemy_locs: list[Loc],
    distance: DistFn,
    rows: int,
    cols: int,
) -> list[list[int]]:
    if not foods or len(enemy_locs) < _CHAMP_ENEMIES:
        return []
    roots, counts = _champ_scan(foods, enemy_locs, rows, cols)
    contested = {r for r, c in counts.items() if c >= _CHAMP_ENEMIES}
    groups: dict[int, list[int]] = {}
    for i, root in enumerate(roots):
        if root in contested:
            groups.setdefault(root, []).append(i)
    return list(groups.values())


def champ_assign(
    ants_list: list[Loc],
    foods: list[Loc],
    enemy_locs: list[Loc],
    distance: DistFn,
    rows: int,
    cols: int,
) -> dict[int, Loc]:
    target: dict[int, Loc] = {}
    if not foods or not ants_list:
        return target
    claimed: set[int] = set()
    denied: set[int] = set()
    for group in _champ_groups(foods, enemy_locs, distance, rows, cols):
        denied.update(group)
        picks = 0
        ordered = sorted(
            (distance(ant, foods[fi]), ai, fi)
            for ai, ant in enumerate(ants_list)
            for fi in group
        )
        for _, ai, fi in ordered:
            if picks >= _CHAMP_CLAIMS:
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


def call_bot(
    ants_list: list[Loc], foods: list[Loc], enemy_locs: list[Loc]
) -> dict[int, Loc]:
    return Quartermaster.assign_food_targets(
        ants_list, foods, enemy_locs, DIST, ROWS, COLS
    )


def test_rich_board_drops_far_foods() -> None:
    # 2 ants, 6 foods (3:1 food-rich): only the near food is claimed.
    ants = [(10, 10), (80, 80)]
    near: Loc = (12, 10)
    far: list[Loc] = [(50, 50), (52, 50), (50, 52), (30, 70), (70, 30)]
    for f in [near, *far]:
        assert min(DIST(a, f) for a in ants) <= 15 or f in far
    assert min(DIST(a, near) for a in ants) == 2
    assert all(min(DIST(a, f) for a in ants) > 15 for f in far)
    foods = [near, *far]
    got = call_bot(ants, foods, [])
    assert set(got.values()) == {near}
    # The champion would have sent the second ant on a long trip.
    champ = champ_assign(ants, foods, [], DIST, ROWS, COLS)
    assert len(champ) == 2
    assert any(v in far for v in champ.values())


def test_ant_rich_extras_contest() -> None:
    # 5 ants, 2 foods: champion leaves 3 idle; extras contest foodA.
    ants = [(8, 8), (9, 9), (70, 70), (72, 72), (60, 60)]
    food_a: Loc = (10, 10)
    food_b: Loc = (80, 80)
    enemies = [(10, 12), (11, 10)]
    got = call_bot(ants, [food_a, food_b], enemies)
    assert len(got) == len(ants)
    champ = champ_assign(ants, [food_a, food_b], enemies, DIST, ROWS, COLS)
    assert len(champ) == 2
    idle = [ai for ai in range(len(ants)) if ai not in champ]
    assert len(idle) == 3
    for ai in idle:
        assert got[ai] == food_a


def test_ant_rich_without_enemies_idles_like_champion() -> None:
    ants = [(8, 8), (9, 9), (70, 70), (72, 72), (60, 60)]
    foods = [(10, 10), (80, 80)]
    got = call_bot(ants, foods, [])
    assert got == champ_assign(ants, foods, [], DIST, ROWS, COLS)


def test_parity_matches_champion_exactly() -> None:
    # 3 ants, 4 foods: neither ratio trips, so byte-identical greedy.
    ants = [(10, 10), (20, 20), (80, 80)]
    foods = [(12, 11), (50, 50), (52, 51), (81, 80)]
    enemies = [(51, 50), (12, 13)]
    got = call_bot(ants, foods, enemies)
    assert got == champ_assign(ants, foods, enemies, DIST, ROWS, COLS)
    # Parity with a live denial cluster (3 foes) still matches exactly.
    foes = [(50, 52), (51, 49), (49, 51)]
    ants2 = [(48, 48), (55, 55), (10, 10), (90, 90)]
    foods2 = [(50, 50), (51, 50), (52, 50), (10, 12), (90, 88)]
    got2 = call_bot(ants2, foods2, foes)
    assert got2 == champ_assign(ants2, foods2, foes, DIST, ROWS, COLS)


def test_ratio_scan_costs_under_1ms_crowded() -> None:
    # 30 ants, 60 foods on a crowded 50x50 board: triage scan < 1ms.
    small = make_distance(50, 50)
    ants = [(i % 50, (i * 7) % 50) for i in range(30)]
    foods = [((i * 13) % 50, (i * 29) % 50) for i in range(60)]
    worst = 0.0
    for _ in range(3):
        start = time.perf_counter()
        Quartermaster.near_food_indices(ants, foods, small)
        elapsed = time.perf_counter() - start
        worst = max(worst, elapsed)
    assert worst < 0.001
