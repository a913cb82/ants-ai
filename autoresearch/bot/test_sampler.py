#!/usr/bin/env python
"""Sampler (Dirichlet combat sampling) tests. No engine games.

Contact combat (an ant with a visible enemy within attack range)
replaces the static local-majority is_safe check with a time-boxed
Dirichlet sampler: per engaged ant, counts over legal moves (init 1
each); each round picks a random engaged ant (own maximize, enemy
minimize the same battle score), scores every legal move with one
step of provisional focus resolution, and increments the best move's
count. Stops at 150ms or 200 rounds. Highest count wins; ties fall
back to the legacy check. Ants not in contact keep legacy untouched.
Battle score: enemyDead*300 - myDead*180 - dist (anti-trade: equal
exchanges score below supported holds).
"""

import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Denial import Denial  # noqa: E402
from Sampler import (  # noqa: E402
    SAMPLER_MS,
    SAMPLER_ROUNDS,
    Sampler,
    battle_score,
    focus_deaths,
    legal_combat_moves,
)

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
        attackradius2: int = 5,
    ):
        self.rows = rows
        self.cols = cols
        self._ants = list(my_ants)
        self._foods = list(foods)
        self._water = set(water)
        self._hills = list(my_hills or [])
        self._enemies = list(enemies or [])
        self.attackradius2 = attackradius2
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


def contact_state() -> FakeAnts:
    # A=(10,10) with friends F1=(9,9) F2=(11,9) faces E1=(10,12)
    # E2=(10,13); food pulls east. Greedy first step east suicides
    # (A dies, nothing dies); holding keeps support and wins the
    # E1 trade; stepping west walks out clean.
    return FakeAnts(
        20,
        20,
        [(10, 10), (9, 9), (11, 9)],
        [(10, 16)],
        enemies=[(10, 12), (10, 13)],
    )


def fresh_sampler(**kw: object) -> Sampler:
    bot = Sampler()
    bot.do_setup(FakeAnts(10, 10, [(0, 0)], []))
    for k, v in kw.items():
        setattr(bot, k, v)
    return bot


def move_score(bot: Sampler, state: FakeAnts, ai: int, move: str | None) -> int:
    ants_list = state.my_ants()
    enemy_locs = [loc for loc, _ in state.enemy_ants()]
    r2 = state.attackradius2 or 5
    my_pos = list(ants_list)
    if move is not None:
        my_pos[ai] = state.destination(ants_list[ai], move)
    my_dead, en_dead = focus_deaths(my_pos, enemy_locs, r2, state.rows, state.cols)
    return battle_score(my_pos, enemy_locs, my_dead, en_dead, state.rows, state.cols)


def test_surrounded_ant_picks_max_survival_not_greedy():
    # Legacy greedy marches east into a kill zone (A dies, no enemy
    # dies, -188). The sampler stays with support: holding kills E1
    # for 110, the best score on the board (the N/S steps tie it;
    # hold-first order keeps the ant still). Never the greedy step.
    state = contact_state()
    champ = Denial()
    champ.do_setup(state)
    champ.do_turn(state)
    assert ((10, 10), "e") in state.orders  # greedy goes east

    bot = fresh_sampler()
    bot._rng = random.Random(1)
    probe = contact_state()
    orders, rounds = bot.sample_battle_orders(
        probe,
        probe.my_ants(),
        [loc for loc, _ in probe.enemy_ants()],
        max_rounds=50,
        budget_s=60.0,
        rng=bot._rng,
    )
    assert rounds >= 1
    assert orders.get(0) is None or orders[0] != "e"
    best = max(
        legal_combat_moves(probe, (10, 10)),
        key=lambda m: move_score(bot, probe, 0, m),
    )
    assert move_score(bot, probe, 0, best) == move_score(bot, probe, 0, orders.get(0))
    assert best is None  # hold-with-support outscores every step
    assert orders.get(0) is None


