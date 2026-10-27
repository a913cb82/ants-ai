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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))

import algorithm
import archive
import game_if
import rewards


def _train_opponents(base: Path, student: str, champ_id: str, n: int,
                     seed: int, champ_share: float = 0.25) -> list[str]:
    """Frontier rivals with champ-share slots first.

    The eval target must be trained against, not merely whitelisted:
    PFSP weights can starve a whitelisted champ 0/60 (round-40
    forensics — Laplace 0.55 loses to beat-you 1.05 every draw).
    The first round(n * champ_share) slots are the champ (first slot
    always the champ when share > 0: the round-40 guaranteed slot);
    the rest are frontier-sampled as before. share 0.0 waives the
    guarantee (zero champ slots); 1.0 fills every slot with the champ.
    At the default (n=4, share 0.25) this is exactly slot 0 champ +
    3 PFSP draws with seeds seed+g — byte-identical to the old code."""
    if n <= 0:
        return []
    if champ_share <= 0:
        n_champ = 0
    else:
        n_champ = max(1, round(n * champ_share))
        n_champ = min(n_champ, n)
    opps = [champ_id] * n_champ
    for g in range(n_champ, n):
        # PFSP draws keep the legacy seed stride (seed+g with the same
        # game index g), so train-4 runs are byte-identical to before.
        opps.append(archive.sample_opponents(
            base, student, 1, seed=seed + g, include=(champ_id,))[0])
    return opps


def _penalty_rng(cfg: dict, gen_index: int, g: int) -> random.Random:
    """Deterministic per-game penalty draw, seeded by (seed, gen, game)."""
    return random.Random(f"{cfg.get('seed', 0)}:{gen_index}:{g}")


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
    (cfg, base, chal_id, opp_id, me_w, other_w, slot, g, role,
     map_path) = args
    try:
        gen_index = int(chal_id[1:])
    except (ValueError, IndexError):
        gen_index = 0
    rel = f"games/{chal_id}/train{g}_slot{slot}"
    first, second = (chal_id, opp_id) if slot == 0 else (opp_id, chal_id)
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
    rows = algorithm.compact_records(
        out["records_a"] if slot == 0 else out["records_b"])
    rets = rewards.compute_returns(game, slot, rows, rewards.scales_for(role),
                                   role,
                                   draw_as_loss=_is_penalty_game(cfg, g, gen_index))
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


def train_generation(cfg: dict, base: Path, champ_id: str, champ_w: dict, role: str = "challenger", parent: str | None = None, opt_state: dict | None = None, anchor: dict | None = None, kl_anchor_beta: float = 0.0, student: str | None = None, line: int | None = None) -> tuple[str, dict, dict, dict]:
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
    try:
        gen_num = int(chal_id[1:])
    except (ValueError, IndexError):
        gen_num = 0
    drill_maps = archive.next_drill_maps(
        base, cfg["maps"], cfg["train_games"], gen_num)
    for g, opp_id in enumerate(_train_opponents(
            base, student or champ_id, champ_id, cfg["train_games"],
            cfg["seed"], cfg.get("champ_share", 0.25))):
        opp_w = archive.load_checkpoint(base, opp_id)
        for slot in (0, 1):
            me_w, other_w = (chal_w, opp_w) if slot == 0 else (opp_w, chal_w)
            jobs.append((cfg, base, chal_id, opp_id, me_w, other_w, slot,
                         g, role, drill_maps[g]))
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
