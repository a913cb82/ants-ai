"""Continuous league scheduler: perpetual round-robin, no generations.

Four persistent learners (main, me, le-a, le-b) take equal turns. Each
tick plays exactly ONE game for the scheduled learner: a PFSP opponent
is sampled from frozen snapshots, the game is logged as the canonical
record, the learner's rows accumulate into its micro-batch, and every
8th own-game runs a PPO micro-batch update. Every 80th own-game freezes
a permanent snapshot; main snapshots are measured against the frozen
anchor ladder (no training). Exploiters are admitted on sustained >60%
over their last 40, or reset to g000 after a 400-game drought.

Invariants (league plan, verbatim):
- One game trains exactly one learner; opponents are always frozen snapshots.
- Anchor games carry no gradient (measurement only).
- Same net, same PPO, all roles; only diet (opponents) and job differ.
"""

from __future__ import annotations

import copy
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))

import algorithm
import archive
import measure
import train

#: Live learners and their matrix/training ids. These ids are NOT
#: manifest members: they accumulate the canonical record in the matrix
#: (member_game_counts covers matrix-only ids) while snapshots -- the
#: permanent, frozen population -- append as manifest rows.
LEARNERS = ("main", "me", "le-a", "le-b")

#: Micro-batch PPO every N own-games per learner.
MICRO_BATCH = archive.MICRO_BATCH_SIZE

#: Permanent snapshot every N own-games per learner (~1 old generation).
SNAPSHOT_EVERY = 80

#: Admission: last-40 window mean above this vs the role target.
ADMISSION_RATE = 0.6


def default_map_pool() -> list[str]:
    """Every playable 2p grid under tools/maps, sorted, deterministic."""
    import mapgen

    return mapgen.default_pool()


def split_pool(pool: list[str]) -> tuple[list[str], list[str]]:
    """Train pool + held-out pool. Every 13th map is held (~11).

    Deterministic, disjoint, union == pool. Kept for the archived
    generation rows and pool-health tooling; the scheduler plays one
    pool (there is no separate exam to hold maps out for)."""
    held = pool[::13] if len(pool) >= 13 else []
    return [m for m in pool if m not in held], held


def default_config() -> dict:
    maps = default_map_pool()
    return {
        "maps": maps,
        "turns": 250,
        "train_draw_penalty_every": 0,
        "water_stall_tax": False,
        "temperature": 1.0,
        "lr": 1e-3,
        "epochs": 3,
        "arch": "base",
        "workers": 8,
        "clip": 0.2,
        "vf_coef": 0.5,
        "entropy_beta": 0.01,
        "kl_anchor_beta": 0.0,
        "max_norm": 1.0,
        "minibatch": 64,
        "gamma": 0.97,
        "seed": 0,
        "ticks": -1,
        "main_source": "g1732",
        "g000": "g000",
        "anchors": [],
        "archive": "ml/archive",
    }


