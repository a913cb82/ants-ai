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

Research: "Approach forms fighting lines" (xathis approaching
enemies) -- ants near enemies advance on them instead of walking
only to food, hills, or empty ground.
"""

from collections.abc import Callable

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]
SqDistFn = Callable[[Loc, Loc], int]

SEEK_RANGE = 8


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
