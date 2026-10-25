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
    assert len(row["window"]) == 6 and len(row["window"][0]) == 9
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

    wpath = ROOT / "bots" / "alphaant" / "weights.json"
    policy = model.CNNPolicy()
    # Old champions predate the value head: strict=False keeps their
    # policy weights and leaves the value head zero-initialized.
    policy.load_state_dict(
        model.lists_to_state_dict(json.loads(wpath.read_text())), strict=False
    )
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


def _train_batch(returns=(1.0, 2.0, 3.0), logps=None):
    import torch

    windows = torch.zeros(len(returns), 6, 9, 9)
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
        policy.values(torch.zeros(2, 6, 9, 9)), torch.zeros(2)
    )
    opt = algorithm.make_optimizer(policy, lr=1e-2)
    windows = torch.zeros(4, 6, 9, 9)
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
    w = torch.zeros(6, 9, 9)
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
        {"window": torch.zeros(6, 9, 9).tolist(), "action": "e"},
        {
            "window": torch.zeros(6, 9, 9).tolist(),
            "action": "stay",
            "legal": [False, False, False, False, True],
        },
    ]
    batch = algorithm.to_batch(records, [1.0, -1.0], [0.0, 0.0])
    assert len(batch) == 2
    assert batch[0][0].shape == torch.Size([6, 9, 9])
    assert batch[0][1] == 1 and batch[1][1] == 4
    assert batch[0][2] == 1.0 and batch[1][2] == -1.0
    assert batch[0][3] == [True] * 5
    assert batch[1][3] == [False, False, False, False, True]


def test_promote_rule_needs_wilson_and_nash():
    import evaluate

    assert evaluate.should_promote(7, 0, 10, 0.5, 0.4)
    assert not evaluate.should_promote(4, 0, 10, 0.5, 0.4)
    assert not evaluate.should_promote(10, 0, 10, 0.2, 0.4)


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
        {"window": torch.zeros(6, 9, 9).tolist(), "action": "e"},
        {"window": torch.zeros(6, 9, 9).tolist(), "action": "stay"},
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
    cid, cw, stats = train.train_generation(cfg, base, champ, w)
    assert stats["rows"] == 0
    ev = evaluate.evaluate(cfg, base, cid, cw, champ, w)
    assert ev["games"] == 0 and ev["win_rate"] == 0.0


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
    assert policy(torch.zeros(2, 6, 9, 9)).shape == (2, 5)
    assert torch.equal(
        policy.values(torch.zeros(2, 6, 9, 9)), torch.zeros(2)
    )


def test_deep_arch_stays_in_param_budget():
    import model

    base = _count_params(model.CNNPolicy(arch="base"))
    deep = _count_params(model.CNNPolicy(arch="deep"))
    assert base == 6294
    assert 4000 < deep < 9000  # same order, no budget blowout


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
        north = torch.zeros(1, 6, 9, 9)
        north[0, 5, 0, 4] = 1.0  # food 4 north
        south = torch.zeros(1, 6, 9, 9)
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


def _mocked_generation(monkeypatch, captured):
    import copy

    import archive
    import evaluate
    import train

    def fake_train(cfg, base, champ_id, champ_w, role="challenger"):
        captured["role"] = role
        captured["init_w"] = copy.deepcopy(champ_w)
        cid = archive.save_checkpoint(base, copy.deepcopy(champ_w), role, champ_id)
        return cid, copy.deepcopy(champ_w), {"rows": 0}

    def fake_eval(cfg, base, chal_id, chal_w, champ_id, champ_w,
                  map_offset=0):
        return {"wins": 0, "draws": 0, "games": 0, "win_rate": 0.0,
                "margins": [], "mean_margin": 0.0}

    monkeypatch.setattr(train, "train_generation", fake_train)
    monkeypatch.setattr(evaluate, "evaluate", fake_eval)
    monkeypatch.setattr(evaluate, "should_promote", lambda *a: False)


def _exploiter_cfg():
    return {"seed": 0, "arch": "base", "gamma": 0.97,
            "promote_threshold": 0.5}


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
    assert captured["init_w"] != champ_w  # fresh random init, not a copy


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

