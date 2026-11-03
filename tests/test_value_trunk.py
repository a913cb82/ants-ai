"""Unshared critic: CNNPolicy owns a separate value trunk (vconv* keys).

TDD for the trunk split: values() runs off vtrunk, actor path untouched,
old (actor-only) checkpoints still load, and the critic fits synthetic
targets on its own trunk.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "ml"))

import features

_C = features.INPUT_CHANNELS
_S = 2 * features.DEFAULT_RADIUS + 1


def _vkeys(policy):
    return {n for n, _ in policy.named_parameters() if n.startswith("vconv")}


def test_values_output_shape_both_arches():
    import model
    import torch

    for arch in ("base", "deep"):
        policy = model.CNNPolicy(arch=arch)
        assert policy.values(torch.zeros(3, _C, _S, _S)).shape == (3,)


def test_state_dict_has_separate_value_trunk_keys():
    import model

    for arch in ("base", "deep"):
        policy = model.CNNPolicy(arch=arch)
        keys = set(policy.state_dict())
        actor = {k for k in keys if k.startswith("conv")}
        value = {k for k in keys if k.startswith("vconv")}
        assert value, arch
        assert actor.isdisjoint(value), arch
        # same tiny shapes, mirrored layer for layer
        for a in sorted(actor):
            v = "v" + a
            assert v in keys, (arch, a)
            assert policy.state_dict()[a].shape == policy.state_dict()[v].shape, (
                arch,
                a,
            )


def test_policy_weights_roundtrip_includes_value_trunk():
    import algorithm
    import model

    for arch in ("base", "deep"):
        policy = model.CNNPolicy(arch=arch)
        w = algorithm.policy_weights(policy)
        assert any(k.startswith("vconv") for k in w), arch
        clone = algorithm.new_policy(w)
        assert _vkeys(clone) == _vkeys(policy)
        for n, p in policy.named_parameters():
            assert (clone.state_dict()[n] == p).all(), (arch, n)


def test_old_actor_only_weights_load_and_values_runs():
    import algorithm
    import model
    import torch

    for arch in ("base", "deep"):
        policy = model.CNNPolicy(arch=arch)
        old = {
            k: v
            for k, v in model.state_dict_to_lists(policy).items()
            if not k.startswith("vconv") and not k.startswith("value")
        }
        assert old  # actor keys only
        fresh = model.CNNPolicy(arch=arch)
        fresh.load_state_dict(model.lists_to_state_dict(old), strict=False)
        assert fresh.values(torch.zeros(2, _C, _S, _S)).shape == (2,)
        # actor weights survived the partial load
        assert torch.equal(
            fresh(torch.zeros(1, _C, _S, _S)), policy(torch.zeros(1, _C, _S, _S))
        )
        # algorithm entry point agrees (old champions lack critic keys)
        via_algo = algorithm.new_policy(old)
        assert via_algo.values(torch.zeros(1, _C, _S, _S)).shape == (1,)


def test_infer_arch_unchanged_by_split():
    import model

    assert model.infer_arch(model.state_dict_to_lists(model.CNNPolicy())) == "base"
    assert (
        model.infer_arch(model.state_dict_to_lists(model.CNNPolicy(arch="deep")))
        == "deep"
    )


def test_actor_path_ignores_value_trunk():
    import model
    import torch

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    x = torch.randn(2, _C, _S, _S)
    before = policy(x).detach().clone()
    with torch.no_grad():
        for n, p in policy.named_parameters():
            if n.startswith("vconv") or n.startswith("value"):
                p.uniform_(-1.0, 1.0)
    assert torch.equal(before, policy(x))


def test_value_only_fit_decreases_loss():
    import model
    import torch

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    x = torch.zeros(32, _C, _S, _S)
    for i in range(32):
        x[i, 1, 4, 4] = float(i + 1) / 32.0  # distinct states, fittable targets
    target = (x[:, 1, 4, 4] * 4.0 - 2.0).detach()
    # value trunk + head only: actor params frozen
    for n, p in policy.named_parameters():
        if not (n.startswith("vconv") or n.startswith("value")):
            p.requires_grad = False
    opt = torch.optim.Adam([p for p in policy.parameters() if p.requires_grad], lr=1e-2)
    losses = []
    for _ in range(50):
        loss = ((policy.values(x) - target) ** 2).mean()
        opt.zero_grad()
        loss.backward()
        opt.step()
        losses.append(loss.item())
    assert losses[-1] < losses[0]
