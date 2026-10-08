#!/usr/bin/env python
"""crowd-gated fixing: packed ants press small fights fearlessly.

Fixing5 keeps the anthonyvh greedy sequential fixing core
(most-constrained-first pins, stationary enemies first, suicide only
to unblock a hill rush) and gates it the Crowd way: an ant without a
pack (3+ friends within 10) never pins a solo attack -- it rallies
toward its nearest friend instead -- and while fewer than 10 enemies
show, KILL takes press without waiting for a hill push (full safety
in crowds). Self-contained: stdlib plus Fixing5 only.

  (a) has_pack counts friends within 10, never the ant itself.
  (b) fearless KILL: acceptable without hills iff fearless, and
      pressed first while the visible army leads (SAFE first when
      behind); DIE always ranks last -- pure, in-fight, and the
      9-vs-10 boundary in-bot.
  (c) plan screens the packless out of the pin population and marks
      them for rally; packed ants pin as before; the rush
      outranks the pack only with no alternative (a SAFE square
      rallies, all-DIE unblocks).
  (d) in-bot: packless ant rallies to its friend, never at the foe;
      fearless ants press the KILL squares the base refuses; rally
      collisions fall through without sharing a destination; hill
      memory spans turns.
  (e) per-fight resolve stays under 10 ms, full crowded turns
      under 1 s; deterministic fuzz keeps every order legal; real
      ants.Ants wiring runs two turns clean.
"""

import io
import os
import random
import sys
import time
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Fixing5 as FX  # noqa: E402
from ants import Ants  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], FX.Fixing5]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = FX.Fixing5()
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
    # No combat.py import: stdlib plus ants.py only. The class and
    # bot-file names match the fresh Fixing5 entry.
    assert FX.__name__ == "Fixing5"
    assert hasattr(FX, "Fixing5")
    with open(str(FX.__file__)) as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    bot_file = os.path.join(os.path.dirname(str(FX.__file__)), "Fixing5.bot")
    with open(bot_file) as handle:
        assert handle.read().strip() == "python Fixing5.py"


def test_has_pack_needs_three_friends() -> None:
    # (a) the ant itself never counts: three friends within 10 is a
    # pack, two is not; (10, 1) sits 9 away, inside, so with two
    # more friends the pack holds.
    me = (10, 10)
    assert FX.has_pack(me, [me, (10, 11), (11, 10), (9, 10)], _dist) is True
    assert FX.has_pack(me, [me, (10, 11), (11, 10)], _dist) is False
    assert FX.has_pack(me, [me], _dist) is False
    assert _dist((10, 10), (10, 1)) == 9
    assert FX.has_pack((10, 10), [(10, 10), (10, 0), (0, 10), (10, 1)], _dist) is True


def test_has_pack_torus_radius() -> None:
    # (a, torus) (10, 0) sits 10 from (10, 10) through the 20-wide
    # wrap (dc min(10, 10) = 10, inside); (0, 0) sits 20 away
    # (10 row steps plus 10 col steps), outside.
    me = (10, 10)
    assert _dist(me, (10, 0)) == 10
    assert _dist(me, (10, 19)) == 9
    assert _dist(me, (0, 0)) == 20
    assert FX.has_pack(me, [me, (10, 0), (10, 19), (0, 10)], _dist) is True
    assert FX.has_pack(me, [me, (0, 0), (10, 19), (0, 10)], _dist) is False


def test_fearless_kill_without_hills() -> None:
    # (b, pure) one foe stamping (5, 6) with influence 1: a lone ant
    # reads KILL there. Peacetime rules refuse it with no hill to
    # push; fearless takes it; hills take it even timid.
    foes = [(5, 7)]
    field = FX.influence_field(foes, ROWS, COLS, FX.threat_reach(5))
    assert FX.classify_step(field, (5, 6), 0) == FX.KILL
    timid = FX.acceptable_moves(
        (5, 5), field, {}, [], _dist, _dest, _allow, _allow, fearless=False
    )
    assert "e" not in timid
    brave = FX.acceptable_moves(
        (5, 5), field, {}, [], _dist, _dest, _allow, _allow, fearless=True
    )
    assert "e" in brave
    pushed = FX.acceptable_moves(
        (5, 5), field, {}, [(5, 10)], _dist, _dest, _allow, _allow, fearless=False
    )
    assert "e" in pushed


