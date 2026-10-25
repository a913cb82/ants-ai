"""AlphaStarZero v0: per-ant linear policy, stdlib only.

TDD seed: features + model must be importable without numpy/torch,
decide a legal move in microseconds, and never suggest water.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphastarzero"))
sys.path.insert(0, str(ROOT / "ml"))


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


def test_outcome_win_adds_terminal_bonus_discounted():
    import rewards

    game = _game(score=[10, 4])
    records = [{"turn": 9, "loc": [1, 1], "dest": [1, 1], "action": "stay"}]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] == rewards.WIN * (rewards.GAMMA ** (10 - 9))


def test_outcome_loss_and_draw():
    import rewards

    assert rewards.outcome(_game(score=[3, 9]), 0) == rewards.LOSS
    assert rewards.outcome(_game(score=[5, 5]), 0) == rewards.DRAW


def test_bot_records_turn_rows_when_env_set(tmp_path, monkeypatch):
    import MyBot

    monkeypatch.setenv("AZ0_RECORD_DIR", str(tmp_path))

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

    bot = MyBot.AlphaZeroBot()
    bot.do_setup(StubAnts())
    bot.do_turn(StubAnts())
    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    row = json.loads(files[0].read_text().strip().splitlines()[-1])
    assert row["turn"] == 1
    assert row["action"] in ("n", "e", "s", "w", "stay")
    assert "dest" in row and "cues" in row
    assert len(row["window"]) == 6 and len(row["window"][0]) == 9


def test_bot_samples_with_temperature(tmp_path, monkeypatch):
    import torch

    import MyBot

    monkeypatch.setenv("AZ0_RECORD_DIR", str(tmp_path))
    monkeypatch.setenv("AZ0_TEMPERATURE", "3.0")

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
    bot = MyBot.AlphaZeroBot()
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
    import MyBot

    torch.manual_seed(123)
    alt = tmp_path / "alt.json"
    alt.write_text(json.dumps(model.state_dict_to_lists(model.CNNPolicy())))
    bot = MyBot.AlphaZeroBot(weights_path=str(alt))
    assert bot.policy(torch.zeros(1, 6, 9, 9)).shape == (1, 5)


def test_food_credit_by_spawnradius_proximity():
    import rewards

    game = _game()
    game["replaydata"]["food"] = [[5, 5, 1, 3, 0]]  # spawnradius2=1: adjacent counts
    records = [
        {"turn": 3, "loc": [5, 3], "dest": [5, 4], "action": "e"},
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
        {"turn": 3, "loc": [5, 3], "dest": [5, 4], "action": "e"},
        {"turn": 3, "loc": [5, 7], "dest": [5, 6], "action": "w"},
        {"turn": 3, "loc": [0, 0], "dest": [0, 0], "action": "stay"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets == [rewards.FOOD / 2, rewards.FOOD / 2, 0.0]


def test_dense_reward_discounts_back_along_ant_path():
    import rewards

    game = _game()
    game["replaydata"]["ants"] = [[4, 4, 0, 99, 0, "ss"]]
    game["replaydata"]["food"] = [[6, 5, 1, 2, 0]]  # adjacent to (6,4) at turn 2
    records = [
        {"turn": 1, "loc": [4, 4], "dest": [5, 4], "action": "s"},
        {"turn": 2, "loc": [5, 4], "dest": [6, 4], "action": "s"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[1] == rewards.FOOD
    assert rets[0] == rewards.FOOD * rewards.GAMMA


def _cnn_window(water_dests=(), radius=4):
    import torch

    from features import CHANNELS

    w = torch.zeros(6, 2 * radius + 1, 2 * radius + 1)
    w[CHANNELS.index("own_ant")][radius][radius] = 1.0
    for action in water_dests:
        dr, dc = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1), "stay": (0, 0)}[action]
        w[CHANNELS.index("water")][radius + dr][radius + dc] = 1.0
    return w


def test_cnn_forward_shape():
    import torch

    import model

    policy = model.CNNPolicy()
    assert policy(torch.zeros(1, 6, 9, 9)).shape == (1, 5)


def test_cnn_radius_agnostic():
    import torch

    import model

    policy = model.CNNPolicy()
    assert policy(torch.zeros(1, 6, 5, 5)).shape == (1, 5)


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
    x = torch.zeros(1, 6, 9, 9)
    assert torch.equal(policy(x), policy2(x))


def test_weights_file_loads_into_cnn():
    import json

    import torch

    import model

    wpath = ROOT / "bots" / "alphastarzero" / "weights.json"
    policy = model.CNNPolicy()
    policy.load_state_dict(model.lists_to_state_dict(json.loads(wpath.read_text())))
    assert policy(torch.zeros(1, 6, 9, 9)).shape == (1, 5)


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


def _train_batch(returns=(1.0, 2.0, 3.0)):
    import torch

    windows = torch.zeros(len(returns), 6, 9, 9)
    windows[:, 1, 4, 4] = 1.0
    return [(windows[i], i % 5, float(r)) for i, r in enumerate(returns)]


def test_reinforce_raises_chosen_logprob():
    import torch

    import model
    import algorithm

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    batch = _train_batch(returns=(1.0, 0.0))
    before = algorithm.logprob(policy, batch[0][0], batch[0][1])
    algorithm.reinforce_step(policy, batch, lr=1e-2)
    assert algorithm.logprob(policy, batch[0][0], batch[0][1]) > before


def test_advantages_center_on_batch_mean():
    import algorithm

    assert algorithm.advantages([1.0, 2.0, 3.0]) == [-1.0, 0.0, 1.0]


def test_train_step_noop_on_equal_returns():
    import torch

    import model
    import algorithm

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    before = [p.detach().clone() for p in policy.parameters()]
    stats = algorithm.reinforce_step(policy, _train_batch((2.0, 2.0, 2.0)), lr=1e-2)
    assert stats["loss"] == 0.0
    for b, p in zip(before, policy.parameters(), strict=True):
        assert torch.equal(b, p)
