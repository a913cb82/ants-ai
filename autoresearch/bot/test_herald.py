#!/usr/bin/env python
"""Herald (turn-scaled muster quorum with standard rally) tests.

Headline mechanism, new from the Understudy base: the muster march
needs a quorum that grows as the war runs on (2 + turn // 150, capped
at 6). Early, pairs still race hills for tempo; late, only a massed
pack marches, so the army stops donating ones and twos into defenders.
Quorum-short ants do not scatter: they rally to the army standard (the
medoid ant) and stay massed until enough have answered the call.
Triumph relaxes the late quorum to the pair-race while ahead on
hills, so a winning army closes out; commitment holds a march already
under way with one fewer ant, so food sprouts do not yo-yo the army.
Food, threatened-hill guard, challenger rotation, safety, and walk-off
match Understudy; only the march is gated, and a suppressed turn records no
challenge (so the next march picks open, never a false rotation).
"""

import os
import sys
import time
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Herald as HD  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20


def torus(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


class FakeAnts:
    def __init__(
        self,
        ants: list[Loc],
        foods: list[Loc],
        enemies: list[Loc],
        homes: list[Loc],
        hills: list[Loc],
    ) -> None:
        self._ants = list(ants)
        self._foods = list(foods)
        self._enemies = list(enemies)
        self._homes = list(homes)
        self._hills = list(hills)
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
        return True

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
    foods: list[Loc] | None = None,
    enemies: list[Loc] | None = None,
) -> FakeAnts:
    fake = FakeAnts(ants, foods or [], enemies or [], homes, hills)
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
    bot = HD.Herald()
    bot.do_setup(cast(Any, FakeAnts([], [], [], [], [])))
    return bot


def test_quorum_boundary_wires_through_do_turn() -> None:
    # Turn 149 (quorum 2): two idlers march. Turn 150 (quorum 3): a
    # fresh pair rallies instead. The counter drives the gate.
    early = fresh_bot()
    early.turn = 148
    turn1 = run_turn(early, [A, B], [H1], HOME)
    assert early.turn == 149
    assert turn1.orders[0] == (A, "w")
    assert early.last_target == H1
    late = fresh_bot()
    late.turn = 149
    run_turn(late, [A, B], [H1], HOME)
    assert late.turn == 150
    assert late.last_target is None


def test_quorum_grows_with_turn() -> None:
    assert HD.muster_quorum(0) == 2
    assert HD.muster_quorum(1) == 2
    assert HD.muster_quorum(149) == 2
    assert HD.muster_quorum(150) == 3
    assert HD.muster_quorum(300) == 4
    assert HD.muster_quorum(600) == 6
    assert HD.muster_quorum(9999) == 6


def test_march_allowed_needs_quorum() -> None:
    assert HD.march_allowed(2, 1) is True
    assert HD.march_allowed(1, 1) is False
    assert HD.march_allowed(6, 900) is True
    assert HD.march_allowed(5, 900) is False
    assert HD.march_allowed(0, 0) is False


def test_march_allowed_relaxes_to_pair_when_ahead() -> None:
    # Triumph: ahead on hills, the late quorum relaxes to the early
    # pair-race, so a winning army closes out instead of massing.
    assert HD.march_allowed(2, 900, ahead=True) is True
    assert HD.march_allowed(1, 900, ahead=True) is False
    assert HD.march_allowed(2, 900, ahead=False) is False


def test_march_allowed_commitment_holds_by_one() -> None:
    # Commitment: a march already under way holds with one fewer ant,
    # so the army does not yo-yo between marching and rallying.
    assert HD.march_allowed(1, 1, committed=True) is True
    assert HD.march_allowed(0, 1, committed=True) is False
    assert HD.march_allowed(5, 900, committed=True) is True
    assert HD.march_allowed(4, 900, committed=True) is False
    assert HD.march_allowed(5, 900, committed=False) is False


def test_same_turn_is_deterministic() -> None:
    # No randomness anywhere: two fresh bots issue identical orders.
    ants = [(10, 10), (10, 12), (0, 0), (5, 5)]
    first = run_turn(fresh_bot(), ants, [H1, H2], HOME, foods=[(10, 11)])
    second = run_turn(fresh_bot(), ants, [H1, H2], HOME, foods=[(10, 11)])
    assert first.orders == second.orders


