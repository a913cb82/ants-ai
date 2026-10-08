#!/usr/bin/env python
"""Warren tests: rout evacuation for losing contacts.

Crowd's safety filter only gates *destinations*; an ant already
standing inside enemy attack range in a strictly losing contact
(foes > friends + 1 at its own square) just sits or explores with
the safe filter and donates. Warren adds a pre-pass: a losing ant
retreats first -- to the passable, unoccupied neighbor with the
fewest foes in attack range (ties: most friends in range) -- even
if that square is "unsafe" by the normal filter, forfeiting any
food claim. Equal or winning contacts hold exactly as Crowd.

No engine games. FakeAnts mirrors test_combat.py's stand-in.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import combat as CX  # noqa: E402

# Warren.py carries Crowd's wiring plus the rout pre-pass; WP
# aliases the live Warren entry.
import Warren as WP  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], WP.Warren]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = WP.Warren()
    bot.do_turn(fake)
    return fake.orders, bot


def _sq(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


def test_losing_contact_gate() -> None:
    # (gate) Strictly losing means foes outnumber friends + self:
    # equal trades and winning stands hold, only overrun routs.
    assert CX.losing_contact(0, 0) is False
    assert CX.losing_contact(0, 1) is False
    assert CX.losing_contact(0, 2) is True
    assert CX.losing_contact(1, 1) is False
    assert CX.losing_contact(1, 2) is False
    assert CX.losing_contact(1, 3) is True
    assert CX.losing_contact(2, 4) is True


def test_rout_square_picks_fewest_foes() -> None:
    # (pure) West has 0 foes in range, north has 1: rout west.
    # Ties on foes break toward most friends in range.
    north, west = (4, 5), (5, 4)
    foes = [(5, 7), (5, 8)]
    friends = [(5, 5)]
    found = CX.rout_square(
        (5, 5),
        [north, west],
        friends,
        foes,
        _sq,
        5,
    )
    assert found == west
    # Tie on foes: befriend the side that gains a backer. The pal
    # at (2, 5) is out of range of the stand but in range north.
    tied_foes = [(0, 0)]
    with_pal = CX.rout_square(
        (5, 5),
        [north, west],
        [(2, 5)],
        tied_foes,
        _sq,
        5,
    )
    assert with_pal == north
    # No improvement over staying: hold (None).
    assert CX.rout_square((5, 5), [], [(5, 4)], [(5, 7)], _sq, 5) is None


def test_losing_ant_routs_instead_of_holding() -> None:
    # (a) Ant at (5, 5) with two foes stacked east is losing (0 vs
    # 2), and west (5, 4) sees only one of them: every neighbor is
    # "unsafe" by the normal filter, so Crowd holds -- Warren routs
    # west and issues exactly one order for the ant.
    import Crowd as CP

    mine = [(5, 5)]
    enemies = [(5, 6), (5, 7)]
    orders, _ = run_turn(mine, enemies)
    assert orders == [((5, 5), "w")]
    ant, direction = orders[0]
    assert ant == (5, 5)
    probe = FakeAnts(mine, enemies)
    moved = probe.destination(ant, direction)
    assert moved != (5, 5)
    assert moved not in enemies
    # Crowd holds: no order issues for the surrounded ant.
    fake = FakeAnts(mine, enemies)
    cbot = CP.Crowd()
    cbot.do_turn(fake)
    assert fake.orders == []


def test_equal_contact_holds_exactly_as_crowd() -> None:
    # (b) One adjacent foe is an equal trade, not a rout: every
    # order matches Crowd byte-for-byte.
    import Crowd as CP

    mine = [(5, 5), (10, 10)]
    enemies = [(5, 6)]
    orders, _ = run_turn(mine, enemies)
    fake = FakeAnts(mine, enemies)
    cbot = CP.Crowd()
    cbot.do_turn(fake)
    assert orders == fake.orders


def test_losing_ant_forfeits_food_claim_to_rout() -> None:
    # (c) A losing ant with a far-west food claim routs instead of
    # walking the claim line: Warren moves where Crowd (whose west
    # food step is unsafe and whose explore steps are all unsafe)
    # holds with no orders.
    import Crowd as CP

    mine = [(5, 5)]
    foods = [(5, 0)]
    enemies = [(5, 6), (5, 7)]
    orders, _ = run_turn(mine, enemies, foods)
    assert orders == [((5, 5), "w")]
    probe = FakeAnts(mine, enemies, foods)
    moved = probe.destination(orders[0][0], orders[0][1])
    assert probe.distance(moved, (5, 0)) <= probe.distance((5, 5), (5, 0))
    fake = FakeAnts(mine, enemies, foods)
    cbot = CP.Crowd()
    cbot.do_turn(fake)
    assert fake.orders == []


def test_quiet_board_matches_crowd() -> None:
    # (d) No losing contacts anywhere: food, guard, seek, muster,
    # and explore all match Crowd exactly.
    import Crowd as CP

    mine = [(5, 5), (2, 2), (10, 10)]
    foods = [(5, 6), (2, 3)]
    enemies = [(5, 12), (2, 6), (5, 9), (10, 15)]
    orders, _ = run_turn(mine, enemies, foods, my_hills=[(10, 12)])
    fake = FakeAnts(mine, enemies, foods, my_hills=[(10, 12)])
    cbot = CP.Crowd()
    cbot.do_turn(fake)
    assert orders == fake.orders


def test_routing_ant_never_counts_as_join_pair() -> None:
    # (e) Pair integrity: A at (5, 5) stands overrun (foes X east
    # and Y south) with a rout north, while packed B at (5, 9) --
    # backed by three near-but-not-adjacent pals -- would pair with
    # A on their shared foe X. A flees, so B must NOT count A: B
    # stays unjoined, its equal-trade step refuses (3 near < 10,
    # armies behind at 5v10 so no grinder release; 10 visible foes
    # also close the fearless gate), and B explores north. Without
    # the roll-call skip B mis-pairs and steps west solo into the
    # contact its fled pairmate promised.
    mine = [(5, 5), (5, 9), (5, 12), (5, 13), (5, 14)]
    enemies = [
        (5, 6),
        (7, 5),
        (15, 15),
        (15, 16),
        (0, 0),
        (16, 15),
        (16, 16),
        (0, 1),
        (19, 19),
        (19, 18),
    ]
    orders, _ = run_turn(mine, enemies)
    assert orders == [
        ((5, 5), "n"),
        ((5, 9), "n"),
        ((5, 12), "w"),
        ((5, 13), "n"),
        ((5, 14), "n"),
    ]


def test_rout_scan_under_1ms_on_crowded_board() -> None:
    # (d) The rout gate itself -- the only new arithmetic on the
    # stand check -- costs far under 1ms per crowded-board pass.
    counts = [(i % 3, (i * 7) % 4) for i in range(48)]
    reps = 2000
    start = time.perf_counter()
    for _ in range(reps):
        for friends, foes_n in counts:
            CX.losing_contact(friends, foes_n)
    elapsed = (time.perf_counter() - start) / reps
    assert elapsed < 0.001


def test_full_turn_under_1s_on_crowded_board() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(10)]
    foods = [((i * 3 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(12)]
    fake = FakeAnts(mine, foes, foods)
    bot = WP.Warren()
    start = time.perf_counter()
    bot.do_turn(fake)
    assert time.perf_counter() - start < 1.0


def test_water_blocked_escape_holds_as_crowd() -> None:
    # (f) No way out: water floods the only improving exit and the
    # east square is foe-held, so every option ties or worsens the
    # stand -- the ant holds with no orders, exactly as Crowd.
    import Crowd as CP

    mine = [(5, 5)]
    enemies = [(5, 6), (5, 7)]
    water = {(5, 4)}
    orders, _ = run_turn(mine, enemies, water=water)
    assert orders == []
    fake = FakeAnts(mine, enemies, water=water)
    cbot = CP.Crowd()
    cbot.do_turn(fake)
    assert orders == fake.orders


def test_rout_uses_toroidal_wrap() -> None:
    # (g) Edge of the world: the ant at (0, 0) stands overrun and
    # its best exit wraps -- west to (0, 19), which sees only one
    # of the two foes -- so it routs off the edge where Crowd holds.
    import Crowd as CP

    mine = [(0, 0)]
    enemies = [(0, 1), (0, 2)]
    orders, _ = run_turn(mine, enemies)
    assert orders == [((0, 0), "w")]
    fake = FakeAnts(mine, enemies)
    cbot = CP.Crowd()
    cbot.do_turn(fake)
    assert fake.orders == []


def test_lone_hill_holder_evacuates_rather_than_donates() -> None:
    # (h) Guard interplay: a friendless holder standing on its own
    # threatened hill with two adjacent foes is overrun -- every
    # explore step is unsafe, so Crowd holds and donates -- while
    # Warren evacuates west to the one-foe square and lives.
    import Crowd as CP

    mine = [(10, 10)]
    enemies = [(10, 11), (10, 12)]
    orders, _ = run_turn(mine, enemies, my_hills=[(10, 10)])
    assert orders == [((10, 10), "w")]
    fake = FakeAnts(mine, enemies, my_hills=[(10, 10)])
    cbot = CP.Crowd()
    cbot.do_turn(fake)
    assert fake.orders == []
    bot = WP.Warren()
    start = time.perf_counter()
    bot.do_turn(fake)
    assert time.perf_counter() - start < 1.0
