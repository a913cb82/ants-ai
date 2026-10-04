#!/usr/bin/env python
"""Second (paired challenge support) tests. No engine games.

One change over champion Denial: when the bot issues a hill
challenge, the nearest free (food-unclaimed, unthreatened) ant
shadows the challenger onto a support square within 3 instead of
its normal fallback -- challenges go in pairs. No free ant
within 10 steps means the challenge goes solo, exactly as today.
"""

import os
import sys
import time
from typing import Any, cast

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Second  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20


def torus(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


class FakeAnts:
    def __init__(
        self,
        ants: list[Loc],
        hills: list[Loc],
        foods: list[Loc],
        enemies: list[Loc] | None = None,
        homes: list[Loc] | None = None,
    ) -> None:
        self._ants = list(ants)
        self._hills = list(hills)
        self._foods = list(foods)
        self._enemies = list(enemies or [])
        self._homes = list(homes if homes is not None else [(0, 0)])
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = 5
        self.orders: list[tuple[Loc, str]] = []

    def food(self) -> list[Loc]:
        return list(self._foods)

    def my_ants(self) -> list[Loc]:
        return list(self._ants)

    def enemy_ants(self) -> list[tuple[Loc, int]]:
        return [(e, 1) for e in self._enemies]

    def enemy_hills(self) -> list[tuple[Loc, int]]:
        return [(h, 1) for h in self._hills]

    def my_hills(self) -> list[Loc]:
        return list(self._homes)

    def distance(self, a: Loc, b: Loc) -> int:
        return torus(a, b)

    def destination(self, loc: Loc, direction: str) -> Loc:
        r, c = loc
        if direction == "n":
            return ((r - 1) % ROWS, c)
        if direction == "s":
            return ((r + 1) % ROWS, c)
        if direction == "e":
            return (r, (c + 1) % COLS)
        return (r, (c - 1) % COLS)

    def passable(self, loc: Loc) -> bool:
        assert 0 <= loc[0] < ROWS and 0 <= loc[1] < COLS
        return True

    def unoccupied(self, loc: Loc) -> bool:
        assert 0 <= loc[0] < ROWS and 0 <= loc[1] < COLS
        return loc not in self._ants and loc not in self._enemies

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 10000


def run_turn(
    ants: list[Loc],
    hills: list[Loc],
    foods: list[Loc],
    enemies: list[Loc] | None = None,
    homes: list[Loc] | None = None,
) -> tuple[Any, FakeAnts]:
    bot = Second.Second()
    fake = FakeAnts(ants, hills, foods, enemies, homes)
    bot.do_setup(cast(Any, fake))
    bot.do_turn(cast(Any, fake))
    return bot, fake


def step_to(order: tuple[Loc, str], fake: FakeAnts) -> Loc:
    return fake.destination(order[0], order[1])


# Shared pair board: three food-free ants march on one hill to the
# east. Ant 0 challenges; ant 1 (one step north of it) is the
# nearest free ant and shadows it; ant 2 marches on untouched.
ARMY: list[Loc] = [(10, 2), (9, 2), (10, 5)]
HILL: Loc = (10, 8)
HOME: Loc = (0, 0)


def test_pair_search_picks_nearest_free_ant() -> None:
    target = Second.assign_food_targets(ARMY, [], [], torus, ROWS, COLS)
    assert target == {}
    pair = Second.pick_challenge_pair(ARMY, target, [HILL], [], torus)
    assert pair is not None
    challenger, supporter = pair
    assert (challenger, supporter) == (0, 1)
    square = Second.support_square(
        ARMY[challenger],
        ARMY[supporter],
        torus,
        FakeAnts(ARMY, [HILL], []).destination,
        FakeAnts(ARMY, [HILL], []).passable,
        set(ARMY),
    )
    assert square is not None
    assert torus(square, ARMY[challenger]) <= Second.SUPPORT_R
    assert square not in ARMY


def test_challenge_goes_in_pairs() -> None:
    # Exactly one ant diverts: the challenger still steps east onto
    # the muster path and the far ant still musters, while the
    # supporter steps north onto a square within 3 of the
    # challenger's new square.
    _, fake = run_turn(ARMY, [HILL], [], [], [HOME])
    assert fake.orders == [((10, 2), "e"), ((9, 2), "n"), ((10, 5), "e")]
    dests = [step_to(o, fake) for o in fake.orders]
    assert torus(dests[0], HILL) < torus(ARMY[0], HILL)
    assert torus(dests[2], HILL) < torus(ARMY[2], HILL)
    assert torus(dests[1], dests[0]) <= Second.SUPPORT_R


def test_challenger_untouched_by_pairing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # With the search disabled the challenger issues the identical
    # order: pairing diverts only the supporter, never the challenge.
    _, fake = run_turn(ARMY, [HILL], [], [], [HOME])
    monkeypatch.setattr(Second, "SUPPORT_REACH", -1)
    _, solo = run_turn(ARMY, [HILL], [], [], [HOME])
    assert solo.orders[0] == fake.orders[0]
    assert solo.orders[1] != fake.orders[1]
    assert solo.orders[2] == fake.orders[2]


def test_no_free_ant_in_reach_goes_solo() -> None:
    # The two free ants stand 20 steps apart: no pair forms, so both
    # march on the hill exactly as the champion would -- every order
    # steps closer to the hill and none shadows a support square.
    ants = [(0, 0), (10, 10)]
    hill = (0, 5)
    target = Second.assign_food_targets(ants, [], [], torus, ROWS, COLS)
    assert Second.pick_challenge_pair(ants, target, [hill], [], torus) is None
    _, fake = run_turn(ants, [hill], [], [], [HOME])
    assert len(fake.orders) == 2
    for order in fake.orders:
        assert torus(step_to(order, fake), hill) < torus(order[0], hill)


def test_defense_means_solo_challenge() -> None:
    # A threatened home hill keeps every free ant on guard duty: the
    # pair search stands down instead of pulling guards off the hill.
    ants = list(ARMY)
    enemies = [(1, 1)]
    target = Second.assign_food_targets(ants, [], enemies, torus, ROWS, COLS)
    threatened: list[Loc] = [HOME]
    assert Second.pick_challenge_pair(ants, target, [HILL], threatened, torus) is None


def test_supporter_rejoins_economy_after_raze() -> None:
    # Turn 1 the pair forms; turn 2 the hill is razed (an ant stands
    # on it, so memory clears) and food appears by the ex-supporter.
    # No pair forms and the ex-supporter walks to food like always.
    bot = Second.Second()
    fake1 = FakeAnts(ARMY, [HILL], [], [], [HOME])
    bot.do_setup(cast(Any, fake1))
    bot.do_turn(cast(Any, fake1))
    assert [o for o in fake1.orders if o[0] == (9, 2)] == [((9, 2), "n")]
    ants2 = [(10, 8), (9, 3), (10, 6)]
    foods2 = [(9, 4)]
    fake2 = FakeAnts(ants2, [], foods2, [], [HOME])
    bot.do_turn(cast(Any, fake2))
    target = Second.assign_food_targets(ants2, foods2, [], torus, ROWS, COLS)
    assert Second.pick_challenge_pair(ants2, target, [], [], torus) is None
    orders = [o for o in fake2.orders if o[0] == (9, 3)]
    assert len(orders) == 1
    assert torus(step_to(orders[0], fake2), (9, 4)) < torus((9, 3), (9, 4))
    assert not any("support" in key for key in vars(bot))


def test_support_search_costs_under_1ms() -> None:
    # Crowded board: 300 ants, 40 foods, 3 hills. The pair search
    # plus the support-square pick must stay far under 1 ms.
    ants = [(i % ROWS, (i // ROWS) % COLS) for i in range(300)]
    foods = [(r, c) for r in (3, 7, 11, 15) for c in range(0, COLS, 2)]
    hills = [(0, 10), (10, 0), (10, 10)]
    enemies = [(10, 10)]
    assert len(foods) == 40
    target = Second.assign_food_targets(ants, foods, enemies, torus, ROWS, COLS)
    probe = FakeAnts(ants, hills, foods, enemies, [HOME])
    worst = 0.0
    for _ in range(5):
        start = time.perf_counter()
        pair = Second.pick_challenge_pair(ants, target, hills, [], torus)
        if pair is not None:
            Second.support_square(
                ants[pair[0]],
                ants[pair[1]],
                torus,
                probe.destination,
                probe.passable,
                set(ants) | set(enemies),
            )
        worst = max(worst, time.perf_counter() - start)
    assert worst < 0.001