def test_fuzz_never_crashes_and_orders_stay_valid() -> None:
    # Deterministic fuzz across 300 scrambled turns (teleporting
    # armies stress rotation, pruning, and quorum bookkeeping): every
    # turn completes, origins are live ants, and no destination doubles.
    import random

    rng = random.Random(12345)
    bot = fresh_bot()

    def spot() -> Loc:
        return (rng.randrange(ROWS), rng.randrange(COLS))

    cells = [(r, c) for r in range(ROWS) for c in range(COLS)]
    for turn_no in range(300):
        # Ants never stack in a real game (collisions kill), so deal
        # unique squares for both armies. Every tenth turn fields a
        # big army to stress the medoid and BFS budgets scrambled.
        big = turn_no % 10 == 9
        n_ants = rng.randint(0, 40) if big else rng.randint(0, 8)
        n_foes = rng.randint(0, 20) if big else rng.randint(0, 5)
        dealt = rng.sample(cells, n_ants + n_foes)
        ants = dealt[:n_ants]
        enemies = dealt[n_ants:]
        hills = [spot() for _ in range(rng.randint(0, 3))]
        homes = [spot() for _ in range(rng.randint(0, 2))]
        foods = [spot() for _ in range(rng.randint(0, 4))]
        if rng.random() < 0.3:
            bot.turn = rng.choice([0, 1, 149, 150, 899, 1200])
        fake = run_turn(bot, ants, hills, homes, foods=foods, enemies=enemies)
        origins = [o for o, _ in fake.orders]
        assert all(o in ants for o in origins)
        assert len(set(origins)) == len(origins)
        dests = [fake.destination(o, d) for o, d in fake.orders]
        assert len(set(dests)) == len(dests)
        # Bookkeeping invariant: a recorded target is always a hill
        # we still remember (suppression records none at all).
        assert bot.last_target is None or bot.last_target in bot.remembered_hills


def test_marching_matches_understudy_across_states() -> None:
    # Differential lock: on turn 1 with no food (quorum met), Herald
    # walks the exact base code path, so orders equal Understudy's
    # across 60 scrambled states. Suppression is the only difference.
    import random

    import Understudy as US

    rng = random.Random(777)
    cells = [(r, c) for r in range(ROWS) for c in range(COLS)]
    for _ in range(60):
        n_ants = rng.randint(2, 6)
        n_foes = rng.randint(0, 4)
        dealt = rng.sample(cells, n_ants + n_foes)
        ants = dealt[:n_ants]
        enemies = dealt[n_ants:]
        hills = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(2)]
        homes = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(1)]
        herald = fresh_bot()
        base = US.Understudy()
        base.do_setup(cast(Any, FakeAnts([], [], [], [], [])))
        mine = run_turn(herald, ants, hills, homes, enemies=enemies)
        theirs = run_turn(base, ants, hills, homes, enemies=enemies)
        assert mine.orders == theirs.orders


def test_manifest_matches_entry() -> None:
    # The .bot manifest must hold exactly one line: python Herald.py.
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "Herald.bot")) as fh:
        assert fh.read() == "python Herald.py\n"


def test_rally_falls_back_when_standard_blocked() -> None:
    # The wing's rally step onto the standard is occupied, so it
    # explores instead; the far ant still gathers on the standard.
    bot = fresh_bot()
    bot.turn = 899
    ants = [(10, 10), (10, 11), (10, 13)]
    turn1 = run_turn(bot, ants, [H1], HOME)
    assert set(turn1.orders) == {
        ((10, 10), "n"),
        ((10, 11), "n"),
        ((10, 13), "w"),
    }
    assert bot.last_target is None


def test_rally_steps_shorten_distance_to_standard() -> None:
    # Convergence contract: every rally step lands exactly one step
    # closer to the standard along a shortest path.
    bot = fresh_bot()
    bot.turn = 899
    ants = [(8, 8), (8, 12), (12, 8), (12, 12)]
    assert HD.rally_point(ants, torus) == (8, 8)
    turn1 = run_turn(bot, ants, [H1], HOME)
    assert bot.last_target is None
    for origin, direction in turn1.orders:
        dest = FakeAnts(ants, [], [], HOME, [H1]).destination(origin, direction)
        if origin == (8, 8):
            continue  # the standard itself explores
        assert torus(dest, (8, 8)) == torus(origin, (8, 8)) - 1


def test_rally_point_is_medoid() -> None:
    # B minimizes the distance sum, so the standard stands on B.
    ants = [(10, 10), (10, 12), (10, 14)]
    assert HD.rally_point(ants, torus) == (10, 12)


