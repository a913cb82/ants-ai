"""Observation encoding for the AlphaAnt bot.

Owns the action space (ACTIONS + OFFSETS) and the two things the bot
sees: dest_of for movement, local_window for the 9-channel relative
state. No policy, no training.
"""

from __future__ import annotations

import base64
import math
from typing import TYPE_CHECKING

import numpy as _np
import torch

if TYPE_CHECKING:
    from ants import Ants

ACTIONS = ("n", "e", "s", "w", "stay")

OFFSETS = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1), "stay": (0, 0)}

# Third-dimension (channel) order of local_window: water, friendly ant,
# friendly hill, enemy ant, enemy hill, food, own-sight flag, local
# force-ratio, distance-to-nearest-enemy, stall-memory.
CHANNELS = (
    "water",
    "own_ant",
    "own_hill",
    "enemy_ant",
    "enemy_hill",
    "food",
    "own_sight",
    "force_ratio",
    "enemy_dist",
    "stall",
)

WATER_CHANNEL = 0
FOOD_CHANNEL = 5
OWN_SIGHT_CHANNEL = 6
FORCE_RATIO_CHANNEL = 7
ENEMY_DIST_CHANNEL = 8
STALL_CHANNEL = 9

# Same-cell/blocked hysteresis gain: ch9 = clip(streak / STALL_K, 0, 1).
# K=8 turns saturates: a week-long hold reads 1.0, a fresh ant 0.0.
STALL_K = 8


_sight_offsets: dict[tuple[int, int], list[tuple[int, int, int, int, bool]]] = {}


def _offsets_for(radius: int, sight2: int) -> list[tuple[int, int, int, int, bool]]:
    """(dr, dc, i, j, in_circle): the whole square, computed once.

    Cells inside the ant's own sight circle carry authoritative
    content; cells outside it (corners of a wide window) read
    0=empty-unseen on the entity channels, with the own_sight
    channel as the mask. The circle never changes mid-game, so the
    per-cell check in local_window becomes a cached iteration list.
    Entity channels (ch1-ch5) fill only inside the circle; cells
    outside it read 0=empty-unseen, with the own_sight channel as
    the mask."""
    key = (radius, sight2)
    if key not in _sight_offsets:
        _sight_offsets[key] = [
            (dr, dc, dr + radius, dc + radius, dr * dr + dc * dc <= sight2)
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
        "rows",
        "cols",
        "sight2",
        "attack2",
        "own_ants",
        "own_hills",
        "enemy_ants",
        "enemy_hills",
        "foods",
        "water",
    )

    def __init__(self, ants, water=None):
        self.rows = ants.rows
        self.cols = ants.cols
        self.sight2 = getattr(ants, "viewradius2", 77)
        self.attack2 = getattr(ants, "attackradius2", 5) or 5
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
# outside the sight circle (77), so they read 0=empty-unseen on the
# entity channels, with the own_sight channel as the mask.
DEFAULT_RADIUS = 7


_attack_offsets: dict[int, list[tuple[int, int]]] = {}


def _offsets_in(attack2: int) -> list[tuple[int, int]]:
    """(dr, dc) with 0 < dr*dr+dc*dc <= attack2: the engine kill range.

    nearby_ants excludes the center cell (0 < dist), and the support
    rule does not count the ant itself — so neither do we. Cached per
    attack2; attackradius2=5 gives the 20-cell ring."""
    if attack2 not in _attack_offsets:
        _attack_offsets[attack2] = [
            (dr, dc)
            for dr in range(-attack2, attack2 + 1)
            for dc in range(-attack2, attack2 + 1)
            if 0 < dr * dr + dc * dc <= attack2
        ]
    return _attack_offsets[attack2]


def _tdelta(a: int, b: int, n: int) -> int:
    """Signed toroidal delta a-b in [-n/2, n/2]."""
    d = (a - b) % n
    if 2 * d > n:
        d -= n
    return d


def dest_of(ants: Ants, loc: tuple[int, int], action: str) -> tuple[int, int]:
    if action == "stay":
        return loc
    return ants.destination(loc, action)


