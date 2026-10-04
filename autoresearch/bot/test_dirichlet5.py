#!/usr/bin/env python
"""Dirichlet5 fight pre-pass tests (test-first for the structural idea).

Self-contained: stdlib plus Dirichlet3.py plus Dirichlet5.py plus
ants.py only. Dirichlet5 is Dirichlet3 with exactly one idea -- a
combat PRE-PASS before food assignment: battle-local ants (an enemy
within LOCAL_R == 6, the sampler's own battle-local screen) run the
sampler (with veto) FIRST and claim destinations; committed fighters
skip food claims entirely (their claims are freed for the
uncommitted); every ant samples at most once per turn (holders
keep their pre-pass verdict, the rest run the base economy
untouched).
No weight, budget, or gate changes.

(a) A battle-local ant fights instead of taking adjacent food: base
    takes the food, Dirichlet5 commits toward the enemy, and the
    freed claim goes to the next-nearest ant (a far control ant
    takes its own food in both).
(b) Quiet boards (no enemies, or every enemy beyond LOCAL_R) are
    byte-identical to base full-turn: same orders across seeds and
    across a multi-turn scripted sequence, same visit counts.
(c) Committed destinations are respected by the economy pass: no
    two orders share a destination on a crowded board, no ant
    issues twice, and a forced commit onto a food square steers
    the economy off it.
(d) Full turn stays under 1s on a crowded 12v9 board.
(e) The pre-pass radius is exactly battle-local: an enemy at
    distance 7 triggers nothing (full-turn identity with base),
    and the module constants match base (no tuning smuggled in).
"""

import os
import random
import sys
import time
from typing import Any
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Dirichlet3 as D3  # noqa: E402
import Dirichlet5 as D5  # noqa: E402

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

    def set_enemies(self, enemies: list[Loc]) -> None:
        self._enemies = list(enemies)

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


def _run_turn(
    mod: Any, cls_name: str, seed: int, fake: FakeAnts
) -> list[tuple[Loc, str]]:
    bot = getattr(mod, cls_name)(seed=seed)
    bot.do_setup(fake)
    fake.orders = []
    bot.do_turn(fake)
    return list(fake.orders)


def _dest(fake: FakeAnts, order: tuple[Loc, str]) -> Loc:
    return fake.destination(order[0], order[1])


# Fight-pre-pass scenario: A0 (5, 5) sits next to food F0 (5, 6)
# with a foe (2, 5) three squares north; A1 (8, 6) is the next ant
# (7 from the foe: NOT battle-local); A2 (12, 12) is a far control
# with its own adjacent food F1 (12, 13). Water (7, 6) and (8, 7)
# pins A1's explore away from its food path: explore reads
# n-blocked, e-blocked and goes south, while the BFS food path to
# F0 goes west around the water -- so a freed claim is observable
# and never coincides with exploring.
MINE_A = [(5, 5), (8, 6), (12, 12)]
FOE_A = [(2, 5)]
FOODS_A = [(5, 6), (12, 13)]
WATER_A = {(7, 6), (8, 7)}


def test_fighter_skips_food_and_frees_claim() -> None:
    # (a) Base takes the adjacent food before combat ever runs;
    # Dirichlet5's pre-pass commits the battle-local ant north
    # toward the foe instead, so the food claim falls to the next
    # ant -- while the far control ant eats identically in both.
    probe = FakeAnts(MINE_A, FOE_A, FOODS_A, WATER_A)
    assert probe.distance((5, 5), (2, 5)) <= 6
    assert probe.distance((8, 6), (2, 5)) > 6
    assert probe.distance((12, 12), (2, 5)) > 6
    for seed in range(5):
        base_orders = _run_turn(
            D3, "Dirichlet3", seed, FakeAnts(MINE_A, FOE_A, FOODS_A, WATER_A)
        )
        new_orders = _run_turn(
            D5, "Dirichlet5", seed, FakeAnts(MINE_A, FOE_A, FOODS_A, WATER_A)
        )
        # Base: A0 eats the adjacent food before the sampler runs.
        assert ((5, 5), "e") in base_orders
        # Pre-pass: A0 fights north instead of eating ...
        assert ((5, 5), "n") in new_orders
        assert ((5, 5), "e") not in new_orders
        # ... so the freed claim drops to A1 (west around water) ...
        assert ((8, 6), "w") in new_orders
        # ... while the far control ant eats in both.
        assert ((12, 12), "e") in base_orders
        assert ((12, 12), "e") in new_orders
        # Base never frees the claim: A1 explores south instead.
        assert ((8, 6), "s") in base_orders
        assert ((8, 6), "w") not in base_orders