def test_rally_point_tie_breaks_by_order() -> None:
    # A and B tie on distance sums; list order wins.
    assert HD.rally_point([A, B], torus) == A
    assert HD.rally_point([B, A], torus) == B


def test_rally_point_empty_is_none() -> None:
    assert HD.rally_point([], torus) is None


def test_rally_point_single_ant_is_itself() -> None:
    assert HD.rally_point([A], torus) == A


def test_early_turn_marches_like_understudy() -> None:
    # Quorum 2 with two ants: the nearest ant challenges H1, as base.
    bot = fresh_bot()
    turn1 = run_turn(bot, [A, B], [H1], HOME)
    assert turn1.orders[0] == (A, "w")
    assert bot.last_challenger.get(H1) == A


def test_rotation_is_per_hill_when_marching() -> None:
    # H1 failed with A, but H2 is fresh: A still answers H2
    # (reinforce) while only B challenges H1 -- base parity.
    bot = fresh_bot()
    turn1 = run_turn(bot, [A, B], [H1], HOME)
    ants2 = [moved_to(turn1, A), moved_to(turn1, B)]
    turn2 = run_turn(bot, ants2, [H1, H2], HOME)
    assert bot.last_challenger.get(H1) == ants2[1]
    assert (ants2[0], "w") not in turn2.orders
    assert ants2[0] in [o for o, _ in turn2.orders]
    assert ants2[1] in [o for o, _ in turn2.orders]


def test_captured_hill_prunes_and_retargets() -> None:
    # Turn 1 marches H1; turn 2 finds A standing on razed H1 with only
    # H2 reported: H1 is forgotten, its challenger record pruned, and
    # the march retargets H2.
    bot = fresh_bot()
    turn1 = run_turn(bot, [A, B], [H1, H2], HOME)
    assert bot.last_target == H1
    a2 = moved_to(turn1, A)
    assert a2 != H1  # sanity: challenger still en route
    turn2 = run_turn(bot, [H1, B], [H2], HOME)
    assert H1 not in bot.last_challenger
    assert bot.last_target == H2
    assert len(turn2.orders) == 2
    # Open hill, quorum met: turn 1 challenges with A, turn 2 still
    # held rotates to B, exactly the base behavior.
    bot = fresh_bot()
    turn1 = run_turn(bot, [A, B], [H1], HOME)
    assert turn1.orders[0] == (A, "w")
    ants2 = [moved_to(turn1, A), moved_to(turn1, B)]
    assert ants2[0] == (10, 9)
    turn2 = run_turn(bot, ants2, [H1], HOME)
    assert bot.last_challenger.get(H1) == ants2[1]
    assert (ants2[0], "w") not in turn2.orders


def test_quorum_short_rallies_to_standard() -> None:
    # Late war (quorum 6) with three idle ants: nobody marches H1.
    # The wings step toward the medoid B=(10,12); the standard
    # itself explores north; no challenge is recorded.
    bot = fresh_bot()
    bot.turn = 899  # next do_turn is 900 -> quorum 6
    ants = [(10, 10), (10, 12), (10, 14)]
    turn1 = run_turn(bot, ants, [H1], HOME)
    assert set(turn1.orders) == {
        ((10, 10), "e"),
        ((10, 12), "n"),
        ((10, 14), "w"),
    }
    assert bot.last_target is None
    assert bot.last_challenger == {}


def test_commitment_holds_march_despite_harvest() -> None:
    # Turn 1 marches the pair; turn 2 sprouts food that pulls one ant
    # onto harvest, but the committed march holds (need drops by one)
    # instead of rallying the army home.
    bot = fresh_bot()
    turn1 = run_turn(bot, [A, B], [H1], HOME)
    assert turn1.orders[0] == (A, "w")
    assert bot.last_target == H1
    a2 = moved_to(turn1, A)
    b2 = moved_to(turn1, B)
    turn2 = run_turn(bot, [a2, b2], [H1], HOME, foods=[b2])
    assert bot.last_target == H1
    assert len(turn2.orders) == 2


def test_suppressed_turn_records_no_false_rotation() -> None:
    # After a suppressed turn the next quorum-met march picks the
    # plain nearest ant, not a rotated understudy: suppression is
    # waiting, not a failed challenge.
    bot = fresh_bot()
    bot.turn = 899
    run_turn(bot, [A, B], [H1], HOME)
    assert bot.last_target is None
    bot.turn = 0
    turn2 = run_turn(bot, [A, B], [H1], HOME)
    assert turn2.orders[0] == (A, "w")
    assert bot.last_challenger.get(H1) == A


