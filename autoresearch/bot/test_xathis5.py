#!/usr/bin/env python
"""Xathis5 fight-first phase tests (test-first).

Xathis5 == Xathis3 except do_turn is restructured into TWO passes
(structural only: no weight or gate changes). PASS 1 (fight):
every ant with an enemy within APPROACH_RANGE resolves combat via
the base two-mode 1-ply (aggressive/passive gates unchanged) and
claims its destination. PASS 2 (economy): all remaining ants run
the base economy (food/guard/muster/explore) with pass-1
destinations treated as occupied.

Self-contained: FakeAnts + Xathis5 for behavior, plus Xathis3
(same dir, the staged-champion copy) as the byte-identical base
reference. No engine games, no staging files.

Boards hand-derive from the base branches; attackradius2 is 5 on
every FakeAnts board, so attack reach is squared 5 and one-move
threat is manhattan 11 (APPROACH_RANGE 8 + threat_reach 3).
Squared distances use the toroidal board 20x20.

Race board (tests a/e): A=(5, 4) gathers east onto S=(5, 5)
towards F1=(5, 12) (unique shortest e-run, and the 5-vs-5 food
tie breaks to A on the lower ant index); B=(4, 5) fights south
onto the same S towards FOE=(1, 9) (dist 7: in range for B,
dist 9: out of range for A). Water walls n/e/w of B --
(3, 5), (4, 6), (4, 4) -- force B's passive advance onto S and
leave B no escape, so base (A moves first) gives A the square
and strands B, while fight-first gives B the square and A
reroutes south to explore. Board (e) adds F2=(2, 5), which the
greedy assigns to B, proving the pass-1 fighter abandons food.
"""

import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Xathis3 as BASE  # noqa: E402
import Xathis5 as XB  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}

_A = (5, 4)
_B = (4, 5)
_S = (5, 5)
_F1 = (5, 12)
_F2 = (2, 5)
_FOE = (1, 9)
_RACE_WATER = frozenset({(3, 5), (4, 6), (4, 4)})


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


