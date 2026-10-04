#!/usr/bin/env python
"""Safe-combat gate tests (Greedy3 entry).

Base is the Greedy2 weak-lure champion copy: 1/(1+d^2) food /
enemy / hill / unseen fields (enemy weight 0.5) plus a kill bonus
gated on strict local superiority. Its combat block is the only
move on the board issued without the survival check: when a foe
stands within COMBAT_RANGE and the greedy fields point at it, the
ant steps in even alone -- 1v1 trades the ant away, 1vN just dies.
Food, guard, muster, reinforce, and explore all pass is_safe; only
combat skips it.

Greedy3 gates the combat step on is_safe (strict superiority,
zero foes in range, or equal numbers with EQUAL_TRADE_NEAR friends
nearby). Wins still advance; suicides hold back and fall through
to muster, reinforce, and explore.

Proves, on fixed boards before the bot code lands:
(a) lone-ant boards where base steps into attack range outnumbered
    and tuned holds back (steps to a safe square instead),
(b) packed 2v1 boards advance byte-identically (kill bonus kept),
(c) equal-trade-with-crowd boards advance byte-identically,
(d) quiet boards (food, guard, explore, walk-off) byte-identical,
(e) a crowded full turn still runs <1s.
"""

import os
import sys
import time
from types import ModuleType
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Greedy2 as Base  # noqa: E402
import Greedy3 as Tuned  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
ATTACK_R2 = 5


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
        self.attackradius2 = ATTACK_R2
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


def make_bot(mod: ModuleType) -> Any:
    if mod is Tuned:
        return Tuned.Greedy3()
    return Base.Greedy2()


