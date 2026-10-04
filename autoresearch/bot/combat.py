#!/usr/bin/env python
"""Shared combat helpers for the combat program.

Leg 1 of 10 on the champion base. Pure top-level functions over
plain locations; entry bots import them and successors extend them
in place. Later legs layer coordinated combat here (Wolfpack
committed-join, Grinder 1v1, Screen interception); this leg only
advances idle ants on nearby enemies so approach forms fighting
lines, with second-rank gap-filling to follow.

Research: "Approach forms fighting lines" (xathis approaching
enemies) -- ants near enemies advance on them instead of walking
only to food, hills, or empty ground.
"""

from collections.abc import Callable

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]

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
