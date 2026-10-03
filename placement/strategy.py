"""Placement strategy. Optimise select_next_game."""

from dataclasses import dataclass
from statistics import NormalDist


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


def _short_stack(bot: Rating, ratings: list[Rating]) -> bool:
    """True when the bot is uncertain or far from the anchor median."""
    pool = _established(ratings, 2)
    mus = sorted(ratings[c].mu for c in pool)
    med = mus[len(mus) // 2]
    spread = max((sum((m - med) ** 2 for m in mus) / len(mus)) ** 0.5, 1.0)
    return bot.sigma > 7.0 or abs(bot.mu - med) > spread


def _closest(bot: Rating, ratings: list[Rating]) -> int:
    """Pool index nearest bot.mu, low sigma then low index on ties."""
    return min(
        range(len(ratings)),
        key=lambda i: (abs(ratings[i].mu - bot.mu), ratings[i].sigma, i),
    )


def _spread(
    bot: Rating,
    ratings: list[Rating],
    k: int,
    width: float = 1.0,
    anchors: bool = True,
) -> list[int]:
    """k distinct opponents nearest quantiles of N(mu, w*sigma)."""
    dist = NormalDist(bot.mu, max(width * bot.sigma, 0.5))
    targets = [dist.inv_cdf((j + 1) / (k + 1)) for j in range(k)]
    pool = _established(ratings, k) if anchors else list(range(len(ratings)))
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
    # Exp (iter 16, MSE): push-fold routing after 2 opening duels.
    if budget_left > 26:
        return [_closest(bot, ratings)]
    if _short_stack(bot, ratings):
        if budget_left > 6:
            return _spread(
                bot,
                ratings,
                min(9, budget_left - 1, len(ratings)),
                2.5,
                False,
            )
        order = sorted(
            range(len(ratings)),
            key=lambda i: (abs(ratings[i].mu - bot.mu), ratings[i].sigma, i),
        )
        idx = (budget_left // 2) % 3
        if idx == 0:
            for i in order:
                if ratings[i].mu >= bot.mu:
                    return [i]
        elif idx == 1:
            for i in order:
                if ratings[i].mu < bot.mu:
                    return [i]
        return [order[0]]
    if budget_left > 6:
        pool = _established(ratings, 1)
        return [
            min(
                pool,
                key=lambda c: (
                    abs(ratings[c].mu - bot.mu),
                    ratings[c].sigma,
                    c,
                ),
            )
        ]
    return _spread(bot, ratings, min(5, budget_left - 1, len(ratings)), 0.5)
