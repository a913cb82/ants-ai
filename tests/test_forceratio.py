"""Force-ratio channels: the net sees fighting odds (fleet features#2).

Two scalar channels appended to the egocentric window in
bots/alphaant/features.py:
  force_ratio (ch7): enemies minus friends within attackradius2 of each
    cell (0 < d2 <= attack2, occupant excluded, raw float; positive =
    outnumbered, so the center cell > 0 iff the focal ant dies under
    the engine support rule).
  enemy_dist (ch8): toroidal distance from each cell to the nearest
    known enemy ant, normalized by the window diagonal
    (radius*sqrt(2)) and clipped to [0, 1]. No enemies known -> 1.0
    (window max: far == safe).
"""

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))

import features

_R = features.DEFAULT_RADIUS
_S = 2 * _R + 1
_MAXD = _R * math.sqrt(2)


class FakeAnts2:
    def __init__(
        self,
        rows=21,
        cols=21,
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


def _combat():
    # Focal ant at (10,10); 2 enemies (d2=1 each), 1 friend (d2=1).
    return FakeAnts2(
        own=[(10, 10), (10, 9)],
        enemy=[(10, 11), (11, 10)],
    )


def test_channel_names_and_count():
    assert features.CHANNELS[-3:-1] == ("force_ratio", "enemy_dist")
    assert features.CHANNELS[-1] == "stall"
    assert len(features.CHANNELS) == 10


def test_force_ratio_exact_on_synthetic_position():
    w = _window(_combat(), (10, 10))
    fr = w[features.CHANNELS.index("force_ratio")]
    c = _R  # window center
    # Center (10,10): enemies (10,11),(11,10) minus friend (10,9) = +1.
    assert fr[c, c].item() == 2 - 1
    # Cell of enemy (10,11): enemies within d2<=5 excl. self: (11,10) at
    # d2=2 -> 1; friends: (10,10) d2=1, (10,9) d2=4 -> 2. Value = -1.
    assert fr[c, c + 1].item() == 1 - 2
    # Cell of friend (10,9): enemies (10,11) d2=4, (11,10) d2=5 -> 2;
    # friends (10,10) d2=1 -> 1. Value = +1.
    assert fr[c, c - 1].item() == 2 - 1
    # Far corner: nobody within attackradius -> 0.
    assert fr[0, 0].item() == 0


def test_force_ratio_center_matches_engine_kill_rule():
    # Support rule: ant dies iff enemies > friends in range (self not
    # counted). Center > 0 must coincide with death.
    w = _window(_combat(), (10, 10))
    assert w[features.CHANNELS.index("force_ratio")][_R, _R].item() > 0
    safe = FakeAnts2(own=[(10, 10), (10, 9), (9, 10)], enemy=[(10, 11)])
    w2 = _window(safe, (10, 10))
    assert w2[features.CHANNELS.index("force_ratio")][_R, _R].item() <= 0


def test_enemy_distance_exact_on_synthetic_position():
    w = _window(_combat(), (10, 10))
    ed = w[features.CHANNELS.index("enemy_dist")]
    c = _R
    # Center: nearest enemy 1 tile away.
    assert abs(ed[c, c].item() - 1.0 / _MAXD) < 1e-6
    # Enemy-occupied cell: distance 0.
    assert ed[c, c + 1].item() == 0.0
    # Far corner saturates at the window max.
    assert ed[0, 0].item() == 1.0
    # Normalized range everywhere.
    assert bool(((ed >= 0) & (ed <= 1)).all())


def test_enemy_distance_no_enemies_is_window_max():
    ants = FakeAnts2(own=[(10, 10)])
    w = _window(ants, (10, 10))
    ed = w[features.CHANNELS.index("enemy_dist")]
    assert bool((ed == 1.0).all())
    fr = w[features.CHANNELS.index("force_ratio")]
    c = _R
    # Own cell: self excluded -> 0. Neighbor cell: own ant counts as a
    # friend in range -> -1.
    assert fr[c, c].item() == 0
    assert fr[c, c + 1].item() == -1


def test_old_channels_unchanged():
    w = _window(_combat(), (10, 10))
    c = _R
    assert w[features.CHANNELS.index("own_ant")][c, c].item() == 1.0
    assert w[features.CHANNELS.index("enemy_ant")][c, c + 1].item() == 1.0
    assert w[features.CHANNELS.index("own_sight")][c, c].item() == 1.0


def _rot90_board(ants, foc):
    # Rotate every entity 90deg about foc: (dr,dc) -> (-dc,dr).
    fr, fc = foc

    def rot(p):
        return ((fr - (p[1] - fc)) % ants.rows, (fc + (p[0] - fr)) % ants.cols)

    return FakeAnts2(
        rows=ants.rows,
        cols=ants.cols,
        own=[rot(p) for p in ants._own],
        enemy=[rot(p) for p in ants._enemy],
        viewradius2=ants.viewradius2,
        attackradius2=ants.attackradius2,
    )


def test_window_d4_equivariance_with_new_channels():
    import torch

    ants = _combat()
    w1 = _window(ants, (10, 10))
    ants2 = _rot90_board(ants, (10, 10))
    w2 = _window(ants2, (10, 10))
    torch.testing.assert_close(w2, torch.rot90(w1, 1, (1, 2)))


def test_logits_d4_equivariant_with_new_channels():
    # The D4-symmetrized net is equivariant, not invariant: a CCW
    # board rotation permutes the action logits (e->n, ...). East of
    # the ant becomes north, so new[n] == old[e], i.e. columns
    # [1,2,3,0,4]. Tight tolerance proves the scalar channels rotate
    # trivially through the symmetrization.
    import model
    import torch

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    policy.eval()
    w = _window(_combat(), (10, 10))
    with torch.no_grad():
        a = policy(w.unsqueeze(0))
        b = policy(torch.rot90(w.unsqueeze(0), 1, (2, 3)))
    torch.testing.assert_close(b, a[:, [1, 2, 3, 0, 4]], atol=1e-6, rtol=1e-5)


def test_old_7ch_weights_still_load():
    import model
    import torch

    torch.manual_seed(1)
    old = model.CNNPolicy(channels=7)
    raw = model.state_dict_to_lists(old)
    new = model.CNNPolicy()  # 9 channels now
    state = model.pad_in_channels(model.lists_to_state_dict(raw), new)
    new.load_state_dict(state, strict=True)
    new.eval()
    old.eval()
    w = _window(_combat(), (10, 10))
    with torch.no_grad():
        a = old(w[:, :7] if False else w[:7].unsqueeze(0))
        b = new(w.unsqueeze(0))
    assert torch.max(torch.abs(a - b)).item() < 1e-5


def test_ablation_new_channels_carry_signal():
    import model
    import torch

    torch.manual_seed(1)
    policy = model.CNNPolicy()
    with torch.no_grad():
        for key in ("conv1.weight", "vconv1.weight"):
            p = dict(policy.named_parameters())[key]
            p[:, 7:9] *= 20.0
    policy.eval()
    w = _window(_combat(), (10, 10))
    z = w.clone()
    z[7:9] = 0
    with torch.no_grad():
        full = policy(w.unsqueeze(0)).flatten()
        zeroed = policy(z.unsqueeze(0)).flatten()
    assert torch.max(torch.abs(full - zeroed)).item() > 1e-3
    assert int(torch.argmax(full)) != int(torch.argmax(zeroed))