def test_fearless_never_unlocks_die() -> None:
    # (b, pure) fearless opens KILL takes, never suicide: every
    # square around (5, 5) carries influence 2 = DIE, and even
    # fearless refuses them all with no hill rush to unblock.
    foes = [(5, 7), (4, 4)]
    field = FX.influence_field(foes, ROWS, COLS, FX.threat_reach(5))
    for dest in [(5, 4), (5, 6), (4, 5), (6, 5)]:
        assert FX.classify_step(field, dest, 0) == FX.DIE
    assert (
        FX.acceptable_moves(
            (5, 5), field, {}, [], _dist, _dest, _allow, _allow, fearless=True
        )
        == []
    )
    assert (
        FX.best_move(
            (5, 5), field, {}, [], foes, _dist, _dest, _allow, _allow, fearless=True
        )
        is None
    )


def test_fearless_flips_fight_pin() -> None:
    # (b, in-fight) (6, 7) vs (7, 10) with every square but (6, 8)
    # blocked: e onto (6, 8) reads KILL (influence 1, ours 1).
    # Timid leaves it unpinned; fearless pins the advance.
    mine = [(6, 7)]
    foes = [(7, 10)]
    field = FX.influence_field(foes, ROWS, COLS, FX.threat_reach(5))
    assert FX.classify_step(field, (6, 8), 0) == FX.KILL
    only_e = lambda loc: loc == (6, 8)  # noqa: E731
    timid = FX.resolve_fight(
        mine,
        foes,
        [],
        ROWS,
        COLS,
        5,
        [],
        _dist,
        _dest,
        _allow,
        only_e,
        None,
        fearless=False,
    )
    brave = FX.resolve_fight(
        mine,
        foes,
        [],
        ROWS,
        COLS,
        5,
        [],
        _dist,
        _dest,
        _allow,
        only_e,
        None,
        fearless=True,
    )
    assert timid == {}
    assert brave == {0: "e"}


def test_plan_screens_packless_into_rally() -> None:
    # (c) the lone ant at (5, 5) faces (5, 8) with no friend near:
    # no pin, rally marked. Its packed twin at (10, 10) with three
    # friends pins normally.
    foes = [(5, 8)]
    lone: list[Loc] = [(5, 5)]
    plan, rally = FX.plan_fixing(
        lone,
        {},
        foes,
        [],
        ROWS,
        COLS,
        5,
        [],
        _dist,
        _dest,
        _allow,
        _allow,
        None,
        fearless=False,
    )
    assert plan == {}
    assert rally == {0}
    packed = [(10, 10), (10, 11), (11, 10), (9, 10)]
    plan2, rally2 = FX.plan_fixing(
        packed,
        {},
        foes,
        [],
        ROWS,
        COLS,
        5,
        [],
        _dist,
        _dest,
        _allow,
        _allow,
        None,
        fearless=False,
    )
    assert 0 not in rally2
    assert len(plan2) >= 1


def test_packed_ant_pins_while_packless_rallies() -> None:
    # (c) ant 0 at (2, 5) faces (2, 2) with no friend within 10:
    # rally. The packed cluster at (10, 10) faces (10, 13) and
    # pins normally.
    mine = [(2, 5), (10, 10), (10, 11), (11, 10), (9, 10)]
    foes = [(2, 2), (10, 13)]
    assert _dist((2, 5), (2, 2)) <= FX.SEEK_RANGE
    assert all(_dist((2, 5), f) > FX.PACK_RADIUS for f in mine[1:])
    plan, rally = FX.plan_fixing(
        mine,
        {},
        foes,
        [],
        ROWS,
        COLS,
        5,
        [],
        _dist,
        _dest,
        _allow,
        _allow,
        None,
        fearless=False,
    )
    assert rally == {0}
    assert any(ai in plan for ai in (1, 2, 3, 4))


