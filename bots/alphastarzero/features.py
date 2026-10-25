"""Per-ant action features for the AlphaStarZero bot (stdlib only).

One ant, five actions. Each action gets four scalar cues. The policy in
model.py is linear over these cues today; richer encoders (local CNN
windows) plug in here later without changing the caller.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ants import Ants

ACTIONS = ("n", "e", "s", "w", "stay")

# Threat radius in toroidal Manhattan distance. An enemy this close to the
# destination can force an unfavorable 1-for-1 trade.
THREAT_RADIUS = 2


def dest_of(ants: Ants, loc: tuple[int, int], action: str) -> tuple[int, int]:
    if action == "stay":
        return loc
    return ants.destination(loc, action)


def nearest_food(ants: Ants, loc: tuple[int, int]) -> tuple[int, int] | None:
    best = None
    best_d = None
    for food in ants.food():
        d = ants.distance(loc, food)
        if best_d is None or d < best_d:
            best, best_d = food, d
    return best


def ant_features(
    ants: Ants,
    loc: tuple[int, int],
    occupied: frozenset[tuple[int, int]] | set[tuple[int, int]] = frozenset(),
) -> dict[str, dict[str, float]]:
    """Score cues for each action from one ant's point of view.

    occupied: destinations already reserved by earlier ants this turn.
    The caller rebuilds features per ant with the live reservation set,
    so crowd==1 marks a collision before the order is issued.
    """
    reserved = set(occupied or ())
    target = nearest_food(ants, loc)
    base_d = ants.distance(loc, target) if target is not None else 0
    enemies = [pos for pos, _owner in ants.enemy_ants()]

    feats: dict[str, dict[str, float]] = {}
    for action in ACTIONS:
        dest = dest_of(ants, loc, action)
        if target is not None:
            step_d = ants.distance(dest, target)
            food = 1.0 if step_d < base_d else (-1.0 if step_d > base_d else 0.0)
        else:
            food = 0.0
        threat = (
            1.0
            if any(ants.distance(dest, e) <= THREAT_RADIUS for e in enemies)
            else 0.0
        )
        feats[action] = {
            "passable": 1.0 if ants.passable(dest) else 0.0,
            "food": food,
            "threat": threat,
            "crowd": 1.0 if (dest in reserved and dest != loc) else 0.0,
        }
    return feats