def test_quiet_boards_match_base_move_for_move() -> None:
    # (b) No contact, no pre-pass, no sampling: with no enemies --
    # or every enemy outside the battle-local radius -- neither
    # entry draws, so full turns agree exactly across seeds, with
    # food, water, and remembered hills in play.
    mine = [(2, 2), (2, 5), (8, 8), (15, 15)]
    foods = [(3, 3), (9, 9), (14, 14)]
    water = {(4, 4), (4, 5)}
    far_foes = [(12, 0), (0, 12), (10, 18)]
    for seed in range(10):
        for foes in ([], far_foes):
            probe = FakeAnts(mine, foes, foods, water, [(18, 18)], [(2, 3)])
            for foe in foes:
                assert all(probe.distance(a, foe) > 6 for a in mine)
            base_bot = D3.Dirichlet3(seed=seed)
            new_bot = D5.Dirichlet5(seed=seed)
            base_bot.do_setup(FakeAnts(mine, foes, foods, water, [(18, 18)], [(2, 3)]))
            new_bot.do_setup(FakeAnts(mine, foes, foods, water, [(18, 18)], [(2, 3)]))
            base_fake = FakeAnts(mine, foes, foods, water, [(18, 18)], [(2, 3)])
            new_fake = FakeAnts(mine, foes, foods, water, [(18, 18)], [(2, 3)])
            base_bot.do_turn(base_fake)
            new_bot.do_turn(new_fake)
            assert base_fake.orders == new_fake.orders
            assert base_bot.visits == new_bot.visits


def test_quiet_multiturn_sequence_matches_base() -> None:
    # (b) The match holds across turns: enemies patrol but stay
    # distant, so both RNG streams stay in lockstep and every
    # turn's orders agree -- no behavior change off-contact.
    mine = [(2, 2), (2, 5), (8, 8), (15, 15)]
    foods = [(3, 3), (9, 9), (14, 14)]
    patrol = [
        [(12, 0), (0, 12), (10, 18)],
        [(12, 2), (2, 12), (8, 16)],
        [(14, 2), (2, 14), (8, 0)],
        [(13, 0), (0, 13), (12, 19)],
        [(12, 0), (0, 12), (10, 18)],
    ]
    bots = {id(D3): D3.Dirichlet3(seed=3), id(D5): D5.Dirichlet5(seed=3)}
    fakes = {
        id(D3): FakeAnts(mine, patrol[0], foods, None, [(18, 18)], [(2, 3)]),
        id(D5): FakeAnts(mine, patrol[0], foods, None, [(18, 18)], [(2, 3)]),
    }
    for mod in (D3, D5):
        bots[id(mod)].do_setup(fakes[id(mod)])
    for foes in patrol:
        orders = {}
        for mod in (D3, D5):
            fake = fakes[id(mod)]
            fake.set_enemies(foes)
            for foe in foes:
                assert all(fake.distance(a, foe) > 6 for a in mine)
            fake.orders = []
            bots[id(mod)].do_turn(fake)
            orders[id(mod)] = list(fake.orders)
        assert orders[id(D3)] == orders[id(D5)]


