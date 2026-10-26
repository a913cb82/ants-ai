"""AlphaAnt v0: per-ant linear policy, stdlib only.

TDD seed: features + model must be importable without numpy/torch,
decide a legal move in microseconds, and never suggest water.
"""

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "ml"))

import features

_C = len(features.CHANNELS)
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


def test_window_shape_channels_dtype():
    import features

    ants = FakeAnts()
    w = features.local_window(ants, (4, 4), radius=2)
    assert list(w.shape) == [_C, 5, 5]
    assert features.CHANNELS == (
        "water",
        "own_ant",
        "own_hill",
        "enemy_ant",
        "enemy_hill",
        "food",
        "own_sight",
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


def test_window_shows_union_content_beyond_own_circle():
    import features

    ants = FakeAnts()
    ants.viewradius2 = 8
    ants._mine = [(4, 4)]
    ants._food = [(7, 4), (6, 4)]  # offsets (+3,0) d2=9, (+2,0) d2=4
    w = features.local_window(ants, (4, 4), radius=3)
    food = w[features.CHANNELS.index("food")]
    sight = w[features.CHANNELS.index("own_sight")]
    assert food[6][3] == 1.0  # union vision: a teammate sees it
    assert sight[6][3] == 0.0  # but not actionable by me right now
    assert food[5][3] == 1.0 and sight[5][3] == 1.0  # own circle: both


def test_window_los_boundary_is_inclusive():
    import features

    ants = FakeAnts()
    ants.viewradius2 = 8
    ants._mine = [(4, 4)]
    ants._food = [(6, 6)]  # offset (+2,+2), d2=8 == viewradius2
    w = features.local_window(ants, (4, 4), radius=3)
    assert w[features.CHANNELS.index("food")][5][5] == 1.0


def test_window_shows_far_teammate_with_sight_flag():
    import features

    ants = FakeAnts()
    ants.viewradius2 = 8
    ants._mine = [(4, 4), (7, 4)]  # second ant at offset (+3,0), d2=9
    w = features.local_window(ants, (4, 4), radius=3)
    own = w[features.CHANNELS.index("own_ant")]
    sight = w[features.CHANNELS.index("own_sight")]
    assert own[3][3] == 1.0  # self still marked
    assert own[6][3] == 1.0  # far teammate visible via union ...
    assert sight[6][3] == 0.0  # ... flagged as beyond my own circle


def test_window_full_radius_inside_default_sight():
    import features

    ants = FakeAnts()  # viewradius2=77: radius-4 corner d2=32, all visible
    w = features.local_window(ants, (4, 4), radius=4)
    assert w.sum() > 0.0
    # water tile (2,2) is offset (-2,-2), d2=8 <= 77: still reported
    assert w[features.CHANNELS.index("water")][2][2] == 1.0
    sight = w[features.CHANNELS.index("own_sight")]
    assert sight.min() == 1.0  # whole small window inside own circle


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


def test_reconstruct_tracks_orders_with_wrap():
    import rewards

    ants = [
        [9, 9, 1, 11, 0, "es"],  # (9,9) ->e-> (9,0) ->s-> (0,0), survives
    ]
    traj = rewards.trajectories(_game()["replaydata"] | {"ants": ants})
    assert traj[(0, 0)] == [(1, (9, 9)), (2, (9, 0)), (3, (0, 0))]


def test_reconstruct_stops_at_death_turn():
    import rewards

    ants = [[4, 4, 1, 2, 0, "s"]]  # moves south on turn 2, dies there
    traj = rewards.trajectories(_game()["replaydata"] | {"ants": ants})
    assert traj[(0, 0)] == [(1, (4, 4)), (2, (5, 4))]


def test_food_credit_goes_to_gatherer_dest():
    import rewards

    game = _game()
    game["replaydata"]["food"] = [[5, 5, 1, 3, 0]]  # gathered by p0 on turn 3
    records = [
        {"turn": 3, "loc": [4, 5], "dest": [5, 5], "action": "s"},
        {"turn": 3, "loc": [0, 0], "dest": [0, 0], "action": "stay"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] == 0.0  # on top: nearby_ants excludes distance 0
    assert rets[1] == 0.0


def test_death_penalizes_dead_ant_only():
    import rewards

    game = _game()
    game["replaydata"]["ants"] = [[4, 4, 1, 2, 0, "s"]]
    records = [
        {"turn": 2, "loc": [4, 4], "dest": [5, 4], "action": "s"},
        {"turn": 2, "loc": [0, 0], "dest": [0, 1], "action": "e"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] == rewards.DEATH
    assert rets[1] == 0.0


def test_kill_credit_splits_among_nearby_attackers():
    import rewards

    game = _game()
    game["replaydata"]["ants"] = [[5, 5, 1, 3, 1, "--"]]  # enemy dies turn 3
    records = [
        {"turn": 3, "loc": [5, 4], "dest": [5, 4], "action": "stay"},
        {"turn": 3, "loc": [0, 0], "dest": [0, 0], "action": "stay"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] == rewards.KILL
    assert rets[1] == 0.0


def test_one_for_one_trade_nets_negative():
    import rewards

    # Asymmetric death: killing pays +1, dying costs -2. A 1-for-1
    # trade nets -1, so mutual annihilation is no longer free — the
    # learner must preserve material to profit from combat.
    game = _game()
    game["replaydata"]["ants"] = [
        [5, 5, 1, 3, 1, "--"],  # enemy dies turn 3
        [5, 4, 1, 3, 0, "s-"],  # own ant dies turn 3
    ]
    records = [
        # death tile is start walked by all orders: (5,4) + s = (6,4).
        {"turn": 3, "loc": [5, 4], "dest": [6, 4], "action": "s"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] == rewards.KILL + rewards.DEATH == -1.0


def test_hill_approach_pays_for_closing():
    import math

    import rewards
    from grid import dist2

    game = _game()
    game["replaydata"]["hills"] = [[5, 9, 1, 99]]  # enemy hill
    game["replaydata"]["ants"] = [[5, 5, 1, 5, 0, "eee"]]
    records = [
        {"turn": 1, "loc": [5, 5], "dest": [5, 6], "action": "e"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    before = math.sqrt(dist2((5, 5), (5, 9), 10, 10))
    after = math.sqrt(dist2((5, 6), (5, 9), 10, 10))
    assert rets[0] == rewards.HILL_APPROACH * (before - after)


def test_hill_approach_ignores_opening_and_staying():
    import rewards

    game = _game()
    game["replaydata"]["hills"] = [[5, 9, 1, 99]]
    game["replaydata"]["ants"] = [[5, 5, 1, 5, 0, "ew-"]]
    records = [
        {"turn": 1, "loc": [5, 5], "dest": [5, 6], "action": "e"},
        {"turn": 2, "loc": [5, 6], "dest": [5, 5], "action": "w"},
        {"turn": 3, "loc": [5, 5], "dest": [5, 5], "action": "stay"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] > 0.0  # closed one tile
    assert rets[1] == 0.0  # opened it back: no credit
    assert rets[2] == 0.0  # stayed: no credit


def test_hill_approach_stays_same_turn_only():
    import rewards

    game = _game()
    game["replaydata"]["hills"] = [[5, 9, 1, 99]]
    game["replaydata"]["ants"] = [[5, 5, 1, 5, 0, "eee"]]
    records = [
        {"turn": 1, "loc": [5, 5], "dest": [5, 4], "action": "w"},
        {"turn": 2, "loc": [5, 4], "dest": [5, 5], "action": "e"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] == 0.0  # opened: no credit, and no walk-back arrives
    assert rets[1] > 0.0  # closed: same-turn credit only


def test_hill_approach_targets_first_hill_only():
    import rewards

    # Shared convention concentrates force: closing to the second hill
    # while opening to the first pays nothing, even though min-nearest
    # would have paid. All ants see the same list, so all march the
    # same hill.
    game = _game()
    game["replaydata"]["hills"] = [[5, 0, 1, 99], [5, 9, 1, 99]]
    game["replaydata"]["ants"] = [[5, 4, 1, 5, 0, "e"]]
    records = [
        {"turn": 1, "loc": [5, 4], "dest": [5, 5], "action": "e"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] == 0.0  # closes to second, opens to first: unpaid
    import rewards

    game = _game()
    game["replaydata"]["ants"] = [[5, 5, 1, 3, 1, "--"]]
    records = [
        {"turn": 3, "loc": [5, 4], "dest": [5, 4], "action": "stay"},
    ]
    base = rewards.compute_returns(game, 0, records)
    sharp = rewards.compute_returns(
        game, 0, records, rewards.scales_for("exploiter"))
    assert sharp[0] == 3 * base[0] == 3 * rewards.KILL


def test_exploiter_scales_keep_outcome():
    import rewards

    assert rewards.scales_for("exploiter")["WIN"] == rewards.WIN
    assert rewards.scales_for("exploiter")["LOSS"] == rewards.LOSS
    assert rewards.scales_for("challenger")["KILL"] == rewards.KILL


def test_hill_raze_credits_the_ant_on_the_hill():
    import rewards

    game = _game()
    game["replaydata"]["hills"] = [[8, 8, 1, 4]]  # enemy hill razed turn 4
    records = [
        {"turn": 4, "loc": [8, 7], "dest": [8, 8], "action": "e"},
        {"turn": 4, "loc": [2, 2], "dest": [2, 2], "action": "stay"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets == [rewards.HILL_RAZE, 0.0]


def test_hill_loss_splits_across_team():
    import rewards

    game = _game()
    game["replaydata"]["hills"] = [[1, 1, 0, 4]]  # own hill lost turn 4
    records = [
        {"turn": 4, "loc": [5, 5], "dest": [5, 5], "action": "stay"},
        {"turn": 4, "loc": [2, 2], "dest": [2, 2], "action": "stay"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets == [rewards.HILL_LOST / 2, rewards.HILL_LOST / 2]


def test_outcome_win_belongs_to_every_move_equally():
    import rewards

    game = _game(score=[10, 4])
    records = [{"turn": 9, "loc": [1, 1], "dest": [1, 1], "action": "stay"}]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] == rewards.WIN


def test_outcome_loss_and_draw():
    import rewards

    assert rewards.outcome(_game(score=[3, 9]), 0) == rewards.LOSS
    assert rewards.outcome(_game(score=[5, 5]), 0) == rewards.DRAW


def test_bot_records_turn_rows_when_env_set(tmp_path, monkeypatch):
    import AlphaAnt

    monkeypatch.setenv("AA_RECORD_DIR", str(tmp_path))

    class StubAnts:
        rows, cols = 10, 10
        viewradius2 = 77

        def my_ants(self):
            return [(4, 4)]

        def enemy_ants(self):
            return []

        def food(self):
            return [(5, 5)]

        def my_hills(self):
            return []

        def enemy_hills(self):
            return []

        def destination(self, loc, d):
            return {"n": (3, 4), "s": (5, 4), "e": (4, 5), "w": (4, 3)}[d]

        def passable(self, loc):
            return True

        def distance(self, a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        def issue_order(self, order):
            pass

        def time_remaining(self):
            return 1000

    bot = AlphaAnt.AlphaAntBot()
    bot.do_setup(StubAnts())
    bot.do_turn(StubAnts())
    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    row = json.loads(files[0].read_text().strip().splitlines()[-1])
    assert row["turn"] == 1
    assert row["action"] in ("n", "e", "s", "w", "stay")
    assert "dest" in row and "legal" in row
    assert len(row["window"]) == len(features.CHANNELS)
    assert len(row["window"][0]) == 2 * features.DEFAULT_RADIUS + 1
    assert len(row["legal"]) == 5


def test_bot_samples_with_temperature(tmp_path, monkeypatch):
    import torch

    import AlphaAnt

    monkeypatch.setenv("AA_RECORD_DIR", str(tmp_path))
    monkeypatch.setenv("AA_TEMPERATURE", "3.0")

    class SymmetricStub:
        rows, cols = 10, 10
        viewradius2 = 77

        def my_ants(self):
            return [(4, 4)]

        def enemy_ants(self):
            return []

        def food(self):
            return []

        def my_hills(self):
            return []

        def enemy_hills(self):
            return []

        def destination(self, loc, d):
            return {"n": (3, 4), "s": (5, 4), "e": (4, 5), "w": (4, 3)}[d]

        def passable(self, loc):
            return True

        def distance(self, a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        def issue_order(self, order):
            pass

        def time_remaining(self):
            return 1000

    torch.manual_seed(0)
    bot = AlphaAnt.AlphaAntBot()
    bot.do_setup(SymmetricStub())
    seen = set()
    for _ in range(200):
        bot.do_turn(SymmetricStub())
        lines = open(next(tmp_path.glob("*.jsonl"))).read().strip().splitlines()
        seen.add(json.loads(lines[-1])["action"])
    assert len(seen) >= 2


def test_bot_weights_path_override(tmp_path):
    import json

    import torch

    import model
    import AlphaAnt

    torch.manual_seed(123)
    alt = tmp_path / "alt.json"
    alt.write_text(json.dumps(model.state_dict_to_lists(model.CNNPolicy())))
    bot = AlphaAnt.AlphaAntBot(weights_path=str(alt))
    assert bot.policy(torch.zeros(1, _C, _S, _S)).shape == (1, 5)


def test_food_credit_by_spawnradius_proximity():
    import rewards

    game = _game()
    game["replaydata"]["food"] = [[5, 5, 1, 3, 0]]  # spawnradius2=1: adjacent counts
    records = [
        # gatherer stays: this stays a pure food-channel test.
        {"turn": 3, "loc": [5, 4], "dest": [5, 4], "action": "stay"},
        {"turn": 3, "loc": [0, 0], "dest": [0, 0], "action": "stay"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] == rewards.FOOD
    assert rets[1] == 0.0


def test_food_splits_one_pickup_across_all_adjacent_ants():
    import rewards

    game = _game()
    game["replaydata"]["food"] = [[5, 5, 1, 3, 0]]
    records = [
        # both gatherers stay: pure split test.
        {"turn": 3, "loc": [5, 4], "dest": [5, 4], "action": "stay"},
        {"turn": 3, "loc": [5, 6], "dest": [5, 6], "action": "stay"},
        {"turn": 3, "loc": [0, 0], "dest": [0, 0], "action": "stay"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets == [rewards.FOOD / 2, rewards.FOOD / 2, 0.0]


def test_dense_reward_discounts_back_along_ant_path():
    import rewards

    game = _game()
    game["replaydata"]["ants"] = [
        [4, 4, 0, 99, 0, "ss"],
        # balancing enemy survivor: the draw stays 0-0 on material so
        # the tiebreak cannot fire and the walk-back shape is isolated.
        [0, 0, 0, 99, 1, "nn"],
    ]
    game["replaydata"]["food"] = [[6, 5, 1, 2, 0]]  # adjacent to (6,4) at turn 2
    records = [
        {"turn": 1, "loc": [4, 4], "dest": [5, 4], "action": "s"},
        {"turn": 2, "loc": [5, 4], "dest": [6, 4], "action": "s"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    # food walks back along the path: full amount on the gather turn,
    # discounted one step on the approach turn.
    assert rets[1] == rewards.FOOD
    assert rets[0] == rewards.FOOD * rewards.GAMMA


def _cnn_window(water_dests=(), radius=4):
    import torch

    from features import CHANNELS

    w = torch.zeros(_C, 2 * radius + 1, 2 * radius + 1)
    w[CHANNELS.index("own_ant")][radius][radius] = 1.0
    for action in water_dests:
        dr, dc = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1), "stay": (0, 0)}[action]
        w[CHANNELS.index("water")][radius + dr][radius + dc] = 1.0
    return w


def test_cnn_forward_shape():
    import torch

    import model

    policy = model.CNNPolicy()
    assert policy(torch.zeros(1, _C, _S, _S)).shape == (1, 5)


def _probs(policy, w):
    import torch

    policy.eval()
    with torch.no_grad():
        return torch.softmax(policy(w), dim=1)


def test_forward_is_rotation_equivariant():
    import torch

    import model

    torch.manual_seed(3)
    policy = model.CNNPolicy()
    w = torch.rand(4, _C, _S, _S)
    base = _probs(policy, w)
    for k in (1, 2, 3):
        got = _probs(policy, torch.rot90(w, k, (2, 3)))
        back = got[:, list(model.UNROT[k])]
        assert torch.allclose(base, back, atol=1e-5), k


def test_forward_is_flip_equivariant():
    import torch

    import model

    torch.manual_seed(5)
    policy = model.CNNPolicy()
    w = torch.rand(4, _C, _S, _S)
    base = _probs(policy, w)
    got = _probs(policy, torch.flip(w, (3,)))
    assert torch.allclose(base, got[:, list(model.UNFLIP)], atol=1e-5)


def test_anchor_kl_zero_for_identical_policies():
    import torch

    import algorithm

    torch.manual_seed(11)
    pol = algorithm.new_policy({})
    anchor = algorithm.new_policy(algorithm.policy_weights(pol))
    opt = algorithm.make_optimizer(pol, lr=0.0)  # frozen: KL stays exact
    recs = [{"window": torch.rand(_C, _S, _S), "action": "n",
             "legal": [True] * 5} for _ in range(32)]
    batch = algorithm.collect(pol, recs, [1.0] * 32)
    stats = algorithm.train_epoch(pol, opt, batch, anchor=anchor,
                                  kl_anchor_beta=0.1)
    assert stats["kl_anchor"] == 0.0


def test_anchor_pulls_policy_toward_it():
    import torch

    import algorithm
    import model

    torch.manual_seed(13)
    pol = algorithm.new_policy({})
    anchor = algorithm.new_policy({})
    anchor.head.bias.data = torch.tensor([5.0, 0, 0, 0, 0])
    anchor.eval()
    probe = [torch.rand(_C, _S, _S) for _ in range(64)]

    def agree(p):
        p.eval()
        with torch.no_grad():
            n = 0
            for w in probe:
                if int(model.masked_logits(
                        p, w, frozenset()).argmax()) == int(
                        model.masked_logits(
                        anchor, w, frozenset()).argmax()):
                    n += 1
            return n / len(probe)

    def mass(p):
        p.eval()
        with torch.no_grad():
            tot = 0.0
            for w in probe:
                m = torch.tensor([[True] * 5])
                lp = model.masked_log_softmax(p, w.unsqueeze(0), m)
                la = model.masked_log_softmax(anchor, w.unsqueeze(0), m)
                tot += float(lp.exp()[0, int(la.argmax())])
            return tot / len(probe)

    before = agree(pol)
    mass_before = mass(pol)
    opt = algorithm.make_optimizer(pol)
    recs = [{"window": torch.rand(_C, _S, _S), "action": "n",
             "legal": [True] * 5} for _ in range(64)]
    batch = algorithm.collect(pol, recs, [1.0] * 64)
    algorithm.train_epoch(pol, opt, batch, vf_coef=0.0,
                          entropy_beta=0.0, anchor=anchor,
                          kl_anchor_beta=0.5)
    assert agree(pol) >= before and mass(pol) > mass_before


def test_padded_old_weights_give_identical_outputs():
    import torch

    import algorithm
    import model

    torch.manual_seed(23)
    old = model.CNNPolicy(channels=6)
    old.eval()
    blob = algorithm.policy_weights(old)
    new = algorithm.new_policy(blob)
    new.eval()
    with torch.no_grad():
        w6 = torch.rand(3, 6, _S, _S)
        pad = torch.zeros(3, 1, _S, _S)
        assert torch.equal(old(w6), new(torch.cat([w6, pad], dim=1)))
        assert torch.equal(old.values(w6),
                           new.values(torch.cat([w6, pad], dim=1)))


def test_opt_state_drops_reshaped_params():
    import torch

    import algorithm
    import model

    torch.manual_seed(31)
    old = model.CNNPolicy(channels=6)
    opt = algorithm.make_optimizer(old)
    old(torch.rand(2, 6, 9, 9)).sum().backward()
    opt.step()  # populates momentum buffers
    blob = algorithm.serialize_opt(opt)
    new = model.CNNPolicy()  # 7 channels now
    opt2 = algorithm.make_optimizer(new)
    algorithm.load_opt_state(opt2, blob)  # must not raise ...
    new(torch.rand(2, 7, 15, 15)).sum().backward()
    opt2.step()  # ... nor crash here (the round-18 failure).
    cur = opt2.state_dict()["state"]
    params = [p for g in opt2.param_groups for p in g["params"]]
    for i, p in enumerate(params):
        if i in cur:
            for v in cur[i].values():
                if torch.is_tensor(v) and v.shape != torch.Size(()):
                    assert v.shape == p.shape


def test_train_opponents_guarantee_champ_slot(tmp_path):
    import archive
    import train

    base = tmp_path / "archive"
    for _ in range(21):
        archive.save_checkpoint(base, {"w": [1.0]}, "main", None)
    archive.set_champion(base, "g020")
    for old in ("g000", "g001"):
        archive.record_result(base, "g020", old, 3, 0)
    opps = train._train_opponents(base, "g020", "g019", 4, seed=3)
    assert opps[0] == "g019"  # the eval target is always trained against
    assert len(opps) == 4


def test_last_exploiter_returns_most_recent(tmp_path):
    import archive

    base = tmp_path / "archive"
    assert archive.last_exploiter(base) is None
    a = archive.save_checkpoint(base, {"w": [1.0]}, "exploiter", None)
    archive.save_checkpoint(base, {"w": [2.0]}, "challenger", None)
    b = archive.save_checkpoint(base, {"w": [3.0]}, "exploiter", a)
    assert archive.last_exploiter(base) == b


def test_exploiter_chains_rival_weights_and_opt(tmp_path, monkeypatch):
    import archive
    import selfplay

    captured: dict = {}
    _mocked_generation(monkeypatch, captured)
    base = tmp_path / "archive"
    cfg = _exploiter_cfg()
    # drive to the first exploiter (gen 2), then the second (gen 5)
    selfplay.run_generation(cfg, base, commit=False)
    selfplay.run_generation(cfg, base, commit=False)
    rep = selfplay.run_generation(cfg, base, commit=False)
    assert rep["exploiter"] is True
    first = rep["challenger"]
    w1 = archive.load_checkpoint(base, first)
    opt_path = base / "checkpoints" / (first + ".opt.json")
    selfplay.append_history(base, {"gen": 97})
    selfplay.append_history(base, {"gen": 98})
    rep2 = selfplay.run_generation(cfg, base, commit=False)
    assert rep2["exploiter"] is True
    assert captured["init_w"] == w1  # rival continues, not reseeds
    members = {m["id"]: m for m in archive.members(base)}
    assert members[rep2["challenger"]]["parent"] == first
    assert opt_path.exists()  # rival banks its optimizer


def test_values_are_rotation_invariant():
    import torch

    import model

    torch.manual_seed(7)
    policy = model.CNNPolicy()
    policy.eval()
    with torch.no_grad():
        w = torch.rand(4, _C, _S, _S)
        base = policy.values(w)
        for k in (1, 2, 3):
            assert torch.allclose(
                base, policy.values(torch.rot90(w, k, (2, 3))), atol=1e-5)


def test_cnn_radius_agnostic():
    import torch

    import model

    policy = model.CNNPolicy()
    assert policy(torch.zeros(1, _C, 5, 5)).shape == (1, 5)


def test_cnn_water_mask_forces_stay():
    import model

    policy = model.CNNPolicy()
    w = _cnn_window(water_dests=("n", "e", "s", "w"))
    assert model.act_greedy(policy, w) == "stay"


def test_cnn_probs_sum_to_one_and_mask_water():
    import model

    policy = model.CNNPolicy()
    w = _cnn_window(water_dests=("n", "e"))
    probs = model.act_probs(policy, w)
    assert abs(sum(probs.values()) - 1.0) < 1e-5
    assert probs["n"] == 0.0 and probs["e"] == 0.0


def test_cnn_sample_stays_legal_and_spreads():
    import torch

    import model

    torch.manual_seed(7)
    policy = model.CNNPolicy()
    w = _cnn_window()
    seen = {model.sample(policy, w, temperature=3.0) for _ in range(200)}
    assert seen <= {"n", "e", "s", "w", "stay"}
    assert len(seen) >= 2


def test_cnn_state_dict_json_roundtrip(tmp_path):
    import json
    import torch

    import model

    policy = model.CNNPolicy()
    path = tmp_path / "w.json"
    path.write_text(json.dumps(model.state_dict_to_lists(policy)))
    policy2 = model.CNNPolicy()
    policy2.load_state_dict(model.lists_to_state_dict(json.loads(path.read_text())))
    x = torch.zeros(1, _C, _S, _S)
    assert torch.equal(policy(x), policy2(x))


def test_weights_file_loads_into_cnn():
    import json

    import torch

    import model

    wpath = ROOT / "bots" / "alphaant" / "weights.json"
    policy = model.CNNPolicy()
    # Old champions predate the value head (strict=False keeps policy
    # weights, value head stays zero-initialized) and the widening
    # (pad_in_channels: new input channels load zeroed, old behavior
    # preserved exactly, lineage continues).
    policy.load_state_dict(
        model.pad_in_channels(
            model.lists_to_state_dict(json.loads(wpath.read_text())),
            policy),
        strict=False,
    )
    assert policy(torch.zeros(1, _C, _S, _S)).shape == (1, 5)


def test_act_ranked_lists_best_first_and_respects_blocked():
    import model

    policy = model.CNNPolicy()
    w = _cnn_window()
    ranked = model.act_ranked(policy, w)
    assert set(ranked) == {"n", "e", "s", "w", "stay"}
    assert ranked[0] == model.act_greedy(policy, w)
    top = model.act_greedy(policy, w)
    ranked_blocked = model.act_ranked(policy, w, blocked={top})
    assert ranked_blocked[0] != top


def _train_batch(returns=(1.0, 2.0, 3.0), logps=None):
    import torch

    windows = torch.zeros(len(returns), _C, _S, _S)
    windows[:, 1, 4, 4] = 1.0
    if logps is None:
        logps = [0.0] * len(returns)
    return [
        (windows[i], i % 5, float(r), [True] * 5, float(o))
        for i, (r, o) in enumerate(zip(returns, logps))
    ]


def test_ppo_raises_advantaged_logprob():
    import torch

    import model
    import algorithm

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    opt = algorithm.make_optimizer(policy, lr=1e-2)
    batch = _train_batch(returns=(1.0, 0.0))
    before = algorithm.masked_log_probs(policy, batch)[0][0].item()
    algorithm.train_epoch(policy, opt, batch)
    assert algorithm.masked_log_probs(policy, batch)[0][0].item() > before


def test_ppo_value_head_starts_at_zero_and_learns():
    import torch

    import model
    import algorithm

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    assert torch.equal(
        policy.values(torch.zeros(2, _C, _S, _S)), torch.zeros(2)
    )
    opt = algorithm.make_optimizer(policy, lr=1e-2)
    windows = torch.zeros(4, _C, _S, _S)
    for i in range(4):
        windows[i, 1, 4, 4] = float(i + 1)  # distinct states, fittable values
    batch = [(windows[i], i % 5, float(i), [True] * 5, 0.0) for i in range(4)]
    first = algorithm.train_epoch(policy, opt, batch, entropy_beta=0.0)
    assert first["v_loss"] > 0.0
    for _ in range(50):
        last = algorithm.train_epoch(policy, opt, batch, entropy_beta=0.0)
    assert last["v_loss"] < first["v_loss"]


def test_train_epoch_policy_noop_on_equal_returns():
    import torch

    import model
    import algorithm

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    opt = algorithm.make_optimizer(policy, lr=1e-2)
    head_before = [p.detach().clone() for p in [policy.head.weight, policy.head.bias]]
    stats = algorithm.train_epoch(
        policy, opt, _train_batch((2.0, 2.0, 2.0)), entropy_beta=0.0
    )
    assert stats["pg_loss"] == 0.0  # equal returns, zero baseline -> no signal
    for b, p in zip(head_before, [policy.head.weight, policy.head.bias], strict=True):
        assert torch.equal(b, p)


def test_train_epoch_empty_batch_is_noop():
    import model
    import algorithm

    policy = model.CNNPolicy()
    opt = algorithm.make_optimizer(policy)
    stats = algorithm.train_epoch(policy, opt, [])
    assert stats["loss"] == 0.0 and stats["mean_return"] == 0.0 and stats["steps"] == 0


def test_train_epoch_ignores_masked_logits():
    import torch

    import model
    import algorithm

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    opt = algorithm.make_optimizer(policy, lr=1e-2)
    # Actions 2-4 are illegal; the gradient must not touch their mass.
    w = torch.zeros(_C, _S, _S)
    w[1, 4, 4] = 1.0
    mask = [True, True, False, False, False]
    batch = [(w, 0, 1.0, mask, 0.0), (w, 1, 0.0, mask, 0.0)]
    before = [p.detach().clone() for p in policy.parameters()]
    algorithm.train_epoch(policy, opt, batch)
    after = [p.detach().clone() for p in policy.parameters()]
    assert any(not torch.equal(b, a) for b, a in zip(before, after))
    logp = model.masked_log_softmax(
        policy,
        torch.stack([w, w]),
        torch.tensor([mask, mask], dtype=torch.bool),
    )
    assert bool((logp[:, 2:].exp() < 1e-6).all())


def test_archive_save_load_roundtrip(tmp_path):
    import archive

    base = tmp_path / "archive"
    cid = archive.save_checkpoint(base, {"w": [1.0]}, role="main", parent=None)
    assert archive.load_checkpoint(base, cid) == {"w": [1.0]}
    assert archive.members(base)[0]["id"] == cid


def test_nash_splits_rock_paper_scissors(tmp_path):
    import archive

    base = tmp_path / "archive"
    a = archive.save_checkpoint(base, {}, role="main", parent=None)
    b = archive.save_checkpoint(base, {}, role="main", parent=None)
    c = archive.save_checkpoint(base, {}, role="main", parent=None)
    archive.record_result(base, a, b, 1, 0)
    archive.record_result(base, b, c, 1, 0)
    archive.record_result(base, c, a, 1, 0)
    mix = archive.nash_mixture(base)
    for cid in (a, b, c):
        assert mix[cid] == abs(mix[cid]) and abs(mix[cid] - 1 / 3) < 0.05


def test_nash_crowns_dominant_strategy(tmp_path):
    import archive

    base = tmp_path / "archive"
    a = archive.save_checkpoint(base, {}, role="main", parent=None)
    b = archive.save_checkpoint(base, {}, role="main", parent=None)
    archive.record_result(base, a, b, 5, 0)
    archive.record_result(base, a, b, 3, 0)
    archive.record_result(base, a, b, 7, 2)
    mix = archive.nash_mixture(base)
    assert mix[a] > 0.9 and mix[b] < 0.1


def test_pfsp_prefers_beaters(tmp_path):
    import archive

    base = tmp_path / "archive"
    champ = archive.save_checkpoint(base, {}, role="main", parent=None)
    beater = archive.save_checkpoint(base, {}, role="main", parent=None)
    victim = archive.save_checkpoint(base, {}, role="main", parent=None)
    for _ in range(5):
        archive.record_result(base, beater, champ, 1, 0)
        archive.record_result(base, champ, victim, 1, 0)
    picks = archive.sample_opponents(base, champ, 200, self_play_frac=0.0, seed=0)
    assert picks.count(beater) > picks.count(victim) * 2


def test_to_batch_converts_rows_and_returns():
    import torch

    import algorithm

    records = [
        {"window": torch.zeros(_C, _S, _S).tolist(), "action": "e"},
        {
            "window": torch.zeros(_C, _S, _S).tolist(),
            "action": "stay",
            "legal": [False, False, False, False, True],
        },
    ]
    batch = algorithm.to_batch(records, [1.0, -1.0], [0.0, 0.0])
    assert len(batch) == 2
    assert batch[0][0].shape == torch.Size([_C, _S, _S])
    assert batch[0][1] == 1 and batch[1][1] == 4
    assert batch[0][2] == 1.0 and batch[1][2] == -1.0
    assert batch[0][3] == [True] * 5
    assert batch[1][3] == [False, False, False, False, True]


def test_promote_rule_needs_wilson():
    import evaluate

    assert evaluate.should_promote(10, 0, 10)
    assert evaluate.should_promote(7, 0, 10)
    assert not evaluate.should_promote(6, 0, 10)
    # draws count half: 6W/2D (7.0 effective) clears, 5W/2D doesn't.
    assert evaluate.should_promote(6, 2, 10)
    assert not evaluate.should_promote(5, 2, 10)


def test_wilson_lower_bounds():
    import archive

    assert archive.wilson_lower(0, 0) == 0.0
    assert archive.wilson_lower(6, 6) > 0.7
    assert archive.wilson_lower(3, 6) < 0.5


def test_matrices_separate_train_and_eval(tmp_path):
    import archive

    base = tmp_path / "archive"
    a = archive.save_checkpoint(base, {}, role="main", parent=None)
    b = archive.save_checkpoint(base, {}, role="main", parent=None)
    archive.record_result(base, a, b, 1, 0, kind="train")
    assert b not in archive.win_rates(base, a)  # train registers no members
    _, mat = archive.payoff_matrix(base)
    assert mat.size == 0  # no eval games yet, no population
    archive.record_result(base, a, b, 1, 0, kind="eval")
    assert archive.win_rates(base, a)[b] < 0.5


def test_kill_credit_excludes_zero_distance():
    import rewards

    game = _game()
    game["replaydata"]["ants"] = [[5, 5, 1, 3, 1, "--"]]  # enemy dies on (5,5)
    records = [{"turn": 3, "loc": [5, 4], "dest": [5, 5], "action": "s"}]
    assert rewards.compute_returns(game, 0, records) == [0.0]




def test_rotation_permutes_actions_and_masks():
    import algorithm

    # n->w->s->e->n per CCW turn; stay fixed; mask follows the action.
    names = ["n", "e", "s", "w", "stay"]
    assert [names[algorithm.ROT_PERM[i]] for i in range(5)] == [
        "w", "n", "e", "s", "stay"]
    mask = [True, False, True, False, True]
    assert [[mask[i] for i in algorithm.ROT_MASK]] == [
        [False, True, False, True, True]]
    # four turns return every action.
    a = 0
    for _ in range(4):
        a = algorithm.ROT_PERM[a]
    assert a == 0


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


def test_decompose_reports_category_mass():
    import rewards

    game = _game(score=[10, 4])
    game["replaydata"]["food"] = [[5, 5, 1, 3, 0]]
    records = [
        {"turn": 3, "loc": [5, 3], "dest": [5, 4], "action": "e"},
        {"turn": 3, "loc": [0, 0], "dest": [0, 0], "action": "stay"},
    ]
    mass = rewards.decompose(game, 0, records)
    assert mass["food"] == rewards.FOOD
    assert mass["terminal"] == rewards.WIN  # per-record, not xN
    assert mass["result"] == "win"
    assert mass["kill"] == 0.0
    assert "draw" not in mass


def test_decompose_draw_and_loss():
    import rewards

    game = _game(score=[1, 1])
    mass = rewards.decompose(game, 0, [{"turn": 0, "loc": [0, 0],
                                         "dest": [0, 0], "action": "stay"}])
    assert mass["terminal"] == 0.0 and mass["result"] == "draw"
    game = _game(score=[0, 5])
    mass = rewards.decompose(game, 0, [{"turn": 0, "loc": [0, 0],
                                         "dest": [0, 0], "action": "stay"}])
    assert mass["terminal"] == -rewards.WIN and mass["result"] == "loss"


def test_legal_mask_blocks_food_tiles():
    import torch

    import model

    policy = model.CNNPolicy()
    w = _cnn_window()
    w[5, 4, 5] = 1.0  # food east of center
    mask = model.legal_mask(w)
    assert mask.tolist() == [True, False, True, True, True]


@pytest.mark.slow
def test_game_if_mirror_plays_and_prices(tmp_path):
    import game_if
    import rewards

    out = game_if.play(
        ROOT,
        sys.executable,
        json.loads((ROOT / "bots" / "alphaant" / "weights.json").read_text()),
        json.loads((ROOT / "bots" / "alphaant" / "weights.json").read_text()),
        game_if.GameConfig(
            map="tools/maps/example/tutorial1.map",
            turns=10,
            temperature=1.0,
            player_seed=0,
            engine_seed=0,
        ),
        tmp_path / "g0",
    )
    assert out["game"]["game_length"] == 10
    assert out["records_a"] and out["records_b"]
    r = rewards.compute_returns(out["game"], 0, out["records_a"])
    assert len(r) == len(out["records_a"])


def test_cli_defaults_match_default_config():
    import selfplay

    cfg = selfplay.parse_args([])
    assert cfg == selfplay.default_config()


def test_cli_overrides():
    import selfplay

    cfg = selfplay.parse_args(
        ["--train-games", "2", "--turns", "20", "--no-commit",
         "--maps", "tools/maps/example/tutorial1.map"]
    )
    assert cfg["train_games"] == 2
    assert cfg["turns"] == 20
    assert cfg["commit"] is False
    # Single-map pools hold nothing out: everything trains.
    assert cfg["maps"] == ["tools/maps/example/tutorial1.map"]
    assert cfg["held_maps"] == []


def test_game_if_cleanup_keeps_replay_drops_sides(tmp_path):
    import game_if

    outdir = tmp_path / "g0"
    (outdir / "side_a" / "records").mkdir(parents=True)
    (outdir / "side_b").mkdir(parents=True)
    (outdir / "logs").mkdir(parents=True)
    (outdir / "logs" / "0.replay").write_text("{}")
    game_if.cleanup(outdir)
    assert (outdir / "logs" / "0.replay").exists()
    assert not (outdir / "side_a").exists()
    assert not (outdir / "side_b").exists()


@pytest.mark.slow
def test_first_generation_runs_and_reports(tmp_path):
    import selfplay

    cfg = selfplay.default_config()
    cfg.update({"turns": 10, "train_games": 1, "eval_games": 1,
                "epochs": 1, "seed": 1})
    rep = selfplay.run_generation(cfg, tmp_path / "archive", commit=False)
    assert rep["train"]["rows"] > 0
    assert set(rep["train"]) >= {"rows", "losses", "mean_return"}
    assert rep["eval"]["games"] == 1
    assert isinstance(rep["promoted"], bool)
    assert rep["config"]["turns"] == 10
    leftovers = [p for p in (tmp_path / "archive" / "games").rglob("side_a")]
    assert leftovers == []


def test_games_index_roundtrip_and_filter(tmp_path):
    import archive

    base = tmp_path / "archive"
    archive.log_game(base, "g001", "train", "g000", "g001", 3, 1, "games/g001/t0/logs/0.replay")
    archive.log_game(base, "g001", "eval", "g001", "g002", 2, 2, "games/g001/e0/logs/0.replay")
    all_games = archive.list_games(base)
    assert len(all_games) == 2
    mine = archive.list_games(base, member="g002")
    assert len(mine) == 1 and mine[0]["kind"] == "eval"
    assert mine[0]["replay"] == "games/g001/e0/logs/0.replay"


def test_log_game_records_map_name(tmp_path):
    import archive

    base = tmp_path / "archive"
    archive.log_game(base, "g001", "train", "g000", "g001", 3, 1,
                     "games/g001/t0/logs/0.replay", map="rung2c_gap.map")
    archive.log_game(base, "g001", "eval", "g001", "g002", 2, 2,
                     "games/g001/e0/logs/0.replay")
    rows = {r["replay"]: r for r in archive.list_games(base)}
    assert rows["games/g001/t0/logs/0.replay"]["map"] == "rung2c_gap.map"
    assert rows["games/g001/e0/logs/0.replay"]["map"] is None


def test_history_append_and_read(tmp_path):
    import selfplay

    base = tmp_path / "archive"
    selfplay.append_history(base, {"gen": 0, "promoted": True})
    selfplay.append_history(base, {"gen": 1, "promoted": False})
    hist = selfplay.read_history(base)
    assert [h["gen"] for h in hist] == [0, 1]


def test_snapshot_empty_and_populated(tmp_path):
    import archive
    import dashboard
    import selfplay

    base = tmp_path / "archive"
    snap = dashboard.snapshot(base)
    assert snap["champion"] is None and snap["members"] == [] and snap["games"] == []
    a = archive.save_checkpoint(base, {}, role="main", parent=None)
    b = archive.save_checkpoint(base, {}, role="challenger", parent=a)
    archive.set_champion(base, a)
    archive.log_game(base, a, "eval", a, b, 3, 1, "games/g000/e0/logs/0.replay")
    selfplay.append_history(base, {"train": {"losses": [0.5], "mean_return": 1.0}})
    snap = dashboard.snapshot(base)
    assert snap["champion"] == a
    assert snap["members"][0]["wins"] == 1.0
    assert snap["games"][0]["replay"].endswith("0.replay")


def test_snapshot_flags_exploiter_generations(tmp_path):
    import dashboard
    import selfplay

    base = tmp_path / "archive"
    selfplay.append_history(base, {
        "challenger": "c1", "champion": "m", "promoted": False,
        "exploiter": True,
        "train": {"losses": [0.5], "mean_return": 0.1},
        "eval": {"wins": 0, "draws": 2, "games": 2, "win_rate": 0.5,
                 "margins": [0, 0], "mean_margin": 0.0},
        "config": {},
    })
    snap = dashboard.snapshot(base)
    assert snap["generations"][0]["exploiter"] is True
    assert snap["generations"][0]["margins"] == [0, 0]


def test_batch_norm_keeps_event_magnitude_over_noise():
    import torch

    import algorithm
    import model

    policy = model.CNNPolicy()
    n = 64
    rets = [0.1] * (n - 1) + [5.0]
    windows = torch.zeros(n, _C, _S, _S)
    values = policy.values(windows)
    all_ret = torch.tensor(rets)
    adv = algorithm._advantages(
        all_ret, values, all_ret.mean(), all_ret.std(unbiased=False))
    noise, event = adv[:-1].abs().max().item(), abs(adv[-1].item())
    # one real event must outweigh the loudest noise row by an order
    # of magnitude; per-minibatch standardization would make them O(1).
    assert event > 10 * noise


def test_snapshot_carries_run_timing_and_plan(tmp_path):
    import dashboard
    import selfplay

    base = tmp_path / "archive"
    for i, dur in enumerate([40.0, 44.0]):
        selfplay.append_history(base, {
            "challenger": f"c{i}", "champion": "m", "promoted": False,
            "started_at": 1000.0 * i, "finished_at": 1000.0 * i + dur,
            "duration_s": dur,
            "train": {"losses": [0.5], "mean_return": 0.1},
            "eval": {"wins": 0, "draws": 2, "games": 2, "win_rate": 0.5,
                     "margins": [0, 0], "mean_margin": 0.0},
            "config": {},
        })
    (base / "run_plan.json").write_text('{"target_gens": 10}')
    snap = dashboard.snapshot(base)
    assert snap["generations"][0]["duration_s"] == 44.0  # newest first
    assert snap["generations"][0]["finished_at"] == 1044.0
    run = snap["run"]
    assert run == {"finished": 2, "target": 10, "avg_s": 42.0,
                   "last_finished_at": 1044.0}


def test_replay_page_guards_traversal(tmp_path):
    import dashboard

    base = tmp_path / "archive"
    (base / "games").mkdir(parents=True)
    (base / "games" / "0.replay").write_text("{}")
    assert dashboard.replay_page(base, "games/0.replay") is not None
    assert dashboard.replay_page(base, "games/r.json") is None  # not a replay
    assert dashboard.replay_page(base, "../../etc/passwd") is None
    assert dashboard.replay_page(base, "missing.json") is None


def test_status_roundtrip(tmp_path):
    import archive

    base = tmp_path / "archive"
    assert archive.read_status(base) == {}
    archive.write_status(base, {"phase": "train", "done": 2, "total": 8})
    assert archive.read_status(base)["done"] == 2


def test_snapshot_carries_live_status(tmp_path):
    import archive
    import dashboard

    base = tmp_path / "archive"
    assert dashboard.snapshot(base)["status"] == {}
    archive.write_status(base, {"phase": "eval", "done": 3, "total": 20})
    assert dashboard.snapshot(base)["status"]["phase"] == "eval"


def test_dashboard_http_api(tmp_path):
    import json
    import threading
    import urllib.request

    import archive
    import dashboard

    base = tmp_path / "archive"
    a = archive.save_checkpoint(base, {}, role="main", parent=None)
    archive.set_champion(base, a)
    srv = dashboard.make_handler(base)
    import http.server

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), srv)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        root = f"http://127.0.0.1:{httpd.server_address[1]}"
        snap = json.load(urllib.request.urlopen(root + "/api/snapshot", timeout=5))
        assert snap["champion"] == a and snap["game_total"] == 0
        assert "generations" in snap and "status" in snap
        archive.log_game(base, a, "eval", a, a, 1, 1, "games/g/e/logs/0.replay")
        page = json.load(urllib.request.urlopen(root + "/api/games?limit=1", timeout=5))
        assert page["total"] == 1 and len(page["rows"]) == 1
        with urllib.request.urlopen(root + "/", timeout=5) as r:
            assert "no-store" in r.headers.get("Cache-Control", "")
    finally:
        httpd.shutdown()


def test_list_games_skips_malformed_rows(tmp_path):
    import archive

    base = tmp_path / "archive"
    archive.init(base)
    with open(base / "games.jsonl", "w") as f:
        f.write("{not json\n")
        f.write('{"gen":"g","kind":"eval","a":"x"}\n')  # missing keys
        f.write('{"gen":"g","kind":"eval","a":"x","b":"y","score_a":null,"score_b":1,"replay":"r"}\n')
        f.write('{"gen":"g","kind":"eval","a":"x","b":"y","score_a":2,"score_b":1,"replay":"r"}\n')
    rows = archive.list_games(base)
    assert len(rows) == 1 and rows[0]["score_a"] == 2


def test_snapshot_survives_poisoned_index(tmp_path):
    import archive
    import dashboard

    base = tmp_path / "archive"
    a = archive.save_checkpoint(base, {}, role="main", parent=None)
    archive.set_champion(base, a)
    with open(base / "games.jsonl", "w") as f:
        f.write('{"gen":"x","kind":"eval","a":"g000"}\n')
    snap = dashboard.snapshot(base)
    assert snap["game_total"] == 0


def test_nash_splits_evenly_on_all_draws(tmp_path):
    import archive

    base = tmp_path / "archive"
    a = archive.save_checkpoint(base, {}, role="main", parent=None)
    b = archive.save_checkpoint(base, {}, role="challenger", parent=a)
    archive.record_result(base, a, b, 1, 1)
    mix = archive.nash_mixture(base)
    assert abs(mix[a] - 0.5) < 1e-6 and abs(mix[b] - 0.5) < 1e-6


def test_read_history_and_members_skip_bad_lines(tmp_path):
    import archive
    import selfplay

    base = tmp_path / "archive"
    archive.init(base)
    with open(base / "manifest.jsonl", "w") as f:
        f.write('{"id": "g000", "role": "main", "parent": null}\n')
        f.write("{broken\n")
        f.write('{"id": 42}\n')
    with open(base / "history.jsonl", "w") as f:
        f.write('{"gen": 0}\n{nope\n[1,2]\n')
    assert [m["id"] for m in archive.members(base)] == ["g000"]
    assert selfplay.read_history(base) == [{"gen": 0}]


def test_collect_attaches_behavior_logps():
    import torch

    import model
    import algorithm

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    records = [
        {"window": torch.zeros(_C, _S, _S).tolist(), "action": "e"},
        {"window": torch.zeros(_C, _S, _S).tolist(), "action": "stay"},
    ]
    batch = algorithm.collect(policy, records, [1.0, -1.0])
    assert len(batch[0]) == 5
    live, _ = algorithm.masked_log_probs(policy, batch)
    assert all(abs(a - b) < 1e-6 for a, b in zip([i[4] for i in batch], live.tolist()))


def test_new_policy_roundtrip_and_lr_default():
    import torch

    import model
    import algorithm

    torch.manual_seed(0)
    policy = algorithm.new_policy()
    assert isinstance(policy, model.CNNPolicy)
    w = algorithm.policy_weights(policy)
    assert algorithm.new_policy(w).value.weight.shape == policy.value.weight.shape
    assert algorithm.make_optimizer(policy).param_groups[0]["lr"] == 1e-3


def test_train_epoch_no_nan_on_singleton_tail():
    import torch

    import model
    import algorithm

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    opt = algorithm.make_optimizer(policy, lr=1e-3)
    batch = _train_batch(tuple([float(i % 7 - 3) for i in range(65)]))
    stats = algorithm.train_epoch(policy, opt, batch, minibatch=64)
    assert stats["steps"] == 5  # adaptive floor: max(16, 65 // 4)
    for key in ("loss", "pg_loss", "v_loss", "entropy", "kl"):
        assert stats[key] == stats[key], key  # no NaN
    for p in policy.parameters():
        assert torch.isfinite(p).all()


def test_outcome_of_mapping():
    import archive

    assert archive.outcome_of(3, 1) == 1.0
    assert archive.outcome_of(1, 1) == 0.5
    assert archive.outcome_of(0, 2) == 0.0


def test_config_plumbs_gamma_and_workers():
    import selfplay

    cfg = selfplay.parse_args(["--gamma", "0.99", "--workers", "3"])
    assert cfg["gamma"] == 0.99 and cfg["workers"] == 3
    assert selfplay.default_config()["gamma"] == 0.97
    assert selfplay.default_config()["workers"] == 8


def test_game_timeouts_raised_and_retry_flagged():
    import game_if

    cfg = game_if.GameConfig(map="m", turns=10)
    assert cfg.turntime_ms == 5000 and cfg.loadtime_ms == 15000
    assert game_if.GameConfig(map="m", turns=1).timeout == 600


def test_snapshot_window_matches_direct():
    import torch

    import features

    ants = FakeAnts()
    ants._mine = [(4, 4), (0, 0), (9, 9)]
    view = features.snapshot(ants)
    for loc in ants.my_ants():
        assert torch.equal(
            features.local_window(ants, loc),
            features.local_window(ants, loc, view=view),
        )


def test_masked_logits_batch_matches_serial():
    import torch

    import features
    import model

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    ants = FakeAnts()
    windows = torch.stack(
        [features.local_window(ants, loc) for loc in [(4, 4), (0, 0), (9, 9)]]
    )
    blockeds = [frozenset(), frozenset({"n"}), frozenset({"n", "e", "s", "w"})]
    batched = model.masked_logits_batch(policy, windows, blockeds)
    assert batched.shape == (3, 5)
    for i, loc in enumerate([(4, 4), (0, 0), (9, 9)]):
        single = model.masked_logits(
            policy, features.local_window(ants, loc), blockeds[i]
        )
        # allclose, not equal: batched GEMM accumulates in a different
        # order, so the last ulp may differ. Same math, same decisions.
        assert torch.allclose(batched[i], single, atol=1e-6)


def test_batch_stay_fallback_when_nothing_legal():
    import torch

    import features
    import model

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    ants = FakeAnts()
    windows = torch.stack([features.local_window(ants, (4, 4))])
    logits = model.masked_logits_batch(policy, windows, [frozenset(features.ACTIONS)])
    assert model.act_greedy_batch(logits) == ["stay"]
    assert model.sample_batch(logits, 1.0) == ["stay"]


def test_batch_act_shapes_and_greedy_agreement():
    import torch

    import features
    import model

    torch.manual_seed(1)
    policy = model.CNNPolicy()
    ants = FakeAnts()
    windows = torch.stack(
        [features.local_window(ants, loc) for loc in [(4, 4), (0, 0)]]
    )
    logits = model.masked_logits_batch(policy, windows, [frozenset(), frozenset()])
    assert model.act_greedy_batch(logits) == [
        model.act_greedy(policy, windows[0]),
        model.act_greedy(policy, windows[1]),
    ]
    assert len(model.sample_batch(logits, 1.0)) == 2


def test_zero_game_counts_do_not_crash_pools(tmp_path):
    import archive
    import evaluate
    import train

    base = tmp_path / "archive"
    w = {"a": [1.0]}
    champ = archive.save_checkpoint(base, w, role="main", parent=None)
    archive.set_champion(base, champ)
    cfg = {"train_games": 0, "eval_games": 0, "workers": 8, "maps": [], "turns": 1,
           "lr": 1e-3, "epochs": 1, "temperature": 0.0, "seed": 0,
           "clip": 0.2, "vf_coef": 0.5, "entropy_beta": 0.01,
           "max_norm": 1.0, "minibatch": 64}
    cid, cw, stats, _opt = train.train_generation(cfg, base, champ, w)
    assert stats["rows"] == 0
    ev = evaluate.evaluate(cfg, base, cid, cw, champ, w)
    assert ev["games"] == 0 and ev["win_rate"] == 0.0


def test_main_pointer_roundtrip(tmp_path):
    import archive

    base = tmp_path / "archive"
    assert archive.get_main(base) is None
    archive.set_main(base, "g007")
    assert archive.get_main(base) == "g007"


def test_optimizer_state_roundtrip():
    import torch

    import algorithm

    pol = algorithm.new_policy({})
    opt = algorithm.make_optimizer(pol)
    loss = pol(torch.randn(1, _C, _S, _S)).sum()
    opt.zero_grad()
    loss.backward()
    opt.step()
    assert opt.state_dict()["state"]  # non-empty after a step.
    blob = algorithm.serialize_opt(opt)
    import json

    json.dumps(blob)  # must survive the archive as JSON.
    pol2 = algorithm.new_policy({})
    opt2 = algorithm.make_optimizer(pol2)
    algorithm.load_opt_state(opt2, blob)
    s1 = opt.state_dict()["state"]
    s2 = opt2.state_dict()["state"]
    assert set(s2) == set(s1)
    k = next(iter(s1))
    assert torch.equal(s1[k]["exp_avg"], s2[k]["exp_avg"])


def test_main_lineage_chains_parents(tmp_path, monkeypatch):
    import archive
    import selfplay

    captured: dict = {}
    _mocked_generation(monkeypatch, captured)
    base = tmp_path / "archive"
    cfg = _exploiter_cfg()
    # two challenger gens (gen 0, 1 — exploiter hits at gen 2).
    # run_generation appends its own history line per gen.
    selfplay.run_generation(cfg, base, commit=False)
    rep = selfplay.run_generation(cfg, base, commit=False)
    assert rep["exploiter"] is False
    roles = {m["id"]: m for m in archive.members(base)}
    second = roles[rep["challenger"]]
    first = [m for m in roles.values()
             if m.get("role") == "challenger"
             and m["id"] != rep["challenger"]][0]
    assert second["parent"] == first["id"]
    assert archive.get_main(base) == rep["challenger"]


def test_bot_env_is_single_threaded():
    import game_if

    env = game_if._bot_env(game_if.GameConfig(map="m", turns=1, temperature=0.5))
    assert env["OMP_NUM_THREADS"] == "1"
    assert env["MKL_NUM_THREADS"] == "1"
    assert env["OPENBLAS_NUM_THREADS"] == "1"
    assert env["AA_TEMPERATURE"] == "0.5"
    assert env["AA_RECORD_DIR"] == "records"


def _count_params(policy) -> int:
    return sum(t.numel() for t in policy.parameters())


def test_deep_arch_shapes_and_value_zero_init():
    import torch

    import model

    torch.manual_seed(0)
    policy = model.CNNPolicy(arch="deep")
    assert policy(torch.zeros(2, _C, _S, _S)).shape == (2, 5)
    assert torch.equal(
        policy.values(torch.zeros(2, _C, _S, _S)), torch.zeros(2)
    )


def test_deep_arch_stays_in_param_budget():
    import model

    base = _count_params(model.CNNPolicy(arch="base"))
    deep = _count_params(model.CNNPolicy(arch="deep"))
    assert base == 12102  # +1 channel: own_sight widens conv1/vconv1
    assert 9000 < deep < 14000  # same order, no budget blowout


def test_deep_arch_sees_full_window_where_base_cannot():
    import torch

    import model

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
            return (
                (policy.trunk(north) - policy.trunk(south)).abs().sum().item()
            )

    # Ones-weights: deterministic. Base sees far food only as pooled
    # smear (weak N-vs-S separation); deep's full-window field keeps
    # the direction signal ~5000x stronger.
    assert separation("deep") > 1000 * separation("base")


def test_infer_arch_from_weights():
    import model

    assert model.infer_arch(model.state_dict_to_lists(model.CNNPolicy())) == "base"
    assert (
        model.infer_arch(
            model.state_dict_to_lists(model.CNNPolicy(arch="deep"))
        )
        == "deep"
    )


def test_new_policy_arch_passthrough_and_inference():
    import algorithm
    import model

    deep_w = model.state_dict_to_lists(model.CNNPolicy(arch="deep"))
    assert algorithm.new_policy(deep_w).arch == "deep"  # inferred
    assert algorithm.new_policy(None, arch="deep").arch == "deep"


def test_config_default_arch_and_cli_override():
    import selfplay

    assert selfplay.default_config()["arch"] == "base"
    assert selfplay.parse_args(["--arch", "deep"])["arch"] == "deep"


def test_bot_loads_deep_weights(tmp_path):
    import json

    import AlphaAnt
    import model

    alt = tmp_path / "deep.json"
    alt.write_text(
        json.dumps(
            model.state_dict_to_lists(model.CNNPolicy(arch="deep"))
        )
    )
    bot = AlphaAnt.AlphaAntBot(weights_path=str(alt))
    assert bot.policy.arch == "deep"


def test_default_maps_exist_and_turns_cover_endgames():
    import os

    import mapgen
    import selfplay

    cfg = selfplay.default_config()
    assert sorted(cfg["maps"] + cfg["held_maps"]) == selfplay.default_map_pool()
    assert len(cfg["maps"]) >= 100  # the full upstream 2p pool + generated
    for m in cfg["maps"]:
        assert os.path.exists(m), m
        assert mapgen.is_playable_2p(m), m
    assert cfg["turns"] >= 250  # pro median is 229; 150 covered 21%


def _parse_grid(lines: list[str]) -> tuple[int, int, list[str]]:
    rows = cols = 0
    grid: list[str] = []
    for line in lines:
        if line.startswith("rows "):
            rows = int(line.split()[1])
        elif line.startswith("cols "):
            cols = int(line.split()[1])
        elif line.startswith("m "):
            grid.append(line[2:])
    return rows, cols, grid


def test_mapgen_deterministic_and_valid():
    import mapgen

    assert mapgen.generate(3) == mapgen.generate(3)
    for seed in range(6):
        lines = mapgen.generate(seed)
        rows, cols, grid = _parse_grid(lines)
        assert len(grid) == rows and all(len(r) == cols for r in grid)
        flat = "".join(grid)
        assert set(flat) <= set(".%*AB")
        assert flat.count("A") == 1 and flat.count("B") == 1


def test_mapgen_symmetric_and_connected():
    import mapgen

    for seed in range(6):
        rows, cols, grid = _parse_grid(mapgen.generate(seed))
        swap = {"A": "B", "B": "A", ".": ".", "%": "%", "*": "*"}
        for r in range(rows):
            for c in range(cols):
                assert swap[grid[r][c]] == grid[rows - 1 - r][cols - 1 - c]
        land = [[cell != "%" for cell in row] for row in grid]
        start = next(
            (r, c)
            for r in range(rows)
            for c in range(cols)
            if grid[r][c] == "A"
        )
        assert mapgen._connected(land, start)


def test_pool_split_disjoint_and_deterministic():
    import selfplay

    full = selfplay.default_map_pool()
    train, held = selfplay.split_pool(full)
    assert len(train) + len(held) == len(full)
    assert not set(train) & set(held)
    assert sorted(train + held) == full
    assert len(held) >= 8  # real held-out set, not a token
    assert selfplay.split_pool(full) == (train, held)


def test_custom_maps_resplit_for_unseen_evals():
    import selfplay

    maps = [f"m{i}.map" for i in range(30)]
    cfg = selfplay.parse_args(["--maps"] + maps)
    assert sorted(cfg["maps"] + cfg["held_maps"]) == sorted(maps)
    assert not set(cfg["maps"]) & set(cfg["held_maps"])
    assert len(cfg["held_maps"]) == 3  # every 13th of 30


def test_eval_uses_held_maps_only(tmp_path, monkeypatch):
    import archive
    import evaluate
    import game_if

    base = tmp_path / "archive"
    w = {"a": [1.0]}
    champ = archive.save_checkpoint(base, w, role="main", parent=None)
    seen = []

    class FakeGame:
        pass

    def fake_play(root, python, wa, wb, gcfg, outdir, **kwargs):
        seen.append(gcfg.map)
        (outdir / "logs").mkdir(parents=True, exist_ok=True)
        (outdir / "logs" / "0.replay").write_text(
            '{"game_length": 10, "score": [1, 0], "replaydata": {}}'
        )
        return {"game": {"game_length": 10, "score": [1, 0], "replaydata": {}},
                "records_a": [], "records_b": []}

    monkeypatch.setattr(game_if, "play", fake_play)
    cfg = {"eval_games": 4, "maps": ["train.map"], "held_maps": ["h1.map", "h2.map"],
           "turns": 5, "temperature": 0.0, "seed": 0}
    evaluate.evaluate(cfg, base, "chal", w, champ, w)
    assert seen == ["h1.map", "h2.map", "h1.map", "h2.map"]


def test_eval_falls_back_to_train_maps_without_held_pool(tmp_path, monkeypatch):
    import evaluate
    import game_if

    base = tmp_path / "archive"
    w = {"a": [1.0]}
    seen = []

    def fake_play(root, python, wa, wb, gcfg, outdir, **kwargs):
        seen.append(gcfg.map)
        (outdir / "logs").mkdir(parents=True, exist_ok=True)
        (outdir / "logs" / "0.replay").write_text(
            '{"game_length": 10, "score": [1, 1], "replaydata": {}}'
        )
        return {"game": {"game_length": 10, "score": [1, 1],
                            "replaydata": {}},
                "records_a": [], "records_b": []}

    monkeypatch.setattr(game_if, "play", fake_play)
    # one-map curriculum: split leaves held empty, evals run the map.
    cfg = {"eval_games": 2, "maps": ["only.map"], "held_maps": [],
           "turns": 5, "temperature": 0.0, "seed": 0, "workers": 1}
    evaluate.evaluate(cfg, base, "chal", w, "champ", w)
    assert seen == ["only.map", "only.map"]


def test_eval_reports_score_margins(tmp_path, monkeypatch):
    import archive
    import evaluate
    import game_if

    base = tmp_path / "archive"
    w = {"a": [1.0]}
    champ = archive.save_checkpoint(base, w, role="main", parent=None)
    scores = iter([(3, 1), (1, 1)])

    def fake_play(root, python, wa, wb, gcfg, outdir, **kwargs):
        sa, sb = next(scores)
        (outdir / "logs").mkdir(parents=True, exist_ok=True)
        (outdir / "logs" / "0.replay").write_text(
            '{"game_length": 10, "score": [%d, %d], "replaydata": {}}' % (sa, sb)
        )
        return {"game": {"game_length": 10, "score": [sa, sb], "replaydata": {}},
                "records_a": [], "records_b": []}

    monkeypatch.setattr(game_if, "play", fake_play)
    cfg = {"eval_games": 2, "maps": ["m.map"], "turns": 5,
           "temperature": 0.0, "seed": 0, "workers": 1}
    ev = evaluate.evaluate(cfg, base, "chal", w, champ, w)
    # Slot 0: chal is A (3-1 -> +2). Slot 1: chal is B (1-1 -> 0).
    # Single worker keeps duel order deterministic.
    assert ev["margins"] == [2, 0]
    assert ev["mean_margin"] == 1.0


def test_stage_side_names_main_file(tmp_path):
    import game_if

    side = game_if.stage_side(tmp_path / "out", {}, "side_a", "g004")
    assert (side / "g004.py").exists()
    assert not (side / game_if.MAIN_BOT).exists()
    assert (side / "ants.py").exists()  # support modules ride along
    assert (side / "weights.json").exists()


def test_play_stages_checkpoint_names(tmp_path, monkeypatch):
    import game_if

    seen = {}

    def fake_run(cmd, root, env, timeout):
        seen["bots"] = [c for c in cmd if c.endswith(".py") and "playgame" not in c]
        logdir = tmp_path / "g0" / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        (logdir / "0.replay").write_text(
            '{"game_length": 10, "score": [1, 1], "replaydata": {}}'
        )

    monkeypatch.setattr(game_if, "_run_once", fake_run)
    w = {"a": [1.0]}
    out = game_if.play(
        tmp_path, "python", w, w,
        game_if.GameConfig(map="m.map", turns=10),
        tmp_path / "g0", name_a="g004", name_b="g000",
    )
    assert out["game"]["game_length"] == 10
    assert seen["bots"][0].endswith("side_a/g004.py")
    assert seen["bots"][1].endswith("side_b/g000.py")


def test_eval_map_offset_rotates_held_pool(tmp_path, monkeypatch):
    import archive
    import evaluate
    import game_if

    base = tmp_path / "archive"
    w = {"a": [1.0]}
    champ = archive.save_checkpoint(base, w, role="main", parent=None)
    seen = []

    def fake_play(root, python, wa, wb, gcfg, outdir, **kwargs):
        seen.append(gcfg.map)
        (outdir / "logs").mkdir(parents=True, exist_ok=True)
        (outdir / "logs" / "0.replay").write_text(
            '{"game_length": 10, "score": [1, 1], "replaydata": {}}'
        )
        return {"game": {"game_length": 10, "score": [1, 1], "replaydata": {}},
                "records_a": [], "records_b": []}

    monkeypatch.setattr(game_if, "play", fake_play)
    cfg = {"eval_games": 2, "maps": ["t.map"],
           "held_maps": ["h1.map", "h2.map", "h3.map"],
           "turns": 5, "temperature": 0.0, "seed": 0, "workers": 1}
    evaluate.evaluate(cfg, base, "chal", w, champ, w, map_offset=1)
    assert seen == ["h2.map", "h3.map"]


def test_eval_turns_overrides_training_turns(tmp_path, monkeypatch):
    import evaluate
    import game_if

    base = tmp_path / "archive"
    w = {"a": [1.0]}
    seen = []

    def fake_play(root, python, wa, wb, gcfg, outdir, **kwargs):
        seen.append(gcfg.turns)
        (outdir / "logs").mkdir(parents=True, exist_ok=True)
        (outdir / "logs" / "0.replay").write_text(
            '{"game_length": 10, "score": [1, 1], "replaydata": {}}'
        )
        return {"game": {"game_length": 10, "score": [1, 1],
                            "replaydata": {}},
                "records_a": [], "records_b": []}

    monkeypatch.setattr(game_if, "play", fake_play)
    cfg = {"eval_games": 2, "maps": ["t.map"], "turns": 60,
           "eval_turns": 250, "temperature": 0.0, "seed": 0,
           "workers": 1}
    evaluate.evaluate(cfg, base, "chal", w, "champ", w)
    assert seen == [250, 250]
    # unset falls back to training turns.
    seen.clear()
    cfg["eval_turns"] = None
    evaluate.evaluate(cfg, base, "chal", w, "champ", w)
    assert seen == [60, 60]


def test_drills_sweep_pool_round_robin(tmp_path):
    import archive

    base = tmp_path / "archive"
    pool = [f"m{i}.map" for i in range(6)]
    seen = []
    for gen in range(3):
        seen += archive.next_drill_maps(base, pool, 2, gen)
    assert sorted(seen) == pool  # every board trains within the cycle
    assert archive.next_drill_maps(base, pool, 2, 3) == pool[:2]


def test_drills_prioritize_untrained_boards(tmp_path):
    import archive

    base = tmp_path / "archive"
    pool = [f"m{i}.map" for i in range(6)]
    archive.next_drill_maps(base, pool[:4], 4, 0)
    # New boards join later: they train before any repeat.
    assert archive.next_drill_maps(base, pool, 2, 1) == pool[4:]


def test_pg_abs_bounds_pg_magnitude():
    import torch

    import algorithm

    torch.manual_seed(41)
    pol = algorithm.new_policy({})
    opt = algorithm.make_optimizer(pol)
    recs = [{"window": torch.rand(_C, _S, _S), "action": "n",
             "legal": [True] * 5} for _ in range(64)]
    batch = algorithm.collect(pol, recs, [1.0] * 64)
    stats = algorithm.train_epoch(pol, opt, batch)
    assert stats["pg_abs"] >= abs(stats["pg_loss"])


def test_train_generation_reserves_drills(tmp_path, monkeypatch):
    import archive
    import train

    base = tmp_path / "archive"
    w = {"a": [1.0]}
    champ = archive.save_checkpoint(base, w, role="main", parent=None)
    archive.set_champion(base, champ)
    cfg = {"train_games": 0, "eval_games": 0, "workers": 8,
           "maps": ["a.map", "b.map"], "turns": 1,
           "lr": 1e-3, "epochs": 1, "temperature": 0.0, "seed": 0,
           "clip": 0.2, "vf_coef": 0.5, "entropy_beta": 0.01,
           "max_norm": 1.0, "minibatch": 64}
    seen = {}
    real = archive.next_drill_maps

    def spy(b, pool, n, gen_num):
        seen["args"] = (pool, n, gen_num)
        return real(b, pool, n, gen_num)

    monkeypatch.setattr(archive, "next_drill_maps", spy)
    train.train_generation(cfg, base, champ, w)
    assert seen["args"][0] == ["a.map", "b.map"]
    assert seen["args"][1] == 0


def _mocked_generation(monkeypatch, captured):
    import copy

    import archive
    import evaluate
    import train

    def fake_train(cfg, base, champ_id, champ_w, role="challenger",
                   parent=None, opt_state=None, **kwargs):
        captured["role"] = role
        captured["kl_anchor_beta"] = kwargs.get("kl_anchor_beta")
        captured["student"] = kwargs.get("student")
        captured["init_w"] = copy.deepcopy(champ_w)
        cid = archive.save_checkpoint(base, copy.deepcopy(champ_w), role, champ_id if parent is None else parent)
        return cid, copy.deepcopy(champ_w), {"rows": 0}, None

    def fake_eval(cfg, base, chal_id, chal_w, champ_id, champ_w,
                  map_offset=0):
        return {"wins": 0, "draws": 0, "games": 0, "win_rate": 0.0,
                "margins": [], "mean_margin": 0.0}

    monkeypatch.setattr(train, "train_generation", fake_train)
    monkeypatch.setattr(evaluate, "evaluate", fake_eval)
    monkeypatch.setattr(evaluate, "should_promote", lambda *a: False)


def _exploiter_cfg():
    return {"seed": 0, "arch": "base", "gamma": 0.97,
            "promote_threshold": 0.5, "kl_anchor_beta": 0.01}


def test_critic_warm_starts_baseline_and_persists(tmp_path, monkeypatch):
    import archive
    import json
    import selfplay

    captured = {}
    _mocked_generation(monkeypatch, captured)
    base = tmp_path / "archive"
    cfg = _exploiter_cfg()
    w = selfplay._random_weights(cfg["seed"], cfg.get("arch", "base"))
    champ = archive.save_checkpoint(base, w, role="main", parent=None)
    archive.set_champion(base, champ)
    critic = {"value.weight": [[7.0] * 128], "value.bias": [7.0],
              "vconv1.weight": [[[[7.0]]]]}
    (base / "critic.json").write_text(json.dumps(critic))
    selfplay.run_generation(cfg, base, commit=False)
    init = captured["init_w"]
    # actor restarts from champion...
    assert init["conv1.weight"] == w["conv1.weight"]
    # ...but the whole baseline warm-starts (trunk AND head) ...
    assert init["value.bias"] == [7.0]
    assert init["vconv1.weight"] == [[[[7.0]]]]
    # ...and the trained critic is banked for the next generation.
    saved = json.loads((base / "critic.json").read_text())
    assert saved["value.bias"] == [7.0]
    assert "vconv1.weight" in saved
    assert all(k.startswith(("value.", "vconv")) for k in saved)


def test_init_weights_seed_gen_zero_champion(tmp_path, monkeypatch):
    import archive
    import json
    import selfplay

    captured = {}
    _mocked_generation(monkeypatch, captured)
    base = tmp_path / "archive"
    cfg = _exploiter_cfg()
    w = selfplay._random_weights(7, "base")
    init = tmp_path / "bc.json"
    init.write_text(json.dumps(w))
    cfg["init_weights"] = str(init)
    selfplay.run_generation(cfg, base, commit=False)
    champ = archive.get_champion(base)
    assert archive.load_checkpoint(base, champ) == w
    # fresh archives only: existing champions are untouched
    w2 = selfplay._random_weights(8, "base")
    init.write_text(json.dumps(w2))
    selfplay.run_generation(cfg, base, commit=False)
    assert archive.load_checkpoint(base, archive.get_champion(base)) != w2


@pytest.mark.parametrize("hist_len,expected", [
    (0, False), (1, False), (2, True), (3, False), (4, False), (5, True),
])
def test_exploiter_triggers_every_third_generation(tmp_path, monkeypatch, hist_len, expected):
    import archive
    import selfplay

    captured: dict = {}
    _mocked_generation(monkeypatch, captured)
    base = tmp_path / "archive"
    cfg = _exploiter_cfg()
    archive.init(base)
    champ = archive.save_checkpoint(base, {"w": [1.0]}, "main", None)
    archive.set_champion(base, champ)
    for i in range(hist_len):
        selfplay.append_history(base, {"gen": i})
    assert len(selfplay.read_history(base)) % 3 == 2 or not expected
    assert (hist_len % 3 == 2) is expected
    rep = selfplay.run_generation(cfg, base, commit=False)
    assert rep["exploiter"] is expected
    assert captured["role"] == ("exploiter" if expected else "challenger")
    assert archive.members(base)[-1]["role"] == captured["role"]
    assert archive.read_status(base)["exploiter"] is expected


def test_sample_opponents_trains_at_the_frontier(tmp_path):
    import archive

    base = tmp_path / "archive"
    for _ in range(21):
        archive.save_checkpoint(base, {"w": [1.0]}, "main", None)
    archive.set_champion(base, "g020")
    # g020 beats the ancients: rates exist so PFSP doesn't degenerate
    # to self-play; the window then decides eligibility.
    for old in ("g000", "g001", "g002"):
        archive.record_result(base, "g020", old, 3, 0)
    got = archive.sample_opponents(
        base, "g020", 50, seed=1, window=15,
        include=("g019",))
    recent = {f"g{i:03d}" for i in range(6, 21)} | {"g020", "g019"}
    assert set(got) <= recent
    assert "g000" not in got  # ancient weaklings never train


def test_run_generation_passes_main_as_student(tmp_path, monkeypatch):
    import archive
    import selfplay

    captured: dict = {}
    _mocked_generation(monkeypatch, captured)
    base = tmp_path / "archive"
    cfg = _exploiter_cfg()
    selfplay.run_generation(cfg, base, commit=False)  # gen 0 challenger
    selfplay.run_generation(cfg, base, commit=False)  # gen 1 challenger
    # gen 0 bootstraps the main from the champ; gen 1 trains from it,
    # so the student is the main (g001), not the champ (g000).
    # (get_main has since advanced to g002; the capture is what matters.)
    assert captured["student"] == "g001"


def test_exploiters_run_unanchored(tmp_path, monkeypatch):
    import archive
    import selfplay

    captured: dict = {}
    _mocked_generation(monkeypatch, captured)
    base = tmp_path / "archive"
    cfg = _exploiter_cfg()
    assert cfg["kl_anchor_beta"] != 0.0  # anchor live in this cfg
    selfplay.run_generation(cfg, base, commit=False)  # gen 0: challenger
    assert captured["kl_anchor_beta"] == cfg["kl_anchor_beta"]
    selfplay.append_history(base, {"gen": 97})  # history len 2: exploiter
    selfplay.run_generation(cfg, base, commit=False)
    assert captured["kl_anchor_beta"] == 0.0  # scouts drift free


def test_exploiter_starts_from_fresh_weights(tmp_path, monkeypatch):
    import archive
    import selfplay

    captured: dict = {}
    _mocked_generation(monkeypatch, captured)
    base = tmp_path / "archive"
    cfg = _exploiter_cfg()
    selfplay.run_generation(cfg, base, commit=False)
    selfplay.append_history(base, {"gen": 97})  # history len 2 -> exploiter
    champ_id = archive.get_champion(base)
    champ_w = archive.load_checkpoint(base, champ_id)
    rep = selfplay.run_generation(cfg, base, commit=False)
    assert rep["exploiter"] is True
    # supervised base (g000), not a champ copy — unless the archive
    # started random, in which case g000 IS random and equality holds.
    assert captured["init_w"] != champ_w or champ_w == archive.load_checkpoint(base, "g000")


def test_exploiter_base_alternates_founding_and_champ(tmp_path):
    import archive
    import selfplay

    base = tmp_path / "archive"
    archive.save_checkpoint(base, {"w": [1.0]}, "main", None)
    champ = {"w": [2.0]}
    # k-th exploiter sits at gen_index 3k+2: even k -> founding
    # weights (fresh competent eyes), odd k -> champion clone
    # (current competence + disruptive objectives).
    assert selfplay._exploiter_base(base, {"seed": 0}, 2, champ) == {"w": [1.0]}
    assert selfplay._exploiter_base(base, {"seed": 0}, 5, champ) == champ
    assert selfplay._exploiter_base(base, {"seed": 0}, 8, champ) == {"w": [1.0]}


def test_non_exploiter_copies_champion(tmp_path, monkeypatch):
    import archive
    import selfplay

    captured: dict = {}
    _mocked_generation(monkeypatch, captured)
    base = tmp_path / "archive"
    cfg = _exploiter_cfg()
    rep = selfplay.run_generation(cfg, base, commit=False)
    assert rep["exploiter"] is False
    champ_id = archive.get_champion(base)
    champ_w = archive.load_checkpoint(base, champ_id)
    assert captured["init_w"] == champ_w
    assert captured["role"] == "challenger"

