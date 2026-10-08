#!/usr/bin/env python
"""Greedy14 pin-and-swarm tests.

Greedy14's new mechanism is top-down victim pinning: each turn the
bot pins ONE enemy -- the foe with the best free-hunter margin
inside SUPPORT_R -- and claim-free hunters within HUNT_RANGE
converge on it. Committed backup lets pinned hunters accept equal
trades; outnumbered steps are never taken. This differs from
bottom-up commitment joining (Swarm/Wolfpack: ants chase their own
nearest foe, join when 2+ share) and from Greedy13's
centroid-wedge (seekers bias toward the seeker centroid).

Proves, on fixed boards before the bot code lands:
(a) pin selection: none without edge, best margin wins, sticky
    pins hold winnable victims across turns, deterministic,
(b) step gates: pinned hunters may trade equal, never outnumbered;
    unpinned ants refuse far equal trades, accept hill-zone ones
    and grinder 1v1s only while the visible army leads; surrounds
    hold winnable fights and release lost ones,
(c) integration: converge-hold-resume kill chain, guards answer
    and screen, draft cap protects gatherers, muster marches
    (fearless when ahead) and falls back through reinforce to
    explore, rally packs up near foes, endgame sits and contests
    only winnable hills, denial holds two claims (one on single
    food), water gaps route, combined arms compose,
(d) engine protocol roundtrip, 40-seed fuzz legality +
    determinism, crowded/large/maze turns < 1s.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Greedy14 as G  # noqa: E402

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

    def visible(self, loc: Loc) -> bool:
        return True

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
    turn: int = 0,
) -> tuple[list[tuple[Loc, str]], G.Greedy14]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = G.Greedy14()
    bot.turn = turn
    bot.do_turn(fake)
    return fake.orders, bot


def dist(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


# (a) pin selection ----------------------------------------------------------


def test_pin_none_without_enemies() -> None:
    assert G.pin_victim([(5, 5), (5, 6)], [], dist) is None


def test_pin_needs_two_hunters() -> None:
    # Lone hunter on a lone foe is a 1v1 donation: no pin.
    assert G.pin_victim([(5, 5)], [(5, 7)], dist) is None


def test_pin_needs_local_edge() -> None:
    # Two hunters facing three packed foes is a lost crowd: no pin.
    hunters = [(5, 5), (5, 6)]
    foes = [(5, 8), (5, 9), (6, 8)]
    assert G.pin_victim(hunters, foes, dist) is None


def test_pin_picks_best_margin() -> None:
    # Lone hunters far away do not count: the near foe pins on
    # margin 2, and the richer pack wins the second board.
    hunters = [(5, 5), (5, 6), (6, 5)]
    assert G.pin_victim(hunters, [(5, 8), (15, 15)], dist) == (5, 8)
    hunters_b = [(15, 14), (15, 16), (14, 15)]
    foes = [(5, 8), (15, 15)]
    hunters_all = [(5, 5), (5, 6)] + hunters_b
    assert G.pin_victim(hunters_all, foes, dist) == (15, 15)


def test_pin_tie_break_is_deterministic() -> None:
    # Tied 2v1 margins on both foes: sorted-first foe pins, every time.
    hunters = [(5, 3), (5, 4), (15, 13), (15, 14)]
    foes = [(5, 5), (15, 15)]
    first = G.pin_victim(hunters, foes, dist)
    assert first == (5, 5)
    assert first == G.pin_victim(hunters, list(reversed(foes)), dist)


def test_sticky_pin_holds_a_winnable_victim() -> None:
    # B has the better margin, but the sticky pin A is still
    # winnable: hunters finish the kill instead of thrashing.
    hunters = [(5, 3), (5, 4), (15, 13), (15, 14)]
    foes = [(5, 5), (15, 15)]
    assert G.pin_victim(hunters, foes, dist) == (5, 5)
    assert G.pin_victim(hunters, foes, dist, sticky=(15, 15)) == (15, 15)


def test_sticky_pin_releases_a_lost_victim() -> None:
    # A sticky pin that is no longer winnable (or gone) releases to
    # the best margin.
    hunters = [(5, 3), (5, 4), (15, 13), (15, 14)]
    foes = [(5, 5), (15, 15)]
    assert G.pin_victim(hunters, foes, dist, sticky=(0, 0)) == (5, 5)
    assert G.pin_victim(hunters, foes, dist, sticky=(5, 5)) == (5, 5)
    crowded = [(5, 5), (5, 6), (5, 4), (15, 15)]
    assert G.pin_victim(hunters, crowded, dist, sticky=(5, 5)) == (15, 15)


def test_pin_holds_across_turns() -> None:
    # Tied victims pin sorted-first; next turn a better margin
    # elsewhere does not steal the sticky pin.
    bot = G.Greedy14()
    fake1 = FakeAnts([(5, 3), (5, 4), (15, 13), (15, 14)], [(5, 5), (15, 15)])
    bot.do_turn(fake1)
    assert bot.pin == (5, 5)
    fake2 = FakeAnts([(5, 3), (5, 4), (15, 13), (15, 14), (15, 12)], [(5, 5), (15, 15)])
    bot.do_turn(fake2)
    assert bot.pin == (5, 5)


def test_pin_ignores_distant_hunters() -> None:
    # Only hunters inside SUPPORT_R count: one near hunter is no pin.
    assert G.pin_victim([(0, 0)], [(5, 7)], dist) is None


# (b) step gates --------------------------------------------------------------


def test_pinned_hunter_may_trade_equal() -> None:
    assert G.pin_trade_safe(friends=0, enemies=1, pinned=True) is True


def test_pinned_hunter_never_steps_outnumbered() -> None:
    assert G.pin_trade_safe(friends=0, enemies=2, pinned=True) is False
    assert G.pin_trade_safe(friends=1, enemies=3, pinned=True) is False


def test_pinned_hunter_takes_free_and_winning_steps() -> None:
    assert G.pin_trade_safe(friends=0, enemies=0, pinned=True) is True
    assert G.pin_trade_safe(friends=1, enemies=1, pinned=True) is True


def test_unpinned_refuses_equal_far_from_objectives() -> None:
    assert G.trade_safe(0, 1, hill_dist=50, backup_dist=1) is False


def test_grinder_releases_ahead_duels_only() -> None:
    # Friendless 1v1 contact: released when the visible army leads,
    # refused when even or behind. Other shapes are untouched.
    assert G.grinder_release(0, 1, 4, 1) is True
    assert G.grinder_release(0, 1, 1, 1) is False
    assert G.grinder_release(0, 1, 1, 4) is False
    assert G.grinder_release(1, 1, 4, 1) is False
    assert G.grinder_release(0, 2, 4, 1) is False
    assert G.grinder_release(0, 0, 4, 1) is False


def test_ahead_lone_ant_takes_the_duel() -> None:
    # 4v1 visible army: the lone ant steps to its food through the
    # contact square instead of routing around.
    orders, _ = run_turn([(5, 5), (0, 0), (0, 1), (0, 2)], [(5, 7)], [(5, 6)])
    by_ant = dict(orders)
    assert by_ant.get((5, 5)) == "e"


def test_behind_lone_ant_refuses_the_duel() -> None:
    # 1v1 armies: no step into contact with the lone foe.
    orders, _ = run_turn([(5, 5)], [(5, 7)])
    probe = FakeAnts([(5, 5)], [(5, 7)])
    for loc, direction in orders:
        dest = probe.destination(loc, direction)
        dr = abs(dest[0] - 5)
        dc = abs(dest[1] - 7)
        assert dr * dr + dc * dc > probe.attackradius2


def test_unpinned_accepts_equal_in_hill_zone_with_backup() -> None:
    assert G.trade_safe(0, 1, hill_dist=3, backup_dist=2) is True


def test_unpinned_gate_strict_wins_and_losses() -> None:
    assert G.trade_safe(0, 0, hill_dist=None, backup_dist=None) is True
    assert G.trade_safe(1, 1, hill_dist=None, backup_dist=None) is True
    assert G.trade_safe(1, 2, hill_dist=None, backup_dist=None) is False
    assert G.trade_safe(2, 1, hill_dist=None, backup_dist=None) is True
    assert G.trade_safe(0, 2, hill_dist=None, backup_dist=None) is False


# (c) integration -------------------------------------------------------------


def test_pack_converges_on_pinned_victim() -> None:
    # Two free ants outside attack range of a lone foe: both step
    # closer to the foe instead of wandering.
    orders, _ = run_turn([(5, 3), (5, 11)], [(5, 7)])
    assert len(orders) == 2
    probe = FakeAnts([(5, 3), (5, 11)], [(5, 7)])
    for loc, direction in orders:
        before = probe.distance(loc, (5, 7))
        after = probe.distance(probe.destination(loc, direction), (5, 7))
        assert after < before


def test_hunters_hold_the_surround() -> None:
    # Hunters already flanking the victim hold the kill instead of
    # wandering: no orders, no drift.
    orders, _ = run_turn([(5, 6), (5, 8)], [(5, 7)])
    assert orders == []


def test_surround_holds_only_winnable_fights() -> None:
    # The surround holds on equality (committed backup) but releases
    # when locally outnumbered.
    assert G.surround_holds(friends=0, enemies=1) is True
    assert G.surround_holds(friends=0, enemies=2) is False
    assert G.surround_holds(friends=1, enemies=1) is True


def test_kill_chain_converge_hold_resume() -> None:
    # Full arc across turns: far hunters converge, adjacent hunters
    # hold the surround, and once the victim is gone the economy
    # resumes on open food.
    probe = FakeAnts([(5, 3), (5, 11)], [(5, 7)])
    orders, _ = run_turn([(5, 3), (5, 11)], [(5, 7)])
    assert len(orders) == 2
    moved = [probe.destination(loc, d) for loc, d in orders]
    assert all(probe.distance(m, (5, 7)) < 4 for m in moved)
    orders, _ = run_turn(moved, [(5, 7)])
    assert len(orders) == 2
    closed = [probe.destination(loc, d) for loc, d in orders]
    orders, _ = run_turn(closed, [(5, 7)])
    assert orders == []
    orders, _ = run_turn(closed, [], foods=[(0, 0)])
    assert orders
    assert any(
        probe.distance(probe.destination(loc, d), (0, 0)) < probe.distance(loc, (0, 0))
        for loc, d in orders
    )


def test_lone_ant_does_not_suicide() -> None:
    # One ant against two packed foes: no pin, and no step into
    # contact with either foe.
    orders, _ = run_turn([(5, 5)], [(5, 7), (5, 8)])
    probe = FakeAnts([(5, 5)], [(5, 7), (5, 8)])
    for loc, direction in orders:
        dest = probe.destination(loc, direction)
        for foe in ((5, 7), (5, 8)):
            dr = abs(dest[0] - foe[0])
            dc = abs(dest[1] - foe[1])
            assert dr * dr + dc * dc > probe.attackradius2


def test_food_claim_steps_to_nearest_food() -> None:
    orders, _ = run_turn([(0, 0), (0, 19)], [], [(0, 1), (0, 18)])
    assert orders == [((0, 0), "e"), ((0, 19), "w")]


def test_guard_answers_threatened_hill() -> None:
    # Water blocks the explore-north drift, so only the guard's
    # routed march steps west toward the hill.
    water = {(4, 5)}
    probe = FakeAnts([(5, 5)], [(2, 8)], water=water, my_hills=[(2, 2)])
    assert probe.distance((2, 2), (2, 8)) <= 10
    orders, _ = run_turn([(5, 5)], [(2, 8)], water=water, my_hills=[(2, 2)])
    assert orders == [((5, 5), "w")]


def test_muster_marches_remembered_hill() -> None:
    # Two remembered hills: the ant marches the nearer one east.
    # Plain explore would drift north, so the exact step proves the
    # muster branch fired.
    orders, bot = run_turn([(0, 0)], [], enemy_hills=[(10, 10), (0, 5)])
    assert (10, 10) in bot.remembered_hills
    assert (0, 5) in bot.remembered_hills
    assert orders == [((0, 0), "e")]


def test_superior_hunters_take_the_hill() -> None:
    # Past turn 600 with a far superior theater, the pinned hunters
    # step onto the uncontrolled hill itself (razing it) instead of
    # milling around it.
    orders, _ = run_turn(
        [(0, 0), (10, 9), (10, 11)],
        [(10, 12)],
        enemy_hills=[(10, 10)],
        my_hills=[(0, 0)],
        turn=600,
    )
    assert orders
    probe = FakeAnts([(0, 0), (10, 9), (10, 11)], [(10, 12)])
    assert any(
        probe.distance(probe.destination(loc, d), (10, 10))
        < probe.distance(loc, (10, 10))
        for loc, d in orders
    )


def test_theater_gate_refuses_lost_hill() -> None:
    # Pure gate: a packed garrison refuses the challenge, a lone
    # sentry allows it.
    foes = [(10, 10), (10, 9), (10, 11), (9, 10), (11, 10)]
    assert G.theater_allows((10, 10), [(5, 5)], foes, ROWS, COLS) is False
    assert G.theater_allows((10, 10), [(10, 9)], [(10, 12)], ROWS, COLS) is True


def test_sit_march_never_donates() -> None:
    # Past turn 600 with no remembered hills: the ant sits home via
    # the routed march, and no issued step lands in contact while
    # outnumbered. Water blocks the explore-north drift, so only
    # the sit march picks the west/south detour.
    foes = [(10, 10), (10, 9), (10, 11), (9, 10), (11, 10)]
    water = {(9, 5)}
    orders, _ = run_turn([(10, 5)], foes, water=water, my_hills=[(3, 3)], turn=600)
    probe = FakeAnts([(10, 5)], foes, water=water)
    assert len(orders) == 1
    (loc, direction) = orders[0]
    assert probe.destination(loc, direction) in ((10, 4), (11, 5))
    for loc, d in orders:
        dest = probe.destination(loc, d)
        contact = sum(
            1
            for f in foes
            if (dest[0] - f[0]) ** 2 + (dest[1] - f[1]) ** 2 <= probe.attackradius2
        )
        assert contact == 0


def test_denial_holds_two_claims_on_contested_cluster() -> None:
    # Three enemies contest a food cluster: exactly two ants claim
    # cluster foods, the rest stay free.
    foods = [(5, 5), (5, 6), (5, 7), (15, 15)]
    foes = [(5, 8), (6, 6), (4, 6)]
    mine = [(0, 0), (0, 1), (0, 2), (15, 14)]
    target = G.assign_food_targets(mine, foods, foes, dist, ROWS, COLS)
    cluster = {(5, 5), (5, 6), (5, 7)}
    claims = [loc for loc in target.values() if loc in cluster]
    assert len(claims) == 2


def test_guard_extras_screen_the_razer() -> None:
    # Three raiders draw two guards but only one ant is free, so a
    # gatherer is drafted: it marches north to the guard rotation
    # instead of stepping east onto its food, while its partners
    # keep gathering. Without the guard branch it would take the
    # meal.
    mine = [(10, 1), (15, 14), (5, 5), (15, 16)]
    foods = [(10, 2), (15, 15), (15, 17)]
    foes = [(2, 4), (2, 5), (2, 6)]
    orders, _ = run_turn(mine, foes, foods=foods, my_hills=[(2, 2)])
    by_ant = dict(orders)
    assert by_ant.get((10, 1)) == "n"
    assert by_ant.get((15, 14)) == "e"
    assert by_ant.get((15, 16)) == "e"


def test_draft_cap_protects_the_economy() -> None:
    # One raider drafts exactly one guard; the other five gatherers
    # keep stepping onto their food.
    mine = [(0, 0), (0, 2), (0, 4), (0, 6), (0, 8), (0, 10)]
    foods = [(0, 1), (0, 3), (0, 5), (0, 7), (0, 9), (0, 11)]
    orders, _ = run_turn(mine, [(10, 9)], foods, my_hills=[(10, 10)])
    assert len(orders) == 5
    assert all(d == "e" for _, d in orders)


def test_muster_fearless_when_ahead_on_hills() -> None:
    # Ahead 2 hills to 1, the free ant marches straight through
    # contact while the drafted guard covers home.
    mine = [(0, 0), (10, 5)]
    orders, _ = run_turn(
        mine,
        [(10, 7)],
        enemy_hills=[(10, 10)],
        my_hills=[(0, 0), (0, 1)],
    )
    by_ant = dict(orders)
    assert by_ant.get((10, 5)) == "e"
    assert by_ant.get((0, 0)) == "e"


def test_food_route_threads_the_water_gap() -> None:
    # A wall with one gap: the claim steps toward the gap, not the wall.
    water = {(5, c) for c in range(20) if c != 10}
    orders, _ = run_turn([(3, 5)], [], foods=[(7, 5)], water=water)
    assert orders
    loc, direction = orders[0]
    probe = FakeAnts([(3, 5)], [], water=water)
    assert probe.distance(probe.destination(loc, direction), (5, 10)) < probe.distance(
        loc, (5, 10)
    )


def test_combined_arms_board() -> None:
    # One mid-game board: the guard routes west home around water,
    # flankers hold their surround, the gatherer steps onto food.
    # Without the guard branch the first ant would grinder-step
    # east instead.
    mine = [(4, 4), (15, 13), (15, 17), (10, 13), (0, 10)]
    foes = [(2, 6), (15, 15)]
    water = {(3, 4)}
    orders, _ = run_turn(
        mine,
        foes,
        foods=[(10, 15)],
        water=water,
        my_hills=[(2, 2)],
        enemy_hills=[(10, 10)],
    )
    by_ant = dict(orders)
    assert by_ant.get((4, 4)) == "w"
    assert by_ant.get((10, 13)) == "e"
    assert (15, 13) not in by_ant and (15, 17) not in by_ant


def test_guard_keeps_post_during_active_pin() -> None:
    # A pin burns elsewhere while a razer threatens home: the free
    # ant still marches home instead of joining the hunt.
    # Water blocks the explore/grinder drift east, so only the
    # guard march steps toward home.
    mine = [(4, 4), (15, 13), (15, 17)]
    foes = [(2, 6), (15, 15)]
    water = {(3, 4)}
    orders, bot = run_turn(mine, foes, water=water, my_hills=[(2, 2)])
    assert bot.pin == (15, 15)
    by_ant = dict(orders)
    assert (4, 4) in by_ant
    probe = FakeAnts(mine, foes, water=water)
    assert probe.distance(
        probe.destination((4, 4), by_ant[(4, 4)]), (2, 2)
    ) < probe.distance((4, 4), (2, 2))


def test_distant_ant_musters_past_the_pin() -> None:
    # A free ant beyond HUNT_RANGE of the victim marches east on the
    # muster instead of trekking to the kill. Plain explore would
    # drift north, so the exact step proves the muster fired while
    # the flankers hold their surround in silence.
    mine = [(15, 13), (15, 17), (0, 5)]
    orders, bot = run_turn(mine, [(15, 15)], enemy_hills=[(0, 10)])
    assert bot.pin == (15, 15)
    by_ant = dict(orders)
    assert by_ant.get((0, 5)) == "e"
    assert (15, 13) not in by_ant and (15, 17) not in by_ant


def test_packless_ant_rallies_near_foes() -> None:
    # No pin, no mission, foe within SEEK_RANGE: the packless ant
    # rallies west to its friend. Without the rally branch the ant
    # would explore north (blocked here by water) or step east into
    # a grinder duel, so only the rally step passes.
    assert G.has_pack((5, 5), [(5, 5), (0, 0)], dist) is False
    water = {(4, 5)}
    orders, _ = run_turn([(5, 5), (0, 0)], [(5, 8)], water=water)
    by_ant = dict(orders)
    assert by_ant.get((5, 5)) == "w"


def test_packed_ant_explores_freely() -> None:
    # With a pack (3+ friends near), the ant scouts instead of
    # rallying, even with foes visible but no pin.
    mine = [(5, 5), (5, 6), (6, 5), (6, 6)]
    foes = [(5, 12), (5, 13), (6, 12), (6, 13)]
    assert G.has_pack((5, 5), mine, dist) is True
    orders, _ = run_turn(mine, foes)
    by_ant = dict(orders)
    assert by_ant.get((5, 5)) == "n"


def test_blocked_muster_falls_back_to_explore() -> None:
    # Muster gated at a defender, reinforce refused, no friend to
    # rally to: the lone ant explores the one safe square instead
    # of donating or freezing.
    orders, _ = run_turn([(10, 5)], [(10, 7)], enemy_hills=[(10, 10), (0, 0)])
    assert orders == [((10, 5), "w")]


def test_corridor_contention_no_collision() -> None:
    # Two ants, one gap: the loser of the gap steps elsewhere, never
    # onto its partner's square.
    water = {(5, c) for c in range(20) if c != 5}
    mine = [(4, 4), (4, 6)]
    orders, _ = run_turn(mine, [], foods=[(7, 5)], water=water)
    probe = FakeAnts(mine, [], water=water)
    dests = [probe.destination(loc, d) for loc, d in orders]
    assert len(orders) == 2
    assert len(set(dests)) == 2


def test_blocked_guard_holds_its_ground() -> None:
    # A full water wall between guard and hill: no path, so the guard
    # holds instead of wandering off to explore.
    water = {(4, c) for c in range(20)}
    orders, _ = run_turn([(5, 5)], [(2, 8)], my_hills=[(2, 2)], water=water)
    assert orders == []


def test_party_cap_keeps_the_muster_intact() -> None:
    # Three hunters already on the surround: a fourth converges no
    # further and scouts instead, keeping the army massed.
    flat = lambda a, b: (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2  # noqa: E731
    assert G.party_full([(5, 6), (5, 8), (6, 7)], (5, 7), flat, 5) is True
    assert G.party_full([(5, 6), (5, 8)], (5, 7), flat, 5) is False
    orders, _ = run_turn([(5, 6), (5, 8), (6, 7), (5, 3)], [(5, 7)])
    assert orders == [((5, 3), "n")]


def test_intercept_routes_around_water() -> None:
    water = {(5, 7)}
    got = G.intercept_square(
        (5, 5), [(5, 9)], dist, lambda loc: loc not in water, ROWS, COLS
    )
    assert got == (4, 7)
    assert G.intercept_square((0, 0), [], dist, lambda loc: True, 0, 0) is None


def test_helpers_edge_values() -> None:
    assert G.nearest_seek_enemy((5, 5), [(15, 15), (5, 7)], dist) == (5, 7)
    assert G.nearest_seek_enemy((5, 5), [(15, 15)], dist) is None
    assert G.guards_needed(1) == 1
    assert G.guards_needed(3) == 2
    assert G.max_gatherer_draft(6) == 2
    assert G.max_gatherer_draft(2) == 0
    assert G.hill_threatened(10, False, False) is True
    assert G.hill_threatened(11, False, False) is False
    assert G.hill_threatened(16, True, False) is True
    assert G.hill_threatened(20, False, True) is True
    assert G.hill_threatened(21, False, True) is False


def test_assign_guards_free_first_then_capped_draft() -> None:
    assert G.assign_guards([0, 1], [2, 3, 4], [3], 1) == {0: 0, 1: 0, 2: 0}
    assert G.assign_guards([0], [1, 2], [1], 0) == {0: 0}
    assert G.endgame_active(599) is False
    assert G.endgame_active(600) is True


def test_reinforced_pack_releases_the_pin() -> None:
    # Hunters converge on a lone foe; when its pack arrives the pin
    # releases and both hunters retreat instead of donating.
    orders, _ = run_turn([(5, 3), (5, 11)], [(5, 7)])
    probe = FakeAnts([(5, 3), (5, 11)], [(5, 7)])
    moved = [probe.destination(loc, d) for loc, d in orders]
    assert len(moved) == 2
    pack = [(5, 7), (5, 6), (5, 8), (4, 7), (6, 7)]
    orders, bot = run_turn(moved, pack)
    assert bot.pin is None
    assert len(orders) == 2
    probe2 = FakeAnts(moved, pack)
    for loc, direction in orders:
        dest = probe2.destination(loc, direction)
        assert probe2.distance(dest, (5, 7)) > probe2.distance(loc, (5, 7))


def test_empty_army_turn_is_quiet() -> None:
    # No ants left: the turn finishes with no orders and no crash.
    orders, _ = run_turn([], [(5, 5)], foods=[(5, 6)], my_hills=[(0, 0)])
    assert orders == []


def test_denial_single_food_draws_single_claim() -> None:
    # A one-food contested cluster draws one claimant, not two; the
    # free ants work the open food instead.
    target = G.assign_food_targets(
        [(0, 0), (0, 2), (0, 4)],
        [(5, 5), (15, 15)],
        [(5, 6), (6, 5), (4, 5)],
        dist,
        ROWS,
        COLS,
    )
    assert list(target.values()).count((5, 5)) == 1
    assert (15, 15) in target.values()


def test_ant_never_camps_home_hill_early() -> None:
    orders, _ = run_turn([(3, 3)], [], my_hills=[(3, 3)])
    assert orders
    loc, direction = orders[0]
    assert FakeAnts([(3, 3)], []).destination(loc, direction) != (3, 3)


def test_big_maze_map_turn_stays_fast() -> None:
    # 100 ants on a 50x50 map with heavy water: BFS budgets hold and
    # the turn stays far inside the 1000ms budget.
    import random as _random

    rng = _random.Random(99)
    size = 50

    class MazeAnts(FakeAnts):
        def __init__(self):
            self.rows = size
            self.cols = size
            self.attackradius2 = 5
            spots = [(r, c) for r in range(size) for c in range(size)]
            rng.shuffle(spots)
            self._mine = spots[:100]
            self._enemies = spots[100:160]
            self._foods = spots[160:210]
            self._water = set(spots[210:610])
            self._enemy_hills = [(49, 49)]
            self._my_hills = [(0, 0)]
            self.orders = []

    fake = MazeAnts()
    bot = G.Greedy14()
    start = time.perf_counter()
    bot.do_turn(fake)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(fake.orders) > 0


def test_large_army_turn_stays_fast() -> None:
    # 150 ants on a 40x40 board: a full turn must stay far inside
    # the 1000ms budget.
    import random as _random

    rng = _random.Random(14)
    big_rows = big_cols = 40

    class BigAnts(FakeAnts):
        def __init__(self):
            self.rows = big_rows
            self.cols = big_cols
            self.attackradius2 = 5
            spots = [(r, c) for r in range(40) for c in range(40)]
            rng.shuffle(spots)
            self._mine = spots[:150]
            self._enemies = spots[150:230]
            self._foods = spots[230:280]
            self._water = set(spots[280:300])
            self._enemy_hills = [(39, 39)]
            self._my_hills = [(0, 0)]
            self.orders = []

    fake = BigAnts()
    bot = G.Greedy14()
    start = time.perf_counter()
    bot.do_turn(fake)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(fake.orders) > 0


def test_fuzz_orders_always_legal() -> None:
    # Random boards: every issued order moves a live ant one step
    # onto a passable, unoccupied square, destinations never collide,
    # and a fresh bot replays the same orders deterministically.
    import random as _random

    for seed in range(40):
        rng = _random.Random(1000 + seed)
        t0 = time.perf_counter()
        spots = [(r, c) for r in range(ROWS) for c in range(COLS)]
        rng.shuffle(spots)
        mine = spots[: rng.randint(1, 12)]
        foes = spots[12 : 12 + rng.randint(0, 12)]
        foods = spots[24 : 24 + rng.randint(0, 10)]
        water = set(spots[34 : 34 + rng.randint(0, 30)])
        mine = [m for m in mine if m not in water]
        foes = [f for f in foes if f not in water]
        foods = [f for f in foods if f not in water]
        if not mine:
            continue
        hills = [mine[0]] if rng.random() < 0.5 else []
        e_hills = [foes[0]] if foes and rng.random() < 0.5 else []
        fake = FakeAnts(mine, foes, foods, water, e_hills, hills)
        bot = G.Greedy14()
        if seed % 5 == 4:
            bot.turn = 599
        bot.do_turn(fake)
        assert time.perf_counter() - t0 < 1.0
        seen_dest: set[Loc] = set()
        for loc, direction in fake.orders:
            assert loc in mine
            assert direction in ("n", "e", "s", "w")
            dest = fake.destination(loc, direction)
            assert fake.passable(dest)
            assert fake.unoccupied(dest)
            assert dest not in seen_dest
            seen_dest.add(dest)
        replay = FakeAnts(mine, foes, foods, water, e_hills, hills)
        replay_bot = G.Greedy14()
        if seed % 5 == 4:
            replay_bot.turn = 599
        replay_bot.do_turn(replay)
        assert replay.orders == fake.orders


def test_engine_protocol_roundtrip() -> None:
    # The real file under the real stdin protocol: setup ack, legal
    # orders, and clean turn finishes across two turns (state such
    # as pin memory and visits carries without crashing).
    import subprocess as _subprocess

    blob = (
        "turn 0\nloadtime 3000\nturntime 1000\nrows 10\ncols 10\n"
        "turns 100\nviewradius2 77\nattackradius2 5\nspawnradius2 1\n"
        "ready\n"
        "turn 1\nf 5 5\na 1 1 0\na 1 2 0\na 8 8 1\nh 0 0 0\ngo\n"
        "turn 2\nf 5 5\na 0 1 0\na 1 3 0\na 8 7 1\nh 0 0 0\ngo\n"
    )
    # The engine loop never EOF-exits (the engine kills the bot), so
    # expect the timeout and parse the flushed output it left behind.
    try:
        _subprocess.run(
            [os.environ.get("PYTHON", "python3"), "Greedy14.py"],
            input=blob,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        out = ""
    except _subprocess.TimeoutExpired as exc:
        raw = exc.stdout or ""
        out = raw.decode() if isinstance(raw, bytes) else raw
    lines = out.splitlines()
    assert lines[0] == "go"
    orders = [ln for ln in lines if ln.startswith("o ")]
    assert len(orders) >= 2
    for ln in orders:
        _, r, c, d = ln.split()
        assert (int(r), int(c)) in [(1, 1), (1, 2), (0, 1), (1, 3)]
        assert d in ("n", "e", "s", "w")
    assert lines[-1] == "go"


def test_dense_maze_fuzz_stays_legal_and_fast() -> None:
    # A third of the board water: routing budgets exhaust often, and
    # every fallback must still issue legal orders inside 1s.
    import random as _random

    for seed in range(10):
        rng = _random.Random(5000 + seed)
        size = 30
        spots = [(r, c) for r in range(size) for c in range(size)]
        rng.shuffle(spots)
        mine = [m for m in spots[:30] if m not in set(spots[90:390])]
        foes = [f for f in spots[30:60] if f not in set(spots[90:390])]
        foods = [f for f in spots[60:90] if f not in set(spots[90:390])]
        water = set(spots[90:390])
        if not mine:
            continue
        fake = FakeAnts(mine, foes, foods, water)
        fake.rows = size
        fake.cols = size
        bot = G.Greedy14()
        start = time.perf_counter()
        bot.do_turn(fake)
        assert time.perf_counter() - start < 1.0
        seen_dest: set[Loc] = set()
        for loc, direction in fake.orders:
            assert loc in mine
            dest = fake.destination(loc, direction)
            assert fake.passable(dest)
            assert fake.unoccupied(dest)
            assert dest not in seen_dest
            seen_dest.add(dest)


# (d) speed -------------------------------------------------------------------


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