def parse_args(argv: list[str] | None = None) -> dict:
    import argparse

    defaults = default_config()
    p = argparse.ArgumentParser(description="Run the continuous league.")
    p.add_argument("--maps", nargs="+", default=None)
    p.add_argument("--turns", type=int, default=defaults["turns"])
    p.add_argument("--train-draw-penalty-every", type=int,
                   default=defaults["train_draw_penalty_every"],
                   help="every Nth train game prices draws as losses "
                   "(anti-turtle); 0 disables")
    p.add_argument("--water-stall-tax", action=argparse.BooleanOptionalAction,
                   default=defaults["water_stall_tax"],
                   help="tax unproductive stays near water "
                   "(anti-dwell shaping); default off = legacy")
    p.add_argument("--temperature", type=float, default=defaults["temperature"])
    p.add_argument("--lr", type=float, default=defaults["lr"])
    p.add_argument("--epochs", type=int, default=defaults["epochs"])
    p.add_argument("--arch", choices=("base", "deep"), default=defaults["arch"])
    p.add_argument("--workers", type=int, default=defaults["workers"])
    p.add_argument("--clip", type=float, default=defaults["clip"])
    p.add_argument("--vf-coef", type=float, default=defaults["vf_coef"])
    p.add_argument("--entropy-beta", type=float, default=defaults["entropy_beta"])
    p.add_argument("--kl-anchor-beta", type=float, default=defaults["kl_anchor_beta"],
                   help="KL penalty toward the supervised base (g000); "
                   "0 disables the anchor")
    p.add_argument("--max-norm", type=float, default=defaults["max_norm"])
    p.add_argument("--minibatch", type=int, default=defaults["minibatch"])
    p.add_argument("--gamma", type=float, default=defaults["gamma"])
    p.add_argument("--seed", type=int, default=defaults["seed"])
    p.add_argument("--ticks", type=int, default=defaults["ticks"],
                   help="scheduler ticks to run; negative runs forever")
    p.add_argument("--main-source", default=defaults["main_source"],
                   help="checkpoint id the live main starts from")
    p.add_argument("--g000", default=defaults["g000"],
                   help="checkpoint id exploiters (re)start from")
    p.add_argument("--anchors", nargs="*", default=defaults["anchors"],
                   help="frozen anchor ids for the progress ladder")
    p.add_argument("--archive", default=defaults["archive"])
    args = p.parse_args(argv)
    return {
        "maps": args.maps if args.maps is not None else defaults["maps"],
        "turns": args.turns,
        "train_draw_penalty_every": args.train_draw_penalty_every,
        "water_stall_tax": args.water_stall_tax,
        "temperature": args.temperature,
        "lr": args.lr,
        "epochs": args.epochs,
        "arch": args.arch,
        "workers": args.workers,
        "clip": args.clip,
        "vf_coef": args.vf_coef,
        "entropy_beta": args.entropy_beta,
        "kl_anchor_beta": args.kl_anchor_beta,
        "max_norm": args.max_norm,
        "minibatch": args.minibatch,
        "gamma": args.gamma,
        "seed": args.seed,
        "ticks": args.ticks,
        "main_source": args.main_source,
        "g000": args.g000,
        "anchors": list(args.anchors),
        "archive": args.archive,
    }


def append_history(base: Path, entry: dict) -> None:
    """One scheduler summary; the dashboard reads this for curves."""
    archive.append_jsonl(base / "history.jsonl", entry)


def read_history(base: Path) -> list[dict]:
    """Scheduler summaries; skips malformed lines like list_games."""
    return archive.read_jsonl(
        base / "history.jsonl",
        lambda row: isinstance(row, dict),
    )


def pair_records(base: Path) -> dict[tuple[str, str], list[int]]:
    """Eval matrix as PFSP pair-records {(a, b): [wins_a, wins_b]}.

    Laplace-free: unseen pairs rate 0.5 inside pfsp (never stored).
    Both slot orders collapse into one directed key."""
    data = json.loads((base / "matrix.json").read_text())
    records: dict[tuple[str, str], list[int]] = {}
    for key, wins in data.get("eval", {}).items():
        if " vs " not in key:
            continue
        a, b = key.split(" vs ", 1)
        if a == b:
            continue  # mirror games train but never inform PFSP/Elo
        try:
            wa, wb = float(wins[0]), float(wins[1])
        except (TypeError, IndexError, ValueError):
            continue
        if (a, b) in records:
            records[(a, b)][0] += wa
            records[(a, b)][1] += wb
        elif (b, a) in records:
            records[(b, a)][0] += wb
            records[(b, a)][1] += wa
        else:
            records[(a, b)] = [wa, wb]
    return records


def learners_dir(base: Path) -> Path:
    return base / "learners"


def _live_paths(base: Path, learner: str) -> tuple[Path, Path]:
    d = learners_dir(base) / learner
    return d / "weights.json", d / "opt.json"


