#!/usr/bin/env python
"""Ring (siege-ring hill assault over a pack-combat economy) tests.
No engine games.

Eight changes over Understudy. (1) Siege muster: when the army
musters on an enemy hill, only the challenger marches onto the
hill square itself; every other muster-bound ant takes a distinct
passable orthogonal neighbor of the hill (the siege ring, n/e/s/w)
instead of stacking behind the challenger, and an escort already
standing on its slot holds it only with backup (or fearless while
ahead on hills) -- a lone holder retreats. The next re-challenge
then starts one step away instead of a column away. (2) Pack
combat: claim-free ants hunt only with a pack (3+ friends within
10); packless ants pack up toward a friend, packed hunters press
small fights fearlessly and focus the pack's most popular prey,
pairs join committed attacks, friendless duels engage only while
ahead, extra guards screen razers at the halfway square, and
equal trades engage at 10 near friends.
(3) Garrison bravery for holders (see above). (4) Defender's
trade: the anchor holds its home hill on fair-or-better contact
but never suicides. (5) Local harvest: only food within FOOD_RADIUS
steps is claimed, so distant treks never scatter the pack --
except a deserted ant still races uncontested far food. (6) Muster
quorum: the siege marches only with challenger + escort and only
inside MUSTER_RADIUS steps, except a lone ant still races an open
hill (no enemy within RACE_RADIUS); farther hills wait for explore.
(7) Grave check: a remembered hill visibly empty is forgotten
instead of marched at. (8) Nearest-anchor drafting: each
threatened hill is held by its nearest claim-free ant.
Challenger rotation, denial, reinforce, and explore are unchanged.
"""

import os
import sys
import time
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Ring as RG  # noqa: E402
import Understudy as US1  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20


