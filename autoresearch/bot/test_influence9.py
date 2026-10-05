#!/usr/bin/env python
"""Heading-gated pursuit-projection tests (Influence9 entry).

Self-contained: FakeAnts plus the Influence7 and Influence9 entries
only, never the shared combat.py helpers. Influence9 keeps the whole
Influence7 tree and changes exactly one mechanism: the foe influence
field is stamped at a visible foe's PROJECTED tile (one toroidal step
toward its nearest own ant) only when the foe is not a proven leaver;
a foe whose last observed step strictly receded from our army stamps
at its snapshot tile instead, so a foe walking away toward food or
hills no longer gets miscounted toward us. New spawns (no match),
held foes (prev == cur), and closing foes keep the Influence7
projection, so pursuer, holder, contact, far-foe, and first-sighting
turns order byte-identically.

Consequences pinned here:

- is_receding unit: strict recession reads True; closing, held,
  and empty-army reads False;
- the leaver discriminator (two turns): foes receding east read
  projected DIE under Influence7 (hunter holds) but snapshot SAFE
  under Influence9 (hunter advances east);
- the pursuer mirror (two turns): closing foes keep the projection
  under both bots -- both hold, byte-identical;
- held foes keep the projection (prev == cur is not leaving) --
  both hold, byte-identical;
- 1v1 contact preserved: projection keeps the KILL trade, both ants
  still march (no new freeze);
- fresh-bot turns (no headings yet) order byte-identically to
  Influence7 on combat, food, hill, and empty boards;
- processing order stays canonical under permutation;
- the full turn stays under 1s crowded;
- entry self-containment.

Pins (a) recession geometry, (b) the leaver discriminator,
(c) the pursuer mirror, (d) holder stability, (e) contact-trade
preservation, (f) fresh-bot byte-identity, (g) canonical order,
(h) cost, and (i) entry self-containment.
"""

import os
import random
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Influence7 as Base  # noqa: E402
import Influence9 as New  # noqa: E402

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
    return run_two_turns(New.Influence9(), mine1, foes1, mine2, foes2, water)


def run_base_two_turns(
    mine1: list[Loc],
    foes1: list[Loc],
    mine2: list[Loc],
    foes2: list[Loc],
    water: set[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], list[tuple[Loc, str]]]:
    return run_two_turns(Base.Influence7(), mine1, foes1, mine2, foes2, water)


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


def test_is_receding_geometry() -> None:
    # (a) Strict recession from the army reads True; closing, held,
    # and empty-army reads False. Distances are toroidal manhattan
    # to the nearest own ant.
    dist = _fake([(10, 10)], []).distance
    assert New.is_receding((10, 15), (10, 14), [(10, 10)], dist) is True
    assert New.is_receding((10, 14), (10, 15), [(10, 10)], dist) is False
    assert New.is_receding((10, 14), (10, 14), [(10, 10)], dist) is False
    assert New.is_receding((10, 15), (10, 14), [], dist) is False
    # Sideways tie (same distance after moving) is not leaving:
    # (11, 13) sits 1+3 = 4 from (10, 10), same as (10, 14).
    assert New.is_receding((11, 13), (10, 14), [(10, 10)], dist) is False
    # Seam wrap: (10, 0) sits 10 from (10, 10); (10, 19) sits 9 --
    # stepping 19 -> 0 recedes.
    assert New.is_receding((10, 0), (10, 19), [(10, 10)], dist) is True


# Leaver discriminator: A=(10,10) hunts east, boxed n/s/w by water.
# Turn 1 foes (10,14),(11,13) project onto (10,13),(11,12): both
# cover the east step (10,11), so it reads DIE and the hunter holds.
# Turn 2 the foes recede to (10,15),(11,14): projected they still
# both cover (10,11) = DIE (Influence7 holds), but snapshots sit at
# distance 4, covering nothing = SAFE (Influence9 advances east).
LEAVER_MINE = [(10, 10)]
LEAVER_T1 = [(10, 14), (11, 13)]
LEAVER_T2 = [(10, 15), (11, 14)]
BOX_WATER = {(9, 10), (11, 10), (10, 9)}


def test_leaver_discriminator() -> None:
    # (b) Turn 1 both bots hold (first sighting: projection under
    # both). Turn 2 Influence7 still holds (projected DIE) while
    # Influence9 marches east (snapshot SAFE).
    base_t1, base_t2 = run_base_two_turns(
        LEAVER_MINE, LEAVER_T1, LEAVER_MINE, LEAVER_T2, BOX_WATER
    )
    new_t1, new_t2 = run_new_two_turns(
        LEAVER_MINE, LEAVER_T1, LEAVER_MINE, LEAVER_T2, BOX_WATER
    )
    assert base_t1 == []
    assert new_t1 == []
    assert base_t2 == []
    assert dict(new_t2)[(10, 10)] == "e"