def test_rally_steps_to_friend_not_foe() -> None:
    # (d, in-bot) lone ant at (5, 5), friend at (5, 2), foe at
    # (5, 8): the ant rallies west toward its friend, never east
    # at the foe.
    orders, _ = run_turn([(5, 5), (5, 2)], [(5, 8)])
    by_ant = dict(orders)
    assert by_ant.get((5, 5)) == "w"


def test_fearless_presses_kill_in_bot() -> None:
    # (d, in-bot) one foe at (5, 7), packed ants at (5, 5) on down:
    # (5, 6) reads KILL and the line presses east; with 10+
    # enemies the same pair holds the advance (crowd safety).
    mine = [(5, 5), (5, 4), (5, 3), (5, 2)]
    orders, _ = run_turn(mine, [(5, 7)])
    by_ant = dict(orders)
    assert by_ant.get((5, 5)) == "e"
    crowd = [(5, 7)] + [(i % ROWS, (i * 3 + 1) % COLS) for i in range(11)]
    orders2, _ = run_turn(mine, crowd)
    by_ant2 = dict(orders2)
    assert by_ant2.get((5, 5)) != "e"


def test_food_and_first_guard_untouched() -> None:
    # Economy and guard stay champion: the denial pair still claims
    # (5, 6) and (2, 3) east, and a lone guard still holds its
    # threatened hill east -- all with enemies in seek range.
    mine = [(5, 5), (2, 2), (10, 10)]
    foods = [(5, 6), (2, 3)]
    enemies = [(5, 12), (2, 6), (5, 9), (10, 15)]
    orders, _ = run_turn(mine, enemies, foods, my_hills=[(10, 12)])
    assert orders == [((5, 5), "e"), ((2, 2), "e"), ((10, 10), "e")]
    guard, _ = run_turn([(10, 8)], [(10, 16)], my_hills=[(10, 10)])
    assert guard == [((10, 8), "e")]


def test_suicide_still_needs_hill_rush() -> None:
    # Suicide rule untouched: the lone ant sacrifices itself east
    # pushing (5, 10), and holds with no hill -- every explore
    # square unsafe, so no order issues at all.
    mine = [(5, 5)]
    foes = [(5, 7), (4, 4)]
    pushed, _ = run_turn(mine, foes, enemy_hills=[(5, 10)])
    assert pushed == [((5, 5), "e")]
    quiet, _ = run_turn(mine, foes)
    assert quiet == []


def test_fight_under_10ms_and_turn_under_1s() -> None:
    # (e) a 24v24 pile-up resolves far inside the 10 ms fight
    # budget, and a full crowded turn (48 ants, food, hills,
    # guards) finishes far inside 1 s.
    ours = [(i % ROWS, (i * 7) % COLS) for i in range(24)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(24)]
    start = time.perf_counter()
    plan, rally = FX.plan_fixing(
        ours,
        {},
        foes,
        [],
        ROWS,
        COLS,
        5,
        [(0, 0)],
        _dist,
        _dest,
        _allow,
        _allow,
        None,
        fearless=False,
    )
    assert (time.perf_counter() - start) < 0.010
    assert isinstance(plan, dict) and isinstance(rally, set)
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


def test_fearless_boundary_nine_vs_ten() -> None:
    # Crowd gate boundary in-bot: 9 visible enemies press the KILL
    # square east; 10 visible enemies hold it (full crowd safety).
    # Far foes sit outside influence reach of (5, 6).
    mine = [(5, 5), (5, 4), (5, 3), (5, 2)]
    far = [(0, 0), (0, 10), (10, 0), (10, 10), (19, 19), (19, 0), (0, 19), (15, 15)]
    for foe in far:
        assert _dist((5, 6), foe) > FX.threat_reach(5)
    brave, _ = run_turn(mine, [(5, 7)] + far)
    assert dict(brave).get((5, 5)) == "e"
    timid, _ = run_turn(mine, [(5, 7)] + far + [(15, 0)])
    assert _dist((5, 6), (15, 0)) > FX.threat_reach(5)
    assert dict(timid).get((5, 5)) != "e"


