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


def _pct_anchor(ratings: list[Rating], q: float) -> int:
    """Established pool member nearest the q-th mu quantile."""
    pool = _established(ratings, 1)
    mus = sorted(ratings[c].mu for c in pool)
    t = mus[min(int(q * len(mus)), len(mus) - 1)]
    return min(pool, key=lambda c: (abs(ratings[c].mu - t), ratings[c].sigma, c))


def _nearest_targets(
    bot: Rating, ratings: list[Rating], targets: list[float]
) -> list[int]:
    """Distinct established opponents nearest each target in order."""
    pool = _established(ratings, len(targets))
    picked: list[int] = []
    used: set[int] = set()
    for t in targets:
        cands = [c for c in pool if c not in used]
        if not cands:
            cands = [c for c in range(len(ratings)) if c not in used]
        if not cands:
            break
        i = min(cands, key=lambda c: (abs(ratings[c].mu - t), ratings[c].sigma, c))
        used.add(i)
        picked.append(i)
    return picked


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
    # Exp (iter 7, MSE): Approach 1 pipeline (2d, 5p, 10p, 5p, 3d).
    if budget_left > 26:
        if budget_left == 30:
            return [_pct_anchor(ratings, 0.5)]
        med = _pct_anchor(ratings, 0.5)
        q = 0.75 if bot.mu >= ratings[med].mu else 0.25
        return [_pct_anchor(ratings, q)]
    if budget_left > 21:
        s = bot.sigma
        return _nearest_targets(bot, ratings, [bot.mu + s, bot.mu, bot.mu, bot.mu - s])
    if budget_left > 11:
        dist = NormalDist(bot.mu, max(bot.sigma, 0.5))
        return _nearest_targets(
            bot, ratings, [dist.inv_cdf(0.1 * j) for j in range(1, 10)]
        )
    if budget_left > 6:
        s = bot.sigma
        return _nearest_targets(
            bot,
            ratings,
            [bot.mu - 0.3 * s, bot.mu, bot.mu, bot.mu + 0.3 * s],
        )
    if budget_left == 6:
        return [_closest(bot, ratings)]
    if budget_left == 4:
        order = sorted(
            range(len(ratings)),
            key=lambda i: (abs(ratings[i].mu - bot.mu), ratings[i].sigma, i),
        )
        for i in order:
            if ratings[i].mu >= bot.mu:
                return [i]
        return [order[0]]
    return [min(range(len(ratings)), key=lambda i: (ratings[i].sigma, i))]
