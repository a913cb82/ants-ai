"""Mirror self-play: one learner, latest vs latest.

Every tick plays exactly one game: main vs main (vs main ...), all
seats running the current live weights. Every seat's records train
the next PPO micro-batch (AlphaZero trains on every position, not one
side). The update trains in a background thread on a weights snapshot taken
at the boundary, so dispatch never stalls; games played mid-update
train from weights at most one update old (bounded staleness of 1).

State is two integers (tick, micro) plus the live weights, Adam blob,
and banked batch on disk. Resume is load + schedule: tick numbers are
persisted at claim and never reused, so a crashed tick's rows simply
stay logged.
"""

from __future__ import annotations

import copy
import random
import signal
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))

import algorithm
import archive
import train
from mirror_bank import (
    MICRO_BATCH,
    _bg_busy,
    _claim_tick,
    _drop_banked,
    _pending_path,
    _pending_shards,
    _select_dispatch,
    _take_batch,
    bank_pending,
    load_banked,
    load_live,
    load_pending,
    store_live,
)

__all__ = [
    "_bg_busy",
    "_claim_tick",
    "_drop_banked",
    "_pending_path",
    "_pending_shards",
    "_select_dispatch",
    "_take_batch",
    "bank_pending",
    "default_config",
    "default_map_pool",
    "ensure",
    "load_banked",
    "load_live",
    "load_pending",
    "parse_args",
    "run_loop",
    "run_tick",
    "store_live",
]

_SHUTDOWN = False



def _request_shutdown(signum, frame) -> None:
    """Finish the current tick, then stop. kill -9 rolls back one tick."""
    global _SHUTDOWN
    _SHUTDOWN = True



def default_map_pool() -> list[str]:
    """Every map in the four upstream dirs (any seat count), sorted."""
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
        "concurrency": 1,
        "ticks": -1,
        "archive": "bots/alphaant/archive",
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
        "--concurrency",
        type=int,
        default=defaults["concurrency"],
        help="games in flight at once (default 1 = serial; "
        "updates still fire every 16 completions)",
    )
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
        "concurrency": args.concurrency,
        "ticks": args.ticks,
        "archive": args.archive,
    }



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
    pending, banked = load_banked(base, cfg.get("arch", "base"))
    return {
        "policy": policy,
        "opt": opt,
        "pending": pending,
        "banked": banked,
        "lr": cfg["lr"],
        "bg": None,  # background update slot; None until first boundary
    }



def _play_tick(cfg: dict, base: Path, weights: dict, tick: int, map_path: str) -> dict:
    """Play + price one tick. Thread-safe: subprocess games in per-tick
    dirs, pricing is pure, the game log shares the append lock.

    No shared mutation: weights arrive as a snapshot dict, the policy
    object stays in the dispatching thread (collect runs there)."""
    import rewards

    rewards.GAMMA = cfg.get("gamma", rewards.GAMMA)
    played = train._play_one(dict(cfg, tick=tick), base, weights, map_path)
    return {"tick": tick, "played": played}



def _finish_tick(cfg: dict, base: Path, live: dict, result: dict) -> dict:
    """Accumulate one completed game, maybe train. Main thread only:
    policy forward, pending batch, counters, weights, Adam all mutate
    here and nowhere else."""
    tick = result["tick"]
    played = result["played"]
    if played.get("scoreless", False):
        # Hills-only diet: all-zero returns teach nothing, so the game
        # banks no rows and the cadence counts scoring games only. The
        # game stays logged (draws are board history), the tick still
        # advances, and a finished update still lands.
        _bg_swap(cfg, base, live, block=False)
        state = archive.load_state(base)
        state["tick"] = max(state.get("tick", 0), tick + 1)
        archive.save_state(base, state)
        return {"tick": tick, "scores": played["scores"], "update": False}
    batch = algorithm.collect(live["policy"], played["rows"], played["rets"])
    live["pending"].extend(batch)
    bank_pending(base, batch, cfg.get("arch", "base"), tick)
    live["banked"].append((tick, len(batch)))
    state = archive.load_state(base)
    micro = state.get("micro", 0) + 1
    _bg_swap(cfg, base, live, block=False)  # land a finished update, if any
    update = False
    if micro % MICRO_BATCH == 0:
        update = True
        # Backpressure: at most one update runs; when the learner is the
        # bottleneck the loop waits here instead of piling up stale games.
        _bg_swap(cfg, base, live, block=True)
        _bg_start(cfg, live, tick)
    # No whole-list bank here: the tick's shard is already written above,
    # so a crash loses only in-flight games, as before, at O(game) cost.
    state["micro"] = micro
    state["tick"] = max(state.get("tick", 0), tick + 1)
    archive.save_state(base, state)
    return {
        "tick": tick,
        "scores": played["scores"],
        "update": update,
    }



