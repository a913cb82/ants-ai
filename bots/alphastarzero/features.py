"""Observation encoding for the AlphaStarZero bot.

Owns the action space (ACTIONS + OFFSETS) and the two things the bot
sees: dest_of for movement, local_window for the 6-channel relative
state. No policy, no training.
"""

from __future__ import annotations

import torch
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ants import Ants

ACTIONS = ("n", "e", "s", "w", "stay")

OFFSETS = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1), "stay": (0, 0)}

# Third-dimension (channel) order of local_window: water, friendly ant,
# friendly hill, enemy ant, enemy hill, food.
CHANNELS = ("water", "own_ant", "own_hill", "enemy_ant", "enemy_hill", "food")

WATER_CHANNEL = 0
FOOD_CHANNEL = 5

# Default view radius in tiles: 9x9 window.
DEFAULT_RADIUS = 4


def dest_of(ants: Ants, loc: tuple[int, int], action: str) -> tuple[int, int]:
    if action == "stay":
        return loc
    return ants.destination(loc, action)


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