def test_quorum_met_late_still_marches() -> None:
    # Eight idle ants answer the late quorum of 6: the nearest
    # ant still challenges H1 at turn 900.
    bot = fresh_bot()
    bot.turn = 899
    ants = [(10, 10), (10, 12), (10, 14), (0, 0), (0, 5), (5, 5), (5, 6), (5, 7)]
    turn1 = run_turn(bot, ants, [H1], HOME)
    assert turn1.orders[0] == ((10, 10), "w")
    assert bot.last_challenger.get(H1) == (10, 10)
    assert bot.last_target == H1


def test_ahead_late_pair_still_races() -> None:
    # Two home hills against one remembered foe: ahead, so the late
    # pair races H1 instead of rallying -- triumph closes out.
    bot = fresh_bot()
    bot.turn = 899
    turn1 = run_turn(bot, [A, B], [H1], [(10, 15), (0, 10)])
    assert turn1.orders[0] == (A, "w")
    assert bot.last_challenger.get(H1) == A
    assert bot.last_target == H1


def test_behind_late_pair_rallies() -> None:
    # One home hill against two remembered foes: behind, so the late
    # pair rallies to the standard and records no challenge.
    bot = fresh_bot()
    bot.turn = 899
    turn1 = run_turn(bot, [A, B], [H1, H2], HOME)
    assert bot.last_target is None
    assert bot.last_challenger == {}
    assert len(turn1.orders) == 2


def test_suppression_keeps_food_harvest() -> None:
    # Late and quorum-short, but the harvester still steps toward its
    # food while the idle ant rallies; the march stays suppressed.
    bot = fresh_bot()
    bot.turn = 899
    turn1 = run_turn(bot, [(10, 10), (0, 0)], [H1], HOME, foods=[(10, 11)])
    assert ((10, 10), "e") in turn1.orders
    assert (0, 0) in [o for o, _ in turn1.orders]
    assert bot.last_target is None


def test_suppression_keeps_home_guard() -> None:
    # A raider at (10,14) threatens home (10,15): the guard holds its
    # hill (no safe step off next to the raider) even though the H1
    # march is gated, while the harvester still works.
    bot = fresh_bot()
    bot.turn = 899
    turn1 = run_turn(bot, [(10, 10), (0, 0)], [H1], HOME, enemies=[(10, 14)])
    assert ((10, 10), "e") in turn1.orders
    assert (0, 0) in [o for o, _ in turn1.orders]
    assert bot.last_target is None


def test_saga_rotate_capture_wait_mass() -> None:
    # Five phases, one story: race H1, rotate on failure, capture H1
    # and retarget H2, wait out the late quorum short-handed, then
    # mass-march H2 with reinforcements.
    bot = fresh_bot()
    turn1 = run_turn(bot, [A, B], [H1], HOME)
    assert turn1.orders[0] == (A, "w")
    ants2 = [moved_to(turn1, A), moved_to(turn1, B)]
    assert ants2 == [(10, 9), (19, 0)]
    turn2 = run_turn(bot, ants2, [H1], HOME)
    assert bot.last_challenger.get(H1) == ants2[1]
    assert (ants2[0], "w") not in turn2.orders
    turn3 = run_turn(bot, [H1, ants2[1]], [H2], HOME)
    assert H1 not in bot.last_challenger
    assert bot.last_target == H2
    assert len(turn3.orders) == 2
    bot.turn = 899
    turn4 = run_turn(bot, ants2, [H2], HOME)
    assert len(turn4.orders) == 2
    assert bot.last_target is None
    mass = ants2 + [(10, 12), (10, 14), (0, 5), (5, 5), (5, 6), (5, 7)]
    turn5 = run_turn(bot, mass, [H2], HOME)
    assert ((19, 0), "w") in turn5.orders
    assert bot.last_challenger.get(H2) == (19, 0)
    assert bot.last_target == H2


