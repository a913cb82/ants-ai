"""Stage-2.4 strike-two: challenger role scales (KILL 2.0, HA 0.5).

TDD pin: scales only, no logic. Gating, base prices, and all other
roles byte-identical.
"""

import math
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


def test_challenger_scales_kill_2_ha_half():
    import rewards

    s = rewards.scales_for("challenger")
    assert s["KILL"] == 2.0
    assert s["HILL_APPROACH"] == 0.5


def test_other_roles_byte_identical():
    import rewards

    exp = rewards.scales_for("exploiter")
    assert exp["FOOD"] == 0.5 and exp["KILL"] == 3.0
    assert exp["DEATH"] == 3.0 and exp["HILL_APPROACH"] == 0.5
    assert exp["WIN"] == rewards.WIN and exp["LOSS"] == rewards.LOSS
    spo = rewards.scales_for("spoiler")
    assert spo["FOOD"] == 0 and spo["KILL"] == 3.0
    assert spo["DEATH"] == -2.0 and spo["HILL_APPROACH"] == 0
    # base prices untouched
    assert (rewards.KILL, rewards.DEATH, rewards.HILL_APPROACH) == (1.0, -2.0, 0.25)
    # challenger keeps base elsewhere
    chal = rewards.scales_for("challenger")
    assert chal["FOOD"] == 1.0 and chal["DEATH"] == -2.0
    assert chal["WIN"] == 5.0 and chal["LOSS"] == -5.0
    assert chal["HILL_RAZE"] == 10.0 and chal["HILL_LOST"] == -10.0
    # gating logic unchanged
    assert rewards.GATED_BY_ROLE["challenger"] == {"hill_approach", "kill"}
    assert rewards.GATED_BY_ROLE["exploiter"] == {"hill_approach"}
    assert rewards.GATED_BY_ROLE["spoiler"] == {"hill_approach"}


def test_won_trade_nets_zero_suicide_nets_minus_two():
    import rewards

    # Mutual kill in a WIN: +2 (kill) -2 (death) +5 terminal.
    # Dense combat nets 0: forgiveness, not subsidy.
    game = _game(score=[2, 0])
    game["replaydata"]["ants"] = [
        [5, 5, 1, 3, 1, "--"],  # enemy dies turn 3
        [5, 4, 1, 3, 0, "s-"],  # own ant dies turn 3
    ]
    records = [
        {"turn": 3, "loc": [5, 4], "dest": [6, 4], "action": "s"},
    ]
    s = rewards.scales_for("challenger")
    rets = rewards.compute_returns(game, 0, records, s, role="challenger")
    assert rets[0] == 2.0 + rewards.DEATH + rewards.WIN
    assert (2.0 + rewards.DEATH) == 0.0  # won-trade dense nets 0
    # Suicide (death, no kill) still nets -2 dense: no kamikaze.
    game2 = _game(score=[2, 0])
    game2["replaydata"]["ants"] = [[4, 4, 1, 2, 0, "s"]]
    rec2 = [{"turn": 2, "loc": [4, 4], "dest": [5, 4], "action": "s"}]
    r2 = rewards.compute_returns(game2, 0, rec2, s, role="challenger")
    assert r2[0] == rewards.DEATH + rewards.WIN
    assert r2[0] - rewards.WIN == -2.0


def test_challenger_gating_unchanged_rival_unchanged():
    import rewards

    # Challenger kill + HA still zero on draw/loss.
    game = _game(score=[0, 1])
    game["replaydata"]["ants"] = [[5, 5, 1, 3, 1, "--"]]
    records = [{"turn": 3, "loc": [5, 4], "dest": [5, 4], "action": "stay"}]
    s = rewards.scales_for("challenger")
    assert rewards.compute_returns(game, 0, records, s, "challenger") == [rewards.LOSS]
    game["score"] = [0, 0]
    assert rewards.compute_returns(game, 0, records, s, "challenger") == [0.0]
    # Rival unchanged: kills pay even in defeat, HA gated on loss.
    se = rewards.scales_for("exploiter")
    game["score"] = [0, 1]
    assert rewards.compute_returns(game, 0, records, se, "exploiter") == [3.0 + rewards.LOSS]
    # Challenger HA pays on wins at the rival's march price.
    game2 = _game(score=[1, 0])
    game2["replaydata"]["hills"] = [[9, 9, 1, 999]]
    rec2 = [{"turn": 1, "loc": [5, 5], "dest": [6, 6], "action": "s"}]
    closed = math.sqrt(32) - math.sqrt(18)
    got = rewards.compute_returns(game2, 0, rec2, s, "challenger")
    assert got == [rewards.WIN + 0.5 * closed]