def torus(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


def open_passable(loc: Loc) -> bool:
    return True


class FakeAnts:
    def __init__(
        self,
        ants: list[Loc],
        foods: list[Loc],
        enemies: list[Loc],
        homes: list[Loc],
        hills: list[Loc],
        water: set[Loc] | None = None,
    ) -> None:
        self._ants = list(ants)
        self._foods = list(foods)
        self._enemies = list(enemies)
        self._homes = list(homes)
        self._hills = list(hills)
        self._water = set(water or set())
        self.rows = ROWS
        self.cols = COLS
        self.attackradius2 = 5
        self.turntime = 1000
        self.orders: list[tuple[Loc, str]] = []

    def food(self) -> list[Loc]:
        return list(self._foods)

    def my_ants(self) -> list[Loc]:
        return list(self._ants)

    def enemy_ants(self) -> list[tuple[Loc, int]]:
        return [(e, 1) for e in self._enemies]

    def enemy_hills(self) -> list[tuple[Loc, int]]:
        return [(h, 1) for h in self._hills]

    def my_hills(self) -> list[Loc]:
        return list(self._homes)

    def distance(self, a: Loc, b: Loc) -> int:
        return torus(a, b)

    def destination(self, loc: Loc, direction: str) -> Loc:
        r, c = loc
        if direction == "n":
            return ((r - 1) % ROWS, c)
        if direction == "s":
            return ((r + 1) % ROWS, c)
        if direction == "e":
            return (r, (c + 1) % COLS)
        return (r, (c - 1) % COLS)

    def passable(self, loc: Loc) -> bool:
        assert 0 <= loc[0] < ROWS and 0 <= loc[1] < COLS
        return loc not in self._water

    def unoccupied(self, loc: Loc) -> bool:
        assert 0 <= loc[0] < ROWS and 0 <= loc[1] < COLS
        return loc not in self._ants and loc not in self._enemies

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 10000


def run_turn(
    bot: Any,
    ants: list[Loc],
    hills: list[Loc],
    homes: list[Loc],
    water: set[Loc] | None = None,
    enemies: list[Loc] | None = None,
) -> FakeAnts:
    fake = FakeAnts(ants, [], enemies or [], homes, hills, water)
    bot.do_turn(cast(Any, fake))
    return fake


def moved_to(fake: FakeAnts, origin: Loc) -> Loc:
    for o, d in fake.orders:
        if o == origin:
            return fake.destination(o, d)
    raise AssertionError(f"ant {origin} issued no order")


H1: Loc = (10, 5)
H2: Loc = (19, 19)
HOME: list[Loc] = [(10, 15)]
A: Loc = (10, 10)
B: Loc = (0, 0)


def fresh_bot() -> Any:
    bot = RG.Ring()
    bot.do_setup(cast(Any, FakeAnts([], [], [], [], [])))
    return bot


def test_siege_slots_are_orthogonal_neighbors_in_order() -> None:
    assert RG.siege_slots(H1, open_passable, ROWS, COLS) == [
        (9, 5),
        (10, 6),
        (11, 5),
        (10, 4),
    ]


def test_siege_slots_wrap_around_edges() -> None:
    assert RG.siege_slots((0, 0), open_passable, ROWS, COLS) == [
        (19, 0),
        (0, 1),
        (1, 0),
        (0, 19),
    ]


def test_siege_slots_skip_water() -> None:
    water = {(9, 5), (11, 5)}
    assert RG.siege_slots(H1, lambda loc: loc not in water, ROWS, COLS) == [
        (10, 6),
        (10, 4),
    ]
    assert RG.siege_slots(H1, lambda loc: False, ROWS, COLS) == []


def test_siege_slots_skip_self_on_thin_board() -> None:
    # A 1-row board folds n/s back onto the hill itself: no escort
    # should target the hill square as a ring slot.
    assert RG.siege_slots((0, 5), open_passable, 1, COLS) == [
        (0, 6),
        (0, 4),
    ]


def test_pick_siege_goal_challenger_gets_hill() -> None:
    slots = RG.siege_slots(H1, open_passable, ROWS, COLS)
    assert RG.pick_siege_goal(A, H1, A, slots, set(), set(), torus) == H1
    # Even standing on a slot, the challenger still marches.
    assert RG.pick_siege_goal((9, 5), H1, (9, 5), slots, set(), set(), torus) == H1


def test_pick_siege_goal_escorts_take_nearest_distinct_slots() -> None:
    slots = RG.siege_slots(H1, open_passable, ROWS, COLS)
    claimed: set[Loc] = set()
    # Each escort draws its own nearest free slot, never doubling
    # up; ties keep ring order.
    first = RG.pick_siege_goal((10, 12), H1, A, slots, claimed, set(), torus)
    assert first == (10, 6)
    claimed.add(first)
    second = RG.pick_siege_goal((8, 5), H1, A, slots, claimed, set(), torus)
    assert second == (9, 5)
    claimed.add(second)
    third = RG.pick_siege_goal((12, 5), H1, A, slots, claimed, set(), torus)
    assert third == (11, 5)
    claimed.add(third)
    fourth = RG.pick_siege_goal((10, 0), H1, A, slots, claimed, set(), torus)
    assert fourth == (10, 4)


def test_pick_siege_goal_falls_back_to_hill_when_ring_full() -> None:
    slots = RG.siege_slots(H1, open_passable, ROWS, COLS)
    claimed = set(slots)
    assert RG.pick_siege_goal(B, H1, A, slots, claimed, set(), torus) == H1
    assert RG.pick_siege_goal(B, H1, A, [], set(), set(), torus) == H1


def test_pick_siege_goal_skips_held_squares() -> None:
    # Slots held by other ants are skipped -- marching at an
    # occupied square only collides -- but an ant never skips
    # the square it stands on itself.
    slots = RG.siege_slots(H1, open_passable, ROWS, COLS)
    assert RG.pick_siege_goal((8, 5), H1, A, slots, set(), set(), torus) == (9, 5)
    assert RG.pick_siege_goal((8, 5), H1, A, slots, set(), {(9, 5)}, torus) == (
        10,
        6,
    )
    assert RG.pick_siege_goal((9, 5), H1, A, slots, set(), {(9, 5)}, torus) == (
        9,
        5,
    )


def test_challenger_still_marches_hill_first() -> None:
    bot = fresh_bot()
    turn1 = run_turn(bot, [A, B], [H1], HOME)
    assert turn1.orders[0] == (A, "w")
    assert bot.last_challenger.get(H1) == A


def test_escort_on_slot_holds_station() -> None:
    # A challenges from (10, 6); B already stands on the (9, 5)
    # slot. Stacking would march B onto the hill ('s'); the ring
    # holds B in place so the re-challenge starts adjacent.
    bot = fresh_bot()
    turn = run_turn(bot, [(10, 6), (9, 5)], [H1], HOME)
    assert turn.orders == [((10, 6), "w")]


def test_escort_off_slot_steps_toward_free_slot() -> None:
    # A challenges; B at (8, 5) has (9, 5) as nearest free slot
    # and steps onto it ('s'), same square stacking would pass
    # through -- but B claims the slot instead of the hill.
    bot = fresh_bot()
    turn = run_turn(bot, [(10, 6), (8, 5)], [H1], HOME)
    assert ((10, 6), "w") in turn.orders
    assert ((8, 5), "s") in turn.orders


def test_two_escorts_hold_distinct_slots() -> None:
    # Three ants equidistant from H1: list order makes A the
    # challenger while B and C each hold their own slots.
    # Stacking would march all three at the hill.
    bot = fresh_bot()
    turn = run_turn(bot, [(10, 6), (9, 5), (10, 4)], [H1], HOME)
    assert turn.orders == [((10, 6), "w")]


def test_latecomer_does_not_evict_holder() -> None:
    # A challenges; H already holds the (9, 5) slot; E arrives
    # with (9, 5) as its nearest free square. E must take another
    # slot instead of evicting H, so H holds station while A
    # marches the hill.
    bot = fresh_bot()
    turn = run_turn(bot, [(10, 6), (9, 6), (9, 5)], [H1], FAR_HOME)
    assert ((10, 6), "w") in turn.orders
    assert (9, 5) not in [o for o, _ in turn.orders]


def test_empty_army_and_unknown_challenger_hold_no_orders() -> None:
    # No ants: the turn is a no-op and challenger stays None.
    # A None challenger still routes every ant to a slot or hill.
    bot = fresh_bot()
    turn = run_turn(bot, [], [H1], HOME)
    assert turn.orders == []
    assert bot.last_challenger == {}
    slots = RG.siege_slots(H1, open_passable, ROWS, COLS)
    assert RG.pick_siege_goal(A, H1, None, slots, set(), set(), torus) == (10, 6)
    assert RG.pick_siege_goal(A, H1, None, [], set(), set(), torus) == H1


def run_both(
    ants: list[Loc],
    foods: list[Loc],
    enemies: list[Loc],
    homes: list[Loc],
    hills: list[Loc],
    turns: int = 3,
    water: set[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], list[tuple[Loc, str]]]:
    # One turn from each bot on identical boards. FakeAnts takes
    # foods, so build it directly instead of via run_turn. Repeat
    # turns on the static board so visits and headings evolve too.
    old = US1.Understudy()
    old.do_setup(cast(Any, FakeAnts([], [], [], [], [])))
    new = RG.Ring()
    new.do_setup(cast(Any, FakeAnts([], [], [], [], [])))
    old_orders: list[tuple[Loc, str]] = []
    new_orders: list[tuple[Loc, str]] = []
    for _ in range(turns):
        fake_old = FakeAnts(ants, foods, enemies, homes, hills, water)
        fake_new = FakeAnts(ants, foods, enemies, homes, hills, water)
        old.do_turn(cast(Any, fake_old))
        new.do_turn(cast(Any, fake_new))
        old_orders.extend(fake_old.orders)
        new_orders.extend(fake_new.orders)
    return old_orders, new_orders


def test_no_hill_turns_match_understudy() -> None:
    # Without enemy hills the siege branch never runs, and with
    # no live contact the combat branch stays quiet: food,
    # explore, and walk-off must issue byte-identical orders.
    # Guard and seek divergence is pinned by dedicated tests.
    scenarios: list[tuple[list[Loc], list[Loc], list[Loc], list[Loc], list[Loc]]] = [
        ([A, B], [(5, 5), (15, 15)], [(12, 5), (3, 3)], HOME, []),
        ([A, B], [], [(0, 10)], HOME, []),
        ([(10, 15)], [], [], HOME, []),
        ([A, B], [(0, 1)], [], HOME, []),
    ]
    for ants, foods, enemies, homes, hills in scenarios:
        old_orders, new_orders = run_both(ants, foods, enemies, homes, hills)
        assert new_orders == old_orders


def test_quiet_boards_match_understudy() -> None:
    # Broad parity sweep: 25 seeded boards with no hills and every
    # foe far from ants (>8) and home (>10) must issue byte-identical
    # orders. Divergence may only come from live contact, threats,
    # or hills -- never from quiet economy/explore drift.
    import random

    count = 0
    for seed in range(300):
        rng = random.Random(seed)
        ants = list({(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(3)})
        foods = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(3)]
        foes = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(1)]
        if min(torus(a, f) for a in ants for f in foes) <= 8:
            continue
        if min(torus((0, 10), f) for f in foes) <= 10:
            continue
        water = {(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(8)} - set(
            ants
        )
        old_orders, new_orders = run_both(ants, foods, foes, HOME, [], 1, water)
        assert new_orders == old_orders
        count += 1
        if count >= 25:
            break
    assert count == 25


def test_water_ring_turns_match_understudy() -> None:
    # A water-sealed ring is empty, so the siege falls back to
    # classic stacking: even with a live hill, orders match
    # Understudy byte-for-byte across evolving turns.
    water = {(9, 5), (10, 6), (11, 5), (10, 4)}
    old_orders, new_orders = run_both([A, B], [], [], HOME, [H1], 3, water)
    assert new_orders == old_orders
    assert len(new_orders) > 0


def test_water_ring_falls_back_to_stacking() -> None:
    # Water on all four neighbors empties the ring: nobody holds
    # a slot, so both ants march the hill itself (A routes around
    # the water) exactly like Understudy.
    water = {(9, 5), (10, 6), (11, 5), (10, 4)}
    bot = fresh_bot()
    turn = run_turn(bot, [A, B], [H1], HOME, water)
    assert {o for o, _ in turn.orders} == {A, B}


FAR_HOME: list[Loc] = [(0, 10)]


def test_ring_holds_while_challenger_is_blocked() -> None:
    # A defender sits on H1 so the hill never falls: turn 1 the
    # tied challenger A is blocked onto the hill and jostles for
    # another angle while escort B holds its slot; turn 2 A sits
    # out (failed) and B -- already adjacent -- takes over as
    # challenger. Homes sit far away so no guard branch fires.
    bot = fresh_bot()
    turn1 = run_turn(bot, [(10, 6), (9, 5)], [H1], FAR_HOME, None, [H1])
    assert turn1.orders == [((10, 6), "n")]
    turn2 = run_turn(bot, [(9, 6), (9, 5)], [H1], FAR_HOME, None, [H1])
    assert bot.last_challenger.get(H1) == (9, 5)
    assert {o for o, _ in turn2.orders} == {(9, 6), (9, 5)}


def test_failed_challenge_rotates_with_ring() -> None:
    # Turn 1: nearest ant A challenges H1. Turn 2: H1 still held,
    # so A sits out and B becomes the challenger instead; the
    # ring must not send the excluded ant back at the hill.
    bot = fresh_bot()
    turn1 = run_turn(bot, [A, B], [H1], HOME)
    assert turn1.orders[0] == (A, "w")
    assert bot.last_challenger.get(H1) == A
    ants2 = [moved_to(turn1, A), moved_to(turn1, B)]
    assert ants2[0] == (10, 9)
    turn2 = run_turn(bot, ants2, [H1], HOME)
    assert bot.last_challenger.get(H1) == ants2[1]
    assert (ants2[0], "w") not in turn2.orders
    assert (ants2[0], "n") in turn2.orders


def test_excluded_challenger_reinforces_second_hill() -> None:
    # Two hills: after A fails on H1 and sits out, A usefully
    # marches H2 (reinforce) instead of idling or re-challenging.
    bot = fresh_bot()
    turn1 = run_turn(bot, [A, B], [H1, H2], HOME)
    assert bot.last_challenger.get(H1) == A
    ants2 = [moved_to(turn1, A), moved_to(turn1, B)]
    turn2 = run_turn(bot, ants2, [H1, H2], HOME)
    assert bot.last_challenger.get(H1) == ants2[1]
    assert ants2[0] in [o for o, _ in turn2.orders]
    assert (ants2[0], "w") not in turn2.orders


def test_escort_becomes_challenger_after_failed_challenge() -> None:
    # Turn 1: lone A challenges H1 and steps to (10, 9). Turn 2:
    # A failed and sits out, so an ant already adjacent to the
    # hill -- where the ring keeps escorts -- becomes challenger
    # and re-challenges in one step ('s' onto the hill).
    bot = fresh_bot()
    turn1 = run_turn(bot, [A], [H1], HOME)
    assert turn1.orders == [(A, "w")]
    turn2 = run_turn(bot, [(10, 9), (9, 5)], [H1], HOME)
    assert bot.last_challenger.get(H1) == (9, 5)
    assert ((9, 5), "s") in turn2.orders
    assert ((10, 9), "w") not in turn2.orders


def test_single_ant_keeps_challenging() -> None:
    bot = fresh_bot()
    turn1 = run_turn(bot, [A], [H1], HOME)
    assert turn1.orders == [(A, "w")]
    turn2 = run_turn(bot, [(10, 9)], [H1], HOME)
    assert ((10, 9), "w") in turn2.orders
    assert bot.last_challenger.get(H1) == (10, 9)


def test_bot_runs_on_real_parsed_board() -> None:
    # Through the real ants.py parser (not the Fake): setup plus
    # ten turns on a water-dotted board with food, both hills,
    # and an enemy marching on our hill. Every turn must issue
    # orders quickly and without raising, while headings,
    # threatened-hill, screen, seek, siege, rotation, and
    # remembered-hill state all evolve through the real path.
    import ants as ants_mod  # noqa: E402

    engine = ants_mod.Ants()
    engine.setup(
        "turn 0\nturns 200\nrows 20\ncols 20\nloadtime 2000\n"
        "turntime 1000\nviewradius2 93\nattackradius2 5\n"
        "spawnradius2 1\nplayer_seed 42\n"
    )
    bot = RG.Ring()
    bot.do_setup(engine)
    orders: list[tuple[Loc, str]] = []
    engine.issue_order = orders.append
    start = time.perf_counter()
    for turn in range(10):
        foe_row = 12 - turn // 2
        engine.update(
            f"f 5 5\nw 9 5\na 10 10 0\na 8 5 0\nh 10 15 0\nh 10 5 1\na {foe_row} 5 1\n"
        )
        assert engine.time_remaining() > 0
        bot.do_turn(engine)
    assert time.perf_counter() - start < 3.0
    assert len(orders) > 0


def test_ring_helpers_cost_under_half_a_ms() -> None:
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(120)]
    slots = RG.siege_slots(H1, open_passable, ROWS, COLS)
    occupied = set(ants)
    n = 2000
    start = time.perf_counter()
    for _ in range(n):
        claimed: set[Loc] = set()
        for ant in ants:
            goal = RG.pick_siege_goal(ant, H1, ants[0], slots, claimed, occupied, torus)
            if goal != H1:
                claimed.add(goal)
    assert (time.perf_counter() - start) / n < 0.0005