def store_live(base: Path, learner: str, weights: dict,
               opt_blob: dict | None) -> None:
    """Persist live training weights + Adam (atomic, old-or-new)."""
    wpath, opath = _live_paths(base, learner)
    wpath.parent.mkdir(parents=True, exist_ok=True)
    archive.atomic_write_json(wpath, weights)
    if opt_blob is None:
        try:
            opath.unlink()
        except OSError:
            pass
    else:
        archive.atomic_write_json(opath, opt_blob)


def load_live(base: Path, learner: str) -> tuple[dict, dict | None]:
    """Live training weights + Adam (None when never banked)."""
    wpath, opath = _live_paths(base, learner)
    weights = json.loads(wpath.read_text())
    try:
        blob = json.loads(opath.read_text())
    except (OSError, ValueError):
        return weights, None
    return weights, blob if isinstance(blob, dict) else None


def learner_games(state: dict, learner: str) -> int:
    """Own-games played by a learner under this league state."""
    if learner == "main":
        return state.get("main_games", 0)
    return state.get("exploiters", {}).get(learner, {}).get("games", 0)


def ensure_league(base: Path, cfg: dict) -> dict:
    """Create league.json on first start; top up scheduler extras after.

    Phase-2 init_league owns the base shape (main working id, exploiter
    slots, anchors, admissions, reset log, scheduler position); the
    scheduler adds its own counters (main own-games, per-learner
    micro-batch progress, tick count, main snapshot lineage) without
    touching that shape. Live slot ids are bare names forever ("main",
    "me", "le-a", "le-b"); ensure their manifest rows once."""
    import rewards

    rewards.GAMMA = cfg.get("gamma", rewards.GAMMA)
    archive.init(base)
    state = archive.load_league(base)
    if state is None:
        source = cfg.get("main_source", "g000")
        state = archive.init_league(
            base, source, list(cfg.get("anchors", [])))
        state.setdefault("main_games", 0)
        state.setdefault("micro", {})
        state.setdefault("tick", 0)
        state.setdefault("main_snapshots", [source])
        for exp in state.get("exploiters", {}).values():
            exp.pop("reset_at", None)
        archive.save_league(base, state)
    else:
        changed = False
        for key, default in (("main_games", 0), ("micro", {}),
                             ("tick", 0), ("resets", [])):
            if key not in state:
                state[key] = copy.deepcopy(default)
                changed = True
        if "main_snapshots" not in state:
            state["main_snapshots"] = [state.get("main_id")]
            changed = True
        for exp in state.get("exploiters", {}).values():
            if exp.pop("reset_at", None) is not None:
                changed = True
        if changed:
            archive.save_league(base, state)
    # Live slot manifest rows (bare ids, parentless seeds): one row per
    # slot ever; games under a slot accumulate for the lineage's life.
    # Resets never mint ids -- the reset log severs the record instead.
    have = {m.get("id") for m in archive.members(base)
            if isinstance(m.get("id"), str)}
    for slot in ("main", "me", "le-a", "le-b"):
        if slot not in have:
            archive.append_member(base, slot, slot, None)
    # Fresh leagues start exploiters on their bare slot ids.
    changed = False
    for slot, exp in state.get("exploiters", {}).items():
        if exp.get("id") is None:
            exp["id"] = slot
            changed = True
    if changed:
        archive.save_league(base, state)
    return state


def ensure_roles(base: Path, cfg: dict) -> None:
    """Role init on scheduler start: create missing live weight files.

    Main resumes from the existing weights + banked Adam at main_source;
    exploiters start from g000 (padding to the current arch happens
    inside algorithm.new_policy on load -- the tested path) with fresh
    Adam. Existing live files are never clobbered: restarts resume."""
    source = cfg.get("main_source", "g000")
    g000 = cfg.get("g000", "g000")
    try:
        archive.load_checkpoint(base, source)
    except (FileNotFoundError, ValueError, KeyError):
        source = g000
        cfg = dict(cfg, main_source=source)
    ensure_league(base, cfg)
    source_w = archive.load_checkpoint(base, source)
    source_opt = archive.load_opt(base, source)
    g000_w = archive.load_checkpoint(base, g000)
    for learner in LEARNERS:
        wpath, _ = _live_paths(base, learner)
        if wpath.exists():
            continue
        if learner == "main":
            store_live(base, learner, copy.deepcopy(source_w),
                       copy.deepcopy(source_opt)
                       if source_opt is not None else None)
        else:
            store_live(base, learner, copy.deepcopy(g000_w), None)


