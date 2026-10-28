"""Honest logging: intent per ant, blocked-aware loss, no fake stays.

(a) AlphaAnt.py sequential reservation erases blocked intent — only the
post-mask action is logged, so the learner never sees "I wanted that
square but a friend took it". Rows must carry intent (pre-mask argmax),
blocked (reservation set as action names), and the taken action.
(b) ml/algorithm.py must not reinforce the second choice as a
preference: on blocked rows the loss trains the intent (mask opened on
the intended action); on unblocked rows the path is byte-identical to
legacy. honest=False reproduces the old behavior exactly.
(c) The timeout path must not forge stay rows for undecided ants.
"""

import json
import sys
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "ml"))

import algorithm
import features

_C = len(features.CHANNELS)
_S = 2 * features.DEFAULT_RADIUS + 1


class StubAnts:
    rows, cols = 10, 10
    viewradius2 = 77

    def __init__(self, mine, clock=(1000,)):
        self._mine = list(mine)
        self._clock = list(clock)
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
        return self._clock.pop(0) if len(self._clock) > 1 else self._clock[0]


def _bot(tmp_path, monkeypatch, logits):
    import AlphaAnt

    monkeypatch.setenv("AA_RECORD_DIR", str(tmp_path))
    bot = AlphaAnt.AlphaAntBot()
    bot.policy = lambda x: logits  # fixed desires, independent of input
    return bot


def _rows(tmp_path):
    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    return [json.loads(line) for line in files[0].read_text().splitlines()]


def test_row_logs_intent_blocked_and_taken_action(tmp_path, monkeypatch):
    """Synthetic blocked position: ant2 wants w into ant1's new square."""
    ants = StubAnts([(4, 4), (4, 6)])
    # ant1: e=10 takes (4,5). ant2: wants w=(4,5, taken), falls back to n.
    logits = torch.tensor([
        [0.0, 10.0, 0.0, 0.0, 0.0],  # n e s w stay
        [5.0, 0.0, 0.0, 10.0, 0.0],
    ])
    bot = _bot(tmp_path, monkeypatch, logits)
    bot.do_setup(ants)
    bot.do_turn(ants)
    row1, row2 = _rows(tmp_path)
    # Old keys byte-identical: all six still present.
    for row in (row1, row2):
        assert {"turn", "loc", "dest", "action", "window", "legal"} <= set(row)
    # Unblocked ant: intent == action, empty blocked set.
    assert row1["intent"] == "e" and row1["action"] == "e"
    assert row1["blocked"] == []
    # Blocked ant: intent is the want, action is the fallback.
    assert row2["intent"] == "w"
    assert row2["blocked"] == ["w"]
    assert row2["action"] == "n"
    assert row2["dest"] == [3, 6]


def test_timeout_logs_zero_fake_stay_rows(tmp_path, monkeypatch):
    """Clock dies after ant0: undecided ants must leave no rows at all."""
    ants = StubAnts([(4, 4), (4, 6), (4, 8)], clock=(5,))
    logits = torch.tensor([[0.0, 10.0, 0.0, 0.0, 0.0]] * 3)  # all want e
    bot = _bot(tmp_path, monkeypatch, logits)
    bot.do_setup(ants)
    bot.do_turn(ants)
    rows = _rows(tmp_path)
    assert len(rows) == 1  # decided ant only; late ants are skipped, not stayed
    assert rows[0]["loc"] == [4, 4] and rows[0]["action"] == "e"


def _rec(action, intent, blocked, legal):
    return {
        "turn": 1,
        "loc": [4, 4],
        "dest": [4, 5],
        "action": action,
        "intent": intent,
        "blocked": list(blocked),
        "window": torch.zeros(_C, 5, 5),
        "legal": list(legal),
    }