def test_crowded_board_turn_stays_fast() -> None:
    bot = fresh_bot()
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(120)]
    run_turn(bot, ants, [H1], HOME)
    ants2 = ants[:]
    start = time.perf_counter()
    run_turn(bot, ants2, [H1, H2], HOME)
    assert time.perf_counter() - start < 1.0


# --- Ring + pack combat (new mix): failing first, then the code. ---


def test_ring_nearest_foe_only_within_eight() -> None:
    assert RG.ring_nearest_foe(A, [(10, 12)], torus) == (10, 12)
    assert RG.ring_nearest_foe(A, [(10, 19)], torus) is None
    assert RG.ring_nearest_foe(A, [], torus) is None
    # Nearest wins; ties keep list order.
    assert RG.ring_nearest_foe(A, [(10, 12), (10, 8)], torus) == (10, 12)
    assert RG.ring_nearest_foe(A, [(10, 8), (10, 12)], torus) == (10, 8)


def test_ring_pack_needs_three_friends_within_ten() -> None:
    assert RG.ring_has_pack(A, [A, (10, 11), (10, 12), (10, 13)], torus) is True
    assert RG.ring_has_pack(A, [A, (10, 11), (10, 12)], torus) is False
    assert RG.ring_has_pack(A, [A], torus) is False
    # Far friends do not count.
    assert RG.ring_has_pack(A, [A, (0, 0), (0, 1), (0, 2)], torus) is False


