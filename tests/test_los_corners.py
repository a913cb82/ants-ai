"""LOS F1: B-tier corner entities zero-filled unless a teammate sees them.

B-tier = window cells outside one ant's own sight circle (dr*dr+dc*dc >
viewradius2, e.g. the (7,7) corner at d2=98 > 77). Cells no ally sees
read 0=empty-unseen with ch6=0. Cells a teammate covers read filled
with ch6=1 (team vision): a corner ant sees itself, so it shows.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))

import features

_R = features.DEFAULT_RADIUS
_S = 2 * _R + 1


class FakeAnts:
    def __init__(
        self,
        rows=31,
        cols=31,
        own=(),
        enemy=(),
        own_hills=(),
        enemy_hills=(),
        food=(),
        viewradius2=77,
        attackradius2=5,
    ):
        self.rows = rows
        self.cols = cols
        self.viewradius2 = viewradius2
        self.attackradius2 = attackradius2
        self._own = list(own)
        self._enemy = list(enemy)
        self._own_hills = list(own_hills)
        self._enemy_hills = list(enemy_hills)
        self._food = list(food)

    def my_ants(self):
        return list(self._own)

    def enemy_ants(self):
        return [(pos, 1) for pos in self._enemy]

    def my_hills(self):
        return list(self._own_hills)

    def enemy_hills(self):
        return [(pos, 1) for pos in self._enemy_hills]

    def food(self):
        return list(self._food)

    def passable(self, cell):
        return True


def _window(ants, loc):
    view = features.snapshot(ants, water=set())
    return features.local_window(ants, loc, view=view)


def _corner_probe(enemy_at=None, own_at=None, food_at=None):
    # Focal ant at (15,15); B-tier corner (dr,dc)=(7,7) -> d2=98 > 77.
    foc = (15, 15)
    kw = dict(own=[foc])
    if enemy_at is not None:
        kw["enemy"] = [enemy_at]
    if own_at is not None:
        kw["own"] = [foc, own_at]
    if food_at is not None:
        kw["food"] = [food_at]
    ants = FakeAnts(**kw)
    return _window(ants, foc), ants, foc


def test_corner_enemy_reads_zero_on_ch3():
    corner = (15 + 7, 15 + 7)  # d2=98, B-tier
    w, _, _ = _corner_probe(enemy_at=corner)
    assert w[3, _R + 7, _R + 7].item() == 0.0


def test_corner_teammate_reads_one_through_team_sight():
    # Teammate standing on the corner sees itself (d2=0): team sight
    # covers the cell, so it fills with the mask set.
    corner = (15 + 7, 15 + 7)
    w, _, _ = _corner_probe(own_at=corner)
    assert w[1, _R + 7, _R + 7].item() == 1.0
    assert w[features.OWN_SIGHT_CHANNEL, _R + 7, _R + 7].item() == 1.0


def test_corner_food_reads_zero_on_ch5():
    corner = (15 - 7, 15 - 7)  # opposite corner, also d2=98
    w, _, _ = _corner_probe(food_at=corner)
    assert w[5, _R - 7, _R - 7].item() == 0.0


def test_in_circle_entities_still_fill():
    # (dr,dc)=(5,5) -> d2=50 <= 77: union intel preserved where it matters.
    w, _, _ = _corner_probe(enemy_at=(15 + 5, 15 + 5))
    assert w[3, _R + 5, _R + 5].item() == 1.0
    w2, _, _ = _corner_probe(own_at=(15 + 5, 15 + 5))
    assert w2[1, _R + 5, _R + 5].item() == 1.0
    w3, _, _ = _corner_probe(food_at=(15 + 5, 15 + 5))
    assert w3[5, _R + 5, _R + 5].item() == 1.0


def test_mask_intact_corner_0_center_1():
    corner = (15 + 7, 15 + 7)
    w, _, _ = _corner_probe(enemy_at=corner)
    assert w[features.OWN_SIGHT_CHANNEL, _R + 7, _R + 7].item() == 0.0
    assert w[features.OWN_SIGHT_CHANNEL, _R, _R].item() == 1.0
    # In-circle dest cells (N/E/S/W/stay of focal ant) still own-visible.
    for dr, dc in ((-1, 0), (0, 1), (1, 0), (0, -1), (0, 0)):
        assert w[features.OWN_SIGHT_CHANNEL, _R + dr, _R + dc].item() == 1.0


def _rot90_board(ants, foc):
    fr, fc = foc

    def rot(p):
        return ((fr - (p[1] - fc)) % ants.rows, (fc + (p[0] - fr)) % ants.cols)

    return FakeAnts(
        rows=ants.rows,
        cols=ants.cols,
        own=[rot(p) for p in ants._own],
        enemy=[rot(p) for p in ants._enemy],
        food=[rot(p) for p in ants._food],
        viewradius2=ants.viewradius2,
        attackradius2=ants.attackradius2,
    )


def test_gated_window_still_d4_equivariant():
    import torch

    foc = (15, 15)
    ants = FakeAnts(
        own=[foc, (15 + 5, 15 + 5)],
        enemy=[(15 + 7, 15 + 7), (15 + 3, 15 - 4)],
        food=[(15 - 7, 15 - 7), (15 + 2, 15 + 2)],
    )
    w1 = _window(ants, foc)
    ants2 = _rot90_board(ants, foc)
    w2 = _window(ants2, foc)
    torch.testing.assert_close(w2, torch.rot90(w1, 1, (1, 2)))
