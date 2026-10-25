"""AlphaStarZero v0: per-ant linear policy, stdlib only.

TDD seed: features + model must be importable without numpy/torch,
decide a legal move in microseconds, and never suggest water.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphastarzero"))


class FakeAnts:
    """Minimal stub of the Ants API used by features/model."""

    def __init__(self):
        self.rows = 10
        self.cols = 10
        self._water = {(2, 2)}
        self._food = [(5, 5)]
        self._mine = [(4, 4)]
        self._enemy = [((4, 6), 1)]
        self._my_hills = [(3, 3)]
        self._enemy_hills = [((6, 6), 1)]
        self.viewradius2 = 77

    def destination(self, loc, direction):
        d = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}[direction]
        return ((loc[0] + d[0]) % self.rows, (loc[1] + d[1]) % self.cols)

    def passable(self, loc):
        return loc not in self._water

    def distance(self, a, b):
        dr = min(abs(a[0] - b[0]), self.rows - abs(a[0] - b[0]))
        dc = min(abs(a[1] - b[1]), self.cols - abs(a[1] - b[1]))
        return dr + dc

    def food(self):
        return list(self._food)

    def my_ants(self):
        return list(self._mine)

    def enemy_ants(self):
        return list(self._enemy)

    def my_hills(self):
        return list(self._my_hills)

    def enemy_hills(self):
        return list(self._enemy_hills)


def test_features_cover_all_five_actions():
    import features

    ants = FakeAnts()
    feats = features.ant_features(ants, (4, 4))
    assert set(feats) == {"n", "e", "s", "w", "stay"}
    for a, vec in feats.items():
        assert set(vec) == {"passable", "food", "threat", "crowd"}
        assert all(isinstance(v, (int, float)) for v in vec.values())


def test_features_flag_water_as_impassable():
    import features

    ants = FakeAnts()
    ants._mine = [(2, 1)]  # east step lands on water (2,2)
    feats = features.ant_features(ants, (2, 1))
    assert feats["e"]["passable"] == 0
    assert feats["n"]["passable"] == 1


def test_model_picks_passable_food_step():
    import features
    import model

    ants = FakeAnts()
    weights = {"passable": 5.0, "food": 1.0, "threat": -2.0, "crowd": -1.0}
    feats = features.ant_features(ants, (4, 4))
    action = model.choose(feats, weights, occupied=set())
    # (4,4) -> food at (5,5): south or east both improve; must be passable.
    assert action in ("s", "e")
    dest = ants.destination((4, 4), action) if action != "stay" else (4, 4)
    assert ants.passable(dest)


def test_model_never_picks_water():
    import features
    import model

    ants = FakeAnts()
    ants._mine = [(2, 1)]
    ants._food = [(2, 5)]  # food lies east, past the water tile
    weights = {"passable": 5.0, "food": 1.0, "threat": -2.0, "crowd": -1.0}
    feats = features.ant_features(ants, (2, 1))
    action = model.choose(feats, weights, occupied=set())
    assert action != "e"


def test_weights_file_loads_and_matches_model_keys():
    import model

    wpath = ROOT / "bots" / "alphastarzero" / "weights.json"
    weights = json.loads(wpath.read_text())
    assert set(weights) == set(model.FEATURE_KEYS)


def test_window_shape_channels_dtype():
    import features

    ants = FakeAnts()
    w = features.local_window(ants, (4, 4), radius=2)
    assert list(w.shape) == [6, 5, 5]
    assert features.CHANNELS == (
        "water",
        "own_ant",
        "own_hill",
        "enemy_ant",
        "enemy_hill",
        "food",
    )
    assert set(w.flatten().tolist()) <= {0.0, 1.0}


def test_window_center_marks_self():
    import features

    ants = FakeAnts()
    w = features.local_window(ants, (4, 4), radius=2)
    r = 2
    assert w[features.CHANNELS.index("own_ant")][r][r] == 1.0
    assert w[features.CHANNELS.index("water")][r][r] == 0.0


def test_window_food_at_relative_offset():
    import features

    ants = FakeAnts()  # food at (5,5), ant at (4,4) -> offset (+1,+1)
    w = features.local_window(ants, (4, 4), radius=2)
    food = w[features.CHANNELS.index("food")]
    assert food[3][3] == 1.0
    assert food.sum() == 1.0


def test_window_wraps_toroidally():
    import features

    ants = FakeAnts()
    ants._mine = [(0, 0)]
    ants._food = [(9, 9)]  # offset (-1,-1) with wrap on a 10x10 map
    w = features.local_window(ants, (0, 0), radius=2)
    food = w[features.CHANNELS.index("food")]
    assert food[1][1] == 1.0
    assert food.sum() == 1.0


def test_window_water_masks_other_channels():
    import features

    ants = FakeAnts()  # water at (2,2); ant at (2,0) -> offset (0,+2)
    ants._mine = [(2, 0)]
    w = features.local_window(ants, (2, 0), radius=2)
    assert w[features.CHANNELS.index("water")][2][4] == 1.0
    for ch in ("own_ant", "enemy_ant", "food"):
        assert w[features.CHANNELS.index(ch)][2][4] == 0.0


def test_window_separates_ant_channels():
    import features

    ants = FakeAnts()  # enemy at (4,6); ant at (4,4) -> offset (0,+2)
    w = features.local_window(ants, (4, 4), radius=2)
    assert w[features.CHANNELS.index("enemy_ant")][2][4] == 1.0
    assert w[features.CHANNELS.index("own_ant")][2][4] == 0.0


def test_window_marks_both_hills():
    import features

    ants = FakeAnts()  # own hill (3,3) -> (-1,-1); enemy hill (6,6) -> (+2,+2)
    w = features.local_window(ants, (4, 4), radius=3)
    assert w[features.CHANNELS.index("own_hill")][2][2] == 1.0
    assert w[features.CHANNELS.index("enemy_hill")][5][5] == 1.0


def test_window_masks_cells_outside_los_circle():
    import features

    ants = FakeAnts()
    ants.viewradius2 = 8
    ants._mine = [(4, 4)]
    ants._food = [(7, 4), (6, 4)]  # offsets (+3,0) d2=9, (+2,0) d2=4
    w = features.local_window(ants, (4, 4), radius=3)
    food = w[features.CHANNELS.index("food")]
    assert food[6][3] == 0.0  # outside the sight circle: masked
    assert food[5][3] == 1.0  # inside: visible


def test_window_los_boundary_is_inclusive():
    import features

    ants = FakeAnts()
    ants.viewradius2 = 8
    ants._mine = [(4, 4)]
    ants._food = [(6, 6)]  # offset (+2,+2), d2=8 == viewradius2
    w = features.local_window(ants, (4, 4), radius=3)
    assert w[features.CHANNELS.index("food")][5][5] == 1.0


def test_window_masks_own_ants_outside_circle():
    import features

    ants = FakeAnts()
    ants.viewradius2 = 8
    ants._mine = [(4, 4), (7, 4)]  # second ant at offset (+3,0), d2=9
    w = features.local_window(ants, (4, 4), radius=3)
    own = w[features.CHANNELS.index("own_ant")]
    assert own[3][3] == 1.0  # self still marked
    assert own[6][3] == 0.0  # far own ant outside this ant's circle


def test_window_full_radius_inside_default_sight():
    import features

    ants = FakeAnts()  # viewradius2=77: radius-4 corner d2=32, all visible
    w = features.local_window(ants, (4, 4), radius=4)
    assert w.sum() > 0.0
    # water tile (2,2) is offset (-2,-2), d2=8 <= 77: still reported
    assert w[features.CHANNELS.index("water")][2][2] == 1.0
