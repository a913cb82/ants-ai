"""Advantage freeze: advantages are computed ONCE per generation.

Regression for the PPO reviewer's confirmed code-fact: train_epoch
recomputed (return - value) from the CURRENT value net in every
minibatch of every epoch, so advantages evaporated as the critic fit.
The contract under test: train_generation freezes advantages with the
pre-update value net and every epoch reuses that frozen vector; the
batch scale (bmean/bstd) stays per-generation as today.
"""

import sys
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "ml"))

import algorithm  # noqa: E402
import features  # noqa: E402
import model  # noqa: E402

_C = len(features.CHANNELS)
_S = 2 * features.DEFAULT_RADIUS + 1


def _batch(n=32, seed=0):
    torch.manual_seed(seed)
    recs = [{"window": torch.rand(_C, _S, _S), "action": "n",
             "legal": [True] * 5} for _ in range(n)]
    pol = algorithm.new_policy({})
    return algorithm.collect(pol, recs, [float(i % 3) for i in range(n)])


def test_frozen_advantages_match_preupdate_values():
    pol = algorithm.new_policy({})
    batch = _batch()
    adv, bmean, bstd = algorithm.frozen_advantages(pol, batch)
    assert len(adv) == len(batch)
    with torch.no_grad():
        windows = torch.stack([w for w, _a, _r, _m, _o in batch])
        values = pol.values(windows)
    rets = torch.tensor([r for _w, _a, r, _m, _o in batch])
    expect = algorithm._advantages(rets, values, rets.mean(),
                                   rets.std(unbiased=False))
    assert torch.equal(adv, expect)
    assert float(bmean) == pytest.approx(rets.mean().item())
    assert float(bstd) == pytest.approx(rets.std(unbiased=False).item())


def test_train_epoch_reuses_frozen_advantages_without_recompute(monkeypatch):
    pol = algorithm.new_policy({})
    opt = algorithm.make_optimizer(pol, lr=1e-3)
    batch = _batch()
    adv, bmean, bstd = algorithm.frozen_advantages(pol, batch)

    def _boom(*a, **k):
        raise AssertionError("advantage recompute: frozen adv must be reused")

    monkeypatch.setattr(algorithm, "_advantages", _boom)
    stats = algorithm.train_epoch(pol, opt, batch, advantages=adv,
                                  bmean=bmean, bstd=bstd)
    assert stats["steps"] > 0


def test_frozen_pg_rows_survive_critic_drift():
    """One epoch from the same actor gives the same actor update even
    when the critic has drifted: the policy gradient cannot evaporate
    mid-generation (the evaporation regression)."""
    import copy

    torch.manual_seed(7)
    pol = algorithm.new_policy({})
    batch = _batch()
    adv, bmean, bstd = algorithm.frozen_advantages(pol, batch)
    drifted = copy.deepcopy(pol)
    with torch.no_grad():
        drifted.value.bias.fill_(5.0)  # critic fit hard; actor untouched
    assert torch.equal(
        drifted.value.bias, torch.full_like(drifted.value.bias, 5.0))

    def one_epoch(policy, seed, lr=1e-3):
        torch.manual_seed(seed)
        opt = algorithm.make_optimizer(policy, lr=lr)
        # max_norm=inf: global clipping would couple critic grads into
        # actor steps; disabled here to isolate the pg term itself.
        algorithm.train_epoch(policy, opt, batch, advantages=adv,
                              bmean=bmean, bstd=bstd, minibatch=8,
                              max_norm=float("inf"))

    one_epoch(pol, 123)
    one_epoch(drifted, 123)
    for (n0, p0), (n1, p1) in zip(pol.named_parameters(),
                                  drifted.named_parameters(), strict=True):
        assert n0 == n1
        if not model.is_critic_key(n0):
            assert torch.equal(p0, p1), f"actor param {n0} moved"
    # Control: without the freeze the drifted critic changes the update.
    torch.manual_seed(7)
    a = algorithm.new_policy({})
    b = copy.deepcopy(a)
    with torch.no_grad():
        b.value.bias.fill_(5.0)
    torch.manual_seed(123)
    algorithm.train_epoch(a, algorithm.make_optimizer(a), batch,
                          minibatch=8)
    torch.manual_seed(123)
    algorithm.train_epoch(b, algorithm.make_optimizer(b), batch,
                          minibatch=8)
    actors = [(n, p) for n, p in a.named_parameters()
              if not model.is_critic_key(n)]
    moved = [n for n, p in actors
             if not torch.equal(p, dict(b.named_parameters())[n])]
    assert moved, "control: recompute should feel critic drift"


def test_train_generation_freezes_advantages_once_per_gen(tmp_path,
                                                          monkeypatch):
    import archive
    import train

    base = tmp_path / "archive"
    w = algorithm.policy_weights(algorithm.new_policy({}))
    champ = archive.save_checkpoint(base, w, role="main", parent=None)
    archive.set_champion(base, champ)

    recs = [{"window": torch.rand(_C, _S, _S).tolist(), "action": "n",
             "legal": [True] * 5} for _ in range(32)]

    def fake_play_one(args):
        return {"rows": list(recs), "rets": [float(i % 3) for i in range(32)]}

    monkeypatch.setattr(train, "_play_one", fake_play_one)
    calls = []
    real_epoch = algorithm.train_epoch

    def spy(policy, opt, batch, **kw):
        calls.append(kw.get("advantages").clone()
                     if kw.get("advantages") is not None else None)
        return real_epoch(policy, opt, batch, **kw)

    monkeypatch.setattr(algorithm, "train_epoch", spy)
    cfg = {"train_games": 1, "eval_games": 0, "workers": 1,
           "maps": ["m.map"], "turns": 1, "lr": 1e-3, "epochs": 3,
           "temperature": 0.0, "seed": 0, "clip": 0.2, "vf_coef": 0.5,
           "entropy_beta": 0.01, "max_norm": 1.0, "minibatch": 32}
    train.train_generation(cfg, base, champ, w)
    assert len(calls) == 3
    assert all(c is not None for c in calls)
    assert all(torch.equal(calls[0], c) for c in calls[1:])
