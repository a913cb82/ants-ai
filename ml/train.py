"""League learning: PFSP opponent selection, single games, micro-batch PPO.

Knows the training loop. Knows nothing about scheduling, promotion, or
the rated bot file; each call plays or trains for exactly one learner
and returns stats for the scheduler to judge.

PPO math is byte-identical to the retired generation path: one frozen
baseline per update (frozen_advantages), then N epochs of train_epoch
over the same batch. Role configs map the four league learners onto
pricing scales (rewards.py untouched: unknown roles get base scales) and
PFSP policies.
"""

from __future__ import annotations

import random
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))

import algorithm
import archive
import game_if
import pfsp
import rewards

#: League learner -> training config. Pricing roles reuse the legacy
#: scale tables (rewards.py knows "exploiter"/"challenger"; "challenger"
#: is absent from ROLE_OVERRIDES so the main trains on base scales,
#: exactly like the old main line). Snapshot roles are the going-forward
#: manifest roles from the league plan. ME tracks the live main
#: (threshold) and otherwise its snapshots; LEs track the pool; only exploiters reset.
ROLE_CONFIGS = {
    "main": {"pricing": "challenger", "policy": "main",
             "snapshot_role": "main-snapshot", "target": None,
             "resets": False},
    "me": {"pricing": "exploiter", "policy": "me",
           "snapshot_role": "me", "target": "main", "resets": True},
    "le-a": {"pricing": "exploiter", "policy": "le",
             "snapshot_role": "le", "target": "pool", "resets": True},
    "le-b": {"pricing": "exploiter", "policy": "le",
             "snapshot_role": "le", "target": "pool", "resets": True},
}

#: Deterministic round-robin training order (mirrors archive.SCHEDULER_ORDER).
LEARNER_ORDER = ("main", "me", "le-a", "le-b")


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
    # Display names ARE attribution ids: every seat id is in-universe
    # (main / me / le-a / le-b / mainN / meN / le-aN / le-bN / legacy
    # g-ids), so replays, tables, and records all show the same names.
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
    kind = cfg.get("game_kind", "train")
    for x in range(len(field)):
        for y in range(x + 1, len(field)):
            archive.record_result(base, field[x], field[y],
                                  scores[x], scores[y], kind=kind)
            archive.log_game(base, chal_id, kind, field[x], field[y],
                             scores[x], scores[y],
                             rel + "/logs/0.replay", map=Path(map_path).name,
                             game=gid)
    n_games = cfg.get("train_games", 0) * 2
    archive.write_status(base, {
        "phase": "train", "challenger": chal_id,
        "done": i + 1, "total": n_games,
        "last_mean_return": sum(rets) / len(rets) if rets else 0.0,
        "last_game": rel,
    })
    return {"rows": rows, "rets": rets, "scores": list(scores)}


def select_opponent(base: Path, learner: str, state: dict,
                    records: pfsp.Records,
                    rng: random.Random,
                    sample_id: str | None = None) -> str:
    """PFSP opponent for one learner tick (pure sampling, no I/O beyond
    the manifest read). Main runs the mini-AlphaStar 3-branch dispatch
    (squared / verification / self-play); ME stays on the live main
    while beating it, else hunts the main's snapshots; LEs probe the
    pool for holes. Frozen candidates are manifest members only; the
    live main is facable by ME and by main's self-play branch (loaded
    live, never frozen).

    sample_id is the seat identity the learner's games log under (the
    bare slot id, "main" for main): records are keyed by it, so it must
    drive the win-fraction lookups and self-exclusion. Defaults to the
    slot for callers without one."""
    members = archive.members(base)
    candidates = [m["id"] for m in members
                  if isinstance(m.get("id"), str)]
    # Live weights move under training: the live head and live slots
    # are never frozen opponents (they have no frozen weights file;
    # sampling them would face the wrong weights). Snapshots and
    # admitted copies stay in the pool. The live main stays facable:
    # ME and main's self-play branch load it live (see run_tick).
    live_ids = {"main"}
    for exp in state.get("exploiters", {}).values():
        if isinstance(exp.get("id"), str):
            live_ids.add(exp["id"])
    candidates = [c for c in candidates if c not in live_ids]
    policy = ROLE_CONFIGS[learner]["policy"]
    live = sample_id if sample_id is not None else learner
    snapshots = list(state.get("main_snapshots", []) or [])
    admitted = [m["id"] for m in members
                if m.get("role") == "admitted"
                and isinstance(m.get("id"), str)]
    if policy == "main":
        return pfsp.main_sample(live, "main", candidates, snapshots,
                                admitted, records, rng)
    if policy == "me":
        return pfsp.me_sample(live, "main", snapshots, records, rng)
    return pfsp.le_sample(live, candidates, records, rng)


def ppo_update(policy, opt, batch: list, cfg: dict, anchor=None,
               kl_anchor_beta: float = 0.0) -> dict:
    """Micro-batch PPO: one frozen baseline, then cfg["epochs"] passes.

    Identical math to the retired generation tail: frozen_advantages
    freezes one baseline per update so advantages cannot evaporate as
    the critic fits, then every epoch reuses that triple. Returns the
    same stats dict the generation path reported."""
    # Advantage freeze: one baseline per update with the pre-update
    # value net. Every epoch reuses this triple, so advantages cannot
    # evaporate as the critic fits (recompute-per-minibatch did).
    frozen_adv, frozen_mean, frozen_std = algorithm.frozen_advantages(
        policy, batch)
    losses, entropies, kls, anchs, pgas, pgs, vs = [], [], [], [], [], [], []
    for _ in range(cfg["epochs"]):
        stats = algorithm.train_epoch(
            policy, opt, batch,
            clip=cfg["clip"], vf_coef=cfg["vf_coef"],
            entropy_beta=cfg["entropy_beta"], max_norm=cfg["max_norm"],
            minibatch=cfg["minibatch"],
            anchor=anchor, kl_anchor_beta=kl_anchor_beta,
            advantages=frozen_adv, bmean=frozen_mean, bstd=frozen_std,
        )
        losses.append(stats["loss"])
        entropies.append(stats["entropy"])
        kls.append(stats["kl"])
        anchs.append(stats["kl_anchor"])
        pgas.append(stats["pg_abs"])
        pgs.append(stats["pg_loss"])
        vs.append(stats["v_loss"])
    mean_return = (
        sum(r for _w, _a, r, _m, _o in batch) / len(batch) if batch else 0.0
    )
    return {
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
    }
