#!/usr/bin/env python
"""Brave-take parity tests (Greedy10 entry).

Base is Greedy6: an even-trade combat step is allowed when brave
(a backup friend within SUPPORT_R of the destination, no shadow
foe) -- but only when the step strictly outscores HOLD. Hold,
though, is subsidized by the very backup that makes the step
brave: a trailing friend in attack range of the hold square scores
+KILL_BONUS for standing still, so hold outscores the brave step
by ~1.8 and the ant wanders off instead of taking the duel it
was built to take. Nearby friends subsidize inaction as well as
takes; the pincer geometry (support beyond the foe, off every
square's attack range) takes only because hold earns no bonus
there. The common geometry -- backup trailing behind the front
line -- never takes.

Greedy10 adds one mechanism -- brave-take parity: a brave step
takes whenever its field gap fits inside the hold subsidy, i.e.
step + KILL_BONUS > hold. The subsidy IS the bonus, so no new
constant. Everything else is untouched: safe takes use the old
strict rule, non-brave steps never take, and objectives still
outvote parity (food/hill weight on hold wins by more than the
bonus, so anchors keep holding).

Proves, on fixed boards before the bot code lands:
(a) trailing duel: 1v1 step with backup trailing at (10,8) --
    brave, but hold carries the subsidy -- base wanders, tuned
    steps east (the take the line was built for),
(b) pincer duel still takes, byte-identical to base,
(c) isolated / shadowed / 1vN still hold, byte-identical,
(d) food-anchored brave step still holds, byte-identical,
(e) packed wins / crowd-backed / quiet boards byte-identical,
(f) any first-ant order that differs from base lands on a brave
    square -- never a wild lunge,
(g) a crowded full turn still runs <1s.
"""

import os
import sys
import time
from types import ModuleType
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Greedy6 as Base  # noqa: E402

try:
    import Greedy10 as Tuned  # noqa: E402

    HAVE_TUNED = True
except ImportError:  # pragma: no cover
    HAVE_TUNED = False

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
    if HAVE_TUNED and mod is Tuned:
        return Tuned.Greedy10()
    return Base.Greedy6()


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


def require_tuned() -> ModuleType:
    assert HAVE_TUNED, "Greedy10.py not written yet"
    return Tuned


# one-idea discipline --------------------------------------------------------


def test_constants_identical_to_base_no_new_knobs() -> None:
    tuned = require_tuned()
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
        "SUPPORT_R",
    ):
        assert getattr(tuned, name) == getattr(Base, name), name
    assert tuned.WEIGHTS == Base.WEIGHTS