def local_window(
    ants: Ants,
    loc: tuple[int, int],
    radius: int = DEFAULT_RADIUS,
    view: View | None = None,
    stall: float = 0.0,
) -> torch.Tensor:
    """Fully local, relative 1-hot state: (channels, height, width).

    The ant sits at the window center; cell (radius+dr, radius+dc) holds
    whatever is `dr, dc` tiles away with toroidal wrap. Channel order is
    CHANNELS. Water is authoritative: a water tile never carries an ant,
    hill, or food mark.

    Two vision tiers: cells inside the ant's own sight circle
    (dr*dr+dc*dc <= viewradius2) are filled authoritatively, including
    water. Cells outside the circle but inside the window read
    0=empty-unseen on the entity channels (ch1-ch5); the own_sight
    channel (1/0) marks the tiers. viewradius2 comes from
    the game settings and defaults to 77 when the wrapper does not
    provide it.

    Channels 7-8 are scalar combat fields, filled for every cell
    including water (they describe the neighborhood, not the tile):
    force_ratio is enemies minus friends with 0 < d2 <= attackradius2
    of the cell (occupant excluded, raw float, positive =
    outnumbered — the center cell is > 0 exactly when the focal ant
    dies under the engine support rule); enemy_dist is the toroidal
    distance to the nearest known enemy ant, divided by the window
    diagonal (radius*sqrt(2)) and clipped to [0, 1], so 0 =
    enemy-here and 1 = nothing near. No enemies known at all fills
    1.0 (window max: far == safe). Both derive from the same union-
    vision sets as the 1-hot channels, and both are scalars, so a
    rotated position yields the rotated window (see
    tests/test_forceratio.py).

    Channel 9 (stall) is the ant's own same-cell/blocked hysteresis:
    clip(streak / STALL_K, 0, 1) broadcast constant over every cell,
    including water and out-of-sight corners. Constant-by-construction
    so a rotated window is the rotated constants (D4-safe trivially);
    the caller (AlphaAnt.py) owns the streak memory, this function
    only stamps it. Defaults to 0.0 (fresh ant), so replayed rows
    from pre-stall checkpoints read as zero-streak.
    """
    size = 2 * radius + 1
    grid = _np.zeros((len(CHANNELS), size, size), dtype=_np.float32)
    grid[STALL_CHANNEL, :, :] = stall
    r0, c0 = loc
    if view is None:
        view = View(ants)
    rows, cols = view.rows, view.cols
    own_ants, own_hills = view.own_ants, view.own_hills
    enemy_ants = view.enemy_ants
    enemy_hills, foods = view.enemy_hills, view.foods
    water = view.water
    # getattr: ml/bc.py rebuilds pre-force-ratio view-likes (a plain
    # namespace) to replay archived windows; they carry no attack2.
    attack2 = getattr(view, "attack2", 5) or 5
    reach = set(_offsets_in(attack2))
    max_d = radius * math.sqrt(2)
    # Candidates near the window: exact, not approximate. An ant
    # outside the force box cannot be within attack2 of any window
    # cell; an enemy outside the dist box is past the clip, so min()
    # never misses it unless no enemy is inside (all-ones fill).
    fr_each = int(math.ceil(math.sqrt(attack2)))
    fr_box = radius + fr_each
    ed_box = radius + int(math.ceil(max_d))
    friends = [
        p
        for p in own_ants
        if abs(_tdelta(p[0], r0, rows)) <= fr_box
        and abs(_tdelta(p[1], c0, cols)) <= fr_box
    ]
    foes = [
        p
        for p in enemy_ants
        if abs(_tdelta(p[0], r0, rows)) <= fr_box
        and abs(_tdelta(p[1], c0, cols)) <= fr_box
    ]
    near = [
        p
        for p in enemy_ants
        if abs(_tdelta(p[0], r0, rows)) <= ed_box
        and abs(_tdelta(p[1], c0, cols)) <= ed_box
    ]
    for dr, dc, i, j, in_circle in _offsets_for(radius, view.sight2):
        if in_circle:
            grid[OWN_SIGHT_CHANNEL, i, j] = 1.0
        cell = ((r0 + dr) % rows, (c0 + dc) % cols)
        foes_n = sum(
            1
            for q in foes
            if (_tdelta(q[0], cell[0], rows), _tdelta(q[1], cell[1], cols)) in reach
        )
        friends_n = sum(
            1
            for q in friends
            if (_tdelta(q[0], cell[0], rows), _tdelta(q[1], cell[1], cols)) in reach
        )
        grid[FORCE_RATIO_CHANNEL, i, j] = foes_n - friends_n
        if near:
            best = min(
                _tdelta(q[0], cell[0], rows) ** 2 + _tdelta(q[1], cell[1], cols) ** 2
                for q in near
            )
            grid[ENEMY_DIST_CHANNEL, i, j] = min(1.0, math.sqrt(best) / max_d)
        else:
            grid[ENEMY_DIST_CHANNEL, i, j] = 1.0
        if in_circle and (
            (cell in water) if water is not None else (not ants.passable(cell))
        ):
            grid[0, i, j] = 1.0
            continue
        if cell in own_ants and in_circle:
            grid[1, i, j] = 1.0
        if cell in own_hills and in_circle:
            grid[2, i, j] = 1.0
        if cell in enemy_ants and in_circle:
            grid[3, i, j] = 1.0
        if cell in enemy_hills and in_circle:
            grid[4, i, j] = 1.0
        if cell in foods and in_circle:
            grid[5, i, j] = 1.0
    return torch.from_numpy(grid)


def encode_window(window) -> dict:
    """Dense window blob for training records: base64 float32 + shape.

    Records arrive as JSON; nested float lists cost ~60KB/row as Python
    objects (2250 floats x 28B) and pile GBs in RAM under concurrency
    (OOM-killed a 14-game run at 11GB). The blob is one ~12KB string
    that decodes straight to a tensor with no intermediate lists.
    Native byte order: both ends run on this machine."""
    w = window.to(torch.float32)
    raw = w.numpy().tobytes()
    return {"b64": base64.b64encode(raw).decode("ascii"), "shape": list(w.shape)}


def decode_window(blob: dict):
    """Base64 blob from encode_window back to a float32 tensor."""
    import base64 as _b64

    raw = _b64.b64decode(blob["b64"])
    arr = _np.frombuffer(raw, dtype=_np.float32).reshape(blob["shape"])
    return torch.from_numpy(arr)
