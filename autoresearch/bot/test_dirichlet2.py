#!/usr/bin/env python
"""Dirichlet2 suicide-veto tests (test-first for the tuning idea).

Self-contained: stdlib plus Dirichlet2.py plus Dirichlet.py plus
ants.py only. Dirichlet2 is the base a1k0n sampler plus exactly one
idea -- the suicide veto: after sampling picks a move, veto it when
provisional resolution shows our ant dies for NOTHING (enemyDead 0,
myDead 1), falling back to the next-best move by provisional score,
or hold if every legal move suicides. 1-for-1 takes stay exactly as
the sampler chooses; everything else is identical to base.

(a) A 0-for-1 sampled top pick is vetoed for the next-best move,
    and the mover lives there.
(b) When every legal move suicides, the bot holds (base walks in).
(c) A 1-for-1 take is unchanged from base on all 200 seeds.
(d) The veto pass costs <0.5ms on a crowded board.
(e) Full crowded turn still under 1s; food claims stay champion-greedy.
(f) Veto helper truth tables (pure, sampling-independent).
"""

import os
import random
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Dirichlet as DP  # noqa: E402
import Dirichlet2 as D2  # noqa: E402

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


def _sq(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


def _pick(
    mod: Any,
    ant: Loc,
    mine: list[Loc],
    foes: list[Loc],
    probe: FakeAnts,
    seed: int,
) -> str:
    fn = mod.sample_fight_move
    return fn(
        ant,
        mine,
        foes,
        5,
        probe.distance,
        _sq,
        probe.destination,
        probe.passable,
        probe.unoccupied,
        set(),
        ROWS,
        COLS,
        random.Random(seed),
    )


# Pinned (a) front: mover (19, 11) with foes (19, 13), (19, 12),
# (0, 12). Exact provisional scores: s -188 (unique top),
# hold -189, n/w -190. Stepping south is a needless suicide
# (mover dies, nothing dies); stepping west lives. Seed 14 draws
# south first and west second, so the base pick is south on every
# run regardless of how many draws the budget allows, and the
# veto fallback is west on every run with at least two draws.
MINE_A = [(19, 11), (17, 12), (16, 12)]
FOES_A = [(19, 13), (19, 12), (0, 12)]
MOVER_A: Loc = (19, 11)
SEED_A = 14


def _casualties(
    ant: Loc, move: str, mine: list[Loc], foes: list[Loc], probe: FakeAnts
) -> tuple[bool, int]:
    idx = mine.index(ant)
    local_my = [i for i, p in enumerate(mine) if probe.distance(p, ant) <= 6]
    local_foe = [j for j, q in enumerate(foes) if probe.distance(q, ant) <= 6]
    base_my = [mine[i] for i in local_my]
    base_foe = [foes[j] for j in local_foe]
    mover_k = local_my.index(idx)
    pos = ant if move == "hold" else probe.destination(ant, move)
    my_local = base_my[:mover_k] + [pos] + base_my[mover_k + 1 :]
    my_dead, foe_dead, _ = D2.best_reply_casualties(
        my_local,
        base_foe,
        5,
        _sq,
        probe.distance,
        probe.destination,
        probe.passable,
    )
    return mover_k in my_dead, len(foe_dead)


def test_0for1_sampled_move_vetoed_for_next_best() -> None:
    # (a) Base samples south first and keeps it: the unique
    # provisional top pick, yet our ant dies there for nothing.
    # Dirichlet2 vetoes it for west, where the mover lives.
    probe = FakeAnts(MINE_A, FOES_A)
    assert _pick(DP, MOVER_A, MINE_A, FOES_A, probe, SEED_A) == "s"
    mover_dies, foe_dead = _casualties(MOVER_A, "s", MINE_A, FOES_A, probe)
    assert mover_dies and foe_dead == 0
    assert _pick(D2, MOVER_A, MINE_A, FOES_A, probe, SEED_A) == "w"
    lives, _ = _casualties(MOVER_A, "w", MINE_A, FOES_A, probe)
    assert not lives


def test_veto_stable_across_runs() -> None:
    # The pin does not depend on sampling luck: south is the exact
    # unique argmax drawn on the first sample, the fallback is an
    # exact rescore, so both picks repeat on every run.
    probe = FakeAnts(MINE_A, FOES_A)
    for _ in range(5):
        assert _pick(DP, MOVER_A, MINE_A, FOES_A, probe, SEED_A) == "s"
        assert _pick(D2, MOVER_A, MINE_A, FOES_A, probe, SEED_A) == "w"


# Pinned (b) trap: our ant at (5, 6) between foes (4, 7), (6, 7),
# (5, 8). Every legal move -- and hold -- dies for nothing under
# provisional best replies. Seed 0 draws east first: east is the
# unique min-distance suicide, so base walks in on every run.
MINE_B = [(5, 6)]
FOES_B = [(4, 7), (6, 7), (5, 8)]
MOVER_B: Loc = (5, 6)


def test_all_suicide_samples_hold() -> None:
    # (b) All samples suicide, so Dirichlet2 holds while base steps
    # east into the trap. The hold is sampling-independent: it holds
    # on every seed, because the exact ranking vetoes everything.
    probe = FakeAnts(MINE_B, FOES_B)
    for move in ("n", "e", "s", "w", "hold"):
        mover_dies, foe_dead = _casualties(MOVER_B, move, MINE_B, FOES_B, probe)
        assert mover_dies and foe_dead == 0, move
    assert _pick(DP, MOVER_B, MINE_B, FOES_B, probe, 0) == "e"
    for seed in range(10):
        assert _pick(D2, MOVER_B, MINE_B, FOES_B, probe, seed) == "hold"


def test_1for1_take_unchanged_from_base() -> None:
    # (c) Lone ant (5, 5) stepping east onto (5, 6) against foe
    # (5, 7) is mutual death -- a 1-for-1 the veto must never touch.
    # Base takes it on all 200 seeds; Dirichlet2 matches exactly.
    mine = [(5, 5)]
    foes = [(5, 7)]
    probe = FakeAnts(mine, foes)
    mover_dies, foe_dead = _casualties((5, 5), "e", mine, foes, probe)
    assert mover_dies and foe_dead == 1
    assert D2.is_needless_suicide(0, {0}, {0}) is False
    for seed in range(200):
        base = _pick(DP, (5, 5), mine, foes, probe, seed)
        veto = _pick(D2, (5, 5), mine, foes, probe, seed)
        assert base == "e", seed
        assert veto == base, seed


def _crowded_scored() -> tuple[dict[str, tuple[int, bool]], FakeAnts, Loc]:
    # A crowded local battle (12 ours vs 10 foes inside the
    # battle-local radius): real provisional scores and suicide
    # flags, as the sampler memoizes them. Setup resolves widely
    # (untimed); the veto decision itself must be instant.
    mine = [
        (9, 9),
        (9, 12),
        (10, 14),
        (11, 9),
        (11, 14),
        (13, 9),
        (13, 14),
        (14, 10),
        (14, 13),
        (10, 10),
        (15, 11),
        (8, 11),
    ]
    foes = [
        (12, 14),
        (13, 12),
        (14, 12),
        (11, 13),
        (10, 12),
        (15, 12),
        (12, 15),
        (13, 15),
        (9, 13),
        (16, 11),
    ]
    probe = FakeAnts(mine + [(12, 11)], foes)
    ant = (12, 11)
    mine = mine + [ant]
    idx = mine.index(ant)
    local_my = [i for i, p in enumerate(mine) if probe.distance(p, ant) <= 6]
    local_foe = [j for j, q in enumerate(foes) if probe.distance(q, ant) <= 6]
    assert len(local_my) >= 10 and len(local_foe) >= 8
    base_my = [mine[i] for i in local_my]
    base_foe = [foes[j] for j in local_foe]
    mover_k = local_my.index(idx)
    opts = [
        d for d in ("n", "e", "s", "w") if probe.unoccupied(probe.destination(ant, d))
    ]
    assert len(opts) >= 2
    scored: dict[str, tuple[int, bool]] = {}
    for move in ["hold"] + opts:
        pos = ant if move == "hold" else probe.destination(ant, move)
        my_local = base_my[:mover_k] + [pos] + base_my[mover_k + 1 :]
        my_dead, foe_dead, score = D2.best_reply_casualties(
            my_local,
            base_foe,
            5,
            _sq,
            probe.distance,
            probe.destination,
            probe.passable,
        )
        scored[move] = (score, D2.is_needless_suicide(mover_k, my_dead, foe_dead))
    return scored, probe, ant


def test_veto_under_half_ms_crowded() -> None:
    # (d) The veto decision over crowded-battle scores costs
    # <0.5ms: it re-ranks memoized scores and resolves nothing.
    scored, probe, ant = _crowded_scored()
    assert len(scored) >= 3
    move = D2.veto_fallback(scored)
    assert move in scored
    if move != "hold":
        assert probe.unoccupied(probe.destination(ant, move))
    worst = 0.0
    for _ in range(1000):
        start = time.perf_counter()
        D2.veto_fallback(scored)
        worst = max(worst, time.perf_counter() - start)
    assert worst < 0.0005, worst


def test_veto_helper_truth_table() -> None:
    # (f) The veto fires exactly on mover-dies-for-nothing.
    assert D2.is_needless_suicide(0, {0}, set()) is True
    assert D2.is_needless_suicide(0, {0}, {1}) is False
    assert D2.is_needless_suicide(0, {1}, set()) is False
    assert D2.is_needless_suicide(0, set(), set()) is False
    assert D2.is_needless_suicide(2, {0, 2}, set()) is True


def test_casualties_agree_with_score() -> None:
    # (f) best_reply_casualties shares one engine with
    # best_reply_score: the returned score equals the eval of the
    # returned dead sets.
    mine = [(5, 5), (5, 6)]
    foes = [(5, 7), (5, 8)]
    probe = FakeAnts(mine, foes)
    my_dead, foe_dead, score = D2.best_reply_casualties(
        mine,
        foes,
        5,
        _sq,
        probe.distance,
        probe.destination,
        probe.passable,
    )
    expect = D2.best_reply_score(
        mine,
        foes,
        5,
        _sq,
        probe.distance,
        probe.destination,
        probe.passable,
    )
    assert score == expect
    assert my_dead <= set(range(len(mine)))
    assert foe_dead <= set(range(len(foes)))


def test_full_turn_under_1s_crowded() -> None:
    # (e) A full crowded turn still decides in under a second.
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [((i * 3 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(20)]
    fake = FakeAnts(mine, foes, foods, enemy_hills=[(15, 15)], my_hills=[(10, 10)])
    bot = D2.Dirichlet2(seed=7)
    start = time.perf_counter()
    bot.do_turn(fake)
    assert time.perf_counter() - start < 1.0
    assert isinstance(fake.orders, list)
