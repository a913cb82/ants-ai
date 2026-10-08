#!/usr/bin/env python
"""Pack-mustered table press with committed-join release (Tables8 entry).

Tables8 keeps the Tables base (precomputed battle tables, hill-gated
trades, Denial economy, guard/muster/reinforce/explore/walk-off) and
adds two Crowd-proven but Tables-new gates, both table-native:

- pack-mustered approaches: packed ants press like the base; a
  packless ant still takes free kills and hill-covered sacrifices
  but never walks solo onto the contact edge through empty ground
  and never mills on refused contacts -- it packs up one
  table-safe step toward its nearest friend instead.
- committed-join release: claim-free ants pre-commit to the foe
  their advancing step would contact; a foe drawing 2+ commitments
  releases equal (TRADE) steps for its committers without hill
  cover. Losing (LOSE) steps still always refuse.

This file is self-contained: stdlib plus ants.py only.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Tables8 as T8  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], T8.Tables8]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = T8.Tables8()
    bot.do_turn(fake)
    return fake.orders, bot


def _dist(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


def test_has_pack_counts_friends_in_radius() -> None:
    # Three friends within 10 steps is a pack; the ant itself never
    # counts, and two friends are not enough.
    mine = [(5, 5), (5, 3), (3, 5), (5, 7)]
    assert T8.has_pack((5, 5), mine, _dist) is True
    assert T8.has_pack((5, 5), [(5, 5), (5, 3), (3, 5)], _dist) is False
    assert T8.has_pack((5, 5), [(5, 5)], _dist) is False


def test_packless_ants_pack_up_instead_of_seeking() -> None:
    # Two lone ants with a foe between them: neither holds a pack
    # (need 3 friends), so (5, 5) steps west toward (5, 1) and
    # (5, 1) steps east toward (5, 5) -- neither walks east/west
    # onto the foe's contact edge.
    mine = [(5, 5), (5, 1)]
    orders, _ = run_turn(mine, [(5, 8)])
    assert orders == [((5, 5), "w"), ((5, 1), "e")]


def test_packless_ant_takes_free_kill() -> None:
    # Only two friends nearby (packless), but (5, 4) backs the step
    # onto (5, 6): ours 2 vs 1 is a table WIN, and free kills go
    # for every ant -- the base agrees.
    import Tables as TB

    mine = [(5, 5), (5, 4), (5, 3)]
    orders, _ = run_turn(mine, [(5, 8)])
    fake = FakeAnts(mine, [(5, 8)])
    TB.Tables().do_turn(fake)
    assert orders[0] == ((5, 5), "e")
    assert orders[0] == fake.orders[0]


def test_lone_ant_takes_hill_sacrifice() -> None:
    # No friends at all, but the friendless 1v1 onto (5, 6) sits 13
    # steps from the held hill: hill cover sends it east, exactly
    # like the base -- the Tables signature survives the muster.
    import Tables as TB

    orders, _ = run_turn([(5, 5)], [(5, 8)], my_hills=[(12, 0)])
    fake = FakeAnts([(5, 5)], [(5, 8)], my_hills=[(12, 0)])
    TB.Tables().do_turn(fake)
    assert orders == fake.orders == [((5, 5), "e")]


def test_packed_ant_advances_to_win() -> None:
    # (5, 5) holds three friends within 10 and steps east onto
    # (5, 6): one foe in range, one pal ((3, 5)) in range -- a table
    # WIN that needs no hill and no join.
    mine = [(5, 5), (5, 3), (3, 5), (5, 1)]
    orders, _ = run_turn(mine, [(5, 8)])
    assert orders[0] == ((5, 5), "e")


def test_joined_pair_trades_without_hills() -> None:
    # A steps (5, 5)->(5, 6) and B steps (5, 11)->(5, 10): each
    # sees exactly the one foe (5, 8) with no pals in range -- a
    # friendless 1v1 TRADE each. No hills are held, so the base
    # hill gate would refuse; the foe draws 2 commitments, so the
    # join releases both steps.
    mine = [(5, 5), (5, 11), (5, 2), (2, 5), (8, 5), (5, 14), (2, 11), (8, 11)]
    foes = [(5, 8)]
    orders, _ = run_turn(mine, foes)
    assert orders[0] == ((5, 5), "e")
    assert orders[1] == ((5, 11), "w")


def test_base_refuses_the_same_joined_board() -> None:
    # The identical board on the Tables base: no hills, so the
    # friendless TRADE refuses and the ant explores north instead.
    # Proves the join release is the Tables8 difference.
    import Tables as TB

    mine = [(5, 5), (5, 11), (5, 2), (2, 5), (8, 5), (5, 14), (2, 11), (8, 11)]
    fake = FakeAnts(mine, [(5, 8)])
    TB.Tables().do_turn(fake)
    assert fake.orders[0] == ((5, 5), "n")
    assert ((5, 5), "e") not in fake.orders


def test_lose_still_refuses_when_packed() -> None:
    # Packed ant facing two foes from (5, 6) is ours 1 vs 2 -- a
    # table LOSE with no join (each foe draws one commitment), so
    # it refuses and explores north.
    mine = [(5, 5), (5, 2), (2, 5), (8, 5)]
    orders, _ = run_turn(mine, [(5, 8), (6, 7)])
    assert orders[0] == ((5, 5), "n")
    assert ((5, 5), "e") not in orders


def test_economy_matches_base_without_contact() -> None:
    # No enemies anywhere: food claims and explore fall-through
    # run the carried-forward base code, so every order matches.
    import Tables as TB

    for mine, foods in [
        ([(5, 5), (2, 2)], [(5, 6), (2, 3)]),
        ([(10, 10)], []),
        ([(10, 8), (10, 11)], [(0, 0)]),
    ]:
        orders, _ = run_turn(mine, [], foods)
        fake = FakeAnts(mine, [], foods)
        TB.Tables().do_turn(fake)
        assert orders == fake.orders


def test_guard_matches_base_when_contact_free() -> None:
    # Threatened hill, contact-free squares: the holder steps onto
    # the hill and the extra screens to the intercept -- guard runs
    # before seek, so every order matches the base.
    import Tables as TB

    mine = [(10, 8), (10, 11)]
    enemies = [(10, 16)]
    orders, _ = run_turn(mine, enemies, my_hills=[(10, 10)])
    fake = FakeAnts(mine, enemies, my_hills=[(10, 10)])
    TB.Tables().do_turn(fake)
    assert orders == fake.orders == [((10, 8), "e"), ((10, 11), "e")]


def test_muster_matches_base_without_enemies() -> None:
    # Muster march with no enemies visible: identical orders.
    import Tables as TB

    orders, _ = run_turn([(10, 10)], [], enemy_hills=[(15, 15)])
    fake = FakeAnts([(10, 10)], [], enemy_hills=[(15, 15)])
    TB.Tables().do_turn(fake)
    assert orders == fake.orders
    assert len(orders) == 1


def test_water_maze_turn_under_1s() -> None:
    # Water forces long BFS detours; the 250-expansion budget and
    # the join pre-pass still keep a 60-ant turn inside budget.
    water = {(r, c) for r in range(ROWS) for c in range(COLS) if (r + c) % 7 == 0}
    mine = [(i % ROWS, (i * 3 + 1) % COLS) for i in range(60)]
    mine = [m for m in mine if m not in water]
    foes = [((i * 5 + 2) % ROWS, (i * 11 + 4) % COLS) for i in range(10)]
    foes = [f for f in foes if f not in water]
    foods = [((i * 3 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(10)]
    foods = [f for f in foods if f not in water]
    start = time.perf_counter()
    run_turn(mine, foes, foods, my_hills=[(0, 1)], enemy_hills=[(19, 18)])
    assert time.perf_counter() - start < 1.0


def test_lone_ant_explores() -> None:
    # No friends at all: no pal to pack toward, the friendless
    # TRADE refuses, so the ant explores north.
    orders, _ = run_turn([(5, 5)], [(5, 8)])
    assert orders == [((5, 5), "n")]


def test_claimed_ant_does_not_commit() -> None:
    # (5, 13) claims the food at (5, 10), so it never reaches the
    # seek branch and never commits; (5, 5) commits alone to
    # (5, 8), draws only one commitment, stays unjoined, and
    # refuses the hill-less TRADE by exploring north.
    mine = [(5, 5), (5, 13)]
    orders, _ = run_turn(mine, [(5, 8)], foods=[(5, 10)])
    assert orders == [((5, 5), "n"), ((5, 13), "w")]


def test_adjacent_pair_splits_roles() -> None:
    # Two adjacent packless ants facing one foe: the rear ant's
    # pack-up step lands on its partner's square (occupied), so it
    # explores north; the front ant sees a backed 2v1 WIN onto
    # (5, 7) and takes the free kill east.
    orders, _ = run_turn([(5, 5), (5, 6)], [(5, 9)])
    assert orders == [((5, 5), "n"), ((5, 6), "e")]


def test_guard_screen_matches_base() -> None:
    # Razer two steps from the hill: the holder steps on, and the
    # rear ants find the screening corridor still occupied (in
    # turn-start positions) and explore north -- guard runs before
    # seek and the lone commitment draws no join, so every order
    # matches the base.
    import Tables as TB

    mine = [(10, 9), (10, 8), (10, 7), (10, 6)]
    enemies = [(10, 12)]
    orders, _ = run_turn(mine, enemies, my_hills=[(10, 10)])
    fake = FakeAnts(mine, enemies, my_hills=[(10, 10)])
    TB.Tables().do_turn(fake)
    assert (
        orders
        == fake.orders
        == [
            ((10, 9), "e"),
            ((10, 8), "n"),
            ((10, 7), "n"),
            ((10, 6), "n"),
        ]
    )


def _sq20(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr * dr + dc * dc


def test_fuzz_never_donates_or_crashes() -> None:
    # Seeded random boards with no hills anywhere (muster never
    # goes fearless, hill cover never applies): every issued step
    # must land on a unique passable square and never step into a
    # locally-losing contact (ours < theirs with foes present).
    import random

    for seed in (1234, 555, 987654):
        rng = random.Random(seed)
        for _ in range(200):
            cells = [(r, c) for r in range(ROWS) for c in range(COLS)]
            rng.shuffle(cells)
            water = set(cells[: rng.randint(0, 12)])
            rest = [c for c in cells if c not in water]
            mine = rest[: rng.randint(1, 8)]
            foes = rest[len(mine) : len(mine) + rng.randint(0, 5)]
            foods = rest[
                len(mine) + len(foes) : len(mine) + len(foes) + rng.randint(0, 4)
            ]
            orders, _ = run_turn(mine, foes, foods, water=water)
            dests = set()
            for loc, d in orders:
                dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
                assert dest not in water
                assert dest not in mine
                assert dest not in foes
                assert dest not in dests
                dests.add(dest)
                foes_at = sum(1 for e in foes if _sq20(dest, e) <= 5)
                if foes_at:
                    ours_at = (
                        sum(1 for f in mine if f != loc and _sq20(dest, f) <= 5) + 1
                    )
                    assert ours_at >= foes_at, (mine, foes, loc, d)


def test_packed_ant_takes_hill_covered_trade() -> None:
    # (5, 5) holds a pack but sees a friendless 1v1 TRADE onto
    # (5, 6) with no join (supporters sit out of seek range):
    # 13 steps from the held hill, so hill cover sends it east.
    mine = [(5, 5), (5, 19), (5, 18), (5, 17)]
    orders, _ = run_turn(mine, [(5, 8)], my_hills=[(12, 0)])
    assert orders[0] == ((5, 5), "e")


def test_two_turns_carry_state() -> None:
    # A foe stepping from (5, 9) to (5, 8) closes on our hill: turn
    # 1 the step east is contact-free (SAFE) so the lone ant
    # explores north; turn 2 the same step is a friendless 1v1
    # under hill cover, so it sacrifices east. Headings, visits,
    # and hill memory persist across both turns without crashing.
    import Tables8 as T8mod

    bot = T8mod.Tables8()
    fake1 = FakeAnts([(5, 5)], [(5, 9)], my_hills=[(5, 5)])
    bot.do_turn(fake1)
    fake2 = FakeAnts([(5, 5)], [(5, 8)], my_hills=[(5, 5)])
    bot.do_turn(fake2)
    assert fake1.orders == [((5, 5), "n")]
    assert fake2.orders == [((5, 5), "e")]


def test_march_matches_base_with_distant_foes() -> None:
    # Remembered hill, foes out of seek range: no commitments, no
    # join, so the muster march matches the base exactly.
    import Tables as TB

    mine = [(10, 10), (10, 11)]
    orders, _ = run_turn(mine, [(0, 0)], enemy_hills=[(15, 15)])
    fake = FakeAnts(mine, [(0, 0)], enemy_hills=[(15, 15)])
    TB.Tables().do_turn(fake)
    assert orders == fake.orders
    assert len(orders) == 2


def test_fuzz_with_hills_never_crashes() -> None:
    # Seeded random boards with hills held and remembered (muster
    # can march fearless, hill cover applies): every issued step
    # must land on a unique passable square; no turn may raise.
    import random

    rng = random.Random(777)
    for _ in range(100):
        cells = [(r, c) for r in range(ROWS) for c in range(COLS)]
        rng.shuffle(cells)
        water = set(cells[: rng.randint(0, 12)])
        rest = [c for c in cells if c not in water]
        mine = rest[: rng.randint(1, 8)]
        foes = rest[len(mine) : len(mine) + rng.randint(0, 5)]
        base = len(mine) + len(foes)
        foods = rest[base : base + rng.randint(0, 4)]
        mine_hills = rest[base + len(foods) : base + len(foods) + rng.randint(0, 2)]
        foe_hills = rest[
            base + len(foods) + len(mine_hills) : base
            + len(foods)
            + len(mine_hills)
            + rng.randint(0, 2)
        ]
        orders, _ = run_turn(
            mine, foes, foods, water=water, enemy_hills=foe_hills, my_hills=mine_hills
        )
        dests = set()
        for loc, d in orders:
            dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
            assert dest not in water
            assert dest not in dests
            dests.add(dest)


def test_same_board_gives_same_orders() -> None:
    # Fresh bots on the same board decide identically: no
    # set-iteration or dict-order nondeterminism in the press.
    mine = [(5, 5), (5, 11), (5, 2), (2, 5), (8, 5), (5, 14), (2, 11), (8, 11)]
    first, _ = run_turn(mine, [(5, 8)], foods=[(0, 0)], my_hills=[(12, 0)])
    for _ in range(3):
        again, _ = run_turn(mine, [(5, 8)], foods=[(0, 0)], my_hills=[(12, 0)])
        assert again == first


def test_blob_warfare_stays_disciplined_and_lively() -> None:
    # Seeded blob-vs-blob boards with no hills: armies start in
    # contact range, so turns must contain contact steps (liveness)
    # yet never a locally-losing one (discipline).
    import random

    rng = random.Random(99)
    lively = 0
    for _ in range(60):
        mine = [((8 + rng.randint(-2, 2)) % ROWS, (8 + rng.randint(-2, 2)) % COLS)]
        mine += [
            (
                (mine[0][0] + rng.randint(-3, 3)) % ROWS,
                (mine[0][1] + rng.randint(-3, 3)) % COLS,
            )
            for _ in range(rng.randint(3, 7))
        ]
        foes = [
            ((12 + rng.randint(-2, 2)) % ROWS, (10 + rng.randint(-2, 2)) % COLS)
            for _ in range(rng.randint(2, 5))
        ]
        orders, _ = run_turn(mine, foes)
        for loc, d in orders:
            dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
            foes_at = sum(1 for e in foes if _sq20(dest, e) <= 5)
            if foes_at:
                lively += 1
                ours_at = sum(1 for f in mine if f != loc and _sq20(dest, f) <= 5) + 1
                assert ours_at >= foes_at, (mine, foes, loc, d)
    assert lively > 20


def test_no_enemies_means_base_parity_for_three_turns() -> None:
    # With no visible enemies the press never fires (the join
    # pre-pass skips, seek never runs), so three full turns with
    # food, water, hills, and hill memory match the base exactly.
    import Tables as TB

    t8, tb = T8.Tables8(), TB.Tables()
    mine = [(5, 5), (5, 6), (2, 2), (15, 15)]
    foods = [(5, 8), (2, 5), (14, 14)]
    water = {(6, 6), (6, 7), (3, 3)}
    for _ in range(3):
        f8 = FakeAnts(mine, [], foods, water, enemy_hills=[(18, 18)], my_hills=[(5, 5)])
        fb = FakeAnts(mine, [], foods, water, enemy_hills=[(18, 18)], my_hills=[(5, 5)])
        t8.do_turn(f8)
        tb.do_turn(fb)
        assert f8.orders == fb.orders
        # Ants advance: next turn starts from the new squares.
        moved = {loc: AIM[d] for loc, d in f8.orders}
        mine = [
            (
                (r + moved.get((r, c), (0, 0))[0]) % ROWS,
                (c + moved.get((r, c), (0, 0))[1]) % COLS,
            )
            for r, c in mine
        ]


def test_pack_converges_on_a_static_foe() -> None:
    # Six turns of pursuit against a foe holding (5, 12): the
    # army's closest distance must shrink every turn and end in
    # contact range -- the press converges instead of milling.
    import Tables8 as T8mod

    bot = T8mod.Tables8()
    mine = [(5, 5), (5, 4), (4, 5), (6, 5)]
    foe = [(5, 12)]
    dists = []
    for _ in range(6):
        fake = FakeAnts(mine, foe)
        bot.do_turn(fake)
        step = {loc: AIM[d] for loc, d in fake.orders}
        mine = [
            (
                (r + step.get((r, c), (0, 0))[0]) % ROWS,
                (c + step.get((r, c), (0, 0))[1]) % COLS,
            )
            for r, c in mine
        ]
        dists.append(min(_dist(m, foe[0]) for m in mine))
    assert dists == sorted(dists, reverse=True), dists
    assert dists[-1] <= 2


def test_packed_safe_approach_advances() -> None:
    # Packed and contact-free onto (5, 6): an empty-square press
    # goes east, exactly like the base.
    import Tables as TB

    mine = [(5, 5), (5, 4), (5, 3), (5, 2)]
    orders, _ = run_turn(mine, [(5, 12)])
    fake = FakeAnts(mine, [(5, 12)])
    TB.Tables().do_turn(fake)
    assert orders[0] == fake.orders[0] == ((5, 5), "e")


def test_packed_unjoined_trade_refuses() -> None:
    # Packed 1v1 TRADE with no join and no hills: refuses and
    # explores north -- the open-field discipline holds for packs.
    mine = [(5, 5), (5, 19), (5, 18), (5, 17)]
    orders, _ = run_turn(mine, [(5, 8)])
    assert orders[0] == ((5, 5), "n")
    assert ((5, 5), "e") not in orders


def test_packless_lose_packs_up() -> None:
    # Outnumbered 1v2 from (5, 6) is LOSE: instead of exploring,
    # the packless ant packs up west toward its partner.
    orders, _ = run_turn([(5, 5), (5, 1)], [(5, 8), (6, 7)])
    assert orders[0] == ((5, 5), "w")
    assert ((5, 5), "e") not in orders


def test_denied_cluster_with_press_stays_legal() -> None:
    # A food cluster contested by 4 foes draws capped denial
    # claims; the claim-free ants press or pack up around it.
    # No hills: every contact step must still be non-losing.
    import random

    rng = random.Random(2026)
    for _ in range(60):
        foods = [
            ((5 + rng.randint(-3, 3)) % ROWS, (5 + rng.randint(-3, 3)) % COLS)
            for _ in range(5)
        ]
        foes = [
            ((5 + rng.randint(-4, 4)) % ROWS, (5 + rng.randint(-4, 4)) % COLS)
            for _ in range(4)
        ]
        mine = [
            ((rng.randint(0, ROWS - 1), rng.randint(0, COLS - 1))) for _ in range(6)
        ]
        orders, _ = run_turn(mine, foes, foods)
        dests = set()
        for loc, d in orders:
            dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
            assert dest not in dests
            dests.add(dest)
            foes_at = sum(1 for e in foes if _sq20(dest, e) <= 5)
            if foes_at:
                ours_at = sum(1 for f in mine if f != loc and _sq20(dest, f) <= 5) + 1
                assert ours_at >= foes_at, (mine, foes, foods, loc, d)


def test_setup_rebuilds_tables_and_resets() -> None:
    # The engine path (do_setup once, then turns) rebuilds the
    # precomputed table and clears per-turn caches before play.
    bot = T8.Tables8()
    bot.do_setup(FakeAnts([(5, 5)], []))
    assert bot.battle_table[(2, 2)] == T8.TRADE
    assert bot.battle_table[(1, 0)] == T8.SAFE
    fake = FakeAnts([(5, 5)], [(5, 8)])
    bot.do_turn(fake)
    assert fake.orders == [((5, 5), "n")]


def test_army_marches_on_remembered_hill() -> None:
    # Six turns marching a remembered hill past two guards: the
    # army jostles at first (corridor occupied) then converges
    # from 9 steps out to contact range, with legal orders every
    # turn and no crashes.
    import Tables8 as T8mod

    bot = T8mod.Tables8()
    mine = [(10, 10), (10, 11), (9, 10), (11, 10)]
    foes = [(15, 14), (14, 15)]
    for _ in range(6):
        fake = FakeAnts(mine, foes, enemy_hills=[(15, 15)])
        bot.do_turn(fake)
        step = {loc: AIM[d] for loc, d in fake.orders}
        for loc, d in fake.orders:
            dest = ((loc[0] + AIM[d][0]) % ROWS, (loc[1] + AIM[d][1]) % COLS)
            assert dest not in mine
        mine = [
            (
                (r + step.get((r, c), (0, 0))[0]) % ROWS,
                (c + step.get((r, c), (0, 0))[1]) % COLS,
            )
            for r, c in mine
        ]
    assert min(abs(r - 15) + abs(c - 15) for r, c in mine) <= 3


def test_table_core_preserved() -> None:
    # The precomputed core is untouched: built at construction,
    # WIN/TRADE/LOSE verdicts intact, huge crowds clamp.
    bot = T8.Tables8()
    assert bot.battle_table[(2, 1)] == T8.WIN
    assert bot.battle_table[(1, 1)] == T8.TRADE
    assert bot.battle_table[(1, 2)] == T8.LOSE
    assert T8.lookup_verdict(bot.battle_table, 100, 100) == T8.TRADE


def test_no_live_resolution_in_source() -> None:
    # Fidelity: per-turn code never re-derives outcomes (no
    # weakness arithmetic), it only counts locals and looks up.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Tables8.py")
    with open(path) as fh:
        source = fh.read()
    assert "weakness" not in source
    assert "import combat" not in source
    assert "from combat" not in source


def test_full_turn_crowded_under_1s() -> None:
    # A full crowded turn -- 48 ants, 12 foes, food, hills -- stays
    # well inside the turn budget, join pre-pass included.
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(12)]
    foods = [((i * 3 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(10)]
    start = time.perf_counter()
    run_turn(mine, foes, foods, my_hills=[(0, 0)], enemy_hills=[(19, 19)])
    assert time.perf_counter() - start < 1.0
