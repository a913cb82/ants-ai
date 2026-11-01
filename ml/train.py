"""Mirror self-play: one game, one PPO micro-batch step.

Knows the training loop. Each call plays exactly one latest-vs-latest
game on the map's player count (any seat count, all main) and returns
every seat's records for the batch (AlphaZero trains on every position,
not one side).

PPO math is byte-identical to the retired generation path: one frozen
baseline per update (frozen_advantages), then N epochs of train_epoch
over the same batch. Pricing is the one diet (rewards.py base scales),
the only diet there is."""

from __future__ import annotations

import random
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


def _cap_rows(rows: list, rets: list, cfg: dict) -> tuple[list, list]:
    """Uniform seed:tick subsample of a game's priced rows to ROW_CAP.

    Small games pass through whole; big ones keep a random subset with
    returns attached, so pricing (computed on full trajectories) stays
    exact while RAM and batch composition stay bounded."""
    if len(rows) <= ROW_CAP:
        return rows, rets
    rng = random.Random(f"{cfg.get('seed', 0)}:{cfg['tick']}")
    keep = sorted(rng.sample(range(len(rows)), ROW_CAP))
    return [rows[i] for i in keep], [rets[i] for i in keep]


#: One diet for every seat: base scales, no roles, no overrides.
ROW_CAP = 4096  # max batch rows per game: 20k-row 250-turn tables
# would otherwise dominate RAM (pending + transients OOM-killed a run
# at 11GB) and the batch. Uniform seed:tick subsample keeps every
# decision equally likely, so the objective is unchanged in expectation
# and each game weighs the same no matter its size.
def _play_one(cfg: dict, base: Path, weights: dict, map_path: str) -> dict:
    """One mirror game: latest vs latest (vs latest ...), all seats train.

    Seats run the same weights; every seat's decision records and
    seat-perspective returns accumulate into the batch. One row is
    logged per game; the tick IS the game number (replay dirs and both
    seeds key on it)."""
    tick = cfg["tick"]
    rel = f"games/main/tick{tick}"
    n = game_if.map_player_count(map_path)
    field = ["main"] * n
    out = game_if.play(
        ROOT,
        sys.executable,
        [weights] * n,  # one entry per seat; all seats same net
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
    rows, rets, misses = [], [], []
    for s in range(n):
        recs = algorithm.compact_records(out["records"][s])
        miss, problems = rewards.trace_report(game, s, recs)
        if problems:
            # Mask breach or ghost: the join should be exact here, so a
            # problem is a bug, not noise. Raise LOUD: the tick fails,
            # the row never logs, the trainer halts for a human.
            # Order-lost infra noise only counts toward misses.
            raise ValueError(f"tick{tick} seat{s}: {'; '.join(problems)}")
        misses.append(miss)
        rows.extend(recs)
        rets.extend(rewards.compute_returns(game, s, recs, scales))
    rows, rets = _cap_rows(rows, rets, cfg)
    scores = list(game["score"])
    gid = f"{rel}#{uuid.uuid4().hex[:12]}"  # one play, one id
    # Behavior facts, parsed once per game from the played game dict:
    # per-seat food/kills/army over owner indices.
    behavior = None
    if isinstance(game, dict):
        try:
            behavior = archive.behavior_from_replay(
                game.get("replaydata"),
                n=n,
                length=game.get("length", game.get("game_length")),
            )
        except Exception:
            behavior = None
    now = time.time()
    kw: dict = {"t": now, "tick": tick}
    if behavior is not None:
        kw["food"] = list(behavior["food"][:n])
        kw["kills"] = list(behavior["kills"][:n])
        kw["army"] = list(behavior["army"][:n])
        kw["length"] = behavior["length"]
    kw["trace_miss"] = sum(misses) / len(misses) if misses else 0.0
    archive.log_game(
        base,
        field,
        scores,
        rel + "/logs/0.replay",
        map=Path(map_path).name,
        game=gid,
        **kw,
    )
    return {"rows": rows, "rets": rets, "scores": list(scores)}


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
