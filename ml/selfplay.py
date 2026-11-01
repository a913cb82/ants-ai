"""Mirror self-play: one learner, latest vs latest, single-threaded.

Every tick plays exactly one game: main vs main, both seats running
the current live weights. Both seats' records train the next PPO
micro-batch (AlphaZero trains on every position, not one side).
Every 8th game runs the update.

State is two integers (tick, micro) plus the live weights, Adam blob,
and banked batch on disk. Resume is load + schedule: tick numbers are
persisted at claim and never reused, so a crashed tick's rows simply
stay logged.
"""

from __future__ import annotations

import copy
import json
import random
import signal
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))

import algorithm
import archive
import train

MICRO_BATCH = 8

_SHUTDOWN = False


def _request_shutdown(signum, frame) -> None:
    """Finish the current tick, then stop. kill -9 rolls back one tick."""
    global _SHUTDOWN
    _SHUTDOWN = True


def default_map_pool() -> list[str]:
    """Every playable 2p grid under tools/maps, sorted, deterministic."""
    import mapgen

    return mapgen.default_pool()


def default_config() -> dict:
    maps = default_map_pool()
    return {
        "maps": maps,
        "turns": 250,
        "temperature": 1.0,
        "lr": 1e-3,
        "epochs": 3,
        "arch": "base",
        "clip": 0.2,
        "vf_coef": 0.5,
        "entropy_beta": 0.01,
        "max_norm": 1.0,
        "minibatch": 64,
        "gamma": 0.97,
        "seed": 0,
        "ticks": -1,
        "archive": "ml/archive",
    }


def parse_args(argv: list[str] | None = None) -> dict:
    import argparse

    defaults = default_config()
    p = argparse.ArgumentParser(description="Run mirror self-play.")
    p.add_argument("--maps", nargs="+", default=None)
    p.add_argument("--turns", type=int, default=defaults["turns"])
    p.add_argument("--temperature", type=float, default=defaults["temperature"])
    p.add_argument("--lr", type=float, default=defaults["lr"])
    p.add_argument("--epochs", type=int, default=defaults["epochs"])
    p.add_argument("--arch", choices=("base", "deep"), default=defaults["arch"])
    p.add_argument("--clip", type=float, default=defaults["clip"])
    p.add_argument("--vf-coef", type=float, default=defaults["vf_coef"])
    p.add_argument("--entropy-beta", type=float, default=defaults["entropy_beta"])
    p.add_argument("--max-norm", type=float, default=defaults["max_norm"])
    p.add_argument("--minibatch", type=int, default=defaults["minibatch"])
    p.add_argument("--gamma", type=float, default=defaults["gamma"])
    p.add_argument("--seed", type=int, default=defaults["seed"])
    p.add_argument(
        "--ticks",
        type=int,
        default=defaults["ticks"],
        help="games to play; negative runs forever",
    )
    p.add_argument("--archive", default=defaults["archive"])
    args = p.parse_args(argv)
    return {
        "maps": args.maps if args.maps is not None else defaults["maps"],
        "turns": args.turns,
        "temperature": args.temperature,
        "lr": args.lr,
        "epochs": args.epochs,
        "arch": args.arch,
        "clip": args.clip,
        "vf_coef": args.vf_coef,
        "entropy_beta": args.entropy_beta,
        "max_norm": args.max_norm,
        "minibatch": args.minibatch,
        "gamma": args.gamma,
        "seed": args.seed,
        "ticks": args.ticks,
        "archive": args.archive,
    }


def _live_paths(base: Path) -> tuple[Path, Path]:
    d = base / "live"
    return d / "weights.json", d / "opt.json"


def _pending_path(base: Path) -> Path:
    return base / "live" / "pending.pt"


def bank_pending(base: Path, items: list, arch: str, tick: int | None = None) -> None:
    """Persist unapplied PPO rows (empty clears the bank)."""
    path = _pending_path(base)
    if not items:
        try:
            path.unlink()
        except OSError:
            pass
        return
    algorithm.dump_pending(path, items, arch, tick)


def load_pending(base: Path, arch: str) -> list:
    """Banked rows for this arch, else [] (clean restart)."""
    return algorithm.read_pending(_pending_path(base), arch)


def store_live(base: Path, weights: dict, opt_blob: dict | None) -> None:
    """Persist live training weights + Adam (atomic, old-or-new)."""
    wpath, opath = _live_paths(base)
    wpath.parent.mkdir(parents=True, exist_ok=True)
    archive.atomic_write_json(wpath, weights)
    if opt_blob is None:
        try:
            opath.unlink()
        except OSError:
            pass
    else:
        archive.atomic_write_json(opath, opt_blob)


