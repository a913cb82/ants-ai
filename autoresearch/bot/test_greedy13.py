#!/usr/bin/env python
"""Wedge-seek + toll-harvest tests (Greedy13 entry).

Greedy13 keeps the proven spine -- denial economy, corner-post
guards with halfway screens, pack-gated seek, joined-pair commits,
ahead-only duels, equal trades at ten near friends, 2:1 hill
assaults, testudo fallback, stand-off harvest, rotated explore,
walk-off -- and adds four new rules:

(a) wedge seek: a combat seeker inside SEEK_RANGE does not chase
    the foe nearest itself; it marches on the foe nearest the
    army centroid, so scattered seekers converge into a wedge
    instead of scattering into 1v1s;
(b) toll harvest: a food claim standing inside a locally lost
    contact (more visible foes than friends within TOLL_R of
    the meal) is ceded outright, so no ant treks into a losing
    fight for a meal the safety filter would refuse anyway;
(c) frontier explore: the least-visited fallback prefers the
    darkest ground (most unseen within radius 3);
(d) grave check: a remembered hill seen empty is forgotten, so
    no raid marches on a razed hill; plus the champion's press
    (packed seekers advance fearlessly under ten enemies).

Proves, on fixed boards before the bot code lands:
(a) wedge_mark picks the centroid-nearest foe in range, and None
    past the range;
(b) toll cedes lost meals and keeps backed ones;
(c) the carried spine still holds: stand-off, guard, assault
    margin, walk-off, and a crowded turn under one second.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Greedy13 as G  # noqa: E402

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
        owners: list[int] | None = None,
    ) -> None:
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = 5
        self._mine = list(mine)
        self._enemies = list(enemies)
        self._owners = list(owners) if owners is not None else [1] * len(enemies)
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
        return list(zip(self._enemies, self._owners, strict=True))

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

    def visible(self, loc: Loc) -> bool:
        return any(self.distance(m, loc) <= 6 for m in self._mine)

    def time_remaining(self) -> int:
        return 100000


def run_turn(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
    bot: G.Greedy13 | None = None,
    owners: list[int] | None = None,
) -> tuple[list[tuple[Loc, str]], G.Greedy13]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills, owners)
    bot = bot if bot is not None else G.Greedy13()
    bot.do_turn(fake)
    return fake.orders, bot


def dist(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


# (a) wedge seek ------------------------------------------------------------


def test_wedge_mark_picks_centroid_nearest_foe_in_range() -> None:
    # Army massed near (10,10); seeker at (10,4). Foe A at (10,5)
    # is nearest the seeker (d=1) but foe B at (10,8) is nearest
    # the army mean: the wedge converges on B, not A.
    mine = [(10, 10), (10, 11), (11, 10), (10, 4)]
    foes = [(10, 5), (10, 8)]
    mark = G.wedge_mark((10, 4), mine, foes, dist)
    assert mark == (10, 8)


def test_wedge_mark_returns_none_past_range() -> None:
    mine = [(10, 10), (10, 11)]
    assert G.wedge_mark((10, 10), mine, [(0, 0)], dist) is None
    assert G.wedge_mark((10, 10), mine, [], dist) is None


def test_wedge_mark_single_foe_in_range_is_that_foe() -> None:
    mine = [(5, 5)]
    assert G.wedge_mark((5, 5), mine, [(5, 7)], dist) == (5, 7)


def test_wedge_mark_far_centroid_still_marks() -> None:
    # The centroid sits far from the contact; the in-range foe
    # must still mark (heart-distance is a ranking, not a gate).
    mine = [(0, 0), (0, 1), (10, 10)]
    assert G.wedge_mark((10, 10), mine, [(10, 12)], dist) == (10, 12)


def test_seekers_converge_on_centroid_foe() -> None:
    # Two seekers straddling two foes: both step toward the foe
    # nearest the massed army, not each toward its own nearest.
    mine = [(10, 10), (10, 11), (11, 10), (8, 4), (12, 4)]
    orders, _ = run_turn(mine, [(8, 6), (10, 8)])
    by_ant = dict(orders)
    # The (8,4) seeker stands two from (8,6) yet the wedge target
    # is (10,8): it must step east/south toward the wedge, never
    # west or north away from it.
    assert by_ant.get((8, 4)) in ("e", "s")


# (b) toll harvest --------------------------------------------------------


def test_toll_cedes_meal_inside_lost_contact() -> None:
    # Meal at (5,5) with three foes and no friend near: locally
    # lost, so the claim is ceded outright.
    assert G.toll_lost((5, 5), (5, 8), [(5, 5)], [(5, 4), (4, 5), (5, 6)], dist)


def test_toll_keeps_backed_meal() -> None:
    # Same meal with two friends backing: not lost, claim stands.
    assert not G.toll_lost((5, 5), (5, 8), [(5, 8), (5, 7)], [(5, 4), (4, 5)], dist)


def test_toll_counts_distant_claimant_as_backup() -> None:
    # Claimant seven away still counts: two near friends plus the
    # trekker beat one foe, so the claim stands.
    assert not G.toll_lost((5, 5), (5, 12), [(5, 12), (5, 4), (5, 6)], [(5, 3)], dist)


def test_toll_cedes_unbacked_trek() -> None:
    # Same trek with no friends near the meal: two foes beat the
    # lone trekker, so the claim is ceded.
    assert G.toll_lost((5, 5), (5, 12), [(5, 12)], [(5, 3), (5, 7)], dist)


def test_toll_keeps_quiet_meal() -> None:
    # No foe near the meal: never lost, however far the friends.
    assert not G.toll_lost((5, 5), (15, 15), [(15, 15)], [(0, 0)], dist)


def test_toll_saves_wasted_trek() -> None:
    # Two foes hold the meal: too few to heat the cluster, but the
    # lone trekker is beaten at the meal -- the claim is ceded and
    # the ant explores north instead of stepping west toward doom.
    orders, _ = run_turn([(0, 8)], [(0, 1), (0, 3)], [(0, 2)])
    assert orders == [((0, 8), "n")]


def test_lone_ant_does_not_trek_into_lost_meal() -> None:
    # One ant, one meal parked between three foes: the meal is
    # ceded and the ant explores instead of trekking to its death.
    orders, _ = run_turn([(5, 8)], [(5, 4), (4, 5), (6, 5)], [(5, 5)])
    for loc, direction in orders:
        assert FakeAnts([(5, 8)], []).destination(loc, direction) != (5, 5)


# (c) carried spine ---------------------------------------------------------


def test_stand_off_holder_stays_adjacent() -> None:
    # Ant adjacent to food holds: no order issues, the engine
    # gathers by proximity and stepping on would be ignored.
    orders, _ = run_turn([(5, 5)], [], [(5, 6)])
    assert orders == []


def test_food_step_never_lands_on_food() -> None:
    orders, _ = run_turn([(5, 3)], [], [(5, 5)])
    assert orders
    loc, direction = orders[0]
    assert FakeAnts([(5, 3)], []).destination(loc, direction) != (5, 5)


def test_guard_answers_threatened_hill() -> None:
    # Two backed ants answer the threat: the point guard steps
    # strictly closer to home (a lone ant correctly refuses the
    # unsafe approach and holds instead of donating).
    probe = FakeAnts([(5, 5)], [(2, 5)], my_hills=[(2, 2)])
    assert probe.distance((2, 2), (2, 5)) <= 10
    orders, _ = run_turn([(5, 5), (5, 6)], [(2, 5)], my_hills=[(2, 2)])
    assert orders
    loc, direction = orders[0]
    assert probe.distance(probe.destination(loc, direction), (2, 2)) < probe.distance(
        loc, (2, 2)
    )


def test_muster_marches_remembered_hill() -> None:
    probe = FakeAnts([(0, 0)], [])
    orders, bot = run_turn([(0, 0)], [], enemy_hills=[(10, 10)])
    assert (10, 10) in bot.hills
    assert orders
    loc, direction = orders[0]
    assert probe.distance(probe.destination(loc, direction), (10, 10)) < probe.distance(
        loc, (10, 10)
    )


def test_gates_pure() -> None:
    assert G.has_majority(3, 2)
    assert not G.has_majority(2, 2)
    assert not G.has_majority(0, 0)
    assert G.strongest_rival([((0, 0), 1), ((0, 1), 1), ((0, 2), 2)]) == 2
    assert G.strongest_rival([]) == 0
    assert G.crowd_fearless(9)
    assert not G.crowd_fearless(10)


def test_takeable_margin_gates_hill_assault() -> None:
    # Empty hills always raid; camped hills need twice the campers.
    assert G.takeable(1, 0)
    assert not G.takeable(1, 2)
    assert not G.takeable(3, 2)
    assert G.takeable(4, 2)
    assert G.takeable(5, 2)


def test_fragmented_field_does_not_block_muster() -> None:
    # Nine visible foes, every one a different owner: the strongest
    # rival is one, so the lone ant still stands even and marches
    # on the empty hill. A sum-of-flags majority would cower.
    mine = [(10, 10)]
    foes = [(5, 0), (5, 1), (5, 2), (0, 5), (0, 6), (1, 5), (2, 5), (3, 5), (4, 5)]
    owners = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    orders, _ = run_turn(mine, foes, enemy_hills=[(15, 15)], owners=owners)
    assert orders
    loc, direction = orders[0]
    assert loc == (10, 10)
    assert dist(FakeAnts(mine, []).destination(loc, direction), (15, 15)) < dist(
        loc, (15, 15)
    )


def test_muster_marches_takeable_hill() -> None:
    # Four ants vs two campers: 4 >= 2*2, so the point ant steps
    # strictly closer to the hill.
    mine = [(0, 0), (0, 1), (1, 0), (1, 1)]
    orders, _ = run_turn(mine, [(10, 9), (9, 10)], enemy_hills=[(10, 10)])
    assert orders
    loc, direction = orders[0]
    assert loc == (0, 0)
    assert dist(FakeAnts(mine, []).destination(loc, direction), (10, 10)) < dist(
        loc, (10, 10)
    )


def test_food_outranks_suicide_march() -> None:
    # One ant, visible food, and a camped hill it cannot take: it
    # gathers instead of donating into the camp.
    orders, _ = run_turn([(0, 0)], [(10, 9), (9, 10)], [(0, 2)], enemy_hills=[(10, 10)])
    assert orders == [((0, 0), "e")]


def test_explore_prefers_unseen_frontier() -> None:
    # All four neighbors unvisited, but the east side is mapped
    # and the west is dark: the wedge pushes west into the dark.
    visits = {(r, c): 5 for r in range(20) for c in range(11, 20)}
    assert G.explore_dirs((10, 10), visits, 20, 20)[0] == "w"


def test_explore_still_prefers_least_visited() -> None:
    # Least-visited outranks the frontier: trampled west loses to
    # fresh squares, with rotation breaking the remaining tie.
    visits = {(10, 9): 5}
    assert G.explore_dirs((10, 10), visits, 20, 20)[0] == "n"


def test_far_centroid_seeker_still_engages() -> None:
    # Six far ants drag the centroid away from the contact, but
    # the packed seeker must still step east onto (10,11) toward
    # the in-range foe instead of idling.
    mine = [(10, 10), (10, 9), (9, 10), (11, 10)] + [(0, c) for c in range(6)]
    orders, _ = run_turn(mine, [(10, 12)])
    assert ((10, 10), "e") in orders


def test_pack_threshold_presses_at_four() -> None:
    # Three pals at mid range make the pack: the seeker presses
    # east into the unsafe contact fearlessly.
    orders, _ = run_turn([(10, 10), (10, 4), (10, 5), (10, 6)], [(10, 12)])
    assert ((10, 10), "e") in orders


def test_pack_threshold_holds_at_three() -> None:
    # Two pals short of a pack: no press, the seeker regroups
    # west toward its nearest pal instead.
    orders, _ = run_turn([(10, 10), (10, 4), (10, 5)], [(10, 12)])
    assert ((10, 10), "e") not in orders
    assert ((10, 10), "w") in orders


def test_unpacked_seeker_regroups_to_pal() -> None:
    # Seeker with a foe in range but only one pal (short of a
    # pack): it steps toward its pal instead of donating in.
    orders, _ = run_turn([(10, 10), (10, 0)], [(10, 12)])
    assert orders
    loc, direction = orders[0]
    assert loc == (10, 10)
    assert FakeAnts([(10, 10)], []).destination(loc, direction) != (10, 11)


def test_outnumbered_ant_testudos_home() -> None:
    # One ant, three rivals, a remembered hill across the map: no
    # march (not standing); the ant testudos toward home instead.
    orders, _ = run_turn(
        [(0, 5)],
        [(10, 9), (10, 10), (10, 11)],
        enemy_hills=[(15, 15)],
        my_hills=[(0, 0)],
    )
    assert orders
    loc, direction = orders[0]
    dest = FakeAnts([(0, 5)], []).destination(loc, direction)
    assert dist(dest, (0, 0)) < dist(loc, (0, 0))


def test_packed_seeker_presses_small_fight() -> None:
    # Packed seeker, two visible foes: the safe filter refuses the
    # step (1v2 at the destination, three near friends short of
    # the ten-gate), but the small-fight press takes it anyway --
    # the wedge hunts.
    mine = [(10, 10), (10, 2), (10, 3), (10, 4)]
    orders, _ = run_turn(mine, [(10, 12), (10, 13)])
    assert ((10, 10), "e") in orders


def test_packed_seeker_holds_crowd() -> None:
    # Same contact with ten-plus visible enemies: the press is off
    # and the safe filter holds the step -- the seeker explores
    # west instead.
    mine = [(10, 10), (10, 2), (10, 3), (10, 4)]
    foes = [(10, 12), (10, 13)] + [(0, c) for c in range(9)]
    orders, _ = run_turn(mine, foes)
    assert ((10, 10), "e") not in orders
    assert ((10, 10), "w") in orders


def test_seen_empty_hill_is_forgotten() -> None:
    # Remembered hill, then a turn with a sighted but empty hill
    # square: the raid cancels instead of marching cross-map.
    _, bot = run_turn([(0, 0)], [], enemy_hills=[(10, 10)])
    assert (10, 10) in bot.hills
    orders, bot = run_turn([(9, 10)], [], enemy_hills=[], bot=bot)
    assert (10, 10) not in bot.hills
    for loc, direction in orders:
        dest = FakeAnts([(9, 10)], []).destination(loc, direction)
        assert dest != (10, 10)


def test_unseen_hill_survives_fog() -> None:
    # Remembered hill far from every ant: out of sight, so the
    # raid stands even though no hill is reported this turn.
    _, bot = run_turn([(0, 0)], [], enemy_hills=[(10, 10)])
    orders, bot = run_turn([(0, 0)], [], enemy_hills=[], bot=bot)
    assert (10, 10) in bot.hills
    assert orders


def test_contests_food_when_ahead() -> None:
    # Four ants, three mid-range foes heating two meals: ahead of
    # the strongest rival, two ants claim (one per meal) while the
    # other two explore -- the last ant steps food-ward, never on
    # its explore-north fallback.
    mine = [(0, 0), (0, 1), (0, 2), (0, 3)]
    foes = [(5, 10), (5, 11), (5, 12)]
    orders, _ = run_turn(mine, foes, [(5, 5), (5, 6)])
    assert len(orders) == 4
    assert orders[0] == ((0, 0), "n")
    assert orders[1] == ((0, 1), "s")
    assert orders[3][0] == (0, 3)
    assert orders[3][1] in ("s", "e")


def test_outnumbered_cedes_contested_food() -> None:
    # Three mid-range foes heat the cluster, but the lone ant is
    # behind the strongest rival: no denial claim fires and the
    # ant explores east instead of trekking west to the meal.
    orders, _ = run_turn([(5, 8)], [(5, 0), (5, 1), (5, 2)], [(5, 5)])
    assert orders == [((5, 8), "e")]


def test_gathering_holds_across_turns() -> None:
    # Turn one steps toward the meal; turn two stands adjacent and
    # gathers by proximity with no order issued.
    orders, bot = run_turn([(0, 0)], [], [(0, 2)])
    assert orders == [((0, 0), "e")]
    orders, _ = run_turn([(0, 1)], [], [(0, 2)], bot=bot)
    assert orders == []


def test_ahead_duel_engages_in_crowd() -> None:
    # Twelve ants, eleven foes: no fearless press, but the packed
    # seeker is friendless at the contact square while the visible
    # army leads -- the 1v1 duel engages east.
    mine = [(5, 5), (5, 0), (5, 1), (5, 2)] + [(15, c) for c in range(10, 18)]
    foes = [(5, 7)] + [(15, c) for c in range(10)]
    orders, _ = run_turn(mine, foes)
    assert orders[0] == ((5, 5), "e")


def test_even_duel_holds_in_crowd() -> None:
    # Eleven against eleven: parity is not a lead, so the same
    # contact holds and the seeker explores west instead.
    mine = [(5, 5), (5, 0), (5, 1), (5, 2)] + [(15, c) for c in range(10, 17)]
    foes = [(5, 7)] + [(15, c) for c in range(10)]
    orders, _ = run_turn(mine, foes)
    assert orders[0] == ((5, 5), "w")


def test_lone_ant_never_duels() -> None:
    # Sole ant with a foe two squares away: no pack, no pal, so no
    # seek at all -- it sidesteps west instead of taking the 1v1.
    orders, _ = run_turn([(5, 5)], [(5, 7)])
    assert orders == [((5, 5), "w")]


def test_sealed_food_falls_back_to_explore() -> None:
    # The only meal is walled in water: the claim stands but no
    # path exists, so the ant explores south instead.
    water = {(5, 6), (4, 7), (6, 7), (5, 8)}
    orders, _ = run_turn([(5, 5)], [], [(5, 7)], water)
    assert orders == [((5, 5), "s")]


def test_stationary_lurker_draws_no_guard() -> None:
    # Foe sits at 16 steps two turns running, never closing: no
    # threat reads, plain explore south both turns.
    bot = G.Greedy13()
    f1 = FakeAnts([(10, 12)], [(2, 2)], my_hills=[(10, 10)])
    bot.do_turn(f1)
    assert f1.orders == [((10, 12), "s")]
    f2 = FakeAnts([(10, 12)], [(2, 2)], my_hills=[(10, 10)])
    bot.do_turn(f2)
    assert f2.orders == [((10, 12), "s")]


def test_closing_memory_spots_razer_early() -> None:
    # Turn one the foe lurks at 16: plain explore south. Turn two
    # it closes to 15: heading memory reads the approach and the
    # guard marches west toward the post.
    bot = G.Greedy13()
    f1 = FakeAnts([(10, 12)], [(2, 2)], my_hills=[(10, 10)])
    bot.do_turn(f1)
    assert f1.orders == [((10, 12), "s")]
    f2 = FakeAnts([(10, 12)], [(2, 3)], my_hills=[(10, 10)])
    bot.do_turn(f2)
    assert f2.orders == [((10, 12), "w")]


def test_water_wall_routes_through_gap() -> None:
    water = {(r, 5) for r in range(20) if r != 10}
    orders, _ = run_turn([(10, 2)], [], [(10, 8)], water)
    assert orders == [((10, 2), "e")]


def test_unsafe_holder_abandons_bait_food() -> None:
    # Adjacent to the meal but a foe covers the square: the holder
    # abandons west instead of dying on the food.
    orders, _ = run_turn([(5, 5)], [(5, 7)], [(5, 6)])
    assert orders == [((5, 5), "w")]


def test_muster_skips_camped_hill_for_empty() -> None:
    # Near hill camped by three (four ants cannot take it) yields
    # to the far empty hill: the point ant marches west.
    mine = [(0, 0), (0, 1), (1, 0), (1, 1)]
    foes = [(5, 4), (4, 5), (6, 5)]
    orders, _ = run_turn(mine, foes, enemy_hills=[(5, 5), (0, 15)])
    assert orders[0] == ((0, 0), "w")


def test_far_testudo_forages_instead() -> None:
    # Outnumbered with home past the horizon: no cross-map trek,
    # the ant forages north on explore.
    orders, _ = run_turn(
        [(0, 0)],
        [(15, 14), (15, 15), (15, 16)],
        enemy_hills=[(15, 15)],
        my_hills=[(11, 10)],
    )
    assert orders == [((0, 0), "n")]


def test_same_board_same_orders() -> None:
    mine = [(5, 5), (5, 6), (0, 0)]
    foes = [(5, 10), (15, 15)]
    first, _ = run_turn(mine, foes, [(0, 5)], enemy_hills=[(15, 15)])
    second, _ = run_turn(mine, foes, [(0, 5)], enemy_hills=[(15, 15)])
    assert first == second


def test_guards_split_across_threats() -> None:
    # Two hills, two razers: each ant answers its nearest threat,
    # and the ant already posted adjacent holds without an order.
    orders, _ = run_turn(
        [(5, 0), (15, 14)], [(5, 8), (15, 12)], my_hills=[(5, 5), (15, 15)]
    )
    assert orders == [((5, 0), "e")]


def test_one_ant_per_food() -> None:
    # Two ants, one meal: the nearer claims and steps east while
    # the farther explores north instead of doubling up.
    orders, _ = run_turn([(0, 0), (0, 2)], [], [(0, 4)])
    assert orders == [((0, 0), "n"), ((0, 2), "e")]


def test_extra_guard_screens_halfway() -> None:
    # Two ants answer one threat: the first anchors home, the extra
    # screens the razer at the halfway square, stepping east.
    orders, _ = run_turn([(5, 0), (5, 1)], [(5, 10)], my_hills=[(5, 5)])
    assert ((5, 1), "e") in orders


def test_joined_pair_takes_even_trade_in_crowd() -> None:
    # Eleven foes visible: no fearless press, no duel (outnumbered),
    # and the safe filter refuses the 1v1 step -- but both seekers
    # committed on the same foe, so the joined even trade goes
    # through without the ten-near-friends gate.
    mine = [(10, 10), (8, 14), (12, 5), (8, 5)]
    foes = [(10, 13)] + [(0, c) for c in range(10)]
    orders, _ = run_turn(mine, foes)
    assert ((10, 10), "e") in orders


def test_quiet_ant_explores_safely() -> None:
    # Lone ant, no contact anywhere: one safe explore step, never
    # a step onto water and never into a foe.
    water = {(4, 5), (6, 5), (5, 4)}
    orders, _ = run_turn([(5, 5)], [(15, 15)], water=water)
    assert orders == [((5, 5), "e")]


def test_empty_army_issues_nothing() -> None:
    orders, _ = run_turn([], [(5, 5)], [(5, 6)])
    assert orders == []


def test_no_food_no_foe_no_crash() -> None:
    orders, _ = run_turn([(5, 5)], [], [])
    assert len(orders) <= 1


def test_walled_ant_holds_without_crash() -> None:
    # Water on all four sides: every branch fails, the ant holds
    # and the turn still ends cleanly.
    water = {(4, 5), (6, 5), (5, 4), (5, 6)}
    orders, _ = run_turn([(5, 5)], [(0, 0)], [(10, 10)], water)
    assert orders == []


def test_fuzz_orders_always_legal() -> None:
    # Sixty seeded scrambles, some with a maze wall and hills: never
    # crash, every order from a live ant, every destination
    # distinct, passable, and unoccupied.
    import random

    rng = random.Random(1234)
    for _ in range(60):
        mine = [
            (rng.randrange(20), rng.randrange(20)) for _ in range(rng.randrange(1, 12))
        ]
        foes = [
            (rng.randrange(20), rng.randrange(20)) for _ in range(rng.randrange(0, 12))
        ]
        foods = [
            (rng.randrange(20), rng.randrange(20)) for _ in range(rng.randrange(0, 8))
        ]
        water = {
            (rng.randrange(20), rng.randrange(20)) for _ in range(rng.randrange(0, 15))
        }
        if rng.randrange(4) == 0:
            water |= {(10, c) for c in range(20) if c != 10}
        hills = [
            (rng.randrange(20), rng.randrange(20)) for _ in range(rng.randrange(0, 2))
        ]
        homes = [
            (rng.randrange(20), rng.randrange(20)) for _ in range(rng.randrange(0, 2))
        ]
        mine = list(dict.fromkeys(m for m in mine if m not in water))
        foes = list(dict.fromkeys(m for m in foes if m not in water))
        if not mine:
            continue
        fake = FakeAnts(mine, foes, foods, water, hills, homes)
        bot = G.Greedy13()
        bot.do_turn(fake)
        seen_locs = [loc for loc, _ in fake.orders]
        assert len(set(seen_locs)) == len(seen_locs)
        dests = set()
        for loc, direction in fake.orders:
            assert loc in mine
            dest = fake.destination(loc, direction)
            assert dest not in dests
            dests.add(dest)
            assert fake.passable(dest)
            assert fake.unoccupied(dest)


def test_soak_mixed_board_many_turns() -> None:
    # Ten turns on a mixed board with one persistent bot: memory
    # (visits, hills, headings) accumulates without crash, every
    # turn ends with legal orders, and the whole soak is fast.
    import time

    bot = G.Greedy13()
    mine = [(5, 5), (5, 6), (0, 0)]
    foes = [(5, 10), (15, 15)]
    start = time.perf_counter()
    for turn in range(10):
        foods = [(0, 5)] if turn % 2 == 0 else [(10, 10)]
        hills = [(15, 15)] if turn < 5 else []
        fake = FakeAnts(mine, foes, foods, enemy_hills=hills, my_hills=[(0, 19)])
        bot.do_turn(fake)
        seen = [loc for loc, _ in fake.orders]
        assert len(set(seen)) == len(seen)
        moves = {}
        for loc, direction in fake.orders:
            dest = fake.destination(loc, direction)
            assert fake.passable(dest)
            assert fake.unoccupied(dest) or dest in moves
            moves[dest] = loc
        mine = [moves.get(m, m) for m in mine]
    assert time.perf_counter() - start < 2.0


def test_setup_resets_memory() -> None:
    bot = G.Greedy13()
    _, bot = run_turn([(0, 0)], [], enemy_hills=[(10, 10)], bot=bot)
    assert (10, 10) in bot.hills
    bot.do_setup(FakeAnts([(0, 0)], []))
    assert bot.hills == set()
    assert bot.visits == {}


def test_arriving_clears_remembered_hill() -> None:
    _, bot = run_turn([(0, 0)], [], enemy_hills=[(10, 10)])
    _, bot = run_turn([(10, 10)], [], enemy_hills=[], bot=bot)
    assert (10, 10) not in bot.hills


def test_fuzz_maze_hills_always_legal() -> None:
    # Thirty seeded maze scrambles with hills on both sides:
    # pathing-heavy turns stay legal and fast.
    import random
    import time

    rng = random.Random(777)
    start = time.perf_counter()
    for _ in range(30):
        mine = list(
            dict.fromkeys(
                (rng.randrange(20), rng.randrange(20))
                for _ in range(rng.randrange(1, 10))
            )
        )
        foes = list(
            dict.fromkeys(
                (rng.randrange(20), rng.randrange(20))
                for _ in range(rng.randrange(0, 10))
            )
        )
        foods = [(rng.randrange(20), rng.randrange(20)) for _ in range(6)]
        water = {(r, 5) for r in range(20) if r not in (3, 10, 17)}
        water |= {(r, 14) for r in range(20) if r not in (6, 13)}
        mine = [m for m in mine if m not in water]
        foes = [f for f in foes if f not in water]
        if not mine:
            continue
        fake = FakeAnts(mine, foes, foods, water, [(18, 18)], [(1, 1)])
        bot = G.Greedy13()
        bot.do_turn(fake)
        seen = [loc for loc, _ in fake.orders]
        assert len(set(seen)) == len(seen)
        for loc, direction in fake.orders:
            dest = fake.destination(loc, direction)
            assert fake.passable(dest)
            assert fake.unoccupied(dest)
    assert time.perf_counter() - start < 3.0


def test_fuzz_tiny_maps_stay_legal() -> None:
    # Forty scrambles on 3x3 and 6x6 tori: wrap-heavy geometry
    # stays legal, with hills remembered and forgotten across
    # turns.
    import random

    rng = random.Random(31337)
    for trial in range(40):
        size = 3 if trial % 2 == 0 else 6
        tiny_mine = list(
            dict.fromkeys(
                (rng.randrange(size), rng.randrange(size))
                for _ in range(rng.randrange(1, 6))
            )
        )
        tiny_foes = list(
            dict.fromkeys(
                (rng.randrange(size), rng.randrange(size))
                for _ in range(rng.randrange(0, 6))
            )
        )
        tiny_foods = [(rng.randrange(size), rng.randrange(size)) for _ in range(3)]
        tiny_hills = [(rng.randrange(size), rng.randrange(size)) for _ in range(1)]
        bot = G.Greedy13()
        first = FakeAnts(tiny_mine, tiny_foes, tiny_foods, set(), tiny_hills, [(0, 0)])
        first.rows = size
        first.cols = size
        bot.do_turn(first)
        for loc, direction in first.orders:
            dest = first.destination(loc, direction)
            assert first.passable(dest)
            assert first.unoccupied(dest)
        moved = [first.destination(loc, d) for loc, d in first.orders]
        second = FakeAnts(
            moved or tiny_mine, tiny_foes, tiny_foods, set(), [], [(0, 0)]
        )
        second.rows = size
        second.cols = size
        bot.do_turn(second)


def test_low_time_still_legal() -> None:
    # Two hundred milliseconds left on a crowded board: the valve
    # shortens pathing but every order stays legal.
    mine = [(r, c) for r in range(0, 20, 2) for c in range(0, 20, 2)][:40]
    enemies = [(r, c) for r in range(1, 20, 2) for c in range(1, 20, 2)][:40]
    fake = FakeAnts(mine, enemies, [(0, 5)], enemy_hills=[(19, 19)], my_hills=[(0, 0)])
    fake.time_remaining = lambda: 200  # type: ignore[method-assign]
    bot = G.Greedy13()
    bot.do_turn(fake)
    for loc, direction in fake.orders:
        dest = fake.destination(loc, direction)
        assert fake.passable(dest)
        assert fake.unoccupied(dest)


def test_real_path_soak() -> None:
    # Twenty turns through the real ants.Ants object: setup,
    # update, do_turn, applied orders. Food gets gathered, the
    # enemy hill is remembered, every turn is fast, and nothing
    # crashes.
    from ants import Ants

    rows, cols = 30, 30
    ants = Ants()
    ants.setup(
        "turn 0\nloadtime 3000\nturntime 1000\n"
        f"rows {rows}\ncols {cols}\nturns 100\n"
        "viewradius2 77\nattackradius2 5\nspawnradius2 1\n"
        "player_seed 5\nready\n"
    )
    bot = G.Greedy13()
    bot.do_setup(ants)
    mine = [(5, 5), (5, 6), (6, 5)]
    foes = [(20, 20), (21, 20)]
    foods = [(5, 10), (12, 12), (25, 25)]
    recorded: list[tuple[Loc, str]] = []
    ants.issue_order = recorded.append
    aim = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
    start = time.perf_counter()
    for turn in range(1, 21):
        lines = [f"turn {turn}"]
        for c in range(8, 22):
            lines.append(f"w 10 {c}")
        for f in foods:
            lines.append(f"f {f[0]} {f[1]}")
        for m in mine:
            lines.append(f"a {m[0]} {m[1]} 0")
        for e in foes:
            lines.append(f"a {e[0]} {e[1]} 1")
        lines.append("h 2 2 0")
        lines.append("h 27 27 1")
        lines.append("go")
        ants.update("\n".join(lines))
        recorded.clear()
        bot.do_turn(ants)
        moves = dict(recorded)
        mine = [
            ((r + aim[moves[(r, c)]][0]) % rows, (c + aim[moves[(r, c)]][1]) % cols)
            if (r, c) in moves
            else (r, c)
            for r, c in mine
        ]
        foods = [
            f
            for f in foods
            if min(abs(f[0] - m[0]) + abs(f[1] - m[1]) for m in mine) > 1
        ]
        foes = [((r + 1) % rows, c) for r, c in foes]
    assert time.perf_counter() - start < 5.0
    assert foods == []
    assert (27, 27) in bot.hills


def test_zero_time_breaks_cleanly() -> None:
    fake = FakeAnts([(5, 5), (6, 6)], [(0, 0)], [(10, 10)])
    fake.time_remaining = lambda: 0  # type: ignore[method-assign]
    bot = G.Greedy13()
    bot.do_turn(fake)


def test_ant_never_camps_home_hill() -> None:
    orders, _ = run_turn([(3, 3)], [], my_hills=[(3, 3)])
    assert orders
    loc, direction = orders[0]
    assert FakeAnts([(3, 3)], []).destination(loc, direction) != (3, 3)


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
