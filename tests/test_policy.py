"""Policy net: forward, equivariance, arch, masking, act/sample, init.

Split from the test_alphastarzero monolith; no behavior change.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "bots" / "alphaant" / "train"))

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



def _probs(policy, w):
    import torch

    policy.eval()
    with torch.no_grad():
        return torch.softmax(policy(w), dim=1)



def _count_params(policy) -> int:
    return sum(t.numel() for t in policy.parameters())



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




def test_cnn_forward_shape():
    import model
    import torch

    policy = model.CNNPolicy()
    assert policy(torch.zeros(1, _C, _S, _S)).shape == (1, 5)




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




def test_legal_mask_blocks_food_tiles():

    import model

    w = _cnn_window()
    w[5, 4, 5] = 1.0  # food east of center
    mask = model.legal_mask(w)
    assert mask.tolist() == [True, False, True, True, True]




def test_masked_logits_batch_matches_serial():
    import features
    import model
    import torch

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    ants = FakeAnts()
    windows = torch.stack(
        [
            features.with_history(features.local_window(ants, loc), None)
            for loc in [(4, 4), (0, 0), (9, 9)]
        ]
    )
    blockeds = [frozenset(), frozenset({"n"}), frozenset({"n", "e", "s", "w"})]
    batched = model.masked_logits_batch(policy, windows, blockeds)
    assert batched.shape == (3, 5)
    for i, loc in enumerate([(4, 4), (0, 0), (9, 9)]):
        single = model.masked_logits(
            policy,
            features.with_history(features.local_window(ants, loc), None),
            blockeds[i],
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
    windows = torch.stack(
        [features.with_history(features.local_window(ants, (4, 4)), None)]
    )
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
        [
            features.with_history(features.local_window(ants, loc), None)
            for loc in [(4, 4), (0, 0)]
        ]
    )
    logits = model.masked_logits_batch(policy, windows, [frozenset(), frozenset()])
    assert model.act_greedy_batch(logits) == [
        model.act_greedy(policy, windows[0]),
        model.act_greedy(policy, windows[1]),
    ]
    assert len(model.sample_batch(logits, 1.0)) == 2




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
    assert base == 13830  # +3 memory channels widen conv1/vconv1 (was 12966)
    assert 9000 < deep < 14000  # same order, no budget blowout




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




def test_rotation_constants_stay_mirrored():
    import algorithm
    import model

    assert model.ROT_PERM == algorithm.ROT_PERM  # duplicated on purpose
