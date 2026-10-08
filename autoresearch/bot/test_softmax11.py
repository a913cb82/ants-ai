#!/usr/bin/env python
"""Softmax11 ghost-memory deterministic pursuit combat tests.

Pins the three new mechanisms before the bot exists:
(a) ghost memory: last-seen foes persist GHOST_TTL turns and
    trigger hill guard while unseen, then expire;
(b) deterministic pursuit: each foe holds contact when already
    in attack range, else greedy-approaches its nearest own ant
    (no RNG anywhere in combat);
(c) directed retreat: ants in rejected (losing) fights step away
    from foes instead of mustering back in;
(d) full turn <1s crowded and identical inputs give identical
    orders (determinism, no random import use).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Softmax11 as SM  # noqa: E402

Loc = tuple[int, int]
ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
R2 = 5


class FakeAnts:
    """Minimal ants.Ants surface used by Softmax11.do_turn."""

    def __init__(
        self,
        mine: list[Loc],
        enemies: list[Loc],
        foods: list[Loc] | None = None,
        water: set[Loc] | None = None,
        enemy_hills: list[Loc] | None = None,
        my_hills: list[Loc] | None = None,
        time_left: int = 100000,
        rows: int = ROWS,
        cols: int = COLS,
    ) -> None:
        self.rows = rows
        self.cols = cols
        self.attackradius2 = R2
        self._mine = list(mine)
        self._enemies = list(enemies)
        self._foods = list(foods or [])
        self._water = set(water or set())
        self._enemy_hills = list(enemy_hills or [])
        self._my_hills = list(my_hills or [])
        self.orders: list[tuple[Loc, str]] = []
        self._time_left = time_left

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
        return self._time_left


def run_turn(
    bot: object,
    mine: list[Loc],
    enemies: list[Loc],
    foods: list[Loc] | None = None,
    water: set[Loc] | None = None,
    enemy_hills: list[Loc] | None = None,
    my_hills: list[Loc] | None = None,
    time_left: int = 100000,
    rows: int = ROWS,
    cols: int = COLS,
) -> FakeAnts:
    fake = FakeAnts(
        mine, enemies, foods, water, enemy_hills, my_hills, time_left, rows, cols
    )
    bot.do_turn(fake)  # type: ignore[attr-defined]
    return fake


def _dest(loc: Loc, direction: str) -> Loc:
    dr, dc = AIM[direction]
    return ((loc[0] + dr) % ROWS, (loc[1] + dc) % COLS)


def _passable(loc: Loc) -> bool:
    return True


def _dist(a: Loc, b: Loc) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, ROWS - dr)
    dc = abs(a[1] - b[1])
    dc = min(dc, COLS - dc)
    return dr + dc


# --- ghost memory ---


def test_ghost_ttl_constant() -> None:
    assert SM.GHOST_TTL == 3


def test_ghosts_remember_and_expire() -> None:
    ghosts = SM.remember_enemies({}, [(5, 5)], 1)
    assert ghosts == {(5, 5): 1}
    ghosts = SM.remember_enemies(ghosts, [], 2)
    assert (5, 5) in ghosts
    ghosts = SM.remember_enemies(ghosts, [], 1 + SM.GHOST_TTL)
    assert (5, 5) in ghosts
    ghosts = SM.remember_enemies(ghosts, [], 1 + SM.GHOST_TTL + 1)
    assert (5, 5) not in ghosts


def test_ghosts_refresh_on_resight() -> None:
    ghosts = SM.remember_enemies({}, [(5, 5)], 1)
    ghosts = SM.remember_enemies(ghosts, [(5, 5)], 1 + SM.GHOST_TTL)
    assert ghosts[(5, 5)] == 1 + SM.GHOST_TTL


def test_sensed_adds_unseen_ghosts_only() -> None:
    ghosts = {(5, 5): 1, (7, 7): 1}
    sensed = SM.sensed_enemies([(5, 5)], ghosts)
    assert sorted(sensed) == [(5, 5), (7, 7)]
    assert SM.sensed_enemies([], {}) == []


def test_ghost_triggers_hill_guard_while_unseen() -> None:
    # One foe leans on our hill, then vanishes into fog. The guard
    # must step back onto the hill on memory alone.
    bot = SM.Softmax11()
    hill = (10, 10)
    run_turn(bot, [(10, 11)], [(10, 12)], my_hills=[hill])
    assert (10, 12) in bot.ghosts
    fake = run_turn(bot, [(10, 11)], [], my_hills=[hill])
    assert fake.orders == [((10, 11), "w")]


def test_ghost_expiry_releases_guard() -> None:
    bot = SM.Softmax11()
    hill = (10, 10)
    run_turn(bot, [(10, 11)], [(10, 12)], my_hills=[hill])
    for _ in range(SM.GHOST_TTL + 2):
        fake = run_turn(bot, [(10, 11)], [], my_hills=[hill])
    # Ghost long gone: the ant explores outward, not back to hills.
    assert bot.ghosts == {}
    assert fake.orders == [((10, 11), "n")]


# --- deterministic pursuit ---


def test_pursuit_holds_contact_in_attack_range() -> None:
    # Foe adjacent to our ant holds (attackers stay to kill).
    joint = SM.pursuit_enemy_joint(
        [(5, 6)], [(5, 5)], R2, ROWS, COLS, _passable, _dest, _dist
    )
    assert joint == [[(5, 6)]]


def test_pursuit_approaches_nearest_own_ant() -> None:
    # Lone foe at (5,10) with ours at (5,5) and (5,15): nearest is
    # (5,15) at distance 5 vs 5... tie. Use asymmetric setup.
    joint = SM.pursuit_enemy_joint(
        [(5, 12)], [(5, 5), (5, 15)], R2, ROWS, COLS, _passable, _dest, _dist
    )
    # Nearest own is (5,15) at d=3; greedy step must close on it.
    assert _dist(joint[0][0], (5, 15)) < 3


def test_pursuit_deterministic_no_rng() -> None:
    foes = [(5, 12), (9, 9)]
    own = [(5, 5), (5, 15), (10, 10)]
    first = SM.pursuit_enemy_joint(foes, own, R2, ROWS, COLS, _passable, _dest, _dist)
    second = SM.pursuit_enemy_joint(foes, own, R2, ROWS, COLS, _passable, _dest, _dist)
    assert first == second
    assert len(first) == 1
    assert len(first[0]) == len(foes)


def test_no_randomness_in_combat_module() -> None:
    import inspect

    src = inspect.getsource(SM)
    assert "import random" not in src
    assert "random." not in src
    assert "Random" not in src


def test_deterministic_aggression_is_majority() -> None:
    assert SM.resolve_aggressive(2, 1) is True
    assert SM.resolve_aggressive(1, 1) is True
    assert SM.resolve_aggressive(1, 2) is False
    assert SM.resolve_aggressive(0, 3) is False
    assert SM.resolve_aggressive(3, 0) is True


def test_ahead_army_contests_one_down() -> None:
    # Global lead contests 1-down fights (dodge, not retreat)
    # but never two-down donations.
    assert SM.resolve_aggressive(1, 2, ahead=True) is True
    assert SM.resolve_aggressive(2, 3, ahead=True) is True
    assert SM.resolve_aggressive(1, 3, ahead=True) is False
    assert SM.resolve_aggressive(1, 2, ahead=False) is False
    assert SM.resolve_aggressive(1, 1, ahead=True) is True


# --- directed retreat ---


def test_retreat_steps_away_from_foe() -> None:
    # Ant at (5,5), foe at (5,6): retreat must not step toward it.
    dest = SM.retreat_dest((5, 5), [(5, 5)], [(5, 6)], R2, ROWS, COLS, _passable, _dist)
    assert _dist(dest, (5, 6)) >= _dist((5, 5), (5, 6))
    assert dest != (5, 6)


def test_retreat_prefers_safety_over_huddling() -> None:
    # Foe adjacent east; west escapes attack range: must go west.
    dest = SM.retreat_dest(
        (5, 5), [(5, 5), (5, 3)], [(5, 6)], R2, ROWS, COLS, _passable, _dist
    )
    assert dest == (5, 4)


def test_retreat_huddles_once_out_of_range() -> None:
    # Every square escapes, so the ant huddles toward its friend.
    dest = SM.retreat_dest(
        (5, 5), [(5, 5), (5, 1)], [(5, 10)], R2, ROWS, COLS, _passable, _dist
    )
    assert dest == (5, 4)


def test_ahead_one_down_holds_instead_of_retreating() -> None:
    # Same 1v2 charge, but the visible army leads 3v2: the fight
    # is contested, so the ant keeps pressing (musters on, since
    # no foe is in contact) instead of retreating west.
    bot = SM.Softmax11()
    foes = [(5, 9), (6, 9)]
    fake = run_turn(
        bot,
        [(5, 5), (0, 0), (0, 1)],
        foes,
        enemy_hills=[(15, 15)],
        my_hills=[(0, 0)],
    )
    assert any(loc == (5, 5) for loc, _ in fake.orders)
    assert ((5, 5), "w") not in fake.orders


def test_losing_fight_retreats_instead_of_mustering() -> None:
    # One ant charged by two approaching foes, with a far enemy hill
    # to muster to: dodging scores 0, every trade scores worse, and
    # the outnumbered ant is passive, so the fight is rejected and
    # the ant retreats west (5,4) instead of mustering south/east.
    bot = SM.Softmax11()
    foes = [(5, 9), (6, 9)]
    fake = run_turn(bot, [(5, 5)], foes, enemy_hills=[(15, 15)], my_hills=[(0, 0)])
    assert fake.orders == [((5, 5), "w")]


def test_focus_surround_kills_free() -> None:
    # Three around one: each of ours faces one foe (weakness 1)
    # while it faces three (weakness 3): it dies, we live.
    own_dead, enemy_dead = SM.resolve_exchange(
        [(5, 4), (5, 5), (6, 5)], [(5, 6)], R2, ROWS, COLS
    )
    assert (own_dead, enemy_dead) == (0, 1)


def test_focus_duel_is_mutual() -> None:
    # Adjacent 1v1: both weakness 1, both die.
    own_dead, enemy_dead = SM.resolve_exchange([(5, 5)], [(5, 6)], R2, ROWS, COLS)
    assert (own_dead, enemy_dead) == (1, 1)


def test_focus_outnumbered_dies_alone() -> None:
    # Lone ant between two: weakness 2 vs their 1; only it dies.
    own_dead, enemy_dead = SM.resolve_exchange(
        [(5, 5)], [(5, 6), (6, 6)], R2, ROWS, COLS
    )
    assert (own_dead, enemy_dead) == (1, 0)


def test_focus_no_contact_no_casualties() -> None:
    own_dead, enemy_dead = SM.resolve_exchange([(5, 5)], [(5, 12)], R2, ROWS, COLS)
    assert (own_dead, enemy_dead) == (0, 0)


def test_focus_split_fire_pins_focused_foe() -> None:
    # X between our pair dies focused; Y beside B alone survives
    # unfocused while B dies doubled. Focus, not symmetry.
    own_dead, enemy_dead = SM.resolve_exchange(
        [(5, 5), (5, 7)], [(5, 6), (5, 9)], R2, ROWS, COLS
    )
    assert (own_dead, enemy_dead) == (1, 1)


def test_argmax_surrounds_under_focus() -> None:
    # 3v1 clumped: holding already kills free (0 dead, 1 kill),
    # so the argmax must keep the surround, never scatter.
    reply = SM.pursuit_enemy_joint(
        [(5, 8)], [(5, 5), (5, 6), (5, 7)], R2, ROWS, COLS, _passable, _dest, _dist
    )[0]
    joint, score = SM.choose_own_joint(
        [(5, 5), (5, 6), (5, 7)],
        [(5, 8)],
        R2,
        ROWS,
        COLS,
        _passable,
        _dest,
        [reply],
    )
    assert score == 1.0
    assert joint == [(5, 5), (5, 6), (5, 7)]


def test_accepted_hold_holds_position() -> None:
    # 3v1 surround with nothing else to do: holding kills free,
    # so the ants must hold, not explore off the surround.
    bot = SM.Softmax11()
    fake = run_turn(bot, [(5, 4), (5, 5), (6, 5)], [(5, 6)])
    assert fake.orders == []


def test_carve_keeps_open_field_fight() -> None:
    fights = SM.carve_fights(
        [(5, 5)], [(5, 7)], _dist, SM.COMBAT_LINK, _passable, _dest, ROWS, COLS
    )
    assert fights == [([(5, 5)], [(5, 7)])]


def test_carve_splits_wall_separated_foes() -> None:
    # Full-height wall between the pair: manhattan 2, path 12+.
    # No meeting means no fight, so no phantom dodges.
    water = {(r, 6) for r in range(ROWS)}

    def p(loc: Loc) -> bool:
        return loc not in water

    fights = SM.carve_fights(
        [(5, 5)], [(5, 7)], _dist, SM.COMBAT_LINK, p, _dest, ROWS, COLS
    )
    assert fights == []


def test_carve_keeps_short_detour_fight() -> None:
    # Two blocked squares, path 6 around them: still one fight.
    water = {(5, 7), (5, 8)}

    def p(loc: Loc) -> bool:
        return loc not in water

    fights = SM.carve_fights(
        [(5, 5)], [(5, 9)], _dist, SM.COMBAT_LINK, p, _dest, ROWS, COLS
    )
    assert fights == [([(5, 5)], [(5, 9)])]


def test_carve_without_map_stays_manhattan() -> None:
    # No passable given: old pure-manhattan behavior, no crash.
    assert SM.carve_fights([(5, 5)], [(5, 7)], _dist) == [([(5, 5)], [(5, 7)])]


def test_winning_fight_still_advances() -> None:
    # 2v1 vs an approaching foe: the exposed ant dodges west to
    # safety (must issue); the anchor has nobody in contact, so it
    # falls through to explore instead of holding empty ground.
    bot = SM.Softmax11()
    fake = run_turn(bot, [(5, 5), (5, 9)], [(5, 12)], my_hills=[(0, 0)])
    assert fake.orders == [((5, 5), "n"), ((5, 9), "w")]


# --- determinism + perf ---


def test_identical_turns_identical_orders() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(20)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(12)]
    first = run_turn(
        SM.Softmax11(), mine, foes, [(3, 3)], enemy_hills=[(15, 15)]
    ).orders
    second = run_turn(
        SM.Softmax11(), mine, foes, [(3, 3)], enemy_hills=[(15, 15)]
    ).orders
    assert first == second


def test_per_fight_under_50ms() -> None:
    own = [(5, 5), (5, 6), (6, 5), (6, 6)]
    foes = [(5, 9), (5, 10), (6, 9), (4, 9)]
    start = time.perf_counter()
    joint = SM.pursuit_enemy_joint(foes, own, R2, ROWS, COLS, _passable, _dest, _dist)[
        0
    ]
    own_joint, score = SM.choose_own_joint(
        own, foes, R2, ROWS, COLS, _passable, _dest, [joint]
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 0.05
    assert len(own_joint) == len(own)
    assert isinstance(score, float)


def test_five_ant_fight_fast_and_profitable() -> None:
    # Five own ants solve quickly with a profitable joint.
    own = [(4, 5), (5, 4), (5, 5), (5, 6), (6, 5)]
    foes = [(5, 8), (5, 9)]
    start = time.perf_counter()
    reply = SM.pursuit_enemy_joint(foes, own, R2, ROWS, COLS, _passable, _dest, _dist)[
        0
    ]
    joint, score = SM.choose_own_joint(
        own, foes, R2, ROWS, COLS, _passable, _dest, [reply]
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 0.05
    assert len(joint) == len(own)
    assert score >= 1.0


def test_memory_chain_across_turns() -> None:
    # Five-turn chain: spot raider -> guard holds on memory after it
    # vanishes -> ghost expires -> ant leaves for food. Memory,
    # guard, and harvest integrate across turns.
    bot = SM.Softmax11()
    hill = (10, 10)
    run_turn(bot, [(10, 11)], [(10, 12)], my_hills=[hill])
    assert (10, 12) in bot.ghosts
    for _ in range(2):
        fake = run_turn(bot, [(10, 11)], [], my_hills=[hill])
        assert fake.orders == [((10, 11), "w")]
    for _ in range(SM.GHOST_TTL):
        fake = run_turn(bot, [(10, 11)], [], my_hills=[hill])
    assert bot.ghosts == {}
    assert fake.orders == [((10, 11), "n")]
    # Food now pulls the freed ant.
    fake = run_turn(bot, [(10, 11)], [], foods=[(10, 13)], my_hills=[hill])
    assert fake.orders == [((10, 11), "e")]


def test_razed_hill_clears_muster_memory() -> None:
    # March on a remembered hill; stepping onto it clears memory so
    # later turns explore instead of mustering at a dead hill.
    bot = SM.Softmax11()
    run_turn(bot, [(10, 10)], [], enemy_hills=[(12, 10)])
    assert (12, 10) in bot.remembered_hills
    run_turn(bot, [(12, 10)], [], enemy_hills=[])
    assert bot.remembered_hills == set()


def test_starved_turn_skips_combat_but_remembers() -> None:
    # Zero clock: no combat plans, no orders, no crash — but enemy
    # sightings still enter ghost memory for later turns.
    bot = SM.Softmax11()
    fake = run_turn(bot, [(5, 5)], [(5, 6)], time_left=0)
    assert fake.orders == []
    assert (5, 6) in bot.ghosts


def test_hold_persists_across_turns() -> None:
    # A winning surround holds still on turn two as well: no drift,
    # no explore, identical empty orders while the foe remains.
    bot = SM.Softmax11()
    first = run_turn(bot, [(5, 4), (5, 5), (6, 5)], [(5, 6)])
    second = run_turn(bot, [(5, 4), (5, 5), (6, 5)], [(5, 6)])
    assert first.orders == []
    assert second.orders == []


def test_deadline_breaks_greedy_early_with_valid_joint() -> None:
    # A huge fight with an expired budget returns the current joint
    # untouched: right length, distinct squares, no crash.
    own = [(4 + i, 5 + i) for i in range(10)]
    foes = [(10, 10), (10, 11)]
    reply = SM.pursuit_enemy_joint(foes, own, R2, ROWS, COLS, _passable, _dest, _dist)[
        0
    ]
    calls = [0]

    def deadline() -> bool:
        calls[0] += 1
        return False

    joint, _ = SM.choose_own_joint(
        own,
        foes,
        R2,
        ROWS,
        COLS,
        _passable,
        _dest,
        [reply],
        deadline=deadline,
    )
    assert len(joint) == len(own)
    assert len(set(joint)) == len(joint)
    assert calls[0] >= 1


def test_open_deadline_solves_fully() -> None:
    own = [(4, 5), (5, 4), (5, 5), (5, 6), (6, 5)]
    foes = [(5, 8), (5, 9)]
    reply = SM.pursuit_enemy_joint(foes, own, R2, ROWS, COLS, _passable, _dest, _dist)[
        0
    ]
    joint, score = SM.choose_own_joint(
        own,
        foes,
        R2,
        ROWS,
        COLS,
        _passable,
        _dest,
        [reply],
        deadline=lambda: True,
    )
    assert score >= 1.0
    assert len(joint) == len(own)


def test_many_ants_turn_stays_fast() -> None:
    # Late-game scale on a big map: 150 own, 80 foes, must finish
    # far inside the 1000 ms budget.
    big = 80
    mine = [(i % big, (i * 7) % big) for i in range(150)]
    foes = [((i * 13 + 5) % big, (i * 11 + 3) % big) for i in range(80)]
    water = {(r, c) for r in range(big) for c in range(big) if (r + c) % 9 == 0}
    water -= set(mine) | set(foes)
    start = time.perf_counter()
    fake = run_turn(
        SM.Softmax11(),
        mine,
        foes,
        [(3, 3)],
        water,
        enemy_hills=[(75, 75)],
        my_hills=[(40, 40)],
        rows=big,
        cols=big,
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(fake.orders) > 0


def test_full_turn_under_1s_crowded() -> None:
    mine = [(i % ROWS, (i * 7) % COLS) for i in range(48)]
    foes = [((i * 13 + 5) % ROWS, (i * 11 + 3) % COLS) for i in range(30)]
    foods = [(3, 3), (17, 17), (10, 2)]
    start = time.perf_counter()
    fake = run_turn(
        SM.Softmax11(),
        mine,
        foes,
        foods,
        enemy_hills=[(15, 15)],
        my_hills=[(10, 10)],
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(fake.orders) > 0