def load_live_all(cfg: dict, base: Path) -> dict:
    """In-memory training state per learner: policy, Adam, micro-batch."""
    live: dict = {"lr": cfg["lr"]}
    for learner in LEARNERS:
        weights, opt_blob = load_live(base, learner)
        # new_policy pads narrow (g000-era) checkpoints to the current
        # arch: identical outputs, lineage keeps training. Fresh Adam
        # when nothing is banked (exploiter starts and resets).
        policy = algorithm.new_policy(weights)
        opt = algorithm.make_optimizer(policy, lr=cfg["lr"])
        algorithm.load_opt_state(opt, opt_blob)
        live[learner] = {"policy": policy, "opt": opt, "pending": []}
    return live


def _next_family_id(base: Path, prefix: str, start: int = 0) -> str:
    """First free family id ``prefix`` + k (k >= start), e.g. main0.

    Scans manifest ids; collision-skips taken names. Numbering is
    0-based and derived from the admissions log (or 0 for a fresh
    namespace), so it continues instead of reusing gaps and restarts
    safely with no counter state. Pure except for the manifest read."""
    try:
        k = int(start)
    except (TypeError, ValueError):
        k = 0
    if k < 0:
        k = 0
    taken = {m.get("id") for m in archive.members(base)
             if isinstance(m.get("id"), str)}
    while f"{prefix}{k}" in taken:
        k += 1
    return f"{prefix}{k}"


def _slot_admissions(state: dict, learner: str) -> int:
    """Existing admissions for a slot, from the league.json log.

    Derived (no counter state, restart-safe, no migration): counts
    entries whose role is the slot name."""
    return sum(1 for a in state.get("admissions", []) or []
               if isinstance(a, dict) and a.get("role") == learner)


def reset_learner(base: Path, live: dict, learner: str, g000_w: dict) -> None:
    """Stall/admission reset: g000 weights + fresh Adam, batch dropped."""
    policy = algorithm.new_policy(copy.deepcopy(g000_w))
    opt = algorithm.make_optimizer(policy, lr=live["lr"])
    live[learner] = {"policy": policy, "opt": opt, "pending": []}
    store_live(base, learner, copy.deepcopy(g000_w), None)


def _window_rate(window: list[float]) -> float:
    return sum(window) / len(window) if window else 0.0


def _window_record(window: list[float]) -> str:
    wins = sum(1 for o in window if o == 1.0)
    draws = sum(1 for o in window if o == 0.5)
    losses = len(window) - wins - draws
    return f"{wins}W-{draws}D-{losses}L"


def maybe_admit(base: Path, live: dict, state: dict, learner: str,
                g000_w: dict) -> dict | None:
    """Admission check: sustained >60% over the last 40 vs the target.

    Freezes the current weights as an admitted pool member under the next
    family id (meN/le-aN/le-bN, 0-based from the admissions log) with the
    live slot as parent, so it seeds from the slot's peak. Logs the
    admission, then resets the live slot IN PLACE (g000 weights + fresh
    Adam, same bare id): the family id is the achievement, the slot is
    the continuing lineage. Returns the entry or None."""
    if learner == "main":
        return None
    exp = state["exploiters"][learner]
    window = exp.get("window", [])
    if len(window) < archive.WINDOW_SIZE:
        return None
    if _window_rate(window) > ADMISSION_RATE:
        weights = algorithm.policy_weights(live[learner]["policy"])
        start = _slot_admissions(state, learner)
        sid = archive.save_named_snapshot(
            base, _next_family_id(base, learner, start),
            weights, "admitted", learner)
        entry = archive.record_admission(
            base, sid, learner, exp.get("games", 0),
            _window_record(window))
        # record_admission saves its own reload: refresh before mutating
        # or the admission entry is clobbered by this stale copy.
        state = archive.load_league(base)
        exp = state["exploiters"][learner]
        reset_learner(base, live, learner, g000_w)
        exp["window"] = []
        archive.save_league(base, state)
        return entry
    return None


