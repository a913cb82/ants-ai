"""Learning step: PPO, collect, batch, optimizer, normalization.

Split from the test_alphastarzero monolith; no behavior change.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "ml"))

import features

_C = features.INPUT_CHANNELS
_S = 2 * features.DEFAULT_RADIUS + 1




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



def _tmp_2p_map(tmp_path, name="e.map"):
    p = tmp_path / name
    p.write_text("rows 16\ncols 24\nplayers 2\n" + "m " + "." * 24 + "\n")
    return str(p)



def _fake_game_out(names, scores, outdir):
    (outdir / "logs").mkdir(parents=True, exist_ok=True)
    (outdir / "logs" / "0.replay").write_text(
        json.dumps({"game_length": 10, "score": list(scores), "replaydata": {}})
    )
    return {
        "game": {"game_length": 10, "score": list(scores), "replaydata": {}},
        "records": [[] for _ in names],
    }



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
