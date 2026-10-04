#!/usr/bin/env python
"""A1K0N Dirichlet sampling combat tests (faithful top-10 sampler).

Self-contained: stdlib plus Dirichlet.py plus ants.py only. No
combat.py import anywhere. The entry keeps the champion's
economy/muster/guard/explore byte-identical and replaces only the
combat core with the a1k0n sampler:

- per-ant Dirichlet(1,1,1,1,1) over 5 moves (n/e/s/w/hold),
  gamma-sampled from stdlib random per combat decision,
- random ant order each turn (seeded RNG, seed stored per game),
- best-reply by provisional resolution under focus-battle rules
  (ant dies iff min enemy weakness <= own weakness),
  score = enemyDead*300 - myDead*180 - dist, best sampled move
  kept until the per-fight time budget runs out,
- sampling replaces minimax because minimax is too conservative:
  the sampler sometimes accepts 1-for-1s the max-min gate refuses
  (xathis contrast: xathis 1-ply minimax with the same eval
  refuses equal trades unless 14+ friends are near).

(a) Dirichlet samples valid distributions (sum to 1, seeded
reproducibility). (b) Provisional resolution matches focus-battle
rules on a fixed hand-resolved 2v2. (c) Time budget respected on a
crowded board. (d) Sampler accepts a 1-for-1 the static majority
filter refuses (seeded). (e) Full turn under 1s crowded.
"""

import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Dirichlet as DP  # noqa: E402

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


def run_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
    seed: int = 7,
) -> tuple[list[tuple[Loc, str]], DP.Dirichlet]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = DP.Dirichlet(seed=seed)
    bot.do_turn(fake)
    return fake.orders, bot


def test_dirichlet_samples_valid_distributions() -> None:
    # (a) Five weights over n/e/s/w/hold, all positive, summing to 1.
    rng = random.Random(42)
    for _ in range(20):
        weights = DP.dirichlet_sample(rng)
        assert len(weights) == 5
        assert all(w > 0.0 for w in weights)
        assert abs(sum(weights) - 1.0) < 1e-9


def test_dirichlet_seeded_reproducibility() -> None:
    # (a) Same seed replays the same stream; the game seed is
    # stored on the bot for reproducibility.
    first = DP.dirichlet_sample(random.Random(1234))
    second = DP.dirichlet_sample(random.Random(1234))
    assert first == second
    third = DP.dirichlet_sample(random.Random(999))
    assert first != third
    bot = DP.Dirichlet(seed=1234)
    assert bot.seed == 1234
    again = DP.Dirichlet(seed=1234)
    assert bot.rng.random() == again.rng.random()


def test_provisional_resolution_matches_focus_battle_2v2() -> None:
    # (b) Hand-resolved under focus rules (attackradius2 5):
    # my (5,5) sees foe (5,7) only (sq 4): weakness 1, foe
    # weakness 2, so 2 <= 1 fails and it lives. My (5,6) sees
    # both foes (sq 1, 4): weakness 2, min foe weakness 1, so
    # 1 <= 2 dies. Foe (5,7) sees both mine (sq 4, 1):
    # weakness 2, min 1, dies. Foe (5,8) sees (5,6) only
    # (sq 4): weakness 1 vs 2, lives. A clean 1-for-1.
    my = [(5, 5), (5, 6)]
    foes = [(5, 7), (5, 8)]
    my_dead, foe_dead = DP.resolve_focus(my, foes, 5, _sq)
    assert my_dead == {1}
    assert foe_dead == {0}
    score = DP.combat_score(len(my_dead), len(foe_dead), my, foes, _dist)
    assert score == 1 * 300 - 1 * 180 - _dist_sum(my, foes)


def _dist(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


def _dist_sum(my: list[Loc], foes: list[Loc]) -> int:
    if not foes:
        return 0
    return sum(min(_dist(m, f) for f in foes) for m in my)


def test_provisional_resolution_lone_1v1_is_mutual_death() -> None:
    # (b2) Focus battle: a lone adjacent pair always kills both
    # (weakness 1 each, 1 <= 1). The xathis static gate refuses
    # this; the sampler may take it.
    my_dead, foe_dead = DP.resolve_focus([(5, 5)], [(5, 6)], 5, _sq)
    assert my_dead == {0}
    assert foe_dead == {0}


def test_time_budget_respected_on_crowded_board() -> None:
    # (c) One combat decision on a crowded board returns within
    # the per-fight budget plus slack, with a legal move.
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    probe = FakeAnts(mine, foes)
    rng = random.Random(11)
    start = time.perf_counter()
    move = DP.sample_fight_move(
        mine[0],
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
        rng,
        budget=DP.FIGHT_BUDGET,
    )
    elapsed = time.perf_counter() - start
    assert move in ("n", "e", "s", "w", "hold")
    assert elapsed < DP.FIGHT_BUDGET + 0.05
    if move != "hold":
        dest = probe.destination(mine[0], move)
        assert probe.passable(dest)
        assert probe.unoccupied(dest)


def test_sampler_accepts_1for1_static_filter_refuses() -> None:
    # (d) Lone ant (5,5) eyes the step east onto (5,6) against one
    # foe (5,7): no friend in attack range, no near friends, so the
    # static majority filter (champion gate: strict superiority or
    # 10 near friends for equal trades) refuses. Provisionally the
    # step is mutual death (1-for-1, 300-180-dist beats retreating),
    # and the seeded sampler takes it on at least one seed: minimax
    # never would, the sampler sometimes does.
    mine = [(5, 5)]
    foes = [(5, 7)]
    probe = FakeAnts(mine, foes)
    dest = probe.destination((5, 5), "e")
    assert dest == (5, 6)
    assert DP.is_safe_step(dest, (5, 5), mine, foes, 5, _sq, probe.distance) is False
    my_dead, foe_dead = DP.resolve_focus([dest], foes, 5, _sq)
    assert my_dead == {0} and foe_dead == {0}
    accepted = []
    for seed in range(200):
        rng = random.Random(seed)
        move = DP.sample_fight_move(
            (5, 5),
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
            rng,
            budget=0.005,
        )
        if move == "e":
            accepted.append(seed)
    assert accepted, "seeded sampler never takes the 1-for-1"
    pinned = DP.sample_fight_move(
        (5, 5),
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
        random.Random(accepted[0]),
        budget=0.005,
    )
    assert pinned == "e"


def test_full_turn_under_1s_crowded() -> None:
    # (e) A full crowded turn (48 ants, 30 foes, food, hills)
    # decides in under a second.
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [((i * 3 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(20)]
    start = time.perf_counter()
    orders, _ = run_turn(
        mine, foes, foods, enemy_hills=[(15, 15)], my_hills=[(10, 10)], seed=7
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert isinstance(orders, list)


def test_random_order_is_seeded_not_engine_order() -> None:
    # Random ant order each turn: same seed replays the same order,
    # and the order is not engine order on a 12-ant board.
    mine = [(i, i) for i in range(12)]
    foes = [(19, 19)]
    probe = FakeAnts(mine, foes)
    first = DP.turn_order(mine, foes, probe.distance, random.Random(3))
    second = DP.turn_order(mine, foes, probe.distance, random.Random(3))
    assert first == second
    assert sorted(first) == list(range(12))
    assert first != list(range(12))


def test_food_claims_stay_champion_greedy() -> None:
    # Economy byte-identical: one food draws the nearest ant only.
    orders, _ = run_turn([(5, 5), (10, 10)], [], foods=[(5, 6)], seed=7)
    assert dict(orders)[(5, 5)] == "e"
    assert (10, 10) not in dict(orders) or dict(orders)[(10, 10)] != "e"