def maybe_snapshot(cfg: dict, base: Path, live: dict, state: dict,
                   learner: str) -> dict | None:
    """Snapshot cadence: the MAIN freezes a permanent member every 80th
    own-game (mainN, fresh 0-based namespace). Exploiters never snapshot:
    they enter the pool only by admission (meN/le-aN/le-bN).

    Main snapshots chain via the league main id and trigger the anchor
    ladder series (measurement only). Returns {"id", "anchors"} or None.
    """
    if learner != "main":
        return None
    games = state.get("main_games", 0)
    if games <= 0 or games % SNAPSHOT_EVERY != 0:
        return None
    weights = algorithm.policy_weights(live[learner]["policy"])
    parent = state.get("main_id")
    sid = archive.save_named_snapshot(
        base, _next_family_id(base, "main", 0),
        weights, train.ROLE_CONFIGS[learner]["snapshot_role"], parent)
    anchors = None
    state["main_id"] = sid
    snaps = state.setdefault("main_snapshots", [])
    if sid not in snaps:
        snaps.append(sid)
    anchor_ws = {}
    for aid in state.get("anchors", []):
        try:
            anchor_ws[aid] = archive.load_checkpoint(base, aid)
        except (FileNotFoundError, ValueError, KeyError):
            continue
    if anchor_ws:
        anchors = measure.measure_all(cfg, base, sid, sid, weights,
                                      anchor_ws)
    archive.save_league(base, state)
    append_history(base, {"snapshot": sid, "learner": learner,
                          "games": games,
                          "anchors": anchors,
                          "tick": state.get("tick", 0)})
    return {"id": sid, "anchors": anchors}


