"""One generation's exam: greedy duels, Wilson promotion rule.

Knows evaluation. Knows nothing about training; returns a verdict the
driver acts on. Promotion needs both evidence of strength (Wilson lower
bound on the duel win rate clears the bar) and population relevance
(Nash mass at least the champion's) — no judgment calls anywhere.
"""

from __future__ import annotations

import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

import archive
import game_if


JURY_WINDOW = 15
JURY_CHAMP_NUM = 3
JURY_CHAMP_DEN = 5
"""Jury exam split: the champ keeps a 3/5 majority share of the exam
(12 of 20); the remaining games spread round-robin across the jurors.
Same games total, same Wilson bar -- only the opponent mix changes."""


def select_jury(base, chal_id, champ_id, n, seed=0,
                window=JURY_WINDOW):
    """PFSP-frontier jury plus the strongest recorded counter.

    Frontier: members within `window` gens of the newest (the same
    recency rule as train-time PFSP), ranked by win rate against the
    champ (counter strength first), then Nash mass. Exact ties break
    by `seed` (deterministic). The highest-Nash non-champ member that
    beats the champ is mandatory: if it sits outside the frontier cut
    it displaces the last juror (the g1234 class stays examined until
    dethroned). The champ itself holds a guaranteed slot -- it is not
    in this list; the plan deals its games separately.
    """
    if n <= 0:
        return []
    try:
        mems = archive.members(base)
    except (OSError, ValueError):
        return []
    try:
        newest = max(int(m["id"][1:]) for m in mems)
    except (ValueError, KeyError):
        return []
    rates = archive.win_rates(base, champ_id)  # opp -> opp's rate vs champ
    mix = archive.nash_mixture(base)
    rng = random.Random(seed)
    order = [m["id"] for m in mems
             if m["id"] not in (chal_id, champ_id)]
    rng.shuffle(order)  # seeded: exact ranking ties break deterministically
    frontier = []
    for cid in order:
        try:
            age = newest - int(cid[1:])
        except (ValueError, IndexError):
            continue
        if age < window:
            frontier.append(cid)
    frontier.sort(key=lambda c: (-rates.get(c, 0.0), -mix.get(c, 0.0)))
    jury = frontier[:max(n, 0)]
    counters = [c for c in order if rates.get(c, 0.0) > 0.5]
    if counters:
        top = max(counters,
                  key=lambda c: (mix.get(c, 0.0), rates.get(c, 0.0), c))
        if top not in jury:
            if len(jury) < n:
                jury.append(top)
            else:
                jury[-1] = top
    return jury


def plan_exam_opponents(base, chal_id, champ_id,
                        eval_games, jury_size=0, seed=0):
    """Per-game exam opponents. jury_size=0 is the legacy path: every
    game vs the champ (byte-identical to the old exam)."""
    if eval_games <= 0:
        return []
    if not jury_size:
        return [champ_id] * eval_games
    jury = select_jury(base, chal_id, champ_id, jury_size, seed=seed)
    if not jury:
        return [champ_id] * eval_games  # fresh archive: nobody to convene
    champ_games = eval_games * JURY_CHAMP_NUM // JURY_CHAMP_DEN
    jury_games = eval_games - champ_games
    games = [champ_id] * champ_games
    games += [jury[i % len(jury)] for i in range(jury_games)]
    random.Random(seed).shuffle(games)  # deterministic given seed
    return games


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


def _play_duel(args) -> tuple[float, float]:
    """One eval duel: play and record. Thread-safe via archive lock."""
    (cfg, base, chal_id, opp_id, me_w, other_w, slot, g, offset) = args
    # A one-map curriculum has no held-out pool: evals run the same map.
    pool = cfg.get("held_maps") or cfg["maps"]  # evals on unseen maps
    rel = f"games/{chal_id}/eval{g}"
    first, second = (chal_id, opp_id) if slot == 0 else (opp_id, chal_id)
    map_path = pool[(offset + g) % len(pool)]
    out = game_if.play(
        ROOT,
        sys.executable,
        me_w,
        other_w,
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
        name_a=first,
        name_b=second,
    )
    game = out["game"]
    sa, sb = game["score"][0], game["score"][1]
    archive.record_result(base, first, second, sa, sb, kind="eval")
    archive.log_game(base, chal_id, "eval", first, second, sa, sb,
                     rel + "/logs/0.replay", map=Path(map_path).name)
    return sa, sb


def evaluate(
    cfg: dict, base: Path, chal_id: str, chal_w: dict, champ_id: str, champ_w: dict,
    map_offset: int = 0,
) -> dict:
    opponents = plan_exam_opponents(
        base, chal_id, champ_id, cfg["eval_games"],
        jury_size=cfg.get("exam_jury_size", 0) or 0,
        seed=cfg.get("seed", 0))
    wcache = {champ_id: champ_w, chal_id: chal_w}
    jobs = []
    for g, opp_id in enumerate(opponents):
        slot = g % 2
        if opp_id not in wcache:  # juror weights are frozen in the archive
            wcache[opp_id] = archive.load_checkpoint(base, opp_id)
        opp_w = wcache[opp_id]
        me_w, other_w = (chal_w, opp_w) if slot == 0 else (opp_w, chal_w)
        jobs.append((cfg, base, chal_id, opp_id, me_w, other_w, slot, g,
                       map_offset))
    workers = min(cfg.get("workers", 8), len(jobs)) or 1
    wins = draws = finished = 0
    margins: list[int] = [0] * cfg["eval_games"]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_g = {pool.submit(_play_duel, job): job[7] for job in jobs}
        for future in as_completed(future_to_g):
            g = future_to_g[future]
            sa, sb = future.result()
            chal_score, opp_score = (sa, sb) if g % 2 == 0 else (sb, sa)
            wins += chal_score > opp_score
            draws += chal_score == opp_score
            margins[g] = chal_score - opp_score  # duel order, not finish order
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
