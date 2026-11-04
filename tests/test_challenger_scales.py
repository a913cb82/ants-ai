"""The one diet: base scales + outcome gating (no roles, no overrides)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))


def _game(**kw):
    base = {
        "score": [0, 0],
        "status": ["survived", "survived"],
        "length": 10,
        "replaydata": {
            "map": {"rows": 10, "cols": 10},
            "viewradius2": 77,
            "attackradius2": 5,
            "food": [],
            "ants": [],
            "hills": [],
        },
    }
    base.update(kw)
    return base


def test_scales_are_base():
    import rewards

    s = rewards.scales()
    assert s["KILL"] == 0.0
    assert s["HILL_APPROACH"] == 0.0
    assert s["FOOD"] == 0.0 and s["DEATH"] == 0.0
    assert s["WIN"] == 0.0 and s["LOSS"] == 0.0
    assert s["HILL_RAZE"] == 10.0 and s["HILL_LOST"] == -10.0
    assert (rewards.KILL, rewards.DEATH, rewards.HILL_APPROACH) == (0.0, 0.0, 0.0)
    assert {"hill_approach"} == rewards.GATED
