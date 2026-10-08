#!/usr/bin/env python
"""Delineate greedy-field combat tests (Greedy entry).

Faithful to the RESEARCH.md row "delineate heuristic combat" (top
10, briefly top 3): zero search, greedy 5-move scoring from BFS
feature fields of the form 1/(1+d^2), kill bonus only with strict
local superiority, conservative at equality. No minimax, no
sampling, no influence maps -- pure greedy field climbing.

Proves, on fixed boards before the bot code lands:
(a) hand-computed field values 1/(1+d^2),
(b) move choice picks the max-score square on a fixed 3-option board,
(c) kill bonus fires only with strict superiority (equality holds),
(d) per-move scoring <0.5ms and a crowded full turn <1s.

Also pins the carried-forward champion wiring the entry keeps
byte-identical: Denial economy claims, threatened-hill guard,
single-target muster, and never camping a home hill.
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Greedy as G  # noqa: E402

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


def run_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], G.Greedy]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = G.Greedy()
    bot.do_turn(fake)
    return fake.orders, bot


def open_passable(loc: Loc) -> bool:
    return True


def flat_sq(a: Loc, b: Loc) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


# (a) hand-computed fields ------------------------------------------------


def test_field_single_target_matches_one_over_one_plus_d2() -> None:
    # (10,10) -> (10,12) is 2 steps on the open torus: 1/(1+4) = 0.2.
    assert G.bfs_field((10, 10), {(10, 12)}, open_passable, 20, 20, 8) == pytest.approx(
        0.2
    )


def test_field_sums_targets_and_cuts_horizon() -> None:
    # d=1 gives 0.5, d=2 gives 0.2; (10,19) sits 9 away, past
    # horizon 8, so it contributes nothing: total 0.7.
    got = G.bfs_field(
        (10, 10), {(10, 11), (10, 12), (10, 19)}, open_passable, 20, 20, 8
    )
    assert got == pytest.approx(0.7)


def test_field_uses_bfs_distance_around_water() -> None:
    # Single wall tile (10,11) forces the (10,9)->(10,12) walk out
    # to 5 steps, so the field is 1/26, not the straight-line 1/10.
    water = {(10, 11)}
    assert G.bfs_field(
        (10, 9), {(10, 12)}, lambda loc: loc not in water, 20, 20, 8
    ) == (pytest.approx(1 / 26))


def test_unseen_field_counts_only_unvisited_squares() -> None:
    # Horizon 2 around (10,10) with every square visited except
    # (10,12): the unseen-only score is exactly 1/(1+2^2) = 0.2.
    near = {
        (10 + dr, 10 + dc)
        for dr in range(-2, 3)
        for dc in range(-2, 3)
        if abs(dr) + abs(dc) <= 2
    }
    visits = {loc: 1 for loc in near if loc != (10, 12)}
    got = G.score_move(
        (10, 10),
        (10, 10),
        [(10, 10)],
        [],
        set(),
        set(),
        visits,
        open_passable,
        flat_sq,
        5,
        20,
        20,
        2,
        (0.0, 0.0, 0.0, 1.0),
    )
    assert got == pytest.approx(0.2)


# (b) max-score choice ------------------------------------------------------


def test_choice_picks_max_score_square() -> None:
    # Food at (5,8): east (d=2, 0.2) beats hold (d=3, 0.1) beats
    # west (d=4, 1/17). No enemies, no hills, no visits tracking.
    ant = (5, 5)
    foods = {(5, 8)}
    east = G.score_move(
        (5, 6), ant, [ant], [], foods, set(), None, open_passable, flat_sq, 5, 20, 20
    )
    hold = G.score_move(
        (5, 5), ant, [ant], [], foods, set(), None, open_passable, flat_sq, 5, 20, 20
    )
    west = G.score_move(
        (5, 4), ant, [ant], [], foods, set(), None, open_passable, flat_sq, 5, 20, 20
    )
    assert east == pytest.approx(G.W_FOOD * 0.2)
    assert hold == pytest.approx(G.W_FOOD * 0.1)
    assert west == pytest.approx(G.W_FOOD * (1 / 17))
    assert east > hold > west
    assert G.pick_best({"e": east, "-": hold, "w": west}) == "e"


def test_choice_holds_ties() -> None:
    # Equal scores keep the first-listed candidate: hold is listed
    # first, so ties never wander.
    assert G.pick_best({"-": 1.0, "e": 1.0, "w": 0.5}) == "-"


# (c) strict-superiority kill gate ------------------------------------------


def test_kill_bonus_fires_only_with_strict_superiority() -> None:
    # Dest (5,6) touches one enemy at (5,7). With a friend at (6,6)
    # ours is 2 > 1 and the bonus fires; lone, ours is 1 == 1 and
    # the score stays field-only.
    dest = (5, 6)
    mover = (5, 5)
    foods = {(5, 9)}  # d=3 from dest: field-only food term 0.1 * W_FOOD.
    lone = G.score_move(
        dest,
        mover,
        [mover],
        [(5, 7)],
        foods,
        set(),
        None,
        open_passable,
        flat_sq,
        5,
        20,
        20,
    )
    packed = G.score_move(
        dest,
        mover,
        [mover, (6, 6)],
        [(5, 7)],
        foods,
        set(),
        None,
        open_passable,
        flat_sq,
        5,
        20,
        20,
    )
    # Enemy field at d=1 is 0.5 * W_ENEMY; no bonus at equality.
    assert lone == pytest.approx(G.W_FOOD * 0.1 + G.W_ENEMY * 0.5)
    assert packed - lone == pytest.approx(G.KILL_BONUS)


def test_packed_ant_advances_on_lone_enemy() -> None:
    # Strict superiority (2v1 at the step) steps east onto (5,6)
    # instead of holding or wandering.
    orders, _ = run_turn([(5, 5), (5, 4)], [(5, 7)])
    assert orders[0] == ((5, 5), "e")


# (d) speed -----------------------------------------------------------------


def test_per_move_scoring_under_half_ms() -> None:
    rows = cols = 30
    water = {(15, c) for c in range(30) if c != 15}

    def passable(loc: Loc) -> bool:
        return loc not in water

    def sq(a: Loc, b: Loc) -> int:
        dr = abs(a[0] - b[0])
        dr = min(dr, rows - dr)
        dc = abs(a[1] - b[1])
        dc = min(dc, cols - dc)
        return dr * dr + dc * dc

    enemies = [(r, c) for r in range(5, 25, 2) for c in range(5, 25, 3)][:60]
    foods = {(r, c) for r in range(0, 30, 3) for c in range(0, 30, 4)}
    hills = {(0, 0), (29, 29)}
    visits = {(r, c): 1 for r in range(12, 18) for c in range(12, 18)}
    own = [(15, 14), (14, 15), (16, 15)]
    G.score_move(
        (15, 15),
        (15, 14),
        own,
        enemies,
        foods,
        hills,
        visits,
        passable,
        sq,
        5,
        rows,
        cols,
    )
    reps = 200
    start = time.perf_counter()
    for _ in range(reps):
        G.score_move(
            (15, 15),
            (15, 14),
            own,
            enemies,
            foods,
            hills,
            visits,
            passable,
            sq,
            5,
            rows,
            cols,
        )
    mean_ms = (time.perf_counter() - start) / reps * 1000
    assert mean_ms < 0.5


def test_crowded_full_turn_under_one_second() -> None:
    mine = [(r, c) for r in range(0, 20, 2) for c in range(0, 20, 2)][:60]
    enemies = [(r, c) for r in range(1, 20, 2) for c in range(1, 20, 2)][:60]
    foods = [(r, c) for r in range(0, 20, 3) for c in range(0, 20, 5)][:40]
    water = {(10, c) for c in range(20) if c not in (9, 10)}
    start = time.perf_counter()
    orders, _ = run_turn(mine, enemies, foods, water, [(19, 19)], [(0, 0)])
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(orders) > 0


# carried-forward champion wiring -------------------------------------------


def test_food_claim_steps_to_nearest_food() -> None:
    orders, _ = run_turn([(0, 0), (0, 19)], [], [(0, 1), (0, 18)])
    assert orders == [((0, 0), "e"), ((0, 19), "w")]


def test_guard_answers_threatened_hill() -> None:
    probe = FakeAnts([(5, 5)], [(2, 5)], my_hills=[(2, 2)])
    assert probe.distance((2, 2), (2, 5)) <= 10
    orders, _ = run_turn([(5, 5)], [(2, 5)], my_hills=[(2, 2)])
    assert orders
    loc, direction = orders[0]
    assert loc == (5, 5)
    assert probe.distance(probe.destination(loc, direction), (2, 2)) < probe.distance(
        loc, (2, 2)
    )


def test_muster_marches_remembered_hill() -> None:
    probe = FakeAnts([(0, 0)], [])
    orders, bot = run_turn([(0, 0)], [], enemy_hills=[(10, 10)])
    assert (10, 10) in bot.remembered_hills
    assert orders
    loc, direction = orders[0]
    assert probe.distance(probe.destination(loc, direction), (10, 10)) < probe.distance(
        loc, (10, 10)
    )


def test_quiet_ant_explores_instead_of_suiciding() -> None:
    # Lone ant, enemy 20 away (past combat range): champion explore
    # steps north, never a cross-map suicide.
    orders, _ = run_turn([(5, 5)], [(15, 15)])
    assert orders == [((5, 5), "n")]


def test_ant_never_camps_home_hill() -> None:
    orders, _ = run_turn([(3, 3)], [], my_hills=[(3, 3)])
    assert orders
    loc, direction = orders[0]
    assert FakeAnts([(3, 3)], []).destination(loc, direction) != (3, 3)
