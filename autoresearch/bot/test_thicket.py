#!/usr/bin/env python
"""Thicket tests: hill attacks commit only with a local majority.

Crowd floods every remembered hill unconditionally; trickling ants
donate into defended hills (the Bulwark wound: 86 ants, zero razes).
Thicket keeps Crowd's full combat chain and gates only the hill
march: an ant marches on a remembered hill iff no visible enemy
stands within COMMIT_RADIUS of it, or our ants within that radius
strictly outnumber those defenders. Outnumbered marches fall
through to reinforce/explore instead of donating.

No engine games. FakeAnts covers do_turn's interface; Crowd is the
regression oracle (Thicket == Crowd whenever the gate passes).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Crowd as CP  # noqa: E402
import Thicket as TH  # noqa: E402

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
    ) -> None:
        self.rows = rows
        self.cols = cols
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


def run_thicket(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
    rows: int = ROWS,
    cols: int = COLS,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills, rows, cols)
    bot = TH.Thicket()
    bot.do_turn(fake)
    return fake.orders


def run_crowd(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
    rows: int = ROWS,
    cols: int = COLS,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills, rows, cols)
    bot = CP.Crowd()
    bot.do_turn(fake)
    return fake.orders


def dist(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


def test_commit_radius_constant() -> None:
    assert TH.COMMIT_RADIUS == 15


def test_empty_hill_always_commits() -> None:
    # No visible defenders: race the empty hill even with nobody near.
    assert TH.hill_commit_ok((15, 15), [(5, 5)], [], dist) is True
    assert TH.hill_commit_ok((15, 15), [], [], dist) is True


def test_outnumbered_hill_refuses() -> None:
    # 0 attackers vs 3 defenders within radius: hold, do not donate.
    mine = [(5, 5), (5, 6)]
    enemies = [(15, 15), (15, 16), (14, 15)]
    assert TH.hill_commit_ok((15, 15), mine, enemies, dist) is False


def test_majority_hill_commits() -> None:
    # 3 attackers vs 1 defender within radius: march.
    mine = [(15, 10), (15, 11), (14, 10)]
    enemies = [(15, 16)]
    assert TH.hill_commit_ok((15, 15), mine, enemies, dist) is True


def test_equal_numbers_refuse() -> None:
    # 2 vs 2 is mutual death with no raze: hold exactly as outnumbered.
    mine = [(15, 10), (15, 11)]
    enemies = [(15, 16), (16, 15)]
    assert TH.hill_commit_ok((15, 15), mine, enemies, dist) is False


def test_claimed_ants_do_not_count_as_attackers() -> None:
    # Pure shape: only marchable ants count. Two defenders hold
    # against two marchers even with a third claimed ant nearby.
    marchers = [(15, 9), (15, 11)]
    enemies = [(15, 16), (15, 17)]
    assert TH.hill_commit_ok((15, 15), marchers, enemies, dist) is False
    assert TH.hill_commit_ok((15, 15), marchers + [(15, 10)], enemies, dist) is True


def test_commit_radius_scales_with_argument() -> None:
    # The radius argument scopes the count: an enemy 10 away
    # defends under the default 15 but not under radius 5.
    mine = [(15, 15)]
    enemies = [(15, 5)]
    assert TH.hill_commit_ok((15, 15), mine, enemies, dist) is False
    assert TH.hill_commit_ok((15, 15), mine, enemies, dist, radius=5) is True


def test_far_armies_do_not_count() -> None:
    # Armies beyond the radius are marching distance away: ignored.
    mine = [(5, 5)]
    enemies = [(5, 6)]
    assert TH.hill_commit_ok((15, 15), mine, enemies, dist) is True


def test_defended_hill_skips_muster_where_crowd_marches() -> None:
    # One far ant, three defenders on the remembered hill: Crowd
    # marches east toward it; Thicket refuses the march (and the
    # same-hill reinforce) and explores north instead.
    mine = [(5, 5)]
    enemies = [(5, 11), (5, 12), (5, 13)]
    thicket = run_thicket(mine, enemies, enemy_hills=[(5, 12)])
    crowd = run_crowd(mine, enemies, enemy_hills=[(5, 12)])
    assert crowd == [((5, 5), "e")]
    assert thicket == [((5, 5), "n")]
    assert thicket != crowd


def test_claimed_ant_near_hill_does_not_trigger_march() -> None:
    # (10, 3) claims the food at (10, 2) and walks west to it, so
    # only (10, 5) and (10, 7) can march: 2 attackers vs 2
    # defenders refuses, while Crowd marches both east.
    mine = [(10, 3), (10, 5), (10, 7)]
    foods = [(10, 2)]
    enemies = [(4, 14), (4, 15)]
    thicket = run_thicket(mine, enemies, foods, enemy_hills=[(10, 10)])
    crowd = run_crowd(mine, enemies, foods, enemy_hills=[(10, 10)])
    assert crowd == [((10, 3), "w"), ((10, 5), "e"), ((10, 7), "e")]
    assert thicket == [((10, 3), "w"), ((10, 5), "n"), ((10, 7), "n")]
    assert thicket != crowd


def test_weak_hill_marches_exactly_as_crowd() -> None:
    # Local majority at the hill: every order matches Crowd.
    mine = [(15, 10), (15, 11), (14, 10), (5, 5)]
    enemies = [(15, 16)]
    thicket = run_thicket(mine, enemies, enemy_hills=[(15, 15)])
    crowd = run_crowd(mine, enemies, enemy_hills=[(15, 15)])
    assert thicket == crowd


def test_refused_muster_falls_through_to_weak_reinforce() -> None:
    # Two remembered hills: the army-nearest muster hill (5, 12)
    # holds three defenders (refused), while the far hill (15, 2)
    # is unseen and empty (accepted) -- the ant reinforces the
    # weak hill instead of trickling down a safe path to donate.
    mine = [(5, 5)]
    enemies = [(5, 11), (5, 12), (5, 13)]
    thicket = run_thicket(mine, enemies, enemy_hills=[(5, 12), (15, 2)])
    crowd = run_crowd(mine, enemies, enemy_hills=[(5, 12), (15, 2)])
    assert crowd == [((5, 5), "e")]
    assert thicket != crowd
    assert thicket[0][0] == (5, 5)
    probe = FakeAnts(mine, enemies)
    assert probe.distance((5, 5), (5, 12)) < probe.distance((5, 5), (15, 2))
    assert TH.hill_commit_ok((5, 12), mine, enemies, probe.distance) is False
    assert TH.hill_commit_ok((15, 2), mine, enemies, probe.distance) is True
    moved = probe.destination((5, 5), thicket[0][1])
    assert probe.distance(moved, (15, 2)) < probe.distance((5, 5), (15, 2))


def test_undefended_hills_match_crowd_on_seeded_boards() -> None:
    # The gate is the only difference: with every remembered hill
    # undefended, Thicket matches Crowd on every seeded board --
    # food, guards, seekers, musters, reinforcements, explores.
    import random

    rng = random.Random(20261008)
    for _ in range(12):
        mine = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(6)]
        enemies = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(4)]
        foods = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(3)]
        hill = (rng.randrange(ROWS), rng.randrange(COLS))
        if any(dist(hill, e) <= TH.COMMIT_RADIUS for e in enemies):
            continue
        assert run_thicket(mine, enemies, foods, enemy_hills=[hill]) == run_crowd(
            mine, enemies, foods, enemy_hills=[hill]
        )


def test_walk_off_matches_crowd() -> None:
    # Held ants still step off home hills: the hill ant moves off
    # exactly as Crowd.
    mine = [(0, 0), (10, 4)]
    enemies = [(10, 16)]
    foods = [(10, 3)]
    thicket_fake = FakeAnts(mine, enemies, foods, my_hills=[(0, 0)])
    crowd_fake = FakeAnts(mine, enemies, foods, my_hills=[(0, 0)])
    thicket_bot, crowd_bot = TH.Thicket(), CP.Crowd()
    thicket_bot.do_turn(thicket_fake)
    crowd_bot.do_turn(crowd_fake)
    assert thicket_fake.orders == crowd_fake.orders
    assert thicket_fake.orders[0][0] == (0, 0)


def test_water_board_matches_crowd_when_gate_passes() -> None:
    # Water maze between ant and weak hill: pathing still matches
    # Crowd exactly once the gate commits.
    mine = [(5, 5)]
    enemies = [(15, 16)]
    water = {(5, 6), (5, 7), (6, 6)}
    thicket = run_thicket(mine, enemies, water=water, enemy_hills=[(5, 12)])
    crowd = run_crowd(mine, enemies, water=water, enemy_hills=[(5, 12)])
    assert thicket == crowd


def test_full_turn_under_1s_at_200_ants() -> None:
    # Late-game FFA scale on a real-size board: 200 ants, 30 foes,
    # food, and 10 remembered hills still clear the 1000 ms turn
    # budget (the gate skips doomed march pathing).
    mine = [(i % 100, (i * 37) % 100) for i in range(200)]
    foes = [((i * 13 + 5) % 100, (i * 11 + 3) % 100) for i in range(30)]
    foods = [((i * 5 + 1) % 100, (i * 3 + 2) % 100) for i in range(40)]
    hills = [(i * 7 % 100, (i * 11 + 5) % 100) for i in range(10)]
    start = time.perf_counter()
    run_thicket(
        mine, foes, foods, enemy_hills=hills, my_hills=[(0, 0)], rows=100, cols=100
    )
    assert time.perf_counter() - start < 1.0


def test_full_turn_under_1s_with_many_hills() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(100)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(12)]
    hills = [(i % ROWS, (i * 5 + 3) % COLS) for i in range(20)]
    start = time.perf_counter()
    run_thicket(mine, foes, enemy_hills=hills, my_hills=[(0, 0)])
    assert time.perf_counter() - start < 1.0


def test_no_drift_outside_the_gate_on_seeded_boards() -> None:
    # The gate is the only difference: whenever no remembered
    # hill holds a defender within COMMIT_RADIUS, every gate
    # passes and Thicket must equal Crowd -- on any board, with
    # food, water, guards, seekers, and hills in play.
    import random

    rng = random.Random(774129)
    big = FakeAnts([], [])
    big.rows, big.cols = 100, 100
    checked = 0
    for _ in range(40):
        mine = [(rng.randrange(100), rng.randrange(100)) for _ in range(8)]
        enemies = [(rng.randrange(100), rng.randrange(100)) for _ in range(5)]
        foods = [(rng.randrange(100), rng.randrange(100)) for _ in range(4)]
        water = {(rng.randrange(100), rng.randrange(100)) for _ in range(6)}
        water -= set(mine) | set(enemies) | set(foods)
        hills = [(rng.randrange(100), rng.randrange(100)) for _ in range(3)]
        my_hills = [(rng.randrange(100), rng.randrange(100))]
        if any(big.distance(h, e) <= TH.COMMIT_RADIUS for h in hills for e in enemies):
            continue
        checked += 1
        assert run_thicket(
            mine, enemies, foods, water, hills, my_hills, 100, 100
        ) == run_crowd(mine, enemies, foods, water, hills, my_hills, 100, 100)
    assert checked > 0


def test_crowd_of_enemies_still_refuses_defended_hill() -> None:
    # FFA shape: 12 enemies visible, three defending the remembered
    # hill, our lone hunter too far to help. The gate refuses 0v3
    # while Crowd trickles east down a safe path.
    mine = [(50, 50)]
    near = [(50, 56), (50, 57), (51, 56)]
    far = [
        (5, 5),
        (5, 95),
        (95, 5),
        (95, 95),
        (5, 50),
        (95, 50),
        (50, 5),
        (50, 95),
        (30, 30),
    ]
    enemies = near + far
    assert len(enemies) == 12
    hills = [(50, 58)]
    probe = FakeAnts(mine, enemies, rows=100, cols=100)
    assert TH.hill_commit_ok((50, 58), mine, enemies, probe.distance) is False
    thicket = run_thicket(mine, enemies, enemy_hills=hills, rows=100, cols=100)
    crowd = run_crowd(mine, enemies, enemy_hills=hills, rows=100, cols=100)
    assert crowd[0] == ((50, 50), "e")
    assert thicket != crowd


def test_big_board_defended_hill_refuses_where_crowd_marches() -> None:
    # Real-scale board: one far hunter, three defenders on the
    # remembered hill. The march path is safe, so Crowd trickles
    # east; Thicket refuses 1v3 and explores north instead.
    mine = [(50, 50)]
    enemies = [(50, 60), (50, 61), (51, 60)]
    hills = [(50, 62)]
    thicket = run_thicket(mine, enemies, enemy_hills=hills, rows=100, cols=100)
    crowd = run_crowd(mine, enemies, enemy_hills=hills, rows=100, cols=100)
    assert crowd == [((50, 50), "e")]
    assert thicket == [((50, 50), "n")]


def test_big_board_majority_matches_crowd() -> None:
    # Real-scale board: four nearby hunters vs one defender --
    # commit, so every order matches Crowd.
    mine = [(50, 50), (50, 51), (51, 50), (49, 50)]
    enemies = [(50, 61)]
    hills = [(50, 62)]
    assert run_thicket(
        mine, enemies, enemy_hills=hills, rows=100, cols=100
    ) == run_crowd(mine, enemies, enemy_hills=hills, rows=100, cols=100)


def test_remembered_hills_and_headings_persist_across_turns() -> None:
    # Turn 1 sights the defended hill; turn 2 (same bot) still
    # refuses it, with the enemy matched to a heading.
    mine = [(50, 50)]
    enemies = [(50, 60), (50, 61), (51, 60)]
    bot = TH.Thicket()
    first = FakeAnts(mine, enemies, enemy_hills=[(50, 62)], rows=100, cols=100)
    bot.do_turn(first)
    assert bot.remembered_hills == {(50, 62)}
    assert first.orders == [((50, 50), "n")]
    second = FakeAnts(mine, enemies, rows=100, cols=100)
    bot.do_turn(second)
    assert bot.remembered_hills == {(50, 62)}
    assert second.orders == [((50, 50), "n")]


def test_guard_still_fires_before_refused_muster() -> None:
    # A threatened home hill drafts the ant before the hills
    # branch: even with a defended remembered hill on the board,
    # both bots step onto the home hill.
    mine = [(10, 9)]
    enemies = [(10, 15)]
    thicket = run_thicket(mine, enemies, enemy_hills=[(0, 0)], my_hills=[(10, 10)])
    assert thicket == [((10, 9), "e")]
    assert thicket == run_crowd(
        mine, enemies, enemy_hills=[(0, 0)], my_hills=[(10, 10)]
    )


def test_no_hills_matches_crowd() -> None:
    # Gate touches the hill march only: no remembered hills, food,
    # guards, seekers, and explorers all match Crowd exactly.
    cases = [
        ([(5, 5)], [(5, 10)], None, None, [(10, 12)]),
        ([(5, 5), (2, 2)], [(5, 12), (2, 6)], [(5, 6)], None, None),
        ([(10, 8), (10, 11)], [(10, 16)], None, None, [(10, 10)]),
        ([(5, 5), (5, 3), (5, 4), (6, 5)], [(5, 10)], None, None, None),
    ]
    for mine, enemies, foods, water, my_hills in cases:
        assert run_thicket(mine, enemies, foods, water, None, my_hills) == run_crowd(
            mine, enemies, foods, water, None, my_hills
        )


def test_commit_gate_under_1ms_on_crowded_board() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(12)]
    hills = [(10, 10), (3, 17), (15, 4)]
    reps = 50
    start = time.perf_counter()
    for _ in range(reps):
        for hill in hills:
            TH.hill_commit_ok(hill, mine, foes, dist)
    elapsed = (time.perf_counter() - start) / (reps * len(hills))
    assert elapsed < 0.001


def test_full_turn_under_1s_on_crowded_board() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(12)]
    foods = [((i * 5 + 1) % ROWS, (i * 3 + 2) % COLS) for i in range(10)]
    start = time.perf_counter()
    run_thicket(mine, foes, foods, enemy_hills=[(10, 10)], my_hills=[(0, 0)])
    assert time.perf_counter() - start < 1.0
