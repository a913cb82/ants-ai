#!/usr/bin/env python
"""Ghost memory, posture, pack joins, and lead-pack discipline (Tables6).

Tables6 keeps the Tables core -- setup-precomputed battle tables with
pure-lookup contact verdicts -- and adds a mix no repo bot has:

1. Ghost memory (decaying last-known-enemy caution): an enemy seen
   last turn but gone now lingers GHOST_TTL turns; a candidate square
   within attack radius of a ghost counts +1 foe in the lookup, so
   the ant treats last-known contacts as live until the memory fades.
2. Army-posture trade gating (mode-switched table reading): ahead on
   visible ants the army is AGGRESSIVE (mutual TRADE goes anywhere),
   behind it is DEFENSIVE (even hill-covered TRADE refuses; only
   WIN/SAFE advance), tied it is EXCHANGE (the Tables hill gate).
   With no visible enemies the posture stays EXCHANGE so ghosts
   never get an aggressive free pass.
3. Pack-gated table joins: claim-free ants whose seek steps contact
   the same live foe commit on it, and 2+ committers engage every
   non-losing contact together (losing contacts always refuse).
4. Lead-pack discipline: a packless ahead seeker (fewer than
   PACK_NEED friends within PACK_RADIUS) packs up toward its nearest
   friend instead of dueling solo; tied and behind ants keep the
   Tables rules.
5. Small-fight press: a packed seeker presses non-losing contacts
   while fewer than SMALL_FIGHT_LIMIT enemies are visible, even
   without hill cover. Crowds keep full table safety, DEFENSIVE
   never presses, and LOSE never presses at any count.
6. Backed-trade near gate: a TRADE with BACKED_NEED+ friends within
   BACKED_RADIUS steps of the step advances at any posture.

Board economy (posture-scaled clustered denial food claims with
soft-cede of lost races), haunted-hill guard, muster, reinforce,
explore, and walk-off match the Tables base. Self-contained:
stdlib plus ants.py only.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Tables6 as T6  # noqa: E402

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
    bot: T6.Tables6 | None = None,
) -> tuple[list[tuple[Loc, str]], T6.Tables6]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    own = bot if bot is not None else T6.Tables6()
    own.do_turn(fake)
    return fake.orders, own


def test_table_grid_still_matches_focus_rule() -> None:
    table = T6.build_battle_table()
    assert table[(1, 1)] == T6.TRADE
    assert table[(2, 1)] == T6.WIN
    assert table[(1, 2)] == T6.LOSE
    assert table[(3, 3)] == T6.TRADE
    assert table[(1, 0)] == T6.SAFE
    assert T6.lookup_verdict(table, 100, 100) == T6.TRADE
    assert T6.lookup_verdict(table, 100, 1) == T6.WIN
    assert T6.lookup_verdict(table, 1, 100) == T6.LOSE


def test_posture_reads_army_parity() -> None:
    assert T6.posture(3, 1) == T6.AGGRESSIVE
    assert T6.posture(1, 3) == T6.DEFENSIVE
    assert T6.posture(2, 2) == T6.EXCHANGE
    # No visible enemies: never aggressive, so ghosts get no free pass.
    assert T6.posture(5, 0) == T6.EXCHANGE
    assert T6.posture(0, 0) == T6.EXCHANGE


def test_aggressive_trade_engages_far_from_hill() -> None:
    # Tables refuses this friendless 1v1 trade 19 steps from any
    # hill; Tables6 ahead 3v1 visible goes AGGRESSIVE and steps east.
    mine = [(5, 5), (0, 0), (0, 10)]
    foes = [(5, 8)]
    orders, _ = run_turn(mine, foes, my_hills=[(15, 15)])
    assert orders[0] == ((5, 5), "e")


def test_defensive_trade_refuses_under_hill() -> None:
    # The same duel 13 steps from a held hill would pass the Tables
    # hill gate; Tables6 behind 1v3 visible goes DEFENSIVE and the
    # seeker explores north instead of stepping east.
    mine = [(5, 5)]
    foes = [(5, 8), (19, 10), (0, 10)]
    orders, _ = run_turn(mine, foes, my_hills=[(12, 0)])
    assert orders == [((5, 5), "n")]
    assert ((5, 5), "e") not in orders


def test_tied_trade_keeps_hill_gate() -> None:
    # Tied 2v2 visible: EXCHANGE keeps the Tables rule -- engages
    # near the hill, refuses far from it.
    mine = [(5, 5), (0, 1)]
    foes = [(5, 8), (0, 10)]
    near, _ = run_turn(mine, foes, my_hills=[(12, 0)])
    assert near[0] == ((5, 5), "e")
    # (15, 0) is 16 steps from the duel square (no cover) and out
    # of threat range of both foes, so no guard interferes either.
    far, _ = run_turn(mine, foes, my_hills=[(15, 0)])
    assert far == [((5, 5), "n"), ((0, 1), "n")]


def test_win_advances_even_when_defensive() -> None:
    # DEFENSIVE only gates TRADE: a backed 2v1 WIN still steps east
    # with no hills held at all.
    mine = [(5, 5), (5, 4)]
    foes = [(5, 8), (0, 0), (0, 10), (10, 10)]
    orders, _ = run_turn(mine, foes)
    assert orders[0] == ((5, 5), "e")


def test_lose_refuses_even_when_aggressive() -> None:
    # AGGRESSIVE only releases TRADE: ours 1 vs 2 is LOSE and still
    # refuses while ahead on armies.
    mine = [(5, 5), (0, 0), (0, 1), (0, 2)]
    foes = [(5, 8), (6, 7)]
    orders, _ = run_turn(mine, foes)
    assert ((5, 5), "e") not in orders


def test_ghost_caution_blocks_empty_square() -> None:
    # Turn 1: duel visible, tied 1v1 far from hills -- refuses.
    # Turn 2: the foe vanishes; the ghost at (5, 8) still covers
    # (5, 6), so the ant keeps refusing east.
    bot = T6.Tables6()
    run_turn([(5, 5)], [(5, 8)], bot=bot)
    assert not bot.ghosts, "visible foes are live, never ghosts"
    run_turn([(5, 5)], [], bot=bot)
    assert bot.ghosts == {(5, 8): 1}
    orders, _ = run_turn([(5, 5)], [], bot=bot)
    assert ((5, 5), "e") not in orders


def test_ghost_expires_after_ttl() -> None:
    # After GHOST_TTL unseen turns the memory fades and the empty
    # square reads SAFE again: the ant may step east.
    bot = T6.Tables6()
    run_turn([(5, 5)], [(5, 8)], bot=bot)
    for _ in range(T6.GHOST_TTL):
        orders, _ = run_turn([(5, 5)], [], bot=bot)
        assert ((5, 5), "e") not in orders, "ghost still cautions"
    run_turn([(5, 5)], [], bot=bot)
    assert not bot.ghosts, "ghosts must expire after TTL turns"
    orders, _ = run_turn([(5, 5)], [], bot=bot)
    assert orders == [((5, 5), "n")]


def test_ghost_cleared_on_resight() -> None:
    # A ghost that reappears as a visible enemy is no longer a
    # ghost -- it is counted live, not double-counted.
    bot = T6.Tables6()
    run_turn([(5, 5)], [(5, 8)], bot=bot)
    run_turn([(5, 5)], [], bot=bot)
    assert bot.ghosts
    run_turn([(5, 5)], [(5, 8)], bot=bot)
    assert (5, 8) not in bot.ghosts


def test_matches_tables_on_calm_boards() -> None:
    # No ghosts linger and armies tie: EXCHANGE reads the Tables
    # hill gate, so food, guard, muster, and explore orders match
    # the base entry exactly on calm boards.
    import Tables as TB

    def tables_orders(
        mine: list[Loc],
        enemies: list[Loc],
        foods: list[Loc] | None = None,
        my_hills: list[Loc] | None = None,
        enemy_hills: list[Loc] | None = None,
    ) -> list[tuple[Loc, str]]:
        fake = FakeAnts(
            mine, enemies, foods, my_hills=my_hills, enemy_hills=enemy_hills
        )
        TB.Tables().do_turn(fake)
        return fake.orders

    mine = [(5, 5), (2, 2)]
    foods = [(5, 6), (2, 3)]
    orders, _ = run_turn(mine, [], foods)
    assert orders == tables_orders(mine, [], foods)
    lone, _ = run_turn([(10, 10)], [])
    assert lone == tables_orders([(10, 10)], [])
    guard, _ = run_turn(mine, [(5, 8), (0, 10)], my_hills=[(12, 0)])
    assert guard == tables_orders(mine, [(5, 8), (0, 10)], my_hills=[(12, 0)])
    muster, _ = run_turn([(10, 10)], [], enemy_hills=[(15, 15)])
    assert muster == tables_orders([(10, 10)], [], enemy_hills=[(15, 15)])


def test_defensive_packs_instead_of_exploring() -> None:
    # Behind 1v3 visible with no food, hills, or foes near: the
    # seeker cannot reach anyone, so Tables would explore north;
    # Tables6 DEFENSIVE packs one step toward its nearest friend.
    mine = [(5, 5), (5, 0)]
    foes = [(15, 15), (15, 16), (16, 15)]
    orders, _ = run_turn(mine, foes)
    assert ((5, 5), "w") in orders


def test_aggressive_still_explores() -> None:
    # Ahead with nothing to do: AGGRESSIVE keeps the Tables explore
    # (least-visited first, north on a fresh board), no packing.
    mine = [(5, 5), (5, 0)]
    foes = [(15, 15)]
    orders, _ = run_turn(mine, foes)
    assert ((5, 5), "n") in orders


def test_haunted_hill_stays_guarded() -> None:
    # Turn 1: a visible razer threatens the hill, the ant guards
    # east toward it. Turn 2: the razer vanishes, but its ghost
    # still haunts the hill -- the ant keeps guarding east instead
    # of wandering off to explore.
    bot = T6.Tables6()
    first, _ = run_turn([(10, 5)], [(10, 12)], my_hills=[(10, 10)], bot=bot)
    assert first == [((10, 5), "e")]
    second, _ = run_turn([(10, 5)], [], my_hills=[(10, 10)], bot=bot)
    assert second == [((10, 5), "e")]


def test_fresh_ghost_draws_investigation() -> None:
    # No hills, no food, no visible foes: turn 1 duels (and
    # refuses) far from cover; turn 2 the vanished foe's fresh
    # ghost draws one investigation step east instead of the
    # explore drift north.
    bot = T6.Tables6()
    run_turn([(10, 5)], [(10, 12)], bot=bot)
    orders, _ = run_turn([(10, 5)], [], bot=bot)
    assert orders == [((10, 5), "e")]


def test_stale_ghost_draws_no_investigation() -> None:
    # The same ghost at age 2+ no longer pulls: the ant resumes
    # exploring north.
    bot = T6.Tables6()
    run_turn([(10, 5)], [(10, 12)], bot=bot)
    run_turn([(10, 5)], [], bot=bot)
    run_turn([(10, 5)], [], bot=bot)
    assert bot.ghosts == {(10, 12): 2}
    orders, _ = run_turn([(10, 5)], [], bot=bot)
    assert orders == [((10, 5), "n")]


def _contested_board() -> tuple[
    list[Loc],
    list[Loc],
    list[Loc],
]:
    # Four foods in one cluster (within CLUSTER_R 8 of each other)
    # with three foes nearby: a contested denial cluster. Six ants
    # line up east of it.
    foods = [(10, 10), (10, 11), (11, 10), (11, 11)]
    foes = [(10, 13), (12, 10), (8, 10)]
    mine = [(10, 8), (10, 9), (10, 7), (10, 6), (10, 5), (10, 4)]
    return mine, foes, foods


def test_denial_claims_scale_with_posture() -> None:
    # The same contested cluster draws 3 claimants when ahead
    # (AGGRESSIVE press), 2 when tied (Tables rule), 1 when behind
    # (DEFENSIVE cede).
    mine, foes, foods = _contested_board()
    probe = FakeAnts(mine, foes, foods)
    assert (
        len(T6.denied_food_groups(foods, foes, probe.distance, probe.rows, probe.cols))
        == 1
    )
    many = T6.assign_food_targets(
        mine, foods, foes, probe.distance, probe.rows, probe.cols, claims=3
    )
    assert len(many) == 3
    tied = T6.assign_food_targets(
        mine[:4], foods, foes, probe.distance, probe.rows, probe.cols, claims=2
    )
    assert len(tied) == 2
    few = T6.assign_food_targets(
        mine, foods, foes, probe.distance, probe.rows, probe.cols, claims=1
    )
    assert len(few) == 1


def test_tied_trade_refuses_without_cover_or_pack() -> None:
    # Tied 2v2, no hills anywhere and no friend in attack radius of
    # the duel square: the bare TRADE keeps the Tables refusal and
    # the ant explores north. (A converging-backup release was
    # tried here and reverted after games showed it over-fed tied
    # 1v1s whenever armies clustered.)
    mine = [(5, 5), (5, 3)]
    foes = [(5, 8), (0, 10)]
    orders, _ = run_turn(mine, foes)
    assert ((5, 5), "e") not in orders


def test_investigation_beats_distant_foes() -> None:
    # A fresh ghost still pulls when the only visible foe is out of
    # seek range: the ant steps east toward the lead instead of
    # exploring north.
    bot = T6.Tables6()
    run_turn([(10, 5)], [(10, 12)], bot=bot)
    orders, _ = run_turn([(10, 5)], [(0, 0)], bot=bot)
    assert orders == [((10, 5), "e")]


def test_no_live_resolution_in_source() -> None:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Tables6.py")
    with open(path) as fh:
        source = fh.read()
    assert "weakness" not in source
    assert "import combat" not in source
    assert "from combat" not in source


def test_full_turn_crowded_under_1s() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(12)]
    foods = [((i * 3 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(10)]
    start = time.perf_counter()
    run_turn(mine, foes, foods, my_hills=[(0, 0)], enemy_hills=[(19, 19)])
    assert time.perf_counter() - start < 1.0


def test_per_decision_under_point1ms() -> None:
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


def test_packless_seeker_packs_up() -> None:
    # Ahead 2v1 visible (AGGRESSIVE) with a foe 3 steps east: Tables
    # and current Tables6 step east into the duel; pack-gated
    # Tables6 holds only one friend within 10 (needs two), so the
    # seeker packs one step west toward (5, 0) instead.
    mine = [(5, 5), (5, 0)]
    foes = [(5, 8)]
    orders, _ = run_turn(mine, foes)
    assert ((5, 5), "w") in orders
    assert ((5, 5), "e") not in orders


def test_packed_seeker_still_hunts() -> None:
    # Two friends within 10 steps: packed, so the AGGRESSIVE seeker
    # still steps east into the backed fight.
    mine = [(5, 5), (5, 4), (5, 3)]
    foes = [(5, 8)]
    orders, _ = run_turn(mine, foes)
    assert orders[0] == ((5, 5), "e")


def test_join_releases_converging_pair() -> None:
    # Tied 10v10 visible, no hills: a full crowd, so the small-fight
    # press stays off. (5, 4) and (5, 8) converge on (5, 6) from
    # opposite sides; each dest reads a friendless 1v1 TRADE, which
    # EXCHANGE refuses far from cover -- but both steps contact the
    # same foe, so the join releases them together.
    mine = [
        (5, 4),
        (5, 2),
        (5, 0),
        (5, 8),
        (5, 10),
        (5, 12),
        (15, 0),
        (15, 1),
        (16, 0),
        (16, 1),
    ]
    foes = [
        (5, 6),
        (15, 15),
        (15, 14),
        (15, 13),
        (14, 15),
        (14, 14),
        (0, 15),
        (0, 16),
        (0, 17),
        (0, 18),
    ]
    orders, _ = run_turn(mine, foes)
    assert ((5, 4), "e") in orders
    assert ((5, 8), "w") in orders


def test_lone_committer_stays_out() -> None:
    # Only one ant steps into contact with the foe: no join forms,
    # and ten enemies visible keep the small-fight press off, so the
    # tied far-from-cover TRADE still refuses.
    mine = [
        (5, 4),
        (5, 2),
        (5, 0),
        (0, 0),
        (0, 10),
        (10, 0),
        (15, 0),
        (15, 1),
        (16, 0),
        (16, 1),
    ]
    foes = [
        (5, 6),
        (15, 15),
        (15, 14),
        (15, 13),
        (14, 15),
        (14, 14),
        (0, 15),
        (0, 16),
        (0, 17),
        (0, 18),
    ]
    orders, _ = run_turn(mine, foes)
    assert ((5, 4), "e") not in orders


def test_join_never_releases_losing_fight() -> None:
    # Both committers read 2v3 LOSE at their dests (three foes
    # clustered, one backup each): joined but still refused.
    mine = [(5, 3), (3, 5), (5, 1), (5, 0), (1, 5), (0, 5)]
    foes = [(5, 5), (5, 6), (6, 5), (15, 15), (15, 14), (14, 15)]
    orders, _ = run_turn(mine, foes)
    assert ((5, 3), "e") not in orders
    assert ((3, 5), "s") not in orders


def test_join_overrides_lead_pack() -> None:
    # Ahead 3v2 visible, both seekers packless (one friend within 10
    # each): each step reads a solo TRADE, which lead-pack discipline
    # would turn into a regroup -- but both steps contact the same
    # foe, so the join releases them together instead.
    mine = [(5, 4), (5, 8), (15, 15)]
    foes = [(5, 6), (15, 0)]
    orders, _ = run_turn(mine, foes)
    assert ((5, 4), "e") in orders
    assert ((5, 8), "w") in orders


def test_helpers_are_pure_and_deterministic() -> None:
    probe = FakeAnts([(5, 5), (5, 4), (5, 3)], [(5, 8)])
    assert T6.has_pack((5, 5), [(5, 5), (5, 4), (5, 3)], probe.distance)
    assert not T6.has_pack((5, 5), [(5, 5), (5, 0)], probe.distance)
    assert not T6.has_pack((5, 5), [(5, 5)], probe.distance)
    assert T6.contact_foe((5, 6), [(5, 8)], lambda a, b: 0, 5) == (5, 8)
    assert T6.contact_foe((0, 0), [(5, 8)], lambda a, b: 100, 5) is None
    assert T6.joined_attackers({0: (1, 1), 1: (1, 1), 2: (3, 3)}) == {0, 1}
    assert T6.joined_attackers({0: (1, 1), 2: (3, 3)}) == set()


def test_water_blocks_join_without_crash() -> None:
    # A water wall between the seekers and the foe: no first step
    # exists, so no commitments form and both ants explore instead.
    water = {(4, 5), (5, 5), (6, 5), (4, 7), (5, 7), (6, 7)}
    mine = [(5, 4), (5, 8)]
    foes = [(5, 6), (0, 0), (0, 10), (10, 0), (10, 10), (19, 19)]
    orders, _ = run_turn(mine, foes, water=water)
    assert len(orders) == 2
    assert ((5, 4), "e") not in orders
    assert ((5, 8), "w") not in orders


def test_single_ant_full_turn_is_sane() -> None:
    # One ant, one hill, one food, one distant foe: the ant takes
    # the food step east and the turn completes with one order.
    orders, bot = run_turn([(5, 5)], [(15, 15)], [(5, 6)], my_hills=[(5, 5)])
    assert orders == [((5, 5), "e")]
    assert bot.prev_enemies == [(15, 15)]


def test_held_ant_walks_off_haunted_hill() -> None:
    # Ant on a home hill with no moves available except off: even
    # with a ghost watching, it must step off the hill square.
    bot = T6.Tables6()
    run_turn([(10, 10)], [(10, 12)], my_hills=[(10, 10)], bot=bot)
    orders, _ = run_turn(
        [(10, 10)], [], my_hills=[(10, 10)], water={(9, 10), (10, 9), (11, 10)}, bot=bot
    )
    assert orders == [((10, 10), "e")]


def test_fuzz_random_boards_stay_legal_and_fast() -> None:
    import random

    rng = random.Random(20261008)
    for _game in range(20):
        mine = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(12)]
        foes = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(8)]
        foods = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(6)]
        water = {(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(30)} - set(
            mine
        )
        hills = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(2)]
        bot = T6.Tables6()
        for _ in range(6):
            fake = FakeAnts(mine, foes, foods, water, my_hills=hills)
            start = time.perf_counter()
            bot.do_turn(fake)
            assert time.perf_counter() - start < 1.0
            seen: set[Loc] = set()
            for loc, _ in fake.orders:
                assert loc in mine
                dest = fake.destination(loc, _)
                assert dest not in water
                assert dest not in seen
                seen.add(dest)
            mine = [fake.destination(loc, d) for loc, d in fake.orders] + [
                m for m in mine if all(m != loc for loc, _ in fake.orders)
            ]


def test_small_fight_press_engages() -> None:
    # Tied 3v3 visible, no hills: (5, 5) holds two friends within 10
    # (packed) and reads a solo TRADE into (5, 6) with only three
    # foes on the board. Tables refuses the uncovered trade; Tables6
    # presses non-losing contacts in small fights and steps east.
    mine = [(5, 5), (5, 3), (5, 1)]
    foes = [(5, 8), (0, 10), (10, 10)]
    orders, _ = run_turn(mine, foes)
    assert ((5, 5), "e") in orders


def test_defensive_small_fight_refuses() -> None:
    # Behind 3v4 visible with the same packed geometry: DEFENSIVE
    # keeps refusing even in a small fight.
    mine = [(5, 5), (5, 3), (5, 1)]
    foes = [(5, 8), (0, 10), (0, 11), (10, 10)]
    orders, _ = run_turn(mine, foes)
    assert ((5, 5), "e") not in orders


def test_packed_ghost_draws_investigation() -> None:
    # Three packed ants duel a lone foe (aggressive) on turn 1; the
    # foe vanishes on turn 2. With no live enemies the small-fight
    # press has nothing to seek, so the lead ant investigates one
    # guarded step east toward the fresh ghost.
    bot = T6.Tables6()
    run_turn([(10, 5), (10, 4), (10, 3)], [(10, 12)], bot=bot)
    assert not bot.ghosts
    orders, _ = run_turn([(10, 5), (10, 4), (10, 3)], [], bot=bot)
    assert bot.ghosts == {(10, 12): 1}
    assert ((10, 5), "e") in orders


def test_cluster_lost_reads_race() -> None:
    # Lost when a foe reaches some cluster food strictly sooner than
    # any ant reaches any cluster food; ties and leads fight on.
    foods = [(10, 10), (10, 11)]
    probe = FakeAnts([(10, 4)], [(10, 12)], foods)
    assert T6.cluster_lost([0, 1], foods, [(10, 4)], [(10, 12)], probe.distance)
    assert not T6.cluster_lost([0, 1], foods, [(10, 9)], [(10, 12)], probe.distance)
    assert not T6.cluster_lost([0, 1], foods, [(10, 9)], [(10, 9)], probe.distance)


def test_lost_cluster_cedes_and_opens() -> None:
    # Three foes contest a two-food cluster but win the race (1 vs
    # 4): with one defensive claim the old code spends it on the
    # nearest ant and blocks the second food; Tables6 cedes the
    # cluster -- zero denial claimants -- and both ants gather fairly.
    mine = [(10, 4), (10, 6)]
    foes = [(10, 12), (11, 11), (9, 11)]
    foods = [(10, 10), (10, 11), (0, 0)]
    probe = FakeAnts(mine, foes, foods)
    assert len(T6.denied_food_groups(foods, foes, probe.distance, 20, 20)) == 1
    got = T6.assign_food_targets(
        mine, foods, foes, probe.distance, probe.rows, probe.cols, claims=1
    )
    assert got == {1: (10, 10), 0: (10, 11)}


def test_won_cluster_keeps_denial_block() -> None:
    # The same shape but an ant wins the race (1 vs 1 tie): the
    # cluster stays contested, so the single claim holds the nearest
    # food and the second stays blocked -- the other ant looks far.
    mine = [(10, 9), (10, 6)]
    foes = [(10, 12), (11, 11), (9, 11)]
    foods = [(10, 10), (10, 11), (0, 0)]
    probe = FakeAnts(mine, foes, foods)
    got = T6.assign_food_targets(
        mine, foods, foes, probe.distance, probe.rows, probe.cols, claims=1
    )
    assert got == {0: (10, 10), 1: (0, 0)}


def _backed_board() -> tuple[list[Loc], list[Loc]]:
    # Tied 12v12 crowd: the seeker (5, 2) duels (5, 5) with ten
    # friends 3-10 steps from its east step (5, 3) but none inside
    # attack range, so the dest reads a bare 1v1 TRADE far from cover.
    friends = [
        (5, 9),
        (5, 10),
        (5, 0),
        (4, 0),
        (6, 0),
        (1, 2),
        (9, 2),
        (0, 2),
        (10, 2),
        (3, 8),
    ]
    mine = [(5, 2)] + friends + [(15, 5)]
    foes = [
        (5, 5),
        (0, 15),
        (0, 16),
        (0, 17),
        (1, 15),
        (1, 16),
        (1, 17),
        (2, 15),
        (2, 16),
        (15, 0),
        (15, 1),
        (16, 0),
    ]
    return mine, foes


def test_backed_trade_engages_in_crowd() -> None:
    # Ten friends back the duel: Tables6 takes the uncovered TRADE
    # even in a full crowd, where the small-fight press stays off.
    mine, foes = _backed_board()
    orders, _ = run_turn(mine, foes)
    assert ((5, 2), "e") in orders


def test_backed_trade_needs_ten() -> None:
    # Nine backers is not a crowd: the same duel refuses.
    mine, foes = _backed_board()
    mine = [(15, 10) if m == (3, 8) else m for m in mine]
    orders, _ = run_turn(mine, foes)
    assert ((5, 2), "e") not in orders


def test_backed_by_counts_ring_not_self() -> None:
    probe = FakeAnts([(5, 2)], [])
    many = [(5, 2)] + [(5, (2 + i) % 20) for i in range(1, 12)]
    assert T6.backed_by((5, 3), (5, 2), many, probe.distance)
    assert not T6.backed_by((5, 3), (5, 2), many[:10], probe.distance)
    assert not T6.backed_by((5, 3), (5, 2), [(5, 2)], probe.distance)
