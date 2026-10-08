#!/usr/bin/env python
"""Rank entry tests: the ranked march on the Crowd base.

No engine games. Rank.py carries Crowd's full wiring (denial food,
pack-gated seek, committed-join packs, ahead-only 1v1 duels,
off-hill screening, 10-gate equal trades, fearless press under ten
enemies) with one idea over it: the army marches in ranks, not
as a mob.

(1) Echelon ordering: claim-free ants (fighters: guard/seek/
muster) issue orders before food-claimed ants (gatherers), so a
fighter wins a same-turn destination clash a gatherer would steal
under list order. Within each echelon the relative order is the
champion's.

(2) Split muster: each free ant marches its own nearest
remembered hill -- one column per hill -- instead of the whole
army flooding the hill nearest the army as a whole.

(3) Ghost invalidation: a remembered hill inside our vision but
unreported is razed, so it is forgotten instead of drawing a
column at an empty square. Unseen hills are kept.

Parity: with one hill and no clashes Rank matches Crowd
order-for-order (30 seeded boards); validity, timing, red-team
edges, multi-turn state, and a 15-turn campaign fuzz pin the
rest.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Crowd as CP  # noqa: E402
import Rank as RP  # noqa: E402

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
        rows: int = ROWS,
        cols: int = COLS,
    ) -> None:
        self.rows = rows
        self.cols = cols
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

    viewradius2 = 36

    def visible(self, loc: Loc) -> bool:
        for ant in self._mine:
            dr = abs(ant[0] - loc[0])
            dr = min(dr, self.rows - dr)
            dc = abs(ant[1] - loc[1])
            dc = min(dc, self.cols - dc)
            if dr * dr + dc * dc <= self.viewradius2:
                return True
        return False


def run_rank(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = RP.Rank()
    bot.do_turn(fake)
    return fake.orders


def run_crowd(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> list[tuple[Loc, str]]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = CP.Crowd()
    bot.do_turn(fake)
    return fake.orders


# Echelon board: S=(5,6) is contested. Gatherer G=(5,5) holds a
# food claim on S and steps east onto it. Fighter T=(5,7) is
# packed (three friends nearby) and seeks the foe at (5,5); its
# shortest path runs west through S. One foe visible: the press
# is fearless, so the seek step takes S when it moves first.
# Under list order [G, T, ...] the gatherer steals S.
_ECH_S = (5, 6)
_ECH_G = (5, 5)
_ECH_T = (5, 7)
_ECH_FOE = (5, 4)
_ECH_FILLERS = [(7, 7), (7, 8), (8, 7)]
_ECH_MINE = [_ECH_G, _ECH_T] + _ECH_FILLERS
_ECH_FOOD = [(5, 6)]


def test_fighter_wins_clash_against_gatherer() -> None:
    # (a) Rank: the claim-free fighter moves first and steps west
    # onto S; the gatherer's food step east is then blocked, so no
    # order sends G east onto S.
    orders = run_rank(_ECH_MINE, [_ECH_FOE], _ECH_FOOD)
    assert ((_ECH_T, "w")) in orders
    assert ((_ECH_G, "e")) not in orders


def test_crowd_loses_same_clash_to_gatherer() -> None:
    # (a-parity) Crowd on the same board moves in list order: the
    # gatherer steals S east first and the fighter never steps
    # west onto it. This pins the behavior Rank changes.
    orders = run_crowd(_ECH_MINE, [_ECH_FOE], _ECH_FOOD)
    assert orders[0] == ((_ECH_G, "e"))
    assert ((_ECH_T, "w")) not in orders


def test_echelon_keeps_relative_order_without_clash() -> None:
    # (a-stable) With no clash and no enemies, every ant takes the
    # same step as Crowd: the echelon sort only decides who wins a
    # contested square, so the ant->move mapping matches exactly
    # (the orders list itself leads with the claim-free explorer).
    mine = [(5, 5), (10, 10), (15, 15)]
    foods = [(5, 6), (10, 11)]
    assert dict(run_rank(mine, [], foods)) == dict(run_crowd(mine, [], foods))


def test_split_muster_sends_each_ant_to_nearest_hill() -> None:
    # (b) Two remembered hills, one ant beside each: Rank marches
    # ant0 north toward H1 and ant1 west toward H2 -- one column
    # per hill -- instead of flooding both onto H1.
    h1, h2 = (2, 2), (16, 14)
    mine = [(3, 3), (16, 16)]
    orders = run_rank(mine, [], enemy_hills=[h1, h2])
    assert orders == [((3, 3), "n"), ((16, 16), "w")]
    probe = FakeAnts(mine, [])
    dest0 = probe.destination(*orders[0])
    dest1 = probe.destination(*orders[1])
    assert probe.distance(dest0, h1) < probe.distance((3, 3), h1)
    assert probe.distance(dest1, h2) < probe.distance((16, 16), h2)


def test_crowd_floods_both_ants_onto_one_hill() -> None:
    # (b-parity) Crowd floods the whole army onto the hill nearest
    # the army as a whole (H1: army-sum 14 beats H2's 18), so ant1
    # marches east toward far H1 instead of west onto nearby H2.
    # This pins the behavior Rank changes.
    h1, h2 = (2, 2), (16, 14)
    mine = [(3, 3), (16, 16)]
    orders = run_crowd(mine, [], enemy_hills=[h1, h2])
    assert orders[0] == ((3, 3), "n")
    assert orders[1] == ((16, 16), "e")
    probe = FakeAnts(mine, [])
    dest1 = probe.destination(*orders[1])
    assert probe.distance(dest1, h1) < probe.distance((16, 16), h1)
    assert probe.distance(dest1, h2) > probe.distance((16, 16), h2)


def test_single_hill_matches_crowd_exactly() -> None:
    # (c) One remembered hill, two ants, no food or enemies: no
    # clash is possible and the flood has one target, so Rank
    # matches Crowd order-for-order.
    mine = [(3, 3), (16, 16)]
    orders = run_rank(mine, [], enemy_hills=[(2, 2)])
    assert orders == run_crowd(mine, [], enemy_hills=[(2, 2)])


def test_guard_mapping_parity_on_threatened_hill() -> None:
    # (e) Threatened home hill with mixed claims and no clashes:
    # the holder holds and the screener screens exactly as Crowd
    # -- the echelon sort never steals a guard step, so the
    # ant->move mapping matches.
    mine = [(10, 8), (10, 11), (5, 5)]
    foods = [(5, 6)]
    enemies = [(10, 16)]
    my = dict(run_rank(mine, enemies, foods, my_hills=[(10, 10)]))
    champ = dict(run_crowd(mine, enemies, foods, my_hills=[(10, 10)]))
    assert my == champ
    assert my[(10, 8)] == "e"


def test_walk_off_hill_parity() -> None:
    # (f) A held ant on its home hill (water on three sides) steps
    # off south under both bots: walk-off runs after the echelons
    # and matches Crowd exactly.
    mine = [(10, 10)]
    water = {(9, 10), (10, 9), (10, 11)}
    assert run_rank(mine, [], water=water, my_hills=[(10, 10)]) == run_crowd(
        mine, [], water=water, my_hills=[(10, 10)]
    )
    assert run_rank(mine, [], water=water, my_hills=[(10, 10)]) == [((10, 10), "s")]


def test_seeded_single_hill_parity() -> None:
    # (g) Seeded random boards, one hill, no food: no claims exist
    # so every ant is a fighter, the echelon order is list order,
    # and the split has one target -- Rank matches Crowd
    # order-for-order on every board. Any divergence is a bug in
    # the reorder, not the idea.
    import random

    rng = random.Random(20261008)
    for _ in range(30):
        mine = [
            (rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(rng.randint(1, 8))
        ]
        mine = list(dict.fromkeys(mine))
        foes = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(4)]
        water = {(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(3)}
        mine = [m for m in mine if m not in water]
        foes = [f for f in foes if f not in water and f not in mine]
        if not mine:
            continue
        hill = (rng.randrange(ROWS), rng.randrange(COLS))
        assert run_rank(mine, foes, water=water, enemy_hills=[hill]) == run_crowd(
            mine, foes, water=water, enemy_hills=[hill]
        )


def test_split_muster_never_marches_away_from_nearest_hill() -> None:
    # (h) Seeded random boards, two hills, no food or enemies: no
    # ant's muster step increases its distance to its own nearest
    # hill. Columns always close on their own target.
    import random

    rng = random.Random(774411)
    for _ in range(20):
        mine = list(
            dict.fromkeys(
                (rng.randrange(ROWS), rng.randrange(COLS))
                for _ in range(rng.randint(2, 5))
            )
        )
        hills = [(2, 2), (16, 14)]
        orders = dict(run_rank(mine, [], enemy_hills=hills))
        probe = FakeAnts(mine, [])
        assert len(orders) == len(mine)
        for ant in mine:
            nearest = min(hills, key=lambda h: probe.distance(ant, h))
            dest = probe.destination(ant, orders[ant])
            assert probe.distance(dest, nearest) < probe.distance(ant, nearest)


def test_scale_turn_inside_1000ms_budget() -> None:
    # (i) 120 ants against 30 foes finish far inside the engine's
    # 1000ms turn budget (echelon sort is O(n); per-ant nearest
    # muster is cheaper than the champion's per-ant army sum).
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(120)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [(3, 3), (17, 17), (10, 2)]
    start = time.perf_counter()
    orders = run_rank(
        mine, foes, foods, enemy_hills=[(0, 0), (19, 19)], my_hills=[(10, 10)]
    )
    assert time.perf_counter() - start < 1.0
    assert len(orders) > 0


def test_ghost_hill_forgotten_when_seen_empty() -> None:
    # (j) A remembered hill inside our vision but unreported is
    # razed: Rank forgets it and explores instead of marching a
    # column at an empty square. Ghost (10, 10) sits 2 steps from
    # our ant -- inside radius-6 vision -- with no hill reported.
    fake = FakeAnts([(10, 12)], [])
    bot = RP.Rank()
    bot.remembered_hills = {(10, 10)}
    assert fake.visible((10, 10)) is True
    bot.do_turn(fake)
    assert bot.remembered_hills == set()
    assert fake.orders == [((10, 12), "n")]


def test_crowd_marches_at_the_same_ghost() -> None:
    # (j-parity) Crowd keeps the ghost and musters toward it, so
    # its ant steps closer to (10, 10). This pins what Rank stops.
    fake = FakeAnts([(10, 12)], [])
    bot = CP.Crowd()
    bot.remembered_hills = {(10, 10)}
    bot.do_turn(fake)
    assert bot.remembered_hills == {(10, 10)}
    probe = FakeAnts([(10, 12)], [])
    dest = probe.destination(*fake.orders[0])
    assert probe.distance(dest, (10, 10)) < probe.distance((10, 12), (10, 10))


def test_unseen_hill_survives_and_draws_muster() -> None:
    # (k) A remembered hill outside vision is kept and still draws
    # the muster: absence of evidence is not evidence of razing.
    fake = FakeAnts([(10, 12)], [])
    bot = RP.Rank()
    bot.remembered_hills = {(0, 0)}
    assert fake.visible((0, 0)) is False
    bot.do_turn(fake)
    assert bot.remembered_hills == {(0, 0)}
    probe = FakeAnts([(10, 12)], [])
    dest = probe.destination(*fake.orders[0])
    assert probe.distance(dest, (0, 0)) < probe.distance((10, 12), (0, 0))


def test_reported_hill_survives_in_vision() -> None:
    # (l) A hill both seen and reported is live: kept, and the
    # ant musters toward it exactly as Crowd does.
    mine = [(10, 12)]
    fake = FakeAnts(mine, [], enemy_hills=[(10, 10)])
    bot = RP.Rank()
    bot.remembered_hills = {(10, 10)}
    bot.do_turn(fake)
    assert bot.remembered_hills == {(10, 10)}
    assert dict(run_rank(mine, [], enemy_hills=[(10, 10)])) == dict(
        run_crowd(mine, [], enemy_hills=[(10, 10)])
    )


def test_wild_boards_issue_valid_orders() -> None:
    # (m) Seeded wild boards (food, foes, hills, water, my hills):
    # every issued destination is passable and distinct -- the
    # echelons never corrupt the order stream. No crash on any.
    import random

    rng = random.Random(5150)
    for _ in range(30):
        mine = list(
            dict.fromkeys(
                (rng.randrange(ROWS), rng.randrange(COLS))
                for _ in range(rng.randint(1, 10))
            )
        )
        foes = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(6)]
        foods = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(4)]
        water = {(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(6)}
        mine = [m for m in mine if m not in water]
        if not mine:
            continue
        hills = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(2)]
        probe = FakeAnts(mine, foes, foods, water)
        fake = FakeAnts(
            mine, foes, foods, water, enemy_hills=hills, my_hills=[(19, 19)]
        )
        bot = RP.Rank()
        bot.do_turn(fake)
        dests = [probe.destination(loc, d) for loc, d in fake.orders]
        assert len(set(dests)) == len(dests)
        assert all(d not in water for d in dests)


def test_three_turn_campaign_state() -> None:
    # (n) Three turns on one bot: hill memory, enemy headings, and
    # visit counts accumulate sanely; every turn issues valid
    # orders and never crashes on stale state.
    hill = (15, 15)
    bot = RP.Rank()
    assert bot.remembered_hills == set()
    # Turn 1: food, one hill, one foe. Hill remembered; foe stored.
    f1 = FakeAnts([(5, 5), (5, 3)], [(5, 10)], [(5, 6)], enemy_hills=[hill])
    bot.do_turn(f1)
    assert bot.remembered_hills == {hill}
    assert bot.prev_enemies == [(5, 10)]
    assert len(f1.orders) == 2
    # Turn 2: hill out of sight is kept; foe stepped east, so its
    # heading ((5, 10) -> (5, 11)) is matched, not a new spawn.
    f2 = FakeAnts([(5, 6), (5, 4)], [(5, 11)], [(5, 7)], enemy_hills=[hill])
    bot.do_turn(f2)
    assert bot.remembered_hills == {hill}
    assert bot.prev_enemies == [(5, 11)]
    assert len(f2.orders) == 2
    # Turn 3: hill razed elsewhere (unreported) but far outside
    # vision, so it is kept; the column still marches, nothing
    # crashes, visits accumulated over all three turns.
    f3 = FakeAnts([(5, 7), (5, 5)], [(5, 12)], [], enemy_hills=[])
    assert f3.visible(hill) is False
    bot.do_turn(f3)
    assert bot.remembered_hills == {hill}
    assert bot.prev_enemies == [(5, 12)]
    assert sum(bot.visits.values()) >= 6
    assert len(f3.orders) == 2


def test_campaign_fuzz_never_retains_visible_ghost() -> None:
    # (o) One bot over 15 random turns: no crash, valid orders
    # every turn, and no remembered hill is ever a visible ghost
    # (seen but unreported) after a turn -- the invalidation leg
    # holds continuously across memory drift.
    import random

    rng = random.Random(999001)
    bot = RP.Rank()
    for _ in range(15):
        mine = list(
            dict.fromkeys(
                (rng.randrange(ROWS), rng.randrange(COLS))
                for _ in range(rng.randint(1, 10))
            )
        )
        foes = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(5)]
        foods = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(3)]
        water = {(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(4)}
        mine = [m for m in mine if m not in water]
        if not mine:
            continue
        reported = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(2)]
        fake = FakeAnts(mine, foes, foods, water, enemy_hills=reported)
        bot.do_turn(fake)
        for h in bot.remembered_hills:
            assert not fake.visible(h) or h in reported
        dests = [fake.destination(loc, d) for loc, d in fake.orders]
        assert len(set(dests)) == len(dests)
        assert all(d not in water for d in dests)


def test_manifest_names_rank_entry() -> None:
    # (p) The .bot manifest runs Rank.py: one line, exact content.
    import pathlib

    manifest = pathlib.Path(__file__).with_name("Rank.bot").read_text()
    assert manifest == "python Rank.py\n"


def test_red_team_edge_boards_never_crash() -> None:
    # (q) Adversarial edges: tiny torus boards, a fully walled ant,
    # a remembered hill on water, zero ants, and a food flood.
    # No crash, and every issued destination stays passable.
    import random

    rng = random.Random(31337)
    # Tiny torus boards with random content.
    for _ in range(30):
        rows = cols = rng.choice((5, 6, 7, 8))
        cells = [(r, c) for r in range(rows) for c in range(cols)]
        rng.shuffle(cells)
        mine = cells[: rng.randint(1, 4)]
        foes = cells[4 : 4 + rng.randint(0, 3)]
        foods = cells[7:9]
        water = set(cells[9 : 9 + rng.randint(0, 5)])
        mine = [m for m in mine if m not in water]
        if not mine:
            continue
        hills = [cells[14 % len(cells)], cells[15 % len(cells)]]
        fake = FakeAnts(
            mine, foes, foods, water, enemy_hills=hills, rows=rows, cols=cols
        )
        bot = RP.Rank()
        bot.do_turn(fake)
        for loc, d in fake.orders:
            assert fake.passable(fake.destination(loc, d))
    # Ant walled in on all four sides: held, then walks off only
    # a hill; here it simply holds with no orders and no crash.
    fake = FakeAnts(
        [(10, 10)],
        [],
        water={(9, 10), (10, 9), (10, 11), (11, 10)},
    )
    RP.Rank().do_turn(fake)
    assert fake.orders == []
    # Remembered hill on a water square: muster pathing finds no
    # first step, so the ant explores instead of crashing.
    fake = FakeAnts([(10, 12)], [], water={(3, 3)}, enemy_hills=[])
    bot = RP.Rank()
    bot.remembered_hills = {(3, 3)}
    bot.do_turn(fake)
    assert len(fake.orders) == 1
    # Zero ants: degenerate but must not crash.
    RP.Rank().do_turn(FakeAnts([], [(5, 5)]))
    # Food flood: 100 foods stay fast and valid.
    foods = [(rng.randrange(ROWS), rng.randrange(COLS)) for _ in range(100)]
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(20)]
    fake = FakeAnts(mine, [(0, 0)], foods)
    RP.Rank().do_turn(fake)
    assert len(fake.orders) > 0


def test_real_ants_protocol_ghost_and_muster() -> None:
    # (r) The REAL ants.Ants protocol object (not the FakeAnts
    # stand-in): a visible-but-unreported hill is forgotten, and a
    # reported hill is remembered and marched at. Catches harness
    # divergence in visible()/unoccupied()/update() semantics.
    import io

    from ants import Ants

    ants = Ants()
    ants.setup(
        "rows 20\ncols 20\nturntime 1000\n"
        "viewradius2 36\nattackradius2 5\nplayer_seed 1\n"
    )
    bot = RP.Rank()
    bot.do_setup(ants)
    bot.remembered_hills = {(10, 10)}
    ants.update("a 10 12 0\n")
    assert ants.visible((10, 10)) is True
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        bot.do_turn(ants)
    finally:
        sys.stdout = old
    assert bot.remembered_hills == set()
    assert buf.getvalue().strip().split("\n") == ["o 10 12 n"]
    ants.update("a 10 12 0\nh 10 10 1\n")
    buf = io.StringIO()
    sys.stdout = buf
    try:
        bot.do_turn(ants)
    finally:
        sys.stdout = old
    assert bot.remembered_hills == {(10, 10)}
    assert buf.getvalue().strip().split("\n") == ["o 10 12 w"]


def test_combat_branches_preserved_without_hills() -> None:
    # (s) No remembered hills anywhere: every ant is claim-free,
    # the echelon order is list order, and ghost checks sleep --
    # so join packs, the ahead-only duel, and off-hill screens play
    # bit-for-bit as Crowd. The champion's combat is preserved.
    # Committed pair joins through the equal-trade gate.
    mine = [(5, 5), (5, 9), (5, 1), (5, 13)]
    foes = [(5, 7)]
    assert run_rank(mine, foes) == run_crowd(mine, foes)
    assert run_rank(mine, foes)[0] == ((5, 5), "e")
    # Ahead lone ant engages the 1v1; behind holds.
    mine = [(5, 5), (15, 15), (15, 16), (5, 2), (5, 1), (5, 0)]
    assert run_rank(mine, foes) == run_crowd(mine, foes)
    assert run_rank(mine, foes)[0] == ((5, 5), "e")
    mine = [(5, 5)]
    behind = [(5, 7), (10, 10), (10, 11)]
    assert run_rank(mine, behind) == run_crowd(mine, behind)
    # Extra guard screens the razer off the home hill.
    mine = [(10, 8), (10, 11)]
    assert run_rank(mine, [(10, 16)], my_hills=[(10, 10)]) == run_crowd(
        mine, [(10, 16)], my_hills=[(10, 10)]
    )
    assert run_rank(mine, [(10, 16)], my_hills=[(10, 10)])[1] == ((10, 11), "e")


def test_interleaved_echelons_fighters_first() -> None:
    # (t) Interleaved list [G1, F1, G2, F2]: both fighters move
    # before both gatherers, each echelon stable in list order.
    # F1 seeks the eastern foe; F2 has no foe in range and packs
    # up west toward F1. G1/G2 hold food claims on the spot foods.
    g1, f1, g2, f2 = (5, 5), (5, 12), (15, 15), (5, 14)
    mine = [g1, f1, g2, f2, (7, 12), (7, 13), (8, 12)]
    foods = [(5, 6), (15, 16)]
    foes = [(5, 17)]
    orders = run_rank(mine, foes, foods)
    loci = [loc for loc, _ in orders]
    assert loci.index(f1) < loci.index(g1)
    assert loci.index(f1) < loci.index(g2)
    assert loci.index(f2) < loci.index(g1)
    assert loci.index(f2) < loci.index(g2)
    assert loci.index(f1) < loci.index(f2)
    assert loci.index(g1) < loci.index(g2)
    assert (f1, "e") in orders


def test_three_hills_draw_three_columns() -> None:
    # (u) Three remembered hills, one ant beside each: every ant
    # closes on its own hill, three columns instead of one flood.
    h1, h2, h3 = (2, 2), (2, 17), (17, 9)
    mine = [(3, 3), (3, 16), (16, 9)]
    orders = run_rank(mine, [], enemy_hills=[h1, h2, h3])
    probe = FakeAnts(mine, [])
    for ant, hill in zip(mine, (h1, h2, h3), strict=True):
        dest = probe.destination(ant, dict(orders)[ant])
        assert probe.distance(dest, hill) < probe.distance(ant, hill)


def test_mixed_ghost_and_live_hills() -> None:
    # (v) One ghost (seen empty) plus one live hill (reported): the
    # ghost is forgotten while the live hill still draws the ant.
    live = (2, 2)
    fake = FakeAnts([(10, 12)], [], enemy_hills=[live])
    assert fake.visible((10, 10)) is True
    assert fake.visible(live) is False
    bot = RP.Rank()
    bot.remembered_hills = {(10, 10), live}
    bot.do_turn(fake)
    assert bot.remembered_hills == {live}


def test_rank_turn_under_half_second_on_crowded_board() -> None:
    # (d) Full turn with 48 ants, 12 foes, food, hills, and water
    # finishes far inside the 1000ms budget.
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(12)]
    foods = [(3, 3), (17, 17), (10, 2), (2, 10)]
    water = {(4, 4), (4, 5), (15, 15)}
    start = time.perf_counter()
    orders = run_rank(
        mine, foes, foods, water, enemy_hills=[(0, 0)], my_hills=[(19, 19)]
    )
    assert time.perf_counter() - start < 0.5
    assert len(orders) > 0