def test_ring_join_releases_pairs_only() -> None:
    assert RG.ring_joined({0: (5, 5), 1: (5, 5), 2: (7, 7)}) == {0, 1}
    assert RG.ring_joined({0: (5, 5), 1: (7, 7)}) == set()
    assert RG.ring_joined({}) == set()


def test_ring_grinder_releases_ahead_duels_only() -> None:
    assert RG.ring_grinder_release(0, 1, 5, 3) is True
    assert RG.ring_grinder_release(0, 1, 3, 5) is False
    assert RG.ring_grinder_release(0, 1, 3, 3) is False
    assert RG.ring_grinder_release(1, 1, 5, 3) is False
    assert RG.ring_grinder_release(0, 2, 5, 3) is False


def test_ring_fearless_only_in_small_fights() -> None:
    assert RG.ring_fearless(0) is True
    assert RG.ring_fearless(9) is True
    assert RG.ring_fearless(10) is False
    assert RG.ring_fearless(40) is False


def test_ring_contact_foe_is_nearest_in_range() -> None:
    # Nearest enemy within attack range of the planned step, else
    # None. The step's fight queues as a pack commitment on it.
    foes = [(10, 5), (10, 7)]
    assert RG.ring_contact_foe((10, 6), foes, torus_sq, 5) == (10, 5)
    assert RG.ring_contact_foe((10, 6), [(10, 7)], torus_sq, 5) == (10, 7)
    assert RG.ring_contact_foe((0, 0), foes, torus_sq, 5) is None
    assert RG.ring_contact_foe((10, 6), [], torus_sq, 5) is None


def test_ring_share_prey_converges_trios() -> None:
    # Two hunters on F1, one on F2, all mates: the odd hunter
    # adopts F1 (3v1 popularity), so the pack focuses fire.
    ants = [(10, 9), (10, 10), (10, 13)]
    prey = {0: (10, 8), 1: (10, 8), 2: (10, 14)}
    assert RG.ring_share_prey(prey, ants, torus) == {
        0: (10, 8),
        1: (10, 8),
        2: (10, 8),
    }


def test_ring_share_prey_keeps_pairs_and_far() -> None:
    # 1-1 split: each hunter keeps its own (own vote ties). A
    # mate's prey beyond SEEK_RANGE is never adopted, and prey
    # for unknown ants passes through untouched.
    ants = [(10, 9), (10, 13)]
    prey = {0: (10, 8), 1: (10, 14)}
    assert RG.ring_share_prey(prey, ants, torus) == prey
    # An artificial far "prey" still keeps its vote: ties hold
    # the status quo, so only strict majorities flip hunters.
    far = {0: (10, 8), 1: (0, 0)}
    assert RG.ring_share_prey(far, [(10, 9), (10, 10)], torus) == far
    assert RG.ring_share_prey({}, ants, torus) == {}


def test_packed_trio_focuses_one_foe() -> None:
    # P3's nearest foe is F2 east, but the pack hunts F1: P3
    # joins the focus west instead of dueling east alone.
    bot = fresh_bot()
    pack = [(10, 9), (10, 10), (10, 13), (10, 11)]
    turn = run_turn(bot, pack, [], FAR_HOME, None, [(10, 8), (10, 14)])
    assert ((10, 13), "w") in turn.orders
    assert ((10, 13), "e") not in turn.orders


def test_ring_intercept_is_halfway_square() -> None:
    mid = RG.ring_intercept((10, 15), [(10, 5)], torus, open_passable, ROWS, COLS)
    assert mid == (10, 10)
    assert RG.ring_intercept((10, 15), [], torus, open_passable, ROWS, COLS) is None


def test_packless_hunter_packs_up_instead_of_advancing() -> None:
    # Lone ant with a foe 5 west but no pack: must not step at the
    # foe. Packing up toward its friend (wrap-east, away from the
    # foe) or holding still are both fine; advancing west is not.
    bot = fresh_bot()
    turn = run_turn(bot, [(10, 10), (10, 0)], [], FAR_HOME, None, [(10, 5)])
    assert ((10, 10), "w") not in turn.orders
    for o, d in turn.orders:
        if o == (10, 10):
            assert torus(fake_dest(o, d), (10, 5)) >= torus(o, (10, 5))


def test_packed_hunters_press_small_fight() -> None:
    # Four packed ants with one foe in range: at least one hunter
    # steps toward the foe instead of exploring away.
    bot = fresh_bot()
    pack = [(10, 10), (10, 11), (10, 12), (10, 13)]
    turn = run_turn(bot, pack, [], FAR_HOME, None, [(10, 5)])
    dests = {fake_dest(o, d) for o, d in turn.orders}
    assert any(torus(d, (10, 5)) < torus((10, 10), (10, 5)) for d in dests)


def fake_dest(origin: Loc, direction: str) -> Loc:
    r, c = origin
    if direction == "n":
        return ((r - 1) % ROWS, c)
    if direction == "s":
        return ((r + 1) % ROWS, c)
    if direction == "e":
        return (r, (c + 1) % COLS)
    return (r, (c - 1) % COLS)


def test_combat_branch_outranks_distant_muster() -> None:
    # Packed army, foe 3 away, hill 10+ away: hunters engage the
    # foe; nobody marches the hill this turn.
    bot = fresh_bot()
    pack = [(10, 10), (10, 11), (10, 12), (10, 13)]
    hill = (10, 0)
    turn = run_turn(bot, pack, [hill], FAR_HOME, None, [(10, 7)])
    assert len(turn.orders) > 0
    for o, d in turn.orders:
        assert fake_dest(o, d) != hill
    # Hunters close on the foe instead of marching the hill: at
    # least one step lands nearer the foe than its origin stood.
    assert any(
        torus(fake_dest(o, d), (10, 7)) < torus(o, (10, 7)) for o, d in turn.orders
    )


def test_extra_guard_screens_razer_off_hill() -> None:
    # Home (10, 15), foe (10, 5): halfway square is (10, 10). The
    # extra guard at (10, 9) steps east onto the midpoint under the
    # new screen; the old foe-chase would step west toward the foe.
    bot = fresh_bot()
    home = [(10, 15)]
    turn = run_turn(bot, [(10, 14), (10, 9)], [], home, None, [(10, 5)])
    assert ((10, 14), "e") in turn.orders
    assert ((10, 9), "e") in turn.orders


def test_crowded_combat_turn_stays_fast() -> None:
    # 120 ants plus 30 visible enemies: the join pre-pass and the
    # seek branch path every claim-free ant, yet one turn must
    # stay far under the 1000 ms engine budget.
    bot = fresh_bot()
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(120)]
    foes = [((r * 3) % ROWS, (r * 11) % COLS) for r in range(30)]
    start = time.perf_counter()
    run_turn(bot, ants, [H1, H2], HOME, None, foes)
    assert time.perf_counter() - start < 1.0


