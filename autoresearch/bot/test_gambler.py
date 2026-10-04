#!/usr/bin/env python
"""Gambler (forward-spawn expansion) tests. No engine games.

The first EXPANSION_WAVES spawn waves march on the most-unseen map
third instead of working nearby food; from the next wave on the
champion greedy resumes untouched.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Flood import Flood  # noqa: E402
from Gambler import EXPANSION_WAVES, Gambler  # noqa: E402

Loc = tuple[int, int]


class FakeAnts:
    """Minimal engine double. Mirrors ants.py semantics (torus grid,
    water blocks, food squares count as occupied)."""

    def __init__(
        self,
        rows: int,
        cols: int,
        my_ants: list[Loc],
        foods: list[Loc],
        water: set[Loc] = frozenset(),  # type: ignore[assignment]
        my_hills: list[Loc] | None = None,
        enemies: list[Loc] | None = None,
    ):
        self.rows = rows
        self.cols = cols
        self._ants = list(my_ants)
        self._foods = list(foods)
        self._water = set(water)
        self._hills = list(my_hills or [])
        self._enemies = list(enemies or [])
        self.attackradius2 = 25
        self.orders: list[tuple[Loc, str]] = []

    def food(self) -> list[Loc]:
        return self._foods[:]

    def my_ants(self) -> list[Loc]:
        return self._ants[:]

    def enemy_ants(self) -> list[tuple[Loc, int]]:
        return [(loc, 1) for loc in self._enemies]

    def my_hills(self) -> list[Loc]:
        return self._hills[:]

    def enemy_hills(self) -> list[tuple[Loc, int]]:
        return []

    def distance(self, a: Loc, b: Loc) -> int:
        dc = min(abs(a[1] - b[1]), self.cols - abs(a[1] - b[1]))
        dr = min(abs(a[0] - b[0]), self.rows - abs(a[0] - b[0]))
        return dr + dc

    def destination(self, loc: Loc, direction: str) -> Loc:
        aim = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
        dr, dc = aim[direction]
        return ((loc[0] + dr) % self.rows, (loc[1] + dc) % self.cols)

    def passable(self, loc: Loc) -> bool:
        return loc not in self._water

    def unoccupied(self, loc: Loc) -> bool:
        taken = set(self._ants) | set(self._enemies) | set(self._foods)
        return loc not in taken

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 1000


def fresh_gambler() -> Gambler:
    bot = Gambler()
    bot.do_setup(FakeAnts(10, 10, [(0, 0)], []))
    return bot


def test_waves_1_to_3_ignore_near_food_and_march_unseen():
    # Ant in the middle third, food 2 steps east (well within 10),
    # unseen thirds lie west. All three early waves must march
    # unseen-ward, never toward the food.
    bot = fresh_gambler()
    positions = [(10, 10), (10, 9), (10, 8)]
    for wave, pos in enumerate(positions, start=1):
        state = FakeAnts(20, 20, [pos], [(10, 12)])
        bot.do_turn(state)
        assert bot.wave == wave
        assert state.orders == [(pos, "w")], f"wave {wave}: {state.orders}"


def run_turns(bot, state_fn, n: int) -> None:
    for _ in range(n):
        bot.do_turn(state_fn())


def test_wave4_matches_champion_greedy_on_three_layouts():
    layouts = [
        # 1 ant, 1 food, open map.
        FakeAnts(10, 10, [(5, 5)], [(5, 7)]),
        # 2 ants, 2 foods, water wall with one gap.
        FakeAnts(
            12,
            12,
            [(2, 2), (9, 9)],
            [(2, 8), (9, 3)],
            water={(r, 5) for r in range(12) if r != 6},
        ),
        # Equidistant tie: greedy must break it exactly like Flood.
        FakeAnts(10, 10, [(5, 5)], [(5, 3), (5, 7)]),
    ]
    for layout in layouts:
        champ = Flood()
        champ.do_setup(layout)
        gamb = Gambler()
        gamb.do_setup(layout)

        def same(lo: FakeAnts = layout) -> FakeAnts:
            return FakeAnts(
                lo.rows,
                lo.cols,
                lo.my_ants(),
                lo.food(),
                water=set(lo._water),
            )

        run_turns(champ, same, EXPANSION_WAVES + 1)
        run_turns(gamb, same, EXPANSION_WAVES)
        assert gamb.wave == EXPANSION_WAVES
        final_champ = same()
        final_gamb = same()
        champ.do_turn(final_champ)
        gamb.do_turn(final_gamb)
        assert gamb.wave == EXPANSION_WAVES + 1
        assert final_gamb.orders == final_champ.orders, layout.food()
        assert len(final_gamb.orders) > 0


def test_wave_counter_survives_hill_loss():
    # Spawns, not ants: losing a hill and most ants mid-expansion
    # must not reset or stall the wave clock.
    bot = fresh_gambler()
    states = [
        FakeAnts(10, 10, [(5, 5)], [(5, 7)], my_hills=[(5, 5)]),
        FakeAnts(10, 10, [(5, 5), (5, 4)], [(5, 7)], my_hills=[(5, 5)]),
        FakeAnts(10, 10, [(5, 4)], [(5, 7)]),  # hill lost
        FakeAnts(10, 10, [(5, 4)], [(5, 7)]),
    ]
    for i, state in enumerate(states, start=1):
        bot.do_turn(state)
        assert bot.wave == i
    # Wave 4 after the hill loss: normal greedy resumes, matching
    # a fresh champion on the same state.
    champ = Flood()
    champ.do_setup(states[-1])
    ref = FakeAnts(10, 10, [(5, 4)], [(5, 7)])
    champ.do_turn(ref)
    assert states[-1].orders == ref.orders


def test_expansion_targeting_costs_under_2ms_on_big_map():
    import random

    rng = random.Random(11)
    water = {
        (r, c)
        for r in range(100)
        for c in range(100)
        if rng.random() < 0.04 and (r, c) not in {(50, 40), (50, 33)}
    }
    ants = [(50, 40), (51, 41), (49, 42)]
    state = FakeAnts(100, 100, ants, [(50, 90)], water=water)
    bot = fresh_gambler()
    start = time.perf_counter()
    step = bot.expansion_step(state, ants[0])
    elapsed = time.perf_counter() - start
    assert step in ("n", "e", "s", "w"), step
    assert elapsed < 0.002, f"{elapsed * 1000:.2f}ms"
