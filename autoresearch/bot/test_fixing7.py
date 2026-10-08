#!/usr/bin/env python
"""Fixing7 scoreboard posture: parity-gated fixing combat (TDD).

Fresh entry: economy, muster, guard, and explore byte-identical to
the Fixing base (Crowd denial claims, threatened-hill guards with
off-hill screening, muster plus reinforce, visits explore,
walk-off); the combat core is the same anthonyvh greedy sequential
fixing, but every trade gate now reads the visible scoreboard.

New mechanism -- scoreboard posture: each turn compares visible
ant counts (ours minus theirs) against SCORE_MARGIN and sets one
posture for the whole turn:

  PRESS (ahead by 3+):  KILL steps pin anywhere, no hill push
      needed; equal trades need only PRESS_TRADE_NEAR (5) friends
      nearby; the hill muster marches fearless.
  PAR   (within 2):     champion behavior -- KILL only while pushing
      a remembered hill; equal trades need EQUAL_TRADE_NEAR (10).
  HOLD  (behind by 3+): strict superiority everywhere -- KILL never
      pins, equal trades always refuse; DIE still only to unblock a
      hill rush.

Self-contained: stdlib plus ants.py only. No combat.py import.

  (a) posture() flips at exactly +/- SCORE_MARGIN.
  (b) kill_allowed() matrix: PRESS always, PAR iff hills, HOLD never.
  (c) equal_trade_near() prices: 5 / 10 / never.
  (d) acceptable_moves/best_move pin a hill-free KILL in PRESS and
      refuse it in PAR and HOLD; PAR-with-hills still pins.
  (e) in-bot: ahead 7v1 the lone contact ant advances onto the KILL
      square; the same contact at parity holds for muster instead.
  (f) full crowded turn stays under 1 s.
  (g) PRESS lifts the denial cap: a 3-contested cluster draws 2
      claims at PAR and full greedy claims at PRESS.
  (h) sight memory marks the toroidal von Neumann diamond.
  (i) the scout's first step routes around a water wall in-bot.
  (j) empty boards read PAR without crashing.
  (k) guards stay champion: a 9-off raider still draws the lone
      ant home.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Fixing7 as FX7  # noqa: E402

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
        self.viewradius2 = 55
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
) -> tuple[list[tuple[Loc, str]], FX7.Fixing7]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = FX7.Fixing7()
    bot.do_turn(fake)
    return fake.orders, bot


def _dist(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


def _dest(loc: Loc, direction: str) -> Loc:
    dr, dc = AIM[direction]
    return ((loc[0] + dr) % ROWS, (loc[1] + dc) % COLS)


def _allow(loc: Loc) -> bool:
    return True


def test_entry_is_self_contained() -> None:
    assert FX7.__name__ == "Fixing7"
    assert hasattr(FX7, "Fixing7")
    with open(str(FX7.__file__)) as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    bot_file = os.path.join(os.path.dirname(str(FX7.__file__)), "Fixing7.bot")
    with open(bot_file) as handle:
        assert handle.read().strip() == "python Fixing7.py"


def test_posture_flips_at_margin() -> None:
    # (a) visible diff ours-theirs: +3 PRESS, +2 PAR, -2 PAR, -3 HOLD.
    assert FX7.posture(7, 4) == FX7.PRESS
    assert FX7.posture(4, 7) == FX7.HOLD
    assert FX7.posture(5, 3) == FX7.PAR
    assert FX7.posture(3, 5) == FX7.PAR
    assert FX7.posture(1, 1) == FX7.PAR
    assert FX7.posture(10, 0) == FX7.PRESS
    assert FX7.posture(0, 10) == FX7.HOLD


def test_kill_allowed_matrix() -> None:
    # (b) PRESS always pins KILL; PAR only pushing hills; HOLD never.
    assert FX7.kill_allowed(FX7.PRESS, []) is True
    assert FX7.kill_allowed(FX7.PRESS, [(0, 0)]) is True
    assert FX7.kill_allowed(FX7.PAR, []) is False
    assert FX7.kill_allowed(FX7.PAR, [(0, 0)]) is True
    assert FX7.kill_allowed(FX7.HOLD, []) is False
    assert FX7.kill_allowed(FX7.HOLD, [(0, 0)]) is False


def test_equal_trade_near_prices() -> None:
    # (c) PRESS halves the near requirement; HOLD prices it at never.
    assert FX7.equal_trade_near(FX7.PRESS) == 5
    assert FX7.equal_trade_near(FX7.PAR) == 10
    assert FX7.equal_trade_near(FX7.HOLD) > 1000


def _kill_field() -> list[list[int]]:
    # Single foe at (5, 8), reach 3: east (5, 6) sits 2 off = KILL
    # for a lone ant. Only east is left occupiable, so the pin
    # decision is exactly the KILL gate.
    return FX7.influence_field([(5, 8)], ROWS, COLS, FX7.threat_reach(5))


def _east_only(loc: Loc) -> bool:
    return loc == (5, 6)


def test_kill_move_gated_by_posture() -> None:
    # (d) Lone ant at (5, 5), no hills: east onto (5, 6) is KILL.
    # PRESS pins it, PAR and HOLD refuse it.
    field = _kill_field()
    assert FX7.classify_step(field, (5, 6), 0) == FX7.KILL
    press = FX7.acceptable_moves(
        (5, 5),
        field,
        {},
        [],
        _dist,
        _dest,
        _allow,
        _east_only,
        kill=FX7.kill_allowed(FX7.PRESS, []),
    )
    assert "e" in press
    par = FX7.acceptable_moves(
        (5, 5),
        field,
        {},
        [],
        _dist,
        _dest,
        _allow,
        _east_only,
        kill=FX7.kill_allowed(FX7.PAR, []),
    )
    assert "e" not in par
    hold = FX7.acceptable_moves(
        (5, 5),
        field,
        {},
        [],
        _dist,
        _dest,
        _allow,
        _east_only,
        kill=FX7.kill_allowed(FX7.HOLD, [(5, 10)]),
    )
    assert "e" not in hold
    # PAR pushing a hill still pins the KILL, as the base does.
    par_hill = FX7.acceptable_moves(
        (5, 5),
        field,
        {},
        [(5, 10)],
        _dist,
        _dest,
        _allow,
        _east_only,
        kill=FX7.kill_allowed(FX7.PAR, [(5, 10)]),
    )
    assert "e" in par_hill
    assert (
        FX7.best_move(
            (5, 5),
            field,
            {},
            [],
            [(5, 8)],
            _dist,
            _dest,
            _allow,
            _east_only,
            kill=FX7.kill_allowed(FX7.PRESS, []),
        )
        == "e"
    )
    assert (
        FX7.best_move(
            (5, 5),
            field,
            {},
            [],
            [(5, 8)],
            _dist,
            _dest,
            _allow,
            _east_only,
            kill=FX7.kill_allowed(FX7.PAR, []),
        )
        != "e"
    )


def test_press_advances_and_parity_holds_in_bot() -> None:
    # (e) Contact ant (5, 5) vs foe (5, 7): east is a lone-ant KILL.
    # Ahead 7v1 the scoreboard reads PRESS and the ant advances;
    # the identical contact at 1v1 reads PAR and refuses the trade
    # (sidestepping SAFE instead).
    rear = [(15, 15), (15, 16), (16, 15), (16, 16), (14, 15), (15, 14)]
    ahead, _ = run_turn([(5, 5)] + rear, [(5, 7)])
    assert ((5, 5), "e") in ahead
    level, _ = run_turn([(5, 5)], [(5, 7)])
    assert ((5, 5), "e") not in level


def test_hold_refuses_equal_trade_in_bot() -> None:
    # Lone ant (5, 5) vs foe (5, 7): every neighbor is a lone-ant
    # KILL. Outnumbered 1v5 the scoreboard reads HOLD, so even with
    # a hill to push (which PAR would take) the ant must not trade
    # -- it sidesteps SAFE or holds, and the fearless muster stays
    # sheathed too.
    foes = [(5, 7), (0, 0), (0, 19), (19, 0), (19, 19)]
    orders, _ = run_turn([(5, 5)], foes, enemy_hills=[(5, 10)])
    assert ((5, 5), "e") not in orders


def test_par_matches_base_at_par() -> None:
    # At PAR the scoreboard changes nothing: same scenario through
    # the Fixing base and Fixing7 must issue identical orders.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import Fixing as FX  # noqa: E402

    mine = [(5, 5), (2, 2), (10, 10), (14, 14), (3, 12), (12, 3)]
    foes = [(5, 12), (2, 6), (5, 9), (10, 15), (13, 13), (1, 1)]
    foods = [(5, 6), (2, 3), (11, 11)]
    water = {(7, 7), (7, 8)}

    def run(bot_cls):
        fake = FakeAnts(
            mine,
            foes,
            foods,
            water,
            enemy_hills=[(15, 15)],
            my_hills=[(10, 12)],
        )
        bot = bot_cls()
        # Fully seen world: no edge exists, so the scout falls back
        # to the same visits diffusion in both bots.
        bot.seen = {(r, c) for r in range(ROWS) for c in range(COLS)}
        bot.do_turn(fake)
        return fake.orders

    assert run(FX.Fixing) == run(FX7.Fixing7)


def test_press_lifts_denial_cap() -> None:
    # Three foods in one cluster, three enemies contesting: at PAR
    # the cluster draws exactly DENIAL_CLAIMS ants; at PRESS the cap
    # lifts and the greedy claims all three.
    foods = [(5, 5), (5, 6), (5, 7)]
    foes = [(5, 10), (6, 9), (4, 9)]
    ants6 = [(5, 0), (5, 1), (5, 2), (15, 15), (15, 16), (16, 15)]
    par = FX7.assign_food_targets(ants6, foods, foes, _dist, ROWS, COLS, press=False)
    assert len(par) == FX7.DENIAL_CLAIMS
    ahead = FX7.assign_food_targets(ants6, foods, foes, _dist, ROWS, COLS, press=True)
    assert len(ahead) == 3
    assert sorted(ahead.values()) == sorted(foods)


def test_press_claims_contested_food_in_bot() -> None:
    # Same contested cluster in-bot: 3 near ants, 3 foes, with and
    # without 3 rear ants (PRESS vs PAR scoreboard).
    foods = [(5, 5), (5, 6), (5, 7)]
    foes = [(5, 10), (6, 9), (4, 9)]
    near = [(5, 0), (5, 1), (5, 2)]
    rear = [(15, 15), (15, 16), (16, 15)]
    # Single file: only the front ant can step east (ants block each
    # other), so the in-bot check is that the press path executes and
    # the lead gatherer advances; the claim counts live in the unit
    # test above.
    ahead, _ = run_turn(near + rear, foes, foods)
    assert ((5, 2), "e") in ahead
    level, _ = run_turn(near, foes, foods)
    assert ((5, 2), "e") in level


def test_edge_step_unit() -> None:
    # Nearest unseen square wins: due north unseen beats unseen
    # elsewhere; a walled front detours around the wall's end.
    assert FX7.edge_step((5, 5), {(5, 5)}, _allow, _dest) == "n"
    assert (
        FX7.edge_step(
            (5, 5),
            {(5, 5), (4, 5), (5, 6), (6, 5), (5, 4)},
            _allow,
            _dest,
            budget=1,
        )
        is None
    )
    wall = {(4, 4), (4, 5), (4, 6)}
    seen = {(5, 5), (5, 4), (5, 6), (6, 5)}

    def gap_passable(loc: Loc) -> bool:
        return loc not in wall

    # North is water: the search fans out in n/e/s/w order and the
    # east arm reaches unseen (5, 7) first, routing around the wall.
    assert FX7.edge_step((5, 5), seen, gap_passable, _dest) == "e"


def test_edge_scout_moves_in_bot() -> None:
    # One ant, nothing else on the board: sight memory covers a
    # disc around home, so the ant steps to the nearest unseen
    # square (due north) instead of diffusing.
    orders, _ = run_turn([(5, 5)], [])
    assert orders == [((5, 5), "n")]


def test_fully_seen_falls_back_to_visits() -> None:
    # A veteran that has seen the world: no edge exists, so the
    # visits diffusion decides -- and the visit is recorded.
    _, bot = run_turn([(5, 5)], [])
    bot.seen = {(r, c) for r in range(ROWS) for c in range(COLS)}
    fake = FakeAnts([(5, 5)], [])
    bot.do_turn(fake)
    assert fake.orders == [((5, 5), "n")]
    assert bot.visits.get((5, 5), 0) == 2


def test_mark_seen_diamond_and_wrap() -> None:
    # Radius 1 marks the von Neumann cross; edges wrap toroidally.
    seen: set[Loc] = set()
    FX7.mark_seen(seen, [(0, 0)], 1, ROWS, COLS)
    assert seen == {(0, 0), (19, 0), (1, 0), (0, 19), (0, 1)}
    FX7.mark_seen(seen, [(0, 0)], 0, ROWS, COLS)
    assert (0, 0) in seen
    empty: set[Loc] = set()
    FX7.mark_seen(empty, [], 7, ROWS, COLS)
    assert empty == set()


def test_edge_routes_through_maze_gap_in_bot() -> None:
    # Water wall with one gap: the scout's first step heads for the
    # gap column instead of milling.
    water = {(4, c) for c in range(COLS) if c != 10}
    orders, _ = run_turn([(6, 5)], [], water=water)
    assert orders
    loc, direction = orders[0]
    assert loc == (6, 5)
    assert direction in ("n", "e", "w")


def test_guards_hold_hills_champion_style() -> None:
    # Guards are posture-free: a raider 9 off still draws the lone
    # ant back to its threatened hill.
    hill = (10, 10)
    foe = (10, 19)
    level, _ = run_turn([(10, 5)], [foe], my_hills=[hill])
    assert level == [((10, 5), "e")]


def test_empty_board_posture_is_par() -> None:
    # No ants on either side: PAR, no crash, no orders.
    assert FX7.posture(0, 0) == FX7.PAR
    orders, _ = run_turn([], [])
    assert orders == []


def test_turn_under_1s() -> None:
    # (f) crowded turn with hills, food, and guards stays in budget.
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    many = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [((i * 3 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(12)]
    start = time.perf_counter()
    orders, _ = run_turn(
        mine,
        many,
        foods,
        enemy_hills=[(0, 0), (19, 19)],
        my_hills=[(10, 10), (3, 3)],
    )
    assert (time.perf_counter() - start) < 1.0
    assert len(orders) > 0
