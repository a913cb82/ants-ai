#!/usr/bin/env python
"""Softmax8 entry tests: sticky owner memory (stdlib only).

One idea: the Softmax4 owner gate reads the CURRENTLY visible
owner count, so mid-game owner collapse (rivals dying elsewhere,
or a local skirmish showing one raider) flips a crowd game into
the deterministic duel-press branch, which donates parity tempo.
Softmax8 fixes the sensing, not the split: it remembers every
distinct enemy owner ever seen (ants plus hills) and gates on
the sticky maximum. Once a crowd, always a crowd; a true duel
never shows a second owner, so it keeps the deterministic press.

Pins:

(a) duel stays duel: single-owner sightings across many turns
    press parity deterministically (hostile coins agree, no draw);
(b) collapse keeps the coin: after owners {1, 2} were seen, a
    later single-owner contested fight still flips with the coin
    (hostile coins disagree) — the base gate would press;
(c) hills reveal rivals: a second owner seen only on a hill
    locks the crowd branch too;
(d) memory never forgets: seen_owners only grows;
(e) economy pins unchanged; full turn <1s.
"""

import os
import random
import sys
import time
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Softmax8 as SM  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
R2 = 5


class FakeAnts:
    """Minimal ants.Ants surface used by Softmax8.do_turn."""

    def __init__(
        self,
        mine: list[Loc],
        enemies: list[Loc],
        foods: list[Loc] | None = None,
        water: set[Loc] | None = None,
        enemy_hills: list[Loc] | None = None,
        my_hills: list[Loc] | None = None,
        owners: list[int] | None = None,
        hill_owners: list[int] | None = None,
    ) -> None:
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = R2
        self._mine = list(mine)
        self._enemies = list(enemies)
        self._owners = list(owners) if owners is not None else [1] * len(enemies)
        assert len(self._owners) == len(self._enemies)
        self._foods = list(foods or [])
        self._water = set(water or set())
        self._enemy_hills = list(enemy_hills or [])
        hills_n = len(self._enemy_hills)
        self._hill_owners = (
            list(hill_owners) if hill_owners is not None else [1] * hills_n
        )
        assert len(self._hill_owners) == hills_n
        self._my_hills = list(my_hills or [])
        self.orders: list[tuple[Loc, str]] = []

    def food(self) -> list[Loc]:
        return list(self._foods)

    def my_ants(self) -> list[Loc]:
        return list(self._mine)

    def enemy_ants(self) -> list[tuple[Loc, int]]:
        return list(zip(self._enemies, self._owners, strict=True))

    def enemy_hills(self) -> list[tuple[Loc, int]]:
        return list(zip(self._enemy_hills, self._hill_owners, strict=True))

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


def play(
    bot: object,
    mine: list[Loc],
    enemies: list[Loc],
    owners: list[int] | None = None,
    **kw: object,
) -> FakeAnts:
    fake = FakeAnts(mine, enemies, owners=owners, **kw)  # type: ignore[arg-type]
    bot.do_turn(fake)  # type: ignore[attr-defined]
    return fake


class _AlwaysHigh(random.Random):
    """Hostile coin: random() sticks near 1, forcing passive in zone."""

    _randbelow = random.Random._randbelow_with_getrandbits  # type: ignore[attr-defined]

    def random(self) -> float:
        return 0.999999


class _AlwaysLow(random.Random):
    """Hostile coin: random() sticks near 0, forcing aggressive in zone."""

    _randbelow = random.Random._randbelow_with_getrandbits  # type: ignore[attr-defined]

    def random(self) -> float:
        return 0.0


def _play_hostile(
    bot: object,
    mine: list[Loc],
    enemies: list[Loc],
    hostile: type[random.Random],
    **kw: object,
) -> FakeAnts:
    with mock.patch.object(SM.random, "Random", hostile):
        return play(bot, mine, enemies, **kw)  # type: ignore[arg-type]


def test_contest_half_documented() -> None:
    assert SM.CONTEST_HALF == 0.2


def test_duel_stays_deterministic_across_turns() -> None:
    # True duel: only owner 1 ever visible. Contested 1v1 must gate
    # deterministically on every turn — hostile coins agree with
    # each other and with the plain run, turn after turn.
    for turn in range(3):
        _ = turn
        low_bot, high_bot, plain_bot = SM.Softmax8(), SM.Softmax8(), SM.Softmax8()
        for bot in (low_bot, high_bot, plain_bot):
            for _ in range(3):
                play(bot, [(5, 5)], [(5, 8)], owners=[1])
        low = _play_hostile(low_bot, [(5, 5)], [(5, 8)], _AlwaysLow, owners=[1])
        high = _play_hostile(high_bot, [(5, 5)], [(5, 8)], _AlwaysHigh, owners=[1])
        plain = play(plain_bot, [(5, 5)], [(5, 8)], owners=[1])
        assert low.orders == high.orders == plain.orders


def test_collapse_keeps_crowd_coin() -> None:
    # Owners {1, 2} seen on turns 1-2; turn 3 shows the same
    # contested 2v2 owned by rival 1 alone (rival 2's raider died,
    # rival 1 reinforced). Sticky memory keeps the crowd coin, so
    # hostile coins must disagree — the instantaneous gate would
    # press deterministically.
    for hostile, other in ((_AlwaysLow, _AlwaysHigh), (_AlwaysHigh, _AlwaysLow)):
        bot_a, bot_b = SM.Softmax8(), SM.Softmax8()
        for bot in (bot_a, bot_b):
            for _ in range(2):
                play(bot, [(5, 5), (5, 6)], [(5, 8), (5, 9)], owners=[1, 2])
        assert bot_a.seen_owners == {1, 2}
        assert SM.is_contested(2, 2) is True
        low = _play_hostile(
            bot_a, [(5, 5), (5, 6)], [(5, 8), (5, 9)], hostile, owners=[1, 1]
        )
        high = _play_hostile(
            bot_b, [(5, 5), (5, 6)], [(5, 8), (5, 9)], other, owners=[1, 1]
        )
        assert low.orders != high.orders


