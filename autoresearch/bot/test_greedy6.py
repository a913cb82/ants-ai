#!/usr/bin/env python
"""Reinforcement-race bravery tests (Greedy6 entry).

Base is Greedy3: every combat step passes is_safe (strict local
superiority, zero foes in range, or equal numbers backed by
EQUAL_TRADE_NEAR friends nearby). The gate refuses every lone
1v1 -- even when a teammate trails one step behind and the foe
stands alone. Under the engine's focus combat, a 1v1 that trades
is still won the next turn when backup arrives first: the duel
geometry, not the objective, decides whether the trade is brave.
Greedy3 cannot see that; Greedy4's answer (Greedy4.py) gates takes
on food/hill proximity instead -- a different mechanism this entry
must not reuse.

Greedy6 adds one mechanism -- reinforcement-race bravery: an
even-trade combat step (ours == theirs >= 1, no strict edge, no
crowd backing) is allowed iff a non-moving friend stands within
SUPPORT_R of the destination (backup wins the race) and no
uncounted foe stands within SUPPORT_R + 1 (no enemy backup joins
next turn). No food, no hills, no objectives -- pure duel
geometry. 1vN is still always refused, isolated 1v1s still hold,
shadowed 1v1s still hold, and every non-combat path keeps the
full is_safe gate.

Proves, on fixed boards before the bot code lands:
(a) supported duel: 1v1 with pincer support at (10,14) -- beyond
    the foe, off every candidate square's attack range (no kill
    bonus anywhere) but inside SUPPORT_R of the step -- and a lone
    foe. Base holds back, tuned steps in (even trade, backup
    coming). Only the gate differs, so the take is pure geometry.
(b) isolated 1v1 -- tuned == base (holds),
(c) shadowed 1v1 (second foe lurking) -- tuned == base (holds),
(d) 1vN even with support -- still refused, tuned == base,
(e) packed wins / quiet boards byte-identical,
(f) a crowded full turn still runs <1s.
"""

import os
import sys
import time
from types import ModuleType
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Greedy3 as Base  # noqa: E402
import Greedy6 as Tuned  # noqa: E402

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
        return Tuned.Greedy6()
    return Base.Greedy3()


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


def tor_dist(a: Loc, b: Loc) -> int:
    probe = FakeAnts([], [])
    return probe.distance(a, b)


def sides(dest: Loc, mover: Loc, own: list[Loc], foes: list[Loc]) -> tuple[int, int]:
    return Tuned.count_sides(dest, mover, own, foes, flat_sq, ATTACK_R2)


# one-idea discipline --------------------------------------------------------


def test_constants_identical_to_base_plus_support_radius() -> None:
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
    assert Tuned.SUPPORT_R == 3


# mechanism units: brave_support is pure duel geometry -------------------------
#
# No food, no hills, no objectives anywhere in the signature -- only
# ant positions. Greedy4's brave_even_trade takes foods and hills;
# this one must not.


def test_supported_lone_1v1_is_brave() -> None:
    # Ant (10,10) steps east onto (10,11): 1v1, friend trailing at
    # (10,8) within SUPPORT_R of the step, foe (10,12) alone.
    assert (
        Tuned.brave_support(
            (10, 11),
            (10, 10),
            [(10, 10), (10, 8)],
            [(10, 12)],
            tor_dist,
            flat_sq,
            ATTACK_R2,
        )
        is True
    )


def test_isolated_1v1_is_not_brave() -> None:
    # Same step with no trailing friend: nobody wins the race.
    assert (
        Tuned.brave_support(
            (10, 11),
            (10, 10),
            [(10, 10)],
            [(10, 12)],
            tor_dist,
            flat_sq,
            ATTACK_R2,
        )
        is False
    )


def test_shadowed_1v1_is_not_brave() -> None:
    # Friend trails, but a second foe lurks at (10,15) -- inside
    # next-turn joining range of the step. Their backup cancels ours.
    assert (
        Tuned.brave_support(
            (10, 11),
            (10, 10),
            [(10, 10), (10, 8)],
            [(10, 12), (10, 15)],
            tor_dist,
            flat_sq,
            ATTACK_R2,
        )
        is False
    )


def test_far_shadow_does_not_veto() -> None:
    # Second foe at (10,16), too far to join next turn: brave again.
    assert tor_dist((10, 11), (10, 16)) > Tuned.SUPPORT_R + 1
    assert (
        Tuned.brave_support(
            (10, 11),
            (10, 10),
            [(10, 10), (10, 8)],
            [(10, 12), (10, 16)],
            tor_dist,
            flat_sq,
            ATTACK_R2,
        )
        is True
    )


def test_uneven_trades_never_brave() -> None:
    # 1vN: outnumbered, not even -- geometry cannot save it.
    assert (
        Tuned.brave_support(
            (10, 11),
            (10, 10),
            [(10, 10), (10, 8)],
            [(10, 12), (11, 11)],
            tor_dist,
            flat_sq,
            ATTACK_R2,
        )
        is False
    )
    # Strict win: not an even trade, needs no bravery.
    assert (
        Tuned.brave_support(
            (5, 6),
            (5, 5),
            [(5, 5), (5, 4)],
            [(5, 7)],
            tor_dist,
            flat_sq,
            ATTACK_R2,
        )
        is False
    )
    # No foe in range at all: nothing to be brave about.
    assert (
        Tuned.brave_support(
            (10, 11),
            (10, 10),
            [(10, 10), (10, 8)],
            [(0, 0)],
            tor_dist,
            flat_sq,
            ATTACK_R2,
        )
        is False
    )