def test_rally_routes_around_water() -> None:
    # Packless ant rallies to its buddy around a water square: west
    # is blocked, so it steps north or south -- never east at the
    # foe, never into the water.
    orders, _ = run_turn([(5, 5), (5, 2)], [(5, 8)], water={(5, 4)})
    by_ant = dict(orders)
    assert by_ant.get((5, 5)) in ("n", "s")


def test_friendless_packless_explores_safely() -> None:
    # One ant, one distant foe, no hills: no pin, no rally buddy --
    # it explores the safe square north, away from the fight.
    orders, _ = run_turn([(5, 5)], [(5, 8)])
    assert orders == [((5, 5), "n")]


def test_big_turn_stays_under_1s() -> None:
    # 120-ant scrum with food and hills finishes far inside 1 s.
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(120)]
    many = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(60)]
    foods = [((i * 3 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(20)]
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


def test_rally_collision_falls_through() -> None:
    # Three packless ants, one foe: (5, 5) rallies at its buddy
    # (5, 6) but the square is occupied, so it explores north;
    # (5, 6) steps north backed by (5, 5) (2-vs-1 superiority);
    # (5, 2) rallies east. No two orders share a destination.
    orders, _ = run_turn([(5, 5), (5, 6), (5, 2)], [(5, 8)])
    assert orders == [((5, 5), "n"), ((5, 6), "n"), ((5, 2), "e")]
    squares = [_dest(loc, d) for loc, d in orders]
    assert len(set(squares)) == len(squares)


def test_hill_memory_spans_turns() -> None:
    # Turn 1 spots an enemy hill: every order shortens the march
    # and the hill is remembered. Turn 2 loses sight of the hill
    # but the rush persists; the bot also records the visible foe
    # for next turn's headings. Turn 3 razes the hill and forgets it.
    bot = FX.Fixing5()
    mine = [(5, 5), (5, 4), (5, 3), (5, 2)]

    fake1 = FakeAnts(mine, [], enemy_hills=[(0, 0)])
    bot.do_setup(fake1)
    bot.do_turn(fake1)
    assert bot.remembered_hills == {(0, 0)}
    assert len(fake1.orders) > 0
    for loc, d in fake1.orders:
        assert _dist(_dest(loc, d), (0, 0)) < _dist(loc, (0, 0))

    fake2 = FakeAnts(mine, [(4, 5)])
    bot.do_turn(fake2)
    assert bot.remembered_hills == {(0, 0)}
    assert bot.prev_enemies == [(4, 5)]
    assert len(fake2.orders) > 0

    razed = [(0, 0), (5, 4), (5, 3), (5, 2)]
    fake3 = FakeAnts(razed, [])
    bot.do_turn(fake3)
    assert bot.remembered_hills == set()


def test_fuzz_orders_always_legal() -> None:
    # Deterministic fuzz: random boards never crash, never double-
    # order an ant, never share a destination, and every step lands
    # on a passable unoccupied square.
    rng = random.Random(12345)
    for _trial in range(60):
        water = set()
        for _ in range(rng.randint(0, 60)):
            water.add((rng.randrange(ROWS), rng.randrange(COLS)))
        free = [(r, c) for r in range(ROWS) for c in range(COLS) if (r, c) not in water]
        rng.shuffle(free)
        n_mine = rng.randint(1, 20)
        n_foe = rng.randint(0, 20)
        mine = free[:n_mine]
        foes = free[n_mine : n_mine + n_foe]
        rest = free[n_mine + n_foe :]
        foods = rest[: rng.randint(0, 6)]
        hills = rest[6 : 6 + rng.randint(0, 2)]
        homes = rest[8 : 8 + rng.randint(0, 2)]
        bot = FX.Fixing5()
        fake = FakeAnts(mine, foes, foods, water, enemy_hills=hills)
        fake._my_hills = list(homes)
        bot.do_setup(fake)
        start = time.perf_counter()
        bot.do_turn(fake)
        assert (time.perf_counter() - start) < 1.0
        seen_sources: set[Loc] = set()
        seen_dests: set[Loc] = set()
        for loc, d in fake.orders:
            assert d in ("n", "e", "s", "w")
            assert loc in mine
            assert loc not in seen_sources
            seen_sources.add(loc)
            dest = _dest(loc, d)
            assert dest not in water
            assert dest not in mine
            assert dest not in foes
            assert dest not in seen_dests
            seen_dests.add(dest)


_ORDER_MINE = [(5, 5), (10, 10), (15, 15)]
_ORDER_FOES = [(5, 8), (6, 7), (10, 13)]


def test_sequential_pinning_order_most_constrained_first() -> None:
    # Kept from the base: no hills, timid, so only SAFE squares pin.
    # A0 (5, 5): n/w SAFE, e DIE, s KILL refused -> 2.
    # A1 (10, 10): n/s/w SAFE, e KILL refused -> 3.
    # A2 (15, 15): everything SAFE -> 4.
    # Most-constrained-first pins [0, 1, 2].
    field = FX.influence_field(_ORDER_FOES, ROWS, COLS, FX.threat_reach(5))
    support: dict[Loc, int] = {}
    counts = [
        len(FX.acceptable_moves(ant, field, support, [], _dist, _dest, _allow, _allow))
        for ant in _ORDER_MINE
    ]
    assert counts == [2, 3, 4]
    trace: list[str] = []
    plan = FX.resolve_fight(
        _ORDER_MINE,
        _ORDER_FOES,
        [],
        ROWS,
        COLS,
        5,
        [],
        _dist,
        _dest,
        _allow,
        _allow,
        trace,
    )
    fixes = [entry for entry in trace if entry.startswith("fix")]
    order = [int(entry.split()[1]) for entry in fixes]
    assert order == [0, 1, 2]
    assert set(plan) == {0, 1, 2}


def test_stationary_enemies_pinned_first() -> None:
    # Kept from the base: (5, 8) never moved, so the trace pins it
    # before either of our ants.
    mine = [(5, 5), (10, 10)]
    foes = [(5, 8), (5, 12)]
    stationary = FX.stationary_pins([(5, 8), (0, 0)], foes, _dist)
    assert stationary == [(5, 8)]
    trace: list[str] = []
    FX.resolve_fight(
        mine,
        foes,
        stationary,
        ROWS,
        COLS,
        5,
        [],
        _dist,
        _dest,
        _allow,
        _allow,
        trace,
    )
    kinds = [entry.split()[0] for entry in trace]
    assert kinds[0] == "pin"
    assert "(5, 8)" in trace[0]
    assert kinds.index("fix") > kinds.index("pin")


def test_suicide_yields_to_safe_move() -> None:
    # Packless lone ant at (5, 5) pushing (5, 10): east onto (5, 6)
    # is DIE (two lurkers) but unblocks the rush, while west is
    # SAFE. The rush outranks the pack only with no alternative:
    # here the ant rallies instead of donating.
    foes = [(5, 8), (6, 8)]
    field = FX.influence_field(foes, ROWS, COLS, FX.threat_reach(5))
    assert FX.classify_step(field, (5, 6), 0) == FX.DIE
    assert FX.classify_step(field, (5, 4), 0) == FX.SAFE
    assert FX.unblocks_hill_rush((5, 5), (5, 6), [(5, 10)], _dist) is True
    plan, rally = FX.plan_fixing(
        [(5, 5)],
        {},
        foes,
        [],
        ROWS,
        COLS,
        5,
        [(5, 10)],
        _dist,
        _dest,
        _allow,
        _allow,
        None,
        fearless=False,
    )
    assert plan == {}
    assert rally == {0}


def _kill_or_safe_setup():
    # Ant (5, 5) vs a lone lurker at (5, 9), no hills, fearless:
    # east onto (5, 6) reads KILL; north/south/west read SAFE.
    foes = [(5, 9)]
    field = FX.influence_field(foes, ROWS, COLS, FX.threat_reach(5))
    assert FX.classify_step(field, (5, 6), 0) == FX.KILL
    for dest in [(4, 5), (6, 5), (5, 4)]:
        assert FX.classify_step(field, dest, 0) == FX.SAFE
    return foes, field


def test_press_kill_while_ahead() -> None:
    # Fearless and leading: the KILL advance east outranks the
    # SAFE retreats. Fearless but behind (or even): SAFE first,
    # north on the direction tiebreak.
    foes, field = _kill_or_safe_setup()
    ahead = FX.best_move(
        (5, 5),
        field,
        {},
        [],
        foes,
        _dist,
        _dest,
        _allow,
        _allow,
        fearless=True,
        press_kills=True,
    )
    assert ahead == "e"
    behind = FX.best_move(
        (5, 5),
        field,
        {},
        [],
        foes,
        _dist,
        _dest,
        _allow,
        _allow,
        fearless=True,
        press_kills=False,
    )
    assert behind == "n"
    timid = FX.best_move(
        (5, 5),
        field,
        {},
        [],
        foes,
        _dist,
        _dest,
        _allow,
        _allow,
        fearless=False,
        press_kills=True,
    )
    assert timid == "n"


def test_press_never_prefers_death() -> None:
    # Even pressing, DIE ranks last: with every square DIE and no
    # hill rush, nothing pins.
    foes = [(5, 7), (4, 4)]
    field = FX.influence_field(foes, ROWS, COLS, FX.threat_reach(5))
    assert (
        FX.best_move(
            (5, 5),
            field,
            {},
            [],
            foes,
            _dist,
            _dest,
            _allow,
            _allow,
            fearless=True,
            press_kills=True,
        )
        is None
    )


def test_ahead_presses_in_fight() -> None:
    # 4 packed ants vs 1 foe: the army leads, so the pin presses
    # the KILL advance east.
    mine = [(5, 5), (5, 4), (5, 3), (5, 2)]
    plan, _rally = FX.plan_fixing(
        mine,
        {},
        [(5, 9)],
        [],
        ROWS,
        COLS,
        5,
        [],
        _dist,
        _dest,
        _allow,
        _allow,
        None,
        fearless=True,
    )
    assert plan.get(0) == "e"


def test_real_ants_wiring_two_turns() -> None:
    # Real ants.Ants (vision, map, orders to stdout): two turns run
    # fast, every order names a live ant, and no ant is ordered
    # twice. Turn 2 carries hill memory and headings without error.
    setup = "\n".join(
        [
            "turn 0",
            "loadtime 3000",
            "turntime 1000",
            "rows 20",
            "cols 20",
            "turns 10",
            "viewradius2 77",
            "attackradius2 5",
            "spawnradius2 1",
        ]
    )
    turn1 = "\n".join(
        [
            "turn 1",
            "f 6 6",
            "f 10 10",
            "a 5 5 0",
            "a 5 4 0",
            "a 5 3 0",
            "a 5 2 0",
            "a 5 9 1",
            "h 0 0 1",
            "h 19 19 0",
        ]
    )
    turn2 = "\n".join(
        [
            "turn 2",
            "f 6 6",
            "a 5 6 0",
            "a 5 9 1",
            "h 0 0 1",
            "h 19 19 0",
        ]
    )
    ants = Ants()
    ants.setup(setup)
    bot = FX.Fixing5()
    bot.do_setup(ants)
    for packet in (turn1, turn2):
        ants.update(packet)
        mine = set(ants.my_ants())
        assert mine
        buf = io.StringIO()
        start = time.perf_counter()
        with redirect_stdout(buf):
            bot.do_turn(ants)
        assert (time.perf_counter() - start) < 1.0
        orders = [
            line.split()
            for line in buf.getvalue().splitlines()
            if line.startswith("o ")
        ]
        sources = [tuple(map(int, o[1:3])) for o in orders]
        assert len(set(sources)) == len(sources)
        assert set(sources) <= mine
        assert all(o[3] in ("n", "e", "s", "w") for o in orders)
    assert bot.remembered_hills == {(0, 0)}


def test_suicide_pins_without_alternative_at_plan_level() -> None:
    # All-DIE packless ant pushing a hill: the post-pass pins east,
    # drops the rally mark, and traces the fix.
    foes = [(5, 7), (4, 4)]
    trace: list[str] = []
    plan, rally = FX.plan_fixing(
        [(5, 5)],
        {},
        foes,
        [],
        ROWS,
        COLS,
        5,
        [(5, 10)],
        _dist,
        _dest,
        _allow,
        _allow,
        trace,
        fearless=False,
    )
    assert plan == {0: "e"}
    assert rally == set()
    assert trace == ["fix 0 e"]


def test_plan_and_rally_never_overlap() -> None:
    # Randomized armies, hills on/off, fearless on/off: no ant is
    # ever both pinned and rally-marked.
    import random

    rng = random.Random(987)
    for _trial in range(60):
        mine = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(8)]
        foes = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(6)]
        hills = [[], [(0, 0)]][_trial % 2]
        fearless = bool(_trial % 2)
        plan, rally = FX.plan_fixing(
            mine,
            {},
            foes,
            [],
            ROWS,
            COLS,
            5,
            hills,
            _dist,
            _dest,
            _allow,
            _allow,
            None,
            fearless=fearless,
        )
        assert set(plan) & rally == set()
        assert set(plan) | rally <= set(range(len(mine)))


