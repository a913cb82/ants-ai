#!/usr/bin/env python
"""Profitable-attrition trade gate (Tables5 entry).

One idea past the Tables2 base: the mutual-engagement support
count is UNCHANGED (a pal counts iff it is within attack range of
the destination AND of a counted foe -- no join-aware relaxation,
no threshold variants), but the open-field TRADE gate is relaxed
by a numbers lead. A mutual 1-for-1 away from home-hill cover is
profitable attrition only when the side can afford it: stepping
into a TRADE outside hill cover is allowed iff own visible ants
strictly outnumber visible enemies. Even or behind: the base
refusal stands. LOSE verdicts always refuse. Self-contained:
stdlib plus ants.py only, never combat.py.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Tables5 as TB  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], TB.Tables5]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = TB.Tables5()
    bot.do_turn(fake)
    return fake.orders, bot


def _sq(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


def _verdict_bot(mine: list[Loc], enemies: list[Loc]) -> TB.Tables5:
    # contact_verdict reads cached turn state; prime it directly so
    # verdict tests stay deterministic with no BFS involved.
    bot = TB.Tables5()
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


def test_table_grid_untouched() -> None:
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


def test_counting_still_base_mutual_only() -> None:
    # The support count is exactly the Tables2 base: backer (5, 4)
    # is in range of the destination (5, 6) but out of range of
    # the foe (5, 8), so it stays phantom and the verdict stays
    # TRADE -- no join-aware relaxation. The engine agrees: the
    # stepping mover dies with the foe.
    assert _sq((5, 4), (5, 6)) <= 5
    assert _sq((5, 4), (5, 8)) > 5
    dead_o, dead_t = focus_deaths([(5, 6), (5, 4)], [(5, 8)])
    assert dead_o == {(5, 6)}
    assert dead_t == {(5, 8)}
    bot = _verdict_bot([(5, 5), (5, 4)], [(5, 8)])
    assert bot.contact_verdict((5, 6), (5, 5)) == TB.TRADE


def test_mutual_2v1_stays_win() -> None:
    # Covered shape: backer (4, 7) is inside attack range of both
    # the destination (5, 6) and the foe (5, 8) -- real support,
    # verdict WIN.
    assert _sq((4, 7), (5, 6)) <= 5
    assert _sq((4, 7), (5, 8)) <= 5
    bot = _verdict_bot([(5, 5), (4, 7)], [(5, 8)])
    assert bot.contact_verdict((5, 6), (5, 5)) == TB.WIN


# Open-field duel boards: ant (5, 5) eyes the step east onto (5, 6)
# against one foe at (5, 8) (squared distance 4, in contact) -- a
# friendless mutual-death trade with no hills held at all.
_DUEL_MINE = [(5, 5)]
_DUEL_FOE = [(5, 8)]
_FAR_HILL = [(15, 15)]


def test_scenario_even_numbers_refuses_open_trade() -> None:
    # Benchmark control (base behavior kept): a lone 1v1 in the
    # open field with no numbers lead -- the trade refuses east
    # and the ant explores north instead.
    orders, _ = run_turn(_DUEL_MINE, _DUEL_FOE)
    assert orders == [((5, 5), "n")]
    assert ((5, 5), "e") not in orders


def test_scenario_ahead_numbers_takes_open_trade() -> None:
    # Benchmark discriminator: the identical duel, but two far-off
    # nestmates (0, 0) and (0, 10) hold a 3v1 numbers lead with no
    # hills anywhere. Base refuses this mutual trade; tuned spends
    # it: the duelist steps east.
    mine = [(5, 5), (0, 0), (0, 10)]
    orders, _ = run_turn(mine, _DUEL_FOE)
    assert orders[0] == ((5, 5), "e")


def test_scenario_behind_numbers_refuses_open_trade() -> None:
    # Behind globally: 1 own ant facing 2 foes where only (5, 8)
    # engages the destination (6, 7)... second foe (15, 15) is far
    # off, so the local verdict is TRADE but the side is behind
    # 1v2 -- the trade still refuses east.
    foes = [(5, 8), (15, 15)]
    probe = FakeAnts([(5, 5)], foes)
    assert _sq((5, 6), (5, 8)) <= 5
    assert _sq((5, 6), (15, 15)) > 5
    assert probe.distance((5, 6), _FAR_HILL[0]) > 14
    bot = _verdict_bot([(5, 5)], foes)
    assert bot.contact_verdict((5, 6), (5, 5)) == TB.TRADE
    orders, _ = run_turn([(5, 5)], foes)
    assert ((5, 5), "e") not in orders
    assert orders == [((5, 5), "n")]


def test_scenario_lose_refuses_even_when_ahead() -> None:
    # The idea is trade-only, not blanket aggression: ours 1 vs 2
    # locally (dest (5, 6) in range of both foes) is LOSE, and it
    # refuses east even holding a 3v2 global lead.
    foes = [(5, 8), (6, 7)]
    assert _sq((5, 6), (5, 8)) <= 5
    assert _sq((5, 6), (6, 7)) <= 5
    bot = _verdict_bot([(5, 5), (0, 0), (0, 10)], foes)
    assert bot.contact_verdict((5, 6), (5, 5)) == TB.LOSE
    orders, _ = run_turn([(5, 5), (0, 0), (0, 10)], foes)
    assert ((5, 5), "e") not in orders


def test_hill_gate_preserved_without_lead() -> None:
    # Base hill cover needs no numbers lead: the friendless duel
    # within radius 14 of a held home hill still goes east even at
    # 1v1 globally.
    hill = [(12, 0)]
    probe = FakeAnts(_DUEL_MINE, _DUEL_FOE)
    assert probe.distance((5, 6), hill[0]) == 13
    assert probe.distance(hill[0], _DUEL_FOE[0]) > 10
    orders, _ = run_turn(_DUEL_MINE, _DUEL_FOE, my_hills=hill)
    assert orders[0] == ((5, 5), "e")


def test_backed_2v1_advances_without_hills_or_lead() -> None:
    # Table WIN needs neither hill cover nor a numbers lead: real
    # 2v1 backing steps east at 2v1 globally.
    orders, _ = run_turn([(5, 5), (4, 7)], _DUEL_FOE)
    assert orders[0] == ((5, 5), "e")


def test_per_decision_still_fast() -> None:
    # One contact decision stays far under 0.1ms: the gate adds
    # two cached list lengths, no search.
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
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Tables5.py")
    with open(path) as fh:
        source = fh.read()
    assert "weakness" not in source
    assert "import combat" not in source
    assert "from combat" not in source
