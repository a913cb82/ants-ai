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


def test_window_shows_far_teammate_with_sight_flag():
    import features

    ants = FakeAnts()
    ants.viewradius2 = 8
    ants._mine = [(4, 4), (7, 4)]  # second ant at offset (+3,0), d2=9
    w = features.local_window(ants, (4, 4), radius=3)
    own = w[features.CHANNELS.index("own_ant")]
    sight = w[features.CHANNELS.index("own_sight")]
    assert own[3][3] == 1.0  # self still marked
    assert own[6][3] == 0.0  # F1: B-tier teammate zero-filled ...
    assert sight[6][3] == 0.0  # ... mask intact


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


def _hill_game(score):
    game = _game()
    game["score"] = score
    game["length"] = 10
    # surviving enemy hill: approach credit without raze credit.
    game["replaydata"]["hills"] = [[9, 9, 1, 999]]
    return game


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

    game = _game(score=[3, 1])  # win: kills pay, terminal lands too
    game["replaydata"]["ants"] = [[5, 5, 1, 3, 1, "--"]]  # enemy dies turn 3
    records = [
        {"turn": 3, "loc": [5, 4], "dest": [5, 4], "action": "stay"},
        {"turn": 3, "loc": [0, 0], "dest": [0, 0], "action": "stay"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] == rewards.KILL + rewards.WIN
    assert rets[1] == rewards.WIN


def test_one_for_one_trade_nets_negative():
    import rewards

    # Asymmetric death: killing pays +1, dying costs -2. A 1-for-1
    # trade nets -1, so mutual annihilation is no longer free — the
    # learner must preserve material to profit from combat. Pinned
    # kills pay on every finish now; only the march subsidy stays
    # gated. Pinned on a win here; the loss case pins in
    # test_main_kills_paid_on_loss.
    game = _game(score=[2, 0])  # win
    game["replaydata"]["ants"] = [
        [5, 5, 1, 3, 1, "--"],  # enemy dies turn 3
        [5, 4, 1, 3, 0, "s-"],  # own ant dies turn 3
    ]
    records = [
        # death tile is start walked by all orders: (5,4) + s = (6,4).
        {"turn": 3, "loc": [5, 4], "dest": [6, 4], "action": "s"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] == rewards.KILL + rewards.DEATH + rewards.WIN


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
    rets = rewards.compute_returns(game, 0, records)
    before = math.sqrt(dist2((5, 5), (5, 9), 10, 10))
    after = math.sqrt(dist2((5, 6), (5, 9), 10, 10))
    assert rets[0] == rewards.WIN + rewards.HILL_APPROACH * (before - after)


def test_hill_approach_ignores_opening_and_staying():
    import rewards

    game = _game(score=[4, 0])  # win: mechanism active, terminal explicit
    game["replaydata"]["hills"] = [[5, 9, 1, 99]]
    game["replaydata"]["ants"] = [[5, 5, 1, 5, 0, "ew-"]]
    records = [
        {"turn": 1, "loc": [5, 5], "dest": [5, 6], "action": "e"},
        {"turn": 2, "loc": [5, 6], "dest": [5, 5], "action": "w"},
        {"turn": 3, "loc": [5, 5], "dest": [5, 5], "action": "stay"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] > rewards.WIN  # closed one tile: HA + terminal
    assert rets[1] == rewards.WIN  # opened it back: terminal only
    assert rets[2] == rewards.WIN  # stayed: terminal only


def test_hill_approach_stays_same_turn_only():
    import rewards

    game = _game(score=[4, 0])  # win: mechanism active, terminal explicit
    game["replaydata"]["hills"] = [[5, 9, 1, 99]]
    game["replaydata"]["ants"] = [[5, 5, 1, 5, 0, "eee"]]
    records = [
        {"turn": 1, "loc": [5, 5], "dest": [5, 4], "action": "w"},
        {"turn": 2, "loc": [5, 4], "dest": [5, 5], "action": "e"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] == rewards.WIN  # opened: terminal only, no walk-back
    # closed one full tile (d 5 -> 4): same-turn credit + terminal.
    assert rets[1] == rewards.WIN + rewards.HILL_APPROACH * 1.0


def test_hill_approach_targets_first_hill_only():
    import rewards

    # Shared convention concentrates force: closing to the second hill
    # while opening to the first pays nothing, even though min-nearest
    # would have paid. All ants see the same list, so all march the
    # same hill.
    game = _game(score=[4, 0])  # win: mechanism active; gate off
    game["replaydata"]["hills"] = [[5, 0, 1, 99], [5, 9, 1, 99]]
    game["replaydata"]["ants"] = [[5, 4, 1, 5, 0, "e"]]
    records = [
        {"turn": 1, "loc": [5, 4], "dest": [5, 5], "action": "e"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    # closes to second, opens to first: no approach, terminal only.
    assert rets[0] == rewards.WIN


def test_hill_raze_scales_by_distance():
    import rewards

    game = _game()
    game["replaydata"]["hills"] = [[5, 5, 1, 4]]  # enemy hill razed turn 4
    records = [
        {"turn": 4, "loc": [5, 4], "dest": [5, 5], "action": "s"},  # d=0
        {"turn": 4, "loc": [5, 7], "dest": [5, 8], "action": "s"},  # d=3
    ]
    rets = rewards.compute_returns(game, 0, records)
    # distance-only: on the tile earns the full +10, d=3 earns ~8.13.
    assert rets[0] == rewards.HILL_RAZE
    assert rets[1] == pytest.approx(rewards.HILL_RAZE * 0.81283, abs=1e-3)


def test_hill_raze_fades_by_twenty_tiles():
    import rewards

    game = _game()
    game["replaydata"]["map"] = {"rows": 30, "cols": 30}
    game["replaydata"]["hills"] = [[5, 5, 1, 4]]  # enemy hill razed turn 4
    records = [
        {"turn": 4, "loc": [5, 4], "dest": [5, 5], "action": "s"},  # d=0
        {"turn": 4, "loc": [5, 14], "dest": [5, 15], "action": "s"},  # d=10
        {"turn": 4, "loc": [5, 19], "dest": [5, 20], "action": "s"},  # d=15
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] == rewards.HILL_RAZE
    assert rets[1] == pytest.approx(rewards.HILL_RAZE / 10)  # 10 out: +-1
    assert rets[2] < rewards.HILL_RAZE / 100  # tail fading to nothing


def test_hill_raze_reaches_far_ants():
    import rewards

    game = _game()
    game["replaydata"]["hills"] = [[8, 8, 1, 4]]  # enemy hill razed turn 4
    records = [
        {"turn": 4, "loc": [8, 7], "dest": [8, 8], "action": "e"},
        {"turn": 4, "loc": [2, 2], "dest": [2, 2], "action": "stay"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] > rets[1] > 0.0  # nearer earns more, far still paid


def test_hill_loss_scales_by_distance():
    import rewards

    game = _game()
    game["replaydata"]["hills"] = [[5, 5, 0, 4]]  # own hill lost turn 4
    records = [
        {"turn": 4, "loc": [5, 7], "dest": [5, 8], "action": "stay"},  # d=3
        {"turn": 4, "loc": [5, 4], "dest": [5, 5], "action": "stay"},  # d=0
    ]
    rets = rewards.compute_returns(game, 0, records)
    # nearer defender eats more blame: full -10 on the tile, -10*exp(-0.5)
    # at d=3. (No ant is inside combat range of a lost hill — else the
    # razer would be dead — so blame starts just outside kill distance.)
    assert rets[1] == rewards.HILL_LOST
    assert rets[0] == pytest.approx(rewards.HILL_LOST * 0.81283, abs=1e-3)


def test_hill_equidistant_ants_split_evenly():
    import rewards

    game = _game()
    game["replaydata"]["hills"] = [[5, 5, 0, 4]]  # own hill lost turn 4
    records = [
        {"turn": 4, "loc": [5, 5], "dest": [5, 6], "action": "s"},  # d=1
        {"turn": 4, "loc": [5, 5], "dest": [6, 5], "action": "s"},  # d=1
    ]
    rets = rewards.compute_returns(game, 0, records)
    # headcount-agnostic: same distance earns the same each, no halving.
    assert rets == [
        pytest.approx(rewards.HILL_LOST * 0.97724, abs=1e-3),
        pytest.approx(rewards.HILL_LOST * 0.97724, abs=1e-3),
    ]


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
    assert features.decode_window(row["window"]).shape[0] == len(features.CHANNELS)
    assert features.decode_window(row["window"]).shape[1] == 2 * features.DEFAULT_RADIUS + 1
    assert len(row["legal"]) == 5


def test_bot_samples_with_temperature(tmp_path, monkeypatch):
    import AlphaAnt
    import torch

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

    import AlphaAnt
    import model
    import torch

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
        dr, dc = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1), "stay": (0, 0)}[
            action
        ]
        w[CHANNELS.index("water")][radius + dr][radius + dc] = 1.0
    return w


def test_cnn_forward_shape():
    import model
    import torch

    policy = model.CNNPolicy()
    assert policy(torch.zeros(1, _C, _S, _S)).shape == (1, 5)


def _probs(policy, w):
    import torch

    policy.eval()
    with torch.no_grad():
        return torch.softmax(policy(w), dim=1)


def test_forward_is_rotation_equivariant():
    import model
    import torch

    torch.manual_seed(3)
    policy = model.CNNPolicy()
    w = torch.rand(4, _C, _S, _S)
    base = _probs(policy, w)
    for k in (1, 2, 3):
        got = _probs(policy, torch.rot90(w, k, (2, 3)))
        back = got[:, list(model.UNROT[k])]
        assert torch.allclose(base, back, atol=1e-5), k


def test_forward_is_flip_equivariant():
    import model
    import torch

    torch.manual_seed(5)
    policy = model.CNNPolicy()
    w = torch.rand(4, _C, _S, _S)
    base = _probs(policy, w)
    got = _probs(policy, torch.flip(w, (3,)))
    assert torch.allclose(base, got[:, list(model.UNFLIP)], atol=1e-5)


def test_truncated_wide_net_matches_narrow():
    import model
    import torch

    torch.manual_seed(4)
    wide = model.CNNPolicy(channels=12)
    wide.eval()
    narrow = model.CNNPolicy(channels=7)
    narrow.load_state_dict(
        model.pad_in_channels(dict(wide.state_dict()), narrow), strict=True
    )
    narrow.eval()
    with torch.no_grad():
        x7 = torch.rand(2, 7, 9, 9)
        x0 = torch.zeros(2, 5, 9, 9)
        assert torch.equal(narrow(x7), wide(torch.cat([x7, x0], dim=1)))
        assert torch.equal(narrow.values(x7), wide.values(torch.cat([x7, x0], dim=1)))


def test_padded_old_weights_give_identical_outputs():
    import algorithm
    import model
    import torch

    torch.manual_seed(23)
    old = model.CNNPolicy(channels=7)
    old.eval()
    blob = algorithm.policy_weights(old)
    new = algorithm.new_policy(blob)
    new.eval()
    with torch.no_grad():
        w7 = torch.rand(3, 7, _S, _S)
        pad = torch.zeros(3, _C - 7, _S, _S)
        assert torch.equal(old(w7), new(torch.cat([w7, pad], dim=1)))
        assert torch.equal(old.values(w7), new.values(torch.cat([w7, pad], dim=1)))


def test_opt_state_drops_reshaped_params():
    import algorithm
    import model
    import torch

    torch.manual_seed(31)
    old = model.CNNPolicy(channels=7)
    opt = algorithm.make_optimizer(old)
    old(torch.rand(2, 7, 9, 9)).sum().backward()
    opt.step()  # populates momentum buffers
    blob = algorithm.serialize_opt(opt)
    new = model.CNNPolicy()  # 9 channels now
    opt2 = algorithm.make_optimizer(new)
    algorithm.load_opt_state(opt2, blob)  # must not raise ...
    new(torch.rand(2, _C, 15, 15)).sum().backward()
    opt2.step()  # ... nor crash here (the round-18 failure).
    cur = opt2.state_dict()["state"]
    params = [p for g in opt2.param_groups for p in g["params"]]
    for i, p in enumerate(params):
        if i in cur:
            for v in cur[i].values():
                if torch.is_tensor(v) and v.shape != torch.Size(()):
                    assert v.shape == p.shape


def test_values_are_rotation_invariant():
    import model
    import torch

    torch.manual_seed(7)
    policy = model.CNNPolicy()
    policy.eval()
    with torch.no_grad():
        w = torch.rand(4, _C, _S, _S)
        base = policy.values(w)
        for k in (1, 2, 3):
            assert torch.allclose(
                base, policy.values(torch.rot90(w, k, (2, 3))), atol=1e-5
            )


def test_cnn_radius_agnostic():
    import model
    import torch

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
    import model
    import torch

    torch.manual_seed(7)
    policy = model.CNNPolicy()
    w = _cnn_window()
    seen = {model.sample(policy, w, temperature=3.0) for _ in range(200)}
    assert seen <= {"n", "e", "s", "w", "stay"}
    assert len(seen) >= 2


def test_cnn_state_dict_json_roundtrip(tmp_path):
    import json

    import model
    import torch

    policy = model.CNNPolicy()
    path = tmp_path / "w.json"
    path.write_text(json.dumps(model.state_dict_to_lists(policy)))
    policy2 = model.CNNPolicy()
    policy2.load_state_dict(model.lists_to_state_dict(json.loads(path.read_text())))
    x = torch.zeros(1, _C, _S, _S)
    assert torch.equal(policy(x), policy2(x))


def test_weights_file_loads_into_cnn():
    import json

    import model
    import torch

    wpath = ROOT / "bots" / "alphaant" / "weights.json"
    policy = model.CNNPolicy()
    # Old champions predate the value head (strict=False keeps policy
    # weights, value head stays zero-initialized) and the widening
    # (pad_in_channels: new input channels load zeroed, old behavior
    # preserved exactly, lineage continues).
    policy.load_state_dict(
        model.pad_in_channels(
            model.lists_to_state_dict(json.loads(wpath.read_text())), policy
        ),
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
    import algorithm
    import model
    import torch

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    opt = algorithm.make_optimizer(policy, lr=1e-2)
    batch = _train_batch(returns=(1.0, 0.0))
    before = algorithm.masked_log_probs(policy, batch)[0][0].item()
    algorithm.train_epoch(policy, opt, batch)
    assert algorithm.masked_log_probs(policy, batch)[0][0].item() > before


def test_ppo_value_head_starts_at_zero_and_learns():
    import algorithm
    import model
    import torch

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    assert torch.equal(policy.values(torch.zeros(2, _C, _S, _S)), torch.zeros(2))
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
    import algorithm
    import model
    import torch

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
    import algorithm
    import model

    policy = model.CNNPolicy()
    opt = algorithm.make_optimizer(policy)
    stats = algorithm.train_epoch(policy, opt, [])
    assert stats["loss"] == 0.0 and stats["mean_return"] == 0.0 and stats["steps"] == 0


def test_train_epoch_ignores_masked_logits():
    import algorithm
    import model
    import torch

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


def test_to_batch_converts_rows_and_returns():
    import algorithm
    import torch

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
        "w",
        "n",
        "e",
        "s",
        "stay",
    ]
    mask = [True, False, True, False, True]
    assert [[mask[i] for i in algorithm.ROT_MASK]] == [[False, True, False, True, True]]
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


def test_legal_mask_blocks_food_tiles():

    import model

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
        [
            json.loads((ROOT / "bots" / "alphaant" / "weights.json").read_text()),
            json.loads((ROOT / "bots" / "alphaant" / "weights.json").read_text()),
        ],
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
    assert out["records"][0] and out["records"][1]
    r = rewards.compute_returns(out["game"], 0, out["records"][0])
    assert len(r) == len(out["records"][0])


def test_cli_defaults_match_default_config():
    import selfplay

    cfg = selfplay.parse_args([])
    assert cfg == selfplay.default_config()


def test_cli_overrides():
    import selfplay

    cfg = selfplay.parse_args(
        ["--ticks", "7", "--turns", "20", "--maps", "tools/maps/example/tutorial1.map"]
    )
    assert cfg["ticks"] == 7
    assert cfg["turns"] == 20
    # No separate exam: custom maps are used directly, nothing held out.
    assert cfg["maps"] == ["tools/maps/example/tutorial1.map"]


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


def test_games_index_roundtrip_and_filter(tmp_path):
    import archive

    base = tmp_path / "archive"
    archive.log_game(base, ["main", "main"], [3, 1], "games/g001/t0/logs/0.replay")
    archive.log_game(base, ["main", "main"], [2, 2], "games/g001/e0/logs/0.replay")
    all_games = archive.list_games(base)
    assert len(all_games) == 2
    assert [r["replay"] for r in all_games] == [
        "games/g001/e0/logs/0.replay",
        "games/g001/t0/logs/0.replay",
    ]


def test_log_game_records_map_name(tmp_path):
    import archive

    base = tmp_path / "archive"
    archive.log_game(
        base, ["main", "main"], [3, 1], "games/g001/t0/logs/0.replay", map="rung2c_gap.map"
    )
    archive.log_game(base, ["main", "main"], [2, 2], "games/g001/e0/logs/0.replay")
    rows = {r["replay"]: r for r in archive.list_games(base)}
    assert rows["games/g001/t0/logs/0.replay"]["map"] == "rung2c_gap.map"
    assert rows["games/g001/e0/logs/0.replay"]["map"] is None


def test_snapshot_empty_and_populated(tmp_path):
    import archive
    import dashboard

    base = tmp_path / "archive"
    snap = dashboard.snapshot(base)
    assert snap["games"] == [] and snap["game_total"] == 0
    assert snap["behavior"] == [
        {
            "id": "main",
            "food": None,
            "kills": None,
            "army_pct": None,
            "length": None,
            "n": 0,
            "spark": {"food": [], "kills": [], "army": [], "length": []},
        }
    ]
    assert snap["alerts"] == [{"level": "ok", "msg": "all clear", "tick": 0}]
    archive.save_state(base, {"tick": 1, "next_tick": 1, "micro": 0})
    archive.log_game(
        base,
        ["main", "main"], [3, 1],
        "games/g000/e0/logs/0.replay",
        game="gid-0",
        tick=0,
        food=[2, 1],
        kills=[1, 0],
        army=[5, 4],
        length=120,
    )
    snap = dashboard.snapshot(base)
    assert snap["game_total"] == 1
    assert snap["games"][0]["replay"].endswith("0.replay")
    assert snap["h0"]["games"] == 1


def test_snapshot_games_carry_dual_time(tmp_path):
    import archive
    import dashboard

    base = tmp_path / "archive"
    archive.log_game(
        base, ["main", "main"], [3, 1], "games/g0/logs/0.replay", game="g#0", tick=7
    )
    archive.log_game(
        base, ["main", "main"], [0, 5], "games/g1/logs/0.replay", game="g#1", tick=9
    )
    snap = dashboard.snapshot(base)
    assert [g["tick"] for g in snap["games"]] == [9, 7]  # newest first
    assert all(
        set(g)
        == {"tick", "learner", "map", "seats", "scores", "stats",
            "length", "trace_miss", "result", "replay"}
        for g in snap["games"]
    )


def test_batch_norm_keeps_event_magnitude_over_noise():
    import algorithm
    import model
    import torch

    policy = model.CNNPolicy()
    n = 64
    rets = [0.1] * (n - 1) + [5.0]
    windows = torch.zeros(n, _C, _S, _S)
    values = policy.values(windows)
    all_ret = torch.tensor(rets)
    adv = algorithm._advantages(
        all_ret, values, all_ret.mean(), all_ret.std(unbiased=False)
    )
    noise, event = adv[:-1].abs().max().item(), abs(adv[-1].item())
    # one real event must outweigh the loudest noise row by an order
    # of magnitude; per-minibatch standardization would make them O(1).
    assert event > 10 * noise


def test_snapshot_h0_tracks_scheduler_state(tmp_path):
    import archive
    import dashboard

    base = tmp_path / "archive"
    archive.save_state(base, {"tick": 5, "next_tick": 5, "micro": 3})
    archive.log_update(
        base,
        {
            "tick": 0,
            "rows": 8,
            "mean_return": 1.0,
            "explained_var": 0.5,
            "loss": 0.1,
            "entropy": 0.9,
            "kl": 0.01,
            "clipfrac": 0.1,
            "pg_loss": -0.2,
            "v_loss": 0.3,
        },
    )
    snap = dashboard.snapshot(base)
    h0 = snap["h0"]
    assert (h0["tick"], h0["micro"], h0["updates"]) == (5, 3, 1)


def test_replay_page_guards_traversal(tmp_path):
    import dashboard

    base = tmp_path / "archive"
    (base / "games").mkdir(parents=True)
    (base / "games" / "0.replay").write_text("{}")
    assert dashboard.replay_page(base, "games/0.replay") is not None
    assert dashboard.replay_page(base, "games/r.json") is None  # not a replay
    assert dashboard.replay_page(base, "../../etc/passwd") is None
    assert dashboard.replay_page(base, "missing.json") is None


def test_snapshot_retires_status_and_members(tmp_path):
    import dashboard

    base = tmp_path / "archive"
    snap = dashboard.snapshot(base)
    assert "status" not in snap and "members" not in snap
    assert "standings" not in snap and "learner" not in snap["h0"]
    assert set(snap["h0"]) == {
        "tick",
        "games",
        "updates",
        "micro",
        "games_per_h",
        "secs_since_game",
        "last_result",
        "last_length",
        "decisive",
    }


def test_dashboard_http_api(tmp_path):
    import json
    import threading
    import urllib.request

    import archive
    import dashboard

    base = tmp_path / "archive"
    archive.save_state(base, {"tick": 0, "next_tick": 0, "micro": 0})
    srv = dashboard.make_handler(base)
    import http.server

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), srv)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        root = f"http://127.0.0.1:{httpd.server_address[1]}"
        snap = json.load(urllib.request.urlopen(root + "/api/snapshot", timeout=5))
        assert snap["h0"]["tick"] == 0 and snap["game_total"] == 0
        assert "history" not in snap and "status" not in snap
        archive.log_game(base, ["main", "main"], [1, 1], "games/g/e/logs/0.replay")
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
        f.write('{"seats":["main"]}\n')  # missing keys
        f.write(
            '{"seats":["main","main"],"scores":[null,1],"replay":"r"}\n'
        )
        f.write(
            '{"seats":["main","main"],"scores":[2,1],"replay":"r"}\n'
        )
    rows = archive.list_games(base)
    assert len(rows) == 1 and rows[0]["scores"] == [2, 1]


def test_snapshot_survives_poisoned_index(tmp_path):
    import archive
    import dashboard

    base = tmp_path / "archive"
    archive.init(base)
    with open(base / "games.jsonl", "w") as f:
        f.write('{"a":"main","b":"main"}\n')
    snap = dashboard.snapshot(base)
    assert snap["game_total"] == 0


def test_collect_attaches_behavior_logps():
    import algorithm
    import model
    import torch

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
    import algorithm
    import model
    import torch

    torch.manual_seed(0)
    policy = algorithm.new_policy()
    assert isinstance(policy, model.CNNPolicy)
    w = algorithm.policy_weights(policy)
    assert algorithm.new_policy(w).value.weight.shape == policy.value.weight.shape
    assert algorithm.make_optimizer(policy).param_groups[0]["lr"] == 1e-3


def test_train_epoch_no_nan_on_singleton_tail():
    import algorithm
    import model
    import torch

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


def test_config_plumbs_gamma_and_workers():
    import selfplay

    cfg = selfplay.parse_args(["--gamma", "0.99", "--seed", "7"])
    assert cfg["gamma"] == 0.99 and cfg["seed"] == 7
    assert selfplay.default_config()["gamma"] == 0.97
    assert selfplay.default_config()["seed"] == 0


def test_game_timeouts_raised_and_retry_flagged():
    import game_if

    cfg = game_if.GameConfig(map="m", turns=10)
    assert cfg.turntime_ms == 5000 and cfg.loadtime_ms == 15000
    assert game_if.GameConfig(map="m", turns=1).timeout == 600


def test_snapshot_window_matches_direct():
    import features
    import torch

    ants = FakeAnts()
    ants._mine = [(4, 4), (0, 0), (9, 9)]
    view = features.snapshot(ants)
    for loc in ants.my_ants():
        assert torch.equal(
            features.local_window(ants, loc),
            features.local_window(ants, loc, view=view),
        )


def test_masked_logits_batch_matches_serial():
    import features
    import model
    import torch

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
    import features
    import model
    import torch

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    ants = FakeAnts()
    windows = torch.stack([features.local_window(ants, (4, 4))])
    logits = model.masked_logits_batch(policy, windows, [frozenset(features.ACTIONS)])
    assert model.act_greedy_batch(logits) == ["stay"]
    assert model.sample_batch(logits, 1.0) == ["stay"]


def test_batch_act_shapes_and_greedy_agreement():
    import features
    import model
    import torch

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


def test_optimizer_state_roundtrip():
    import algorithm
    import torch

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
    import model
    import torch

    torch.manual_seed(0)
    policy = model.CNNPolicy(arch="deep")
    assert policy(torch.zeros(2, _C, _S, _S)).shape == (2, 5)
    assert torch.equal(policy.values(torch.zeros(2, _C, _S, _S)), torch.zeros(2))


def test_deep_arch_stays_in_param_budget():
    import model

    base = _count_params(model.CNNPolicy(arch="base"))
    deep = _count_params(model.CNNPolicy(arch="deep"))
    assert base == 12966  # +3 channels: force_ratio/enemy_dist/stall widen conv1/vconv1
    assert 9000 < deep < 14000  # same order, no budget blowout


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


def test_infer_arch_from_weights():
    import model

    assert model.infer_arch(model.state_dict_to_lists(model.CNNPolicy())) == "base"
    assert (
        model.infer_arch(model.state_dict_to_lists(model.CNNPolicy(arch="deep")))
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
    alt.write_text(json.dumps(model.state_dict_to_lists(model.CNNPolicy(arch="deep"))))
    bot = AlphaAnt.AlphaAntBot(weights_path=str(alt))
    assert bot.policy.arch == "deep"


def test_default_pool_covers_any_player_count():
    import game_if
    import mapgen
    import selfplay

    pool = selfplay.default_map_pool()
    counts = {}
    for m in pool:
        assert mapgen.is_playable(m), m
        n = game_if.map_player_count(m)
        counts[n] = counts.get(n, 0) + 1
    assert 2 in counts and 4 in counts  # small and large tables play
    assert max(counts) >= 8  # the big multi_hill/cell_maze tables join
    import glob as _glob

    assert sorted(pool) == sorted(
        f
        for d in ("cell_maze", "maze", "multi_hill_maze", "random_walk")
        for f in _glob.glob(f"tools/maps/{d}/*.map")
    )  # every map in the four upstream dirs, none odder


def test_is_playable_accepts_n_player_maps(tmp_path):
    import mapgen

    def tiny(players, hills):
        n = max(8, players)
        grid = ["m " + "." * 8 for _ in range(n)]
        for i, h in enumerate(hills):
            grid[i] = "m " + h + "." * 7
        p = tmp_path / f"p{players}.map"
        p.write_text(f"rows {n}\ncols 8\nplayers {players}\n" + "\n".join(grid) + "\n")
        return str(p)

    assert mapgen.is_playable(tiny(2, "01"))
    assert mapgen.is_playable(tiny(3, "012"))
    assert mapgen.is_playable(tiny(4, "0123"))
    assert mapgen.is_playable(tiny(5, "01234"))  # any table size plays
    assert mapgen.is_playable(tiny(10, "0123456789"))  # up to 10 seats
    assert not mapgen.is_playable(tiny(1, "0"))  # solo is not a game
    assert not mapgen.is_playable(tiny(3, "01"))  # seat 2 has no hill


def test_default_maps_exist_and_turns_cover_endgames():
    import os

    import mapgen
    import selfplay

    cfg = selfplay.default_config()
    assert sorted(cfg["maps"]) == selfplay.default_map_pool()
    assert len(cfg["maps"]) >= 200  # the mixed 2/3/4p upstream pool
    for m in cfg["maps"]:
        assert os.path.exists(m), m
        assert mapgen.is_playable(m), m
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
            (r, c) for r in range(rows) for c in range(cols) if grid[r][c] == "A"
        )
        assert mapgen._connected(land, start)


def test_custom_maps_used_directly_without_split():
    import selfplay

    maps = [f"m{i}.map" for i in range(30)]
    cfg = selfplay.parse_args(["--maps"] + maps)
    # No separate exam under the continuous league: the scheduler plays
    # one pool, nothing held out.
    assert cfg["maps"] == maps


def _tmp_2p_map(tmp_path, name="e.map"):
    p = tmp_path / name
    p.write_text("rows 16\ncols 24\nplayers 2\n" + "m " + "." * 24 + "\n")
    return str(p)


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
        tmp_path,
        "python",
        [w, w],
        game_if.GameConfig(map="m.map", turns=10),
        tmp_path / "g0",
        names=["g004", "g000"],
    )
    assert out["game"]["game_length"] == 10
    assert seen["bots"][0].endswith("side_0/g004.py")
    assert seen["bots"][1].endswith("side_1/g000.py")


def test_pg_abs_bounds_pg_magnitude():
    import algorithm
    import torch

    torch.manual_seed(41)
    pol = algorithm.new_policy({})
    opt = algorithm.make_optimizer(pol)
    recs = [
        {"window": torch.rand(_C, _S, _S), "action": "n", "legal": [True] * 5}
        for _ in range(64)
    ]
    batch = algorithm.collect(pol, recs, [1.0] * 64)
    stats = algorithm.train_epoch(pol, opt, batch)
    assert stats["pg_abs"] >= abs(stats["pg_loss"])


def test_gated_shaping_zeroes_march_on_loss():
    import rewards

    game = _hill_game([0, 1])  # loss
    records = [{"turn": 1, "loc": [5, 5], "dest": [6, 6], "action": "s"}]
    rets = rewards.compute_returns(game, 0, records)
    # marching paid nothing: only the terminal loss remains.
    assert rets[0] == rewards.LOSS


def test_gated_shaping_zeroes_march_on_draw():
    import rewards

    game = _hill_game([0, 0])  # draw
    records = [{"turn": 1, "loc": [5, 5], "dest": [6, 6], "action": "s"}]
    rets = rewards.compute_returns(game, 0, records)
    # draws keep no march subsidy either: turtling must pay nothing.
    assert rets[0] == 0.0


def test_wins_pay_march_and_kills():
    import math

    import rewards

    game = _hill_game([1, 0])  # win
    records = [{"turn": 1, "loc": [5, 5], "dest": [6, 6], "action": "s"}]
    rets = rewards.compute_returns(game, 0, records)
    closed = math.sqrt(32) - math.sqrt(18)
    assert rets[0] == rewards.WIN + rewards.HILL_APPROACH * closed


def test_third_seat_gets_own_outcome():
    import rewards

    game = _game()
    game["score"] = [0, 0, 3]  # seat 2 wins alone
    game["replaydata"]["ants"] = [[5, 5, 1, 3, 1, "--"]]
    records = [
        {"turn": 3, "loc": [4, 5], "dest": [5, 5], "action": "s"},
    ]
    assert rewards.compute_returns(game, 2, records)[0] == rewards.WIN
    assert rewards.compute_returns(game, 0, records)[0] == rewards.LOSS


def test_main_kills_paid_on_loss():
    import rewards

    game = _game()
    game["score"] = [0, 1]  # loss
    game["replaydata"]["ants"] = [[5, 5, 1, 3, 1, "--"]]
    records = [
        {"turn": 3, "loc": [5, 4], "dest": [5, 4], "action": "stay"},
    ]
    main = rewards.compute_returns(game, 0, records)
    assert main[0] == rewards.KILL + rewards.LOSS  # kills always pay now


def test_death_still_hurts_on_loss():
    import rewards

    game = _game()
    game["score"] = [0, 1]  # loss
    game["replaydata"]["ants"] = [[4, 4, 1, 2, 0, "s"]]
    records = [
        {"turn": 2, "loc": [4, 4], "dest": [5, 4], "action": "s"},
    ]
    rets = rewards.compute_returns(game, 0, records)
    assert rets[0] == rewards.DEATH + rewards.LOSS


# --- idea 3: draw-penalty training games (turtle tax) ---


def test_map_player_count_reads_header(tmp_path):
    import game_if

    p = tmp_path / "m.map"
    p.write_text("rows 16\ncols 24\nplayers 3\nm " + "." * 24 + "\n")
    assert game_if.map_player_count(p) == 3


@pytest.mark.slow
def test_3p_game_end_to_end_fixed_seats(tmp_path):
    """A real 3-player engine game through the N-seat path: 3 bots, 3 scores,
    per-seat records, student seat 0 priced without crashing."""
    import game_if
    import model
    import rewards

    sys.path.insert(0, str(ROOT / "tools" / "mapgen"))
    import gen_mixed

    train, _eval = gen_mixed.fresh_pool(1, 0, tmp_path / "maps", seed=99, jobs=1)
    maps3 = [m for m in train if game_if.map_player_count(m) == 3]
    assert maps3, "seed 99 must draw a 3p map"
    w = model.state_dict_to_lists(model.CNNPolicy())
    out = game_if.play(
        ROOT,
        sys.executable,
        [w, w, w],
        game_if.GameConfig(
            map=maps3[0], turns=2, temperature=0.0, player_seed=1, engine_seed=1
        ),
        tmp_path / "g3",
        names=["s", "c", "x"],
    )
    assert len(out["game"]["score"]) == 3
    assert len(out["records"]) == 3
    rows = out["records"][0]
    rets = rewards.compute_returns(out["game"], 0, rows)
    assert len(rets) == len(rows)


# --- dash-np: native 2/3/4-player dashboard (impl/dash-np) ---
#
# games.jsonl rows are ONE ROW PER SEAT-PAIR: a 4p game logs 6 rows sharing
# (gen, kind, replay, map). The dashboard must render one visual game per
# game, all N seats, N-way outcomes, for train AND eval.


def test_log_game_logs_n_seats_and_scores(tmp_path):
    import archive

    base = tmp_path / "archive"
    archive.log_game(
        base, ["main", "main", "main"], [3, 1, 0],
        "games/g/logs/0.replay", game="gid-3", tick=5,
        food=[2, 1, 0], kills=[1, 0, 0], army=[5, 4, 6], length=120)
    (row,) = archive.list_games(base)
    assert row["seats"] == ["main", "main", "main"]
    assert row["scores"] == [3, 1, 0] and row["tick"] == 5
    assert row["food"] == [2, 1, 0] and row["army"] == [5, 4, 6]


def test_log_game_carries_game_id(tmp_path):
    import archive

    base = tmp_path / "archive"
    archive.log_game(
        base,
        ["main", "main"], [3, 1],
        "games/g001/t0/logs/0.replay",
        game="games/g001/t0#abc",
    )
    rows = archive.list_games(base)
    assert len(rows) == 1 and rows[0]["game"] == "games/g001/t0#abc"


def test_log_game_game_optional_for_old_callers(tmp_path):
    import archive

    base = tmp_path / "archive"
    archive.log_game(base, ["main", "main"], [3, 1], "games/g001/t0/logs/0.replay")
    rows = archive.list_games(base)
    assert len(rows) == 1 and not rows[0].get("game")


def test_rank_of_matches_engine_ties_share_rank():
    import dashboard

    assert dashboard.rank_of([5, 3, 3, 1]) == [0, 1, 1, 3]
    assert dashboard.rank_of([10, 10, 5]) == [0, 0, 2]
    assert dashboard.rank_of([2, 2]) == [0, 0]


def test_train_play_one_tags_pairs_with_one_game_id(tmp_path, monkeypatch):
    import archive
    import game_if
    import train

    base = tmp_path / "archive"
    cfg = {"seed": 0, "turns": 5, "temperature": 0.0, "tick": 7}
    seen_cfg = {}

    def fake_play(*a, **k):
        seen_cfg.update(vars(a[3]))  # GameConfig carries both seeds
        assert isinstance(a[2], list) and len(a[2]) == 2  # one entry per seat
        return _fake_game_out(["main", "main"], [1, 0], a[4])

    monkeypatch.setattr(game_if, "play", fake_play)
    import algorithm
    import rewards

    monkeypatch.setattr(algorithm, "compact_records", lambda rows: [])
    monkeypatch.setattr(rewards, "compute_returns", lambda *a, **k: [0.1])
    train._play_one(cfg, base, {}, _tmp_2p_map(tmp_path))
    assert (seen_cfg["player_seed"], seen_cfg["engine_seed"]) == (7, 1007)
    rows = archive.list_games(base)
    assert len(rows) == 1  # mirror logs one game row
    assert rows[0]["game"].startswith("games/main/tick7#")
    assert rows[0]["tick"] == 7
    gids = {r.get("game") for r in rows}
    assert len(gids) == 1
    (gid,) = gids
    assert gid.startswith("games/main/tick7#")


def _tmp_3p_map(tmp_path, name="e3.map"):
    p = tmp_path / name
    p.write_text("rows 16\ncols 24\nplayers 3\n" + "m " + "." * 24 + "\n")
    return str(p)


def test_play_one_learns_from_every_seat(tmp_path, monkeypatch):
    import game_if
    import train

    base = tmp_path / "archive"
    cfg = {"seed": 0, "turns": 5, "temperature": 0.0, "tick": 7}

    def fake_play(*a, **k):
        assert isinstance(a[2], list) and len(a[2]) == 3  # one entry per seat
        game = {
            "game_length": 10,
            "score": [3, 1, 0],
            "replaydata": {
                "map": {
                    "rows": 10,
                    "cols": 10,
                    "data": [".........." for _ in range(10)],
                },
                "viewradius2": 77,
                "attackradius2": 5,
                "food": [],
                "ants": [
                    [4, 4, 1, 10, 0, "--"],
                    [6, 6, 1, 10, 1, "--"],
                    [5, 5, 1, 3, 2, "--"],
                ],
                "hills": [],
            },
        }
        # Each seat's record traces to its own staying ant, so the join
        # is exact. The owner-2 ant died: kills stay [1, 1, 0].
        recs = [
            [{"turn": 3, "loc": [4, 4], "dest": [4, 4], "action": "stay",
              "window": [[[0.0]]]}],
            [{"turn": 3, "loc": [6, 6], "dest": [6, 6], "action": "stay",
              "window": [[[0.0]]]}],
            [{"turn": 3, "loc": [5, 5], "dest": [5, 5], "action": "stay",
              "window": [[[0.0]]]}],
        ]
        return {"game": game, "records": recs}

    monkeypatch.setattr(game_if, "play", fake_play)
    out = train._play_one(cfg, base, {}, _tmp_3p_map(tmp_path))
    assert len(out["rows"]) == 3  # one decision row per seat
    assert out["rets"][0] > 0 > out["rets"][2]  # winner up, loser down
    (row,) = __import__("archive").list_games(base)
    assert row["seats"] == ["main", "main", "main"]
    assert row["scores"] == [3, 1, 0]
    assert row["food"] == [0, 0, 0] and row["kills"] == [1, 1, 0]


def _fake_game_out(names, scores, outdir):
    (outdir / "logs").mkdir(parents=True, exist_ok=True)
    (outdir / "logs" / "0.replay").write_text(
        json.dumps({"game_length": 10, "score": list(scores), "replaydata": {}})
    )
    return {
        "game": {"game_length": 10, "score": list(scores), "replaydata": {}},
        "records": [[] for _ in names],
    }


def test_cached_panel_shares_one_build_per_poll(tmp_path):
    import archive
    import dashboard

    base = tmp_path / "archive"
    archive.log_game(base, ["main", "main"], [1, 0], "games/g/e0/logs/0.replay", game="g#1")
    first = dashboard.cached_panel(base)
    assert dashboard.cached_panel(base) is first  # no rebuild on repoll
    assert len(first) == 1 and set(first[0]) == {
        "tick", "learner", "map", "seats", "scores", "stats",
        "length", "trace_miss", "result", "replay"}
    assert first[0]["result"] == "win"  # seat-0 perspective
    archive.log_game(base, ["main", "main"], [0, 1], "games/g/e1/logs/0.replay", game="g#2")
    second = dashboard.cached_panel(base)
    assert len(second) == 2  # file change rebuilds
    assert second[0]["result"] == "loss"  # newest first, seat-0 lost


def test_fresh_policy_head_is_small_scale():
    import model
    import torch

    policy = model.CNNPolicy()
    std = float(policy.head.weight.std())
    assert 0.0 < std < 0.03  # near-uniform initial policy, not a bias
    assert torch.equal(policy.head.bias, torch.zeros_like(policy.head.bias))


def test_fresh_trunk_is_orthogonal_gain_sqrt2():
    import model
    import torch

    policy = model.CNNPolicy()
    flat = policy.conv1.weight.reshape(policy.conv1.weight.shape[0], -1)
    gram = flat @ flat.T
    gain2 = 2.0
    assert torch.allclose(
        torch.diag(gram), torch.full_like(torch.diag(gram), gain2), atol=0.2
    )
    off = gram - torch.diag(torch.diag(gram))
    assert off.abs().max() < 0.2


def test_fresh_value_head_zero():
    import model
    import torch

    policy = model.CNNPolicy()
    assert torch.equal(policy.value.weight, torch.zeros_like(policy.value.weight))
    assert torch.equal(policy.value.bias, torch.zeros_like(policy.value.bias))


def test_two_fresh_policies_differ():
    import model
    import torch

    a, b = model.CNNPolicy(), model.CNNPolicy()
    assert any(not torch.equal(p, q) for p, q in zip(a.parameters(), b.parameters()))


def test_ppo_update_reports_clipfrac_and_explained_var():
    import algorithm
    import torch
    import train

    torch.manual_seed(0)
    policy = algorithm.new_policy(None, "base")
    opt = algorithm.make_optimizer(policy, lr=1e-3)
    batch = algorithm.collect(
        policy,
        [
            {"window": torch.zeros(_C, _S, _S).tolist(), "action": "stay"}
            for _ in range(16)
        ],
        [float(i % 3 - 1) for i in range(16)],
    )
    cfg = {
        "epochs": 1,
        "clip": 0.2,
        "vf_coef": 0.5,
        "entropy_beta": 0.01,
        "max_norm": 1.0,
        "minibatch": 64,
    }
    stats = train.ppo_update(policy, opt, batch, cfg)
    assert all(0.0 <= c <= 1.0 for c in stats["clipfrac"])
    assert stats["explained_var"] <= 1.0


def test_run_once_discards_engine_stdout_off_ram(tmp_path, monkeypatch):
    import subprocess
    import sys

    import game_if

    seen = {}
    real = subprocess.run

    def spy(cmd, **kw):
        seen.update(kw)
        assert kw.get("capture_output") is not True  # never buffer stdout in RAM
        assert kw.get("stdout") == subprocess.DEVNULL
        assert kw.get("stderr") == subprocess.PIPE
        return real([sys.executable, "-c", "pass"], cwd=kw.get("cwd"), env=kw.get("env"))

    monkeypatch.setattr(subprocess, "run", spy)
    game_if._run_once([sys.executable, "-c", "print('x' * 100)"], tmp_path, {}, 60)


def test_run_once_failure_reports_stderr_tail(tmp_path):
    import sys

    import game_if

    try:
        game_if._run_once(
            [sys.executable, "-c", "import sys; sys.stderr.write('boom' * 100); sys.exit(3)"],
            tmp_path, {}, 60,
        )
    except RuntimeError as e:
        assert "boom" in str(e)
    else:
        raise AssertionError("failing engine must raise")


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


def _big_game(monkeypatch, tmp_path, n_rows=5000):
    """Stub engine game: n_rows priced rows, returns stay attached."""
    import game_if
    import rewards as _rewards
    import train as _train

    rec = {
        "turn": 2,
        "loc": [1, 1],
        "dest": [1, 1],
        "action": "stay",
        "window": [[[0.0] * 9] * 9] * 10,
    }
    land = ["." * 8 for _ in range(8)]
    game = {
        "score": [1, 2],
        "game_length": 10,
        "replaydata": {
            "map": {"rows": 8, "cols": 8, "data": land},
            "viewradius2": 77,
            "attackradius2": 5,
            "food": [],
            "ants": [[1, 1, 1, 10, 0, "-" * 9], [2, 2, 1, 10, 1, "-" * 9]],
            "hills": [],
        },
    }
    mapp = tmp_path / "m.map"
    mapp.write_text("rows 8\ncols 8\nplayers 2\n" + "m " + "." * 8 + "\n")

    def fake_play(*a, **k):
        return {"game": game, "records": [[dict(rec) for _ in range(n_rows)]] * 2}

    monkeypatch.setattr(game_if, "play", fake_play)
    monkeypatch.setattr(
        _rewards, "compute_returns", lambda g, s, r, sc: [float(i) for i in range(len(r))]
    )
    cfg = {"tick": 4, "turns": 10, "temperature": 1.0, "seed": 7}
    return _train._play_one(cfg, tmp_path, {}, str(mapp))


def test_play_one_caps_rows_per_game(tmp_path, monkeypatch):
    out = _big_game(monkeypatch, tmp_path)
    assert len(out["rows"]) == 4096 and len(out["rets"]) == 4096
    out2 = _big_game(monkeypatch, tmp_path)
    assert list(out2["rets"]) == list(out["rets"])  # seed:tick stable
    assert out["rets"] != [float(i) for i in range(4096)]  # subsampled, not truncated


def test_play_one_keeps_small_games_whole(tmp_path, monkeypatch):
    out = _big_game(monkeypatch, tmp_path, n_rows=100)
    assert len(out["rows"]) == 200 and len(out["rets"]) == 200  # 2 seats x 100


def test_outcome_linear_over_placements():
    import rewards

    assert rewards.outcome(_game(score=[7, 4, 2, 0]), 0) == rewards.WIN
    assert rewards.outcome(_game(score=[7, 4, 2, 0]), 1) == pytest.approx(5 - 10 / 3)
    assert rewards.outcome(_game(score=[7, 4, 2, 0]), 2) == pytest.approx(-(5 - 10 / 3))
    assert rewards.outcome(_game(score=[7, 4, 2, 0]), 3) == rewards.LOSS
    for me in (1, 2):  # tied middle shares the middle value
        assert rewards.outcome(_game(score=[7, 4, 4, 0]), me) == 0.0
    assert rewards.outcome(_game(score=[10, 10, 0, 0]), 0) == rewards.WIN
    assert rewards.outcome(_game(score=[10, 10, 0, 0]), 2) == rewards.LOSS
    assert rewards.outcome(_game(score=[3, 3, 3]), 1) == rewards.DRAW
    assert rewards.outcome(_game(score=[5, 3]), 0) == rewards.WIN  # 2p unchanged
    assert rewards.outcome(_game(score=[5, 3]), 1) == rewards.LOSS


def test_second_place_terminal_graduated_not_snapped():
    import rewards

    game = _game(score=[0, 1, 2, 3])
    records = [{"turn": 3, "loc": [1, 1], "dest": [1, 1], "action": "stay"}]
    assert rewards.compute_returns(game, 2, records)[0] == pytest.approx(5 - 10 / 3)
    assert rewards.compute_returns(game, 1, records)[0] == pytest.approx(-(5 - 10 / 3))


def test_refresh_water_grows_with_vision():
    import importlib.util

    # Explicit path: test_mapgen_java puts tools/ on sys.path, where a
    # generic `import ants` resolves to the ENGINE ants, not the bot's.
    spec = importlib.util.spec_from_file_location(
        "bot_side_ants", ROOT / "bots" / "alphaant" / "ants.py"
    )
    bot_ants = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot_ants)
    import AlphaAnt

    a = bot_ants.Ants()
    a.setup("rows 10\ncols 10\n")
    assert AlphaAnt.refresh_water(a) == set()  # no vision yet: honest empty
    a.update("w 5 5\nf 2 2\na 1 1 0\n")
    assert AlphaAnt.refresh_water(a) == {(5, 5)}  # food stays passable


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


def _trace_game():
    import rewards  # noqa: F401  (keeps the one-diet import idiom)

    game = _game()
    rows = [".........." for _ in range(10)]
    rows[5] = "......%..."
    game["replaydata"]["map"] = {"rows": 10, "cols": 10, "data": rows}
    game["replaydata"]["ants"] = [[5, 5, 1, 6, 0, "----"]]
    game["playerturns"] = [3, 3]
    return game


def test_trace_report_flags_water_breach():
    import rewards

    game = _trace_game()
    recs = [{"turn": 3, "loc": [5, 5], "dest": [5, 6], "action": "e"}]
    miss, problems = rewards.trace_report(game, 0, recs)
    assert miss == 1.0 and len(problems) == 1 and "water" in problems[0]


def test_trace_report_clean_when_matched():
    import rewards

    game = _trace_game()
    recs = [{"turn": 3, "loc": [5, 5], "dest": [5, 5], "action": "stay"}]
    assert rewards.trace_report(game, 0, recs) == (0.0, [])


def test_trace_report_flags_food_breach_and_ghost():
    import rewards

    game = _trace_game()
    game["replaydata"]["food"] = [[5, 4, 2, 5, 1]]
    recs = [{"turn": 3, "loc": [5, 5], "dest": [5, 4], "action": "w"}]
    miss, problems = rewards.trace_report(game, 0, recs)
    assert miss == 1.0 and len(problems) == 1 and "food" in problems[0]
    lonely = [{"turn": 9, "loc": [5, 5], "dest": [5, 4], "action": "w"}]
    miss, problems = rewards.trace_report(game, 0, lonely)
    assert miss == 1.0 and len(problems) == 1 and "ghost" in problems[0]


def test_trace_report_needs_map_data():
    import rewards

    game = _game()
    game["replaydata"]["ants"] = [[5, 5, 1, 6, 0, "----"]]
    recs = [{"turn": 3, "loc": [5, 5], "dest": [5, 6], "action": "e"}]
    with pytest.raises(ValueError):  # a miss with no grid to classify it
        rewards.trace_report(game, 0, recs)
    assert rewards.trace_report(game, 0, []) == (0.0, [])  # vacuous: clean


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


def _timeout_game():
    game = _trace_game()
    game["status"] = ["timeout", "timeout"]
    return game


def test_resolve_stranded_rewrites_dest_not_action():
    import rewards

    game = _timeout_game()
    recs = [{"turn": 3, "loc": [5, 5], "dest": [5, 4], "action": "w"}]
    out = rewards.resolve_stranded(game, 0, recs)
    assert out[0]["dest"] == [5, 5]  # stranded ≡ stay: joinable
    assert out[0]["action"] == "w"  # intent stays honest for PPO
    assert recs[0]["dest"] == [5, 4]  # input untouched: pure return


def test_resolve_stranded_leaves_the_rest_for_trace():
    import rewards

    game = _timeout_game()
    matched = {"turn": 3, "loc": [5, 5], "dest": [5, 5], "action": "stay"}
    assert rewards.resolve_stranded(game, 0, [matched])[0]["dest"] == [5, 5]
    water = {"turn": 3, "loc": [5, 5], "dest": [5, 6], "action": "e"}
    assert rewards.resolve_stranded(game, 0, [water])[0]["dest"] == [5, 6]
    ghost = {"turn": 9, "loc": [5, 5], "dest": [5, 4], "action": "w"}
    assert rewards.resolve_stranded(game, 0, [ghost])[0]["dest"] == [5, 4]
    # Off the timeout turn even passable loss stays put: trace raises.
    game["playerturns"] = [5, 5]
    calm = {"turn": 3, "loc": [5, 5], "dest": [5, 4], "action": "w"}
    assert rewards.resolve_stranded(game, 0, [calm])[0]["dest"] == [5, 4]
    assert rewards.resolve_stranded(game, 0, []) == []


def test_play_one_resolves_stranded_orders_on_timeout_turns(tmp_path, monkeypatch):
    import archive
    import game_if
    import train as _train

    base = tmp_path / "archive"
    cfg = {"seed": 0, "turns": 5, "temperature": 0.0, "tick": 7}
    land = ["." * 10 for _ in range(10)]

    def fake_play(*a, **k):
        game = {
            "game_length": 10,
            "score": [3, 1],
            "status": ["timeout", "survived"],
            "playerturns": [3, 0],
            "replaydata": {
                "map": {"rows": 10, "cols": 10, "data": land},
                "viewradius2": 77,
                "attackradius2": 5,
                "food": [],
                "ants": [
                    [4, 4, 1, 10, 0, "-" * 9],
                    [6, 6, 1, 10, 1, "-" * 9],
                ],
                "hills": [],
            },
        }
        recs = [
            [{"turn": 3, "loc": [4, 4], "dest": [5, 4], "action": "e",
              "window": [[[0.0]]]}],
            [{"turn": 3, "loc": [6, 6], "dest": [6, 6], "action": "stay",
              "window": [[[0.0]]]}],
        ]
        return {"game": game, "records": recs}

    monkeypatch.setattr(game_if, "play", fake_play)
    out = _train._play_one(cfg, base, {}, _tmp_2p_map(tmp_path))
    assert out["rows"][0]["dest"] == [4, 4]  # stranded ≡ stay: joinable
    assert out["rows"][0]["action"] == "e"  # intent stays honest
    assert out["rows"][1]["dest"] == [6, 6]
    (row,) = archive.list_games(base)
    assert row["trace_miss"] == 0.0  # resolved before audit, not tolerated
