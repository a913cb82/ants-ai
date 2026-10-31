"""One generation's exam: fixed-seat games, Wilson promotion rule.

Knows evaluation. Knows nothing about training; returns a verdict the
driver acts on. Promotion needs evidence of strength (Wilson lower
bound on the challenger-vs-champion score comparison clears the bar).
Every opponent seat is Nash-sampled with replacement; the verdict is
challenger score vs champion score only.
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

import archive
import game_if


def should_promote(
    wins: int,
    draws: int,
    games: int,
    threshold: float = 0.5,
) -> bool:
    """Automated promotion: Wilson lower bound clears the bar.

    Draws count half a win. Head-to-head vs the champion is the only
    evidence we trust: challengers never face each other (star data),
    so the Nash mixture collapses onto whoever last beat the champ
    and cannot gate promotion. Nash stays recorded for display only."""
    lower = archive.wilson_lower(wins + 0.5 * draws, games)
    return lower > threshold


def _eval_map_for(cfg, g):
    """Map for eval game g: the dedicated eval slice 1:1."""
    return cfg["eval_maps"][g]


def _play_duel(args) -> tuple[float, float]:
    """One eval game: play and record. Thread-safe via archive lock.

    Seats are fixed: challenger 0, champion 1, Nash-sampled extras.
    The verdict is chal score vs champ score only; extras are shared
    weather. Every seat pair is recorded (pairwise matrix food)."""
    (cfg, base, chal_id, champ_id, field, weights, g) = args
    map_path = _eval_map_for(cfg, g)
    rel = f"games/{chal_id}/eval{g}"
    out = game_if.play(
        ROOT,
        sys.executable,
        weights,
        game_if.GameConfig(
            map=map_path,
            # exams run long: 60-turn games truncate before skill gaps
            # compound (all draws by turn limit). Train short for sharp
            # credit, judge long for resolution.
            turns=cfg.get("eval_turns") or cfg["turns"],
            temperature=0.0,
            player_seed=5000 + g,
            engine_seed=9000 + g,
        ),
        base / rel,
        names=field,
    )
    game = out["game"]
    scores = game["score"]
    for x in range(len(field)):
        for y in range(x + 1, len(field)):
            archive.record_result(base, field[x], field[y],
                                  scores[x], scores[y], kind="eval")
            archive.log_game(base, chal_id, "eval", field[x], field[y],
                             scores[x], scores[y],
                             rel + "/logs/0.replay", map=Path(map_path).name)
    return scores[0], scores[1]


def evaluate(
    cfg: dict, base: Path, chal_id: str, chal_w: dict, champ_id: str, champ_w: dict,
) -> dict:
    wcache = {champ_id: champ_w, chal_id: chal_w}
    # Fixed mixture, drawn once: see train.train_generation (per-game
    # Nash recomputation costs ~40s x games of silent prologue).
    # 2p-only exams skip it entirely.
    seat_counts = [game_if.map_player_count(_eval_map_for(cfg, g))
                   for g in range(cfg["eval_games"])]
    mix_ids, mix_p = [], np.array([])
    if any(n > 2 for n in seat_counts):
        _mix = archive.nash_mixture(base)
        mix_ids, mix_p = archive.prune_missing(
            base, list(_mix), np.array([_mix[i] for i in _mix]))
    jobs = []
    for g in range(cfg["eval_games"]):
        map_path = _eval_map_for(cfg, g)
        n_seats = seat_counts[g]
        field = [chal_id, champ_id] + archive.mixture_draw(
            mix_ids, mix_p, k=n_seats - 2,
            rng=np.random.default_rng(cfg.get("seed", 0) + g),
            exclude=(chal_id, champ_id))
        weights = []
        for fid in field:
            if fid not in wcache:  # extras load frozen from the archive
                wcache[fid] = archive.load_checkpoint(base, fid)
            weights.append(wcache[fid])
        jobs.append((cfg, base, chal_id, champ_id, field, weights, g))
    workers = min(cfg.get("workers", 8), len(jobs)) or 1
    wins = draws = finished = 0
    margins: list[int] = [0] * cfg["eval_games"]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_g = {pool.submit(_play_duel, job): job[6] for job in jobs}
        for future in as_completed(future_to_g):
            g = future_to_g[future]
            chal_score, champ_score = future.result()
            wins += chal_score > champ_score
            draws += chal_score == champ_score
            margins[g] = chal_score - champ_score  # seat order, not finish order
            finished += 1
            archive.write_status(base, {
                "phase": "eval", "challenger": chal_id,
                "done": finished, "total": cfg["eval_games"],
                "wins": wins, "draws": draws,
                "last_game": f"games/{chal_id}/eval{g}",
            })
    return {
        "wins": wins,
        "draws": draws,
        "games": cfg["eval_games"],
        "win_rate": (wins + 0.5 * draws) / cfg["eval_games"] if cfg["eval_games"] else 0.0,
        # Score differential per duel (challenger minus champion).
        # Display only: the promotion rule still reads W/D. But when
        # mirrors draw 90%+, the margin is where improvement shows first.
        "margins": margins,
        "mean_margin": sum(margins) / len(margins) if margins else 0.0,
    }
