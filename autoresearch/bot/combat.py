#!/usr/bin/env python
"""Shared combat helpers for the combat program.

Leg 1 of 10 on the champion base. Pure top-level functions over
plain locations; entry bots import them and successors extend them
in place. Later legs layer coordinated combat here (Wolfpack
committed-join, Grinder 1v1, Screen interception); this leg only
advances idle ants on nearby enemies so approach forms fighting
lines, with second-rank gap-filling to follow.

Leg 2 adds the Wolfpack join: contact_foe maps a planned step to
the foe it would fight, and joined_attackers releases every ant
whose foe draws 2+ commitments this turn.

Leg 3 adds the Grinder gate: grinder_release permits a friendless
1v1 contact step only when the visible army strictly outnumbers
theirs, so ahead lone ants engage while behind or even ones hold
as champion.

Leg 4 adds the Screen intercept: intercept_square screens a razer
by returning the passable square halfway between a threatened
home hill and its nearest enemy, so extra guards meet the razer
off the hill and the hill stays spawnable.

Leg 5 adds the Odds gate: EQUAL_TRADE_NEAR drops the equal-trade
near-friend requirement from champion's tuned 14 to 10, so
crowded-board equal trades engage sooner. Entry bots read the
constant in their safety filter; strict superiority, Grinder, and
join are untouched.

Leg 6 adds the Gang gate: has_pack reports whether an ant holds
PACK_NEED+ friends within PACK_RADIUS steps, and a packless ant
packs up toward its nearest friend instead of advancing, so
fearless solo hunters stop donating into crowds.

Leg 7 adds the Crowd gate: crowd_fearless reports whether fewer
than CROWD_LIMIT enemies are visible, so packed hunters skip the
safety filter on advancing moves in small fights and keep full
champion safety in crowds.

Leg 8 adds the Legion gate: legion_ready reports whether 10+
own ants (LEGION_MIN) are visible, so the crowd-fearless advance
issues only with a real army; smaller armies keep full champion
safety on every advance regardless of enemy count. Fearless
babies donate in duels; press only with numbers.

Research: "Approach forms fighting lines" (xathis approaching
enemies) -- ants near enemies advance on them instead of walking
only to food, hills, or empty ground.
"""

from collections import deque
from collections.abc import Callable

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]
SqDistFn = Callable[[Loc, Loc], int]
PassFn = Callable[[Loc], bool]

SEEK_RANGE = 8

# Leg 5 (Odds): equal trades (friends + 1 == enemies) need this
# many near friends (within 10 steps of the step) for the safety
# filter to accept them. Champion tuned 14 on its scale; Odds
# tests 10 on ours.
EQUAL_TRADE_NEAR = 10

# Leg 6 (Gang): hunt only with a pack -- an ant advances on a
# nearby enemy only with PACK_NEED+ friends within PACK_RADIUS
# steps, else it packs up toward its nearest friend. Fearless
# solo hunters donate into crowds.
PACK_NEED = 3
PACK_RADIUS = 10

# Leg 7 (Crowd): fearless under ten enemies -- hunters press
# small fights and survive big ones. Fewer than CROWD_LIMIT
# visible enemies skips the safety filter on advancing moves;
# CROWD_LIMIT+ visible enemies keeps full champion safety.
# Donations happen in crowds, not duels.
CROWD_LIMIT = 10

# Leg 8 (Legion): press needs ten ants -- early growth is
# spawns, not winning; fearless babies donate in duels. The
# crowd-fearless advance issues only with LEGION_MIN+ own ants
# visible; smaller armies keep full champion safety on every
# advance regardless of enemy count.
LEGION_MIN = 10


def legion_ready(my_army: int, limit: int = LEGION_MIN) -> bool:
    """Whether the visible army is big enough to press fearlessly.

    True when my_army reaches limit, so a packed advance in a
    small fight skips the safety filter; smaller armies hold full
    champion safety on every advance. Pure: integer compare, no
    side effects.
    """
    return my_army >= limit


def crowd_fearless(enemy_count: int, limit: int = CROWD_LIMIT) -> bool:
    """Whether hunters advance fearlessly at this visible count.

    True when fewer than limit enemies are visible, so the seek
    branch skips the safety filter on the advancing move; False
    in crowds, where full champion safety applies. Pure: integer
    compare, no side effects.
    """
    return enemy_count < limit


