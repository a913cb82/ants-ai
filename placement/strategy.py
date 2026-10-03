"""Placement strategy. Optimise select_next_game."""

from dataclasses import dataclass


@dataclass
class Rating:
    mu: float
    sigma: float


def select_next_game(bot: Rating, ratings: list[Rating], budget_left: int) -> list[int]:
    """Return opponent ids for the next game.

    Each id is an index into ratings. Game size is len(return) + 1.
    budget_left counts all remaining slots, including the bot.
    A duel costs 2. A 10p game costs 10. Return [] if budget_left < 2.
    The harness clips the return to budget_left and the pool size.
    """
    if not ratings or budget_left < 2:
        return []
    # Exp: duels first, then FFA with late budget.
    order = sorted(range(len(ratings)), key=lambda i: (abs(ratings[i].mu - bot.mu), i))
    if budget_left > 20:
        return order[:1]
    return order[: min(9, budget_left - 1, len(order))]
