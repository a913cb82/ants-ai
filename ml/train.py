"""Mirror self-play: one game, one PPO micro-batch step.

Knows the training loop. Each call plays exactly one latest-vs-latest
game and returns both seats' records for the batch (AlphaZero trains
on every position, not one side).

PPO math is byte-identical to the retired generation path: one frozen
baseline per update (frozen_advantages), then N epochs of train_epoch
over the same batch. Pricing is the main line's diet (rewards.py base
scales + the challenger outcome gate), the only diet there is."""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))

import algorithm
import archive
import game_if
import rewards


#: League learner -> training config. Pricing roles reuse the legacy
#: scale tables (rewards.py knows "exploiter"/"challenger"; "challenger"
#: is absent from ROLE_OVERRIDES so the main trains on base scales,
#: exactly like the old main line). Snapshot roles are the going-forward
#: manifest roles from the league plan. ME tracks the live main
#: above its threshold, otherwise its snapshots; LEs track the pool.
def _play_one(cfg: dict, base: Path, weights: dict, map_path: str) -> dict:
    """One mirror game: latest vs latest, both seats train.

    Both seats run the same weights; both seats' decision records and
    seat-perspective returns accumulate into the batch. One row is
    logged per game; the tick IS the game number (replay dirs and both
    seeds key on it)."""
    tick = cfg["tick"]
    rel = f"games/main/tick{tick}"
    field = ["main", "main"]
    out = game_if.play(
        ROOT,
        sys.executable,
        weights,
        game_if.GameConfig(
            map=map_path,
            turns=cfg["turns"],
            temperature=cfg["temperature"],
            player_seed=cfg["seed"] + tick,
            engine_seed=1000 + tick,
        ),
        base / rel,
        names=field,
    )
    game = out["game"]
    scales = rewards.scales()  # the one diet
    rows0 = algorithm.compact_records(out["records"][0])
    rows1 = algorithm.compact_records(out["records"][1])
    rets0 = rewards.compute_returns(game, 0, rows0, scales)
    rets1 = rewards.compute_returns(game, 1, rows1, scales)
    rows, rets = rows0 + rows1, rets0 + rets1
    scores = game["score"]
    gid = f"{rel}#{uuid.uuid4().hex[:12]}"  # one play, one id
    # Behavior facts, parsed once per game from the played game dict:
    # per-seat food/kills/army over owner indices.
    behavior = None
    if isinstance(game, dict):
        try:
            behavior = archive.behavior_from_replay(
                game.get("replaydata"),
                n=2,
                length=game.get("length", game.get("game_length")),
            )
        except Exception:
            behavior = None
    now = time.time()
    kw: dict = {"t": now, "tick": tick}
    if behavior is not None:
        kw["food"] = [behavior["food"][0], behavior["food"][1]]
        kw["kills"] = [behavior["kills"][0], behavior["kills"][1]]
        kw["army"] = [behavior["army"][0], behavior["army"][1]]
        kw["length"] = behavior["length"]
    archive.log_game(
        base,
        "main",
        "main",
        scores[0],
        scores[1],
        rel + "/logs/0.replay",
        map=Path(map_path).name,
        game=gid,
        **kw,
    )
    return {"rows": rows, "rets": rets, "scores": list(scores), "game": game}


def ppo_update(policy, opt, batch: list, cfg: dict) -> dict:
    """Micro-batch PPO: one frozen baseline, then cfg["epochs"] passes.

    Identical math to the retired generation tail: frozen_advantages
    freezes one baseline per update so advantages cannot evaporate as
    the critic fits, then every epoch reuses that triple. Returns the
    same stats dict the generation path reported."""
    # Advantage freeze: one baseline per update with the pre-update
    # value net. Every epoch reuses this triple, so advantages cannot
    # evaporate as the critic fits (recompute-per-minibatch did).
    frozen_adv, frozen_mean, frozen_std = algorithm.frozen_advantages(policy, batch)
    with torch.no_grad():
        all_ret = torch.tensor([r for _w, _a, r, _m, _o in batch], dtype=torch.float32)
        vals = []
        for start in range(0, len(batch), 256):
            windows = torch.stack(
                [w for w, _a, _r, _m, _o in batch[start : start + 256]]
            )
            vals.append(policy.values(windows).detach().cpu())
        pred = torch.cat(vals) if vals else torch.zeros(0)
        var_y = float(all_ret.var(unbiased=False)) if len(all_ret) else 0.0
        explained_var = (
            float("nan")
            if var_y == 0
            else float(1 - (all_ret - pred).var(unbiased=False) / var_y)
        )
    losses, entropies, kls, clips, pgas, pgs, vs = [], [], [], [], [], [], []
    for _ in range(cfg["epochs"]):
        stats = algorithm.train_epoch(
            policy,
            opt,
            batch,
            clip=cfg["clip"],
            vf_coef=cfg["vf_coef"],
            entropy_beta=cfg["entropy_beta"],
            max_norm=cfg["max_norm"],
            minibatch=cfg["minibatch"],
            advantages=frozen_adv,
            bmean=frozen_mean,
            bstd=frozen_std,
        )
        losses.append(stats["loss"])
        entropies.append(stats["entropy"])
        kls.append(stats["kl"])
        clips.append(stats["clipfrac"])
        pgas.append(stats["pg_abs"])
        pgs.append(stats["pg_loss"])
        vs.append(stats["v_loss"])
    mean_return = sum(r for _w, _a, r, _m, _o in batch) / len(batch) if batch else 0.0
    return {
        "rows": len(batch),
        "losses": losses,
        "entropies": entropies,
        "kl": kls,
        "clipfrac": clips,
        "explained_var": explained_var,
        "pg_abs": pgas,
        "pg_loss": pgs,
        "v_loss": vs,
        "steps": stats.get("steps", 0),
        "mean_return": mean_return,
    }
