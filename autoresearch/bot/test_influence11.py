#!/usr/bin/env python
"""Unanimous-recession gate tests (Influence11 entry).

Base is Influence9 (heading-gated pursuit-projection) with exactly
one change: a foe counts as a leaver -- and stamps at its snapshot
tile instead of its projected tile -- only when its last observed
step strictly receded from EVERY own ant, not just from the nearest
one. A foe that leaves one hunter while closing on another keeps
the pursuit projection.

Why: Influence9 keys recession off nearest-army distance (a scalar
min), so a foe sliding along our line -- leaving a near ant fast
while walking into a far hunter -- reads "leaving" and demotes to
its snapshot. The projection leans toward the near ant; the
snapshot sits on top of the far hunter's approach lane, so the far
hunter's pincer step reads KILL and holds a take Influence7 (pure
projection) marched. The unanimous gate recovers that demoted take:
the foe still closes on the far hunter, so the projection stands
and the pincer advances. True leavers -- receding from every ant,
the food/hill-bound walkers the gate was built for -- still demote,
so single-ant chases order byte-identically to Influence9 and no
leaver is re-poisoned.

Consequences pinned here:

- is_receding unit: unanimous geometry -- recedes-from-all reads
  True; closing-on-any (even while the nearest recedes) reads
  False; single-ant behavior matches Influence9 exactly;
- the pincer discriminator (two turns): far hunter A1 holds north
  under Influence9 (snapshot KILL) but marches west under
  Influence11 and Influence7 (projection frees the lane);
- the leaver chase preserved: single-ant receding foes advance
  east under both Influence11 and Influence9, held under
  Influence7;
- the true-leaver multi-ant case: foes leaving every ant still
  demote -- Influence11 matches Influence9 (advance), not
  Influence7 (hold);
- single-ant turns (fresh or two-turn) order byte-identically to
  Influence9 on combat, food, hill, and empty boards;
- processing order stays canonical under permutation;
- the full turn stays under 1s crowded;
- entry self-containment.

Pins (a) unanimous geometry, (b) the pincer discriminator,
(c) leaver-chase preservation, (d) multi-ant true-leaver demotion,
(e) single-ant byte-identity, (f) canonical order, (g) cost, and
(h) entry self-containment.
"""

import os
import random
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Influence9 as Base  # noqa: E402
import Influence11 as New  # noqa: E402

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
        dc = min(dc, self.rows - dc)
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


def _fake(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> FakeAnts:
    return FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)


def run_two_turns(
    bot: object,
    mine1: list[Loc],
    foes1: list[Loc],
    mine2: list[Loc],
    foes2: list[Loc],
    water: set[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], list[tuple[Loc, str]]]:
    """Two consecutive turns on one bot instance; headings carry over."""
    first = _fake(mine1, foes1, water=water)
    bot.do_turn(first)  # type: ignore[attr-defined]
    second = _fake(mine2, foes2, water=water)
    bot.do_turn(second)  # type: ignore[attr-defined]
    return first.orders, second.orders


def run_new_two_turns(
    mine1: list[Loc],
    foes1: list[Loc],
    mine2: list[Loc],
    foes2: list[Loc],
    water: set[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], list[tuple[Loc, str]]]:
    return run_two_turns(New.Influence11(), mine1, foes1, mine2, foes2, water)


def run_base_two_turns(
    mine1: list[Loc],
    foes1: list[Loc],
    mine2: list[Loc],
    foes2: list[Loc],
    water: set[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], list[tuple[Loc, str]]]:
    return run_two_turns(Base.Influence9(), mine1, foes1, mine2, foes2, water)


