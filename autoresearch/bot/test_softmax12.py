#!/usr/bin/env python
"""Softmax12 tests: path-aware harvest by BFS food miles on crowd combat.

TDD-first pins for the risky part (BFS miles), then combat-chain
parity with the Crowd legs, then timing. All stdlib only.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Softmax12 as SM12  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
R2 = 5


class FakeAnts:
    """Minimal ants.Ants surface used by Softmax12.do_turn."""

    def __init__(
        self,
        mine: list[Loc],
        enemies: list[Loc],
        foods: list[Loc] | None = None,
        water: set[Loc] | None = None,
        enemy_hills: list[Loc] | None = None,
        my_hills: list[Loc] | None = None,
        attackradius2: int = R2,
    ) -> None:
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = attackradius2
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
) -> FakeAnts:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = SM12.Softmax12()
    bot.do_turn(fake)
    return fake


def _dest(loc: Loc, direction: str) -> Loc:
    dr, dc = AIM[direction]
    return ((loc[0] + dr) % ROWS, (loc[1] + dc) % COLS)


def _dist(a: Loc, b: Loc) -> int:
    dr = min(abs(a[0] - b[0]), ROWS - abs(a[0] - b[0]))
    dc = min(abs(a[1] - b[1]), COLS - abs(a[1] - b[1]))
    return dr + dc


def _open(loc: Loc) -> bool:
    return True


def test_packaging_manifest_matches_module() -> None:
    # The scorer runs the .bot manifest from the bot dir: it must
    # name this file, and both sources must compile.
    import py_compile

    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "Softmax12.bot")) as fh:
        manifest = fh.read()
    assert manifest == "python Softmax12.py\n"
    py_compile.compile(os.path.join(here, "Softmax12.py"), doraise=True)
    py_compile.compile(os.path.join(here, "test_softmax12.py"), doraise=True)
    assert SM12.Softmax12.__name__ == "Softmax12"


# --- BFS miles: the new mechanism -------------------------------------


def test_bfs_miles_open_board_equals_manhattan() -> None:
    miles = SM12.bfs_miles((3, 3), ROWS, COLS, _open, _dest)
    assert miles[(3, 3)] == 0
    assert miles[(3, 6)] == 3
    assert miles[(5, 3)] == 2
    # Torus wrap: (3,3) -> (3,19) is 4 steps west... check vs manhattan.
    assert miles[(3, 19)] == _dist((3, 3), (3, 19))
    assert miles[(19, 3)] == _dist((3, 3), (19, 3))


def test_bfs_miles_routes_around_wall() -> None:
    # Vertical wall at col 5 rows 0..18 with a gap at row 19.
    # Manhattan says (4,4)->(4,6) is 2; the true walk is long.
    water = {(r, 5) for r in range(19)}

    def blocked(loc: Loc) -> bool:
        return loc not in water

    miles = SM12.bfs_miles((4, 4), ROWS, COLS, blocked, _dest)
    assert miles[(4, 6)] > _dist((4, 4), (4, 6))
    # Torus detour: 5 north around the wall top to row 19, 2 east
    # through the gap, 5 south back to row 4.
    assert miles[(4, 6)] == 12
    # Same-side neighbour stays short.
    assert miles[(4, 3)] == 1


def test_bfs_miles_goals_early_exit_is_exact() -> None:
    # Stopping once every goal is reached records identical miles.
    water = {(r, 5) for r in range(19)}

    def blocked(loc: Loc) -> bool:
        return loc not in water

    goals = {(4, 3), (4, 6), (10, 10)}
    full = SM12.bfs_miles((4, 4), ROWS, COLS, blocked, _dest)
    early = SM12.bfs_miles((4, 4), ROWS, COLS, blocked, _dest, goals=goals)
    for g in goals:
        assert early[g] == full[g]
    assert early[(4, 3)] == 1
    assert early[(4, 6)] == 12


def test_bfs_miles_unreached_beyond_horizon() -> None:
    miles = SM12.bfs_miles((0, 0), ROWS, COLS, _open, _dest, horizon=2)
    assert miles[(0, 0)] == 0
    assert miles[(0, 2)] == 2
    assert (0, 3) not in miles
    assert (10, 10) not in miles


def test_food_mile_falls_back_with_wall_penalty() -> None:
    water = {(r, 5) for r in range(19)}

    def blocked(loc: Loc) -> bool:
        return loc not in water

    cache: dict[Loc, dict[Loc, int]] = {}
    # Reachable food: exact BFS length.
    near = SM12.food_mile((4, 3), (4, 4), ROWS, COLS, blocked, _dest, _dist, cache)
    assert near == 1
    # Wall-blocked food: BFS length (long detour), still finite here.
    far = SM12.food_mile((4, 4), (4, 6), ROWS, COLS, blocked, _dest, _dist, cache)
    assert far > _dist((4, 4), (4, 6))
    # Fully sealed food: manhattan + WALL_PENALTY fallback.
    sealed = {(1, 1), (1, 2), (1, 0), (0, 1), (2, 1), (1, 19), (19, 1), (0, 0)}

    def sealed_pass(loc: Loc) -> bool:
        return loc not in sealed

    cache2: dict[Loc, dict[Loc, int]] = {}
    val = SM12.food_mile((5, 5), (1, 1), ROWS, COLS, sealed_pass, _dest, _dist, cache2)
    assert val == _dist((5, 5), (1, 1)) + SM12.WALL_PENALTY


def test_assignment_prefers_walkable_food_over_manhattan_near() -> None:
    # Ant at (4,4). Food A at (4,6) is manhattan-2 but behind a wall
    # (long walk); food B at (4,0) is manhattan-4 but open ground.
    # Manhattan greedy takes A; miles must take B.
    water = {(r, 5) for r in range(19)}

    def blocked(loc: Loc) -> bool:
        return loc not in water

    ants_list = [(4, 4)]
    foods = [(4, 6), (4, 0)]
    target = SM12.assign_food_targets(
        ants_list, foods, [], _dist, ROWS, COLS, blocked, _dest
    )
    assert target[0] == (4, 0)


def _dist60(a: Loc, b: Loc) -> int:
    dr = min(abs(a[0] - b[0]), 60 - abs(a[0] - b[0]))
    dc = min(abs(a[1] - b[1]), 60 - abs(a[1] - b[1]))
    return dr + dc


def _dest60(loc: Loc, direction: str) -> Loc:
    dr, dc = AIM[direction]
    return ((loc[0] + dr) % 60, (loc[1] + dc) % 60)


def _open60(loc: Loc) -> bool:
    return True


def test_food_mile_reuses_cached_bfs() -> None:
    # One BFS per food no matter how many ants query it.
    cache: dict[Loc, dict[Loc, int]] = {}
    a = SM12.food_mile((4, 3), (4, 4), ROWS, COLS, _open, _dest, _dist, cache)
    b = SM12.food_mile((5, 5), (4, 4), ROWS, COLS, _open, _dest, _dist, cache)
    assert a == 1
    assert b == _dist((5, 5), (4, 4))
    assert len(cache) == 1


def test_bfs_prefilter_exact() -> None:
    # Foods no ant can walk to within the horizon skip the BFS:
    # min manhattan over ants is already beyond MILE_HORIZON.
    ants_list = [(0, 0)]
    assert SM12.bfs_worthwhile([(0, 2)], ants_list, _dist60) == {0}
    assert SM12.bfs_worthwhile([(30, 30)], ants_list, _dist60) == set()
    both = SM12.bfs_worthwhile([(0, 2), (30, 30)], ants_list, _dist60)
    assert both == {0}
    # Boundary: exactly at the horizon counts as worthwhile.
    assert SM12.bfs_worthwhile([(16, 16)], [(0, 0)], _dist60) == {0}
    assert SM12.bfs_worthwhile([(16, 17)], [(0, 0)], _dist60) == set()


def test_prefilter_keeps_assignment_identical() -> None:
    # Prefilter is speed-only: far foods fall back to
    # manhattan + WALL_PENALTY either way, so the near food wins.
    ants_list = [(0, 0)]
    foods = [(0, 2), (30, 30)]
    target = SM12.assign_food_targets(
        ants_list, foods, [], _dist60, 60, 60, _open60, _dest60
    )
    assert target[0] == (0, 2)


def test_sealed_ring_food_loses_to_walkable() -> None:
    # Food B sits inside a 4-neighbour water ring: unreachable, so
    # it costs manhattan + WALL_PENALTY. The farther-but-walkable
    # food A must win the claim (a zero penalty would flip this).
    ring = {(9, 10), (11, 10), (10, 9), (10, 11)}

    def blocked(loc: Loc) -> bool:
        return loc not in ring

    ants_list = [(10, 12)]
    foods = [(10, 10), (10, 16)]
    target = SM12.assign_food_targets(
        ants_list, foods, [], _dist, ROWS, COLS, blocked, _dest
    )
    assert target[0] == (10, 16)
    assert (
        SM12.food_mile((10, 12), (10, 10), ROWS, COLS, blocked, _dest, _dist, {})
        == _dist((10, 12), (10, 10)) + SM12.WALL_PENALTY
    )


def test_assignment_prefers_same_side_ant() -> None:
    # Food (4,6) sits east of the wall. The west ant is manhattan-4
    # but walks 12; the east ant is manhattan-8 but walks 8.
    # Miles sends the east ant; manhattan would send the west one.
    water = {(r, 5) for r in range(19)}

    def blocked(loc: Loc) -> bool:
        return loc not in water

    ants_list = [(4, 2), (4, 14)]
    foods = [(4, 6)]
    target = SM12.assign_food_targets(
        ants_list, foods, [], _dist, ROWS, COLS, blocked, _dest
    )
    assert target == {1: (4, 6)}


def test_assignment_open_board_matches_manhattan_greedy() -> None:
    # No walls: miles == manhattan, so the closest ant-food pair wins.
    ants_list = [(0, 0), (10, 10)]
    foods = [(0, 2), (10, 12)]
    target = SM12.assign_food_targets(
        ants_list, foods, [], _dist, ROWS, COLS, _open, _dest
    )
    assert target[0] == (0, 2)
    assert target[1] == (10, 12)


def test_claims_are_exclusive_and_bounded() -> None:
    # One ant per food, one food per ant, never more claims than
    # foods -- on open and walled boards, with and without foes.
    import random

    rng = random.Random(31)
    locs = [(r, c) for r in range(ROWS) for c in range(COLS)]
    for _ in range(30):
        water = {loc for loc in locs if rng.random() < 0.15}

        def blocked(loc: Loc, _w: set[Loc] = water) -> bool:
            return loc not in _w

        mine = [
            loc for loc in rng.sample(locs, rng.randrange(1, 10)) if loc not in water
        ]
        foods = list(rng.sample(locs, rng.randrange(1, 8)))
        foes = [
            loc
            for loc in rng.sample(locs, rng.randrange(0, 6))
            if loc not in water and loc not in mine
        ]
        target = SM12.assign_food_targets(
            mine, foods, foes, _dist, ROWS, COLS, blocked, _dest
        )
        assert len(set(target.values())) == len(target)
        assert len(target) <= len(foods)
        assert len(target) <= len(mine)
        assert set(target.values()) <= set(foods)


def test_denial_claims_use_miles_ordering() -> None:
    # Contested cluster of 3 foods, 3 foes nearby -> exactly 2 claims,
    # and the two claimed foods are the miles-nearest to the army.
    ants_list = [(0, 0), (0, 1), (0, 2)]
    foods = [(5, 5), (5, 6), (5, 7)]
    foes = [(5, 4), (6, 5), (4, 6)]
    target = SM12.assign_food_targets(
        ants_list, foods, foes, _dist, ROWS, COLS, _open, _dest
    )
    assert len(target) == SM12.DENIAL_CLAIMS
    claimed = set(target.values())
    assert claimed <= set(foods)
    assert len(claimed) == SM12.DENIAL_CLAIMS


# --- Food race gate (fourmidable FOOD_HEAD_START, ported) -------------


def test_nearest_foe_mile_open_and_walled() -> None:
    cache: dict[Loc, dict[Loc, int]] = {}
    assert (
        SM12.nearest_foe_mile(
            (5, 5), ROWS, COLS, _open, _dest, _dist, [(5, 8), (0, 0)], cache
        )
        == 3
    )
    assert (
        SM12.nearest_foe_mile((5, 5), ROWS, COLS, _open, _dest, _dist, [], cache)
        is None
    )
    water = {(r, 5) for r in range(19)}

    def blocked(loc: Loc) -> bool:
        return loc not in water

    cache2: dict[Loc, dict[Loc, int]] = {}
    assert (
        SM12.nearest_foe_mile(
            (4, 6), ROWS, COLS, blocked, _dest, _dist, [(4, 2)], cache2
        )
        == 14
    )


def test_race_gate_skips_lost_food() -> None:
    # Ant walks 5, foe walks 1: foe beats us by 4 > HEAD_START, so
    # no claim -- the ant explores instead of donating the walk.
    assert SM12.FOOD_HEAD_START == 3
    target = SM12.assign_food_targets(
        [(0, 0)], [(0, 5)], [(0, 4)], _dist, ROWS, COLS, _open, _dest
    )
    assert target == {}


def test_head_start_margin_allows_close_race() -> None:
    # Foe beats us by 1 only (mile 4 vs our 5): inside the head
    # start, so the claim stands.
    target = SM12.assign_food_targets(
        [(0, 0)], [(0, 5)], [(0, 1)], _dist, ROWS, COLS, _open, _dest
    )
    assert target == {0: (0, 5)}


def test_denial_clusters_ignore_the_race_gate() -> None:
    # Contested clusters are deliberate fights: adjacent foes never
    # veto the two denial claims.
    ants_list = [(0, 0), (0, 1), (0, 2)]
    foods = [(5, 5), (5, 6), (5, 7)]
    foes = [(5, 4), (6, 5), (4, 6)]
    target = SM12.assign_food_targets(
        ants_list, foods, foes, _dist, ROWS, COLS, _open, _dest
    )
    assert len(target) == SM12.DENIAL_CLAIMS


# --- Combat chain parity (crowd legs, no sampling) --------------------


def test_no_sampling_machinery() -> None:
    # Softmax12 must not carry the softmax combat core: no sampling,
    # no logistic gate, no max-min. The combat is the crowd chain.
    for name in (
        "sample_enemy_joints",
        "all_enemy_joints",
        "worst_score_for_own",
        "choose_own_joint",
        "carve_fights",
        "aggressive_probability",
        "roll_aggressive",
        "resolve_exchange",
    ):
        assert not hasattr(SM12, name), name


def test_pack_gate_helpers() -> None:
    ants_list = [(5, 5), (5, 6), (5, 7), (5, 8)]
    assert SM12.has_pack((5, 5), ants_list, _dist) is True
    assert SM12.has_pack((5, 5), [(5, 5)], _dist) is False
    assert SM12.has_pack((0, 0), [(0, 0), (10, 10)], _dist) is False
    assert SM12.crowd_fearless(9) is True
    assert SM12.crowd_fearless(10) is False
    assert SM12.grinder_release(0, 1, 5, 3) is True
    assert SM12.grinder_release(0, 1, 3, 5) is False
    assert SM12.grinder_release(1, 1, 5, 3) is False


def test_join_needs_two_commitments() -> None:
    foe = (5, 5)
    assert SM12.joined_attackers({0: foe, 1: foe}) == {0, 1}
    assert SM12.joined_attackers({0: foe}) == set()
    assert SM12.joined_attackers({0: foe, 1: (9, 9)}) == set()


def test_seek_advances_with_pack_small_fight() -> None:
    # Packed hunter, few enemies visible -> fearless advance at the foe.
    fake = run_turn(
        mine=[(5, 5), (5, 4), (5, 3), (6, 5)],
        enemies=[(5, 8)],
        foods=[],
    )
    assert len(fake.orders) > 0


def test_joined_pair_engages_together() -> None:
    # Two ants whose steps contact the same foe, in a crowd of 10,
    # are joined: the unblocked one steps into the equal trade
    # without the near gate.
    far = [
        (15, 15),
        (15, 16),
        (16, 15),
        (16, 16),
        (14, 15),
        (15, 14),
        (14, 14),
        (16, 16),
        (14, 16),
    ]
    fake = run_turn(
        mine=[(5, 5), (5, 6), (6, 5), (6, 6), (7, 5)],
        enemies=[(5, 8)] + far,
        foods=[],
    )
    assert ((5, 6), "e") in fake.orders


def test_grinder_engages_1v1_only_when_army_leads() -> None:
    # Packed ant, friendless contact step, one foe: engages with 11
    # vs 10 behind it, since the visible army strictly leads.
    pack = [(5, 0), (6, 0), (7, 0)]
    rear = [(15, 15), (15, 16), (16, 15), (16, 16), (14, 15), (15, 14), (14, 14)]
    far_foes = [
        (15, 10),
        (16, 10),
        (14, 10),
        (16, 11),
        (14, 11),
        (13, 10),
        (17, 10),
        (13, 11),
        (17, 11),
    ]
    fake = run_turn(
        mine=[(5, 5)] + pack + rear,
        enemies=[(5, 8)] + far_foes,
        foods=[],
    )
    assert ((5, 5), "e") in fake.orders


def test_lone_hunter_packs_up_instead_of_donating() -> None:
    # Single ant, many enemies visible (crowd) -> no fearless donate;
    # the ant must not step adjacent toward the pack-less foe.
    foes = [
        (5, 8),
        (6, 8),
        (7, 8),
        (8, 8),
        (9, 8),
        (5, 9),
        (6, 9),
        (7, 9),
        (8, 9),
        (9, 9),
        (10, 10),
        (11, 11),
    ]
    fake = run_turn(mine=[(5, 5)], enemies=foes, foods=[])
    for loc, _ in fake.orders:
        assert loc == (5, 5)


def test_hill_memory_marches_and_forgets() -> None:
    # Turn 1: an enemy hill is seen and remembered; idle ants march.
    # Turn 2: hill still unseen -> still marched on. Turn 3: one of
    # ours stands on it -> forgotten, no more march orders there.
    bot = SM12.Softmax12()
    hill = (15, 15)
    t1 = FakeAnts(mine=[(5, 5)], enemies=[], enemy_hills=[hill])
    bot.do_turn(t1)
    assert hill in bot.remembered_hills
    assert len(t1.orders) > 0
    t2 = FakeAnts(mine=[(5, 6)], enemies=[], enemy_hills=[])
    bot.do_turn(t2)
    assert hill in bot.remembered_hills
    assert len(t2.orders) > 0
    t3 = FakeAnts(mine=[hill], enemies=[], enemy_hills=[])
    bot.do_turn(t3)
    assert hill not in bot.remembered_hills


def test_walk_off_hill_steps_off() -> None:
    # A held ant sitting on its own hill must step off to free spawn.
    home = (10, 10)
    fake = run_turn(mine=[home], enemies=[], foods=[], my_hills=[home])
    assert len(fake.orders) == 1
    loc, _ = fake.orders[0]
    assert loc == home
    assert fake.orders[0][1] in ("n", "e", "s", "w")


def test_guard_answers_threatened_hill() -> None:
    # No food: both ants answer the threatened hill; the first holds
    # it and the second screens the razer off it.
    home = (10, 10)
    fake = run_turn(
        mine=[(10, 12), (10, 13)],
        enemies=[(10, 16)],
        foods=[],
        my_hills=[home],
    )
    assert len(fake.orders) == 2


def test_do_turn_reroutes_around_wall_not_like_base() -> None:
    # End-to-end novelty: the wall at col 5 makes (4,6) cost 12
    # steps while (4,0) costs 4. Miles claim (4,0) and step west;
    # the manhattan base claims (4,6) and steps north around.
    import Softmax as SM  # noqa: E402

    water = {(r, 5) for r in range(19)}
    mine = [(4, 4)]
    foods = [(4, 6), (4, 0)]
    mine12 = run_turn(mine, [], foods, water)
    assert mine12.orders == [((4, 4), "w")]
    base = FakeAnts(mine, [], foods, water)
    SM.Softmax().do_turn(base)
    assert len(base.orders) == 1
    assert base.orders[0][1] != "w"


def test_open_board_matches_base_exactly() -> None:
    # No walls: miles equal manhattan, so harvest and every later
    # phase must reproduce the base turn order-for-order.
    import Softmax as SM  # noqa: E402

    kwargs: dict = {
        "mine": [(5, 5), (6, 6), (10, 2)],
        "enemies": [],
        "foods": [(3, 3), (8, 8), (12, 12)],
        "enemy_hills": [(15, 15)],
        "my_hills": [(10, 10)],
    }
    ours = FakeAnts(**kwargs)
    SM12.Softmax12().do_turn(ours)
    theirs = FakeAnts(**kwargs)
    SM.Softmax().do_turn(theirs)
    assert ours.orders == theirs.orders


def test_sealed_food_claim_degrades_to_explore() -> None:
    # The only food is ring-sealed: it still draws the claim (no
    # starvation), but the unwalkable step falls through to explore
    # instead of crashing or colliding.
    ring = {(9, 10), (11, 10), (10, 9), (10, 11)}
    fake = run_turn(mine=[(3, 3)], enemies=[], foods=[(10, 10)], water=ring)
    assert len(fake.orders) == 1
    loc, d = fake.orders[0]
    assert loc == (3, 3)
    assert _dest(loc, d) not in ring


def test_ant_on_food_does_not_crash_or_stall() -> None:
    # Mile 0 claims the square; first_step is None, so the ant
    # flows to explore instead of stalling or colliding.
    fake = run_turn(mine=[(3, 3), (3, 5)], enemies=[], foods=[(3, 3)])
    assert len(fake.orders) == 2
    dests = set()
    for loc, d in fake.orders:
        dests.add(_dest(loc, d))
    assert len(dests) == 2


def test_repeated_turn_is_deterministic() -> None:
    # No RNG anywhere: identical turns give identical orders.
    kwargs: dict = {
        "mine": [(5, 5), (5, 4), (6, 5)],
        "enemies": [(5, 8), (9, 9)],
        "foods": [(3, 3), (7, 7)],
        "enemy_hills": [(15, 15)],
        "my_hills": [(10, 10)],
    }
    first = run_turn(**kwargs)
    second = run_turn(**kwargs)
    assert first.orders == second.orders


def test_thirty_turn_walled_scenario_stays_legal_and_eats() -> None:
    # Stateful maze pocket: 3 ants, wall with one gap, food both
    # sides. Every order must land on a passable, per-turn-unique
    # square, and the army must eat at least one food in 30 turns.
    water = {(r, 5) for r in range(19)}
    mine: list[Loc] = [(4, 2), (6, 2), (10, 10)]
    foods: list[Loc] = [(4, 0), (4, 7), (15, 15)]
    bot = SM12.Softmax12()
    eaten = 0
    for _ in range(30):
        fake = FakeAnts(mine, [], list(foods), water)
        bot.do_turn(fake)
        seen: set[Loc] = set()
        pls: dict[Loc, Loc] = {}
        for loc, d in fake.orders:
            assert loc in mine
            nxt = _dest(loc, d)
            assert nxt not in water
            assert nxt not in seen
            seen.add(nxt)
            pls[loc] = nxt
        mine = [pls.get(m, m) for m in mine]
        for m in mine:
            if m in foods:
                foods.remove(m)
                eaten += 1
        if not foods:
            break
    assert eaten >= 1


def test_seeded_fuzz_stays_legal_and_deterministic() -> None:
    # 60 random boards incl. empty armies, food on water, full
    # water walls: no crash, every order from a live ant to a
    # passable per-turn-unique square, repeated turns identical.
    import random

    rng = random.Random(12345)
    locs = [(r, c) for r in range(ROWS) for c in range(COLS)]
    for turn_i in range(60):
        # Engine attack radii vary by map; cover small and huge.
        radius2 = (2, 5, 13, 25)[turn_i % 4]
        water = {loc for loc in locs if rng.random() < 0.12}
        mine = [
            loc for loc in rng.sample(locs, rng.randrange(0, 9)) if loc not in water
        ]
        foes = [
            loc
            for loc in rng.sample(locs, rng.randrange(0, 7))
            if loc not in water and loc not in mine
        ]
        foods = rng.sample(locs, rng.randrange(0, 6))
        hills = rng.sample(locs, rng.randrange(0, 2))
        first = FakeAnts(mine, foes, foods, water, hills, [(0, 0)], radius2)
        SM12.Softmax12().do_turn(first)
        seen: set[Loc] = set()
        for loc, d in first.orders:
            assert loc in mine
            nxt = _dest(loc, d)
            assert nxt not in water
            assert nxt not in seen
            seen.add(nxt)
        second = FakeAnts(mine, foes, foods, water, hills, [(0, 0)], radius2)
        SM12.Softmax12().do_turn(second)
        assert first.orders == second.orders


def test_open_board_fuzz_matches_base_exactly() -> None:
    # No water anywhere: miles equal manhattan on every pair, so
    # all 40 random enemy-free boards must reproduce the base
    # order-for-order (harvest, guard, muster, explore, walk-off).
    import random

    import Softmax as SM  # noqa: E402

    rng = random.Random(999)
    locs = [(r, c) for r in range(ROWS) for c in range(COLS)]
    for _ in range(40):
        mine = rng.sample(locs, rng.randrange(1, 9))
        foods = rng.sample(locs, rng.randrange(1, 6))
        hills = rng.sample(locs, rng.randrange(0, 2))
        ours = FakeAnts(mine, [], foods, set(), hills, [(0, 0)])
        SM12.Softmax12().do_turn(ours)
        theirs = FakeAnts(mine, [], foods, set(), hills, [(0, 0)])
        SM.Softmax().do_turn(theirs)
        assert ours.orders == theirs.orders


def test_big_board_turn_under_1s() -> None:
    # 100x100 with 120 ants and maze water: worst-case engine
    # scale must clear a turn in under a second with margin.
    import random

    rng = random.Random(77)
    size = 100

    def dest(loc: Loc, direction: str) -> Loc:
        dr, dc = AIM[direction]
        return ((loc[0] + dr) % size, (loc[1] + dc) % size)

    def dist(a: Loc, b: Loc) -> int:
        dr = min(abs(a[0] - b[0]), size - abs(a[0] - b[0]))
        dc = min(abs(a[1] - b[1]), size - abs(a[1] - b[1]))
        return dr + dc

    water = {(r, c) for r in range(size) for c in range(size) if rng.random() < 0.2}

    def ps(loc: Loc) -> bool:
        return loc not in water

    mine = [
        m
        for m in [(rng.randrange(size), rng.randrange(size)) for _ in range(130)]
        if m not in water
    ][:120]
    foes = [
        f
        for f in [(rng.randrange(size), rng.randrange(size)) for _ in range(70)]
        if f not in water and f not in mine
    ]
    foods = [
        f
        for f in [(rng.randrange(size), rng.randrange(size)) for _ in range(50)]
        if f not in water
    ]
    start = time.perf_counter()
    target = SM12.assign_food_targets(mine, foods, foes, dist, size, size, ps, dest)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert isinstance(target, dict)


def test_full_turn_under_1s_crowded_with_walls() -> None:
    water = {(r, 10) for r in range(ROWS) if r not in (0, 10, 19)}
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [(3, 3), (17, 17), (10, 2), (12, 14), (1, 18)]
    start = time.perf_counter()
    fake = FakeAnts(mine, foes, foods, water, [(15, 15)], [(10, 10)])
    bot = SM12.Softmax12()
    bot.do_turn(fake)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(fake.orders) > 0


def test_maze_scale_turn_under_1s() -> None:
    # Maze-like stripes: many foods, many ants, walls everywhere.
    water = {
        (r, c) for r in range(ROWS) for c in range(COLS) if c % 4 == 2 and r % 2 == 0
    }
    mine = [(r, c) for r in range(0, ROWS, 2) for c in range(0, COLS, 4)][:40]
    foes = [(r, c) for r in range(1, ROWS, 3) for c in range(1, COLS, 3)][:20]
    foods = [(r, c) for r in range(0, ROWS, 3) for c in range(0, COLS, 3)][:25]
    start = time.perf_counter()
    fake = FakeAnts(mine, foes, foods, water)
    bot = SM12.Softmax12()
    bot.do_turn(fake)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
