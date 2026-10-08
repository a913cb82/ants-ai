#!/usr/bin/env python
"""Swarm entry tests: reserves reinforce joined battles.

Swarm keeps the champion Crowd wiring byte-identical (denial food,
pack-gated seek, committed-join, grinder 1v1, off-hill screen,
10-gate equal trades, crowd fearless, flood muster, least-visited
explore) except one new mechanism in the explore slot: a packed ant
with no food move, no guard move, no seek foe, and no remembered
hill reinforces the nearest JOINED battle (a foe drawing 2+
commitments this turn) within REINFORCE_RANGE steps, via the normal
safe step. Everything else explores exactly as champion.

No engine games. Boards run on FakeAnts; Crowd.py is the parity
baseline (imported, never modified).
"""

import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Crowd as CP  # noqa: E402  parity baseline, champion wiring
import Swarm as SW  # noqa: E402  entry under test

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
        rows: int = ROWS,
        cols: int = COLS,
        attackradius2: int = 5,
    ) -> None:
        self.rows = rows
        self.cols = cols
        self.attackradius2 = attackradius2
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


def run_swarm(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    SW.Swarm().do_turn(fake)
    return fake.orders


def run_crowd(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    CP.Crowd().do_turn(fake)
    return fake.orders


# Real engine states, reconstructed from replay move strings: a
# duel-map mid-game (8v5 on 24x24) and an FFA mid-game (35v35 on
# 52x164). Both bots see identical inputs; the entry must match
# the champion order-for-order on real distributions.
_DUEL_P0 = [(11, 4), (11, 5), (11, 7), (11, 9), (12, 5), (15, 6), (22, 12), (23, 14)]
_DUEL_P1 = [(8, 19), (11, 18), (11, 19), (12, 20), (19, 12)]
_DUEL_FOOD = [(10, 11), (11, 11), (12, 12), (13, 12)]
_FFA_P0 = [
    (0, 160),
    (2, 161),
    (3, 161),
    (6, 141),
    (8, 149),
    (8, 154),
    (9, 147),
    (9, 151),
    (9, 152),
    (9, 153),
    (9, 156),
    (10, 149),
    (11, 1),
    (11, 6),
    (11, 152),
    (12, 149),
    (13, 6),
    (13, 15),
    (18, 2),
    (18, 16),
    (19, 162),
    (20, 10),
    (24, 1),
    (24, 9),
    (24, 159),
    (27, 2),
    (29, 1),
    (32, 13),
    (33, 19),
    (38, 10),
    (42, 2),
    (43, 8),
    (44, 1),
    (50, 162),
    (51, 2),
]
_FFA_P1 = [
    (1, 125),
    (3, 124),
    (4, 136),
    (8, 143),
    (12, 133),
    (14, 128),
    (16, 122),
    (20, 128),
    (22, 130),
    (27, 119),
    (28, 119),
    (29, 120),
    (30, 125),
    (32, 99),
    (34, 107),
    (34, 108),
    (34, 110),
    (34, 112),
    (34, 113),
    (34, 126),
    (35, 112),
    (35, 125),
    (36, 106),
    (37, 111),
    (37, 129),
    (38, 109),
    (38, 135),
    (39, 128),
    (44, 125),
    (44, 137),
    (45, 121),
    (46, 133),
    (48, 124),
    (50, 118),
    (51, 133),
]


def _run_sized(
    bot: Any,
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc],
    rows: int,
    cols: int,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, rows=rows, cols=cols)
    bot.do_turn(fake)
    return fake.orders


def test_real_states_match_champion() -> None:
    # Duel mid-game, both perspectives: identical orders.
    for me, foe in ((_DUEL_P0, _DUEL_P1), (_DUEL_P1, _DUEL_P0)):
        swarm = _run_sized(SW.Swarm(), me, foe, _DUEL_FOOD, 24, 24)
        crowd = _run_sized(CP.Crowd(), me, foe, _DUEL_FOOD, 24, 24)
        assert swarm == crowd
    assert _run_sized(SW.Swarm(), _DUEL_P0, _DUEL_P1, _DUEL_FOOD, 24, 24) != []
    # FFA mid-game, both perspectives: identical orders.
    for me, foe in ((_FFA_P0, _FFA_P1), (_FFA_P1, _FFA_P0)):
        swarm = _run_sized(SW.Swarm(), me, foe, [], 52, 164)
        crowd = _run_sized(CP.Crowd(), me, foe, [], 52, 164)
        assert swarm == crowd


# Shared fixture: pair A(5,5)/B(5,9) with fillers packs both and
# joins them on F(5,7); reserve R(5,16) is packed, has no foe
# within SEEK_RANGE (nearest is F at 9), no food, no hills.
_PAIR = [(5, 5), (5, 9), (5, 3), (5, 11)]
_FOE = [(5, 7)]
_RESERVE = (5, 16)


def test_reinforce_range_constant_sits_past_seek() -> None:
    # The reserve band starts where seek stops: SEEK_RANGE < 12.
    assert SW.SEEK_RANGE == 8
    assert SW.REINFORCE_RANGE == 12
    assert SW.REINFORCE_RANGE > SW.SEEK_RANGE


def test_reserve_reinforces_joined_battle() -> None:
    # The pair joins on F (both step into contact); the reserve at
    # distance 9 reinforces west toward F instead of exploring
    # north as champion.
    mine = _PAIR + [_RESERVE]
    orders = run_swarm(mine, _FOE)
    by_ant = dict(orders)
    assert by_ant[(5, 5)] == "e"
    assert by_ant[(5, 9)] == "w"
    assert by_ant[_RESERVE] == "w"
    crowd = run_crowd(mine, _FOE)
    assert dict(crowd)[_RESERVE] == "n"
    assert orders != crowd
    probe = FakeAnts(mine, _FOE)
    assert probe.distance((5, 5), (5, 7)) == 2
    assert probe.distance(_RESERVE, (5, 7)) == 9
    assert probe.distance(probe.destination(_RESERVE, "w"), (5, 7)) == 8


def test_no_reinforce_without_joined_battle() -> None:
    # One commitment is no join: the packed reserve explores north
    # exactly as champion.
    mine = [(5, 5), (5, 3), (5, 11), (5, 1), (5, 16), (5, 13)]
    orders = run_swarm(mine, _FOE)
    assert orders == run_crowd(mine, _FOE)
    assert dict(orders)[(5, 16)] == "n"


def test_food_claim_blocks_reinforce() -> None:
    # A claimed reserve eats adjacent food instead of reinforcing,
    # exactly as champion.
    mine = _PAIR + [_RESERVE]
    orders = run_swarm(mine, _FOE, foods=[(5, 17)])
    assert orders == run_crowd(mine, _FOE, foods=[(5, 17)])
    assert dict(orders)[_RESERVE] == "e"


def test_muster_blocks_reinforce() -> None:
    # A remembered hill musters instead of reinforcing, exactly as
    # champion: the reserve never deserts the march.
    mine = _PAIR + [_RESERVE]
    orders = run_swarm(mine, _FOE, enemy_hills=[(15, 16)])
    assert orders == run_crowd(mine, _FOE, enemy_hills=[(15, 16)])
    assert dict(orders)[_RESERVE] == "n"


def test_far_battle_explores_as_champion() -> None:
    # A joined battle 20 steps out is past REINFORCE_RANGE: the
    # reserve explores exactly as champion.
    mine = [(15, 13), (15, 17), (15, 11), (15, 19), (5, 5)]
    foes = [(15, 15)]
    orders = run_swarm(mine, foes)
    assert orders == run_crowd(mine, foes)
    assert dict(orders)[(5, 5)] == "n"


def test_guard_blocks_reinforce() -> None:
    # A threatened hill consumes every ant (hold + screen), so the
    # reserve never deserts guard duty: exactly as champion.
    mine = [(10, 8), (10, 11), (5, 5), (5, 9), (5, 3), (5, 11)]
    foes = [(10, 16), (5, 7)]
    orders = run_swarm(mine, foes, my_hills=[(10, 10)])
    assert orders == run_crowd(mine, foes, my_hills=[(10, 10)])


def test_boxed_reserve_holds_as_champion() -> None:
    # Water on all four sides: no reinforce path, no explore step --
    # the reserve holds exactly as champion.
    mine = _PAIR + [_RESERVE]
    water = {(4, 16), (6, 16), (5, 15), (5, 17)}
    orders = run_swarm(mine, _FOE, water=water)
    assert orders == run_crowd(mine, _FOE, water=water)
    assert _RESERVE not in [loc for loc, _ in orders]


def test_packless_reserve_explores_as_champion() -> None:
    # A friendless reserve (14, 7) eyes the joined battle at distance
    # 9 but holds no pack, so it explores north exactly as champion.
    mine = _PAIR + [(14, 7)]
    orders = run_swarm(mine, _FOE)
    assert orders == run_crowd(mine, _FOE)
    assert dict(orders)[(14, 7)] == "n"


def test_reinforce_picks_nearest_joined_foe() -> None:
    # Two joined battles at equal distance: the sorted scan picks
    # (5, 7) deterministically, and the reserve steps west toward it
    # (north is water) while champion explores east.
    mine = _PAIR + [(15, 13), (15, 17), (15, 11), (15, 19), (10, 11)]
    foes = [(5, 7), (15, 15)]
    water = {(9, 11)}
    orders = run_swarm(mine, foes, water=water)
    crowd = run_crowd(mine, foes, water=water)
    assert dict(orders)[(10, 11)] == "w"
    assert dict(crowd)[(10, 11)] == "e"
    assert orders != crowd


def test_contested_denial_matches_champion() -> None:
    # Two foods watched by three foes: denial claims two ants and
    # the unclaimed reserve holds -- every order as champion.
    mine = [(5, 5), (5, 9), (5, 15)]
    foes = [(5, 12), (5, 13), (5, 14)]
    orders = run_swarm(mine, foes, foods=[(5, 6), (5, 8)])
    assert orders == run_crowd(mine, foes, foods=[(5, 6), (5, 8)])
    # The reserve's contact step is occupied and every escape is
    # unsafe, so it holds with no order -- exactly as champion.
    assert (5, 15) not in [loc for loc, _ in orders]


def test_food_guard_chain_matches_champion() -> None:
    # Food claims resolve before guard duty on a threatened-hill
    # board with a distant skirmish: every order as champion.
    mine = [(10, 8), (10, 11), (5, 5), (5, 9), (5, 3), (5, 11)]
    foes = [(10, 16), (5, 7)]
    orders = run_swarm(mine, foes, foods=[(5, 6)], my_hills=[(10, 10)])
    assert orders == run_crowd(mine, foes, foods=[(5, 6)], my_hills=[(10, 10)])


def test_full_turn_under_1s_on_crowded_board() -> None:
    # Perf: a full 48-ant do_turn finishes far inside the 1000 ms
    # engine budget on open ground.
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(10)]
    start = time.perf_counter()
    run_swarm(mine, foes)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
