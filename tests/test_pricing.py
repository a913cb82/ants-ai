"""Reward pricing: food/kill/death/hill credit, discount, gating, outcomes.

Split from the test_alphastarzero monolith; no behavior change.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "bots" / "alphaant" / "train"))

import pytest

import features

_C = features.INPUT_CHANNELS
_S = 2 * features.DEFAULT_RADIUS + 1




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
    diet test (challenger scales) and the live-engine zero tests."""
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
    rets = rewards.compute_returns(game, 0, records, _classic_table())
    assert rets[0] == 0.1 + 5.0
    assert rets[1] == 5.0




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
    rets = rewards.compute_returns(game, 0, records, _classic_table())
    assert rets[0] == 0.1 + -0.2 + 5.0




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
    rets = rewards.compute_returns(game, 0, records, _classic_table())
    assert rets[0] > 5.0  # closed one tile: HA + terminal
    assert rets[1] == 5.0  # opened it back: terminal only
    assert rets[2] == 5.0  # stayed: terminal only




def test_hill_approach_stays_same_turn_only():
    import rewards

    game = _game(score=[4, 0])  # win: mechanism active, terminal explicit
    game["replaydata"]["hills"] = [[5, 9, 1, 99]]
    game["replaydata"]["ants"] = [[5, 5, 1, 5, 0, "eee"]]
    records = [
        {"turn": 1, "loc": [5, 5], "dest": [5, 4], "action": "w"},
        {"turn": 2, "loc": [5, 4], "dest": [5, 5], "action": "e"},
    ]
    rets = rewards.compute_returns(game, 0, records, _classic_table())
    assert rets[0] == 5.0  # opened: terminal only, no walk-back
    # closed one full tile (d 5 -> 4): same-turn credit + terminal.
    assert rets[1] == 5.0 + 0.25 * 1.0




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
    rets = rewards.compute_returns(game, 0, records, _classic_table())
    # closes to second, opens to first: no approach, terminal only.
    assert rets[0] == 5.0




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




def test_outcome_win_belongs_to_every_move_equally():
    import rewards

    game = _game(score=[10, 4])
    records = [{"turn": 9, "loc": [1, 1], "dest": [1, 1], "action": "stay"}]
    rets = rewards.compute_returns(game, 0, records, _classic_table())
    assert rets[0] == 5.0




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




def test_kill_credit_excludes_zero_distance():
    import rewards

    game = _game()
    game["replaydata"]["ants"] = [[5, 5, 1, 3, 1, "--"]]  # enemy dies on (5,5)
    records = [{"turn": 3, "loc": [5, 4], "dest": [5, 5], "action": "s"}]
    assert rewards.compute_returns(game, 0, records) == [0.0]




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
    rets = rewards.compute_returns(game, 0, records, _classic_table())
    closed = math.sqrt(32) - math.sqrt(18)
    assert rets[0] == 5.0 + 0.25 * closed




def test_third_seat_gets_own_outcome():
    import rewards

    game = _game()
    game["score"] = [0, 0, 3]  # seat 2 wins alone
    game["replaydata"]["ants"] = [[5, 5, 1, 3, 1, "--"]]
    records = [
        {"turn": 3, "loc": [4, 5], "dest": [5, 5], "action": "s"},
    ]
    assert rewards.compute_returns(game, 2, records, _classic_table())[0] == 5.0
    assert rewards.compute_returns(game, 0, records, _classic_table())[0] == -5.0




def test_outcome_linear_over_placements():
    import rewards

    table = {"WIN": 5.0, "LOSS": -5.0}
    assert rewards.outcome(_game(score=[7, 4, 2, 0]), 0, table) == 5.0
    assert rewards.outcome(_game(score=[7, 4, 2, 0]), 1, table) == pytest.approx(5 - 10 / 3)
    assert rewards.outcome(_game(score=[7, 4, 2, 0]), 2, table) == pytest.approx(-(5 - 10 / 3))
    assert rewards.outcome(_game(score=[7, 4, 2, 0]), 3, table) == -5.0
    for me in (1, 2):  # tied middle shares the middle value
        assert rewards.outcome(_game(score=[7, 4, 4, 0]), me, table) == 0.0
    assert rewards.outcome(_game(score=[10, 10, 0, 0]), 0, table) == 5.0
    assert rewards.outcome(_game(score=[10, 10, 0, 0]), 2, table) == -5.0
    assert rewards.outcome(_game(score=[3, 3, 3]), 1, table) == rewards.DRAW
    assert rewards.outcome(_game(score=[5, 3]), 0, table) == 5.0  # 2p unchanged
    assert rewards.outcome(_game(score=[5, 3]), 1, table) == -5.0
    assert rewards.outcome(_game(score=[7, 4, 2, 0]), 0) == 0.0  # live: no terminal




def test_second_place_terminal_graduated_not_snapped():
    import rewards

    game = _game(score=[0, 1, 2, 3])
    records = [{"turn": 3, "loc": [1, 1], "dest": [1, 1], "action": "stay"}]
    classic = _classic_table()
    assert rewards.compute_returns(game, 2, records, classic)[0] == pytest.approx(5 - 10 / 3)
    assert rewards.compute_returns(game, 1, records, classic)[0] == pytest.approx(-(5 - 10 / 3))
    assert rewards.compute_returns(game, 2, records)[0] == 0.0  # live: no terminal