def has_pack(
    ant_loc: Loc,
    ants_list: list[Loc],
    distance: DistFn,
    need: int = PACK_NEED,
    radius: int = PACK_RADIUS,
) -> bool:
    """Whether an ant holds a pack: need+ friends within radius steps.

    The ant itself never counts toward its own pack. Pure: no board
    state, no side effects.
    """
    found = 0
    for friend in ants_list:
        if friend == ant_loc:
            continue
        if distance(ant_loc, friend) <= radius:
            found += 1
            if found >= need:
                return True
    return False


def nearest_seek_enemy(
    ant_loc: Loc, enemy_locs: list[Loc], distance: DistFn
) -> Loc | None:
    """Nearest visible enemy within SEEK_RANGE steps, else None.

    Ties keep the first enemy in list order so the branch is
    deterministic. Pure: no board state, no side effects.
    """
    best: Loc | None = None
    best_d = SEEK_RANGE + 1
    for foe in enemy_locs:
        d = distance(ant_loc, foe)
        if d <= SEEK_RANGE and d < best_d:
            best_d = d
            best = foe
    return best


def contact_foe(
    dest: Loc, enemy_locs: list[Loc], sq_dist: SqDistFn, attack_r2: int
) -> Loc | None:
    """Nearest enemy within attack range of a planned step, else None.

    A seek step landing here would fight that foe next battle phase,
    so the move queues as a pack commitment on it. Ties keep the
    first enemy in list order so the branch is deterministic. Pure:
    no board state, no side effects.
    """
    best: Loc | None = None
    best_d = attack_r2 + 1
    for foe in enemy_locs:
        d = sq_dist(dest, foe)
        if d <= attack_r2 and d < best_d:
            best_d = d
            best = foe
    return best


def joined_attackers(commitments: dict[int, Loc]) -> set[int]:
    """Ant indices released to attack: foes with 2+ committers.

    Each commitment maps one ant index to the foe its planned step
    would contact. A foe drawing two or more commitments releases
    every committer, so the pair engages together; lone committers
    stay out and fall back to champion safety. Pure: no board
    state, no side effects.
    """
    counts: dict[Loc, int] = {}
    for foe in commitments.values():
        counts[foe] = counts.get(foe, 0) + 1
    return {ai for ai, foe in commitments.items() if counts[foe] >= 2}


def grinder_release(friends: int, enemies: int, my_army: int, enemy_army: int) -> bool:
    """Grinder 1v1 gate: engage a friendless duel only when ahead.

    A planned step with no friend in attack range facing exactly one
    foe is mutual death under focus battle, so champion refuses it.
    Grinder permits it when the visible army strictly outnumbers
    theirs (my_army > enemy_army); every other shape -- backed,
    crowded, contact-free, behind, or even -- refuses exactly as
    champion does today. Pure: integer compare, no side effects.
    """
    return friends == 0 and enemies == 1 and my_army > enemy_army


def intercept_square(
    hill: Loc,
    enemy_locs: list[Loc],
    distance: DistFn,
    passable: PassFn,
    rows: int,
    cols: int,
) -> Loc | None:
    """Off-hill intercept for one threatened home hill.

    Screens the razer instead of piling onto the hill: take the
    nearest enemy to the hill, halve the toroidal approach, and
    return the nearest passable square to that midpoint (the
    midpoint itself when open). Ties keep the first enemy in list
    order so the branch is deterministic. No enemies -- or no
    passable square on the whole board -- returns None so the
    caller holds the champion fallback. Pure: no board state, no
    side effects.
    """
    if not enemy_locs or rows <= 0 or cols <= 0:
        return None
    foe = min(enemy_locs, key=lambda e: distance(hill, e))
    dr = foe[0] - hill[0]
    if dr > rows // 2:
        dr -= rows
    elif dr < -(rows // 2):
        dr += rows
    dc = foe[1] - hill[1]
    if dc > cols // 2:
        dc -= cols
    elif dc < -(cols // 2):
        dc += cols
    mid = ((hill[0] + int(dr / 2)) % rows, (hill[1] + int(dc / 2)) % cols)
    if passable(mid):
        return mid
    seen = {mid}
    queue: deque[Loc] = deque([mid])
    while queue:
        cur = queue.popleft()
        for step in ((-1, 0), (0, 1), (1, 0), (0, -1)):
            nxt = ((cur[0] + step[0]) % rows, (cur[1] + step[1]) % cols)
            if nxt in seen:
                continue
            seen.add(nxt)
            if passable(nxt):
                return nxt
            queue.append(nxt)
    return None
