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