def load_live(base: Path) -> tuple[dict, dict | None]:
    """Live training weights + Adam (None when never banked)."""
    wpath, opath = _live_paths(base)
    weights = json.loads(wpath.read_text())
    try:
        blob = json.loads(opath.read_text())
    except (OSError, ValueError):
        return weights, None
    return weights, blob


def _claim_tick(base: Path) -> int:
    """Next tick number, persisted at claim: never reused, even by
    restarts. A crashed tick's number is never handed out again, so
    its rows can simply stay logged — no stripping is ever needed."""
    state = archive.load_state(base) or {}
    tick = max(state.get("tick", 0), state.get("next_tick", 0))
    state["next_tick"] = tick + 1
    archive.save_state(base, state)
    return tick


def ensure(base: Path, cfg: dict) -> dict:
    """First start or restart: seed counters, load or mint the net.

    A missing state file seeds the tick past any logged games (an old
    archive keeps its history continuous). A missing live net mints a
    freshly initialized one; existing files are never clobbered."""
    archive.init(base)
    state = archive.load_state(base)
    if state is None:
        tick = 0
        for r in archive.list_games(base):
            t = r.get("tick")
            if isinstance(t, (int, float)):
                tick = max(tick, int(t) + 1)
        state = {"tick": tick, "next_tick": tick, "micro": 0}
        archive.save_state(base, state)
    wpath, _ = _live_paths(base)
    if wpath.exists():
        weights, opt_blob = load_live(base)
        policy = algorithm.new_policy(weights)
    else:
        policy = algorithm.new_policy(None, cfg.get("arch", "base"))
        weights, opt_blob = algorithm.policy_weights(policy), None
        store_live(base, copy.deepcopy(weights), None)
    opt = algorithm.make_optimizer(policy, lr=cfg["lr"])
    algorithm.load_opt_state(opt, opt_blob)
    return {
        "policy": policy,
        "opt": opt,
        "pending": load_pending(base, cfg.get("arch", "base")),
        "lr": cfg["lr"],
    }


def run_tick(cfg: dict, base: Path, live: dict) -> dict:
    """One mirror game: play, log, accumulate, maybe train."""
    import rewards

    rewards.GAMMA = cfg.get("gamma", rewards.GAMMA)
    tick = _claim_tick(base)  # persisted: never reused, even by restarts
    rng = random.Random(f"{cfg.get('seed', 0)}:{tick}")
    map_path = rng.choice(cfg["maps"])
    weights = algorithm.policy_weights(live["policy"])
    played = train._play_one(dict(cfg, tick=tick), base, weights, map_path)
    batch = algorithm.collect(live["policy"], played["rows"], played["rets"])
    live["pending"].extend(batch)
    state = archive.load_state(base)
    micro = state.get("micro", 0) + 1
    update_stats = None
    if micro % MICRO_BATCH == 0:
        update_stats = train.ppo_update(
            live["policy"], live["opt"], live["pending"], cfg
        )
    if update_stats is not None:
        live["pending"] = []
        bank_pending(base, [], cfg.get("arch", "base"))
        store_live(
            base,
            algorithm.policy_weights(live["policy"]),
            algorithm.serialize_opt(live["opt"]),
        )

        def _mean(v):
            return sum(v) / len(v) if v else 0.0

        archive.log_update(
            base,
            {
                "tick": tick,
                "rows": update_stats["rows"],
                "mean_return": update_stats["mean_return"],
                "explained_var": update_stats["explained_var"],
                "loss": _mean(update_stats["losses"]),
                "entropy": _mean(update_stats["entropies"]),
                "kl": _mean(update_stats["kl"]),
                "clipfrac": _mean(update_stats["clipfrac"]),
                "pg_loss": _mean(update_stats["pg_loss"]),
                "v_loss": _mean(update_stats["v_loss"]),
            },
        )
    else:
        # No update this tick: bank the batch so an early exit loses
        # nothing; the next run resumes it like a continued loop.
        bank_pending(base, live["pending"], cfg.get("arch", "base"), tick)
    state["micro"] = micro
    state["tick"] = max(state.get("tick", 0), tick + 1)
    archive.save_state(base, state)
    return {
        "tick": tick,
        "scores": played["scores"],
        "update": update_stats is not None,
    }


def run_loop(cfg: dict, base: Path, ticks: int) -> None:
    """Play ticks (negative = forever). Ctrl-C finishes the tick."""
    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)
    live = ensure(base, cfg)
    done = 0
    while (ticks < 0 or done < ticks) and not _SHUTDOWN:
        run_tick(cfg, base, live)
        done += 1


def main(argv: list[str] | None = None) -> int:
    cfg = parse_args(argv)
    run_loop(cfg, Path(cfg["archive"]), ticks=cfg["ticks"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
