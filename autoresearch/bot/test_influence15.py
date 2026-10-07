#!/usr/bin/env python
"""Regroup-on-refusal tests (Influence15 entry).

Self-contained: FakeAnts plus the staged Influence10 entry and
Influence15 only, never the shared combat.py helpers. Influence15
keeps the whole Influence8 tree (the staged Influence10 file minus
its backup-priced KILL, which scored 32.4 against Influence8's
45.9) and changes exactly two mechanisms (a new mix: verdicts
plus regroup plus scout): in the seek branch the Influence8
verdict still decides every advance, but a refused hunter with no
pack -- fewer than PACK_NEED (3) friends within PACK_RADIUS (10)
steps -- regroups one step toward its nearest friend under the
normal safety filter (Crowd's leg-6 rule, copied) instead of
diffusing away through explore; and idle ants scout the unseen
edge (Duelist's edge BFS, DIE-skipped, unstamped) before falling
back to least-visited explore. Packing only redirects refusals,
so free advances march exactly as base.

Consequences pinned here:

- has_pack geometry unit (need, radius, self-exclusion);
- unpacked SAFE marches preserved byte-identically (free wins
  are never ceded for cohesion);
- the DIE-path discriminator: two foes make the east step DIE --
  base refuses and explores north while Influence15 regroups
  south toward its pal (explore's first viable pick differs from
  the regroup direction, so the orders visibly split);
- the lone-ant edge: no pal to regroup toward, so byte-identical
  base behavior with no crash and no forced clumping;
- packed hunters order byte-identical to base (regroup never
  fires for packed ants; every contact verdict pinned SAFE so
  pricing cannot diverge either);
- quiet boards order byte-identical to base (food, hills, guard)
  with no ant reaching explore, so the scout stays dark;
- packed deadlock-KILL still marches (Influence8 aggression kept);
- blocked approvals fall through to explore exactly as base
  (packing fires on verdict refusals, never on blocked takes);
- failed guard with an approved hunt marches exactly as base;
- three-turn state stays consistent (orders valid, hills remembered);
- the full turn stays under 1s crowded;
- regroup holds on a tall map with a bigger attack reach;
- idle ants scout the unseen edge (Duelist's edge BFS, DIE-skipped);
- fully-seen boards fall back to base-identical explore;
- the scout refuses DIE first steps exactly like explore;
- the KILL-path discriminator: a refused out-of-contact KILL
  regroups south while base wanders north, with no pricing
  involved;
- a remembered hill disables regroup (hill races keep base muster);
- sighting a hill mid-game closes regroup from the next turn;
- entry self-containment.

Pins (a) the pack geometry unit, (b) free-march identity, (c)
the DIE-path split where Influence15 steps south while base
explores north, (d) lone-ant identity, (e) packed-hunter
identity, (f) quiet-board identity, (g) deadlock-KILL retention,
(h) blocked-approval identity, (i) guard-fail identity, (j)
multi-turn consistency, (k) cost, (l) tall-map identity, (m) the
unseen-edge scout split, (n) fully-seen fallback identity, (o)
scout DIE-skip identity, (p) the KILL-path regroup split,
(q) hill-gate identity, (s) the mid-game gate transition, and
(r) self-containment.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Influence10 as Base  # noqa: E402
import Influence15 as New  # noqa: E402

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

    def visible(self, loc: Loc) -> bool:
        # Stand-in for engine vision (viewradius2 55 ~ euclidean 7.4):
        # seen when within toroidal manhattan 7 of any own ant.
        return any(_manhattan(loc, a) <= 7 for a in self._mine)

    def issue_order(self, order: tuple[Loc, str]) -> None:
        self.orders.append(order)

    def time_remaining(self) -> int:
        return 100000


def run_both(
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
) -> tuple[list[tuple[Loc, str]], list[tuple[Loc, str]]]:
    """Same fresh turn through base and Influence15; returns both orders."""
    fake_base = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    Base.Influence10().do_turn(fake_base)
    fake_new = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    New.Influence15().do_turn(fake_new)
    return fake_base.orders, fake_new.orders


def _manhattan(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


def test_has_pack_geometry() -> None:
    # (a) Unit: the ant itself never counts; need is 3 friends
    # within radius 10; the boundary is inclusive.
    assert New.PACK_NEED == 3
    assert New.PACK_RADIUS == 10
    anchor = (10, 10)
    pals = [(10, 11), (10, 12), (10, 9)]
    assert New.has_pack(anchor, [anchor] + pals, _manhattan) is True
    assert New.has_pack(anchor, [anchor] + pals[:2], _manhattan) is False
    # Radius is inclusive: a pal exactly 10 away still counts.
    far = [(10, 0), (0, 10), (10, 12)]
    assert all(_manhattan(anchor, p) == 10 for p in far[:2])
    assert New.has_pack(anchor, [anchor] + far, _manhattan) is True
    # A pal 11 away does not count; wrap-around counts as near.
    assert _manhattan((0, 0), (0, 19)) == 1  # sanity: wrap is near
    assert New.has_pack((0, 0), [(0, 0), (0, 11)], _manhattan) is False
    # Lone ant: no pack.
    assert New.has_pack(anchor, [anchor], _manhattan) is False


def test_unpacked_safe_march_preserved() -> None:
    # (b) Free wins are never ceded: unpacked H=(10,10) hunts
    # F=(10,15) due east; the east step D=(10,11) sits 4 from F
    # (outside the reach-3 diamond) with H stamped on it, so
    # mid-turn reads ours 1 vs theirs 0 -> SAFE. The verdict takes
    # it in both bots -- packing only redirects refusals, so H
    # marches east identically while pal P=(10,5) explores north
    # (P is unpacked but out of seek range, so it never hunts).
    H = (10, 10)
    P = (10, 5)
    F = (10, 15)
    D = (10, 11)
    assert _manhattan(H, F) == 5
    assert _manhattan(H, P) == 5
    assert _manhattan(P, F) == 10
    live, foe = New.influence_fields([H, P], [F], ROWS, COLS, 3)
    assert New.rate_step(live, foe, D) == New.SAFE
    assert New.has_pack(H, [H, P], _manhattan) is False
    base_orders, new_orders = run_both([H, P], [F])
    assert dict(base_orders) == {H: "e", P: "n"}
    assert new_orders == base_orders


def test_unpacked_hunter_packs_up_instead_of_explore() -> None:
    # (c) Crowd-hold discriminator on a DIE step. H=(10,12) faces
    # F=(10,15) and F2=(10,16): the east step D=(10,13) reads
    # theirs 2 vs ours 1 -> DIE, so base refuses and its explore
    # walks H north (first viable pick: north SAFE and safe, east
    # DIE). H's pal P=(16,12) sits 6 south -- unpacked, out of
    # seek range (9+ from both foes), exploring north identically
    # in both bots. Influence15 packs H up south toward P, so the
    # orders split north/south with no KILL anywhere (backup
    # pricing cannot explain the split).
    H = (10, 12)
    P = (16, 12)
    F = (10, 15)
    F2 = (10, 16)
    D = (10, 13)
    assert _manhattan(H, F) == 3
    assert _manhattan(H, P) == 6
    assert _manhattan(P, F) == 9
    live, foe = New.influence_fields([H, P], [F, F2], ROWS, COLS, 3)
    assert New.rate_step(live, foe, D) == New.DIE
    assert New.rate_step(live, foe, (9, 12)) == New.SAFE
    assert New.rate_step(live, foe, (11, 12)) == New.SAFE
    assert New.has_pack(H, [H, P], _manhattan) is False
    base_orders, new_orders = run_both([H, P], [F, F2])
    assert dict(base_orders) == {H: "n", P: "n"}
    assert dict(new_orders) == {H: "s", P: "n"}
    assert new_orders != base_orders


def test_lone_ant_hunts_exactly_like_base() -> None:
    # (d) No pal at all: nothing to regroup toward, so the lone
    # hunter keeps the exact base behavior -- marching the SAFE east
    # step alone. Pins the single-ant edge: no crash, no forced
    # clumping, byte-identical orders.
    H = (10, 10)
    F = (10, 15)
    live, foe = New.influence_fields([H], [F], ROWS, COLS, 3)
    assert New.rate_step(live, foe, (10, 11)) == New.SAFE
    base_orders, new_orders = run_both([H], [F])
    assert new_orders == base_orders
    assert dict(new_orders) == {H: "e"}


def test_packed_hunters_byte_identical_to_base() -> None:
    # (e) A packed 2x2 block hunts a distant lone foe with a hill
    # in play: every ant holds 3 friends within 10, so pack-up
    # never fires, and every contact verdict reads SAFE (pinned),
    # so base's backup pricing cannot fire either. The leader
    # SAFE-marches east while the followers muster on the hill --
    # no ant reaches explore, so the scout stays dark and every
    # order must match base exactly.
    block = [(10, 10), (10, 11), (11, 10), (11, 11)]
    F = (10, 18)
    for ant in block:
        assert New.has_pack(ant, block, _manhattan) is True
    live, foe = New.influence_fields(block, [F], ROWS, COLS, 3)
    assert New.rate_step(live, foe, (10, 12)) == New.SAFE
    assert New.rate_step(live, foe, (10, 11)) == New.SAFE
    base_orders, new_orders = run_both(block, [F], enemy_hills=[(15, 15)])
    assert new_orders == base_orders
    assert dict(new_orders)[(10, 11)] == "e"


def test_quiet_boards_byte_identical_to_base() -> None:
    # (f) Nothing to pack up for on quiet boards -- food-only race,
    # hills to muster with no foes, a lone guard marching home, and
    # a packed cluster splitting food and muster -- and no ant ever
    # reaches explore, so the scout stays dark and every order
    # matches base exactly (the scout only fires for idle ants).
    block = [(10, 10), (10, 11), (11, 10), (11, 11)]
    quiet: list[
        tuple[
            list[Loc], list[Loc], list[Loc] | None, list[Loc] | None, list[Loc] | None
        ]
    ] = [
        ([(5, 5)], [], [(0, 0)], None, None),
        ([(5, 5)], [], [(0, 0)], [(15, 15)], None),
        ([(10, 11)], [(10, 15)], None, None, [(10, 10)]),
        (block, [(19, 19)], [(1, 1)], [(15, 15)], None),
    ]
    for mine, foes, foods, hills, my_hills in quiet:
        base_orders, new_orders = run_both(
            mine, foes, foods=foods, enemy_hills=hills, my_hills=my_hills
        )
        assert new_orders == base_orders


def test_packed_deadlock_kill_still_marches() -> None:
    # (g) Influence8 aggression retained where it matters: packed
    # hunter H stands in contact with F (squared distance 4) with
    # west walled by water -- every free neighbor reads mid-turn
    # KILL, so no SAFE move exists and the deadlock KILL marches
    # east in both bots (no hills anywhere, so pricing and hill
    # push cannot explain it; the veto keeps a mid-KILL that reads
    # final KILL). Three pals give H its pack (7/9/9 steps) while standing
    # clear of seek range themselves, marching adjacent food claims
    # identically -- no ant explores, so the scout stays dark.
    H = (10, 12)
    pals = [(10, 5), (12, 5), (8, 5)]
    foods = [(9, 5), (13, 5), (7, 5)]
    F = (10, 14)
    water = {(10, 11)}
    mine = [H] + pals
    assert New.has_pack(H, mine, _manhattan) is True
    assert all(_manhattan(p, F) > 8 for p in pals)
    live, foe = New.influence_fields(mine, [F], ROWS, COLS, 3)
    assert New.rate_step(live, foe, (10, 13)) == New.KILL
    assert New.rate_step(live, foe, (9, 12)) == New.KILL
    assert New.rate_step(live, foe, (11, 12)) == New.KILL
    fake_base = FakeAnts(mine, [F], foods=foods, water=water)
    Base.Influence10().do_turn(fake_base)
    fake_new = FakeAnts(mine, [F], foods=foods, water=water)
    New.Influence15().do_turn(fake_new)
    assert dict(fake_base.orders) == {H: "e", (10, 5): "n", (12, 5): "s", (8, 5): "n"}
    assert fake_new.orders == fake_base.orders


def test_blocked_hunt_falls_through_like_base() -> None:
    # (h) Adjacent unpacked pair facing a foe: the leader's approved
    # east step lands on its pal's occupied tile and fails, so both
    # fall through to explore exactly as base (packing only fires
    # on verdict refusals, never on blocked approvals). The trailer
    # hunts east alone in both bots. Pins the fallthrough: no crash,
    # byte-identical orders.
    H = (10, 10)
    P = (10, 11)
    F = (10, 15)
    assert New.has_pack(H, [H, P], _manhattan) is False
    assert New.has_pack(P, [H, P], _manhattan) is False
    base_orders, new_orders = run_both([H, P], [F])
    assert dict(base_orders) == {H: "n", P: "e"}
    assert new_orders == base_orders


def test_failed_guard_hunts_like_base() -> None:
    # (i) Guard interplay: A holds its own threatened hill (so its
    # guard step is None) while unpacked, with pal P two south and
    # a foe five east. The approved SAFE east step marches in both
    # bots -- packing only redirects refusals, and guard-failures
    # with approved hunts are untouched. Pins full identity here.
    A = (10, 10)
    P = (12, 10)
    F = (10, 15)
    assert _manhattan(A, F) == 5
    assert _manhattan(A, P) == 2
    assert New.has_pack(A, [A, P], _manhattan) is False
    live, foe = New.influence_fields([A, P], [F], ROWS, COLS, 3)
    assert New.rate_step(live, foe, (10, 11)) == New.SAFE
    base_orders, new_orders = run_both([A, P], [F], my_hills=[(10, 10)])
    assert new_orders == base_orders
    assert dict(new_orders)[A] == "e"


def test_multi_turn_state_stays_consistent() -> None:
    # (j) Three full turns with food, a remembered hill, and foes:
    # every order each turn comes from a current own ant, no turn
    # raises, and the hill memory latches across turns.
    AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
    bot = New.Influence15()
    mine = [(5, 5), (5, 6), (6, 5), (10, 10), (10, 3)]
    foes = [(10, 15), (10, 16), (4, 4)]
    start = time.perf_counter()
    seen_sizes = []
    for _ in range(3):
        fake = FakeAnts(mine, foes, foods=[(0, 0), (19, 19)], enemy_hills=[(15, 15)])
        bot.do_turn(fake)
        seen_sizes.append(len(bot.seen))
        for src, direction in fake.orders:
            assert src in mine
            assert direction in AIM
        moved = dict(fake.orders)
        mine = [
            ((a[0] + AIM[moved[a]][0]) % ROWS, (a[1] + AIM[moved[a]][1]) % COLS)
            if a in moved
            else a
            for a in mine
        ]
    assert time.perf_counter() - start < 1.0
    assert (15, 15) in bot.remembered_hills
    assert seen_sizes == sorted(seen_sizes)  # memory only grows
    assert seen_sizes[-1] > 0


def test_full_turn_costs_under_1s_on_crowded_board() -> None:
    # (k) A full crowded turn -- 30 ants a side plus food and two
    # contested hills -- finishes far inside one second; regroup
    # adds one linear friend scan per refused hunt and the scout
    # BFS is budget-capped with a fully-seen short-circuit.
    ours = [((i * 7 + 1) % ROWS, (i * 5 + 2) % COLS) for i in range(30)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [((i * 3 + 9) % ROWS, (i * 17 + 4) % COLS) for i in range(10)]
    start = time.perf_counter()
    base_orders, new_orders = run_both(
        ours, foes, foods=foods, enemy_hills=[(10, 10), (10, 3)]
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert isinstance(new_orders, list)
    assert isinstance(base_orders, list)


def test_tall_map_with_big_reach_matches_base() -> None:
    # (l) Size-independence: a 30x40 board with attackradius2 18
    # (reach 5). H=(15,20) hunts F=(15,27) due east; the east step
    # D=(15,21) sits 6 from F (outside the reach-5 diamond), so
    # mid-turn reads SAFE and the approved march goes through in
    # both bots (packing only redirects refusals). Pal P=(15,10)
    # sits 10 west, unpacked but out of seek range, exploring north
    # identically in both bots.
    assert New.threat_reach(18) == 5
    H = (15, 20)
    P = (15, 10)
    F = (15, 27)
    D = (15, 21)
    base_fake = FakeAnts([H, P], [F])
    base_fake.rows = 30
    base_fake.cols = 40
    base_fake.attackradius2 = 18
    new_fake = FakeAnts([H, P], [F])
    new_fake.rows = 30
    new_fake.cols = 40
    new_fake.attackradius2 = 18
    live, foe = New.influence_fields([H, P], [F], 30, 40, 5)
    assert New.rate_step(live, foe, D) == New.SAFE
    Base.Influence10().do_turn(base_fake)
    New.Influence15().do_turn(new_fake)
    assert dict(base_fake.orders) == {H: "e", P: "n"}
    assert new_fake.orders == base_fake.orders


def test_idle_ant_scouts_unseen_edge_instead_of_wandering() -> None:
    # (m) Duelist-scout discriminator: lone H=(10,10) with every
    # square seen except far-east U=(10,18) (8 away, outside vision,
    # so it stays unseen). No food, foes, or hills: base wanders
    # north off least-visited; Influence15 BFS-scouts the unseen
    # edge and marches east down the unique-shortest corridor.
    H = (10, 10)
    U = (10, 18)
    assert _manhattan(H, U) == 8
    seen = {(r, c) for r in range(ROWS) for c in range(COLS)} - {U}
    base_orders, _ = run_both([H], [])
    assert dict(base_orders) == {H: "n"}
    bot = New.Influence15()
    bot.seen = set(seen)
    fake = FakeAnts([H], [])
    bot.do_turn(fake)
    assert U not in bot.seen  # still out of vision
    assert dict(fake.orders) == {H: "e"}


def test_fully_seen_board_falls_back_to_base_explore() -> None:
    # (n) Nothing unseen: the scout finds no edge and the ant falls
    # back to least-visited explore, byte-identical to base, while
    # the turn banks the whole board into seen-memory.
    H = (10, 10)
    bot = New.Influence15()
    bot.seen = {(r, c) for r in range(ROWS) for c in range(COLS)}
    fake = FakeAnts([H], [])
    bot.do_turn(fake)
    base_orders, _ = run_both([H], [])
    assert fake.orders == base_orders
    assert dict(fake.orders) == {H: "n"}
    assert len(bot.seen) == ROWS * COLS


def test_scout_skips_die_first_step() -> None:
    # (o) Scout caution: H=(10,12) faces F=(10,12+2) and F2 one
    # further east, so the east edge-step onto (10,13) reads DIE
    # (theirs 2 vs ours 1) and is refused; both bots fall back to
    # least-visited explore and walk west off the KILL-safe tile.
    # Pins the DIE-skip on the scout path: no KILL-chasing into
    # fog, full identity with base when the edge is shut.
    H = (10, 12)
    F = (10, 14)
    F2 = (10, 15)
    U = (10, 18)
    seen = {(r, c) for r in range(ROWS) for c in range(COLS)} - {U}
    live, foe = New.influence_fields([H], [F, F2], ROWS, COLS, 3)
    assert New.rate_step(live, foe, (10, 13)) == New.DIE
    assert U not in seen
    bot = New.Influence15()
    bot.seen = set(seen)
    fake = FakeAnts([H], [F, F2])
    bot.do_turn(fake)
    base_orders, _ = run_both([H], [F, F2])
    assert fake.orders == base_orders
    assert dict(fake.orders) == {H: "w"}


def test_refused_kill_regroups_instead_of_diffusing() -> None:
    # (p) Core regroup discriminator on a KILL step. H=(10,12)
    # hunts F=(10,15): the east step D=(10,13) reads theirs 1 vs
    # ours 1 -> KILL, and H stands clear of contact (squared
    # distance 9) with no hills remembered, so both bots refuse.
    # Base's explore then wanders north; Influence15 packs H up
    # south toward its pal P=(16,12) (6 away, unpacked, out of seek
    # range, exploring north identically in both bots). No pricing
    # is involved: the split is regroup-on-refusal alone.
    H = (10, 12)
    P = (16, 12)
    F = (10, 15)
    D = (10, 13)
    assert _manhattan(H, F) == 3
    assert _manhattan(H, P) == 6
    assert _manhattan(P, F) == 9
    live, foe = New.influence_fields([H, P], [F], ROWS, COLS, 3)
    assert New.rate_step(live, foe, D) == New.KILL
    assert New.has_pack(H, [H, P], _manhattan) is False
    base_orders, new_orders = run_both([H, P], [F])
    assert dict(base_orders) == {H: "n", P: "n"}
    assert dict(new_orders) == {H: "s", P: "n"}
    assert new_orders != base_orders


def test_remembered_hill_disables_regroup() -> None:
    # (q) Hill-gate: the (c) DIE board plus a remembered hill.
    # Base refuses the east DIE step and musters on the hill; the
    # gated regroup stands down (hill races keep every body), so
    # Influence15 runs the identical muster path -- byte-identical
    # orders, and H never steps south to regroup.
    H = (10, 12)
    P = (16, 12)
    F = (10, 15)
    F2 = (10, 16)
    live, foe = New.influence_fields([H, P], [F, F2], ROWS, COLS, 3)
    assert New.rate_step(live, foe, (10, 13)) == New.DIE
    base_orders, new_orders = run_both([H, P], [F, F2], enemy_hills=[(0, 0)])
    assert new_orders == base_orders
    assert dict(new_orders)[H] != "s"


def test_hill_sighting_closes_regroup_mid_game() -> None:
    # (s) Dynamic gate: same refused DIE board across two turns.
    # Turn 1 knows no hills, so H regroups south; turn 2 sights a
    # hill, the gate closes, and H musters instead -- never south.
    # Pins the transition, not just the static states.
    H = (10, 12)
    P = (16, 12)
    F = (10, 15)
    F2 = (10, 16)
    bot = New.Influence15()
    turn1 = FakeAnts([H, P], [F, F2])
    bot.do_turn(turn1)
    assert dict(turn1.orders)[H] == "s"
    assert (0, 0) not in bot.remembered_hills
    turn2 = FakeAnts([H, P], [F, F2], enemy_hills=[(0, 0)])
    bot.do_turn(turn2)
    assert (0, 0) in bot.remembered_hills
    assert dict(turn2.orders)[H] != "s"


def test_entry_is_self_contained() -> None:
    # (r) The entry carries its own combat core: stdlib plus
    # ants.py only, never the shared combat.py helpers.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Influence15.py")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    assert hasattr(New, "Influence15")
    assert hasattr(New, "influence_fields")
    assert hasattr(New, "move_own_stamp")
    assert hasattr(New, "classify_counts")
    assert hasattr(New, "project_final_field")
    assert hasattr(New, "has_pack")
    assert New.PACK_NEED == 3
    assert New.PACK_RADIUS == 10
    assert hasattr(New.Influence15(), "seen")
    bot_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "Influence15.bot"
    )
    with open(bot_path, encoding="utf-8") as handle:
        assert handle.read() == "python Influence15.py\n"
