"""One generation's learning: sample opponents, play, price, train.

Knows the training loop. Knows nothing about promotion or the rated
bot file; returns trained weights and stats for the driver to judge.
"""

from __future__ import annotations

import copy
import gc
import os
import random
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))

import algorithm
import archive
import game_if
import rewards


def _penalty_rng(cfg: dict, gen_index: int, g: int) -> random.Random:
    """Deterministic per-game penalty draw, seeded by (seed, gen, game)."""
    return random.Random(f"{cfg.get('seed', 0)}:{gen_index}:{g}")


def _train_map_for(cfg, i):
    """Map for train game i: first train_games*2 boards 1:1, cycling if
    the pool is shorter (debug pools)."""
    maps = cfg["maps"]
    return maps[i % len(maps)]


def _is_penalty_game(cfg: dict, g: int, gen_index: int = 0) -> bool:
    """Seeded per-game draw penalty: probability 1/N for each game.

    This replaces the every-Nth stride, which synchronized with drill
    rotation and dumped every penalized game onto the same few boards
    (no within-board normal-vs-penalized overlap). The seeded draw is
    reproducible across reruns and spreads penalized games across all
    boards every gen. 0/None/missing disables: behavior byte-identical
    to no penalty."""
    n = cfg.get("train_draw_penalty_every", 0) or 0
    if not n:
        return False
    return _penalty_rng(cfg, gen_index, g).random() < 1.0 / n


def _play_one(args) -> dict:
    """One train game: play, price, record. Thread-safe via archive lock."""
    (cfg, base, chal_id, field, weights, i, role, map_path) = args
    try:
        gen_index = int(chal_id[1:])
    except (ValueError, IndexError):
        gen_index = 0
    rel = f"games/{chal_id}/train{i}"
    out = game_if.play(
        ROOT,
        sys.executable,
        weights,
        game_if.GameConfig(
            map=map_path,
            turns=cfg["turns"],
            temperature=cfg["temperature"],
            player_seed=cfg["seed"] + i,
            engine_seed=1000 + i,
        ),
        base / rel,
        names=field,
    )
    game = out["game"]
    rows = algorithm.compact_records(out["records"][0])  # student seat 0
    rets = rewards.compute_returns(game, 0, rows, rewards.scales_for(role),
                                   role,
                                   draw_as_loss=_is_penalty_game(cfg, i, gen_index),
                                   enable_water_stall=cfg.get("water_stall_tax", False))
    scores = game["score"]
    gid = f"{rel}#{uuid.uuid4().hex[:12]}"  # one play, one id (pairs group back)
    for x in range(len(field)):
        for y in range(x + 1, len(field)):
            archive.record_result(base, field[x], field[y],
                                  scores[x], scores[y], kind="train")
            archive.log_game(base, chal_id, "train", field[x], field[y],
                             scores[x], scores[y],
                             rel + "/logs/0.replay", map=Path(map_path).name,
                             game=gid)
    n_games = cfg["train_games"] * 2
    archive.write_status(base, {
        "phase": "train", "challenger": chal_id,
        "done": i + 1, "total": n_games,
        "last_mean_return": sum(rets) / len(rets) if rets else 0.0,
        "last_game": rel,
    })
    return {"rows": rows, "rets": rets}


