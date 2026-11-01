"""Stall-memory channel: 1-bit same-cell/blocked hysteresis (ch9).

ch9 = clip(streak / K, 0, 1), K=8, broadcast constant across the whole
window (rotation-invariant by construction). streak increments per ant
when it holds its cell across turns, and carries through a move whose
intent was reservation-blocked; free moves and new ids reset to 0.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))

import features

K = 8


class StubAnts:
    rows, cols = 10, 10
    viewradius2 = 77

    def __init__(self, mine):
        self._mine = list(mine)
        self.orders = []

    def my_ants(self):
        return list(self._mine)

    def enemy_ants(self):
        return []

    def food(self):
        return []

    def my_hills(self):
        return []

    def enemy_hills(self):
        return []

    def destination(self, loc, d):
        r, c = loc
        return {
            "n": ((r - 1) % self.rows, c),
            "s": ((r + 1) % self.rows, c),
            "e": (r, (c + 1) % self.cols),
            "w": (r, (c - 1) % self.cols),
        }[d]

    def passable(self, loc):
        return True

    def issue_order(self, order):
        self.orders.append(order)

    def time_remaining(self):
        return 1000


def _bot(tmp_path, monkeypatch, logits_fn):
    import AlphaAnt

    monkeypatch.setenv("AA_RECORD_DIR", str(tmp_path))
    bot = AlphaAnt.AlphaAntBot()
    bot.policy = logits_fn
    bot.do_setup(StubAnts([(5, 5)]))
    return bot


def _stay_logits():
    import torch

    def fn(x):
        out = torch.zeros(x.shape[0], 5)
        out[:, 4] = 10.0
        return out

    return fn


def _windows_by_turn(tmp_path):
    rows = []
    for f in tmp_path.glob("*.jsonl"):
        rows += [json.loads(line) for line in f.read_text().splitlines()]
    by_turn: dict = {}
    for r in rows:
        by_turn.setdefault(r["turn"], []).append(
            features.decode_window(r["window"])
        )
    return by_turn


def test_channels_declares_stall_ch9():
    assert len(features.CHANNELS) == 10
    assert features.CHANNELS[9] == "stall"
    assert features.STALL_CHANNEL == 9


def test_held_ant_streak_matches_formula(tmp_path, monkeypatch):
    import AlphaAnt

    assert AlphaAnt.STALL_K == K
    bot = _bot(tmp_path, monkeypatch, _stay_logits())
    stub = StubAnts([(5, 5)])
    for _ in range(6):
        bot.do_turn(stub)
    by_turn = _windows_by_turn(tmp_path)
    # 5 same-cell transitions across 6 held turns -> 5/8 on the 6th.
    for t in range(1, 7):
        assert float(by_turn[t][0][9, 0, 0]) == pytest.approx((t - 1) / K)
    assert float(by_turn[6][0][9, 0, 0]) == pytest.approx(5 / K)


def test_move_resets_and_new_id_starts_zero(tmp_path, monkeypatch):
    bot = _bot(tmp_path, monkeypatch, _stay_logits())
    stub = StubAnts([(5, 5)])
    for _ in range(3):
        bot.do_turn(stub)
    # free move elsewhere: next window at the new cell reads 0
    import torch

    def north(x):
        out = torch.zeros(x.shape[0], 5)
        out[:, 0] = 10.0
        return out

    bot.policy = north
    bot.do_turn(stub)
    assert stub.orders  # it actually moved
    stub._mine = [(4, 5)]
    stub.orders.clear()
    bot.policy = _stay_logits()
    bot.do_turn(stub)
    by_turn = _windows_by_turn(tmp_path)
    assert float(by_turn[5][0][9, 0, 0]) == 0.0
    # dead-id replacement at a fresh cell also starts at 0
    stub._mine = [(1, 1)]
    bot.do_turn(stub)
    by_turn = _windows_by_turn(tmp_path)
    assert float(by_turn[6][0][9, 0, 0]) == 0.0


def test_stall_channel_is_window_constant(tmp_path, monkeypatch):
    import torch

    bot = _bot(tmp_path, monkeypatch, _stay_logits())
    stub = StubAnts([(5, 5)])
    for _ in range(4):
        bot.do_turn(stub)
    by_turn = _windows_by_turn(tmp_path)
    ch9 = by_turn[4][0][9]
    assert torch.all(ch9 == ch9[0, 0]).item()


def test_intent_blocked_move_carries_hysteresis(tmp_path, monkeypatch):
    """Blocked-but-moved ant keeps memory despite changing cells."""
    import torch

    def contest(x):
        # A(row0) wants e -> (5,6); B(row1) wants w -> (5,6): B blocked.
        return torch.tensor([[0.0, 10.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 10.0, 0.0]])[
            : x.shape[0]
        ]

    bot = _bot(tmp_path, monkeypatch, contest)
    stub = StubAnts([(5, 5), (5, 7)])
    bot.do_turn(stub)
    by_turn = _windows_by_turn(tmp_path)
    rows = []
    for f in tmp_path.glob("*.jsonl"):
        rows += [json.loads(line) for line in f.read_text().splitlines()]
    b_row = [r for r in rows if r["loc"] == [5, 7]][0]
    assert "w" in b_row["blocked"] and b_row["action"] != "w"
    dest = tuple(b_row["dest"])
    assert dest != (5, 7)  # moved to a fallback, not held
    stub._mine = [(5, 6), dest]
    bot.policy = _stay_logits()
    bot.do_turn(stub)
    by_turn = _windows_by_turn(tmp_path)
    turn2 = by_turn[2]
    assert len(turn2) == 2
    # B's new cell carries hysteresis despite the move
    vals = sorted(float(w[9, 0, 0]) for w in turn2)
    assert vals[1] > 0.0


def test_d4_equivariance_with_nonzero_stall():
    import model
    import torch

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    policy.eval()
    w = torch.rand(1, 10, 15, 15)
    w[:, 9, :, :] = 3 / K  # nonzero constant stall, as the bot emits
    with torch.no_grad():
        a = policy(w)
        b = policy(torch.rot90(w, 1, (2, 3)))
    torch.testing.assert_close(b, a[:, [1, 2, 3, 0, 4]], atol=1e-6, rtol=1e-5)


def test_9ch_checkpoint_loads_zero_padded_with_identical_logits():
    """Cold start: old champ weights behave bit-identically on ch9=0."""
    import model
    import torch

    torch.manual_seed(1)
    old = model.CNNPolicy(channels=9)
    raw = model.state_dict_to_lists(old)
    new = model.CNNPolicy()  # 10 channels now
    state = model.pad_in_channels(model.lists_to_state_dict(raw), new)
    new.load_state_dict(state, strict=True)
    assert torch.all(new.conv1.weight[:, 9, :, :] == 0).item()
    assert torch.all(new.vconv1.weight[:, 9, :, :] == 0).item()
    new.eval()
    old.eval()
    w9 = torch.rand(2, 9, 15, 15)
    w10 = torch.zeros(2, 10, 15, 15)
    w10[:, :9] = w9
    with torch.no_grad():
        a = old(w9)
        b = new(w10)
    torch.testing.assert_close(b, a, atol=0.0, rtol=0.0)
