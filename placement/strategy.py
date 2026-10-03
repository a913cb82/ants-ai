"""Placement strategy. Optimise select_next_game."""

from dataclasses import dataclass
from statistics import NormalDist  # noqa: F401 (kept for candidate reuse)


@dataclass
class Rating:
    mu: float
    sigma: float


def _nearest_to(ratings: list[Rating], target: float, used: set[int]) -> int:
    return min(
        (c for c in range(len(ratings)) if c not in used),
        key=lambda c: (abs(ratings[c].mu - target), ratings[c].sigma, c),
    )


def _closest(bot: Rating, ratings: list[Rating]) -> int:
    """Pool index nearest bot.mu, low sigma then low index on ties."""
    return min(
        range(len(ratings)),
        key=lambda i: (abs(ratings[i].mu - bot.mu), ratings[i].sigma, i),
    )


def _percentile(ratings: list[Rating], p: float) -> int:
    order = sorted(range(len(ratings)), key=lambda i: (ratings[i].mu, i))
    return order[min(int(p * (len(order) - 1)), len(order) - 1)]


def _deciles(ratings: list[Rating], k: int) -> list[int]:
    order = sorted(range(len(ratings)), key=lambda i: (ratings[i].mu, i))
    n = len(order)
    picks = list(
        dict.fromkeys(order[min(int(j * (n - 1) / 10), n - 1)] for j in range(1, 10))
    )
    return picks[:k]


def select_next_game(bot: Rating, ratings: list[Rating], budget_left: int) -> list[int]:
    """Return opponent ids for the next game.

    Each id is an index into ratings. Game size is len(return) + 1.
    budget_left counts all remaining slots, including the bot.
    A duel costs 2. A 10p game costs 10. Return [] if budget_left < 2.
    The harness clips the return to budget_left and the pool size.
    """
    if not ratings or budget_left < 2:
        return []
    # Exp (bold, Approach 1): 2p, 2p, 5p, 10p, 5p, 2p, 2p, 2p.
    sigma = max(bot.sigma, 0.5)
    if budget_left > 28:  # M1: low anchor at the 50th percentile.
        return [_percentile(ratings, 0.50)]
    if budget_left > 26:  # M2: binary search, win path iff mu rose.
        return [_percentile(ratings, 0.75 if bot.mu >= 25.0 else 0.25)]
    if budget_left > 21:  # M3: 5p cluster at +1s, s, s, -1s.
        targets = [bot.mu + sigma, bot.mu, bot.mu, bot.mu - sigma]
        picked, used = [], set()
        for t in targets:
            if len(used) >= min(4, budget_left - 1, len(ratings)):
                break
            i = _nearest_to(ratings, t, used)
            used.add(i)
            picked.append(i)
        return picked
    if budget_left > 11:  # M4: decile-stratified 10p.
        return _deciles(ratings, min(9, budget_left - 1, len(ratings)))
    if budget_left > 6:  # M5: tight 5p, closest mus only.
        picked, used = [], set()
        for _ in range(min(4, budget_left - 1, len(ratings))):
            i = _nearest_to(ratings, bot.mu, used)
            used.add(i)
            picked.append(i)
        return picked
    return [_closest(bot, ratings)]  # M6-8: precision duels.