def test_war_arc_race_wait_mass() -> None:
    # The whole Herald story in three turns: an early pair races,
    # the late remnant rallies instead of donating, and late
    # reinforcements mass-march with the plain nearest challenger.
    bot = fresh_bot()
    turn1 = run_turn(bot, [A, B], [H1], HOME)
    assert turn1.orders[0] == (A, "w")
    ants2 = [moved_to(turn1, A), moved_to(turn1, B)]
    bot.turn = 899
    waiting = run_turn(bot, ants2, [H1], HOME)
    assert len(waiting.orders) == 2
    assert bot.last_target is None
    # Waiting is not a failed challenge: the old record stands, but
    # with no target the next march still picks open (see below).
    assert bot.last_challenger.get(H1) == A
    mass = ants2 + [(10, 12), (10, 14), (0, 5), (5, 5), (5, 6), (5, 7)]
    charge = run_turn(bot, mass, [H1], HOME)
    assert charge.orders[0] == (ants2[0], "w")
    assert bot.last_challenger.get(H1) == ants2[0]
    assert bot.last_target == H1


def test_medoid_stays_fast_at_army_scale() -> None:
    # A 300-ant late army: the medoid still resolves quickly.
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(300)]
    start = time.perf_counter()
    assert HD.rally_point(ants, torus) is not None
    assert time.perf_counter() - start < 0.2


