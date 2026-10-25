"""Per-ant action features for the AlphaStarZero bot (stdlib only).

One ant, five actions. Each action gets four scalar cues. The policy in
model.py is linear over these cues today; richer encoders (local CNN
windows) plug in here later without changing the caller.
"""

from __future__ import annotations

import torch
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ants import Ants

ACTIONS = ("n", "e", "s", "w", "stay")

# Third-dimension (channel) order of local_window: water, friendly ant,
# friendly hill, enemy ant, enemy hill, food.
CHANNELS = ("water", "own_ant", "own_hill", "enemy_ant", "enemy_hill", "food")

# Default view radius in tiles: 9x9 window, matches the ml/README v1 plan.
DEFAULT_RADIUS = 4

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


def local_window(
    ants: Ants, loc: tuple[int, int], radius: int = DEFAULT_RADIUS
) -> torch.Tensor:
    """Fully local, relative 1-hot state: (channels, height, width).

    The ant sits at the window center; cell (radius+dr, radius+dc) holds
    whatever is `dr, dc` tiles away with toroidal wrap. Channel order is
    CHANNELS. Water is authoritative: a water tile never carries an ant,
    hill, or food mark.

    Engine line of sight: only cells with dr*dr+dc*dc <= viewradius2
    (the ant's own sight circle, cf. tools/ants.py neighbourhood_offsets)
    are filled. Cells outside the circle stay all-zero, matching what the
    engine actually reveals to the bot. viewradius2 comes from the game
    settings and defaults to 77 when the wrapper does not provide it.
    """
    size = 2 * radius + 1
    window = torch.zeros((len(CHANNELS), size, size), dtype=torch.float32)
    r0, c0 = loc
    sight2 = getattr(ants, "viewradius2", 77)
    own_ants = set(ants.my_ants())
    own_hills = set(ants.my_hills())
    enemy_ants = {pos for pos, _owner in ants.enemy_ants()}
    enemy_hills = {pos for pos, _owner in ants.enemy_hills()}
    foods = set(ants.food())
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            if dr * dr + dc * dc > sight2:
                continue
            cell = ((r0 + dr) % ants.rows, (c0 + dc) % ants.cols)
            i, j = dr + radius, dc + radius
            if not ants.passable(cell):
                window[0, i, j] = 1.0
                continue
            if cell in own_ants:
                window[1, i, j] = 1.0
            if cell in own_hills:
                window[2, i, j] = 1.0
            if cell in enemy_ants:
                window[3, i, j] = 1.0
            if cell in enemy_hills:
                window[4, i, j] = 1.0
            if cell in foods:
                window[5, i, j] = 1.0
    return window
