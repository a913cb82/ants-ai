"""One automated generation: train, evaluate, publish.

Thin orchestration over train.py and evaluate.py. run_generation has no
side effects beyond the archive: file writes and git happen in publish,
only when the scripted rule accepts. The rated bot file changes only
on promotion.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))

import archive
import evaluate
import model
import train

BOT_WEIGHTS = ROOT / "bots" / "alphaant" / "weights.json"


def default_map_pool() -> list[str]:
    """Every playable 2p grid under tools/maps, sorted, deterministic.

    ~150 maps: upstream grids (maze/random_walk/cell_maze/tutorial)
    plus the generated symmetric set. Rotation in train/eval cycles
    the pool; slot alternation keeps asymmetric layouts fair."""
    import mapgen

    return mapgen.default_pool()


def split_pool(pool: list[str]) -> tuple[list[str], list[str]]:
    """Train pool + held-out eval pool. Every 13th map is held (~11).

    Deterministic, disjoint, union == pool. Evals run on maps the
    challenger never trained on, so eval W/D measures generalization
    instead of memorization. Pools under 13 maps hold nothing out."""
    held = pool[::13] if len(pool) >= 13 else []
    excluded = set(held)
    return [m for m in pool if m not in excluded], held


def default_config() -> dict:
    train_maps, held_maps = split_pool(default_map_pool())
    return {
        "maps": train_maps,
        "held_maps": held_maps,
        "turns": 250,
        "turns": 250,
        "train_games": 4,
        "eval_games": 20,
        "temperature": 1.0,
        "lr": 1e-3,
        "epochs": 3,
        "arch": "base",
        "workers": 8,
        "clip": 0.2,
        "vf_coef": 0.5,
        "entropy_beta": 0.01,
        "max_norm": 1.0,
        "minibatch": 64,
        "gamma": 0.97,
        "promote_threshold": 0.5,
        "seed": 0,
        "init_weights": None,
        "eval_turns": None,
        "archive": "ml/archive",
        "commit": True,
    }


def parse_args(argv: list[str] | None = None) -> dict:
    import argparse

    defaults = default_config()
    p = argparse.ArgumentParser(description="Run one automated generation.")
    p.add_argument("--maps", nargs="+", default=None)
    p.add_argument("--turns", type=int, default=defaults["turns"])
    p.add_argument("--train-games", type=int, default=defaults["train_games"])
    p.add_argument("--eval-games", type=int, default=defaults["eval_games"])
    p.add_argument("--temperature", type=float, default=defaults["temperature"])
    p.add_argument("--lr", type=float, default=defaults["lr"])
    p.add_argument("--epochs", type=int, default=defaults["epochs"])
    p.add_argument("--arch", choices=("base", "deep"), default=defaults["arch"])
    p.add_argument("--workers", type=int, default=defaults["workers"])
    p.add_argument("--clip", type=float, default=defaults["clip"])
    p.add_argument("--vf-coef", type=float, default=defaults["vf_coef"])
    p.add_argument("--entropy-beta", type=float, default=defaults["entropy_beta"])
    p.add_argument("--max-norm", type=float, default=defaults["max_norm"])
    p.add_argument("--minibatch", type=int, default=defaults["minibatch"])
    p.add_argument("--gamma", type=float, default=defaults["gamma"])
    p.add_argument("--promote-threshold", type=float,
                   default=defaults["promote_threshold"])
    p.add_argument("--seed", type=int, default=defaults["seed"])
    p.add_argument("--init-weights", default=defaults["init_weights"],
                     help="JSON weights seeding the gen-0 champion "
                     "(e.g. BC-from-pros); fresh archives only")
    p.add_argument("--eval-turns", type=int, default=defaults["eval_turns"],
                     help="exam game length (default: --turns); longer "
                     "than training so wars have time to resolve")
    p.add_argument("--archive", default=defaults["archive"])
    p.add_argument("--commit", action=argparse.BooleanOptionalAction,
                   default=defaults["commit"])
    args = p.parse_args(argv)
    if args.maps is None:
        train_maps, held_maps = defaults["maps"], defaults["held_maps"]
    else:
        # Custom pool: re-split so evals stay on unseen maps.
        train_maps, held_maps = split_pool(sorted(set(args.maps)))
    return {
        "maps": train_maps,
        "held_maps": held_maps,
        "turns": args.turns,
        "train_games": args.train_games,
        "eval_games": args.eval_games,
        "temperature": args.temperature,
        "lr": args.lr,
        "epochs": args.epochs,
        "arch": args.arch,
        "workers": args.workers,
        "clip": args.clip,
        "vf_coef": args.vf_coef,
        "entropy_beta": args.entropy_beta,
        "max_norm": args.max_norm,
        "minibatch": args.minibatch,
        "gamma": args.gamma,
        "promote_threshold": args.promote_threshold,
        "seed": args.seed,
        "init_weights": args.init_weights,
        "eval_turns": args.eval_turns,
        "archive": args.archive,
        "commit": args.commit,
    }


def _random_weights(seed: int, arch: str) -> dict:
    import torch

    torch.manual_seed(seed)
    return model.state_dict_to_lists(model.CNNPolicy(arch=arch))


def _load_critic(base: Path) -> dict:
    """Last generation's value-head weights, or {}.

    The critic is training apparatus, not the agent: the actor always
    restarts from the champion (honest league comparison; evals use
    the policy only), but the baseline persists across generations
    instead of re-learning from zeros every 3 epochs."""
    try:
        data = json.loads((base / "critic.json").read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def append_history(base: Path, entry: dict) -> None:
    """Append one generation summary; the dashboard reads this for curves."""
    archive.append_jsonl(base / "history.jsonl", entry)


def read_history(base: Path) -> list[dict]:
    """Generation summaries; skips malformed lines like list_games."""
    return archive.read_jsonl(
        base / "history.jsonl",
        lambda row: isinstance(row, dict),
    )


def publish(base: Path, report: dict, commit: bool) -> None:
    """Champion pointer + rated weights + optional git commit."""
    archive.set_champion(base, report["challenger"])
    archive.atomic_write_json(BOT_WEIGHTS, report["challenger_weights"])
    if commit:
        subprocess.run(["git", "-C", str(ROOT), "add", str(BOT_WEIGHTS)], check=True)
        subprocess.run(
            ["git", "-C", str(ROOT), "commit", "-m",
             f"ml: promote {report['challenger']} over {report['champion']} "
             f"(win-rate {report['eval']['win_rate']:.2f}, "
             f"nash {report['nash'].get(report['challenger'], 0.0):.2f})"],
            check=True,
        )


def run_generation(cfg: dict, base: Path, commit: bool = True) -> dict:
    import rewards

    started = time.time()
    archive.init(base)
    rewards.GAMMA = cfg.get("gamma", rewards.GAMMA)
    champ_id = archive.get_champion(base)
    if champ_id is None:
        init = cfg.get("init_weights")
        if init:
            # Supervised start (e.g. BC-from-pros): generation zero begins
            # from learned weights instead of random. Fresh archives only.
            champ_w = json.loads(Path(init).read_text())
        else:
            champ_w = _random_weights(cfg["seed"], cfg.get("arch", "base"))
        champ_id = archive.save_checkpoint(base, champ_w, "main", None)
        archive.set_champion(base, champ_id)
    else:
        champ_w = archive.load_checkpoint(base, champ_id)
    gen_index = len(read_history(base))
    exploiter = gen_index % 3 == 2
    start_w = (
        _random_weights(cfg["seed"] + gen_index, cfg.get("arch", "base"))
        if exploiter else champ_w
    )
    critic = _load_critic(base)
    if critic:
        # warm-start the baseline only; actor keys stay champ (or fresh).
        start_w = {**start_w,
                   **{k: v for k, v in critic.items()
                      if k in start_w and model.is_critic_key(k)}}
    chal_id, chal_w, train_stats = train.train_generation(
        cfg, base, champ_id, start_w,
        role="exploiter" if exploiter else "challenger")
    ev = evaluate.evaluate(cfg, base, chal_id, chal_w, champ_id, champ_w,
                             map_offset=gen_index)
    archive.atomic_write_json(
        base / "critic.json",
        {k: v for k, v in chal_w.items() if model.is_critic_key(k)})
    mix = archive.nash_mixture(base)
    promoted = evaluate.should_promote(
        ev["wins"], ev["draws"], ev["games"],
        mix.get(chal_id, 0.0), mix.get(champ_id, 0.0), cfg["promote_threshold"],
    )
    finished = time.time()
    report = {
        "champion": champ_id,
        "challenger": chal_id,
        "challenger_weights": chal_w,
        "train": train_stats,
        "eval": ev,
        "nash": mix,
        "promoted": promoted,
        "exploiter": exploiter,
        "started_at": started,
        "finished_at": finished,
        "duration_s": round(finished - started, 1),
        "config": cfg,
    }
    archive.atomic_write_json(base / "last_report.json", report)
    append_history(base, {k: v for k, v in report.items()
                           if k != "challenger_weights"})
    if promoted:
        publish(base, report, commit)
    archive.write_status(base, {
        "phase": "done", "challenger": chal_id,
        "champion": archive.get_champion(base),
        "promoted": promoted,
        "exploiter": exploiter,
    })
    return report


def main(argv: list[str] | None = None) -> dict:
    cfg = parse_args(argv)
    return run_generation(cfg, Path(cfg["archive"]), commit=cfg["commit"])


if __name__ == "__main__":
    report = main()
    print(json.dumps({k: v for k, v in report.items()
                      if k not in ("nash", "challenger_weights")}, indent=1))