def run_fresh(
    bot_cls: type,
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list:
    fake = _fake(mine, enemies, foods, water, enemy_hills, my_hills)
    bot_cls().do_turn(fake)
    return fake.orders


def test_is_receding_unanimous_geometry() -> None:
    # (a) Leaver needs strict recession from EVERY own ant. Closing
    # on any ant -- even while the nearest recedes -- is not
    # leaving, so the projection stands.
    dist = _fake([(10, 10)], []).distance
    # Single ant: strict recession reads True, as Influence9.
    assert New.is_receding((10, 15), (10, 14), [(10, 10)], dist) is True
    assert Base.is_receding((10, 15), (10, 14), [(10, 10)], dist) is True
    assert New.is_receding((10, 14), (10, 15), [(10, 10)], dist) is False
    assert New.is_receding((10, 14), (10, 14), [(10, 10)], dist) is False
    assert New.is_receding((10, 15), (10, 14), [], dist) is False
    # The slide: (10,14) -> (10,15) leaves (10,12) 2 -> 3 but walks
    # into (10,19) 5 -> 4. Nearest says leaving; unanimous says no.
    assert Base.is_receding((10, 15), (10, 14), [(10, 12), (10, 19)], dist) is True
    assert New.is_receding((10, 15), (10, 14), [(10, 12), (10, 19)], dist) is False
    # True leaver with company: leaving every ant still reads True.
    assert New.is_receding((10, 15), (10, 14), [(10, 10), (16, 10)], dist) is True
    assert Base.is_receding((10, 15), (10, 14), [(10, 10), (16, 10)], dist) is True
    # Sideways tie against one ant (equal distance) is not leaving.
    assert New.is_receding((11, 13), (10, 14), [(10, 10), (10, 19)], dist) is False


# Pincer discriminator: B=(10,12) presses from the west, A1=(10,19)
# holds the east lane; the foe slides (10,14) -> (10,15), leaving B
# 2 -> 3 while closing on A1 5 -> 4. Influence9 demotes to the
# snapshot (10,15), which covers A1's west step (10,18) at distance
# 3: KILL, so A1 holds (explores north). Influence11 keeps the
# projection (10,14) -- it leans back toward B, freeing the lane at
# distance 4: SAFE, so A1 marches west into the pincer.
PINCER_MINE = [(10, 12), (10, 19)]
PINCER_T1 = [(10, 14)]
PINCER_T2 = [(10, 15)]


def test_pincer_discriminator() -> None:
    # (b) Turn 1 both bots agree (first sighting: projection under
    # both). Turn 2 Influence9 holds A1 (no west step) while
    # Influence11 marches A1 west.
    _, base_t2 = run_base_two_turns(PINCER_MINE, PINCER_T1, PINCER_MINE, PINCER_T2)
    _, new_t2 = run_new_two_turns(PINCER_MINE, PINCER_T1, PINCER_MINE, PINCER_T2)
    assert dict(base_t2).get((10, 19)) != "w"
    assert dict(new_t2)[(10, 19)] == "w"


# Leaver chase (from the Influence9 suite): A=(10,10) hunts east,
# boxed n/s/w by water. Turn 1 foes (10,14),(11,13) project onto
# (10,13),(11,12): DIE, hunter holds. Turn 2 the foes recede to
# (10,15),(11,14): snapshots cover nothing = SAFE (Influence9 and
# Influence11 advance east); projections still cover = DIE.
LEAVER_MINE = [(10, 10)]
LEAVER_T1 = [(10, 14), (11, 13)]
LEAVER_T2 = [(10, 15), (11, 14)]
BOX_WATER = {(9, 10), (11, 10), (10, 9)}


def test_leaver_chase_preserved() -> None:
    # (c) The single-ant chase Influence9 was built for still fires:
    # both bots hold turn 1 and march east turn 2.
    base_t1, base_t2 = run_base_two_turns(
        LEAVER_MINE, LEAVER_T1, LEAVER_MINE, LEAVER_T2, BOX_WATER
    )
    new_t1, new_t2 = run_new_two_turns(
        LEAVER_MINE, LEAVER_T1, LEAVER_MINE, LEAVER_T2, BOX_WATER
    )
    assert base_t1 == []
    assert new_t1 == []
    assert dict(base_t2)[(10, 10)] == "e"
    assert dict(new_t2)[(10, 10)] == "e"


def test_true_leaver_multi_ant_still_demotes() -> None:
    # (d) Foes leaving EVERY ant still demote with company: a second
    # ant far south (16,10) also recedes (10 -> 11), so Influence11
    # matches Influence9's east march, not a hold.
    mine = [(10, 10), (16, 10)]
    base_t1, base_t2 = run_base_two_turns(mine, LEAVER_T1, mine, LEAVER_T2, BOX_WATER)
    new_t1, new_t2 = run_new_two_turns(mine, LEAVER_T1, mine, LEAVER_T2, BOX_WATER)
    assert new_t1 == base_t1
    assert new_t2 == base_t2
    assert dict(new_t2)[(10, 10)] == "e"


def test_single_ant_turns_byte_identical_to_base() -> None:
    # (e) One ant means unanimous == nearest: fresh turns and full
    # two-turn heading sequences match Influence9 order-for-order.
    boards: list[tuple[list[Loc], list[Loc], dict[str, Any]]] = [
        ([(10, 10)], [(10, 15), (10, 14)], {"water": BOX_WATER}),
        ([(5, 5)], [(15, 15)], {}),
        ([(5, 5)], [(15, 15)], {"foods": [(0, 0)]}),
        ([(5, 5)], [(15, 15)], {"enemy_hills": [(5, 12)]}),
        ([(10, 10)], [(10, 12)], {}),
        ([(10, 10), (10, 12)], [(10, 16), (12, 12)], {}),
    ]
    for mine, foes, kw in boards:
        assert run_fresh(New.Influence11, list(mine), list(foes), **kw) == run_fresh(
            Base.Influence9, list(mine), list(foes), **kw
        )
    pairs: list[tuple[list[Loc], list[Loc]]] = [
        (LEAVER_T1, LEAVER_T2),
        (LEAVER_T2, LEAVER_T1),
        ([(10, 12)], [(10, 13)]),
    ]
    for t1, t2 in pairs:
        assert run_new_two_turns(
            LEAVER_MINE, t1, LEAVER_MINE, t2, BOX_WATER
        ) == run_base_two_turns(LEAVER_MINE, t1, LEAVER_MINE, t2, BOX_WATER)


def test_processing_order_canonical_under_permutation() -> None:
    # (f) Combat-only boards: reversing and shuffling the input
    # list never changes Influence11's orders.
    rng = random.Random(20260709)
    for _ in range(20):
        n_ours = rng.randint(2, 4)
        n_foes = rng.randint(1, 3)
        mine = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(n_ours)]
        foes = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(n_foes)]
        if len(set(mine + foes)) < n_ours + n_foes:
            continue
        listed = run_fresh(New.Influence11, list(mine), list(foes))
        assert run_fresh(New.Influence11, list(reversed(mine)), list(foes)) == listed
        shuffled = list(mine)
        rng.shuffle(shuffled)
        assert run_fresh(New.Influence11, shuffled, list(foes)) == listed


def test_full_turn_costs_under_1s_on_crowded_board() -> None:
    # (g) A full crowded turn -- 30 ants a side plus food and two
    # contested hills -- finishes far inside one second; unanimous
    # matching short-circuits on the first approached ant.
    ours = [((i * 7 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(30)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [((i * 3 + 9) % ROWS, (i * 17 + 4) % COLS) for i in range(10)]
    bot = New.Influence11()
    first = _fake(ours, foes, foods=foods, enemy_hills=[(10, 10), (10, 3)])
    bot.do_turn(first)
    start = time.perf_counter()
    second = _fake(ours, foes, foods=foods, enemy_hills=[(10, 10), (10, 3)])
    bot.do_turn(second)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert isinstance(second.orders, list)


def test_entry_is_self_contained() -> None:
    # (h) The entry carries its own combat core: stdlib plus ants.py
    # only, never the shared combat.py helpers.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Influence11.py")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert hasattr(New, "Influence11")
    assert hasattr(New, "influence_fields")
    assert hasattr(New, "predict_foe")
    assert hasattr(New, "predict_foes")
    assert hasattr(New, "classify_counts")
    assert hasattr(New, "is_receding")