def test_lone_holder_abandons_death_trap_slot() -> None:
    # Two defenders on/near H1, one escort on the (9, 5) slot with
    # only the blocked challenger backing it: 2v2 with nobody
    # near, so the slot is a death trap. The escort must retreat
    # north to (8, 5) (2v1, safe) instead of holding station.
    bot = fresh_bot()
    turn = run_turn(bot, [(10, 6), (9, 5)], [H1], FAR_HOME, None, [(10, 5), (11, 5)])
    assert ((9, 5), "n") in turn.orders


def test_backed_holders_stand_the_ring() -> None:
    # Full ring around a defended hill: every holder has 3 friends
    # in range against 1 defender, so all three escorts hold while
    # only the blocked challenger jostles.
    bot = fresh_bot()
    turn = run_turn(
        bot, [(10, 6), (9, 5), (10, 4), (11, 5)], [H1], FAR_HOME, None, [(10, 5)]
    )
    assert {o for o, _ in turn.orders} == {(10, 6)}


def test_ahead_holder_stands_fearless() -> None:
    # Ahead on hills (2 homes vs 1 hill): the lone escort holds its
    # slot fearlessly even with two defenders nearby, while the
    # blocked challenger jostles elsewhere.
    bot = fresh_bot()
    homes = [(10, 15), (0, 0)]
    turn = run_turn(bot, [(10, 6), (9, 5)], [H1], homes, None, [(10, 5), (11, 5)])
    assert (9, 5) not in [o for o, _ in turn.orders]


def test_rotation_survives_visible_enemies() -> None:
    # Far enemies keep the join pre-pass and headings running, yet
    # challenger rotation on H1 must work exactly as without them.
    bot = fresh_bot()
    pack = [(10, 10), (10, 11), (10, 12), (10, 13)]
    turn1 = run_turn(bot, pack, [H1], HOME, None, [(0, 0)])
    assert turn1.orders[0] == ((10, 10), "w")
    assert bot.last_challenger.get(H1) == (10, 10)
    ants2 = [
        moved_to(turn1, a) if a in [o for o, _ in turn1.orders] else a for a in pack
    ]
    turn2 = run_turn(bot, ants2, [H1], HOME, None, [(0, 0)])
    assert bot.last_challenger.get(H1) != (10, 9)
    assert ((10, 9), "w") not in turn2.orders


def test_sealed_ring_still_hunts() -> None:
    # Water seals the ring, but pack combat is independent of the
    # ring: packed hunters still advance on a close foe.
    bot = fresh_bot()
    water = {(9, 5), (10, 6), (11, 5), (10, 4)}
    pack = [(10, 10), (10, 11), (10, 12), (10, 13)]
    turn = run_turn(bot, pack, [H1], FAR_HOME, water, [(10, 8)])
    assert ((10, 10), "w") in turn.orders


def test_ring_intercept_dodges_water() -> None:
    # Mid (10, 10) is water: the screen falls to the nearest
    # passable square via n/e/s/w expansion, never water itself.
    wet = lambda loc: loc != (10, 10)  # noqa: E731
    mid = RG.ring_intercept((10, 15), [(10, 5)], torus, wet, ROWS, COLS)
    assert mid is not None and mid != (10, 10)
    assert torus(mid, (10, 10)) == 1
    assert (
        RG.ring_intercept((10, 15), [(10, 5)], torus, lambda loc: False, ROWS, COLS)
        is None
    )


def test_ring_combat_helpers_stay_cheap() -> None:
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(120)]
    foes = [((r * 3) % ROWS, (r * 11) % COLS) for r in range(30)]
    n = 500
    start = time.perf_counter()
    for _ in range(n):
        for ant in ants:
            RG.ring_nearest_foe(ant, foes, torus)
            RG.ring_has_pack(ant, ants, torus)
        RG.ring_joined({i: foes[i % len(foes)] for i in range(len(ants))})
    # ~2 ms a turn batch: 500x under the 1000 ms engine budget.
    assert (time.perf_counter() - start) / n < 0.005


def test_capture_clears_hill_and_stands_army_down() -> None:
    # Undefended hill: challenger marches on (turn 1), steps onto
    # the hill (turn 2), and once an ant stands on it the hill is
    # forgotten, the challenger record is cleaned, and the army
    # stops mustering and explores instead.
    bot = fresh_bot()
    turn1 = run_turn(bot, [(10, 7)], [H1], FAR_HOME)
    assert turn1.orders == [((10, 7), "w")]
    assert bot.last_challenger.get(H1) == (10, 7)
    turn2 = run_turn(bot, [(10, 6)], [H1], FAR_HOME)
    assert turn2.orders == [((10, 6), "w")]
    assert H1 in bot.remembered_hills
    turn3 = run_turn(bot, [H1], [H1], FAR_HOME)
    assert bot.remembered_hills == set()
    assert bot.last_challenger == {}
    assert bot.last_target is None
    # One ant left: at most one order, and never a march (no hills).
    assert len(turn3.orders) <= 1


def test_siege_captures_empty_hill_then_stands_down() -> None:
    # Three ants on an empty hill: the challenger marches while
    # escorts take ring slots, someone steps onto the hill within
    # a few turns, and the army then stands down (hill forgotten,
    # no muster orders) instead of milling at rubble.
    bot = fresh_bot()
    ants = [(10, 8), (8, 5), (12, 5)]
    turn0 = run_turn(bot, ants, [H1], FAR_HOME)
    assert ((8, 5), "s") in turn0.orders
    for _ in range(6):
        moved = {o: fake_dest(o, d) for o, d in turn0.orders}
        ants = [moved.get(a, a) for a in ants]
        turn0 = run_turn(bot, ants, [H1], FAR_HOME)
        if not bot.remembered_hills:
            break
    assert bot.remembered_hills == set()
    assert bot.last_target is None


def test_contested_cluster_draws_exactly_two() -> None:
    foods = [(5, 5), (5, 6), (5, 7), (15, 15)]
    foes = [(5, 5), (5, 6), (5, 8)]
    groups = RG.denied_food_groups(foods, foes, torus, ROWS, COLS)
    assert sorted(groups) == [[0, 1, 2]]
    ants = [(5, 5), (5, 6), (0, 0), (15, 14)]
    target = RG.assign_food_targets(ants, foods, foes, torus, ROWS, COLS)
    assert len(target) == 3
    assert set(target.values()) <= {(5, 5), (5, 6), (15, 15)}
    assert (15, 15) in target.values()


def test_two_enemies_do_not_deny() -> None:
    foods = [(5, 5), (5, 6)]
    foes = [(5, 5), (5, 6)]
    assert RG.denied_food_groups(foods, foes, torus, ROWS, COLS) == []


def test_wrap_adjacent_foods_cluster() -> None:
    # (5, 0) and (5, 19) are torus-adjacent: one cluster, and three
    # nearby enemies deny both.
    foods = [(5, 0), (5, 19), (15, 15)]
    foes = [(5, 1), (5, 18), (6, 0)]
    groups = RG.denied_food_groups(foods, foes, torus, ROWS, COLS)
    assert sorted(groups) == [[0, 1]]


