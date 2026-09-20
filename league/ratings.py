"""OpenSkill BradleyTerryFull ratings over FFA placements.

ratings: {bot_id: {"mu": float, "sigma": float, "games": int}}
Unseen bots enter at the model prior. Updates are functional (no mutation).
"""
from __future__ import annotations

import json
from pathlib import Path

from openskill.models import BradleyTerryFull

MU = 25.0
SIGMA = 25.0 / 3


def new_model() -> BradleyTerryFull:
    return BradleyTerryFull()


def prior_dict(m: BradleyTerryFull | None = None) -> dict:
    m = m or new_model()
    return {"mu": m.mu, "sigma": m.sigma, "games": 0}


def for_id(ratings: dict, bot_id: str, m: BradleyTerryFull | None = None) -> dict:
    return ratings.get(bot_id, prior_dict(m))


def update(ratings: dict, field: list[str], result: list[str],
           ranks: dict[str, int] | None = None) -> dict:
    """One FFA game. field = ids by slot, result = ids best-first.
    Optional ranks maps id -> 1-based rank (ties share)."""
    m = new_model()
    place = {bid: i + 1 for i, bid in enumerate(result)}
    if ranks:
        place.update(ranks)
    teams = []
    for bid in field:
        e = for_id(ratings, bid, m)
        teams.append([m.rating(mu=e["mu"], sigma=e["sigma"])])
    new_teams = m.rate(teams, ranks=[place[bid] for bid in field])
    out = dict(ratings)
    for bid, (r,) in zip(field, new_teams):
        e = for_id(ratings, bid, m)
        out[bid] = {"mu": r.mu, "sigma": r.sigma, "games": e["games"] + 1}
    return out


def rebuild(games: list[dict]) -> dict:
    ratings: dict = {}
    for g in games:
        ratings = update(ratings, field=g["field"], result=g["result"],
                         ranks=g.get("ranks"))
    return ratings


def load(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    data = json.loads(p.read_text())
    if isinstance(data, dict) and "bots" in data:
        return data["bots"]
    return data


def save(path: str | Path, ratings: dict) -> None:
    Path(path).write_text(json.dumps({"v": 1, "bots": ratings}, indent=1))