def test_pursuer_mirror_byte_identical() -> None:
    # (c) Foes closing in (5 -> 4 from our ant) keep the projection
    # under Influence9: both bots hold on both turns.
    t1 = [(10, 15), (11, 14)]
    t2 = [(10, 14), (11, 13)]
    base_t1, base_t2 = run_base_two_turns(LEAVER_MINE, t1, LEAVER_MINE, t2, BOX_WATER)
    new_t1, new_t2 = run_new_two_turns(LEAVER_MINE, t1, LEAVER_MINE, t2, BOX_WATER)
    assert base_t1 == []
    assert new_t1 == []
    assert new_t2 == base_t2 == []


def test_held_foes_keep_projection() -> None:
    # (d) Unmoved foes (prev == cur) are holding, not leaving: the
    # projection stays, the east step still reads DIE, both hold.
    held = [(10, 15), (11, 14)]
    base_t1, base_t2 = run_base_two_turns(
        LEAVER_MINE, held, LEAVER_MINE, held, BOX_WATER
    )
    new_t1, new_t2 = run_new_two_turns(LEAVER_MINE, held, LEAVER_MINE, held, BOX_WATER)
    assert base_t1 == []
    assert new_t1 == []
    assert new_t2 == base_t2 == []


def test_contact_trade_preserved() -> None:
    # (e) 1v1 contact: a fresh bot has no headings, so the foe
    # projects exactly as Influence7 -- the KILL trade stands and
    # both ants still march (no new freeze).
    mine = [(10, 10)]
    foes = [(10, 12)]
    assert dict(run_fresh(Base.Influence7, mine, foes))[(10, 10)] == "e"
    assert dict(run_fresh(New.Influence9, mine, foes))[(10, 10)] == "e"


def test_fresh_bot_turns_byte_identical_to_base() -> None:
    # (f) No headings on a fresh bot: every foe projects, so combat,
    # food, hill, approach, and empty turns match Influence7.
    boards: list[tuple[list[Loc], list[Loc], dict[str, Any]]] = [
        ([(10, 10)], [(10, 15), (10, 14)], {"water": BOX_WATER}),
        ([(5, 5)], [(15, 15)], {}),
        ([(5, 5)], [(15, 15)], {"foods": [(0, 0)]}),
        ([(5, 5)], [(15, 15)], {"enemy_hills": [(5, 12)]}),
        ([(5, 5), (9, 9)], [], {"foods": [(0, 0), (15, 15)]}),
        ([(10, 10), (10, 12)], [(10, 16), (12, 12)], {}),
    ]
    for mine, foes, kw in boards:
        assert run_fresh(New.Influence9, list(mine), list(foes), **kw) == run_fresh(
            Base.Influence7, list(mine), list(foes), **kw
        )


def test_processing_order_canonical_under_permutation() -> None:
    # (g) Combat-only boards: reversing and shuffling the input
    # list never changes Influence9's orders.
    rng = random.Random(20260709)
    for _ in range(20):
        n_ours = rng.randint(2, 4)
        n_foes = rng.randint(1, 3)
        mine = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(n_ours)]
        foes = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(n_foes)]
        if len(set(mine + foes)) < n_ours + n_foes:
            continue
        listed = run_fresh(New.Influence9, list(mine), list(foes))
        assert run_fresh(New.Influence9, list(reversed(mine)), list(foes)) == listed
        shuffled = list(mine)
        rng.shuffle(shuffled)
        assert run_fresh(New.Influence9, shuffled, list(foes)) == listed


def test_full_turn_costs_under_1s_on_crowded_board() -> None:
    # (h) A full crowded turn -- 30 ants a side plus food and two
    # contested hills -- finishes far inside one second; heading
    # matching plus gating ride one linear pass.
    ours = [((i * 7 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(30)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [((i * 3 + 9) % ROWS, (i * 17 + 4) % COLS) for i in range(10)]
    bot = New.Influence9()
    first = _fake(ours, foes, foods=foods, enemy_hills=[(10, 10), (10, 3)])
    bot.do_turn(first)
    start = time.perf_counter()
    second = _fake(ours, foes, foods=foods, enemy_hills=[(10, 10), (10, 3)])
    bot.do_turn(second)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert isinstance(second.orders, list)


def test_entry_is_self_contained() -> None:
    # (i) The entry carries its own combat core: stdlib plus ants.py
    # only, never the shared combat.py helpers.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Influence9.py")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert hasattr(New, "Influence9")
    assert hasattr(New, "influence_fields")
    assert hasattr(New, "predict_foe")
    assert hasattr(New, "predict_foes")
    assert hasattr(New, "classify_counts")
    assert hasattr(New, "is_receding")
