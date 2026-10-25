"""One generation's learning: sample opponents, play, price, train.

Knows the training loop. Knows nothing about promotion or the rated
bot file; returns trained weights and stats for the driver to judge.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "bots" / "alphastarzero"))

import algorithm
import archive
import game_if
import model
import rewards


def train_generation(cfg: dict, base: Path, champ_id: str, champ_w: dict) -> tuple[str, dict, dict]:
    """Self-play training games -> (challenger id, weights, train stats)."""
    chal_id = archive.save_checkpoint(base, copy.deepcopy(champ_w), "challenger", champ_id)
    chal_w = copy.deepcopy(champ_w)
    batch: list = []
    policy = model.CNNPolicy()
    opt = algorithm.make_optimizer(policy, lr=cfg["lr"])
    for g in range(cfg["train_games"]):
        opp_id = archive.sample_opponents(base, champ_id, 1, seed=cfg["seed"] + g)[0]
        opp_w = archive.load_checkpoint(base, opp_id)
        for slot in (0, 1):
            me_w, other_w = (chal_w, opp_w) if slot == 0 else (opp_w, chal_w)
            out = game_if.play(
                ROOT,
                sys.executable,
                me_w,
                other_w,
                game_if.GameConfig(
                    map=cfg["maps"][g % len(cfg["maps"])],
                    turns=cfg["turns"],
                    temperature=cfg["temperature"],
                    player_seed=cfg["seed"] + g,
                    engine_seed=1000 + g,
                ),
                base / "games" / f"train{g}_slot{slot}",
            )
            game = out["game"]
            rows = out["records_a"] if slot == 0 else out["records_b"]
            rets = rewards.compute_returns(game, slot, rows)
            batch.extend(algorithm.to_batch(rows, rets))
            sa, sb = game["score"][0], game["score"][1]
            archive.record_result(
                base, chal_id if slot == 0 else opp_id,
                opp_id if slot == 0 else chal_id, sa, sb, kind="train",
            )
    policy.load_state_dict(model.lists_to_state_dict(chal_w))
    losses, entropies = [], []
    for _ in range(cfg["epochs"]):
        stats = algorithm.train_epoch(policy, opt, batch)
        losses.append(stats["loss"])
        entropies.append(stats["entropy"])
    chal_w = model.state_dict_to_lists(policy)
    archive.store(base, chal_id, chal_w)
    mean_return = sum(r for _w, _a, r, _m in batch) / len(batch) if batch else 0.0
    return chal_id, chal_w, {
        "rows": len(batch),
        "losses": losses,
        "entropies": entropies,
        "mean_return": mean_return,
    }
