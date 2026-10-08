#!/usr/bin/env python
"""Bound-support precomputed-resolution combat tables (Tables7 entry).

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

import Tables7 as TB  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], TB.Tables7]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = TB.Tables7()
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
    bot = TB.Tables7()
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
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Tables7.py")
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

    here = os.path.dirname(os.path.abspath(__file__))

    def show(ref_path: str) -> str:
        return subprocess.run(
            ["git", "show", ref_path],
            capture_output=True,
            check=True,
            cwd=here,
        ).stdout.decode()

    tmpdir_ctx = tempfile.TemporaryDirectory(prefix="champion_")
    with tmpdir_ctx as tmpdir:
        with open(os.path.join(tmpdir, "champion_Crowd.py"), "w") as fh:
            fh.write(show("champion/main:autoresearch/bot/Crowd.py"))
        # Crowd.py does `import combat`: stage the champion's shared
        # module beside it so the import resolves off sys.path.
        with open(os.path.join(tmpdir, "combat.py"), "w") as fh:
            fh.write(show("champion/main:autoresearch/bot/combat.py"))
        champ_path = os.path.join(tmpdir, "champion_Crowd.py")
        spec = importlib.util.spec_from_file_location("champion_Crowd", champ_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, tmpdir)
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.remove(tmpdir)
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


# Bound support (Tables7): the table counts only pals that stand
# to fight -- claim-free ants and contested-cluster denial holders
# at their live squares. Greedy harvesters walking away from the
# fight are phantom backing, and moved ants cover their live
# destinations, not their stale squares.


def test_contact_verdict_uses_live_squares() -> None:
    # (5,5) eyes east onto (5,6) against one foe at (5,8): with
    # the pal's stale square (5,4) in range the contact is WIN,
    # but the pal already stepped west to (5,3), out of range,
    # so the live count reads TRADE. A pal outside the bound set
    # never counts.
    bot = TB.Tables7()
    bot._rows, bot._cols = ROWS, COLS
    bot._attack_r2 = 5
    bot._ants_list = [(5, 5), (5, 4)]
    bot._enemy_locs = [(5, 8)]
    bot._bound = {(5, 5), (5, 4)}
    bot._moved = {}
    assert bot.contact_verdict((5, 6), (5, 5)) == TB.WIN
    bot._moved = {(5, 4): (5, 3)}
    assert bot.contact_verdict((5, 6), (5, 5)) == TB.TRADE
    bot._moved = {}
    bot._bound = {(5, 5)}
    assert bot.contact_verdict((5, 6), (5, 5)) == TB.TRADE


def test_claimant_pal_does_not_back_contact() -> None:
    # (5,5) eyes the 1v1 step east onto (5,6) against (5,8). The
    # only pal at (5,4) holds the (5,3) food claim, so bound
    # support excludes it: ours 1 vs 1 is TRADE with no hills
    # held, and the ant explores north instead of engaging.
    orders, _ = run_turn([(5, 5), (5, 4)], [(5, 8)], foods=[(5, 3)])
    assert orders == [((5, 5), "n"), ((5, 4), "w")]


def test_moved_away_pal_no_longer_covers() -> None:
    # B musters west toward remembered (5,0) before A decides:
    # stale (5,4) covers the (5,6) contact but live (5,3) does
    # not, so A reads TRADE with no hills held and refuses east.
    # The vacated (5,4) still reads occupied mid-turn, so the
    # muster fallback cannot step back into it and A explores
    # north instead. Stale counting would read WIN and step east.
    orders, _ = run_turn([(5, 4), (5, 5)], [(5, 8)], enemy_hills=[(5, 0)])
    assert orders == [((5, 4), "w"), ((5, 5), "n")]


def test_moved_toward_pal_covers_at_live_square() -> None:
    # B starts at (5,3), out of range of the (5,6) contact, and
    # seeks east onto (5,4) first. Bound support counts the live
    # square: ours 2 vs 1 is WIN, so A steps east with it. Stale
    # counting leaves B out of range and refuses the contact.
    orders, _ = run_turn([(5, 3), (5, 5)], [(5, 8)])
    assert orders == [((5, 3), "e"), ((5, 5), "e")]


def test_differs_from_base_on_muster_board() -> None:
    # The identical board under the Tables base: stale counting
    # backs the contact, so A steps east. Tables7 refuses it --
    # the entry decides differently from the base rule.
    import importlib.util as _ilu

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Tables.py")
    spec = _ilu.spec_from_file_location("base_Tables", path)
    assert spec is not None and spec.loader is not None
    base = _ilu.module_from_spec(spec)
    spec.loader.exec_module(base)
    fake = FakeAnts([(5, 4), (5, 5)], [(5, 8)], enemy_hills=[(5, 0)])
    base.Tables().do_turn(fake)
    assert ((5, 5), "e") in fake.orders


def test_bound_state_tracks_claims_and_moves() -> None:
    # A lone claimed ant leaves no bound supporters, and its own
    # explore step north is recorded as its live square.
    orders, bot = run_turn([(5, 5)], [(5, 8)], foods=[(5, 6)])
    assert orders == [((5, 5), "n")]
    assert bot._bound == set()
    assert bot._moved == {(5, 5): (4, 5)}


def _base_orders(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    # The staged Tables base on the same FakeAnts board: the
    # reference behavior bound support must match whenever no
    # claim pulls a pal away and no pal moved yet this turn.
    import importlib.util as _ilu

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Tables.py")
    spec = _ilu.spec_from_file_location("base_Tables_parity", path)
    assert spec is not None and spec.loader is not None
    base = _ilu.module_from_spec(spec)
    spec.loader.exec_module(base)
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    base.Tables().do_turn(fake)
    return fake.orders


def test_no_food_contact_matches_base() -> None:
    # A lone 1v1 with no hills and no claims: bound support
    # counts nothing either way, so both refuse east and
    # explore north identically. Bound support changes nothing
    # where no pal exists to (mis)count.
    mine = [(5, 5)]
    orders, _ = run_turn(mine, [(5, 8)])
    assert orders == _base_orders(mine, [(5, 8)]) == [((5, 5), "n")]


def test_no_food_guard_matches_base() -> None:
    # Contact-free guard board with no claims: bound support is
    # identical to stale counting, so every order matches.
    mine = [(10, 8), (10, 11)]
    enemies = [(10, 16)]
    orders, _ = run_turn(mine, enemies, my_hills=[(10, 10)])
    assert orders == _base_orders(mine, enemies, my_hills=[(10, 10)])


def test_held_pal_still_backs() -> None:
    # B at (5,4) is walled in by water on three sides with A
    # east, so it holds -- and a held claim-free pal stays to
    # fight: A reads the 2v1 WIN and steps east with its cover.
    water = {(4, 4), (5, 3), (6, 4)}
    mine = [(5, 4), (5, 5)]
    orders, bot = run_turn(mine, [(5, 8)], water=water)
    assert orders == [((5, 5), "e")]
    assert orders == _base_orders(mine, [(5, 8)], water=water)
    assert bot._moved == {(5, 5): (5, 6)}


def test_food_step_records_live_square() -> None:
    # The claimant test's B walks its claim west: the live
    # square is recorded, and A's explore step north too.
    orders, bot = run_turn([(5, 5), (5, 4)], [(5, 8)], foods=[(5, 3)])
    assert orders == [((5, 5), "n"), ((5, 4), "w")]
    assert bot._moved == {(5, 5): (4, 5), (5, 4): (5, 3)}


def test_setup_resets_bound_state() -> None:
    # Bound support is per-turn cache: a fresh setup empties the
    # bound set and the live-square map, even after a turn filled
    # both.
    _, bot = run_turn([(5, 5), (5, 4)], [(5, 8)], foods=[(5, 3)])
    assert bot._bound != set()
    assert bot._moved != {}
    bot.do_setup(FakeAnts([(5, 5)], []))
    assert bot._bound == set()
    assert bot._moved == {}
    assert bot.battle_table[(2, 1)] == TB.WIN


def test_guard_holds_despite_claimed_pal() -> None:
    # Razer at (10,11) threatens home (10,10). The guard at
    # (10,8) steps east onto (10,9): the only pal in range at
    # (10,7) walks a (10,5) food claim, so bound support reads
    # TRADE -- but the step sits 1 from home hill cover and goes
    # through anyway. Defense never depended on phantom backing.
    mine = [(10, 8), (10, 7)]
    enemies = [(10, 11)]
    orders, _ = run_turn(mine, enemies, foods=[(10, 5)], my_hills=[(10, 10)])
    assert orders == [((10, 8), "e"), ((10, 7), "w")]
    assert orders == _base_orders(mine, enemies, foods=[(10, 5)], my_hills=[(10, 10)])


def test_denial_claimants_stand_together() -> None:
    # Foods (5,5),(5,6) cluster with 3 foes in range: contested,
    # so B holds the (5,5) denial claim -- a combat mission, not
    # a harvest walk. Denial holders stand the field together:
    # B reads A's live square as backing, ours 2 vs 1 is WIN, and
    # steps east onto the food exactly like the base. Greedy harvest
    # claims still never count (see claimant test above).
    mine = [(5, 3), (5, 4)]
    foes = [(5, 7), (5, 9), (6, 9)]
    foods = [(5, 5), (5, 6)]
    orders, bot = run_turn(mine, foes, foods)
    assert orders == [((5, 3), "n"), ((5, 4), "e")]
    assert orders == _base_orders(mine, foes, foods)
    assert (5, 3) in bot._bound
    assert (5, 4) in bot._bound


def test_remembered_hills_prune_across_turns() -> None:
    # Hill memory and bound state span turns: a seen hill is
    # remembered, then forgotten once stood on, and the per-turn
    # bound cache never leaks from the previous turn.
    bot = TB.Tables7()
    bot.do_turn(FakeAnts([(10, 10)], [], enemy_hills=[(15, 15)]))
    assert (15, 15) in bot.remembered_hills
    assert bot._moved != {}
    bot.do_turn(FakeAnts([(15, 15)], []))
    assert (15, 15) not in bot.remembered_hills
    assert len(bot._moved) == 1


def test_hot_denial_with_hills_matches_base() -> None:
    # Contested cluster under home-hill cover: denial holders
    # stand, hill cover gates the trades, and every order matches
    # the base. Bound support changes nothing in hot zones.
    mine = [(5, 3), (5, 4)]
    foes = [(5, 7), (5, 9), (6, 9)]
    foods = [(5, 5), (5, 6)]
    orders, _ = run_turn(mine, foes, foods, my_hills=[(5, 0)])
    assert orders == _base_orders(mine, foes, foods, my_hills=[(5, 0)])
    assert orders == [((5, 3), "w"), ((5, 4), "e")]


def test_denial_live_square_backs() -> None:
    # Both rules together: B walks its (5,4) denial claim east
    # (3 foes contest the food, so the claim is combat-bound),
    # and A at (5,5) eyes the (5,6) contact against (5,8). B's
    # stale (5,3) sits out of range but its live (5,4) covers:
    # ours 2 vs 1 is WIN, so A steps east with it. Stale
    # counting -- and greedy-claim counting -- refuse north.
    mine = [(5, 3), (5, 5)]
    foes = [(5, 8), (5, 11), (7, 9)]
    foods = [(5, 4)]
    orders, bot = run_turn(mine, foes, foods)
    assert orders == [((5, 3), "e"), ((5, 5), "e")]
    assert (5, 3) in bot._bound
    assert _base_orders(mine, foes, foods) == [((5, 3), "e"), ((5, 5), "n")]


def test_seeded_boards_stay_legal_and_fast() -> None:
    # Fixed-seed sweep over small crowded boards: every turn
    # issues distinct passable destinations and finishes far
    # inside the turn budget. Deterministic: same seed, same
    # boards, every run.
    import random as _random

    rng = _random.Random(20261008)
    start = time.perf_counter()
    for _ in range(25):
        rows = rng.randint(8, 16)
        cols = rng.randint(8, 16)
        cells = [(r, c) for r in range(rows) for c in range(cols)]
        rng.shuffle(cells)
        mine = cells[:6]
        foes = cells[6:10]
        foods = cells[10:15]
        water = set(rng.sample(cells, rng.randint(0, 6)))
        mine = [m for m in mine if m not in water]
        foes = [f for f in foes if f not in water]
        if not mine:
            continue
        fake = FakeAnts(mine, foes, foods, water)
        fake.rows, fake.cols = rows, cols
        TB.Tables7().do_turn(fake)
        dests = [fake.destination(a, d) for a, d in fake.orders]
        assert len(set(dests)) == len(dests)
        assert all(d not in water for d in dests)
    assert time.perf_counter() - start < 2.0


def test_precomputed_denial_groups_match_fresh_scan() -> None:
    # Single-scan turn economy: passing the caller's denial groups
    # assigns byte-identical targets to a fresh scan, so sharing
    # one bucketed scan never changes food claims or bound support.
    mine = [(5, 3), (5, 4)]
    foes = [(5, 7), (5, 9), (6, 9)]
    foods = [(5, 5), (5, 6)]
    probe = FakeAnts(mine, foes, foods)
    groups = TB.denied_food_groups(foods, foes, probe.distance, ROWS, COLS)
    fresh = TB.assign_food_targets(mine, foods, foes, probe.distance, ROWS, COLS)
    shared = TB.assign_food_targets(
        mine, foods, foes, probe.distance, ROWS, COLS, denial_groups=groups
    )
    assert shared == fresh
    assert set(shared.values()) <= set(foods)
    orders, bot = run_turn(mine, foes, foods)
    assert orders == [((5, 3), "n"), ((5, 4), "e")]
    assert (5, 3) in bot._bound
    assert (5, 4) in bot._bound