def train_generation(cfg: dict, base: Path, champ_id: str, champ_w: dict, role: str = "challenger", parent: str | None = None, opt_state: dict | None = None, anchor: dict | None = None, kl_anchor_beta: float = 0.0, line: int | None = None) -> tuple[str, dict, dict, dict]:
    """Self-play training games -> (challenger id, weights, train stats, opt state).

    The snapshot's parent defaults to the champion; the continuous
    main passes its own last id so parents form chains, not stars.
    Incoming optimizer state (main lineage) is restored before
    training; outgoing state is returned for banking."""
    chal_id = archive.save_checkpoint(base, copy.deepcopy(champ_w), role, parent if parent is not None else champ_id, line=line if role in ("exploiter", "spoiler") else None)
    chal_w = copy.deepcopy(champ_w)
    batch: list = []
    policy = algorithm.new_policy(chal_w)
    opt = algorithm.make_optimizer(policy, lr=cfg["lr"])
    algorithm.load_opt_state(opt, opt_state)
    anchor_pol = None
    if anchor is not None and kl_anchor_beta:
        anchor_pol = algorithm.new_policy(anchor)
        anchor_pol.eval()
    jobs = []
    n_games = cfg["train_games"] * 2
    wcache = {chal_id: chal_w}
    # The field is drawn from a mixture computed ONCE: nash_mixture over
    # the full matrix costs ~40s, so per-game sampling draws from this
    # fixed mixture (pure arithmetic) instead of recomputing every game.
    # 2p-only pools need no mixture at all (k=0 short-circuits).
    seat_counts = [game_if.map_player_count(_train_map_for(cfg, i))
                   for i in range(n_games)]
    mix_ids, mix_p = [], np.array([])
    if any(n > 2 for n in seat_counts):
        _mix = archive.nash_mixture(base)
        mix_ids, mix_p = archive.prune_missing(
            base, list(_mix), np.array([_mix[i] for i in _mix]))
    for i in range(n_games):
        map_path = _train_map_for(cfg, i)
        n_seats = seat_counts[i]
        field = [chal_id] + archive.mixture_draw(
            mix_ids, mix_p, k=n_seats - 1,
            rng=np.random.default_rng(cfg["seed"] + i),
            exclude=(chal_id,))
        weights = []
        for fid in field:
            if fid not in wcache:
                wcache[fid] = archive.load_checkpoint(base, fid)
            weights.append(wcache[fid])
        jobs.append((cfg, base, chal_id, field, weights, i, role,
                     map_path))
    workers = min(cfg.get("workers", 8), len(jobs)) or 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        games = list(pool.map(_play_one, jobs))
    for out in games:
        batch.extend(algorithm.collect(policy, out["rows"], out["rets"]))
    # Free the per-game row holders before the PPO epochs: windows are
    # already compacted to tensors shared with the batch, so games holds
    # only duplicate references plus dict overhead. Peak from here on is
    # tensors alone instead of rows + batch side by side.
    del games
    gc.collect()
    losses, entropies, kls, pgs, vs, anchs, pgas = [], [], [], [], [], [], []
    # Advantage freeze: one baseline per generation with the pre-update
    # value net. Every epoch reuses this triple, so advantages cannot
    # evaporate as the critic fits (recompute-per-minibatch did).
    frozen_adv, frozen_mean, frozen_std = algorithm.frozen_advantages(
        policy, batch)
    for _ in range(cfg["epochs"]):
        stats = algorithm.train_epoch(
            policy, opt, batch,
            clip=cfg["clip"], vf_coef=cfg["vf_coef"],
            entropy_beta=cfg["entropy_beta"], max_norm=cfg["max_norm"],
            minibatch=cfg["minibatch"],
            anchor=anchor_pol, kl_anchor_beta=kl_anchor_beta,
            advantages=frozen_adv, bmean=frozen_mean, bstd=frozen_std,
        )
        losses.append(stats["loss"])
        entropies.append(stats["entropy"])
        kls.append(stats["kl"])
        anchs.append(stats["kl_anchor"])
        pgas.append(stats["pg_abs"])
        pgs.append(stats["pg_loss"])
        vs.append(stats["v_loss"])
    chal_w = algorithm.policy_weights(policy)
    archive.store(base, chal_id, chal_w)
    opt_out = algorithm.serialize_opt(opt)
    mean_return = (
        sum(r for _w, _a, r, _m, _o in batch) / len(batch) if batch else 0.0
    )
    return chal_id, chal_w, {
        "rows": len(batch),
        "losses": losses,
        "entropies": entropies,
        "kl": kls,
        "kl_anchor": anchs,
        "pg_abs": pgas,
        "pg_loss": pgs,
        "v_loss": vs,
        "steps": stats.get("steps", 0),
        "mean_return": mean_return,
    }, opt_out
