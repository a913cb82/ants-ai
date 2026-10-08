#!/usr/bin/env python
"""Codetiger precomputed-resolution combat tables (Tables entry).

Faithful port of the codetiger Python datapoint
(autoresearch/docs/RESEARCH.md, "codetiger Python time datapoint"):
full battle search is infeasible in Python under the turn limit, so
local battle outcomes are PRECOMPUTED once at setup into lookup
tables derived from the engine's focus-battle rules (an ant dies
iff its minimum enemy nearby-count is <= its own nearby-count).
Per-turn contact decisions
are pure table lookups -- the turn loop never resolves a battle
live per ant. Friendless 1v1 sacrifices (mutual-death trades) are
allowed ONLY within radius 14 of a held home hill, hiding the
replacement cost; elsewhere they always refuse.

Board economy (clustered denial food claims), muster, guard,
reinforce, explore, and walk-off match champion Crowd; only the
combat core (majority filter, join, grinder, crowd-fearless,
influence) is replaced by the table lookup plus the hill-gated
trade rule. This file is self-contained: stdlib plus ants.py only,
never combat.py.
"""

import importlib.util
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Tables as TB  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], TB.Tables]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = TB.Tables()
    bot.do_turn(fake)
    return fake.orders, bot


def _sq(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


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


def test_table_1v1_is_mutual_trade() -> None:
    # Hand-verified: lone pair, nearby-count 1 each, so 1 <= 1 kills both.
    dead_o, dead_t = focus_deaths([(5, 5)], [(5, 6)])
    assert dead_o == {(5, 5)}
    assert dead_t == {(5, 6)}
    assert TB.build_battle_table()[(1, 1)] == TB.TRADE


def test_table_2v1_is_clean_win() -> None:
    # Hand-verified: each of ours sees 1 foe (nearby-count 1) while
    # the foe sees 2 (nearby-count 2); 2 <= 1 is false so ours live, and
    # 1 <= 2 kills the foe.
    ours = [(5, 5), (5, 6)]
    theirs = [(5, 7)]
    dead_o, dead_t = focus_deaths(ours, theirs)
    assert dead_o == set()
    assert dead_t == {(5, 7)}
    assert TB.build_battle_table()[(2, 1)] == TB.WIN


def test_table_2v2_is_mutual_trade() -> None:
    # Hand-verified: all four mutually in range, nearby-count 2 each,
    # so 2 <= 2 kills every ant.
    ours = [(5, 5), (6, 5)]
    theirs = [(5, 6), (6, 6)]
    dead_o, dead_t = focus_deaths(ours, theirs)
    assert dead_o == set(ours)
    assert dead_t == set(theirs)
    assert TB.build_battle_table()[(2, 2)] == TB.TRADE


def test_table_3v2_is_clean_win() -> None:
    # Hand-verified: ours nearby-count 2 each, foes nearby-count 3;
    # 3 <= 2 is false so all three live, and 2 <= 3 kills both foes.
    ours = [(5, 5), (6, 5), (5, 4)]
    theirs = [(5, 6), (6, 6)]
    dead_o, dead_t = focus_deaths(ours, theirs)
    assert dead_o == set()
    assert dead_t == set(theirs)
    assert TB.build_battle_table()[(3, 2)] == TB.WIN


# Hand-verified outcome grid from the focus rule under mutual
# contact: our ant dies iff O <= E, their ant dies iff E <= O, so
# O > E is a clean WIN, O == E a mutual TRADE, O < E a LOSE.
EXPECTED_GRID: dict[tuple[int, int], str] = {
    (1, 1): TB.TRADE,
    (1, 2): TB.LOSE,
    (1, 3): TB.LOSE,
    (1, 4): TB.LOSE,
    (2, 1): TB.WIN,
    (2, 2): TB.TRADE,
    (2, 3): TB.LOSE,
    (2, 4): TB.LOSE,
    (3, 1): TB.WIN,
    (3, 2): TB.WIN,
    (3, 3): TB.TRADE,
    (3, 4): TB.LOSE,
    (4, 1): TB.WIN,
    (4, 2): TB.WIN,
    (4, 3): TB.WIN,
    (4, 4): TB.TRADE,
}


def test_table_matches_focus_rule_on_grid() -> None:
    table = TB.build_battle_table()
    for key, expected in EXPECTED_GRID.items():
        assert table[key] == expected, key


def test_tables_built_at_setup() -> None:
    # The lookup table exists from construction (engine calls
    # do_setup once; tests drive do_turn directly) and rebuilds on
    # do_setup, covering the full 1..4 grid plus the empty square.
    bot = TB.Tables()
    assert bot.battle_table[(1, 1)] == TB.TRADE
    assert bot.battle_table[(3, 2)] == TB.WIN
    bot.do_setup(FakeAnts([(5, 5)], []))
    assert bot.battle_table[(2, 2)] == TB.TRADE
    assert bot.battle_table[(1, 0)] == TB.SAFE


def test_lookup_clamps_huge_crowds() -> None:
    # Crowded boards can stack more ants in radius than the table
    # spans; the lookup clamps instead of raising KeyError, and the
    # verdict still follows the rule (more wins, equal trades).
    table = TB.build_battle_table()
    assert TB.lookup_verdict(table, 100, 100) == TB.TRADE
    assert TB.lookup_verdict(table, 100, 1) == TB.WIN
    assert TB.lookup_verdict(table, 1, 100) == TB.LOSE


def test_no_live_resolution_in_source() -> None:
    # Fidelity: per-turn code never re-derives outcomes (no
    # weakness arithmetic), it only counts locals and looks up.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Tables.py")
    with open(path) as fh:
        source = fh.read()
    assert "weakness" not in source
    assert "import combat" not in source
    assert "from combat" not in source


# 1v1 hill-gate boards: ant (5, 5) eyes the step east onto (5, 6)
# against one foe at (5, 8) (squared distance 4, in contact) with
# no friends anywhere -- a friendless mutual-death trade. The hill
# sits 13 steps from the destination but 15 from the foe, so the
# hill is never threatened and the seek branch decides alone.
_DUEL_MINE = [(5, 5)]
_DUEL_FOE = [(5, 8)]
_NEAR_HILL = [(12, 0)]
_FAR_HILL = [(15, 15)]


def test_1v1_near_own_hill_engages() -> None:
    # Destination (5, 6) is 7 + 6 = 13 steps from (12, 0): within
    # the codetiger radius, so the sacrifice goes through east.
    probe = FakeAnts(_DUEL_MINE, _DUEL_FOE)
    assert probe.distance((5, 6), _NEAR_HILL[0]) == 13
    assert probe.distance(_NEAR_HILL[0], _DUEL_FOE[0]) > 10
    orders, _ = run_turn(_DUEL_MINE, _DUEL_FOE, my_hills=_NEAR_HILL)
    assert orders[0] == ((5, 5), "e")


def test_1v1_far_from_hill_refuses() -> None:
    # Identical board except the hill moves to (15, 15), 10 + 9 =
    # 19 steps from the destination: the same trade refuses and the
    # ant explores north instead.
    probe = FakeAnts(_DUEL_MINE, _DUEL_FOE)
    assert probe.distance((5, 6), _FAR_HILL[0]) == 19
    assert probe.distance(_FAR_HILL[0], _DUEL_FOE[0]) > 10
    orders, _ = run_turn(_DUEL_MINE, _DUEL_FOE, my_hills=_FAR_HILL)
    assert orders == [((5, 5), "n")]
    assert ((5, 5), "e") not in orders


def test_boundary_exactly_14_engages() -> None:
    # Exactly 14 steps (8 + 6) from the destination is still
    # "within radius 14": the duel goes through east.
    hill = [(13, 0)]
    probe = FakeAnts(_DUEL_MINE, _DUEL_FOE)
    assert probe.distance((5, 6), hill[0]) == 14
    assert probe.distance(hill[0], _DUEL_FOE[0]) > 10
    orders, _ = run_turn(_DUEL_MINE, _DUEL_FOE, my_hills=hill)
    assert orders[0] == ((5, 5), "e")


def test_boundary_15_refuses() -> None:
    # One step past the radius (8 + 7 = 15): the identical duel
    # refuses and explores north.
    hill = [(13, 19)]
    probe = FakeAnts(_DUEL_MINE, _DUEL_FOE)
    assert probe.distance((5, 6), hill[0]) == 15
    assert probe.distance(hill[0], _DUEL_FOE[0]) > 10
    orders, _ = run_turn(_DUEL_MINE, _DUEL_FOE, my_hills=hill)
    assert orders == [((5, 5), "n")]
    assert ((5, 5), "e") not in orders


def test_backed_2v1_advances_without_hills() -> None:
    # Table WIN needs no hill cover: (5, 5) steps east onto (5, 6)
    # with (5, 4) backing (ours 2 vs 1) and no hills held at all.
    mine = [(5, 5), (5, 4)]
    orders, _ = run_turn(mine, _DUEL_FOE)
    assert orders[0] == ((5, 5), "e")


def test_outnumbered_1v2_refuses_without_hills() -> None:
    # Table LOSE refuses even near a hill: (5, 5) facing (5, 8) and
    # (6, 7) from (5, 6) is ours 1 vs 2, so it explores north.
    foes = [(5, 8), (6, 7)]
    probe = FakeAnts([(5, 5)], foes)
    assert _sq((5, 6), (5, 8)) <= 5
    assert _sq((5, 6), (6, 7)) <= 5
    assert probe.distance((5, 6), _NEAR_HILL[0]) <= 14
    orders, _ = run_turn([(5, 5)], foes, my_hills=_NEAR_HILL)
    assert orders == [((5, 5), "n")]
    assert ((5, 5), "e") not in orders


def _load_champion() -> Any:
    import subprocess
    import tempfile

    src = subprocess.run(
        ["git", "show", "champion/main:autoresearch/bot/Crowd.py"],
        capture_output=True,
        check=True,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    ).stdout.decode()
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(src)
        champ_path = fh.name
    spec = importlib.util.spec_from_file_location("champion_Crowd", champ_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_economy_matches_champion_without_contact() -> None:
    # No enemies anywhere: food claims and explore fall-through run
    # the carried-forward champion code, so every order matches.
    module = _load_champion()
    crowd_cls = module.Crowd

    def crowd_orders(
        mine: list[Loc],
        enemies: list[Loc],
        foods: list[Loc] | None = None,
        my_hills: list[Loc] | None = None,
    ) -> list[tuple[Loc, str]]:
        fake = FakeAnts(mine, enemies, foods, my_hills=my_hills)
        crowd_cls().do_turn(fake)
        return fake.orders

    mine = [(5, 5), (2, 2)]
    foods = [(5, 6), (2, 3)]
    orders, _ = run_turn(mine, [], foods)
    assert orders == crowd_orders(mine, [], foods) == [((5, 5), "e"), ((2, 2), "e")]
    lone, _ = run_turn([(10, 10)], [])
    assert lone == crowd_orders([(10, 10)], []) == [((10, 10), "n")]


def test_guard_and_muster_match_champion() -> None:
    # Threatened hill plus a far enemy: the holder steps onto the
    # hill and the extra screens to the (10, 13) intercept -- both
    # squares contact-free, so the table safety agrees with the
    # champion filter and every order matches. Muster with no
    # enemies visible marches the remembered hill identically.
    module = _load_champion()
    crowd_cls = module.Crowd
    mine = [(10, 8), (10, 11)]
    enemies = [(10, 16)]
    orders, _ = run_turn(mine, enemies, my_hills=[(10, 10)])
    fake = FakeAnts(mine, enemies, my_hills=[(10, 10)])
    crowd_cls().do_turn(fake)
    assert orders == fake.orders == [((10, 8), "e"), ((10, 11), "e")]
    tables_muster, _ = run_turn([(10, 10)], [], enemy_hills=[(15, 15)])
    fake2 = FakeAnts([(10, 10)], [], enemy_hills=[(15, 15)])
    crowd_cls().do_turn(fake2)
    assert tables_muster == fake2.orders
    assert len(tables_muster) == 1


def test_per_decision_under_point1ms() -> None:
    # The codetiger point is Python speed: one contact decision is
    # a local count plus a dict lookup, far under 0.1ms.
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
    # A full crowded turn -- 48 ants, 12 foes, food, hills -- stays
    # well inside the turn budget.
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(12)]
    foods = [((i * 3 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(10)]
    start = time.perf_counter()
    run_turn(mine, foes, foods, my_hills=[(0, 0)], enemy_hills=[(19, 19)])
    assert time.perf_counter() - start < 1.0