def _bg_start(cfg: dict, live: dict, tick: int) -> None:
    """Snapshot live weights+Adam and train them in a daemon thread.

    The batch is the pending prefix (own list; items shared read-only —
    the main thread only ever appends). Staleness is bounded: games
    played mid-update train from weights at most one update old."""
    bg = live["bg"]
    if bg is None:
        bg = live["bg"] = {
            "policy": algorithm.new_policy(None, cfg.get("arch", "base")),
            "opt": None,
            "busy": False,
        }
        bg["opt"] = algorithm.make_optimizer(bg["policy"], lr=live["lr"])
    bg["policy"].load_state_dict(live["policy"].state_dict())
    bg["opt"].load_state_dict(live["opt"].state_dict())
    if live["banked"]:
        taken, n0 = _take_batch(
            [n for _t, n in live["banked"]], BATCH_CAP_ROWS
        )
        consumed = [t for t, _n in live["banked"][:taken]]
        live["banked"] = live["banked"][taken:]
    else:
        # Untracked rows (should not happen: bank and manifest grow
        # together): train everything, drop nothing.
        n0, consumed = len(live["pending"]), []
    batch = live["pending"][:n0]
    bg.update(
        n0=n0, tick=tick, started=time.perf_counter(),
        stats=None, seconds=None, busy=True, done=threading.Event(),
        banked=consumed,
    )

    def _run() -> None:
        try:
            bg["stats"] = train.ppo_update(
                bg["policy"], bg["opt"], batch, cfg
            )
        finally:
            bg["seconds"] = time.perf_counter() - bg["started"]
            bg["done"].set()

    threading.Thread(target=_run, daemon=True).start()



def _bg_swap(cfg: dict, base: Path, live: dict, block: bool) -> bool:
    """Land a finished background update: swap weights+Adam into live,
    log with its wall seconds, consume its pending prefix. No-op when
    nothing is running (or running and block is False)."""
    bg = live.get("bg")
    if not bg or not bg["busy"]:
        return False
    if not bg["done"].wait(timeout=None if block else 0):
        return False
    live["policy"].load_state_dict(bg["policy"].state_dict())
    live["opt"].load_state_dict(bg["opt"].state_dict())
    store_live(
        base,
        algorithm.policy_weights(live["policy"]),
        algorithm.serialize_opt(live["opt"]),
    )

    def _mean(v):
        return sum(v) / len(v) if v else 0.0

    stats = bg["stats"]
    archive.log_update(
        base,
        {
            "tick": bg["tick"],
            "rows": stats["rows"],
            "mean_return": stats["mean_return"],
            "explained_var": stats["explained_var"],
            "loss": _mean(stats["losses"]),
            "entropy": _mean(stats["entropies"]),
            "kl": _mean(stats["kl"]),
            "clipfrac": _mean(stats["clipfrac"]),
            "pg_loss": _mean(stats["pg_loss"]),
            "v_loss": _mean(stats["v_loss"]),
            "update_seconds": bg["seconds"],
        },
    )
    del live["pending"][: bg["n0"]]
    _drop_banked(base, bg["banked"])
    bg["busy"] = False
    return True



def _drain_bg(cfg: dict, base: Path, live: dict) -> None:
    """Wait out a running background update and land it, if any."""
    _bg_swap(cfg, base, live, block=True)



def run_tick(cfg: dict, base: Path, live: dict) -> dict:
    """One mirror game: play, log, accumulate, maybe train.

    Serial: drains any background update before returning, so one call
    is one fully-applied tick, exactly as before."""
    tick = _claim_tick(base)  # persisted: never reused, even by restarts
    rng = random.Random(f"{cfg.get('seed', 0)}:{tick}")
    map_path = rng.choice(cfg["maps"])
    weights = algorithm.policy_weights(live["policy"])
    rep = _finish_tick(
        cfg, base, live, _play_tick(cfg, base, weights, tick, map_path)
    )
    _drain_bg(cfg, base, live)
    return rep



def _dispatch_tick(
    cfg: dict, base: Path, live: dict, pool, tick: int, map_path: str
) -> object:
    """Claim a tick and submit its game: the weights snapshot is live,
    so training progress reaches games even mid-update."""
    _claim_tick(base)  # persisted: never reused, even by restarts
    weights = algorithm.policy_weights(live["policy"])
    return pool.submit(_play_tick, cfg, base, weights, tick, map_path)



def run_loop(cfg: dict, base: Path, ticks: int) -> None:
    """Play ticks (negative = forever). Ctrl-C stops dispatching new
    games, drains the in-flight ones and the background update, exits."""
    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)
    live = ensure(base, cfg)
    concurrency = max(1, cfg.get("concurrency", 1))
    done = dispatched = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        in_flight = {}
        while (ticks < 0 or done < ticks) and not _SHUTDOWN:
            while (
                len(in_flight) < concurrency
                and (ticks < 0 or dispatched < ticks)
                and not _SHUTDOWN
            ):
                sel = _select_dispatch(
                    base, cfg, sum(in_flight.values()), len(live["pending"])
                )
                if sel is None:
                    break  # over budget: wait for room, then retry
                tick, map_path, seats = sel
                in_flight[_dispatch_tick(cfg, base, live, pool, tick, map_path)] = seats
                dispatched += 1
            if not in_flight:
                if ticks >= 0 and done >= ticks:
                    break
                # Stalled with nothing running: land any finished update
                # and force-start a drain when backlogged and idle, so
                # the backlog gate can never deadlock the loop.
                _bg_swap(cfg, base, live, block=False)
                if _pending_stalled(cfg, len(live["pending"])) and not _bg_busy(live):
                    _bg_start(cfg, live, _prospective_tick(base))
                time.sleep(1)
                continue
            finished, _ = wait(
                in_flight, timeout=5, return_when=FIRST_COMPLETED
            )
            _bg_swap(cfg, base, live, block=False)  # land between games
            for fut in finished:
                del in_flight[fut]
                # A failed game propagates, as in the serial loop; its
                # row simply never logs while the rest stay valid.
                _finish_tick(cfg, base, live, fut.result())
                done += 1
    _drain_bg(cfg, base, live)



def main(argv: list[str] | None = None) -> int:
    cfg = parse_args(argv)
    run_loop(cfg, Path(cfg["archive"]), ticks=cfg["ticks"])
    return 0