def test_engine_loop_smoke() -> None:
    # The full stdin/stdout loop: setup plus two turns run as a
    # subprocess, so wiring (setup/update/orders/go) is exercised.
    import subprocess

    here = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(here, "Herald.py")
    setup = (
        "turntime 1000\nloadtime 1000\nturns 500\nrows 20\ncols 20\n"
        "viewradius2 77\nattackradius2 5\nspawnradius2 1\n"
        "player_seed 1\nready\n"
    )
    turn = "a 10 10 0\na 0 0 0\nh 10 15 0\nh 10 5 1\nf 10 12\ngo\n"
    proc = subprocess.Popen(
        [sys.executable, script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        # The engine loop never exits on EOF, so collect the three
        # go-lines' worth of output, then stop the bot.
        out, err = proc.communicate(input=setup + turn + turn, timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
    assert "Traceback" not in err
    assert out.count("go") >= 3  # setup ack plus two turns
    assert "o 10 10 e" in out  # harvester closes on its food


def test_longer_war_smoke() -> None:
    # Six turns through the real Ants parser: spawning ants, a food
    # wave, and a newly sighted enemy hill. The bot must keep
    # answering every turn with no traceback.
    import subprocess

    here = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(here, "Herald.py")
    setup = (
        "turntime 1000\nloadtime 1000\nturns 500\nrows 20\ncols 20\n"
        "viewradius2 77\nattackradius2 5\nspawnradius2 1\n"
        "player_seed 1\nready\n"
    )
    turns = [
        "a 10 10 0\nh 10 15 0\ngo\n",
        "a 10 10 0\na 10 15 0\nh 10 15 0\nf 5 5\ngo\n",
        "a 10 9 0\na 10 15 0\nh 10 15 0\nh 10 5 1\nf 5 5\ngo\n",
        "a 10 8 0\na 9 15 0\nh 10 15 0\nh 10 5 1\nf 5 5\ngo\n",
        "a 10 7 0\na 9 14 0\na 10 15 0\nh 10 15 0\nh 10 5 1\ngo\n",
        "a 10 6 0\na 9 13 0\na 10 15 0\nh 10 15 0\nh 10 5 1\ngo\n",
    ]
    proc = subprocess.Popen(
        [sys.executable, script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        out, err = proc.communicate(input=setup + "".join(turns), timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
    assert "Traceback" not in err
    assert out.count("go") >= 7  # setup ack plus six turns
    assert "o " in out


def test_continuous_war_arc_marches_and_gathers() -> None:
    # A continuous 160-turn arc (no teleports): spawning ants, food
    # waves, hills revealed mid-war, and the real turn counter growing
    # through the 150-turn quorum step. The colony marches, gathers,
    # and tracks without stuck states or bookkeeping drift.
    bot = fresh_bot()
    ants: list[Loc] = [(10, 15)]
    homes: list[Loc] = [(10, 15)]
    foods: list[Loc] = []
    marched: list[Loc | None] = []
    for turn in range(1, 161):
        hills = []
        if turn >= 5:
            hills.append(H1)
        if turn >= 15:
            hills.append(H2)
        if turn % 5 == 3:
            foods += [(4, 4), (15, 15)]
            foods = sorted(set(foods))
        fake = run_turn(bot, ants, hills, homes, foods=foods)
        moves = {o: fake.destination(o, d) for o, d in fake.orders}
        ants = [moves.get(a, a) for a in ants]
        foods = [f for f in foods if all(torus(a, f) > 1 for a in ants)]
        if turn % 3 == 0:
            for cand in [homes[0]] + [
                fake.destination(homes[0], d) for d in ("n", "e", "s", "w")
            ]:
                if cand not in ants:
                    ants.append(cand)
                    break
        marched.append(bot.last_target)
    assert bot.turn == 160
    # Tracking never drifts: only ever-reported hills are remembered
    # (a stood-on hill is correctly pruned even while reported).
    assert set(bot.remembered_hills) <= {H1, H2}
    assert H1 in marched or H2 in marched  # the colony marched
    assert len(ants) > 1  # spawning outpaced losses (no combat here)


def test_setup_resets_turn_counter() -> None:
    bot = fresh_bot()
    run_turn(bot, [A], [], HOME)
    assert bot.turn == 1
    bot.do_setup(cast(Any, FakeAnts([], [], [], [], [])))
    assert bot.turn == 0
    assert bot.last_target is None


def test_empty_army_turn_is_quiet() -> None:
    bot = fresh_bot()
    fake = run_turn(bot, [], [H1], HOME)
    assert fake.orders == []
    assert bot.last_target is None


def test_midgame_mixed_priorities() -> None:
    # Food, a threatened home, and a remembered hill together: the
    # harvester harvests, the guard holds its hill (every step is
    # unsafe next to the raider), and the quorum-short idler rallies.
    bot = fresh_bot()
    bot.turn = 899
    ants = [(10, 10), (10, 15), (0, 0)]
    turn1 = run_turn(bot, ants, [H1], [(10, 15)], foods=[(10, 11)], enemies=[(10, 14)])
    assert set(turn1.orders) == {((10, 10), "e"), ((0, 0), "n")}
    assert bot.last_target is None  # H1 march stays suppressed


def test_denial_claims_hold_while_remainder_rallies() -> None:
    # Contested cluster late: denial still posts its two claimants on
    # the two nearest foods while the quorum-short remainder rallies
    # instead of feeding the contest.
    bot = fresh_bot()
    bot.turn = 899
    ants = [(5, 2), (5, 4), (0, 0)]
    foods = [(5, 5), (5, 6)]
    enemies = [(5, 11), (5, 12), (5, 13)]
    turn1 = run_turn(bot, ants, [H1], HOME, foods=foods, enemies=enemies)
    assert ((5, 4), "e") in turn1.orders
    assert ((5, 2), "e") in turn1.orders
    assert (0, 0) in [o for o, _ in turn1.orders]
    assert bot.last_target is None


def test_lone_idler_refuses_late_donation_march() -> None:
    # Five harvesters work their foods while one idler stands near a
    # defended hill far from home late in the war: the base would
    # march the lone ant onto the defender, but the quorum holds it
    # back at the standard instead.
    HILL: Loc = (2, 10)
    bot = fresh_bot()
    bot.turn = 899
    ants = [(0, 0), (0, 2), (0, 4), (0, 6), (0, 8), (2, 5)]
    foods = [(0, 1), (0, 3), (0, 5), (0, 7), (0, 9)]
    turn1 = run_turn(bot, ants, [HILL], HOME, foods=foods, enemies=[(2, 11)])
    assert len(turn1.orders) == 6
    assert ((2, 5), "n") in turn1.orders  # rallies, never marches HILL
    assert ((2, 5), "e") not in turn1.orders
    assert bot.last_target is None


def test_contrast_base_marches_where_herald_holds() -> None:
    # Same late board for both bots: Understudy marches the lone idler
    # at the defended hill (donation), Herald holds it back. The
    # difference is the whole idea.
    import Understudy as US

    HILL: Loc = (2, 10)
    ants = [(0, 0), (0, 2), (0, 4), (0, 6), (0, 8), (2, 5)]
    foods = [(0, 1), (0, 3), (0, 5), (0, 7), (0, 9)]
    herald = fresh_bot()
    herald.turn = 899
    mine = run_turn(herald, ants, [HILL], HOME, foods=foods, enemies=[(2, 11)])
    base = US.Understudy()
    base.do_setup(cast(Any, FakeAnts([], [], [], [], [])))
    theirs = run_turn(base, ants, [HILL], HOME, foods=foods, enemies=[(2, 11)])
    assert ((2, 5), "e") in theirs.orders  # base feeds the defender
    assert ((2, 5), "e") not in mine.orders  # herald masses instead
    assert herald.last_target is None


def test_all_harvesting_stays_suppressed() -> None:
    # Nobody mission-free late: both ants harvest, the march stays
    # suppressed, and the unused standard changes nothing.
    bot = fresh_bot()
    bot.turn = 899
    turn1 = run_turn(bot, [(0, 0), (0, 2)], [H1], HOME, foods=[(0, 1), (0, 3)])
    assert set(turn1.orders) == {((0, 0), "e"), ((0, 2), "e")}
    assert bot.last_target is None


def test_massing_never_donates_next_to_foe() -> None:
    # The standard stands adjacent to a foe late: its own steps are
    # all unsafe so it holds, the wing rallies only on safe steps,
    # and nothing marches the hill.
    bot = fresh_bot()
    bot.turn = 899
    turn1 = run_turn(bot, [(5, 5), (0, 0)], [H1], HOME, enemies=[(5, 6)])
    assert (5, 5) not in [o for o, _ in turn1.orders]
    assert (0, 0) in [o for o, _ in turn1.orders]
    assert bot.last_target is None


def test_march_allowed_ahead_and_committed() -> None:
    assert HD.march_allowed(1, 900, ahead=True, committed=True) is True
    assert HD.march_allowed(0, 900, ahead=True, committed=True) is False


def test_lone_ant_suppressed_explores() -> None:
    # One ant cannot answer even the opening pair-quorum alone: with
    # a hill known it explores instead of donating onto the hill.
    bot = fresh_bot()
    turn1 = run_turn(bot, [A], [H1], HOME)
    assert len(turn1.orders) == 1
    assert bot.last_target is None


def test_homeless_and_hill_less_late_explores() -> None:
    # No home hills and no known hills late: there is nothing to
    # defend and no march to wait for, so every ant scouts.
    bot = fresh_bot()
    bot.turn = 899
    turn1 = run_turn(bot, [(10, 10), (10, 12), (0, 0)], [], [])
    assert set(turn1.orders) == {
        ((10, 10), "n"),
        ((10, 12), "n"),
        ((0, 0), "n"),
    }
    assert bot.last_target is None


def test_no_hills_late_still_explores() -> None:
    # No hills known late: there is no march to wait for, so scouts
    # keep scouting instead of rallying to the standard.
    bot = fresh_bot()
    bot.turn = 899
    turn1 = run_turn(bot, [(10, 10), (10, 12)], [], HOME)
    assert set(turn1.orders) == {((10, 10), "n"), ((10, 12), "n")}
    assert bot.last_target is None


def test_no_hills_explores_like_base() -> None:
    # No hills known: quorum is moot, ants explore least-visited.
    bot = fresh_bot()
    turn1 = run_turn(bot, [A, B], [], HOME)
    assert set(turn1.orders) == {(A, "n"), (B, "n")}
    assert bot.last_target is None


def test_turn_counter_advances_each_turn() -> None:
    bot = fresh_bot()
    assert bot.turn == 0
    run_turn(bot, [A], [], HOME)
    assert bot.turn == 1
    run_turn(bot, [A], [], HOME)
    assert bot.turn == 2


def test_big_late_army_turn_stays_fast() -> None:
    # 300 ants on a late turn: medoid plus rally still finish well
    # under the 1000ms turn budget.
    bot = fresh_bot()
    bot.turn = 899
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(300)]
    start = time.perf_counter()
    run_turn(bot, ants, [H1, H2], HOME)
    assert time.perf_counter() - start < 1.0


def test_medoid_costs_little() -> None:
    # The per-turn medoid over a 120-ant army must stay cheap.
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(120)]
    n = 20
    start = time.perf_counter()
    for _ in range(n):
        assert HD.rally_point(ants, torus) is not None
    assert (time.perf_counter() - start) / n < 0.05


def test_crowded_late_turn_stays_fast() -> None:
    # 120 ants on a late turn (quorum path plus rally): the full
    # turn still finishes well under the 1000ms turn budget.
    bot = fresh_bot()
    bot.turn = 899
    ants = [(r % ROWS, (r * 7) % COLS) for r in range(120)]
    run_turn(bot, ants, [H1], HOME)
    start = time.perf_counter()
    run_turn(bot, ants, [H1, H2], HOME)
    assert time.perf_counter() - start < 1.0
