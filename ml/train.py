"""One generation's learning: sample opponents, play, price, train.

Knows the training loop. Knows nothing about promotion or the rated
bot file; returns trained weights and stats for the driver to judge.
"""

from __future__ import annotations

import copy
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))

import algorithm
import archive
import game_if
import rewards


def _play_one(args) -> dict:
    """One train game: play, price, record. Thread-safe via archive lock."""
    (cfg, base, chal_id, opp_id, me_w, other_w, slot, g) = args
    rel = f"games/{chal_id}/train{g}_slot{slot}"
    first, second = (chal_id, opp_id) if slot == 0 else (opp_id, chal_id)
    map_path = cfg["maps"][g % len(cfg["maps"])]
    out = game_if.play(
        ROOT,
        sys.executable,
        me_w,
        other_w,
        game_if.GameConfig(
            map=map_path,
            turns=cfg["turns"],
            temperature=cfg["temperature"],
            player_seed=cfg["seed"] + g,
            engine_seed=1000 + g,
        ),
        base / rel,
        name_a=first,
        name_b=second,
    )
    game = out["game"]
    rows = out["records_a"] if slot == 0 else out["records_b"]
    rets = rewards.compute_returns(game, slot, rows)
    sa, sb = game["score"][0], game["score"][1]
    archive.record_result(base, first, second, sa, sb, kind="train")
    archive.log_game(base, chal_id, "train", first, second, sa, sb,
                     rel + "/logs/0.replay", map=Path(map_path).name)
    archive.write_status(base, {
        "phase": "train", "challenger": chal_id,
        "done": g * 2 + slot + 1, "total": cfg["train_games"] * 2,
        "last_mean_return": sum(rets) / len(rets) if rets else 0.0,
        "last_game": rel,
    })
    return {"rows": rows, "rets": rets}


def train_generation(cfg: dict, base: Path, champ_id: str, champ_w: dict, role: str = "challenger") -> tuple[str, dict, dict]:
    """Self-play training games -> (challenger id, weights, train stats)."""
    chal_id = archive.save_checkpoint(base, copy.deepcopy(champ_w), role, champ_id)
    chal_w = copy.deepcopy(champ_w)
    batch: list = []
    policy = algorithm.new_policy(chal_w)
    opt = algorithm.make_optimizer(policy, lr=cfg["lr"])
    jobs = []
    for g in range(cfg["train_games"]):
        opp_id = archive.sample_opponents(base, champ_id, 1, seed=cfg["seed"] + g)[0]
        opp_w = archive.load_checkpoint(base, opp_id)
        for slot in (0, 1):
            me_w, other_w = (chal_w, opp_w) if slot == 0 else (opp_w, chal_w)
            jobs.append((cfg, base, chal_id, opp_id, me_w, other_w, slot, g))
    workers = min(cfg.get("workers", 8), len(jobs)) or 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        games = list(pool.map(_play_one, jobs))
    for out in games:
        batch.extend(algorithm.collect(policy, out["rows"], out["rets"]))
    losses, entropies, kls, pgs, vs = [], [], [], [], []
    for _ in range(cfg["epochs"]):
        stats = algorithm.train_epoch(
            policy, opt, batch,
            clip=cfg["clip"], vf_coef=cfg["vf_coef"],
            entropy_beta=cfg["entropy_beta"], max_norm=cfg["max_norm"],
            minibatch=cfg["minibatch"],
        )
        losses.append(stats["loss"])
        entropies.append(stats["entropy"])
        kls.append(stats["kl"])
        pgs.append(stats["pg_loss"])
        vs.append(stats["v_loss"])
    chal_w = algorithm.policy_weights(policy)
    archive.store(base, chal_id, chal_w)
    mean_return = (
        sum(r for _w, _a, r, _m, _o in batch) / len(batch) if batch else 0.0
    )
    return chal_id, chal_w, {
        "rows": len(batch),
        "losses": losses,
        "entropies": entropies,
        "kl": kls,
        "pg_loss": pgs,
        "v_loss": vs,
        "steps": stats.get("steps", 0),
        "mean_return": mean_return,
    }