def test_scan_board_matches_naive_model() -> None:
    # The inherited denial clustering (shipped in this entry) equals
    # a naive toroidal model on random boards: same food clusters,
    # same per-cluster enemy counts.
    import random

    def tdist(a: Loc, b: Loc) -> int:
        dr = abs(a[0] - b[0])
        dr = min(dr, ROWS - dr)
        dc = abs(a[1] - b[1])
        dc = min(dc, COLS - dc)
        return dr + dc

    def canon(rs: list[int]) -> list[list[int]]:
        groups: dict[int, list[int]] = {}
        for i, r in enumerate(rs):
            groups.setdefault(r, []).append(i)
        return sorted(sorted(g) for g in groups.values())

    rng = random.Random(7)
    for _trial in range(30):
        n = rng.randint(0, 12)
        foods = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(n)]
        foes = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(6)]
        roots, counts = FX._scan_board(foods, foes, ROWS, COLS)
        parent = list(range(n))

        def find(a: int, _parent: list[int] = parent) -> int:
            while _parent[a] != a:
                _parent[a] = _parent[_parent[a]]
                a = _parent[a]
            return a

        for i in range(n):
            for j in range(i + 1, n):
                if tdist(foods[i], foods[j]) <= FX.CLUSTER_R:
                    a, b = find(i), find(j)
                    if a != b:
                        parent[max(a, b)] = min(a, b)
        nroots = [find(i) for i in range(n)]
        assert canon(roots) == canon(nroots)

        def cntmap(rs: list[int], cs: dict[int, int]) -> dict[tuple[int, ...], int]:
            return {
                tuple(sorted(i for i, rr in enumerate(rs) if rr == r)): c
                for r, c in cs.items()
            }

        ncounts: dict[int, int] = {}
        for e in foes:
            for r in {nroots[j] for j in range(n) if tdist(e, foods[j]) <= 8}:
                ncounts[r] = ncounts.get(r, 0) + 1
        assert cntmap(roots, counts) == cntmap(nroots, ncounts)


