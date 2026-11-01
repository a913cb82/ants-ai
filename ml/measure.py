"""Anchor games: fixed-reference measurement, no training.

The mirror-only translation of external test matches: two games per
main snapshot against each frozen anchor, greedy play, results appended
to anchor.jsonl. Anchor games carry no gradient (weights are never
touched), feed no matrix (PFSP must not see them), and log no dashboard
rows -- the only record is the measurement row itself.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

import archive
import game_if

#: Anchor games per (snapshot, anchor) pair (plan: 2, seats alternate).
GAMES_PER_ANCHOR = 2


def play_anchor_game(cfg: dict, base: Path, snap_w: dict, anchor_w: dict,
                     game_index: int, map_path: str) -> tuple[float, float]:
    """One anchor game. Returns (snapshot_score, anchor_score).

    Seats alternate so neither side owns a color advantage: even games
    seat the snapshot first, odd games the anchor. No pricing, no
    records, no logging -- measurement only."""
    snap_first = game_index % 2 == 0
    weights = [snap_w, anchor_w] if snap_first else [anchor_w, snap_w]
    names = ["snapshot", "anchor"] if snap_first else ["anchor", "snapshot"]
    rel = f"anchors/game{game_index}"
    out = game_if.play(
        ROOT,
        sys.executable,
        weights,
        game_if.GameConfig(
            map=map_path,
            turns=cfg["turns"],
            temperature=0.0,
            player_seed=cfg.get("seed", 0) + game_index,
            engine_seed=9000 + game_index,
        ),
        base / rel,
        names=names,
    )
    scores = out["game"]["score"]
    if snap_first:
        return scores[0], scores[1]
    return scores[1], scores[0]


def measure_anchor(cfg: dict, base: Path, snapshot_id: str, main_id: str,
                   anchor_id: str, snap_w: dict, anchor_w: dict,
                   games: int = GAMES_PER_ANCHOR,
                   rng: random.Random | None = None,
                   tick: int | None = None) -> dict:
    """One (snapshot, anchor) series: play, tally, record. No training."""
    if rng is None:
        rng = random.Random(f"{snapshot_id}:{anchor_id}")
    wins = losses = draws = 0
    for g in range(games):
        map_path = rng.choice(cfg["maps"])
        snap_score, anchor_score = play_anchor_game(
            cfg, base, snap_w, anchor_w, g, map_path)
        if snap_score > anchor_score:
            wins += 1
        elif anchor_score > snap_score:
            losses += 1
        else:
            draws += 1
        archive.write_status(base, {
            "phase": "anchor", "snapshot": snapshot_id,
            "anchor": anchor_id, "done": g + 1, "total": games,
            "last_game": f"anchors/game{g}",
        })
    return archive.record_anchor(base, snapshot_id, main_id, anchor_id,
                                 wins, losses, draws, tick=tick)


def measure_all(cfg: dict, base: Path, snapshot_id: str, main_id: str,
                snap_w: dict, anchors: dict[str, dict],
                games_per: int = GAMES_PER_ANCHOR,
                rng: random.Random | None = None,
                tick: int | None = None) -> list[dict]:
    """Full ladder series for one main snapshot. Returns the rows."""
    if rng is None:
        rng = random.Random(snapshot_id)
    rows = []
    for anchor_id, anchor_w in anchors.items():
        rows.append(measure_anchor(cfg, base, snapshot_id, main_id,
                                   anchor_id, snap_w, anchor_w,
                                   games=games_per, rng=rng, tick=tick))
    return rows
