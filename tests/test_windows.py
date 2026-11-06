"""Observation windows: shape, channels, LoS masking, team sight, b64 blobs.

Split from the test_alphastarzero monolith; no behavior change.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "ml"))

import pytest

import features

_C = features.INPUT_CHANNELS
_S = 2 * features.DEFAULT_RADIUS + 1


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




def _trace_game():
    import rewards  # noqa: F401  (keeps the one-diet import idiom)

    game = _game()
    rows = [".........." for _ in range(10)]
    rows[5] = "......%..."
    game["replaydata"]["map"] = {"rows": 10, "cols": 10, "data": rows}
    game["replaydata"]["ants"] = [[5, 5, 1, 6, 0, "----"]]
    game["playerturns"] = [3, 3]
    return game



def _game(**kw):
    """Minimal 0.replay-shaped game: 10x10, 2 players, 10 turns."""
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



def _classic_table():
    """Pre-zero diet: mechanism tests run on explicit amounts.

    The live table zeroes everything but hills, which would vacate
    coverage of splits, gating, walk-back, and terminal interpolation.
    Mechanism tests take this table; the live zeros are pinned by the
    diet test (reward scales) and the live-engine zero tests."""
    return {
        "FOOD": 0.1,
        "KILL": 0.1,
        "DEATH": -0.2,
        "HILL_RAZE": 10.0,
        "HILL_LOST": -10.0,
        "WIN": 5.0,
        "LOSS": -5.0,
        "HILL_APPROACH": 0.25,
    }



def _hill_game(score):
    game = _game()
    game["score"] = score
    game["length"] = 10
    # surviving enemy hill: approach credit without raze credit.
    game["replaydata"]["hills"] = [[9, 9, 1, 999]]
    return game



def test_window_shape_channels_dtype():
    import features

    ants = FakeAnts()
    w = features.local_window(ants, (4, 4), radius=2)
    assert list(w.shape) == [len(features.CHANNELS), 5, 5]
    assert features.CHANNELS == (
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
    one_hot = w[:7].flatten().tolist()
    assert set(one_hot) <= {0.0, 1.0}
    fr = w[features.CHANNELS.index("force_ratio")]
    assert bool(((fr == fr.int()) & (fr.abs() <= 20)).all())
    ed = w[features.CHANNELS.index("enemy_dist")]
    assert bool(((ed >= 0) & (ed <= 1)).all())




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




def test_window_shows_union_content_beyond_own_circle():
    # F1 (losfix): B-tier cells read 0=empty-unseen; the own_sight
    # channel stays the mask. Union content beyond the own circle is
    # no longer stamped into ch1-ch5 (it was indistinguishable from
    # own-visible except ch6=0, a flag the net cannot use).
    import features

    ants = FakeAnts()
    ants.viewradius2 = 8
    ants._mine = [(4, 4)]
    ants._food = [(7, 4), (6, 4)]  # offsets (+3,0) d2=9, (+2,0) d2=4
    w = features.local_window(ants, (4, 4), radius=3)
    food = w[features.CHANNELS.index("food")]
    sight = w[features.CHANNELS.index("own_sight")]
    assert food[6][3] == 0.0  # B-tier: zero-filled, unseen
    assert sight[6][3] == 0.0  # mask intact
    assert food[5][3] == 1.0 and sight[5][3] == 1.0  # own circle: both




def test_window_los_boundary_is_inclusive():
    import features

    ants = FakeAnts()
    ants.viewradius2 = 8
    ants._mine = [(4, 4)]
    ants._food = [(6, 6)]  # offset (+2,+2), d2=8 == viewradius2
    w = features.local_window(ants, (4, 4), radius=3)
    assert w[features.CHANNELS.index("food")][5][5] == 1.0




def test_window_shows_teammate_through_team_sight():
    # Team sight: a cell any allied ant sees reads as seen. The
    # teammate at (7,4) is outside my own circle (d2=9 > 8) but sits
    # inside its own — so it (and the sight flag) now show.
    import features

    ants = FakeAnts()
    ants.viewradius2 = 8
    ants._mine = [(4, 4), (7, 4)]  # second ant at offset (+3,0), d2=9
    w = features.local_window(ants, (4, 4), radius=3)
    own = w[features.CHANNELS.index("own_ant")]
    sight = w[features.CHANNELS.index("own_sight")]
    assert own[3][3] == 1.0  # self still marked
    assert own[6][3] == 1.0  # teammate seen by itself: filled ...
    assert sight[6][3] == 1.0  # ... mask honest




def test_window_team_sight_union_covers_ally_seen_corners():
    # Me (4,4), ally (6,7), sight2=8. Corner cell (7,7) is outside my
    # circle (d2=18) but inside the ally's (d2=1): team sight fills it.
    # Cell (1,1) is outside both circles (d2=18 / d2=41): stays fogged.
    import features

    ants = FakeAnts()
    ants.viewradius2 = 8
    ants._mine = [(4, 4), (6, 7)]
    ants._my_hills = []
    ants._enemy_hills = []
    ants._food = []
    ants._enemy = [((7, 7), 1), ((1, 1), 1)]
    w = features.local_window(ants, (4, 4), radius=3)
    foe = w[features.CHANNELS.index("enemy_ant")]
    sight = w[features.CHANNELS.index("own_sight")]
    assert foe[6][6] == 1.0  # ally-covered corner: filled ...
    assert sight[6][6] == 1.0  # ... mask honest
    assert foe[0][0] == 0.0  # nobody sees (1,1): fog preserved ...
    assert sight[0][0] == 0.0  # ... mask honest




def test_window_full_radius_inside_default_sight():
    import features

    ants = FakeAnts()  # viewradius2=77: radius-4 corner d2=32, all visible
    w = features.local_window(ants, (4, 4), radius=4)
    assert w.sum() > 0.0
    # water tile (2,2) is offset (-2,-2), d2=8 <= 77: still reported
    assert w[features.CHANNELS.index("water")][2][2] == 1.0
    sight = w[features.CHANNELS.index("own_sight")]
    assert sight.min() == 1.0  # whole small window inside own circle




def test_hill_approach_pays_for_closing():
    import math

    import rewards
    from grid import dist2

    game = _game(score=[4, 0])  # win: the mechanism pays; gate off
    game["replaydata"]["hills"] = [[5, 9, 1, 99]]  # enemy hill
    game["replaydata"]["ants"] = [[5, 5, 1, 5, 0, "eee"]]
    records = [
        {"turn": 1, "loc": [5, 5], "dest": [5, 6], "action": "e"},
    ]
    rets = rewards.compute_returns(game, 0, records, _classic_table())
    before = math.sqrt(dist2((5, 5), (5, 9), 10, 10))
    after = math.sqrt(dist2((5, 6), (5, 9), 10, 10))
    assert rets[0] == 5.0 + 0.25 * (before - after)




def test_hill_loss_is_flat_regardless_of_distance():
    import rewards

    game = _game()
    game["replaydata"]["hills"] = [[5, 5, 0, 4]]  # own hill lost turn 4
    records = [
        {"turn": 4, "loc": [5, 7], "dest": [5, 8], "action": "stay"},  # d=3
        {"turn": 4, "loc": [5, 4], "dest": [5, 5], "action": "stay"},  # d=0
    ]
    rets = rewards.compute_returns(game, 0, records)
    # Flat: fleeing must not shrink the loss, or the ledger teaches
    # hill-avoidance instead of hill-defense. Same -10 everywhere.
    assert rets == [rewards.HILL_LOST, rewards.HILL_LOST]




def test_hill_loss_flat_for_equidistant_ants():
    import rewards

    game = _game()
    game["replaydata"]["hills"] = [[5, 5, 0, 4]]  # own hill lost turn 4
    records = [
        {"turn": 4, "loc": [5, 5], "dest": [5, 6], "action": "s"},  # d=1
        {"turn": 4, "loc": [5, 5], "dest": [6, 5], "action": "s"},  # d=1
    ]
    rets = rewards.compute_returns(game, 0, records)
    # headcount-agnostic and distance-agnostic: full -10 each, no halving.
    assert rets == [rewards.HILL_LOST, rewards.HILL_LOST]




def test_outcome_loss_and_draw():
    import rewards

    table = {"WIN": 5.0, "LOSS": -5.0}
    assert rewards.outcome(_game(score=[3, 9]), 0, table) == -5.0
    assert rewards.outcome(_game(score=[5, 5]), 0, table) == rewards.DRAW
    assert rewards.outcome(_game(score=[3, 9]), 0) == 0.0  # live: no terminal




def test_rotate_item_turns_window_action_mask_together():
    import algorithm
    import torch

    w = torch.zeros(_C, _S, _S)
    w[0, 0, _S // 2] = 1.0  # north-center marker
    item = (w, 0, 1.0, [True, False, False, False, True], 0.0)
    rw, ra, rr, rm, _ = algorithm._rotate_item(item, 1)
    assert rw.shape == (_C, _S, _S)
    assert rw[0, _S // 2, 0] == 1.0 and rw.sum() == 1.0  # west-center
    assert ra == 3  # n became w
    assert rr == 1.0  # return untouched
    assert rm == [False, False, False, True, True]  # legal n became legal w
    # stay is invariant under any rotation.
    sw = torch.zeros(_C, _S, _S)
    s = (sw, 4, 0.5, [False, False, False, False, True], 0.0)
    for k in (1, 2, 3):
        _, sa, _, sm, _ = algorithm._rotate_item(s, k)
        assert sa == 4 and sm == [False, False, False, False, True]
    # k=0 identity, k=4 == k=0.
    for k in (0, 4):
        zw, za, _, zm, _ = algorithm._rotate_item(item, k)
        assert torch.equal(zw, w) and za == 0
        assert zm == [True, False, False, False, True]




def test_deep_arch_sees_full_window_where_base_cannot():
    import model
    import torch

    def separation(arch: str) -> float:
        policy = model.CNNPolicy(arch=arch)
        with torch.no_grad():
            for mod in policy.modules():
                if isinstance(mod, torch.nn.Conv2d):
                    mod.weight.fill_(1.0)
                    mod.bias.zero_()
        north = torch.zeros(1, _C, _S, _S)
        north[0, 5, 0, 4] = 1.0  # food 4 north
        south = torch.zeros(1, _C, _S, _S)
        south[0, 5, 8, 4] = 1.0  # food 4 south
        with torch.no_grad():
            return (policy.trunk(north) - policy.trunk(south)).abs().sum().item()

    # Ones-weights: deterministic. Base sees far food only as pooled
    # smear (weak N-vs-S separation); deep's full-window field keeps
    # the direction signal ~5000x stronger.
    assert separation("deep") > 1000 * separation("base")




def test_gated_shaping_zeroes_march_on_loss():
    import rewards

    game = _hill_game([0, 1])  # loss
    records = [{"turn": 1, "loc": [5, 5], "dest": [6, 6], "action": "s"}]
    rets = rewards.compute_returns(game, 0, records)
    # marching pays nothing (amount zero, gate moot): no terminal remains.
    assert rets[0] == 0.0




def test_main_kills_unpaid_on_loss():
    import rewards

    game = _game()
    game["score"] = [0, 1]  # loss
    game["replaydata"]["ants"] = [[5, 5, 1, 3, 1, "--"]]
    records = [
        {"turn": 3, "loc": [5, 4], "dest": [5, 4], "action": "stay"},
    ]
    main = rewards.compute_returns(game, 0, records)
    assert main[0] == 0.0  # kills pay nothing now (split covered live)




def test_death_unpaid_on_loss():
    import rewards

    game = _game()
    game["score"] = [0, 1]  # loss
    game["replaydata"]["ants"] = [[4, 4, 1, 2, 0, "s"]]
    records = [
        {"turn": 2, "loc": [4, 4], "dest": [5, 4], "action": "s"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] == 0.0




def test_window_b64_roundtrip_is_bit_exact():
    import algorithm
    import features
    import torch

    w = torch.randn(10, 15, 15)
    blob = features.encode_window(w)
    assert isinstance(blob, dict) and isinstance(blob["b64"], str)
    assert len(blob["b64"]) == 12000  # 2250 float32 -> base64, exact
    import json as _json

    assert len(_json.dumps(w.tolist())) > 30000  # nested lists balloon
    recs = algorithm.compact_records([{"window": blob, "action": "north"}])
    assert torch.equal(recs[0]["window"], w.to(torch.float32))




def test_compact_records_accepts_both_window_formats():
    import algorithm
    import features
    import torch

    w = torch.zeros(10, 15, 15)
    recs = algorithm.compact_records(
        [{"window": w.tolist(), "action": "stay"},
         {"window": features.encode_window(w), "action": "stay"}]
    )
    assert all(isinstance(r["window"], torch.Tensor) for r in recs)
    assert torch.equal(recs[0]["window"], recs[1]["window"])




def test_window_water_channel_masks_the_move():
    import model
    from types import SimpleNamespace

    loc = (5, 5)
    view = SimpleNamespace(
        rows=10, cols=10, sight2=77, attack2=5, own_ants={loc},
        own_hills=set(), enemy_ants=set(), enemy_hills=set(),
        foods=set(), water={(5, 4)},
    )
    w = features.local_window(None, loc, radius=2, view=view)
    assert w[features.WATER_CHANNEL, 2, 1] == 1.0  # west cell marked
    assert float(w[features.WATER_CHANNEL].sum()) == 1.0
    assert model.legal_mask(w, frozenset()).tolist() == [True, True, True, False, True]




def test_trace_report_counts_order_lost_when_timed_out():
    import rewards

    game = _trace_game()
    game["status"] = ["timeout", "timeout"]
    recs = [{"turn": 3, "loc": [5, 5], "dest": [5, 4], "action": "w"}]
    miss, problems = rewards.trace_report(game, 0, recs)
    assert miss == 1.0 and problems == []




def test_trace_report_flags_order_lost_off_the_timeout_turn():
    import rewards

    game = _trace_game()
    game["status"] = ["timeout", "timeout"]
    game["playerturns"] = [5, 5]  # timeout came later; turn 3 stood alone
    recs = [{"turn": 3, "loc": [5, 5], "dest": [5, 4], "action": "w"}]
    miss, problems = rewards.trace_report(game, 0, recs)
    assert miss == 1.0 and len(problems) == 1 and "without timeout" in problems[0]




def test_trace_report_needs_playerturns_for_lost():
    import rewards

    game = _trace_game()
    game["status"] = ["timeout", "timeout"]
    game.pop("playerturns")
    recs = [{"turn": 3, "loc": [5, 5], "dest": [5, 4], "action": "w"}]
    with pytest.raises(ValueError):  # no turn to pin the cutoff to
        rewards.trace_report(game, 0, recs)




def test_trace_report_flags_order_lost_without_timeout():
    import rewards

    game = _trace_game()
    game["status"] = ["survived", "survived"]
    recs = [{"turn": 3, "loc": [5, 5], "dest": [5, 4], "action": "w"}]
    miss, problems = rewards.trace_report(game, 0, recs)
    assert miss == 1.0 and len(problems) == 1 and "without timeout" in problems[0]




def test_trace_report_needs_status_for_lost():
    import rewards

    game = _trace_game()
    game.pop("status")  # _game carries survived/survived; drop it
    recs = [{"turn": 3, "loc": [5, 5], "dest": [5, 4], "action": "w"}]
    with pytest.raises(ValueError):  # no status to explain the loss
        rewards.trace_report(game, 0, recs)