def test_empty_army_issues_nothing() -> None:
    # No ants left: the turn still runs without error and the hills
    # are forgotten only when razed -- with no ants nothing changes.
    orders, bot = run_turn([], [(5, 5)], enemy_hills=[(0, 0)])
    assert orders == []
    assert bot.remembered_hills == {(0, 0)}


def test_behind_retreats_in_fight() -> None:
    # 5 packed ants vs 6 foes: fearless unlocks KILL but the army
    # trails, so the pin prefers the SAFE retreat north over the
    # KILL advance east.
    mine = [(5, 5), (5, 4), (5, 3), (5, 2), (15, 15)]
    foes = [(5, 9), (0, 0), (0, 19), (19, 0), (19, 19), (10, 10)]
    field = FX.influence_field(foes, ROWS, COLS, FX.threat_reach(5))
    assert FX.classify_step(field, (5, 6), 0) == FX.KILL
    for dest in [(4, 5), (6, 5), (5, 4)]:
        assert FX.classify_step(field, dest, 0) == FX.SAFE
    plan, rally = FX.plan_fixing(
        mine,
        {},
        foes,
        [],
        ROWS,
        COLS,
        5,
        [],
        _dist,
        _dest,
        _allow,
        _allow,
        None,
        fearless=True,
    )
    assert 0 not in rally
    assert plan.get(0) == "n"
