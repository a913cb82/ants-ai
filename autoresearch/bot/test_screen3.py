#!/usr/bin/env python
"""Screen3 entry tests: second-rank hole-filling plus corridor screening.

Screen3 carries Crowd's wiring (Denial food economy, pack-gated seek,
committed-join packs, ahead-only 1v1 duels, 10-gate equal trades,
fearless small fights) and adds two mechanisms the Screen base lacks:

- hole-filling: a packed hunter -- or a blocked muster marcher --
  whose shortest-path step fails tries combat.hole_steps, the other
  directions that still close on the same goal, under the same safety
  regime, never through the join or the grinder release;
- corridor screening: extra guards stand on combat.screen_square, so
  a flooded midpoint meets the razer on its approach corridor instead
  of the nearest dry square.

No engine games. A FakeAnts stand-in covers do_turn's interface, the
same shape as test_combat.py. Boards are small and every turn costs
milliseconds; the only timing test is one 48-ant turn far inside the
1000 ms budget. Each Screen3 assertion pairs with the Screen base on
the same board wherever the mechanisms differ.
"""

import ast
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import combat as CX  # noqa: E402
import Screen as Base  # noqa: E402
import Screen3 as S3  # noqa: E402

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


def run_screen3(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], S3.Screen3]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = S3.Screen3()
    bot.do_turn(fake)
    return fake.orders, bot