def test_trailing_support_step_is_brave_but_holds_base() -> None:
    # Premise of the whole entry: the step east is brave (backup
    # trails at (10,8), foe alone) yet base refuses it, because
    # hold carries the friend-subsidized kill bonus.
    assert (
        Base.brave_support(
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
    orders = run_turn(Base, [(10, 10), (10, 8)], [(10, 12)])
    first = [o for o in orders if o[0] == (10, 10)]
    assert first, "probing ant must still move or the test is vacuous"
    assert first[0] != ((10, 10), "e"), "base must refuse the subsidized duel"


# (a) trailing duel: tuned takes what base wanders away from --------------


def test_tuned_takes_trailing_duel() -> None:
    tuned = require_tuned()
    mine = [(10, 10), (10, 8)]
    enemies = [(10, 12)]
    orders = run_turn(tuned, mine, enemies)
    assert ((10, 10), "e") in orders
    assert orders != run_turn(Base, mine, enemies)


def test_trailing_take_is_exactly_brave_not_outnumbered() -> None:
    tuned = require_tuned()
    mine = [(10, 10), (10, 8)]
    enemies = [(10, 12)]
    orders = dict(run_turn(tuned, mine, enemies))
    dest = post_move((10, 10), orders[(10, 10)])
    assert dest == (10, 11)
    assert tuned.count_sides(dest, (10, 10), mine, enemies, flat_sq, ATTACK_R2) == (
        1,
        1,
    )
    assert tuned.brave_support(
        dest, (10, 10), mine, enemies, tor_dist, flat_sq, ATTACK_R2
    )


def test_trailing_take_fits_inside_hold_subsidy() -> None:
    # The field gap hold-step must be smaller than KILL_BONUS: the
    # take is the subsidy band working, not a field win.
    tuned = require_tuned()
    mine = [(10, 10), (10, 8)]
    enemies = [(10, 12)]
    visits = {(10, 10): 1, (10, 8): 1}
    hold = tuned.score_move(
        (10, 10),
        (10, 10),
        mine,
        enemies,
        set(),
        set(),
        visits,
        lambda loc: True,
        flat_sq,
        ATTACK_R2,
        ROWS,
        COLS,
    )
    step = tuned.score_move(
        (10, 11),
        (10, 10),
        mine,
        enemies,
        set(),
        set(),
        visits,
        lambda loc: True,
        flat_sq,
        ATTACK_R2,
        ROWS,
        COLS,
    )
    assert hold > step, "without the subsidy there is no take to explain"
    assert step + tuned.KILL_BONUS > hold


# (b) pincer take kept, byte-identical -----------------------------------------


def test_pincer_take_byte_identical_to_base() -> None:
    tuned = require_tuned()
    mine = [(10, 10), (10, 14)]
    enemies = [(10, 12)]
    assert run_turn(Base, mine, enemies)[0] == ((10, 10), "e")
    assert run_turn(tuned, mine, enemies) == run_turn(Base, mine, enemies)


# (c) refusal geometries stay byte-identical ----------------------------------


def test_isolated_1v1_byte_identical_to_base() -> None:
    tuned = require_tuned()
    mine = [(10, 10)]
    enemies = [(10, 12)]
    assert run_turn(tuned, mine, enemies) == run_turn(Base, mine, enemies)
    assert ((10, 10), "e") not in run_turn(tuned, mine, enemies)


def test_shadowed_1v1_byte_identical_to_base() -> None:
    tuned = require_tuned()
    mine = [(10, 10), (10, 14)]
    enemies = [(10, 12), (10, 15)]
    assert run_turn(tuned, mine, enemies) == run_turn(Base, mine, enemies)
    assert ((10, 10), "e") not in run_turn(tuned, mine, enemies)


def test_1v2_with_support_still_refused() -> None:
    tuned = require_tuned()
    mine = [(10, 10), (10, 8)]
    enemies = [(10, 12), (11, 11)]
    assert run_turn(tuned, mine, enemies) == run_turn(Base, mine, enemies)
    assert ((10, 10), "e") not in run_turn(tuned, mine, enemies)


# (d) objectives still outvote parity ------------------------------------------
#
# Food on the hold square adds more than the bonus band bridges,
# so the anchored ant keeps holding (here: no east lunge) exactly
# like base.


def test_food_anchored_brave_step_still_holds() -> None:
    tuned = require_tuned()
    mine = [(10, 10), (10, 8)]
    enemies = [(10, 12)]
    base_orders = run_turn(Base, mine, enemies, [(10, 10)])
    tuned_orders = run_turn(tuned, mine, enemies, [(10, 10)])
    assert ((10, 10), "e") not in base_orders
    assert tuned_orders == base_orders


def test_brave_take_outranks_far_hill_march() -> None:
    # A contact duel is combat, and combat outranks the muster
    # march in base too (safe and pincer takes already preempt
    # it). A far remembered hill must not veto the trailing take.
    tuned = require_tuned()
    boards = [
        ([(10, 10), (10, 8)], [(10, 12)], [(0, 0)]),
        ([(5, 5), (5, 3)], [(5, 7)], [(15, 15)]),
    ]
    for mine, enemies, enemy_hills in boards:
        base_orders = run_turn(Base, mine, enemies, None, None, enemy_hills)
        tuned_orders = run_turn(tuned, mine, enemies, None, None, enemy_hills)
        assert (mine[0], "e") not in base_orders
        assert (mine[0], "e") in tuned_orders
        dest = post_move(mine[0], dict(tuned_orders)[mine[0]])
        assert tuned.brave_support(
            dest, mine[0], mine, enemies, tor_dist, flat_sq, ATTACK_R2
        )


# (e) wins and quiet boards byte-identical -------------------------------------


def test_packed_wins_byte_identical_to_base() -> None:
    tuned = require_tuned()
    boards = [
        ([(5, 5), (5, 4)], [(5, 7)]),
        ([(5, 5), (5, 4), (6, 5)], [(5, 7), (6, 7)]),
    ]
    for mine, enemies in boards:
        assert run_turn(Base, mine, enemies)[0] == ((5, 5), "e")
        assert run_turn(tuned, mine, enemies) == run_turn(Base, mine, enemies)


def test_equal_trade_with_crowd_byte_identical_to_base() -> None:
    tuned = require_tuned()
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
    assert run_turn(tuned, mine, enemies) == run_turn(Base, mine, enemies)


def test_quiet_boards_byte_identical_to_base() -> None:
    tuned = require_tuned()
    boards = [
        ([(0, 0), (0, 19)], [], [(0, 1), (0, 18)], None, None, None),
        ([(0, 0)], [], None, None, [(10, 10)], None),
        ([(5, 5)], [(15, 15)], None, None, None, None),
        ([(3, 3)], [], None, None, None, [(3, 3)]),
    ]
    for mine, enemies, foods, water, enemy_hills, my_hills in boards:
        assert run_turn(
            tuned, mine, enemies, foods, water, enemy_hills, my_hills
        ) == run_turn(Base, mine, enemies, foods, water, enemy_hills, my_hills)


# (f) no wild lunges ---------------------------------------------------------------


def test_any_new_first_ant_take_lands_on_brave_square() -> None:
    # Sweep small duel geometries: the prober moves first, so its
    # destinations are pristine. Any tuned order for the prober
    # that differs from base must land on a brave square -- never
    # outnumbered, never an unbacked lunge.
    tuned = require_tuned()
    probers = [(10, 10), (5, 5), (0, 0)]
    supports = [[], [(10, 8)], [(10, 14)], [(10, 8), (9, 10)], [(5, 3)], [(1, 0)]]
    foe_sets = [
        [(10, 12)],
        [(10, 12), (10, 15)],
        [(10, 12), (0, 0)],
        [(9, 12)],
        [(5, 7)],
        [(0, 2)],
    ]
    for prober in probers:
        for extra in supports:
            mine = [prober] + [s for s in extra if s != prober]
            for foes in foe_sets:
                base_orders = dict(run_turn(Base, mine, foes))
                tuned_orders = dict(run_turn(tuned, mine, foes))
                if tuned_orders.get(prober) == base_orders.get(prober):
                    continue
                assert prober in tuned_orders, (mine, foes, tuned_orders)
                dest = post_move(prober, tuned_orders[prober])
                assert tuned.brave_support(
                    dest,
                    prober,
                    mine,
                    foes,
                    tor_dist,
                    flat_sq,
                    ATTACK_R2,
                ), (mine, foes, tuned_orders)


# (g) speed ---------------------------------------------------------------------------


def test_crowded_full_turn_under_one_second() -> None:
    tuned = require_tuned()
    mine = [(r, c) for r in range(0, 20, 2) for c in range(0, 20, 2)][:60]
    enemies = [(r, c) for r in range(1, 20, 2) for c in range(1, 20, 2)][:60]
    foods = [(r, c) for r in range(0, 20, 3) for c in range(0, 20, 5)][:40]
    water = {(10, c) for c in range(20) if c not in (9, 10)}
    start = time.perf_counter()
    orders = run_turn(tuned, mine, enemies, foods, water, [(19, 19)], [(0, 0)])
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(orders) > 0


def test_combat_heavy_turn_under_one_second() -> None:
    tuned = require_tuned()
    mine = [(10 + (i // 10), 8 + (i % 10)) for i in range(40)]
    enemies = [(10 + (i // 10), 12 + (i % 4)) for i in range(16)]
    start = time.perf_counter()
    orders = run_turn(tuned, mine, enemies)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(orders) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
