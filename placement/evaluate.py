"""Evaluate a placement strategy. Standalone: stdlib + openskill only."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import random
import statistics
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from openskill.models import BradleyTerryFull

PRIOR_MU = 25.0
PRIOR_SIGMA = 25.0 / 3
BETA = 25.0 / 6
BUDGET = 30
TRUE_LOW = -50.0
TRUE_HIGH = 100.0
MAX_SIZE = 10


@dataclass
class Rating:
    mu: float
    sigma: float


Select = Callable[[Rating, list[Rating], int], list[int]]


def load_strategy(spec: str) -> Select:
    """Load select func from FILE[:FUNC] or MODULE[:FUNC]."""
    file, _, func = spec.partition(":")
    func = func or "select_next_game"
    if file.endswith(".py"):
        path = Path(file)
        if not path.is_absolute():
            path = Path.cwd() / path
        mod_name = f"strategy_{path.stem}"
        mod_spec = importlib.util.spec_from_file_location(mod_name, path)
        if mod_spec is None or mod_spec.loader is None:
            raise ImportError(f"cannot load {spec}")
        mod = importlib.util.module_from_spec(mod_spec)
        sys.modules[mod_name] = mod
        mod_spec.loader.exec_module(mod)
        return getattr(mod, func)
    mod = importlib.import_module(file or "strategy")
    return getattr(mod, func)


def run(n_bots: int, seed: int, select: Select) -> float:
    """Add n_bots in order. Return corr(recorded mu, mu_true)."""
    rng = random.Random(seed)
    model = BradleyTerryFull()
    ratings: list[Rating] = []
    trues: list[float] = []
    mus: list[float] = []
    for _ in range(n_bots):
        mu_true = rng.uniform(TRUE_LOW, TRUE_HIGH)
        bot = Rating(PRIOR_MU, PRIOR_SIGMA)
        slots = 0
        while slots < BUDGET and ratings:
            picks = select(bot, list(ratings), BUDGET - slots)
            picks = [p for p in dict.fromkeys(picks) if 0 <= p < len(ratings)]
            picks = picks[: BUDGET - slots - 1][: MAX_SIZE - 1]
            if not picks:
                break
            field = [bot] + [ratings[i] for i in picks]
            field_true = [mu_true] + [trues[i] for i in picks]
            perfs = [rng.gauss(t, BETA) for t in field_true]
            order = sorted(range(len(field)), key=lambda i: -perfs[i])
            ranks = [0] * len(field)
            for rank, idx in enumerate(order, start=1):
                ranks[idx] = rank
            teams = [[model.rating(mu=r.mu, sigma=r.sigma)] for r in field]
            new_teams = model.rate(teams, ranks=ranks)
            bot = Rating(new_teams[0][0].mu, new_teams[0][0].sigma)
            for j, i in enumerate(picks, start=1):
                ratings[i] = Rating(new_teams[j][0].mu, new_teams[j][0].sigma)
            slots += len(field)
        ratings.append(bot)
        trues.append(mu_true)
        mus.append(bot.mu)
    if len(mus) < 2:
        return 0.0
    try:
        return statistics.correlation(mus, trues)
    except statistics.StatisticsError:
        return 0.0


def main() -> None:
    default = f"{Path(__file__).with_name('strategy.py')}:select_next_game"
    parser = argparse.ArgumentParser()
    parser.add_argument("--bots", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--strategy", default=default)
    args = parser.parse_args()
    select = load_strategy(args.strategy)
    corr = run(args.bots, args.seed, select)
    print(f"bots={args.bots} seed={args.seed} strategy={args.strategy} corr={corr:.4f}")


if __name__ == "__main__":
    main()