def run_turn(
    mod: ModuleType,
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    make_bot(mod).do_turn(fake)
    return fake.orders


def flat_sq(a: Loc, b: Loc) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def post_move(start: Loc, direction: str) -> Loc:
    dr, dc = AIM[direction]
    return ((start[0] + dr) % ROWS, (start[1] + dc) % COLS)


def is_outnumbered(dest: Loc, own_count: int, enemies: list[Loc]) -> bool:
    """True when dest stands in attack range of a foe with no local edge.

    Mirrors the bot's survival rule for a lone ant: one foe in range
    and nobody backing the move means the step trades the ant away
    (1v1) or just dies (1vN). A strict edge (more ants than foes in
    range) is winnable, not outnumbered.
    """
    foes = sum(1 for e in enemies if flat_sq(dest, e) <= ATTACK_R2)
    return foes >= 1 and own_count <= foes


# one-idea discipline --------------------------------------------------------


def test_constants_identical_to_base() -> None:
    for name in (
        "W_FOOD",
        "W_ENEMY",
        "W_HILL",
        "W_UNSEEN",
        "KILL_BONUS",
        "FIELD_HORIZON",
        "COMBAT_RANGE",
        "EQUAL_TRADE_NEAR",
        "CLUSTER_R",
        "DENIAL_ENEMIES",
        "DENIAL_CLAIMS",
    ):
        assert getattr(Tuned, name) == getattr(Base, name), name
    assert Tuned.WEIGHTS == Base.WEIGHTS


# (a) suicides hold back ------------------------------------------------------
#
# Lone ant (10,10), foe (10,12), no food and no hills: combat fires
# (foe within 8) and the enemy field points east. Base steps onto
# (10,11) -- attack range (sq 1) at 1v1, trading the ant away. Tuned
# must not step into an outnumbered attack-range square; it falls
# through to safe explore instead.


def test_base_steps_into_lone_1v1() -> None:
    orders = run_turn(Base, [(10, 10)], [(10, 12)])
    assert orders[0] == ((10, 10), "e")
    dest = post_move(*orders[0])
    assert is_outnumbered(dest, 1, [(10, 12)])


def test_tuned_holds_back_from_lone_1v1() -> None:
    base_orders = run_turn(Base, [(10, 10)], [(10, 12)])
    tuned_orders = run_turn(Tuned, [(10, 10)], [(10, 12)])
    assert tuned_orders != base_orders
    first = [o for o in tuned_orders if o[0] == (10, 10)]
    assert first, "probing ant must still move or the test is vacuous"
    dest = post_move(*first[0])
    assert not is_outnumbered(dest, 1, [(10, 12)])


def test_tuned_holds_back_from_1v2() -> None:
    # Two foes: stepping east dies outright. Base still marches in;
    # tuned refuses every outnumbered attack-range square. All four
    # neighbors touch a foe, so the ant holds (no order at all).
    enemies = [(10, 12), (11, 11)]
    base_orders = run_turn(Base, [(10, 10)], enemies)
    assert base_orders[0] == ((10, 10), "e")
    assert is_outnumbered(post_move(*base_orders[0]), 1, enemies)
    tuned_orders = run_turn(Tuned, [(10, 10)], enemies)
    assert tuned_orders != base_orders
    for start, direction in tuned_orders:
        assert start != (10, 10) or not is_outnumbered(
            post_move(start, direction), 1, enemies
        )
    assert all(start != (10, 10) for start, _ in tuned_orders)


def test_tuned_refuses_unsafe_step_with_hills_present() -> None:
    # Foe (2,5) sits 3 from ant (5,5) with a remembered hill at
    # (2,2): base's combat step marches north into a lone 1v1 while
    # tuned refuses it and falls through to the hill march instead.
    mine = [(5, 5)]
    enemies = [(2, 5)]
    base_orders = run_turn(Base, mine, enemies, None, None, [(2, 2)], None)
    assert base_orders[0][1] == "n"
    assert is_outnumbered(post_move(*base_orders[0]), 1, enemies)
    tuned_orders = run_turn(Tuned, mine, enemies, None, None, [(2, 2)], None)
    assert tuned_orders != base_orders
    for start, direction in tuned_orders:
        assert not is_outnumbered(post_move(start, direction), 1, enemies)


def test_tuned_keeps_weak_lure_retreat_and_food_claim() -> None:
    # Greedy2's weak-lure board: ant (10,7) holds the food claim at
    # (10,8) while ant (10,10) faces the foe. The weak lure already
    # turns (10,10) west to safety through combat, and the gate
    # agrees that square is safe -- so the whole order list stays
    # byte-identical (retreat kept, food claim kept).
    mine = [(10, 10), (10, 7)]
    enemies = [(10, 12)]
    foods = [(10, 8)]
    base_orders = run_turn(Base, mine, enemies, foods)
    assert base_orders[0] == ((10, 10), "w")
    assert ((10, 7), "e") in base_orders
    assert run_turn(Tuned, mine, enemies, foods) == base_orders


def test_tuned_never_closer_on_suicide_boards() -> None:
    # On every lone-ant suicide board, the tuned ant ends no closer
    # to its nearest foe than it started (holds back or retreats).
    probe = FakeAnts([(10, 10)], [(10, 12)])
    for mine, enemies in (
        ([(10, 10)], [(10, 12)]),
        ([(10, 10)], [(10, 12), (11, 11)]),
        ([(10, 10)], [(10, 13), (9, 12)]),
    ):
        tuned_orders = run_turn(Tuned, mine, enemies)
        first = [o for o in tuned_orders if o[0] == mine[0]]
        after = post_move(*first[0]) if first else mine[0]
        before = min(probe.distance(mine[0], e) for e in enemies)
        now = min(probe.distance(after, e) for e in enemies)
        assert now >= before


# (b) winners still advance ----------------------------------------------------


def test_packed_2v1_advance_byte_identical_to_base() -> None:
    # Strict superiority (2v1 at the step): both march east onto
    # (5,6) with the exact same full order list.
    mine = [(5, 5), (5, 4)]
    enemies = [(5, 7)]
    assert run_turn(Base, mine, enemies)[0] == ((5, 5), "e")
    assert run_turn(Tuned, mine, enemies) == run_turn(Base, mine, enemies)


def test_packed_3v2_advance_byte_identical_to_base() -> None:
    mine = [(5, 5), (5, 4), (6, 5)]
    enemies = [(5, 7), (6, 7)]
    assert run_turn(Tuned, mine, enemies) == run_turn(Base, mine, enemies)
    assert run_turn(Base, mine, enemies)[0] == ((5, 5), "e")


# (c) equal trades with a crowd still go ----------------------------------------


def test_equal_trade_with_crowd_byte_identical_to_base() -> None:
    # Ten friends within 10 steps but none in attack range of the
    # step: the equal-trade rule calls it safe, so both step east.
    crowd = [
        (10, 4),
        (10, 5),
        (11, 4),
        (11, 5),
        (9, 4),
        (9, 5),
        (12, 4),
        (12, 5),
        (8, 4),
        (8, 5),
    ]
    mine = [(10, 10)] + crowd
    enemies = [(10, 12)]
    assert run_turn(Base, mine, enemies)[0] == ((10, 10), "e")
    assert run_turn(Tuned, mine, enemies) == run_turn(Base, mine, enemies)


# (d) quiet boards byte-identical -------------------------------------------------


def test_quiet_boards_byte_identical_to_base() -> None:
    # Food claims, far-foe explore, guard, muster, and walk-off
    # never touch the combat gate, so orders match base exactly.
    boards = [
        ([(0, 0), (0, 19)], [], [(0, 1), (0, 18)], None, None, None),
        ([(0, 0)], [], None, None, [(10, 10)], None),
        ([(5, 5)], [(15, 15)], None, None, None, None),
        ([(3, 3)], [], None, None, None, [(3, 3)]),
    ]
    for mine, enemies, foods, water, enemy_hills, my_hills in boards:
        assert run_turn(
            Tuned, mine, enemies, foods, water, enemy_hills, my_hills
        ) == run_turn(Base, mine, enemies, foods, water, enemy_hills, my_hills)


# (e) speed -----------------------------------------------------------------------


def test_crowded_full_turn_under_one_second() -> None:
    mine = [(r, c) for r in range(0, 20, 2) for c in range(0, 20, 2)][:60]
    enemies = [(r, c) for r in range(1, 20, 2) for c in range(1, 20, 2)][:60]
    foods = [(r, c) for r in range(0, 20, 3) for c in range(0, 20, 5)][:40]
    water = {(10, c) for c in range(20) if c not in (9, 10)}
    start = time.perf_counter()
    orders = run_turn(Tuned, mine, enemies, foods, water, [(19, 19)], [(0, 0)])
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(orders) > 0


def test_combat_heavy_turn_under_one_second() -> None:
    # Every ant starts in combat range: the gate runs on each one.
    mine = [(10 + (i // 10), 8 + (i % 10)) for i in range(40)]
    enemies = [(10 + (i // 10), 12 + (i % 4)) for i in range(16)]
    start = time.perf_counter()
    orders = run_turn(Tuned, mine, enemies)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(orders) > 0
