"""Placement strategy. Optimise select_next_game."""

from dataclasses import dataclass
from statistics import NormalDist  # noqa: F401 (kept for width experiments)

from openskill.models import BradleyTerryFull

_MODEL = BradleyTerryFull()
_SIGMA_WEIGHT = 0.02
_PREFILTER = 40


@dataclass
class Rating:
    mu: float
    sigma: float


def _established(ratings: list[Rating], k: int) -> list[int]:
    """Pool indices in the low-sigma tertile, or the full pool if too few."""
    cutoff = sorted(r.sigma for r in ratings)[len(ratings) // 3]
    pool = [c for c in range(len(ratings)) if ratings[c].sigma <= cutoff]
    if len(pool) < k:
        pool = list(range(len(ratings)))
    return pool


def _draw_field(bot: Rating, ratings: list[Rating], k: int) -> list[int]:
    """Greedy predict_draw field: seed bot, add max draw prob each step."""
    pool = _established(ratings, k)
    near = sorted(
        pool, key=lambda c: (abs(ratings[c].mu - bot.mu), ratings[c].sigma, c)
    )[:_PREFILTER]
    field: list[int] = []
    avail = set(near)
    while len(field) < k and avail:
        base = [bot] + [ratings[c] for c in field]
        teams = [[_MODEL.rating(mu=r.mu, sigma=r.sigma)] for r in base]
        best, best_key = None, None
        for c in avail:
            r = ratings[c]
            cand = [[_MODEL.rating(mu=r.mu, sigma=r.sigma)]]
            s = _MODEL.predict_draw(teams + cand) + _SIGMA_WEIGHT * r.sigma
            if best_key is None or (-s, c) < best_key:
                best, best_key = c, (-s, c)
        field.append(best)
        avail.discard(best)
    for c in near:
        if len(field) >= k:
            break
        if c not in field:
            field.append(c)
    return field[:k]


def _closest(bot: Rating, ratings: list[Rating]) -> int:
    """Pool index nearest bot.mu, low sigma then low index on ties."""
    return min(
        range(len(ratings)),
        key=lambda i: (abs(ratings[i].mu - bot.mu), ratings[i].sigma, i),
    )


def _spread(
    bot: Rating, ratings: list[Rating], k: int, width: float = 1.0
) -> list[int]:
    """k distinct established opponents nearest quantiles of N(mu, w*sigma)."""
    dist = NormalDist(bot.mu, max(width * bot.sigma, 0.5))
    targets = [dist.inv_cdf((j + 1) / (k + 1)) for j in range(k)]
    pool = _established(ratings, k)
    picked: list[int] = []
    used: set[int] = set()
    for t in targets:
        i = min(
            (c for c in pool if c not in used),
            key=lambda c: (abs(ratings[c].mu - t), ratings[c].sigma, c),
        )
        used.add(i)
        picked.append(i)
    return picked


def select_next_game(bot: Rating, ratings: list[Rating], budget_left: int) -> list[int]:
    """Return opponent ids for the next game.

    Each id is an index into ratings. Game size is len(return) + 1.
    budget_left counts all remaining slots, including the bot.
    A duel costs 2. A 10p game costs 10. Return [] if budget_left < 2.
    The harness clips the return to budget_left and the pool size.
    """
    if not ratings or budget_left < 2:
        return []
    # Exp (iter 43): duels first, greedy predict_draw FFA fields.
    if budget_left > 20:
        return [_closest(bot, ratings)]
    return _draw_field(bot, ratings, min(9, budget_left - 1, len(ratings)))