def test_seeded_boards_never_crash_and_stay_fast() -> None:
    # 30 seeded random boards x 4 turns: food, enemies, hills, and
    # water anywhere. Every turn must finish without raising and
    # far under budget. Deterministic: fixed seeds, no flakiness.
    import random

    start = time.perf_counter()
    for seed in range(30):
        rng = random.Random(seed)
        bot = fresh_bot()
        ants = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(12)]
        foods = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(8)]
        foes = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(8)]
        hills = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(2)]
        water = {(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(15)} - set(
            ants
        )
        for _ in range(4):
            fake = FakeAnts(ants, foods, foes, HOME, hills, water)
            bot.do_turn(cast(Any, fake))
            moved = {o: fake.destination(o, d) for o, d in fake.orders}
            ants = [moved.get(a, a) for a in ants]
    assert time.perf_counter() - start < 8.0


def test_anchor_trades_one_for_one_to_hold_hill() -> None:
    # One razer adjacent to home, one guard adjacent: the anchor's
    # step onto the hill is a 1v1 mutual kill that saves the hill.
    # The safe filter refuses it; the defender's trade takes it.
    bot = fresh_bot()
    turn = run_turn(bot, [(10, 14)], [], [(10, 15)], None, [(10, 13)])
    assert turn.orders == [((10, 14), "e")]


def test_anchor_refuses_suicidal_hold() -> None:
    # Three razers around home: stepping in is 1v3, so the anchor
    # must not donate -- it holds station instead.
    bot = fresh_bot()
    foes = [(10, 13), (10, 12), (9, 13)]
    turn = run_turn(bot, [(10, 14)], [], [(10, 15)], None, foes)
    assert turn.orders == []
    assert (
        RG.ring_defend_release((10, 15), (10, 14), [(10, 14)], foes, torus_sq, 5)
        is False
    )


def torus_sq(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


def test_defend_release_gate() -> None:
    ants = [(10, 14)]
    assert RG.ring_defend_release((10, 15), (10, 14), ants, [], torus_sq, 5) is True
    assert (
        RG.ring_defend_release((10, 15), (10, 14), ants, [(10, 13)], torus_sq, 5)
        is True
    )
    assert (
        RG.ring_defend_release(
            (10, 15), (10, 14), ants, [(10, 13), (9, 13)], torus_sq, 5
        )
        is False
    )


def test_ring_pick_challenger_is_nearest() -> None:
    assert RG.pick_challenger(H1, [A, B], torus) == A
    assert RG.pick_challenger(H1, [B, A], torus) == A
    assert RG.pick_challenger(H1, [A, B], torus, exclude=A) == B
    assert RG.pick_challenger(H1, [A], torus, exclude=A) is None
    assert RG.pick_challenger(H1, [], torus) is None


def test_ring_exclusion_needs_failed_challenge() -> None:
    held = {H1}
    rec = {H1: A}
    assert RG.challenge_exclusion(H1, H1, held, rec, [A, B], torus) == A
    assert RG.challenge_exclusion(H2, H1, held, rec, [A, B], torus) is None
    assert RG.challenge_exclusion(H1, None, held, rec, [A, B], torus) is None
    assert RG.challenge_exclusion(H1, H1, set(), rec, [A, B], torus) is None
    assert RG.challenge_exclusion(H1, H1, held, {}, [A, B], torus) is None
    assert RG.challenge_exclusion(H1, H1, held, rec, [(10, 9), B], torus) == (10, 9)


def test_muster_radius_constant_exists() -> None:
    # The army only marches hills within MUSTER_RADIUS steps;
    # farther hills wait for explore/hunt to close the distance
    # instead of cross-map donation treks.
    assert RG.MUSTER_RADIUS == 20


def test_far_escort_skips_muster_for_explore() -> None:
    # Radius 5: A sits 5 from H1 and musters, but B sits 15 away
    # and must not march -- it explores instead.
    old = RG.MUSTER_RADIUS
    RG.MUSTER_RADIUS = 5
    try:
        bot = fresh_bot()
        turn = run_turn(bot, [A, B], [H1], FAR_HOME)
        assert ((10, 10), "w") in turn.orders
        assert ((0, 0), "n") in turn.orders
    finally:
        RG.MUSTER_RADIUS = old


def test_far_lone_hill_gets_no_reinforce() -> None:
    # Radius 5: the only hill sits 18 away, so even reinforce
    # stands down and the lone ant explores north instead.
    old = RG.MUSTER_RADIUS
    RG.MUSTER_RADIUS = 5
    try:
        bot = fresh_bot()
        turn = run_turn(bot, [A], [H2], FAR_HOME)
        assert turn.orders == [(A, "n")]
    finally:
        RG.MUSTER_RADIUS = old


def test_big_board_turn_stays_fast() -> None:
    # Exam maps run to 42x196: one crowded turn on a 40x160 board
    # with food, both hills, water, and 40 visible enemies must
    # finish far under the 1000 ms engine budget.
    import ants as ants_mod  # noqa: E402

    engine = ants_mod.Ants()
    engine.setup(
        "turn 0\nturns 200\nrows 40\ncols 160\nloadtime 2000\n"
        "turntime 1000\nviewradius2 93\nattackradius2 5\n"
        "spawnradius2 1\nplayer_seed 42\n"
    )
    bot = RG.Ring()
    bot.do_setup(engine)
    orders: list[tuple[Loc, str]] = []
    engine.issue_order = orders.append
    lines = ["f 5 5", "f 30 100", "w 9 5", "h 10 150 0", "h 10 5 1"]
    for i in range(60):
        lines.append(f"a {(i * 7) % 40} {(i * 13) % 160} 0")
    for i in range(40):
        lines.append(f"a {(i * 3) % 40} {(i * 11) % 160} 1")
    engine.update("\n".join(lines) + "\n")
    start = time.perf_counter()
    bot.do_turn(engine)
    assert time.perf_counter() - start < 1.0
    assert len(orders) > 0


# --- Grave check (new mechanism): failing first. ---


def test_ring_grave_gate() -> None:
    # A remembered hill is gone iff it is unreported AND an ant
    # stands within viewradius2 of its square (we would see it).
    assert RG.ring_hill_gone(H1, [A], set(), 93, torus_sq) is True
    assert RG.ring_hill_gone(H1, [A], {H1}, 93, torus_sq) is False
    assert RG.ring_hill_gone(H2, [A], set(), 93, torus_sq) is False
    assert RG.ring_hill_gone(H1, [], set(), 93, torus_sq) is False


def test_visibly_empty_hill_is_forgotten() -> None:
    # A sees H1's square (sq 25 < 93) but no hill is reported:
    # someone razed it, so forget it. H2 sits out of view
    # (sq 162 > 93) and stays remembered.
    bot = fresh_bot()
    bot.remembered_hills = {H1, H2}
    run_turn(bot, [A], [], FAR_HOME)
    assert bot.remembered_hills == {H2}


def test_food_detour_routes_around_wall() -> None:
    # A wall seals column 5 except a gap at row 0. Greedy east
    # (torus distance 6) walks into the wall; the torus-aware BFS
    # instead wraps west around the planet (14 open steps) and
    # the ant marches food without stepping into the wall.
    water = {(r, 5) for r in range(ROWS) if r != 0}
    bot = fresh_bot()
    fake = FakeAnts([(10, 2)], [(10, 8)], [], FAR_HOME, [], water)
    bot.do_turn(cast(Any, fake))
    assert fake.orders == [((10, 2), "w")]


def test_unreachable_food_falls_through_to_explore() -> None:
    # Full walls on columns 5 and 15 seal the board into two
    # regions: the food sits unreachable across the seal. The
    # claim is kept (no other ant chases it) while this ant
    # falls through to least-visited explore instead of stalling.
    water = {(r, 5) for r in range(ROWS)} | {(r, 15) for r in range(ROWS)}
    bot = fresh_bot()
    fake = FakeAnts([(10, 2)], [(10, 8)], [], FAR_HOME, [], water)
    bot.do_turn(cast(Any, fake))
    assert fake.orders == [((10, 2), "n")]


def test_beyond_budget_food_falls_through_to_explore() -> None:
    # Food 20 steps out is claimed but beyond the BFS budget, so
    # no path exists this turn: the ant explores north instead of
    # stalling on an unpathable claim. Pins the implicit
    # localizer -- retune the budget and this test moves with it.
    bot = fresh_bot()
    fake = FakeAnts([A], [(0, 0)], [], FAR_HOME, [], None)
    bot.do_turn(cast(Any, fake))
    assert fake.orders == [(A, "n")]


def test_identical_turns_issue_identical_orders() -> None:
    # The bot is deterministic: two fresh bots on identical boards
    # (food, enemies, hills, water) must issue byte-identical
    # orders. This pins behavior across perf refactors like the
    # step cache: caching may skip work, never change a step.
    import random

    rng = random.Random(7)
    ants = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(30)]
    foods = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(12)]
    foes = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(12)]
    hills = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(2)]
    water = {(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(20)} - set(ants)
    first = fresh_bot()
    fake1 = FakeAnts(ants, foods, foes, HOME, hills, water)
    first.do_turn(cast(Any, fake1))
    second = fresh_bot()
    fake2 = FakeAnts(ants, foods, foes, HOME, hills, water)
    second.do_turn(cast(Any, fake2))
    assert fake1.orders == fake2.orders


def test_muster_quorum_constant_exists() -> None:
    # The siege marches only with a quorum; a lone claim-free ant
    # reinforces safely instead of donating onto a defended hill.
    assert RG.MUSTER_QUORUM == 2


def test_nearest_ant_anchors_threatened_hill() -> None:
    # Home (10, 15) threatened from (10, 5): the near ant (10, 14)
    # must anchor (march the hill east) while the far ant (10, 0)
    # screens toward the halfway square -- not the reverse.
    bot = fresh_bot()
    turn = run_turn(bot, [(10, 0), (10, 14)], [], [(10, 15)], None, [(10, 5)])
    assert ((10, 14), "e") in turn.orders
    assert ((10, 0), "e") in turn.orders


def test_harvester_does_not_steal_anchor() -> None:
    # (5, 5) harvests (5, 6) while home is threatened: the draft
    # skips the busy harvester, so near ant (10, 14) still anchors
    # east and far ant (10, 0) screens east.
    bot = fresh_bot()
    fake = FakeAnts(
        [(10, 0), (10, 14), (5, 5)], [(5, 6)], [(10, 5)], [(10, 15)], [], None
    )
    bot.do_turn(cast(Any, fake))
    assert ((5, 5), "e") in fake.orders
    assert ((10, 14), "e") in fake.orders
    assert ((10, 0), "e") in fake.orders


def test_overflow_hill_falls_back_to_first_come() -> None:
    # Two threatened homes but only one claim-free ant: the draft
    # covers one hill, so the other falls back to first-come and
    # the lone ant still marches a guard post (one order).
    bot = fresh_bot()
    homes = [(10, 15), (0, 0)]
    foes = [(10, 5), (0, 10)]
    turn = run_turn(bot, [A], [], homes, None, foes)
    assert len(turn.orders) == 1
    assert turn.orders[0][0] == A


def test_opening_ant_leaves_home_hill() -> None:
    # Turn 0: the lone ant starts on its home hill with food
    # nearby. It must march the food (exactly one order) and
    # step off the hill, keeping the spawn square open.
    bot = fresh_bot()
    fake = FakeAnts([(10, 15)], [(10, 12)], [], [(10, 15)], [], None)
    bot.do_turn(cast(Any, fake))
    assert fake.orders == [((10, 15), "w")]


def test_opening_ant_explores_off_hill_without_food() -> None:
    # No food either: the ant still steps off (least-visited
    # neighbor) instead of sitting on the spawn.
    bot = fresh_bot()
    turn = run_turn(bot, [(10, 15)], [], [(10, 15)])
    assert len(turn.orders) == 1
    assert turn.orders[0][0] == (10, 15)


def test_besieged_ant_holds_without_orders() -> None:
    # Water on all four sides: no legal move exists, so the ant
    # holds station with no orders instead of crashing or
    # stepping into water.
    bot = fresh_bot()
    water = {(9, 15), (10, 16), (11, 15), (10, 14)}
    turn = run_turn(bot, [(10, 15)], [], [(10, 15)], water)
    assert turn.orders == []


def test_low_time_breaks_gracefully() -> None:
    # Engine timeout path: with almost no time left the turn
    # still returns without raising (partial orders at most).
    class SlowAnts(FakeAnts):
        def time_remaining(self) -> int:
            return 5

    bot = fresh_bot()
    fake = SlowAnts([A, B], [(5, 5)], [(12, 5)], HOME, [H1])
    bot.do_turn(cast(Any, fake))
    assert len(fake.orders) <= 2


def test_explore_avoids_visited_squares() -> None:
    # Least-visited first: with north visited 5 times, the
    # explorer takes east instead of the default north.
    bot = fresh_bot()
    bot.visits[(9, 10)] = 5
    turn = run_turn(bot, [A], [], FAR_HOME)
    assert turn.orders == [(A, "e")]


def test_anchor_relay_leaves_hill_next_turn() -> None:
    # The anchor marches onto the home hill (turn 0), then relays
    # off north (turn 1) instead of sitting on the spawn -- the
    # hill stays spawnable while coverage rotates.
    bot = fresh_bot()
    turn0 = run_turn(bot, [(10, 14)], [], [(10, 15)], None, [(10, 5)])
    assert turn0.orders == [((10, 14), "e")]
    turn1 = run_turn(bot, [(10, 15)], [], [(10, 15)], None, [(10, 5)])
    assert turn1.orders == [((10, 15), "n")]


def test_challenger_rotates_while_defender_holds() -> None:
    # Four ants against a static defender: every failed turn
    # rotates a new challenger while the hill stays remembered --
    # the siege never sends the same ant twice in a row.
    bot = fresh_bot()
    ants = [(10, 8), (8, 5), (12, 5), (9, 7)]
    seen: list[Loc] = []
    for _ in range(4):
        turn = run_turn(bot, ants, [H1], FAR_HOME, None, [H1])
        seen.append(bot.last_challenger.get(H1))
        moved = {o: fake_dest(o, d) for o, d in turn.orders}
        ants = [moved.get(a, a) for a in ants]
    assert H1 in bot.remembered_hills
    assert len(set(seen)) == 4


def test_orders_never_collide_or_drown() -> None:
    # Across 30 seeded boards: every order has a distinct origin,
    # every destination is distinct and passable (never water).
    # Collisions and water steps waste ants, so pin them gone.
    import random

    for seed in range(30):
        rng = random.Random(5000 + seed)
        bot = fresh_bot()
        ants = list({(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(15)})
        foods = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(8)]
        foes = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(8)]
        hills = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(2)]
        water = {(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(25)} - set(
            ants
        )
        fake = FakeAnts(ants, foods, foes, HOME, hills, water)
        bot.do_turn(cast(Any, fake))
        origins = [o for o, _ in fake.orders]
        assert len(set(origins)) == len(origins)
        dests = [fake.destination(o, d) for o, d in fake.orders]
        assert len(set(dests)) == len(dests)
        for dest in dests:
            assert dest not in water


def test_lone_ant_skips_defended_muster_for_reinforce() -> None:
    # Solo ant, H1 defended by an enemy on it, two hills, no food:
    # the quorum sends it to reinforce H2 instead of donating.
    bot = fresh_bot()
    turn = run_turn(bot, [A], [H1, H2], FAR_HOME, None, [H1])
    assert len(turn.orders) == 1
    assert turn.orders[0][0] == A
    assert turn.orders[0] != (A, "w")


def test_lone_ant_races_empty_hill() -> None:
    # Same board with no defender: racing the empty hill is free
    # tempo, so the lone ant still marches H1 west.
    bot = fresh_bot()
    turn = run_turn(bot, [A], [H1, H2], FAR_HOME)
    assert (A, "w") in turn.orders


def test_ring_hill_open_gate() -> None:
    # Open iff no visible enemy stands within RACE_RADIUS steps.
    assert RG.RACE_RADIUS == 8
    assert RG.ring_hill_open(H1, [], torus) is True
    assert RG.ring_hill_open(H1, [(10, 5)], torus) is False
    assert RG.ring_hill_open(H1, [(10, 14)], torus) is True


def test_pair_still_musters_with_quorum() -> None:
    # Two claim-free ants meet the quorum: the challenger still
    # marches the muster hill first.
    bot = fresh_bot()
    turn = run_turn(bot, [A, B], [H1, H2], FAR_HOME)
    assert turn.orders[0] == (A, "w")
    assert bot.last_challenger.get(H1) == A


# --- Local harvest (new mechanism): failing first. ---


def test_local_harvest_radius_constant_exists() -> None:
    # Ants only chase food within FOOD_RADIUS steps; distant food is
    # left for explorers/hunters/muster instead of cross-map treks.
    assert RG.FOOD_RADIUS == 20


def test_local_harvest_ignores_distant_food() -> None:
    # Radius 5: near food (10, 12) is claimed, far food (0, 0) is not.
    ants = [A]
    foods = [(10, 12), (0, 0)]
    target = RG.assign_food_targets(ants, foods, [], torus, ROWS, COLS, radius=5)
    assert target == {0: (10, 12)}


def test_local_harvest_radius_zero_keeps_standing_food() -> None:
    # Boundary: radius 0 still claims the square underfoot, so a
    # harvester never starves itself.
    target = RG.assign_food_targets([A], [A], [], torus, ROWS, COLS, radius=0)
    assert target == {0: A}


def test_desert_race_claims_uncontested_far_food() -> None:
    # Deserted (nothing within 5) with no enemy near the food:
    # the ant beelines the far food ballistically instead of
    # diffusing on explore.
    target = RG.assign_food_targets([A], [(0, 0)], [], torus, ROWS, COLS, radius=5)
    assert target == {0: (0, 0)}


def test_desert_race_skips_contested_far_food() -> None:
    # Same desert, but an enemy sits on the far food: cede it and
    # stay free for hunt/muster/explore instead of donating.
    foes = [(0, 0)]
    target = RG.assign_food_targets([A], [(0, 0)], foes, torus, ROWS, COLS, radius=5)
    assert target == {}


def test_desert_race_single_claim_per_food() -> None:
    # Two deserted ants, one far food: exactly one claim, no
    # doubling up on the trek.
    target = RG.assign_food_targets(
        [A, (10, 0)], [(0, 0)], [], torus, ROWS, COLS, radius=5
    )
    assert len(target) == 1
    assert set(target.values()) == {(0, 0)}


def test_deserted_ant_marches_far_food_end_to_end() -> None:
    # Radius 5 through do_turn: A is deserted, the far food is
    # uncontested, so the race claims it and A marches (one
    # order from A toward the food) instead of exploring.
    old = RG.FOOD_RADIUS
    RG.FOOD_RADIUS = 5
    try:
        bot = fresh_bot()
        fake = FakeAnts([A], [(0, 0)], [], FAR_HOME, [], None)
        bot.do_turn(cast(Any, fake))
        assert len(fake.orders) == 1
        assert fake.orders[0][0] == A
    finally:
        RG.FOOD_RADIUS = old


def test_desert_race_yields_to_denial() -> None:
    # (10, 18) sits 15+ from every foe (uncontested in isolation)
    # but clusters with (10, 10), which three foes contest -- the
    # whole cluster is denied, so the deserted ant cedes both and
    # stays free instead of racing the far end.
    foods = [(10, 10), (10, 18)]
    foes = [(10, 2), (10, 3), (10, 4)]
    target = RG.assign_food_targets([(0, 0)], foods, foes, torus, ROWS, COLS, radius=5)
    assert RG.denied_food_groups(foods, foes, torus, ROWS, COLS) == [[0, 1]]
    assert target == {}


def test_local_harvest_default_keeps_existing_boards_claimed() -> None:
    # Default radius must not starve the pinned boards: the
    # no-hill parity scenario stays fully claimed by default.
    ants = [A, B]
    foods = [(5, 5), (15, 15)]
    target = RG.assign_food_targets(ants, foods, [], torus, ROWS, COLS)
    assert len(target) == 2
    assert set(target.values()) == {(5, 5), (15, 15)}


def test_local_harvest_denied_cluster_beyond_radius_draws_nobody() -> None:
    # Contested cluster far away draws nobody when out of radius;
    # the denial ants stay free for local fights instead.
    foods = [(0, 0), (0, 1), (10, 12)]
    foes = [(0, 0), (0, 1), (1, 0)]
    target = RG.assign_food_targets([A], foods, foes, torus, ROWS, COLS, radius=5)
    assert target == {0: (10, 12)}