def test_collapse_coin_is_seeded_reproducible() -> None:
    runs = []
    for _ in range(2):
        bot = SM.Softmax8()
        for _ in range(2):
            play(bot, [(5, 5), (5, 6)], [(5, 8), (5, 9)], owners=[1, 2])
        runs.append(play(bot, [(5, 5), (5, 6)], [(5, 8), (5, 9)], owners=[1, 1]).orders)
    assert runs[0] == runs[1]


def test_hill_sighting_locks_crowd() -> None:
    # Second owner seen only as a hill still locks crowd shape: a
    # later single-owner contested fight flips with the coin.
    bot_a, bot_b = SM.Softmax8(), SM.Softmax8()
    for bot in (bot_a, bot_b):
        play(
            bot,
            [(5, 5), (5, 6)],
            [(5, 8), (5, 9)],
            owners=[1, 1],
            enemy_hills=[(15, 15)],
            hill_owners=[2],
        )
        play(bot, [(5, 5), (5, 6)], [(5, 8), (5, 9)], owners=[1, 1])
    assert bot_a.seen_owners == {1, 2}
    low = _play_hostile(
        bot_a, [(5, 5), (5, 6)], [(5, 8), (5, 9)], _AlwaysLow, owners=[1, 1]
    )
    high = _play_hostile(
        bot_b, [(5, 5), (5, 6)], [(5, 8), (5, 9)], _AlwaysHigh, owners=[1, 1]
    )
    assert low.orders != high.orders


def test_memory_never_forgets() -> None:
    bot = SM.Softmax8()
    assert bot.seen_owners == set()
    play(bot, [(5, 5)], [(5, 8)], owners=[3])
    assert bot.seen_owners == {3}
    play(bot, [(5, 5)], [], owners=[])
    assert bot.seen_owners == {3}
    play(bot, [(5, 5)], [(5, 8)], owners=[7])
    assert bot.seen_owners == {3, 7}


def test_decisive_fights_ignore_coin_either_shape() -> None:
    # Sticky or fresh, decisive odds never flip: hostile coins
    # agree with the plain run whether the bot is a fresh duel
    # (2v1 press) or a crowd-locked underdog (1v2 refuse).
    duel = SM.Softmax8()
    plain_duel = play(duel, [(5, 5), (5, 6)], [(5, 8)], owners=[1])
    for hostile in (_AlwaysLow, _AlwaysHigh):
        duel2 = SM.Softmax8()
        assert (
            _play_hostile(duel2, [(5, 5), (5, 6)], [(5, 8)], hostile, owners=[1]).orders
            == play(SM.Softmax8(), [(5, 5), (5, 6)], [(5, 8)], owners=[1]).orders
        )
    assert plain_duel.orders
    locked = SM.Softmax8()
    play(locked, [(5, 5)], [(5, 8), (5, 9)], owners=[1, 2])
    plain_locked = play(SM.Softmax8(), [(5, 5)], [(5, 8), (5, 9)], owners=[1, 2])
    locked2 = SM.Softmax8()
    play(locked2, [(5, 5)], [(5, 8), (5, 9)], owners=[1, 2])
    for hostile in (_AlwaysLow, _AlwaysHigh):
        locked3 = SM.Softmax8()
        play(locked3, [(5, 5)], [(5, 8), (5, 9)], owners=[1, 2])
        assert (
            _play_hostile(
                locked3, [(5, 5)], [(5, 8), (5, 9)], hostile, owners=[1, 2]
            ).orders
            == plain_locked.orders
        )
    assert SM.decide_aggression(1, 2, _AlwaysLow(0), n_owners=2) is False
    assert SM.decide_aggression(2, 1, _AlwaysHigh(0), n_owners=1) is True


def test_non_gate_boards_match_base() -> None:
    def run_turn(
        mine: list[Loc],
        enemies: list[Loc],
        **kw: object,
    ) -> FakeAnts:
        return play(SM.Softmax8(), mine, enemies, **kw)  # type: ignore[arg-type]

    food = run_turn([(5, 5), (15, 15)], [], foods=[(5, 8), (15, 12)])
    assert sorted(food.orders) == [((5, 5), "e"), ((15, 15), "w")]
    muster = run_turn([(5, 5), (6, 6)], [], enemy_hills=[(15, 15)])
    assert sorted(muster.orders) == [((5, 5), "n"), ((6, 6), "n")]
    guard = run_turn([(10, 10), (12, 12)], [(10, 15)], my_hills=[(10, 10)])
    assert sorted(guard.orders) == [((10, 10), "n"), ((12, 12), "n")]


def test_full_turn_under_1s_crowded() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [(3, 3), (17, 17), (10, 2)]
    owners = [(i % 9) + 1 for i in range(30)]
    start = time.perf_counter()
    fake = play(
        SM.Softmax8(),
        mine,
        foes,
        foods=foods,
        enemy_hills=[(15, 15)],
        my_hills=[(10, 10)],
        owners=owners,
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(fake.orders) > 0
