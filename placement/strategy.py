"""Placement strategy. Optimise select_next_game."""

from dataclasses import dataclass
from statistics import NormalDist


@dataclass
class Rating:
    mu: float
    sigma: float


def _established(ratings: list[Rating], k: int) -> list[int]:
    """Pool indices in the low-sigma quartile, or the full pool if too few."""
    cutoff = sorted(r.sigma for r in ratings)[len(ratings) // 4]
    pool = [c for c in range(len(ratings)) if ratings[c].sigma <= cutoff]
    if len(pool) < k:
        pool = list(range(len(ratings)))
    return pool


def _closest(bot: Rating, ratings: list[Rating]) -> int:
    """Pool index nearest bot.mu, low sigma then low index on ties."""
    return min(
        range(len(ratings)),
        key=lambda i: (abs(ratings[i].mu - bot.mu), ratings[i].sigma, i),
    )


def _spread(bot: Rating, ratings: list[Rating], k: int) -> list[int]:
    """k distinct established opponents nearest quantiles of N(mu, sigma)."""
    dist = NormalDist(bot.mu, max(bot.sigma, 0.5))
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
    # Exp (iter 23): duels first, quartile-anchor spread FFAs late.
    if budget_left > 20:
        return [_closest(bot, ratings)]
    return _spread(bot, ratings, min(9, budget_left - 1, len(ratings)))