def _items_equal(a, b):
    assert len(a) == len(b)
    for (wa, ia, ra, ma, oa), (wb, ib, rb, mb, ob) in zip(a, b):
        assert torch.equal(wa, wb) and ia == ib and ra == rb
        assert ma == mb and oa == ob


def test_blocked_loss_trains_intent_unblocked_identical():
    """honest=True opens the mask on the intent and trains it; naive
    reinforces the fallback. Unblocked rows are untouched either way."""
    open_mask = [True] * 5
    taken_mask = [True, True, True, False, True]  # w reserved away
    free = _rec("n", "n", [], open_mask)
    blocked = _rec("n", "w", ["w"], taken_mask)
    rets, logps = [1.0, -0.5], [0.0, 0.0]

    naive = algorithm.to_batch([free, blocked], rets, logps, honest=False)
    honest = algorithm.to_batch([free, blocked], rets, logps, honest=True)
    # Unblocked row: byte-identical path (same action, same mask).
    _items_equal([naive[0]], [honest[0]])
    # Blocked row: naive trains the fallback n; honest trains the want w
    # with the mask opened on it.
    assert naive[1][1] == features.ACTIONS.index("n")
    assert honest[1][1] == features.ACTIONS.index("w")
    assert naive[1][3] == taken_mask and honest[1][3] == [True] * 5


def test_honest_path_byte_identical_without_blocking():
    """No blocked rows anywhere -> honest=True == honest=False, exactly.
    Legacy rows without intent keys are also untouched by honest=True."""
    recs = [
        _rec("e", "e", [], [True] * 5),
        {"turn": 2, "loc": [1, 1], "dest": [1, 2], "action": "s",
         "window": torch.zeros(_C, 5, 5), "legal": [True] * 5},
    ]
    rets, logps = [0.3, 0.7], [-0.1, -0.2]
    _items_equal(
        algorithm.to_batch(recs, rets, logps, honest=True),
        algorithm.to_batch(recs, rets, logps, honest=False),
    )


def test_blocked_loss_differs_only_on_blocked_rows():
    """End-to-end through collect + one PPO epoch (seeded): blocked
    rows move the loss, unblocked-only batches give identical stats."""
    torch.manual_seed(7)
    policy = algorithm.new_policy()
    open_mask = [True] * 5
    free = _rec("n", "n", [], open_mask)
    blocked = _rec("n", "w", ["w"], [True, True, True, False, True])

    torch.manual_seed(0)
    mixed_old = algorithm.collect(policy, [free, blocked], [1.0, -0.5],
                                  honest=False)
    torch.manual_seed(0)
    mixed_new = algorithm.collect(policy, [free, blocked], [1.0, -0.5],
                                  honest=True)
    assert [a for _, a, _, _, _ in mixed_old] != [
        a for _, a, _, _, _ in mixed_new]

    def _epoch(batch):
        pol = algorithm.new_policy(algorithm.policy_weights(policy))
        opt = algorithm.make_optimizer(pol)
        torch.manual_seed(0)
        stats = algorithm.train_epoch(pol, opt, batch)
        return stats, algorithm.policy_weights(pol)

    old_stats, old_w = _epoch(mixed_old)
    new_stats, new_w = _epoch(mixed_new)
    # Same scalar means can hide different directions: the updates differ.
    assert any(not torch.equal(torch.tensor(old_w[k]), torch.tensor(new_w[k]))
               for k in old_w)

    torch.manual_seed(0)
    free_old = algorithm.collect(policy, [free, free], [1.0, -0.5],
                                 honest=False)
    torch.manual_seed(0)
    free_new = algorithm.collect(policy, [free, free], [1.0, -0.5],
                                 honest=True)
    assert _epoch(free_old)[0] == _epoch(free_new)[0]
    _, free_old_w = _epoch(free_old)
    _, free_new_w = _epoch(free_new)
    assert all(torch.equal(torch.tensor(free_old_w[k]),
                           torch.tensor(free_new_w[k]))
               for k in free_old_w)
