#!/usr/bin/env python
"""Xathis6 doomed-advance tests (test-first).

Mechanism: the aggressive 1-ply scores every option as
enemyDead*300 - myDead*180 - dist. When ALL options lose material
(outnumbered clash), the kill/loss terms tie and the -dist term
decides -- so the search steps TOWARD the enemy pack (minimising
dist) instead of retreating. A lone advanced ant with distant
friends (aggression gate ON, zero in-range support) walks into a
lost clash it should refuse.

Xathis6 == Xathis5 except the distance pressure is
outcome-dependent: press (nearer) when the clash wins material,
separate (farther) when it loses. Winning takes (S2) and 1-for-1
trades (S3) are byte-identical; only losing clashes (S1, S4)
change.

Self-contained: FakeAnts + Xathis6 for behavior, plus Xathis5
(same dir, the fight-first base) as the discrimination
reference. No engine games, no staging files.

Boards: 20x20 torus, attackradius2 5 (attack reach squared 5,
threat manhattan APPROACH_RANGE 8 + threat_reach 3 = 11).
S1/S3: A=(10,10) vs E1=(10,12) (+ E2=(11,11), E3=(9,11) in S1),
no friends in range. S2 adds F1=(9,10), F2=(10,9) (2 supporters
vs 1 attacker: winning press). S4 end-to-end: A plus 10 friends
at manhattan 7-9 (gate ON, zero in-range support) vs the S1 pack.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Xathis5 as BASE  # noqa: E402

try:
    import Xathis6 as XB  # noqa: E402
except ImportError:
    XB = None

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}

_A = (10, 10)
_E1 = (10, 12)
_E2 = (11, 11)
_E3 = (9, 11)
_PACK = [_E1, _E2, _E3]
_F1 = (9, 10)
_F2 = (10, 9)
# Ten friends at manhattan 7-9 from A (gate ON) but squared 25+
# from every square adjacent to A (zero in-range support).
_DISTANT = [
    (10, 2),
    (10, 3),
    (10, 18),
    (10, 17),
    (2, 10),
    (3, 10),
    (18, 10),
    (17, 10),
    (5, 6),
    (15, 14),
]


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
        return ((loc[0] + dr) % self.rows, (loc[1] + dc) % COLS)

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


def make_funcs(fake: FakeAnts):
    def sq(a: Loc, b: Loc) -> int:
        dr = abs(a[0] - b[0])
        dr = min(dr, fake.rows - dr)
        dc = abs(a[1] - b[1])
        dc = min(dc, fake.cols - dc)
        return dr * dr + dc * dc

    return sq


def search(mod, mine: list[Loc], foes: list[Loc], ant: Loc):
    fake = FakeAnts(mine, foes)
    return mod.search_best_move(
        ant,
        mine,
        foes,
        fake.destination,
        fake.passable,
        fake.distance,
        make_funcs(fake),
        ROWS,
        COLS,
        5,
        set(),
    )


def nearest_foe_d(loc: Loc, foes: list[Loc]) -> int:
    fake = FakeAnts([], [])
    return min(fake.distance(loc, f) for f in foes)


def test_base_advances_when_doomed():
    """S1 base pin: outnumbered 1v3, search steps TOWARD the pack."""
    move, dest, score = search(BASE, [_A], _PACK, _A)
    assert (move, dest) == ("n", (9, 10))
    assert score < 0
    assert nearest_foe_d(dest, _PACK) < nearest_foe_d(_A, _PACK)


def test_tuned_retreats_when_doomed():
    """S1 discrimination: Xathis6 refuses the losing advance."""
    assert XB is not None
    move_b, dest_b, _ = search(BASE, [_A], _PACK, _A)
    move_x, dest_x, score_x = search(XB, [_A], _PACK, _A)
    assert score_x < 0
    assert dest_x != dest_b
    assert nearest_foe_d(dest_x, _PACK) >= nearest_foe_d(_A, _PACK)
    assert move_x is None or nearest_foe_d(dest_x, _PACK) > nearest_foe_d(dest_b, _PACK)


def test_tuned_still_presses_winning_kill():
    """S2 no-regression: 2 supporters vs 1 attacker presses east."""
    assert XB is not None
    assert search(BASE, [_A, _F1, _F2], [_E1], _A) == ("e", (10, 11), 300)
    assert search(XB, [_A, _F1, _F2], [_E1], _A) == ("e", (10, 11), 300)


def test_tuned_still_takes_one_for_one():
    """S3 no-regression: equal 1-for-1 trade still engages east."""
    assert XB is not None
    assert search(BASE, [_A], [_E1], _A) == ("e", (10, 11), 120)
    assert search(XB, [_A], [_E1], _A) == ("e", (10, 11), 120)


def test_gate_on_with_distant_friends():
    """S4 setup sanity: 10 friends at range 7-9 open aggression."""
    assert XB is not None
    fake = FakeAnts([], [])
    assert BASE.is_aggressive(_A, [_A] + _DISTANT, fake.distance, n_enemies=len(_PACK))
    assert XB.is_aggressive(_A, [_A] + _DISTANT, fake.distance, n_enemies=len(_PACK))


def run_turn(mod, mine: list[Loc], foes: list[Loc]):
    fake = FakeAnts(mine, foes)
    bot = mod.Xathis6() if mod is XB else mod.Xathis5()
    bot.do_turn(fake)
    return dict(fake.orders)


def test_do_turn_refuses_doomed_advance():
    """S4 end-to-end: base marches A north; Xathis6 will not advance."""
    assert XB is not None
    mine = [_A] + _DISTANT
    base_orders = run_turn(BASE, mine, _PACK)
    assert base_orders.get(_A) == "n"
    tuned_orders = run_turn(XB, mine, _PACK)
    dest_x = (
        FakeAnts([], []).destination(_A, tuned_orders[_A]) if _A in tuned_orders else _A
    )
    dest_b = FakeAnts([], []).destination(_A, base_orders[_A])
    assert nearest_foe_d(dest_x, _PACK) >= nearest_foe_d(_A, _PACK)
    assert nearest_foe_d(dest_x, _PACK) > nearest_foe_d(dest_b, _PACK)