def test_zero_rounds_equals_legacy_exactly():
    layouts = [
        contact_state(),
        FakeAnts(10, 10, [(5, 5)], [(5, 7)], enemies=[(0, 0)]),
        FakeAnts(
            20,
            20,
            [(10, 10), (10, 11), (11, 10)],
            [(5, 5)],
            enemies=[(12, 11), (11, 12), (12, 12)],
        ),
    ]
    for layout in layouts:
        champ = Denial()
        champ.do_setup(layout)
        samp = fresh_sampler(sampler_rounds=0)

        def same(lo: FakeAnts = layout) -> FakeAnts:
            return FakeAnts(
                lo.rows,
                lo.cols,
                lo.my_ants(),
                lo.food(),
                water=set(lo._water),
                enemies=list(lo._enemies),
            )

        ref = same()
        got = same()
        champ.do_turn(ref)
        samp.do_turn(got)
        assert got.orders == ref.orders


def test_two_rounds_avoids_legacy_suicide():
    # Legacy allows east (local majority 3v2) but east suicides.
    # Two sampler rounds already refuse it.
    state = contact_state()
    champ = Denial()
    champ.do_setup(state)
    champ.do_turn(state)
    assert ((10, 10), "e") in state.orders
    east = move_score(fresh_sampler(), contact_state(), 0, "e")
    assert east < 0  # dies for nothing

    bot = fresh_sampler(sampler_rounds=2)
    bot._rng = random.Random(3)
    probe = contact_state()
    bot.do_turn(probe)
    assert ((10, 10), "e") not in probe.orders
    chosen = next((d for loc, d in probe.orders if loc == (10, 10)), None)
    assert move_score(bot, contact_state(), 0, chosen) > east


def test_sampler_caps_under_150ms_on_20_ant_brawl():
    assert SAMPLER_MS == 150
    assert SAMPLER_ROUNDS == 200
    own = [(8 + (i % 4), 8 + (i // 4)) for i in range(20)]
    en = [(8 + (i % 4), 13 + (i // 4)) for i in range(20)]
    state = FakeAnts(30, 30, own, [(15, 15)], enemies=en)
    bot = fresh_sampler()
    start = time.perf_counter()
    orders, rounds = bot.sample_battle_orders(
        state, state.my_ants(), [loc for loc, _ in state.enemy_ants()]
    )
    elapsed = time.perf_counter() - start
    assert isinstance(orders, dict)
    assert 1 <= rounds <= SAMPLER_ROUNDS
    # Hard cap holds on any machine: the per-round time check stops
    # the loop at the budget plus at most one round of overshoot.
    assert elapsed * 1000 < SAMPLER_MS + 50, f"{elapsed * 1000:.1f}ms"
    # And it is the time-box that enforces it: a brawl no machine
    # can finish gets cut off after a handful of rounds.
    big_own = [(5 + (i % 6), 5 + (i // 6)) for i in range(60)]
    big_en = [(5 + (i % 6), 11 + (i // 6)) for i in range(60)]
    big = FakeAnts(30, 30, big_own, [(15, 15)], enemies=big_en)
    start = time.perf_counter()
    _, big_rounds = bot.sample_battle_orders(
        big,
        big.my_ants(),
        [loc for loc, _ in big.enemy_ants()],
        max_rounds=10**6,
        budget_s=0.05,
        rng=random.Random(0),
    )
    big_elapsed = time.perf_counter() - start
    assert 1 <= big_rounds < 10**6
    assert big_elapsed < 0.2, f"{big_elapsed * 1000:.1f}ms"


def test_stop_conditions():
    state = contact_state()
    bot = fresh_sampler()
    orders, rounds = bot.sample_battle_orders(
        state,
        state.my_ants(),
        [loc for loc, _ in state.enemy_ants()],
        max_rounds=200,
        budget_s=0.0,
        rng=random.Random(0),
    )
    assert (orders, rounds) == ({}, 0)
    orders, rounds = bot.sample_battle_orders(
        state,
        state.my_ants(),
        [loc for loc, _ in state.enemy_ants()],
        max_rounds=200,
        budget_s=60.0,
        rng=random.Random(0),
    )
    assert rounds == 200
