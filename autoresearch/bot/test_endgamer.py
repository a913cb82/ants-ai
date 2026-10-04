#!/usr/bin/env python
"""Endgamer closing-rule tests: hand-built layouts, no engine games.

Flood diffuses instead of closing: past turn 600 (of 1000) idle
explorers must sit on held hills and contest the nearest uncontrolled
hill only with strict local superiority. Proves, on the champion base:
(1) pre-600 orders are byte-identical to the base on 3+ probe layouts,
(2) post-600 explorers convert to hill-sitters, (3) a contested-hill
challenge issues only with strict superiority (destination gate and
theater gate), (4) the turn-600 switch costs <2ms on a crowded board.
"""

import time

from ants import Ants
from Duelist import (
    ENDGAME_THEATER_R2,
    ENDGAME_TURN,
    Duelist,
    count_near,
    endgame_active,
    endgame_challenge_allowed,
)

AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}


class FakeAnts(Ants):
    """Hand-built board stub: open land plus a chosen water set."""

    def __init__(
        self,
        rows: int,
        cols: int,
        my_ants: list[tuple[int, int]],
        enemies: list[tuple[int, int]],
        enemy_hills: list[tuple[int, int]],
        my_hills: list[tuple[int, int]],
        foods: list[tuple[int, int]],
        water: set[tuple[int, int]] | None = None,
    ) -> None:
        super().__init__()
        self.rows = rows
        self.cols = cols
        self.attackradius2 = 5
        self._my = list(my_ants)
        self._enemies = list(enemies)
        self._hills = list(enemy_hills)
        self._home = list(my_hills)
        self._food = list(foods)
        self._water = set(water or set())
        self.orders: list[tuple[tuple[int, int], str]] = []

    def my_ants(self) -> list[tuple[int, int]]:
        return list(self._my)

    def enemy_ants(self) -> list[tuple[tuple[int, int], int]]:
        return [(loc, 1) for loc in self._enemies]

    def enemy_hills(self) -> list[tuple[tuple[int, int], int]]:
        return [(loc, 1) for loc in self._hills]

    def my_hills(self) -> list[tuple[int, int]]:
        return list(self._home)

    def food(self) -> list[tuple[int, int]]:
        return list(self._food)

    def visible(self, loc: tuple[int, int]) -> bool:
        return True

    def passable(self, loc: tuple[int, int]) -> bool:
        return loc not in self._water

    def unoccupied(self, loc: tuple[int, int]) -> bool:
        return loc not in self._my and loc not in self._enemies

    def destination(self, loc: tuple[int, int], direction: str) -> tuple[int, int]:
        dr, dc = AIM[direction]
        return ((loc[0] + dr) % self.rows, (loc[1] + dc) % self.cols)

    def distance(self, loc1: tuple[int, int], loc2: tuple[int, int]) -> int:
        d_col = min(abs(loc1[1] - loc2[1]), self.cols - abs(loc1[1] - loc2[1]))
        d_row = min(abs(loc1[0] - loc2[0]), self.rows - abs(loc1[0] - loc2[0]))
        return d_row + d_col

    def issue_order(self, order: tuple[tuple[int, int], str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 10000


def run_at(ants: FakeAnts, turn: int) -> FakeAnts:
    """Play one turn as if `turn` turns have elapsed (1-indexed)."""
    bot = Duelist()
    bot.do_setup(ants)
    bot.turn = turn - 1
    bot.do_turn(ants)
    assert bot.turn == turn
    return ants


def test_pre600_probe_guard_layout_matches_base() -> None:
    """Turn 1: probe layout orders match the recorded base orders."""
    ants = run_at(
        FakeAnts(
            rows=30,
            cols=60,
            my_ants=[(10, 20), (10, 14)],
            enemies=[(10, 4)],
            enemy_hills=[(10, 29)],
            my_hills=[(10, 10)],
            foods=[],
        ),
        1,
    )
    assert ants.orders == [((10, 20), "w"), ((10, 14), "n")]


def test_pre600_probe_open_field_matches_base() -> None:
    """Turn 1: a lone explorer diffuses north, as the base does."""
    ants = run_at(
        FakeAnts(
            rows=30,
            cols=60,
            my_ants=[(10, 20)],
            enemies=[],
            enemy_hills=[],
            my_hills=[],
            foods=[],
        ),
        1,
    )
    assert ants.orders == [((10, 20), "n")]


def test_pre600_probe_food_layout_matches_base() -> None:
    """Turn 1: gatherer plus muster orders match the recorded base."""
    ants = run_at(
        FakeAnts(
            rows=30,
            cols=60,
            my_ants=[(10, 20), (12, 22)],
            enemies=[(5, 5)],
            enemy_hills=[(10, 29)],
            my_hills=[(10, 10)],
            foods=[(13, 22)],
        ),
        1,
    )
    assert ants.orders == [((10, 20), "w"), ((12, 22), "s")]


def test_turn599_still_diffuses() -> None:
    """Turn 599: the switch has not flipped; the explorer diffuses."""
    ants = run_at(
        FakeAnts(
            rows=30,
            cols=60,
            my_ants=[(10, 20)],
            enemies=[],
            enemy_hills=[],
            my_hills=[(10, 10)],
            foods=[],
        ),
        599,
    )
    assert ants.orders == [((10, 20), "n")]


def test_turn600_explorer_sits_on_held_hill() -> None:
    """Turn 600: the same explorer marches west onto the held hill."""
    ants = run_at(
        FakeAnts(
            rows=30,
            cols=60,
            my_ants=[(10, 20)],
            enemies=[],
            enemy_hills=[],
            my_hills=[(10, 10)],
            foods=[],
        ),
        600,
    )
    assert ants.orders == [((10, 20), "w")]


def test_sitter_on_hill_challenges_when_open() -> None:
    """Turn 600: an ant already on its hill contests the far hill.

    The far hill is past BFS reach (the muster fails), so the base
    diffuses; the endgamer crawls east with strict superiority.
    """
    ants = run_at(
        FakeAnts(
            rows=30,
            cols=60,
            my_ants=[(10, 10)],
            enemies=[],
            enemy_hills=[(10, 40)],
            my_hills=[(10, 10)],
            foods=[],
        ),
        600,
    )
    assert ants.orders == [((10, 10), "e")]


def test_challenge_issues_with_strict_superiority() -> None:
    """Turn 600: the blocked explorer crawls south at the far hill.

    B's BFS step east is held by C, so the muster fails; the greedy
    fallback steps south, closer to the hill, with no enemies near.
    """
    ants = run_at(
        FakeAnts(
            rows=30,
            cols=60,
            my_ants=[(8, 18), (8, 19)],
            enemies=[],
            enemy_hills=[(10, 40)],
            my_hills=[],
            foods=[],
        ),
        600,
    )
    assert ((8, 18), "s") in ants.orders


def test_challenge_holds_when_outnumbered_at_destination() -> None:
    """Turn 600: two defenders by the crawl step veto the challenge.

    The theater around the far hill is empty, so the theater gate is
    open; the destination gate (1 friend + self vs 2 enemies) holds
    both ants instead of marching.
    """
    ants = run_at(
        FakeAnts(
            rows=30,
            cols=60,
            my_ants=[(8, 18), (8, 19)],
            enemies=[(9, 20), (10, 19)],
            enemy_hills=[(10, 40)],
            my_hills=[],
            foods=[],
        ),
        600,
    )
    assert ants.orders == []


def test_challenge_holds_when_theater_lost() -> None:
    """Turn 600: three campers on the far hill veto any challenge."""
    ants = run_at(
        FakeAnts(
            rows=30,
            cols=60,
            my_ants=[(8, 18)],
            enemies=[(10, 39), (11, 40), (9, 40)],
            enemy_hills=[(10, 40)],
            my_hills=[],
            foods=[],
        ),
        600,
    )
    assert ants.orders == []


def test_challenge_gate_is_strict() -> None:
    """Outnumbered challenges are refused; anything better marches.

    `friends` counts nearby allies; the +1 is the challenger, so
    (0, 1) is a refused 1-for-1 while (1, 1) is a superior 2-for-1.
    """
    assert endgame_challenge_allowed(0, 0)
    assert not endgame_challenge_allowed(0, 1)
    assert endgame_challenge_allowed(1, 1)
    assert endgame_challenge_allowed(1, 0)
    assert endgame_challenge_allowed(2, 1)
    assert not endgame_challenge_allowed(1, 2)
    assert endgame_challenge_allowed(5, 5)
    assert not endgame_challenge_allowed(5, 6)
    assert endgame_challenge_allowed(5, 4)


def test_switch_flips_at_turn_600() -> None:
    """The gate is shut at 599 and open at 600 through turn 1000."""
    assert not endgame_active(ENDGAME_TURN - 1)
    assert endgame_active(ENDGAME_TURN)
    assert endgame_active(1000)


def test_count_near_uses_attack_style_range() -> None:
    """Neighbors inside the radius count; far ants do not."""
    others = [(10, 11), (10, 13), (25, 40)]
    assert count_near((10, 10), others, ENDGAME_THEATER_R2, 30, 60) == 2


def test_switch_cost_under_2ms_on_crowded_board() -> None:
    """Theater counts plus strict gates for 150 ants take <2ms."""
    rows, cols = 40, 80
    my = [(r, c) for r in range(5, 20) for c in range(5, 15)][:150]
    foes = [(r, c) for r in range(20, 30) for c in range(60, 70)][:80]
    hills = [(25, 70), (5, 5)]
    start = time.perf_counter()
    reps = 20
    for _ in range(reps):
        for goal in hills:
            friends = count_near(goal, my, ENDGAME_THEATER_R2, rows, cols)
            enemies = count_near(goal, foes, ENDGAME_THEATER_R2, rows, cols)
            assert isinstance(endgame_challenge_allowed(friends, enemies), bool)
    elapsed_ms = (time.perf_counter() - start) / reps * 1000
    assert elapsed_ms < 2, f"switch costs {elapsed_ms:.2f}ms per turn"


def test_crowded_endgame_turn_finishes_inside_limit() -> None:
    """A full turn-600 turn on a crowded board stays far off the kill."""
    rows, cols = 40, 80
    my = [(r, c) for r in range(5, 20) for c in range(5, 15)][:150]
    foes = [(r, c) for r in range(20, 30) for c in range(60, 70)][:80]
    foods = [(10, 40), (11, 41), (12, 42)]
    ants = FakeAnts(
        rows=rows,
        cols=cols,
        my_ants=my,
        enemies=foes,
        enemy_hills=[(25, 70)],
        my_hills=[(5, 5)],
        foods=foods,
    )
    start = time.perf_counter()
    run_at(ants, 600)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert ants.orders, "a crowded endgame turn must still issue orders"
    assert elapsed_ms < 1000, f"endgame turn took {elapsed_ms:.1f}ms"
