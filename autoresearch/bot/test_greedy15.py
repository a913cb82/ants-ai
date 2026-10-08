#!/usr/bin/env python
"""Tests for Greedy15: focus-foe greedy fields, phased weights, exorcism,
proportional guard.

TDD: written before Greedy15.py exists. Risky parts pinned first:
focus-foe selection, phased weight schedule, ghost-hill exorcism,
focus-weighted combat scoring, and N+1 guard quotas.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import Greedy15
import pytest
from Greedy15 import (
    WEIGHTS,
    focus_foe,
    phased_weights,
    pick_best,
    retain_hills,
    score_move,
)


def manhattan(rows, cols):
    def distance(a, b):
        return min(abs(a[0] - b[0]), rows - abs(a[0] - b[0])) + min(
            abs(a[1] - b[1]), cols - abs(a[1] - b[1])
        )

    return distance


def sqdist(rows, cols):
    def fn(a, b):
        dr = min(abs(a[0] - b[0]), rows - abs(a[0] - b[0]))
        dc = min(abs(a[1] - b[1]), cols - abs(a[1] - b[1]))
        return dr * dr + dc * dc

    return fn


class FakeAnts:
    """Minimal harness: open board, configurable ants/food/hills."""

    def __init__(
        self,
        rows=20,
        cols=20,
        me=((10, 10),),
        foes=(),
        foods=(),
        my_hills=(),
        foe_hills=(),
        water=frozenset(),
    ):
        self.rows = rows
        self.cols = cols
        self._me = list(me)
        self._foes = list(foes)
        self._foods = list(foods)
        self._my_hills = list(my_hills)
        self._foe_hills = list(foe_hills)
        self._water = set(water)
        self.attackradius2 = 5
        self.orders = []
        self._t0 = time.perf_counter()
        self._seen = None

    def food(self):
        return list(self._foods)

    def my_ants(self):
        return list(self._me)

    def enemy_ants(self):
        return [(loc, 1) for loc in self._foes]

    def my_hills(self):
        return list(self._my_hills)

    def enemy_hills(self):
        return [(loc, 1) for loc in self._foe_hills]

    def distance(self, a, b):
        return min(abs(a[0] - b[0]), self.rows - abs(a[0] - b[0])) + min(
            abs(a[1] - b[1]), self.cols - abs(a[1] - b[1])
        )

    def destination(self, loc, d):
        from ants import AIM

        dr, dc = AIM[d]
        return ((loc[0] + dr) % self.rows, (loc[1] + dc) % self.cols)

    def passable(self, loc):
        return loc not in self._water

    def unoccupied(self, loc):
        # Mirrors the real engine: validate_orders ignores moves onto
        # FOOD/WATER, and do_gather banks food within spawnradius 1 --
        # ants gather adjacent, never by stepping on.
        return loc not in self._me and loc not in self._foes and loc not in self._foods

    def visible(self, loc):
        # visible iff within manhattan 5 of any own ant
        return any(self.distance(a, loc) <= 5 for a in self._me)

    def time_remaining(self):
        return 1000 - int(1000 * (time.perf_counter() - self._t0))

    def issue_order(self, order):
        self.orders.append(order)


# --- focus_foe ---


def test_focus_none_without_enemies():
    assert focus_foe([(5, 5)], [], manhattan(20, 20)) is None


def test_focus_none_without_ants():
    assert focus_foe([], [(5, 5)], manhattan(20, 20)) is None


def test_focus_picks_foe_nearest_centroid():
    # army clustered at (10, 10); foe A at (10, 12) is centroid-nearest,
    # foe B at (0, 0) is far. Focus must be A even though B is listed first.
    own = [(10, 10), (10, 11), (11, 10)]
    foes = [(0, 0), (10, 12)]
    assert focus_foe(own, foes, manhattan(20, 20)) == (10, 12)


def test_focus_single_foe():
    assert focus_foe([(0, 0)], [(7, 7)], manhattan(20, 20)) == (7, 7)


def test_focus_toroidal():
    # rows=20: (19, 5) is distance 2 from (1, 5) through the seam.
    assert focus_foe([(1, 5)], [(19, 5), (1, 15)], manhattan(20, 20)) == (19, 5)


# --- phased_weights ---


def test_phased_turn_zero_is_base():
    assert phased_weights(0) == WEIGHTS


def test_phased_food_decays_hills_grow():
    early = phased_weights(0)
    late = phased_weights(400)
    assert late[0] < early[0]  # food down
    assert late[2] > early[2]  # hills up
    assert late[1] == early[1]  # enemy flat
    assert late[3] == early[3]  # unseen flat


def test_phased_bounds():
    wf, we, wh, wu = phased_weights(100000)
    assert wf >= 0.4
    assert wh <= 6.0
    wf0, _, _, _ = phased_weights(-5)
    assert wf0 == WEIGHTS[0]


def test_phased_monotone():
    hills = [phased_weights(t)[2] for t in (0, 50, 200, 500, 2000)]
    assert hills == sorted(hills)
    foods = [phased_weights(t)[0] for t in (0, 50, 200, 500, 2000)]
    assert foods == sorted(foods, reverse=True)


# --- retain_hills (exorcism) ---


def _see_all(loc):
    return True


def _see_none(loc):
    return False


def test_exorcism_drops_visible_empty_ghost():
    remembered = {(5, 5), (15, 15)}
    live: set[tuple[int, int]] = set()  # no enemy hill visible anywhere
    assert retain_hills(remembered, live, _see_all) == set()


def test_exorcism_keeps_unseen_ghost():
    remembered = {(5, 5)}
    assert retain_hills(remembered, set(), _see_none) == {(5, 5)}


def test_exorcism_keeps_visible_live_hill():
    remembered = {(5, 5)}
    assert retain_hills(remembered, {(5, 5)}, _see_all) == {(5, 5)}


def test_exorcism_mixed():
    remembered = {(1, 1), (2, 2), (3, 3)}
    live = {(2, 2)}
    seen = {(1, 1), (2, 2)}  # (3,3) unseen

    def _see_some(loc):
        return loc in seen

    out = retain_hills(remembered, live, _see_some)
    assert out == {(2, 2), (3, 3)}


# --- score_move with focus ---


def _always_open(loc):
    return True


def _score_kwargs(rows=20, cols=20):
    return {
        "passable": _always_open,
        "sq_dist": sqdist(rows, cols),
        "attack_r2": 5,
        "rows": rows,
        "cols": cols,
    }


def test_score_focus_step_beats_nonfocus_step():
    # mover at (10,10); focus foe adjacent north at (9,10),
    # other foe adjacent south at (12,10) but two steps away via (11,10).
    # Stepping north lands next to the focus foe: focus weight must win.
    mover = (10, 10)
    focus = (9, 10)
    foes = [(9, 10), (12, 10)]
    kw = _score_kwargs()
    north = score_move(
        (9, 10), mover, [mover], foes, set(), set(), None, focus=focus, **kw
    )
    south = score_move(
        (11, 10), mover, [mover], foes, set(), set(), None, focus=focus, **kw
    )
    assert north > south


def test_score_no_focus_matches_base_weights():
    mover = (10, 10)
    foes = [(10, 12)]
    kw = _score_kwargs()
    a = score_move(
        (10, 11), mover, [mover], foes, {(0, 0)}, set(), None, focus=None, **kw
    )
    b = score_move(
        (10, 11),
        mover,
        [mover],
        foes,
        {(0, 0)},
        set(),
        None,
        focus=(10, 12),
        focus_weight=0.0,
        **kw,
    )
    assert a == pytest.approx(b)


def test_score_kill_bonus_still_gated():
    # 3v1 at the destination: the kill bonus must apply exactly once.
    # Same geometry with KILL_BONUS zeroed scores exactly 2.0 lower.
    mover = (10, 10)
    own = [mover, (9, 9), (9, 11)]
    kw = _score_kwargs()
    dest = (9, 10)
    with_bonus = score_move(
        dest, mover, own, [(8, 10)], set(), set(), None, focus=(8, 10), **kw
    )
    saved, Greedy15.KILL_BONUS = Greedy15.KILL_BONUS, 0.0
    try:
        without_bonus = score_move(
            dest, mover, own, [(8, 10)], set(), set(), None, focus=(8, 10), **kw
        )
    finally:
        Greedy15.KILL_BONUS = saved
    assert with_bonus - without_bonus == pytest.approx(2.0)
    # lone ant, even trade: fields pull toward the foe (step outscores
    # hold) but no kill bonus applies -- the safety gate, not the
    # score, is what refuses the 1v1. Pins delineate doctrine.
    lone_step = score_move(
        (10, 11), mover, [mover], [(10, 12)], set(), set(), None, **kw
    )
    lone_hold = score_move(mover, mover, [mover], [(10, 12)], set(), set(), None, **kw)
    assert lone_step > lone_hold


def test_focus_sampled_deterministic_and_close():
    import random

    rng = random.Random(99)
    own = [(rng.randrange(30), rng.randrange(30)) for _ in range(200)]
    foes = [(rng.randrange(30), rng.randrange(30)) for _ in range(200)]
    dist = manhattan(30, 30)
    assert focus_foe(own, foes, dist) == focus_foe(own, foes, dist)
    # sampled focus must be near-optimal: within 25% of the exact optimum.
    exact = min(foes, key=lambda e: sum(dist(a, e) for a in own))
    got = focus_foe(own, foes, dist)
    exact_cost = sum(dist(a, exact) for a in own)
    got_cost = sum(dist(a, got) for a in own)
    assert got_cost <= exact_cost * 1.25


def test_focus_scale_budget():
    own = [(r % 60, (r * 7) % 60) for r in range(400)]
    foes = [((r * 13) % 60, r % 60) for r in range(400)]
    dist = manhattan(60, 60)
    t0 = time.perf_counter()
    focus_foe(own, foes, dist)
    assert (time.perf_counter() - t0) < 0.1


def test_muster_target_centroid_nearest():
    from Greedy15 import muster_target

    own = [(10, 10), (10, 11), (11, 10)]
    hills = [(0, 0), (10, 13)]
    assert muster_target(hills, own, manhattan(20, 20)) == (10, 13)
    assert muster_target([], own, manhattan(20, 20)) is None


def test_pick_best_tie_holds():
    assert pick_best({"-": 1.0, "n": 1.0, "s": 0.5}) == "-"


# --- bot-level ---


def test_bot_food_run_and_walkoff():
    bot = Greedy15.Greedy15()
    ants = FakeAnts(me=((5, 5), (5, 6)), foods=((5, 8),), my_hills=((5, 5),))
    bot.do_setup(ants)
    bot.do_turn(ants)
    assert len(ants.orders) > 0
    # nobody ends parked on the home hill: walk-off holds
    dests = set()
    for loc, d in ants.orders:
        dests.add(ants.destination(loc, d))
    assert (5, 5) not in dests


def test_bot_exorcises_ghost_hill():
    bot = Greedy15.Greedy15()
    ants = FakeAnts(me=((10, 10),))
    bot.do_setup(ants)
    bot.remembered_hills = {(10, 12)}  # visible (dist 2), but razed
    ants._foe_hills = []
    bot.do_turn(ants)
    assert (10, 12) not in bot.remembered_hills


def test_bot_remembers_live_hill():
    bot = Greedy15.Greedy15()
    ants = FakeAnts(me=((10, 10),), foe_hills=((10, 12),))
    bot.do_setup(ants)
    bot.do_turn(ants)
    assert (10, 12) in bot.remembered_hills


def test_bot_turn_counter_phases_weights():
    bot = Greedy15.Greedy15()
    ants = FakeAnts(me=((10, 10),))
    bot.do_setup(ants)
    assert bot.turn == 0
    bot.do_turn(ants)
    assert bot.turn == 1
    assert bot.last_weights == phased_weights(1)


def test_bot_turn_under_budget():
    bot = Greedy15.Greedy15()
    me = tuple((r, c) for r in range(5, 10) for c in range(5, 13))
    foes = tuple((r, c) for r in range(12, 15) for c in range(5, 10))
    foods = tuple((r, c) for r in range(0, 20, 3) for c in range(0, 20, 3))
    ants = FakeAnts(
        me=me, foes=foes, foods=foods, foe_hills=((0, 0),), my_hills=((9, 9),)
    )
    bot.do_setup(ants)
    t0 = time.perf_counter()
    bot.do_turn(ants)
    assert (time.perf_counter() - t0) < 1.0


def test_exorcism_frees_hunters_differential():
    # Both bots remember a ghost hill south of the ant, visible but razed.
    # Greedy6 musters at the ghost (marches south); Greedy15 exorcises it
    # and explores north (least-visited fallback order). Pins the new
    # mechanism behaviorally, not just at unit level.
    import Greedy6

    def run(bot):
        ants = FakeAnts(me=((10, 10),))
        bot.do_setup(ants)
        bot.remembered_hills = {(12, 10)}
        bot.do_turn(ants)
        return ants.orders

    g6_orders = run(Greedy6.Greedy6())
    g15_orders = run(Greedy15.Greedy15())
    assert g6_orders == [((10, 10), "s")]
    assert g15_orders == [((10, 10), "n")]
    assert g6_orders != g15_orders


def test_focus_converges_where_greedy6_splits():
    # Symmetric foes north/south, unseen hill far south. Greedy6's hill
    # field drags its step south; Greedy15's focus foe (north, nearest
    # the centroid) doubles the northern bump and steps north into a
    # strict-superiority kill. Pins focus-fire at bot level.
    import Greedy6

    def run(bot):
        ants = FakeAnts(me=((10, 10), (9, 9), (9, 11)))
        bot.do_setup(ants)
        bot.remembered_hills = {(16, 10)}  # unseen: kept by both bots
        ants._foes = [(8, 10), (12, 10)]
        bot.do_turn(ants)
        return ants.orders[0]

    assert run(Greedy6.Greedy6()) == ((10, 10), "s")
    assert run(Greedy15.Greedy15()) == ((10, 10), "n")


def test_multiturn_gather_loop():
    # Short scenario: 20 turns on one map, orders applied, food eaten on
    # arrival. The economy must actually bank food without crashing.
    import random

    rng = random.Random(15)
    me = [(10, 10), (11, 10), (10, 11)]
    foods = [(rng.randrange(20), rng.randrange(20)) for _ in range(12)]
    eaten = 0
    bot = Greedy15.Greedy15()
    ants = FakeAnts(me=tuple(me), foods=list(foods))
    bot.do_setup(ants)
    for _ in range(20):
        ants._foods = list(foods)
        ants._me = list(me)
        ants.orders = []
        t0 = time.perf_counter()
        bot.do_turn(ants)
        assert (time.perf_counter() - t0) < 0.2
        # Engine do_gather: food within spawnradius 1 of our ants is
        # banked -- adjacency gathers, stepping on is illegal.
        me = [ants.destination(loc, d) for loc, d in ants.orders]
        me += [loc for loc in ants._me if loc not in [o[0] for o in ants.orders]]
        held = set(me)
        before = len(foods)
        foods = [f for f in foods if not any(ants.distance(a, f) <= 1 for a in held)]
        eaten += before - len(foods)
    assert eaten > 0


def test_exorcism_wraps_the_seam():
    # rows=20: ant at (1,10), ghost at (19,10) is 2 steps through the
    # seam -- visible, razed, must go.
    bot = Greedy15.Greedy15()
    ants = FakeAnts(me=((1, 10),))
    bot.do_setup(ants)
    bot.remembered_hills = {(19, 10)}
    bot.do_turn(ants)
    assert (19, 10) not in bot.remembered_hills


def test_phased_weights_at_endgame():
    bot = Greedy15.Greedy15()
    ants = FakeAnts(me=((10, 10),))
    bot.do_setup(ants)
    bot.turn = 599
    bot.do_turn(ants)
    assert bot.last_weights == phased_weights(600)
    assert bot.last_weights[2] == 6.0  # hill cap reached


def test_combat_boxed_except_one_exit():
    # water walls on three sides; only east is open. Combat scoring
    # must not crash and must pick the exit over holding into a kill.
    water = {(9, 10), (10, 9), (11, 10)}
    ants = FakeAnts(me=((10, 10), (10, 12)), foes=((10, 14),), water=water)
    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    bot.do_turn(ants)
    assert ((10, 10), "e") in ants.orders


def test_gather_and_guard_parity_with_greedy6():
    # No combat, no ghosts: phased turn-1 weights must not drift food
    # claims, guard posts, or explore steps away from the Greedy6 base.
    import Greedy6

    def run(bot):
        ants = FakeAnts(
            me=((10, 10), (12, 14), (20, 20)),
            foes=((11, 11),),
            foods=((10, 13), (21, 21), (0, 0)),
            my_hills=((12, 14),),
        )
        bot.do_setup(ants)
        bot.do_turn(ants)
        return sorted(ants.orders)

    assert run(Greedy15.Greedy15()) == run(Greedy6.Greedy6())


def test_fuzz_random_boards_no_crash():
    # 20 seeded random boards through the real engine object: every
    # turn must finish in budget with well-formed, legal orders.
    import io
    import random

    from ants import Ants

    rng = random.Random(20261008)
    for trial in range(20):
        rows, cols = 24, 24
        ants = Ants()
        ants.setup(
            f"cols {cols}\nrows {rows}\nplayer_seed 1\nturntime 1000\n"
            "loadtime 3000\nviewradius2 77\nattackradius2 5\n"
            "spawnradius2 1\nturns 500\n"
        )
        water = {(rng.randrange(rows), rng.randrange(cols)) for _ in range(30)}

        def spawn(_rows=rows, _cols=cols):
            return (rng.randrange(_rows), rng.randrange(_cols))

        me = [spawn() for _ in range(rng.randint(1, 25))]
        foes = [spawn() for _ in range(rng.randint(0, 25))]
        foods = [spawn() for _ in range(rng.randint(0, 20))]
        lines = [f"w {r} {c}" for r, c in water]
        lines += [f"a {r} {c} 0" for r, c in me if (r, c) not in water]
        lines += [f"a {r} {c} 1" for r, c in foes if (r, c) not in water]
        lines += [f"f {r} {c}" for r, c in foods if (r, c) not in water]
        lines += [f"d {r} {c} 1" for r, c in foes[:2]]
        lines += ["h 0 0 0", "h 23 23 1"]
        ants.update("\n".join(lines))
        bot = Greedy15.Greedy15()
        bot.do_setup(ants)
        old = sys.stdout
        sys.stdout = io.StringIO()
        try:
            t0 = time.perf_counter()
            bot.do_turn(ants)
            dt = time.perf_counter() - t0
            out = sys.stdout.getvalue()
        finally:
            sys.stdout = old
        assert dt < 1.0, f"trial {trial}: {dt:.3f}s"
        mine = set(ants.my_ants())
        foodset = set(ants.food())
        seen_from = set()
        for ln in out.splitlines():
            if not ln.strip():
                continue
            parts = ln.split()
            assert parts[0] == "o" and len(parts) == 4, (trial, ln)
            assert (int(parts[1]), int(parts[2])) in mine, (trial, ln)
            assert (int(parts[1]), int(parts[2])) not in seen_from, (trial, ln)
            seen_from.add((int(parts[1]), int(parts[2])))
            assert parts[3] in ("n", "e", "s", "w"), (trial, ln)
            # Engine validate_orders ignores food/water steps: destinations
            # must be passable land, never a food square.
            dest = ants.destination((int(parts[1]), int(parts[2])), parts[3])
            assert ants.passable(dest), (trial, ln)
            assert dest not in foodset, (trial, ln)


def test_ten_turn_live_scenario():
    # 10 live turns through the real engine object with orders
    # applied: foods get banked, the razed hill gets exorcised once
    # visible-empty, every turn stays in budget.
    import io

    from ants import Ants

    rows = cols = 15
    ants = Ants()
    ants.setup(
        f"cols {cols}\nrows {rows}\nplayer_seed 3\nturntime 1000\n"
        "loadtime 3000\nviewradius2 77\nattackradius2 5\n"
        "spawnradius2 1\nturns 500\n"
    )
    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    me = [(7, 7), (3, 3), (11, 11)]
    foe = [(1, 12)]
    foods = [(7, 9), (3, 5), (11, 9)]
    eaten = 0
    old = sys.stdout
    try:
        for turn in range(10):
            lines = [f"a {r} {c} 0" for r, c in me]
            lines += [f"a {r} {c} 1" for r, c in foe]
            lines += [f"f {r} {c}" for r, c in foods]
            if turn == 0:
                lines.append("h 9 12 1")  # razed after turn 1
            lines.append("h 7 7 0")
            ants.update("\n".join(lines))
            sys.stdout = io.StringIO()
            t0 = time.perf_counter()
            bot.do_turn(ants)
            dt = time.perf_counter() - t0
            out = sys.stdout.getvalue()
            assert dt < 1.0, f"turn {turn}: {dt:.3f}s"
            moved = {}
            for ln in out.splitlines():
                if not ln.strip():
                    continue
                _, r, c, d = ln.split()
                moved[(int(r), int(c))] = d
            me = [ants.destination(loc, d) for loc, d in moved.items()]
            me += [loc for loc in ants.my_ants() if loc not in moved]
            before = len(foods)
            held = set(me)
            foods = [
                f for f in foods if not any(ants.distance(a, f) <= 1 for a in held)
            ]
            eaten += before - len(foods)
            # enemy paces to keep headings/exorcism live
            foe = [ants.destination(foe[0], ("s", "e", "n", "w")[turn % 4])]
    finally:
        sys.stdout = old
    assert eaten > 0
    assert (9, 12) not in bot.remembered_hills
    assert bot.turn == 10


def test_adjacent_ant_never_steps_onto_food():
    # Engine rule pin (validate_orders ignores food-steps, do_gather
    # banks within spawnradius 1): an ant next to food must NOT step
    # onto it. Banking-from-adjacency is covered by the gather loops.
    ants = FakeAnts(me=((7, 8),), foods=((7, 9),))
    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    bot.do_turn(ants)
    for loc, d in ants.orders:
        assert ants.destination(loc, d) != (7, 9)
    assert any(ants.distance(a, (7, 9)) <= 1 for a in ants.my_ants())


def test_maze_wall_routes_to_food():
    # Vertical water wall with gaps top and bottom: the ant must BFS
    # around it and bank the food from adjacency within 30 turns.
    water = {(r, 7) for r in range(2, 13)}
    ants = FakeAnts(rows=15, cols=15, me=((7, 3),), foods=((7, 11),), water=water)
    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    me = [(7, 3)]
    foods = [(7, 11)]
    for _ in range(30):
        ants._foods = list(foods)
        ants._me = list(me)
        ants.orders = []
        bot.do_turn(ants)
        me = [ants.destination(loc, d) for loc, d in ants.orders]
        me += [loc for loc in ants._me if loc not in [o[0] for o in ants.orders]]
        held = set(me)
        foods = [f for f in foods if not any(ants.distance(a, f) <= 1 for a in held)]
        if not foods:
            break
    assert not foods


def test_fifteen_turn_gather_parity_with_greedy6():
    # Food-only map, 15 turns: without combat, ghosts, or late-phase
    # weights in play, Greedy15 must trace Greedy6 exactly. Any drift
    # in claims, routing, or explore would show up here.
    import random

    import Greedy6

    rng = random.Random(7)
    me = [(rng.randrange(20), rng.randrange(20)) for _ in range(8)]
    foods = [(rng.randrange(20), rng.randrange(20)) for _ in range(10)]

    def run(bot):
        ants = FakeAnts(me=tuple(me), foods=list(foods))
        bot.do_setup(ants)
        cur = list(me)
        remaining = list(foods)
        trace = []
        for _ in range(15):
            ants._foods = list(remaining)
            ants._me = list(cur)
            ants.orders = []
            bot.do_turn(ants)
            trace.append(sorted(ants.orders))
            cur = [ants.destination(loc, d) for loc, d in ants.orders]
            cur += [loc for loc in ants._me if loc not in [o[0] for o in ants.orders]]
            held = set(cur)
            remaining = [
                f for f in remaining if not any(ants.distance(a, f) <= 1 for a in held)
            ]
        return trace

    assert run(Greedy15.Greedy15()) == run(Greedy6.Greedy6())


def test_guard_quotas_n_plus_one():
    from Greedy15 import guard_quotas

    dist = manhattan(20, 20)
    # no foe in range: one holder.
    assert guard_quotas([(10, 10)], [(0, 0)], dist) == {(10, 10): 1}
    # two foes in range, one far: 2 + 1.
    foes = [(10, 12), (12, 10), (0, 0)]
    assert guard_quotas([(10, 10)], foes, dist) == {(10, 10): 3}
    # per-hill quotas.
    assert guard_quotas([(10, 10), (0, 0)], [(10, 12)], dist) == {
        (10, 10): 2,
        (0, 0): 1,
    }
    assert guard_quotas([], [(10, 12)], dist) == {}


def _guard_scenario():
    # One foe 9 from our hill threatens it; five ants, no food, no
    # remembered hills, foe out of combat range (9 > COMBAT_RANGE 8).
    ants = FakeAnts(me=((10, 6), (9, 6), (10, 9), (11, 10), (8, 8)))
    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    ants._foes = [(10, 19)]
    ants._my_hills = [(10, 10)]
    for loc in [(10, 9), (11, 10), (9, 11), (10, 11), (11, 11), (10, 7), (9, 7)]:
        bot.visits[loc] = 10
    bot.do_turn(ants)
    return ants.orders


def test_proportional_guard_frees_hunters():
    # N+1 drafts exactly two guards (holder marches east at the hill,
    # second screens east at the razer); the other three explore
    # north instead of piling onto the threatened hill.
    assert _guard_scenario() == [
        ((10, 6), "e"),
        ((9, 6), "e"),
        ((10, 9), "n"),
        ((11, 10), "n"),
        ((8, 8), "n"),
    ]


def test_multi_hill_quotas_independent():
    # Two threatened hills draft N+1 = 2 guards each; the fifth ant is
    # past both quotas and explores. A guard step onto a square another
    # guard already took falls through to explore (no collisions).
    ants = FakeAnts(me=((5, 4), (5, 6), (4, 5), (15, 14), (15, 16), (10, 10)))
    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    ants._foes = [(5, 14), (15, 6)]
    ants._my_hills = [(5, 5), (15, 15)]
    bot.do_turn(ants)
    assert ants.orders == [
        ((5, 4), "e"),
        ((5, 6), "e"),
        ((4, 5), "n"),
        ((15, 14), "e"),
        ((15, 16), "n"),
        ((10, 10), "n"),
    ]


def test_closing_threat_posts_one_holder():
    # Foe closes 15 -> 13 from our hill: threatened via the closing
    # rule with nobody in range, so the quota is exactly one holder.
    # Turn 0 is unthreatened (ants explore north); turn 1 posts the
    # holder east onto the hill while the rest keep exploring.
    import io

    from ants import Ants

    ants = Ants()
    ants.setup(
        "cols 30\nrows 30\nplayer_seed 3\nturntime 1000\nloadtime 3000\n"
        "viewradius2 77\nattackradius2 5\nspawnradius2 1\nturns 500\n"
    )
    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    me = [(10, 8), (9, 9), (11, 9), (8, 10)]
    out_turns = []
    old = sys.stdout
    try:
        for foe in ([(10, 25)], [(10, 23)]):
            lines = [f"a {r} {c} 0" for r, c in me]
            lines += [f"a {r} {c} 1" for r, c in foe]
            lines.append("h 10 10 0")
            ants.update("\n".join(lines))
            sys.stdout = io.StringIO()
            bot.do_turn(ants)
            out = sys.stdout.getvalue()
            out_turns.append(out)
            moved = {}
            for ln in out.splitlines():
                if ln.strip():
                    _, r, c, d = ln.split()
                    moved[(int(r), int(c))] = d
            me = [ants.destination(loc, d) for loc, d in moved.items()]
            me += [loc for loc in ants.my_ants() if loc not in moved]
    finally:
        sys.stdout = old
    turn1 = [ln for ln in out_turns[1].splitlines() if ln.strip()]
    assert turn1 == ["o 9 8 n", "o 8 9 n", "o 10 9 e", "o 7 10 n"]


def test_attack_radius_variants_no_crash():
    # Engine maps configure attackradius2; the combat core must run
    # sane at both extremes without crashing.
    for radius in (1, 9):
        ants = FakeAnts(me=((10, 10), (9, 9)), foes=((10, 12), (12, 10)))
        ants.attackradius2 = radius
        bot = Greedy15.Greedy15()
        bot.do_setup(ants)
        bot.do_turn(ants)
        assert len(ants.orders) == 2


def test_narrow_vision_keeps_distant_ghost():
    # viewradius2 8: a remembered hill 6 away is unseen, so even though
    # no live hill is reported, the ghost must be kept, not exorcised.
    from ants import Ants

    ants = Ants()
    ants.setup(
        "cols 30\nrows 30\nplayer_seed 5\nturntime 1000\nloadtime 3000\n"
        "viewradius2 8\nattackradius2 5\nspawnradius2 1\nturns 500\n"
    )
    ants.update("a 10 10 0\nh 10 10 0")
    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    bot.remembered_hills = {(16, 10)}
    import io

    old = sys.stdout
    sys.stdout = io.StringIO()
    try:
        bot.do_turn(ants)
    finally:
        sys.stdout = old
    assert (16, 10) in bot.remembered_hills


def test_kitchen_sink_integration():
    # Threats + combat + hills + food + water over 6 live turns:
    # every order legal, every turn in budget, food banked, the live
    # hill remembered.
    import io

    from ants import Ants

    ants = Ants()
    ants.setup(
        "cols 20\nrows 20\nplayer_seed 11\nturntime 1000\nloadtime 3000\n"
        "viewradius2 77\nattackradius2 5\nspawnradius2 1\nturns 500\n"
    )
    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    me = [(10, 10), (10, 11), (11, 10), (5, 5), (5, 6), (14, 14)]
    foes = [(10, 13), (4, 6), (16, 16)]
    foods = [(12, 12), (6, 6), (15, 5), (5, 15)]
    water = {(7, 7), (7, 8), (8, 7)}
    eaten = 0
    old = sys.stdout
    try:
        for _ in range(6):
            lines = [f"w {r} {c}" for r, c in water]
            lines += [f"a {r} {c} 0" for r, c in me]
            lines += [f"a {r} {c} 1" for r, c in foes]
            lines += [f"f {r} {c}" for r, c in foods]
            lines += ["h 10 10 0", "h 2 2 0", "h 18 18 1"]
            ants.update("\n".join(lines))
            sys.stdout = io.StringIO()
            t0 = time.perf_counter()
            bot.do_turn(ants)
            assert (time.perf_counter() - t0) < 1.0
            out = sys.stdout.getvalue()
            foodset = set(foods)
            moved = {}
            for ln in out.splitlines():
                if not ln.strip():
                    continue
                _, r, c, d = ln.split()
                dest = ants.destination((int(r), int(c)), d)
                assert ants.passable(dest)
                assert dest not in foodset
                moved[(int(r), int(c))] = d
            me = [ants.destination(loc, d) for loc, d in moved.items()]
            me += [loc for loc in ants.my_ants() if loc not in moved]
            held = set(me)
            before = len(foods)
            foods = [
                f for f in foods if not any(ants.distance(a, f) <= 1 for a in held)
            ]
            eaten += before - len(foods)
            foes = [
                ants.destination(foes[0], "w"),
                ants.destination(foes[1], "s"),
                ants.destination(foes[2], "n"),
            ]
    finally:
        sys.stdout = old
    assert eaten > 0
    assert (18, 18) in bot.remembered_hills


def test_big_battle_turn_in_budget():
    # 120v120 with hills and food on 60x60: one turn must finish in
    # 1000 ms (the entry requirement), with most ants ordered.
    me = tuple((r, c) for r in range(0, 60, 2) for c in range(0, 60, 2))[:120]
    foes = tuple((r, c) for r in range(1, 60, 2) for c in range(1, 60, 2))[:120]
    foods = tuple((r, c) for r in range(0, 60, 3) for c in range(0, 60, 3))[:200]
    ants = FakeAnts(
        rows=60,
        cols=60,
        me=me,
        foes=foes,
        foods=foods,
        foe_hills=((0, 0),),
        my_hills=((59, 59),),
    )
    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    t0 = time.perf_counter()
    bot.do_turn(ants)
    assert (time.perf_counter() - t0) < 1.0
    assert len(ants.orders) > 100


def test_captured_hill_discarded():
    # We stand on a remembered hill: it is ours now, drop it so the
    # muster does not march on our own hill.
    ants = FakeAnts(me=((5, 5),))
    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    bot.remembered_hills = {(5, 5), (15, 15)}
    bot.do_turn(ants)
    assert (5, 5) not in bot.remembered_hills


def test_zero_ants_no_crash():
    import io

    from ants import Ants

    ants = Ants()
    ants.setup(
        "cols 20\nrows 20\nplayer_seed 1\nturntime 1000\nloadtime 3000\n"
        "viewradius2 55\nattackradius2 5\nspawnradius2 1\nturns 100\n"
    )
    ants.update("")
    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    old = sys.stdout
    sys.stdout = io.StringIO()
    try:
        bot.do_turn(ants)
        out = sys.stdout.getvalue()
    finally:
        sys.stdout = old
    assert out.strip() == ""


def test_lone_ant_holds_vs_razer():
    # One ant next to a razer standing on our hill: the 1v1 is
    # refused (no strict edge, no backup), so the ant holds instead
    # of donating. Pins delineate doctrine at bot level.
    import io

    from ants import Ants

    ants = Ants()
    ants.setup(
        "cols 20\nrows 20\nplayer_seed 1\nturntime 1000\nloadtime 3000\n"
        "viewradius2 55\nattackradius2 5\nspawnradius2 1\nturns 100\n"
    )
    ants.update("a 10 11 0\na 10 10 1\nh 10 10 0")
    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    old = sys.stdout
    sys.stdout = io.StringIO()
    try:
        bot.do_turn(ants)
        out = sys.stdout.getvalue()
    finally:
        sys.stdout = old
    assert out.strip() == ""


def test_screen_then_kill_pursuit():
    # A razer marches west at our hill: guards screen forward of the
    # hill (abreast at col 11 by turn 2), then converge east onto the
    # razer for the strict-superiority kill. Pins the guard +
    # intercept + combat interplay end to end (stops before contact,
    # where the engine's battle resolution would take over).
    import io

    from ants import Ants

    ants = Ants()
    ants.setup(
        "cols 20\nrows 20\nplayer_seed 1\nturntime 1000\nloadtime 3000\n"
        "viewradius2 77\nattackradius2 5\nspawnradius2 1\nturns 100\n"
    )
    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    me = [(10, 8), (9, 8), (11, 8)]
    foe = (10, 16)
    trace = []
    old = sys.stdout
    try:
        for _ in range(5):
            lines = [f"a {r} {c} 0" for r, c in me]
            lines += [f"a {foe[0]} {foe[1]} 1", "h 10 10 0"]
            ants.update("\n".join(lines))
            sys.stdout = io.StringIO()
            bot.do_turn(ants)
            out = sys.stdout.getvalue()
            moved = {}
            for ln in out.splitlines():
                if ln.strip():
                    _, r, c, d = ln.split()
                    moved[(int(r), int(c))] = d
            me = [ants.destination(loc, d) for loc, d in moved.items()]
            me += [loc for loc in ants.my_ants() if loc not in moved]
            trace.append(sorted(me))
            foe = (foe[0], foe[1] - 1)
    finally:
        sys.stdout = old
    assert trace == [
        [(9, 9), (10, 9), (11, 9)],
        [(9, 10), (10, 10), (11, 10)],
        [(9, 11), (10, 11), (11, 11)],
        [(9, 12), (10, 10), (11, 12)],
        [(9, 13), (10, 11), (11, 13)],
    ]


def test_random_multiturn_campaign():
    # 5 seeded random maps x 5 live turns with orders applied, food
    # banked from adjacency, foes wandering, hills razed mid-game:
    # every turn legal, in budget, and productive across turns.
    import io
    import random

    from ants import Ants

    rng = random.Random(5150)
    for trial in range(5):
        rows = cols = 20
        ants = Ants()
        ants.setup(
            f"cols {cols}\nrows {rows}\nplayer_seed 1\nturntime 1000\n"
            "loadtime 3000\nviewradius2 55\nattackradius2 5\n"
            "spawnradius2 1\nturns 500\n"
        )
        water = {(rng.randrange(rows), rng.randrange(cols)) for _ in range(15)}

        def free(_rows=rows, _cols=cols):
            return (rng.randrange(_rows), rng.randrange(_cols))

        me = [free() for _ in range(rng.randint(3, 8))]
        foes = [free() for _ in range(rng.randint(1, 6))]
        foods = [free() for _ in range(rng.randint(3, 8))]
        hill = free()
        eaten = 0
        bot = Greedy15.Greedy15()
        bot.do_setup(ants)
        old = sys.stdout
        try:
            for turn in range(5):
                lines = [f"w {r} {c}" for r, c in water]
                lines += [f"a {r} {c} 0" for r, c in me]
                lines += [f"a {r} {c} 1" for r, c in foes]
                lines += [f"f {r} {c}" for r, c in foods]
                lines += ["h 2 2 0"]
                if turn < 2:
                    lines.append(f"h {hill[0]} {hill[1]} 1")
                ants.update("\n".join(lines))
                sys.stdout = io.StringIO()
                t0 = time.perf_counter()
                bot.do_turn(ants)
                assert (time.perf_counter() - t0) < 1.0, (trial, turn)
                out = sys.stdout.getvalue()
                foodset = set(ants.food())
                moved = {}
                for ln in out.splitlines():
                    if not ln.strip():
                        continue
                    _, r, c, d = ln.split()
                    dest = ants.destination((int(r), int(c)), d)
                    assert ants.passable(dest), (trial, turn, ln)
                    assert dest not in foodset, (trial, turn, ln)
                    moved[(int(r), int(c))] = d
                me = [ants.destination(loc, d) for loc, d in moved.items()]
                me += [loc for loc in ants.my_ants() if loc not in moved]
                held = set(me)
                before = len(foods)
                foods = [
                    f for f in foods if not any(ants.distance(a, f) <= 1 for a in held)
                ]
                eaten += before - len(foods)
                foes = [ants.destination(f, rng.choice("nesw")) for f in foes]
        finally:
            sys.stdout = old
        assert eaten > 0, f"trial {trial} banked nothing"


def test_largest_map_scale_in_budget():
    # 150x150 (largest real maps) with maze water and 150 ants a
    # side: one turn must finish in 1000 ms with nearly all ants
    # ordered. Seeded, deterministic.
    import random

    rng = random.Random(4)
    rows = cols = 150
    water = frozenset((rng.randrange(rows), rng.randrange(cols)) for _ in range(1500))
    me = tuple((rng.randrange(rows), rng.randrange(cols)) for _ in range(150))
    foes = tuple((rng.randrange(rows), rng.randrange(cols)) for _ in range(150))
    foods = tuple((rng.randrange(rows), rng.randrange(cols)) for _ in range(100))
    ants = FakeAnts(
        rows=rows,
        cols=cols,
        me=me,
        foes=foes,
        foods=foods,
        foe_hills=((0, 0),),
        my_hills=((149, 149),),
        water=water,
    )
    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    t0 = time.perf_counter()
    bot.do_turn(ants)
    assert (time.perf_counter() - t0) < 1.0
    assert len(ants.orders) > 130


def test_guard_quota_invariant_fuzz():
    # 40 random guard configurations: no hill ever drafts past its
    # N+1 quota, and total guards stay within the quota sum.
    import random

    from Greedy15 import guard_quotas

    rng = random.Random(31337)
    for trial in range(40):
        me = [(rng.randrange(20), rng.randrange(20)) for _ in range(rng.randint(1, 10))]
        foes = [
            (rng.randrange(20), rng.randrange(20)) for _ in range(rng.randint(1, 6))
        ]
        hills = [
            (rng.randrange(20), rng.randrange(20)) for _ in range(rng.randint(1, 2))
        ]
        ants = FakeAnts(me=tuple(me))
        ants._foes = list(foes)
        ants._my_hills = list(hills)
        bot = Greedy15.Greedy15()
        bot.do_setup(ants)
        bot.do_turn(ants)
        # Fresh bot per trial: no headings, so the closing rule never
        # fires and threatened == static-10 here, matching the bot.
        threatened = [
            h for h in ants.my_hills() if any(ants.distance(h, e) <= 10 for e in foes)
        ]
        quotas = guard_quotas(threatened, foes, ants.distance)
        for h, used in bot.last_guard_count.items():
            assert used <= quotas[h], (trial, h, used, quotas[h])
        assert sum(bot.last_guard_count.values()) <= sum(quotas.values()), trial


def test_manifest_matches():
    path = os.path.join(os.path.dirname(__file__), "Greedy15.bot")
    with open(path) as fh:
        assert fh.read().strip() == "python Greedy15.py"


# --- real-engine protocol scenario ---

_SETUP = (
    "cols 30\nrows 30\nplayer_seed 7\nturntime 1000\nloadtime 3000\n"
    "viewradius2 55\nattackradius2 5\nspawnradius2 1\nturns 500\n"
)


def _engine_turn(extra_lines):
    from ants import Ants

    ants = Ants()
    ants.setup(_SETUP)
    ants.update("\n".join(extra_lines))
    return ants


def _run_bot(ants):
    import io

    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        bot.do_turn(ants)
    finally:
        sys.stdout = old
    return bot, buf.getvalue()


def test_engine_protocol_orders_wellformed():
    ants = _engine_turn(
        [
            "w 3 3",
            "w 3 4",
            "f 5 5",
            "f 20 20",
            "a 10 10 0",
            "a 11 10 0",
            "a 10 12 1",
            "h 10 10 0",
            "h 0 0 1",
        ]
    )
    _, out = _run_bot(ants)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert lines, "bot must issue at least one order"
    seen_from = set()
    for ln in lines:
        parts = ln.split()
        assert parts[0] == "o" and len(parts) == 4, ln
        r, c, d = int(parts[1]), int(parts[2]), parts[3]
        assert d in ("n", "e", "s", "w"), ln
        assert (r, c) not in seen_from, ln  # one order per ant
        seen_from.add((r, c))
        assert ants.passable(ants.destination((r, c), d)), ln


def test_engine_exorcism_over_turns():
    # turn 1 sees a live hill; turn 2 the square is visible but empty.
    turn1 = ["a 10 10 0", "h 10 12 1"]
    turn2 = ["a 10 10 0"]
    from ants import Ants

    ants = Ants()
    ants.setup(_SETUP)
    import io

    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    old = sys.stdout
    try:
        for lines in (turn1, turn2):
            ants.update("\n".join(lines))
            sys.stdout = io.StringIO()
            bot.do_turn(ants)
    finally:
        sys.stdout = old
    assert (10, 12) not in bot.remembered_hills


def test_engine_maze_perf():
    water = [f"w {r} 15" for r in range(30) if r != 15]
    me = [f"a {5 + i // 8} {5 + i % 8} 0" for i in range(40)]
    foes = [f"a {20 + i // 8} {20 + i % 8} 1" for i in range(30)]
    foods = [f"f {r} {c}" for r in range(0, 30, 4) for c in range(0, 30, 4)]
    ants = _engine_turn(water + me + foes + foods + ["h 0 0 1", "h 29 29 0"])
    import io

    bot = Greedy15.Greedy15()
    bot.do_setup(ants)
    old = sys.stdout
    sys.stdout = io.StringIO()
    try:
        t0 = time.perf_counter()
        bot.do_turn(ants)
    finally:
        sys.stdout = old
    assert (time.perf_counter() - t0) < 1.0