def run_base(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = Base.Screen()
    bot.do_turn(fake)
    return fake.orders


def dist(a: Loc, b: Loc) -> int:
    return FakeAnts([], []).distance(a, b)


def safe_baseline(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    """Screen3 with the crowd gate forced closed: full safety everywhere."""
    orig = CX.CROWD_LIMIT
    CX.CROWD_LIMIT = 0
    try:
        orders, _ = run_screen3(mine, enemies, foods, water, enemy_hills, my_hills)
    finally:
        CX.CROWD_LIMIT = orig
    return orders


# Food economy: Denial's claims, pinned on the Screen3 copy. The base
# shares them byte-for-byte, so every board here also matches Screen.


def test_denied_needs_three_enemies() -> None:
    foods = [(5, 5), (5, 6)]
    assert S3.denied_food_groups(foods, [(5, 10), (5, 12)], dist, ROWS, COLS) == []
    assert S3.denied_food_groups(foods, [], dist, ROWS, COLS) == []
    assert S3.denied_food_groups([], [(5, 5)] * 3, dist, ROWS, COLS) == []


def test_contested_cluster_takes_exactly_two_claims() -> None:
    foods = [(5, 5), (5, 6), (5, 7)]
    enemies = [(5, 12), (5, 13), (6, 12)]
    groups = S3.denied_food_groups(foods, enemies, dist, ROWS, COLS)
    assert groups == [[0, 1, 2]]
    mine = [(5, 0), (5, 1), (5, 2), (5, 3)]
    target = S3.assign_food_targets(mine, foods, enemies, dist, ROWS, COLS)
    assert len(target) == 2
    assert set(target.values()) <= set(foods)
    assert (5, 7) not in set(target.values())


def test_single_food_cluster_draws_one_claimant() -> None:
    foods = [(5, 5)]
    enemies = [(5, 10), (5, 11), (6, 10)]
    mine = [(5, 0), (5, 1), (5, 2)]
    target = S3.assign_food_targets(mine, foods, enemies, dist, ROWS, COLS)
    assert len(target) == 1
    assert set(target.values()) == {(5, 5)}


def test_food_assign_empty_inputs() -> None:
    assert S3.assign_food_targets([], [(5, 5)], [], dist, ROWS, COLS) == {}
    assert S3.assign_food_targets([(5, 5)], [], [], dist, ROWS, COLS) == {}


def test_uncontested_food_is_nearest_greedy() -> None:
    mine = [(5, 5), (0, 0)]
    foods = [(5, 6), (0, 1)]
    target = S3.assign_food_targets(mine, foods, [], dist, ROWS, COLS)
    assert target == {0: (5, 6), 1: (0, 1)}
    assert run_base(mine, [], foods)[0] == run_screen3(mine, [], foods)[0][0]


# 10-gate: equal trades engage at 10 near friends, not the base's 14.
# Hunter (5, 5) eyes east onto (5, 6): two foes, one backing friend in
# range, fillers near but out of attack range. Ten enemies visible keep
# the crowd gate closed so only the near gate decides.


def _odds_board(fill: int) -> tuple[list[Loc], list[Loc], list[Loc]]:
    fillers = [
        (5, 0),
        (5, 1),
        (5, 2),
        (4, 0),
        (4, 1),
        (4, 2),
        (6, 0),
        (6, 1),
        (6, 2),
        (4, 3),
    ][:fill]
    far = [
        (15, 15),
        (15, 16),
        (15, 14),
        (14, 15),
        (16, 15),
        (16, 16),
        (12, 12),
        (13, 13),
    ]
    return [(5, 5), (5, 4)] + fillers, [(5, 7), (5, 8)] + far, [(5, 3)]


def test_ten_near_engages_equal_trade() -> None:
    mine, enemies, foods = _odds_board(10)
    assert len(enemies) == 10
    orders, _ = run_screen3(mine, enemies, foods)
    assert orders[0] == ((5, 5), "e")


def test_nine_near_refuses_equal_trade() -> None:
    mine, enemies, foods = _odds_board(8)
    orders, _ = run_screen3(mine, enemies, foods)
    assert orders[0] == ((5, 5), "n")
    assert orders[0] != ((5, 5), "e")


def test_base_refuses_where_screen3_trades() -> None:
    mine, enemies, foods = _odds_board(10)
    assert run_base(mine, enemies, foods)[0] != ((5, 5), "e")
    assert run_screen3(mine, enemies, foods)[0][0] == ((5, 5), "e")


# Pack gate: hunt only with 3+ friends in range, else pack up.


def test_packless_ant_packs_up_toward_friend() -> None:
    orders, _ = run_screen3([(5, 5), (5, 2)], [(5, 10)])
    assert orders[0] == ((5, 5), "w")


def test_packed_ant_seeks_in_crowd() -> None:
    far = [
        (15, 15),
        (15, 16),
        (15, 14),
        (14, 15),
        (16, 15),
        (16, 16),
        (0, 0),
        (0, 1),
        (19, 19),
    ]
    mine = [(5, 5), (5, 3), (5, 4), (6, 5)]
    orders, _ = run_screen3(mine, [(5, 10)] + far)
    assert orders[0] == ((5, 5), "e")


def test_lone_ant_explores_while_base_seeks() -> None:
    orders, _ = run_screen3([(5, 5)], [(5, 10)])
    assert orders == [((5, 5), "n")]
    assert run_base([(5, 5)], [(5, 10)]) == [((5, 5), "e")]


def test_pack_boundary_three_seeks_two_packs_up() -> None:
    enemies = [(5, 10)]
    orders, _ = run_screen3([(5, 5), (5, 0), (5, 1), (5, 2)], enemies)
    assert orders[0] == ((5, 5), "e")
    orders2, _ = run_screen3([(5, 5), (5, 0), (5, 1)], enemies)
    assert orders2[0] == ((5, 5), "w")


# Crowd gate: fearless below ten visible enemies, full safety at ten+.


def test_fearless_small_fight_where_safe_holds() -> None:
    mine = [(5, 5), (5, 2), (5, 3), (5, 1)]
    enemies = [(5, 7), (5, 8), (15, 15)]
    orders, _ = run_screen3(mine, enemies)
    assert orders[0] == ((5, 5), "e")
    assert safe_baseline(mine, enemies)[0] == ((5, 5), "n")


def test_crowd_holds_exactly_as_safe() -> None:
    mine = [(5, 5), (5, 2), (5, 3), (5, 1)]
    far = [
        (15, 15),
        (15, 16),
        (15, 14),
        (14, 15),
        (16, 15),
        (16, 16),
        (0, 0),
        (0, 1),
        (19, 19),
        (19, 18),
    ]
    enemies = [(5, 7), (5, 8)] + far
    assert len(enemies) == 12
    orders, _ = run_screen3(mine, enemies)
    assert orders == safe_baseline(mine, enemies)
    assert orders[0] != ((5, 5), "e")


def test_crowd_boundary_nine_fearless_ten_safe() -> None:
    mine = [(5, 5), (5, 2), (5, 3), (5, 1)]
    far = [
        (15, 15),
        (15, 16),
        (15, 14),
        (14, 15),
        (16, 15),
        (16, 16),
        (0, 0),
        (0, 1),
    ]
    nine = [(5, 7), (5, 8)] + far[:7]
    assert len(nine) == 9
    orders9, _ = run_screen3(mine, nine)
    assert orders9[0] == ((5, 5), "e")
    ten = [(5, 7), (5, 8)] + far[:8]
    assert len(ten) == 10
    orders10, _ = run_screen3(mine, ten)
    assert orders10 == safe_baseline(mine, ten)
    assert orders10[0] != ((5, 5), "e")


# Hole-filling: the blocked shortest step falls through to a closing
# alternate on the same goal, never via join or grinder release.


def _gap_board() -> tuple[list[Loc], list[Loc]]:
    far = [
        (15, 15),
        (15, 16),
        (15, 14),
        (14, 15),
        (16, 15),
        (16, 16),
        (0, 0),
        (0, 1),
        (0, 2),
    ]
    return [(5, 5), (5, 6), (7, 7), (7, 5)], [(6, 7)] + far


def test_blocked_hunter_fills_hole_south() -> None:
    mine, enemies = _gap_board()
    assert len(enemies) == 10
    orders, _ = run_screen3(mine, enemies)
    assert orders[0] == ((5, 5), "s")
    probe = FakeAnts(mine, enemies)
    moved = probe.destination((5, 5), orders[0][1])
    assert probe.distance(moved, (6, 7)) < probe.distance((5, 5), (6, 7))


def test_base_wanders_where_screen3_fills() -> None:
    mine, enemies = _gap_board()
    assert run_base(mine, enemies)[0] == ((5, 5), "n")
    assert run_screen3(mine, enemies)[0][0] == ((5, 5), "s")


def test_no_closing_step_falls_through_off_water() -> None:
    mine, enemies = _gap_board()
    orders, _ = run_screen3(mine, enemies, water={(6, 5)})
    assert orders[0] == ((5, 5), "n")


def test_packless_blocked_ant_never_gap_fills() -> None:
    orders, _ = run_screen3([(5, 5), (5, 6)], [(6, 7), (15, 15)])
    assert orders[0] == ((5, 5), "n")
    assert all(o != ((5, 5), "s") for o in orders)


def test_gap_fill_fearless_in_small_fight() -> None:
    mine = [(5, 5), (5, 6), (7, 7), (7, 5)]
    foes = [(6, 7), (7, 4), (6, 3), (7, 6)]
    orders, _ = run_screen3(mine, foes)
    assert orders[0] == ((5, 5), "s")
    assert safe_baseline(mine, foes)[0] == ((5, 5), "n")


def test_blocked_marcher_sidesteps_toward_same_hill() -> None:
    mine = [(5, 5), (5, 6)]
    orders, _ = run_screen3(mine, [], enemy_hills=[(6, 7)])
    assert orders == [((5, 5), "s"), ((5, 6), "e")]
    assert run_base(mine, [], enemy_hills=[(6, 7)])[0] == ((5, 5), "n")


def test_unblocked_marcher_keeps_shortest_path() -> None:
    orders, _ = run_screen3([(5, 5)], [], enemy_hills=[(6, 7)])
    assert orders == [((5, 5), "e")]


# Corridor screening: a flooded midpoint stands on the approach, not
# the nearest dry square. Hill (5, 5), foe (5, 9): the row is dammed
# at (5, 7) with the north bank closed, so the approach runs south.


def test_extra_guard_takes_corridor_tile() -> None:
    water = {(4, 5), (4, 6), (5, 7)}
    mine = [(5, 3), (4, 3)]
    orders, _ = run_screen3(mine, [(5, 9)], water=water, my_hills=[(5, 5)])
    assert orders == [((5, 3), "e"), ((4, 3), "e")]
    probe = FakeAnts(mine, [(5, 9)], water=water)
    moved = probe.destination((4, 3), orders[1][1])
    assert probe.distance(moved, (6, 7)) < probe.distance((4, 3), (6, 7))


def test_base_screener_leaves_corridor() -> None:
    water = {(4, 5), (4, 6), (5, 7)}
    mine = [(5, 3), (4, 3)]
    base = run_base(mine, [(5, 9)], water=water, my_hills=[(5, 5)])
    assert base == [((5, 3), "e"), ((4, 3), "n")]
    mine_orders, _ = run_screen3(mine, [(5, 9)], water=water, my_hills=[(5, 5)])
    assert base != mine_orders


def test_open_board_screen_matches_base() -> None:
    mine = [(10, 8), (10, 11)]
    enemies = [(10, 16)]
    orders, _ = run_screen3(mine, enemies, my_hills=[(10, 10)])
    assert orders == [((10, 8), "e"), ((10, 11), "e")]
    assert run_base(mine, enemies, my_hills=[(10, 10)]) == orders


# State, boundaries, budget, and entry hygiene.


def test_setup_resets_and_hills_remembered_then_razed() -> None:
    fake = FakeAnts([(5, 5)], [(6, 6)], enemy_hills=[(15, 15)])
    bot = S3.Screen3()
    bot.visits = {(9, 9): 5}
    bot.remembered_hills = {(1, 1)}
    bot.prev_enemies = [(0, 0)]
    bot.do_setup(fake)
    assert bot.visits == {}
    assert bot.remembered_hills == set()
    assert bot.prev_enemies == []
    bot.do_turn(fake)
    assert (15, 15) in bot.remembered_hills
    assert bot.prev_enemies == [(6, 6)]
    assert bot.visits.get((5, 5), 0) == 1
    raze = FakeAnts([(15, 15)], [])
    bot.do_turn(raze)
    assert (15, 15) not in bot.remembered_hills


def test_surrounded_ant_holds_as_base() -> None:
    mine = [(5, 5)]
    enemies = [(4, 5), (5, 6), (6, 5), (5, 4)]
    orders, _ = run_screen3(mine, enemies)
    assert orders == []
    assert run_base(mine, enemies) == []


def test_turn_is_deterministic_across_repeats() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(24)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(12)]
    foods = [((i * 5 + 2) % ROWS, (i * 9 + 1) % COLS) for i in range(10)]
    kw: dict[str, Any] = {
        "foods": foods,
        "water": {(3, 3), (3, 4), (10, 10)},
        "enemy_hills": [(15, 15)],
        "my_hills": [(0, 0)],
    }
    first, _ = run_screen3(mine, foes, **kw)
    for _ in range(3):
        again, _ = run_screen3(mine, foes, **kw)
        assert again == first


def test_full_turn_costs_under_half_second() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(12)]
    foods = [((i * 5 + 2) % ROWS, (i * 9 + 1) % COLS) for i in range(20)]
    fake = FakeAnts(mine, foes, foods)
    bot = S3.Screen3()
    start = time.perf_counter()
    bot.do_turn(fake)
    assert time.perf_counter() - start < 0.5
    assert len(fake.orders) > 0


def test_manifest_is_one_line_python_screen3() -> None:
    text = (Path(__file__).parent / "Screen3.bot").read_text().strip()
    assert text == "python Screen3.py"


def test_entry_imports_stay_stdlib_ants_combat() -> None:
    src = (Path(__file__).parent / "Screen3.py").read_text()
    tree = ast.parse(src)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert roots <= {"collections", "ants", "combat", "psyco"}, roots
    assert "sleep(" not in src
