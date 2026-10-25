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
    (cfg, base, chal_id, champ_id, me_w, other_w, slot, g) = args
    rel = f"games/{chal_id}/eval{g}"
    out = game_if.play(
        ROOT,
        sys.executable,
        me_w,
        other_w,
        game_if.GameConfig(
            map=cfg["maps"][g % len(cfg["maps"])],
            turns=cfg["turns"],
            temperature=0.0,
            player_seed=5000 + g,
            engine_seed=9000 + g,
        ),
        base / rel,
    )
    game = out["game"]
    sa, sb = game["score"][0], game["score"][1]
    first, second = (chal_id, champ_id) if slot == 0 else (champ_id, chal_id)
    archive.record_result(base, first, second, sa, sb, kind="eval")
    archive.log_game(base, chal_id, "eval", first, second, sa, sb,
                     rel + "/logs/0.replay")
    return sa, sb


def evaluate(
    cfg: dict, base: Path, chal_id: str, chal_w: dict, champ_id: str, champ_w: dict
) -> dict:
    jobs = []
    for g in range(cfg["eval_games"]):
        slot = g % 2
        me_w, other_w = (chal_w, champ_w) if slot == 0 else (champ_w, chal_w)
        jobs.append((cfg, base, chal_id, champ_id, me_w, other_w, slot, g))
    workers = min(cfg.get("workers", 8), len(jobs)) or 1
    wins = draws = finished = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_g = {pool.submit(_play_duel, job): job[-1] for job in jobs}
        for future in as_completed(future_to_g):
            g = future_to_g[future]
            sa, sb = future.result()
            chal_score, champ_score = (sa, sb) if g % 2 == 0 else (sb, sa)
            wins += chal_score > champ_score
            draws += chal_score == champ_score
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
    }