def _crowded() -> tuple[
    list[Loc], list[Loc], list[Loc], list[Loc] | None, list[Loc] | None
]:
    # Dense mutually-local 12v9 skirmish with food and hills.
    mine = [(5 + i // 4, 5 + i % 4) for i in range(12)]
    foes = [(6 + i // 3, 9 + i % 3) for i in range(9)]
    foods = [(0, 0), (19, 19), (10, 2)]
    return mine, foes, foods, [(15, 15)], [(10, 10)]


def test_committed_destinations_unique_crowded() -> None:
    # (c) Committed pre-pass claims join the shared destination set
    # before the economy runs, so no two orders -- fighter or
    # economy -- ever share a square, and no ant issues twice.
    mine, foes, foods, enemy_hills, my_hills = _crowded()
    for seed in range(3):
        fake = FakeAnts(mine, foes, foods, None, enemy_hills, my_hills)
        orders = _run_turn(D5, "Dirichlet5", seed, fake)
        assert len(orders) > 0
        dests = [_dest(fake, o) for o in orders]
        assert len(set(dests)) == len(dests)
        origins = [loc for loc, _ in orders]
        assert len(set(origins)) == len(origins)
        for dest in dests:
            assert fake.passable(dest)


def test_forced_commit_onto_food_steers_economy_off() -> None:
    # (c) Wiring, deterministically: stub the sampler so A0 (5, 5)
    # commits straight onto the food square (5, 6). A1 (5, 7) then
    # wants that square for food -- the claim must hold and the
    # economy must go elsewhere instead of overlapping.
    mine = [(5, 5), (5, 7)]
    foes = [(2, 5)]
    foods = [(5, 6)]
    fake = FakeAnts(mine, foes, foods)
    assert all(fake.distance(a, (2, 5)) <= 6 for a in mine)

    def commit_east(ant_loc: Loc, *rest: Any) -> str:
        _ = rest
        return "e" if ant_loc == (5, 5) else "hold"

    with mock.patch.object(D5, "sample_fight_move", side_effect=commit_east):
        stub_bot = D5.Dirichlet5(seed=1)
        stub_bot.do_setup(FakeAnts(mine, foes, foods))
        stub_fake = FakeAnts(mine, foes, foods)
        stub_bot.do_turn(stub_fake)
        stub_orders = list(stub_fake.orders)
    assert ((5, 5), "e") in stub_orders
    assert ((5, 7), "w") not in stub_orders
    dests = [_dest(stub_fake, o) for o in stub_orders]
    assert len(set(dests)) == len(dests)

    def commit_north(ant_loc: Loc, *rest: Any) -> str:
        _ = rest
        return "n" if ant_loc == (5, 5) else "hold"

    with mock.patch.object(D5, "sample_fight_move", side_effect=commit_north):
        free_bot = D5.Dirichlet5(seed=1)
        free_bot.do_setup(FakeAnts(mine, foes, foods))
        free_fake = FakeAnts(mine, foes, foods)
        free_bot.do_turn(free_fake)
        free_orders = list(free_fake.orders)
    # Commit elsewhere leaves the food square open: A1 claims it.
    assert ((5, 5), "n") in free_orders
    assert ((5, 7), "w") in free_orders


def test_each_ant_samples_at_most_once_per_turn() -> None:
    # The 1s law: the pre-pass must not duplicate full-budget
    # draws. Count sampler calls per ant over a crowded turn --
    # holders keep their verdict, so nobody draws twice.
    mine, foes, foods, enemy_hills, my_hills = _crowded()
    counts: dict[Loc, int] = {}
    real = D5.sample_fight_move

    def counting(ant_loc: Loc, *args: Any, **kwargs: Any) -> str:
        counts[ant_loc] = counts.get(ant_loc, 0) + 1
        return real(ant_loc, *args, **kwargs)

    with mock.patch.object(D5, "sample_fight_move", side_effect=counting):
        fake = FakeAnts(mine, foes, foods, None, enemy_hills, my_hills)
        orders = _run_turn(D5, "Dirichlet5", 7, fake)
    assert counts
    assert all(n <= 1 for n in counts.values()), counts
    assert len(orders) > 0


def test_full_turn_under_1s_crowded() -> None:
    # (d) A full crowded turn (12 ours vs 9 foes, food and hills
    # in play) still decides in under a second.
    mine, foes, foods, enemy_hills, my_hills = _crowded()
    for seed in (7, 8):
        fake = FakeAnts(mine, foes, foods, None, enemy_hills, my_hills)
        bot = D5.Dirichlet5(seed=seed)
        bot.do_setup(fake)
        start = time.perf_counter()
        bot.do_turn(fake)
        assert time.perf_counter() - start < 1.0
        assert len(fake.orders) > 0


def test_radius_is_exactly_battle_local_and_constants_match() -> None:
    # (e) The pre-pass screen is the sampler's own LOCAL_R: an
    # enemy at distance 7 triggers nothing, so the full turn is
    # base-identical; and no weight, budget, or gate moved.
    assert D5.LOCAL_R == 6
    assert D5.LOCAL_R == D3.LOCAL_R
    assert D5.FIGHT_BUDGET == D3.FIGHT_BUDGET == 0.015
    assert D5.EQUAL_TRADE_NEAR == D3.EQUAL_TRADE_NEAR
    assert D5.MOVES == D3.MOVES
    mine = [(2, 2)]
    foes = [(2, 9)]
    foods = [(2, 3)]
    probe = FakeAnts(mine, foes, foods)
    assert probe.distance((2, 2), (2, 9)) == 7
    for seed in range(10):
        base_orders = _run_turn(D3, "Dirichlet3", seed, FakeAnts(mine, foes, foods))
        new_orders = _run_turn(D5, "Dirichlet5", seed, FakeAnts(mine, foes, foods))
        assert base_orders == new_orders == [((2, 2), "e")]
        assert len(new_orders) > 0


def test_prepass_decision_uses_real_sampler_with_veto() -> None:
    # The pre-pass calls the real sampler (not a stub path): a lone
    # battle-local ant with a far food claim still draws, and the
    # decision is always a legal move or hold.
    mine = [(5, 5), (15, 15)]
    foes = [(5, 8)]
    foods = [(15, 16)]
    seen: set[str] = set()
    real = D5.sample_fight_move

    def recording(ant_loc: Loc, *args: Any, **kwargs: Any) -> str:
        move = real(ant_loc, *args, **kwargs)
        if ant_loc == (5, 5):
            seen.add(move)
        return move

    for seed in range(3):
        fake = FakeAnts(mine, foes, foods)
        assert fake.distance((5, 5), (5, 8)) <= 6
        assert fake.distance((15, 15), (5, 8)) > 6
        with mock.patch.object(D5, "sample_fight_move", side_effect=recording):
            orders = _run_turn(D5, "Dirichlet5", seed, fake)
        assert seen
        assert all(m in ("n", "e", "s", "w", "hold") for m in seen)
        dests = [_dest(fake, order) for order in orders]
        assert len(set(dests)) == len(dests)
        assert len(orders) > 0


def test_full_turn_under_1s_random_battle() -> None:
    # (d) Second timing net: a scattered random-style battle with a
    # fixed seed also decides in under a second.
    rng = random.Random(99)
    mine = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(24)]
    foes = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(16)]
    foods = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(10)]
    for seed in (3, 4):
        fake = FakeAnts(mine, foes, foods, None, [(15, 15)], [(10, 10)])
        bot = D5.Dirichlet5(seed=seed)
        bot.do_setup(fake)
        start = time.perf_counter()
        bot.do_turn(fake)
        assert time.perf_counter() - start < 1.0
