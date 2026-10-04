#!/usr/bin/env python
"""Join-aware support tables (Tables4 entry).

Tests for the one idea past the Tables2 base: a pal counts as
support iff it is within attack range of the destination AND it is
mutually engaged (within attack range of a counted foe) OR one
step away from mutual engagement (one of its 5 stay/step options
lands within attack range of a counted foe). Battles resolve after
all ants move, so a pal that can step into the fight is real
support; a pal two or more steps out is still phantom and stays
filtered. Self-contained: stdlib plus ants.py only, never
combat.py.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Tables4 as TB  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], TB.Tables4]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = TB.Tables4()
    bot.do_turn(fake)
    return fake.orders, bot


def _sq(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


def _verdict_bot(mine: list[Loc], enemies: list[Loc]) -> TB.Tables4:
    # contact_verdict reads cached turn state; prime it directly so
    # verdict tests stay deterministic with no BFS involved.
    bot = TB.Tables4()
    bot._ants_list = list(mine)
    bot._enemy_locs = list(enemies)
    bot._home_hills = []
    bot._attack_r2 = 5
    bot._rows = ROWS
    bot._cols = COLS
    return bot


def focus_deaths(
    ours: list[Loc], theirs: list[Loc], attack_r2: int = 5
) -> tuple[set[Loc], set[Loc]]:
    """Independent reference for the engine's do_attack_focus.

    Each ant's nearby-count is its nearby-enemy total (squared
    distance within attack_r2); an ant with enemies nearby dies iff
    its minimum enemy nearby-count is <= its own. Mirrors
    tools/ants.py do_attack_focus exactly, on plain locations.
    """
    weak_o = {a: sum(1 for e in theirs if _sq(a, e) <= attack_r2) for a in ours}
    weak_t = {e: sum(1 for a in ours if _sq(e, a) <= attack_r2) for e in theirs}
    dead_o = {
        a
        for a in ours
        if weak_o[a] > 0
        and min(weak_t[e] for e in theirs if _sq(a, e) <= attack_r2) <= weak_o[a]
    }
    dead_t = {
        e
        for e in theirs
        if weak_t[e] > 0
        and min(weak_o[a] for a in ours if _sq(e, a) <= attack_r2) <= weak_t[e]
    }
    return dead_o, dead_t


def test_table_grid_still_holds() -> None:
    # The precomputed table itself is untouched by the idea: more
    # ants wins clean, equal trades, fewer loses alone.
    table = TB.build_battle_table()
    assert table[(1, 1)] == TB.TRADE
    assert table[(2, 1)] == TB.WIN
    assert table[(2, 2)] == TB.TRADE
    assert table[(3, 2)] == TB.WIN
    assert table[(1, 2)] == TB.LOSE
    assert table[(1, 0)] == TB.SAFE
    assert TB.lookup_verdict(table, 100, 100) == TB.TRADE
    assert TB.lookup_verdict(table, 100, 1) == TB.WIN
    assert TB.lookup_verdict(table, 1, 100) == TB.LOSE


def test_mutual_2v1_stays_win() -> None:
    # Covered shape: backer (4, 7) is inside attack range of both
    # the destination (5, 6) and the foe (5, 8) -- real support
    # under both the base filter and the join-aware rule.
    assert _sq((4, 7), (5, 6)) <= 5
    assert _sq((4, 7), (5, 8)) <= 5
    bot = _verdict_bot([(5, 5), (4, 7)], [(5, 8)])
    assert bot.contact_verdict((5, 6), (5, 5)) == TB.WIN


def test_far_phantom_still_filters_to_trade() -> None:
    # The filter's truth survives: backer (5, 4) is in range of the
    # destination (5, 6) but no stay/step option lands within
    # attack range of the foe (5, 8) -- closest is (5, 5) at
    # squared distance 9 -- so it stays phantom and the verdict
    # stays TRADE, exactly like the base. The engine agrees: the
    # stepping mover dies with the foe.
    assert _sq((5, 4), (5, 6)) <= 5
    assert _sq((5, 4), (5, 8)) > 5
    for cand in [(5, 4), (4, 4), (6, 4), (5, 3), (5, 5)]:
        assert _sq(cand, (5, 8)) > 5, cand
    dead_o, dead_t = focus_deaths([(5, 6), (5, 4)], [(5, 8)])
    assert dead_o == {(5, 6)}
    assert dead_t == {(5, 8)}
    bot = _verdict_bot([(5, 5), (5, 4)], [(5, 8)])
    assert bot.contact_verdict((5, 6), (5, 5)) == TB.TRADE


def test_one_step_pal_counts_as_win() -> None:
    # The discriminator: backer (3, 6) is in range of the
    # destination (5, 6) but out of range of the foe (5, 8)
    # (squared distance 8), so the base filter calls it phantom
    # and prices TRADE. But one step south to (4, 6) lands within
    # attack range of the foe (squared distance 5) -- the pal can
    # join this turn -- so join-aware prices WIN. The engine, with
    # the pal joining at (4, 6), confirms a clean WIN: the foe
    # dies, both of ours live.
    assert _sq((3, 6), (5, 6)) <= 5
    assert _sq((3, 6), (5, 8)) > 5
    assert _sq((4, 6), (5, 8)) <= 5
    dead_o, dead_t = focus_deaths([(5, 6), (4, 6)], [(5, 8)])
    assert dead_o == set()
    assert dead_t == {(5, 8)}
    bot = _verdict_bot([(5, 5), (3, 6)], [(5, 8)])
    assert bot.contact_verdict((5, 6), (5, 5)) == TB.WIN


def test_two_steps_out_stays_phantom() -> None:
    # One step is the whole relaxation: backer (3, 4) is in range
    # of the destination (5, 6) (squared distance 8 > 5 -- pick a
    # pal in range instead: (4, 4) is squared 1 + 4 = 5 from the
    # destination) yet no stay/step option reaches the foe (5, 8),
    # so the verdict stays TRADE.
    assert _sq((4, 4), (5, 6)) <= 5
    for cand in [(4, 4), (3, 4), (5, 4), (4, 3), (4, 5)]:
        assert _sq(cand, (5, 8)) > 5, cand
    bot = _verdict_bot([(5, 5), (4, 4)], [(5, 8)])
    assert bot.contact_verdict((5, 6), (5, 5)) == TB.TRADE


_DUEL_MINE = [(5, 5)]
_DUEL_FOE = [(5, 8)]
_NEAR_HILL = [(12, 0)]
_FAR_HILL = [(15, 15)]


def test_1v1_near_own_hill_engages() -> None:
    # Unchanged hill gate: friendless trade within radius 14 of a
    # held home hill still goes through east.
    probe = FakeAnts(_DUEL_MINE, _DUEL_FOE)
    assert probe.distance((5, 6), _NEAR_HILL[0]) == 13
    assert probe.distance(_NEAR_HILL[0], _DUEL_FOE[0]) > 10
    orders, _ = run_turn(_DUEL_MINE, _DUEL_FOE, my_hills=_NEAR_HILL)
    assert orders[0] == ((5, 5), "e")


def test_1v1_far_from_hill_refuses() -> None:
    # Unchanged hill gate: the same friendless trade far from any
    # hill still refuses east and explores north.
    orders, _ = run_turn(_DUEL_MINE, _DUEL_FOE, my_hills=_FAR_HILL)
    assert orders == [((5, 5), "n")]
    assert ((5, 5), "e") not in orders


def test_scenario_covered_mutual_2v1_advances() -> None:
    # Benchmark 1 (covered shape): real 2v1 backing -- the tuned
    # bot steps east into the winning fight, exactly like base.
    orders, _ = run_turn([(5, 5), (4, 7)], [(5, 8)])
    assert orders[0] == ((5, 5), "e")


def test_scenario_far_phantom_2v1_refuses() -> None:
    # Benchmark 2 (filter truth): far-phantom backing -- tuned
    # still refuses east and explores north (no hills, no cover),
    # exactly like base.
    orders, _ = run_turn([(5, 5), (5, 4)], [(5, 8)])
    assert ((5, 5), "e") not in orders
    assert orders[0] == ((5, 5), "n")


def test_scenario_one_step_pal_advances() -> None:
    # Benchmark 3 (the recovered take): one-step backing -- base
    # reads TRADE and refuses, tuned reads WIN and steps east
    # into a fight the engine scores a clean win when the pal
    # joins (test_one_step_pal_counts_as_win).
    orders, _ = run_turn([(5, 5), (3, 6)], [(5, 8)])
    assert orders[0] == ((5, 5), "e")


def test_scenario_outnumbered_1v2_still_refuses() -> None:
    # No pals at all: ours 1 vs 2 is LOSE under every counting
    # rule, so the ant explores north even near a hill.
    orders, _ = run_turn([(5, 5)], [(5, 8), (6, 7)], my_hills=_NEAR_HILL)
    assert orders == [((5, 5), "n")]
    assert ((5, 5), "e") not in orders


def test_per_decision_still_fast() -> None:
    # One contact decision stays far under 0.1ms: the one-step
    # options are 5 squared-distance checks per pal, no search.
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(12)]
    _, bot = run_turn(mine, foes, my_hills=[(0, 0)])
    dests = [((i * 3) % ROWS, (i * 5) % COLS) for i in range(12)]
    reps = 200
    start = time.perf_counter()
    for _ in range(reps):
        for dest in dests:
            bot.contact_verdict(dest, mine[0])
    elapsed = (time.perf_counter() - start) / (reps * len(dests))
    assert elapsed < 0.0001


def test_full_turn_crowded_under_1s() -> None:
    # A full crowded turn stays well inside the turn budget.
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(12)]
    foods = [((i * 3 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(10)]
    start = time.perf_counter()
    run_turn(mine, foes, foods, my_hills=[(0, 0)], enemy_hills=[(19, 19)])
    assert time.perf_counter() - start < 1.0


def test_no_live_resolution_in_source() -> None:
    # Fidelity: per-turn code never re-derives outcomes (no
    # weakness arithmetic), it only counts locals and looks up.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Tables4.py")
    with open(path) as fh:
        source = fh.read()
    assert "weakness" not in source
    assert "import combat" not in source
    assert "from combat" not in source
