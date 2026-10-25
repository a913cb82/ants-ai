"""One generation's exam: greedy duels, Wilson promotion rule.

Knows evaluation. Knows nothing about training; returns a verdict the
driver acts on. Promotion needs both evidence of strength (Wilson lower
bound on the duel win rate clears the bar) and population relevance
(Nash mass at least the champion's) — no judgment calls anywhere.
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

import archive
import game_if


def should_promote(
    wins: int,
    draws: int,
    games: int,
    nash_chal: float,
    nash_champ: float,
    threshold: float = 0.5,
) -> bool:
    """Automated promotion: Wilson lower bound clears the bar AND Nash
    mass. Draws count half a win in both the rate and the bound."""
    lower = archive.wilson_lower(wins + 0.5 * draws, games)
    return lower > threshold and nash_chal >= nash_champ


def _play_duel(args) -> tuple[float, float]:
    """One eval duel: play and record. Thread-safe via archive lock."""
    (cfg, base, chal_id, champ_id, me_w, other_w, slot, g, offset) = args
    # A one-map curriculum has no held-out pool: evals run the same map.
    pool = cfg.get("held_maps") or cfg["maps"]  # evals on unseen maps
    rel = f"games/{chal_id}/eval{g}"
    first, second = (chal_id, champ_id) if slot == 0 else (champ_id, chal_id)
    out = game_if.play(
        ROOT,
        sys.executable,
        me_w,
        other_w,
        game_if.GameConfig(
            map=pool[(offset + g) % len(pool)],
            # exams run long: 60-turn games truncate before skill gaps
            # compound (all draws by turn limit). Train short for sharp
            # credit, judge long for resolution.
            turns=cfg.get("eval_turns") or cfg["turns"],
            temperature=0.0,
            player_seed=5000 + g,
            engine_seed=9000 + g,
        ),
        base / rel,
        name_a=first,
        name_b=second,
    )
    game = out["game"]
    sa, sb = game["score"][0], game["score"][1]
    archive.record_result(base, first, second, sa, sb, kind="eval")
    archive.log_game(base, chal_id, "eval", first, second, sa, sb,
                     rel + "/logs/0.replay")
    return sa, sb


def evaluate(
    cfg: dict, base: Path, chal_id: str, chal_w: dict, champ_id: str, champ_w: dict,
    map_offset: int = 0,
) -> dict:
    jobs = []
    for g in range(cfg["eval_games"]):
        slot = g % 2
        me_w, other_w = (chal_w, champ_w) if slot == 0 else (champ_w, chal_w)
        jobs.append((cfg, base, chal_id, champ_id, me_w, other_w, slot, g,
                       map_offset))
    workers = min(cfg.get("workers", 8), len(jobs)) or 1
    wins = draws = finished = 0
    margins: list[int] = [0] * cfg["eval_games"]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_g = {pool.submit(_play_duel, job): job[7] for job in jobs}
        for future in as_completed(future_to_g):
            g = future_to_g[future]
            sa, sb = future.result()
            chal_score, champ_score = (sa, sb) if g % 2 == 0 else (sb, sa)
            wins += chal_score > champ_score
            draws += chal_score == champ_score
            margins[g] = chal_score - champ_score  # duel order, not finish order
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
