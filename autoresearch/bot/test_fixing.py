#!/usr/bin/env python
"""anthonyvh greedy sequential fixing combat (53rd/7897).

Faithful port of the RESEARCH.md row "anthonyvh greedy fixing":
exact search rejected past 10-ant zones; Memetix-style influence
(enemies that could attack each tile after 1 move) plus greedy
sequential fixing, suicide only to unblock a hill rush. Eval fell
200 ms to 5-10 ms via local updates and a lazy bucketed queue;
stationary enemies pin first as fixed points of the field.

Self-contained: stdlib plus Fixing only. No combat.py import.

  (a) fixing_order pins most-constrained-first on a fixed 3v3.
  (b) pinned support re-evaluation flips the next ant's move vs
      the simultaneous (unpinned) choice.
  (c) stationary enemies pin before any of our ants.
  (d) suicide (a DIE order) issues iff its square unblocks this
      turn's hill rush -- both sides of the iff, pure and in-bot.
  (e) per-fight resolve stays under 10 ms, full crowded turn
      under 1 s.

Complexity (documented in Fixing.py): influence costs O(E*R^2)
diamond stamps (R = threat reach, ~3); each pin re-scores only
neighbors within R+1 steps and pops the lazy buckets in O(1)
amortized. No 5^A search, no full recompute per pin.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Fixing as FX  # noqa: E402

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
) -> tuple[list[tuple[Loc, str]], FX.Fixing]:
    fake = FakeAnts(mine, enemies, foods, water, enemy_hills, my_hills)
    bot = FX.Fixing()
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
    # bot-file names match the fresh Fixing entry.
    assert FX.__name__ == "Fixing"
    assert hasattr(FX, "Fixing")
    with open(str(FX.__file__)) as handle:
        source = handle.read()
    assert "import combat" not in source
    assert "from combat" not in source
    bot_file = os.path.join(os.path.dirname(str(FX.__file__)), "Fixing.bot")
    with open(bot_file) as handle:
        assert handle.read().strip() == "python Fixing.py"


def test_threat_reach_and_influence() -> None:
    # attackradius2 5 attacks at range 2, plus the enemy's step: 3.
    # One stamp covers the manhattan-3 diamond, axis 3 in, axis 4
    # and far diagonals out.
    assert FX.threat_reach(5) == 3
    field = FX.influence_field([(5, 5)], ROWS, COLS, 3)
    assert field[5][5] == 1
    assert field[5][8] == 1
    assert field[8][5] == 1
    assert field[5][9] == 0
    assert field[8][6] == 0
    assert FX.influence_field([], ROWS, COLS, 3)[5][5] == 0


def test_classify_step_die_kill_safe() -> None:
    # Ours is friends + 1 (the moving ant): 3 lurkers DIE a lone
    # step, KILL a backed pair, and lose to a packed triple.
    field = FX.influence_field([(5, 9), (2, 6), (8, 6)], ROWS, COLS, 3)
    assert FX.classify_step(field, (5, 6), 0) == FX.DIE
    assert FX.classify_step(field, (5, 6), 2) == FX.KILL
    assert FX.classify_step(field, (5, 6), 5) == FX.SAFE


def test_stationary_pins_match_unmoved_enemies() -> None:
    # (5, 8) sat still (distance-0 match to last turn); (5, 9) is a
    # new spawn (nothing within 1 step last turn), so only (5, 8)
    # pins as a fixed point of the field.
    assert FX.stationary_pins([(5, 8), (0, 0)], [(5, 8), (5, 9)], _dist) == [(5, 8)]
    assert FX.stationary_pins([], [(5, 8)], _dist) == []
    assert FX.stationary_pins([(5, 8)], [(5, 8)], _dist) == [(5, 8)]


# (a) 3v3 pinning order. Reach 3, no hills, so only SAFE squares
# are acceptable and the constraint score is the SAFE-step count:
# A0 (5, 5) vs (5, 8), (6, 7): n (4, 5) SAFE, e (5, 6) DIE(2),
# s (6, 5) KILL(1), w (5, 4) SAFE -> 2. A1 (10, 10) vs (10, 13):
# n/s/w SAFE, e (10, 11) KILL(1) -> 3. A2 (15, 15): everything
# SAFE -> 4. Most-constrained-first pins [0, 1, 2].
_ORDER_MINE = [(5, 5), (10, 10), (15, 15)]
_ORDER_FOES = [(5, 8), (6, 7), (10, 13)]


def test_sequential_pinning_order_most_constrained_first() -> None:
    field = FX.influence_field(_ORDER_FOES, ROWS, COLS, FX.threat_reach(5))
    support: dict[Loc, int] = {}
    counts = [
        len(
            FX.acceptable_moves(
                ant,
                field,
                support,
                [],
                _dist,
                _dest,
                _allow,
                _allow,
            )
        )
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
    assert [int(entry.split()[1]) for entry in fixes] == [0, 1, 2]
    assert set(plan) == {0, 1, 2}


def test_pinned_reevaluation_changes_next_move() -> None:
    # (b) A (6, 7) and B (7, 6) both score 3 acceptable steps, so
    # list order pins A first. A takes n onto (5, 7) (both n and w
    # sit 5 from the foe; n wins the direction tiebreak), landing
    # within sq 4 of B's pressing square (7, 7). Simultaneous B
    # (no pinned support) sees influence 1 = KILL and refuses the
    # advance, sidestepping n onto (6, 6). Re-evaluated with A's
    # pin, ours is 2 > 1 = SAFE, and B advances e onto (7, 7) --
    # the pin flips retreat into attack.
    mine = [(6, 7), (7, 6)]
    foes = [(7, 10)]
    field = FX.influence_field(foes, ROWS, COLS, FX.threat_reach(5))
    assert FX.classify_step(field, (7, 7), 0) == FX.KILL
    assert FX.classify_step(field, (7, 7), 1) == FX.SAFE
    alone = FX.best_move(
        mine[1],
        field,
        {},
        [],
        foes,
        _dist,
        _dest,
        _allow,
        _allow,
    )
    assert alone == "n"
    support: dict[Loc, int] = {}
    FX.add_support(support, (5, 7), ROWS, COLS, 5)
    backed = FX.best_move(
        mine[1],
        field,
        support,
        [],
        foes,
        _dist,
        _dest,
        _allow,
        _allow,
    )
    assert backed == "e"
    assert backed != alone
    trace: list[str] = []
    plan = FX.resolve_fight(
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
        _allow,
        trace,
    )
    assert plan == {0: "n", 1: "e"}
    assert trace.index("fix 0 n") < trace.index("fix 1 e")


def test_stationary_enemies_pinned_first() -> None:
    # (c) (5, 8) never moved, so the trace pins it before either of
    # our ants, and the stationary-first field equals the full
    # single-pass field stamp for stamp.
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
    reach = FX.threat_reach(5)
    assert FX.influence_field(foes, ROWS, COLS, reach) == FX.influence_field(
        stationary + [e for e in foes if e not in stationary], ROWS, COLS, reach
    )


def test_unblocks_hill_rush_iff() -> None:
    # (d, unit) east shortens the rush (5, 5)->(5, 10) from 5 to 4;
    # every other step holds or lengthens it.
    hills = [(5, 10)]
    assert FX.unblocks_hill_rush((5, 5), (5, 6), hills, _dist) is True
    assert FX.unblocks_hill_rush((5, 5), (5, 5), hills, _dist) is False
    assert FX.unblocks_hill_rush((5, 5), (5, 4), hills, _dist) is False
    assert FX.unblocks_hill_rush((5, 5), (4, 5), hills, _dist) is False
    assert FX.unblocks_hill_rush((5, 5), (6, 5), hills, _dist) is False
    assert FX.unblocks_hill_rush((5, 5), (5, 6), [], _dist) is False


def test_suicide_allowed_iff_it_unblocks_hill_rush() -> None:
    # (d, pure) every square around (5, 5) carries influence 2 =
    # DIE for a lone ant, so the only acceptable move is the one
    # that unblocks the rush -- and only while hills are contested.
    mine = [(5, 5)]
    foes = [(5, 7), (4, 4)]
    field = FX.influence_field(foes, ROWS, COLS, FX.threat_reach(5))
    for dest in [(5, 5), (5, 4), (5, 6), (4, 5), (6, 5)]:
        assert FX.classify_step(field, dest, 0) == FX.DIE
    assert (
        FX.best_move(
            mine[0],
            field,
            {},
            [(5, 10)],
            foes,
            _dist,
            _dest,
            _allow,
            _allow,
        )
        == "e"
    )
    assert (
        FX.best_move(
            mine[0],
            field,
            {},
            [],
            foes,
            _dist,
            _dest,
            _allow,
            _allow,
        )
        is None
    )
    assert FX.resolve_fight(
        mine,
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
    ) == {0: "e"}
    assert (
        FX.resolve_fight(
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
            _allow,
            None,
        )
        == {}
    )


def test_suicide_iff_in_bot() -> None:
    # (d, in-bot) pushing the remembered hill at (5, 10), the lone
    # ant sacrifices itself east; with no hill to rush it holds --
    # every explore square is unsafe, so no order issues at all.
    mine = [(5, 5)]
    foes = [(5, 7), (4, 4)]
    pushed, _ = run_turn(mine, foes, enemy_hills=[(5, 10)])
    assert pushed == [((5, 5), "e")]
    quiet, _ = run_turn(mine, foes)
    assert quiet == []


def test_food_and_first_guard_untouched_by_fixing() -> None:
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


def test_fight_under_10ms_and_turn_under_1s() -> None:
    # (e) a 24v24 pile-up resolves far inside the 10 ms fight
    # budget, and a full crowded turn (48 ants, food, hills,
    # guards) finishes far inside 1 s.
    ours = [(i % ROWS, (i * 7) % COLS) for i in range(24)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(24)]
    start = time.perf_counter()
    plan = FX.resolve_fight(
        ours,
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
    )
    assert (time.perf_counter() - start) < 0.010
    assert isinstance(plan, dict)
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