def run_tick(cfg: dict, base: Path, live: dict,
             rng: random.Random | None = None) -> dict:
    """One scheduler iteration: play, log, accumulate, maybe train.

    Trains exactly one learner (the seat-0 side); the opponent's weights
    are fixed for the game (frozen snapshot, or a live-main copy that
    learns nothing from it). Returns a report dict."""
    import rewards

    rewards.GAMMA = cfg.get("gamma", rewards.GAMMA)
    state = archive.load_league(base)
    if state is None:
        raise FileNotFoundError(f"no league.json under {base}")
    tick = state.get("tick", 0)
    if rng is None:
        rng = random.Random(f"{cfg.get('seed', 0)}:{tick}")
    learner = archive.current_learner(state)
    lcfg = train.ROLE_CONFIGS[learner]
    entry = live[learner]
    g000_w = archive.load_checkpoint(base, cfg.get("g000", "g000"))

    # Seat identity: bare slot names, forever. The main logs under
    # "main" (it never resets); exploiters log under their slot
    # ("me", "le-a", "le-b") across resets. No incarnation ids:
    # the reset log severs the record instead (see note_reset + the
    # Elo reset-cuts), and admissions freeze peaks under family ids.
    seat_id = learner

    records = pair_records(base)
    opp = train.select_opponent(base, learner, state, records, rng)
    if opp == "main":
        # live main: loaded live, never frozen (ME threshold branch and
        # main's self-play branch). The weights are fixed for the game;
        # only the seat-0 learner trains.
        opp_w = algorithm.policy_weights(live["main"]["policy"])
    else:
        opp_w = archive.load_checkpoint(base, opp)
    live_w = algorithm.policy_weights(entry["policy"])
    game_no = learner_games(state, learner)
    map_path = rng.choice(cfg["maps"])
    played = train._play_one(
        (dict(cfg, game_kind="eval"), base, seat_id, [seat_id, opp],
         [live_w, opp_w], game_no, lcfg["pricing"], map_path))
    batch = algorithm.collect(entry["policy"], played["rows"],
                              played["rets"])
    entry["pending"].extend(batch)

    micro = state.setdefault("micro", {}).get(learner, 0) + 1
    state["micro"][learner] = micro
    update_stats = None
    if micro % MICRO_BATCH == 0:
        update_stats = train.ppo_update(entry["policy"], entry["opt"],
                                        entry["pending"], cfg)
        entry["pending"] = []
        store_live(base, learner,
                   algorithm.policy_weights(entry["policy"]),
                   algorithm.serialize_opt(entry["opt"]))
    # Persist progress before the counter helpers below: they reload the
    # league from disk and would drop unsaved in-memory progress.
    archive.save_league(base, state)

    my_score, opp_score = played["scores"][0], played["scores"][1]
    outcome = archive.outcome_of(my_score, opp_score)
    if learner == "main":
        state["main_games"] = state.get("main_games", 0) + 1
    else:
        # Every exploiter game grows its window: ME faces the main
        # lineage (live main or its snapshots), LEs face the pool.
        target = state.get("main_id") if learner == "me" else "pool"
        archive.note_exploiter_game(base, learner, outcome,
                                    target=target)
        state = archive.load_league(base)
    archive.save_league(base, state)

    admitted = maybe_admit(base, live, state, learner, g000_w)
    snapshot = None
    if admitted is not None:
        # maybe_admit reloads internally: refresh or the final save
        # clobbers the admission entry and the reset.
        state = archive.load_league(base)
        archive.note_reset(base, learner, seat_id, game_no, tick)
        state = archive.load_league(base)
    else:
        # No stall rule: a drought simply keeps training under the same
        # bare id with a rolling window. The admitted freeze is the
        # permanent record for that tick; a fresh reset must not
        # snapshot on the same tick.
        snapshot = maybe_snapshot(cfg, base, live, state, learner)
        # maybe_snapshot saves state itself for main/exploiters.
        state = archive.load_league(base)

    state["tick"] = tick + 1
    archive.save_league(base, state)
    next_learner = archive.advance_scheduler(base)
    archive.write_status(base, {
        "phase": "league", "learner": learner, "opponent": opp,
        "tick": tick + 1, "next": next_learner,
        "own_games": learner_games(state, learner),
        "micro": state.get("micro", {}).get(learner, 0),
        "admitted": admitted["id"] if admitted else None,
        "snapshot": snapshot["id"] if snapshot else None,
    })
    return {
        "learner": learner,
        "opponent": opp,
        "scores": played["scores"],
        "outcome": outcome,
        "micro": state.get("micro", {}).get(learner, 0),
        "update": update_stats,
        "admitted": admitted,
        "snapshot": snapshot,
        "tick": tick,
    }


def run_loop(cfg: dict, base: Path, ticks: int | None = None) -> list[dict]:
    """Perpetual scheduler: ensure roles, then tick until ticks run out."""
    ensure_roles(base, cfg)
    live = load_live_all(cfg, base)
    reports = []
    n = cfg.get("ticks", -1) if ticks is None else ticks
    tick = 0
    while n is None or n < 0 or tick < n:
        reports.append(run_tick(cfg, base, live))
        tick += 1
    return reports


def main(argv: list[str] | None = None) -> list[dict]:
    cfg = parse_args(argv)
    return run_loop(cfg, Path(cfg["archive"]), ticks=cfg["ticks"])


if __name__ == "__main__":
    reports = main()
    print(json.dumps(reports[-1] if reports else {}, indent=1, default=str))