def _dist(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


def run_new_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = XB.Xathis5()
    bot.do_turn(fake)
    return fake.orders


def run_base_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = BASE.Xathis3()
    bot.do_turn(fake)
    return fake.orders


def _dests(mine: list[Loc], orders: list[tuple[Loc, str]]) -> dict[Loc, Loc]:
    fake = FakeAnts(mine, [])
    return {origin: fake.destination(origin, d) for origin, d in orders}


def test_constants_unchanged() -> None:
    # Structural only: every weight, gate, and range matches base.
    assert XB.AGGRO_NEED == BASE.AGGRO_NEED == 10
    assert XB.AGGRO_RADIUS == BASE.AGGRO_RADIUS == 10
    assert XB.AGGRO_MAX_ENEMIES == BASE.AGGRO_MAX_ENEMIES == 10
    assert XB.APPROACH_RANGE == BASE.APPROACH_RANGE == 8
    assert XB.KILL_SCORE == BASE.KILL_SCORE == 300
    assert XB.DEATH_COST == BASE.DEATH_COST == 180
    assert XB.ESCAPE_RADIUS == BASE.ESCAPE_RADIUS == 3
    assert XB.CLUSTER_R == BASE.CLUSTER_R == 8
    assert XB.DENIAL_ENEMIES == BASE.DENIAL_ENEMIES == 3
    assert XB.DENIAL_CLAIMS == BASE.DENIAL_CLAIMS == 2


def test_race_board_geometry() -> None:
    # B sees the foe (7 steps: fighter); A does not (9: gatherer).
    # B is passive (one friend near: strict superiority advance).
    assert _dist(_B, _FOE) == 7
    assert _dist(_A, _FOE) == 9
    assert _dist(_A, _F1) == 8
    assert _dist(_B, _F1) == 8
    assert XB.count_near(_B, [_A, _B], _dist) == 1
    assert XB.is_aggressive(_B, [_A, _B], _dist, n_enemies=1) is False
    assert XB.nearest_approach_enemy(_B, [_FOE], _dist) == _FOE
    assert XB.nearest_approach_enemy(_A, [_FOE], _dist) is None


def test_fighter_vs_gatherer_race() -> None:
    # Base moves A first: the gatherer takes S, the fighter's
    # advance dies on the claim and every escape is walled, so B
    # strands with no order at all.
    base_orders = run_base_turn([_A, _B], [_FOE], foods=[_F1], water=set(_RACE_WATER))
    assert base_orders == [(_A, "e")]
    # Fight-first: pass 1 puts B on S before A moves; pass 2 finds
    # S claimed, so A reroutes south to explore (n walled, e
    # claimed, s/s/w all unvisited: stable order picks s).
    new_orders = run_new_turn([_A, _B], [_FOE], foods=[_F1], water=set(_RACE_WATER))
    assert new_orders == [(_B, "s"), (_A, "s")]
    assert _dests([_A, _B], new_orders)[_B] == _S
    assert _dests([_A, _B], new_orders)[_A] != _S


def test_fighter_abandons_food_for_fight() -> None:
    # The greedy still assigns B its own nearby food -- the pass-1
    # fighter holds a claim -- yet fight-first sends B onto S, not
    # towards its food: combat runs before economy, not on its
    # leftovers.
    fake = FakeAnts([_A, _B], [_FOE])
    target = XB.assign_food_targets(
        [_A, _B], [_F1, _F2], [_FOE], fake.distance, ROWS, COLS
    )
    assert target == {1: _F2, 0: _F1}
    assert target == BASE.assign_food_targets(
        [_A, _B], [_F1, _F2], [_FOE], fake.distance, ROWS, COLS
    )
    new_orders = run_new_turn(
        [_A, _B], [_FOE], foods=[_F1, _F2], water=set(_RACE_WATER)
    )
    assert new_orders == [(_B, "s"), (_A, "s")]
    assert _dests([_A, _B], new_orders)[_B] == _S
    # Base still feeds A first and strands B on the same board.
    assert run_base_turn(
        [_A, _B], [_FOE], foods=[_F1, _F2], water=set(_RACE_WATER)
    ) == [(_A, "e")]


def test_zero_enemy_boards_byte_identical() -> None:
    # No enemies means no pass-1 fighters, so pass 2 walks the
    # base body in base order: every board below matches exactly.
    crowded = [(i % ROWS, (i * 7) % COLS) for i in range(20)]
    boards: list[tuple[list[Loc], list[Loc], set[Loc] | None, list[Loc], list[Loc]]] = [
        ([(5, 5), (5, 6), (10, 10)], [(5, 9), (0, 0), (15, 15)], None, [], []),
        ([_A, _B], [_F1], set(_RACE_WATER), [], []),
        ([(5, 5), (6, 6), (7, 7)], [], None, [(15, 15)], []),
        ([(5, 5)], [], {(4, 5), (5, 6), (6, 5)}, [], [(5, 5)]),
        ([(8, 8)], [], {(7, 8), (8, 9), (9, 8), (8, 7)}, [], [(8, 8)]),
        (crowded, [(1, 1), (2, 2), (18, 18)], {(0, 1), (10, 10)}, [(15, 15)], []),
        ([(5, 5), (10, 10), (10, 11)], [(5, 8), (12, 12)], {(6, 5)}, [], []),
    ]
    for mine, foods, water, ehills, mhills in boards:
        orders = run_new_turn(
            mine, [], foods=foods, water=water, enemy_hills=ehills, my_hills=mhills
        )
        assert orders == run_base_turn(
            mine,
            [],
            foods=foods,
            water=water,
            enemy_hills=ehills,
            my_hills=mhills,
        )


def test_pass1_destinations_respected_no_overlaps() -> None:
    # Crowded board with fighters and gatherers mixed: pass-2
    # orders never land on a pass-1 destination and no two orders
    # share a square.
    mine = [
        (5, 4),
        (4, 5),
        (5, 6),
        (6, 5),
        (4, 4),
        (6, 6),
        (5, 3),
        (3, 5),
        (10, 10),
        (10, 11),
        (12, 12),
        (0, 0),
    ]
    foes = [(1, 9), (10, 2), (11, 12)]
    foods = [(5, 12), (13, 13), (1, 1)]
    water = {(3, 5), (4, 6), (4, 4), (11, 11)}
    orders = run_new_turn(mine, foes, foods=foods, water=set(water))
    assert len(orders) > 0
    dests = _dests(mine, orders)
    assert len(set(dests.values())) == len(dests)
    fighters = {a for a in mine if min(_dist(a, f) for f in foes) <= XB.APPROACH_RANGE}
    assert len(fighters) > 0
    assert any(origin in fighters for origin, _ in orders)
    fighter_dests = {dests[o] for o in dests if o in fighters}
    other_dests = {dests[o] for o in dests if o not in fighters}
    assert fighter_dests.isdisjoint(other_dests)
    fake = FakeAnts(mine, foes, foods, set(water))
    for _origin, dest in dests.items():
        assert fake.passable(dest)
        assert dest not in mine
        assert dest not in foes


def _fuzz_boards(seed: int, n: int, enemies: bool) -> None:
    # Seeded sweep: zero-enemy boards must match base order for
    # order; boards with enemies must keep every order legal and
    # every destination unique with pass-1 squares untouched.
    rng = random.Random(seed)
    for _ in range(n):
        cells = [(r, c) for r in range(ROWS) for c in range(COLS)]
        rng.shuffle(cells)
        n_mine = rng.randint(1, 12)
        n_foes = rng.randint(1, 6) if enemies else 0
        n_foods = rng.randint(0, 5)
        mine = cells[:n_mine]
        foes = cells[n_mine : n_mine + n_foes]
        foods = cells[n_mine + n_foes : n_mine + n_foes + n_foods]
        rest = cells[n_mine + n_foes + n_foods :]
        water = set(rng.sample(rest, min(len(rest), rng.randint(0, 12))))
        free = [c for c in rest if c not in water]
        ehills = rng.sample(free, min(len(free), rng.randint(0, 2)))
        orders = run_new_turn(mine, foes, foods=foods, water=water, enemy_hills=ehills)
        if not enemies:
            assert orders == run_base_turn(
                mine, foes, foods=foods, water=water, enemy_hills=ehills
            )
            continue
        dests = _dests(mine, orders)
        assert len({o for o, _ in orders}) == len(orders)
        assert len(set(dests.values())) == len(dests)
        fighters = {
            a for a in mine if min(_dist(a, f) for f in foes) <= XB.APPROACH_RANGE
        }
        fighter_dests = {dests[o] for o in dests if o in fighters}
        other_dests = {dests[o] for o in dests if o not in fighters}
        assert fighter_dests.isdisjoint(other_dests)
        fake = FakeAnts(mine, foes, foods, water)
        for _origin, dest in dests.items():
            assert fake.passable(dest)
            assert dest not in mine
            assert dest not in foes


def test_fuzz_zero_enemy_byte_identical() -> None:
    _fuzz_boards(seed=20261004, n=200, enemies=False)


def test_fuzz_with_enemies_legal_and_disjoint() -> None:
    _fuzz_boards(seed=20261005, n=200, enemies=True)


def test_full_turn_under_1s_on_crowded_board() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(10)]
    start = time.perf_counter()
    orders = run_new_turn(mine, foes)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(orders) > 0
