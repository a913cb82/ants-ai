"""Observation encoding for the AlphaAnt bot.

Owns the action space (ACTIONS + OFFSETS) and the two things the bot
sees: dest_of for movement, local_window for the 6-channel relative
state. No policy, no training.
"""

from __future__ import annotations

import numpy as _np
import torch
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ants import Ants

ACTIONS = ("n", "e", "s", "w", "stay")

OFFSETS = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1), "stay": (0, 0)}

# Third-dimension (channel) order of local_window: water, friendly ant,
# friendly hill, enemy ant, enemy hill, food, own-sight flag.
CHANNELS = ("water", "own_ant", "own_hill", "enemy_ant", "enemy_hill",
            "food", "own_sight")

WATER_CHANNEL = 0
FOOD_CHANNEL = 5
OWN_SIGHT_CHANNEL = 6


_sight_offsets: dict[tuple[int, int], list[tuple[int, int, int, int, bool]]] = {}


def _offsets_for(radius: int, sight2: int) -> list[tuple[int, int, int, int, bool]]:
    """(dr, dc, i, j, in_circle): the whole square, computed once.

    Cells inside the ant's own sight circle carry authoritative
    content; cells outside it (corners of a wide window) carry
    union-vision content — what teammates see — flagged by the
    own_sight channel. The circle never changes mid-game, so the
    per-cell check in local_window becomes a cached iteration list."""
    key = (radius, sight2)
    if key not in _sight_offsets:
        _sight_offsets[key] = [
            (dr, dc, dr + radius, dc + radius,
             dr * dr + dc * dc <= sight2)
            for dr in range(-radius, radius + 1)
            for dc in range(-radius, radius + 1)
        ]
    return _sight_offsets[key]


class View:
    """One turn's board state, read once instead of once per ant.

    local_window used to rebuild these five sets (plus a passable()
    call per cell) for every ant; on a 150-ant turn that is hundreds
    of full-board scans. snapshot() reads them once; pass the View
    as local_window's view= to reuse it. water is None unless the
    caller hands in a cached impassable set (water never changes
    mid-game, so the bot builds it once in do_setup)."""

    __slots__ = (
        "rows", "cols", "sight2", "own_ants", "own_hills",
        "enemy_ants", "enemy_hills", "foods", "water",
    )

    def __init__(self, ants, water=None):
        self.rows = ants.rows
        self.cols = ants.cols
        self.sight2 = getattr(ants, "viewradius2", 77)
        self.own_ants = set(ants.my_ants())
        self.own_hills = set(ants.my_hills())
        self.enemy_ants = {pos for pos, _owner in ants.enemy_ants()}
        self.enemy_hills = {pos for pos, _owner in ants.enemy_hills()}
        self.foods = set(ants.food())
        self.water = water


def snapshot(ants, water=None) -> View:
    """Read the whole board once; see View."""
    return View(ants, water)

# Default view radius in tiles: 15x15 window. Corners (d2=98) sit
# outside the sight circle (77), so they carry union-vision content —
# what teammates see — flagged by the own_sight channel.
DEFAULT_RADIUS = 7


def dest_of(ants: Ants, loc: tuple[int, int], action: str) -> tuple[int, int]:
    if action == "stay":
        return loc
    return ants.destination(loc, action)


def local_window(
    ants: Ants, loc: tuple[int, int], radius: int = DEFAULT_RADIUS,
    view: View | None = None,
) -> torch.Tensor:
    """Fully local, relative 1-hot state: (channels, height, width).

    The ant sits at the window center; cell (radius+dr, radius+dc) holds
    whatever is `dr, dc` tiles away with toroidal wrap. Channel order is
    CHANNELS. Water is authoritative: a water tile never carries an ant,
    hill, or food mark.

    Two vision tiers: cells inside the ant's own sight circle
    (dr*dr+dc*dc <= viewradius2) are filled authoritatively, including
    water. Cells outside the circle but inside the window carry
    union-vision content — entities visible to any teammate — with
    water left unknown (0); the own_sight channel (1/0) tells the
    tiers apart. Far-side friendlies and distant hills are visible;
    whether they are actionable now is marked. viewradius2 comes from
    the game settings and defaults to 77 when the wrapper does not
    provide it.
    """
    size = 2 * radius + 1
    grid = _np.zeros((len(CHANNELS), size, size), dtype=_np.float32)
    r0, c0 = loc
    if view is None:
        view = View(ants)
    rows, cols = view.rows, view.cols
    own_ants, own_hills = view.own_ants, view.own_hills
    enemy_ants = view.enemy_ants
    enemy_hills, foods = view.enemy_hills, view.foods
    water = view.water
    for dr, dc, i, j, in_circle in _offsets_for(radius, view.sight2):
        if in_circle:
            grid[OWN_SIGHT_CHANNEL, i, j] = 1.0
        cell = ((r0 + dr) % rows, (c0 + dc) % cols)
        if in_circle and ((cell in water) if water is not None
                           else (not ants.passable(cell))):
            grid[0, i, j] = 1.0
            continue
        if cell in own_ants:
            grid[1, i, j] = 1.0
        if cell in own_hills:
            grid[2, i, j] = 1.0
        if cell in enemy_ants:
            grid[3, i, j] = 1.0
        if cell in enemy_hills:
            grid[4, i, j] = 1.0
        if cell in foods:
            grid[5, i, j] = 1.0
    return torch.from_numpy(grid)
