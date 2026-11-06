"""Toroidal grid math. Stdlib only; everyone imports from here."""

from __future__ import annotations

# NOTE: no ACTIONS/OFFSETS table here on purpose. The bot owns the
# action space (features.ACTIONS); the engine owns order names.
# AIM in tools/ants.py has no "-" or "stay": unknown orders fall back here.
VECTORS = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1), "-": (0, 0)}


def step(loc: tuple[int, int], order: str, rows: int, cols: int) -> tuple[int, int]:
    dr, dc = VECTORS.get(order, (0, 0))
    return ((loc[0] + dr) % rows, (loc[1] + dc) % cols)


def dist2(a: tuple[int, int], b: tuple[int, int], rows: int, cols: int) -> int:
    dr = min(abs(a[0] - b[0]), rows - abs(a[0] - b[0]))
    dc = min(abs(a[1] - b[1]), cols - abs(a[1] - b[1]))
    return dr * dr + dc * dc