def test_support_radius_boundary() -> None:
    # Friend exactly at SUPPORT_R: brave. One step beyond: not.
    assert tor_dist((10, 11), (10, 8)) == Tuned.SUPPORT_R
    assert (
        Tuned.brave_support(
            (10, 11),
            (10, 10),
            [(10, 10), (10, 8)],
            [(10, 12)],
            tor_dist,
            flat_sq,
            ATTACK_R2,
        )
        is True
    )
    assert tor_dist((10, 11), (10, 7)) == Tuned.SUPPORT_R + 1
    assert (
        Tuned.brave_support(
            (10, 11),
            (10, 10),
            [(10, 10), (10, 7)],
            [(10, 12)],
            tor_dist,
            flat_sq,
            ATTACK_R2,
        )
        is False
    )


# (a) supported duel: base holds, tuned steps in --------------------------------
#
# No food and no hills on the board: Greedy4's objective gate would
# hold here too, so any take is pure geometry. Probing ant
# (10,10), pincer support at (10,14), lone foe (10,12).


def test_base_holds_supported_duel() -> None:
    mine = [(10, 10), (10, 14)]
    enemies = [(10, 12)]
    orders = run_turn(Base, mine, enemies)
    first = [o for o in orders if o[0] == (10, 10)]
    assert first, "probing ant must still move or the test is vacuous"
    assert first[0] != ((10, 10), "e"), "base must refuse the even 1v1"


def test_tuned_takes_supported_duel() -> None:
    mine = [(10, 10), (10, 14)]
    enemies = [(10, 12)]
    orders = run_turn(Tuned, mine, enemies)
    assert ((10, 10), "e") in orders
    assert orders != run_turn(Base, mine, enemies)
    # The take is exactly even -- never outnumbered.
    ours, theirs = sides((10, 11), (10, 10), mine, enemies)
    assert (ours, theirs) == (1, 1)


def test_supported_take_needs_no_objectives() -> None:
    # Same geometry with food and an enemy hill far away: the take
    # must not depend on them (remove them, same probing order).
    mine = [(10, 10), (10, 14)]
    enemies = [(10, 12)]
    plain = [o for o in run_turn(Tuned, mine, enemies) if o[0] == (10, 10)]
    dressed = [
        o
        for o in run_turn(Tuned, mine, enemies, [(0, 0)], None, [(0, 19)], None)
        if o[0] == (10, 10)
    ]
    assert plain == dressed == [((10, 10), "e")]


# (b/c/d) refusal geometries stay byte-identical ----------------------------------


def test_isolated_1v1_byte_identical_to_base() -> None:
    mine = [(10, 10)]
    enemies = [(10, 12)]
    assert run_turn(Tuned, mine, enemies) == run_turn(Base, mine, enemies)
    assert ((10, 10), "e") not in run_turn(Tuned, mine, enemies)


def test_shadowed_1v1_byte_identical_to_base() -> None:
    mine = [(10, 10), (10, 14)]
    enemies = [(10, 12), (10, 15)]
    assert run_turn(Tuned, mine, enemies) == run_turn(Base, mine, enemies)
    assert ((10, 10), "e") not in run_turn(Tuned, mine, enemies)


def test_1v2_with_support_still_refused() -> None:
    # Two foes in range of the step: outnumbered, not even.
    mine = [(10, 10), (10, 14)]
    enemies = [(10, 12), (11, 11)]
    assert run_turn(Tuned, mine, enemies) == run_turn(Base, mine, enemies)
    assert ((10, 10), "e") not in run_turn(Tuned, mine, enemies)


def test_supported_take_never_steps_outnumbered() -> None:
    # Sweep small duel geometries ant by ant: any tuned order that
    # differs from base's order for the SAME ant must land on a
    # brave square (exactly even, backed, unshadowed) -- never
    # outnumbered, never a wild lunge.
    ants = [(10, 10), (10, 14), (10, 7), (9, 10)]
    foes = [[(10, 12)], [(10, 12), (10, 15)], [(10, 12), (0, 0)], [(9, 12)]]
    for extra in ([], [(10, 14)], [(10, 14), (9, 10)]):
        mine = [ants[0]] + extra
        for enemies in foes:
            base_orders = dict(run_turn(Base, mine, enemies))
            tuned_orders = dict(run_turn(Tuned, mine, enemies))
            for start in mine:
                if tuned_orders.get(start) == base_orders.get(start):
                    continue
                assert start in tuned_orders, (mine, enemies, tuned_orders)
                dest = post_move(start, tuned_orders[start])
                assert Tuned.brave_support(
                    dest,
                    start,
                    mine,
                    enemies,
                    tor_dist,
                    flat_sq,
                    ATTACK_R2,
                ), (mine, enemies, tuned_orders)


# (e) wins and quiet boards byte-identical ------------------------------------------


def test_packed_wins_byte_identical_to_base() -> None:
    boards = [
        ([(5, 5), (5, 4)], [(5, 7)]),
        ([(5, 5), (5, 4), (6, 5)], [(5, 7), (6, 7)]),
    ]
    for mine, enemies in boards:
        assert run_turn(Base, mine, enemies)[0] == ((5, 5), "e")
        assert run_turn(Tuned, mine, enemies) == run_turn(Base, mine, enemies)


def test_equal_trade_with_crowd_byte_identical_to_base() -> None:
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


def test_quiet_boards_byte_identical_to_base() -> None:
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


# (f) speed ---------------------------------------------------------------------------


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
    mine = [(10 + (i // 10), 8 + (i % 10)) for i in range(40)]
    enemies = [(10 + (i // 10), 12 + (i % 4)) for i in range(16)]
    start = time.perf_counter()
    orders = run_turn(Tuned, mine, enemies)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(orders) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
