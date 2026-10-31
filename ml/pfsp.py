"""Prioritized fictitious self-play (PFSP) opponent sampling.

Phase 1 of ml/runs/plan-league.md. PURE functions only: no imports from
ml/*, no archive/disk/network access. All samplers take explicit records
arguments plus a caller-owned random.Random, and return one opponent id,
deterministic given a seeded rng.

Weighting functions take a win fraction p (unseen pairs rate 0.5):
linear p, squared p^2, variance p(1-p) (peaks at even = learning-rich),
linear_capped min(p, 0.5) (no single-nemesis obsession).

Role policies (mini-AlphaStar league sampling):
- main: with probability 0.5 squared-weighted by opponent-win-fraction vs
  me (seeks counters), else variance-weighted.
- ME: locked onto main while my win-rate vs main > 0.1, else
  variance-weighted over easier historicals by own win fraction (main is
  excluded from the fallback pool while other candidates exist).
- LE: linear_capped over all historicals by own win fraction (seeks
  victims/holes without single-opponent domination).

Newcomer boost: members with <10 total games get x5 weight in all
samplers (self-limiting; ancient well-evaluated weaklings get ~zero by
weighting alone).
"""

from __future__ import annotations

import random

# Fraction assigned to pairs with no recorded games.
UNSEEN_WIN_FRACTION = 0.5
# Main policy: probability of the squared (counter-seeking) branch.
MAIN_SQUARED_PROB = 0.5
# ME policy: stays on main while its win-rate vs main is above this.
ME_STICK_THRESHOLD = 0.1
# Newcomer boost: members below this many total games get NEWCOMER_BOOST.
NEWCOMER_GAMES = 10
NEWCOMER_BOOST = 5.0

# Records map (id_a, id_b) -> [wins_a, wins_b].
Records = dict[tuple[str, str], list[int]]
# Per-member total games map id -> games.
Totals = dict[str, int]


def linear(p: float) -> float:
    """Weight proportional to the win fraction."""
    return p


def squared(p: float) -> float:
    """Weight quadratic in the win fraction (seeks counters/nemeses)."""
    return p * p


def variance(p: float) -> float:
    """Weight peaking at even matchups (learning-rich games)."""
    return p * (1.0 - p)


def linear_capped(p: float) -> float:
    """Weight proportional to the win fraction, capped so no single
    opponent can dominate sampling."""
    return min(p, 0.5)


def win_fraction(a: str, b: str, records: Records) -> float:
    """Win fraction of a vs b. Unseen pairs (or scoreless entries) rate 0.5.
    Record keys are read in either order."""
    if (a, b) in records:
        wins_a, wins_b = records[(a, b)]
    elif (b, a) in records:
        wins_b, wins_a = records[(b, a)]
    else:
        return UNSEEN_WIN_FRACTION
    total = wins_a + wins_b
    if total <= 0:
        return UNSEEN_WIN_FRACTION
    return wins_a / total


def boosted(weight: float, opp: str, total_games: Totals) -> float:
    """Apply the newcomer boost: x5 while the opponent has <10 total games."""
    if total_games.get(opp, 0) < NEWCOMER_GAMES:
        return weight * NEWCOMER_BOOST
    return weight


def _weighted_pick(
    candidates: list[str], weights: list[float], rng: random.Random
) -> str:
    """Sample one candidate proportionally to weights (uniform if all zero)."""
    if not candidates:
        raise ValueError("_weighted_pick: no candidates to sample from")
    total = sum(weights)
    if total <= 0:
        return candidates[rng.randrange(len(candidates))]
    r = rng.random() * total
    acc = 0.0
    for cand, w in zip(candidates, weights):
        acc += w
        if r < acc:
            return cand
    return candidates[-1]


def _lobby(learner_id: str, candidates: list[str]) -> list[str]:
    """Candidate pool minus the learner itself."""
    pool = [c for c in candidates if c != learner_id]
    if not pool:
        raise ValueError("no opponents to sample from")
    return pool


def main_sample(
    learner_id: str,
    candidates: list[str],
    records: Records,
    total_games: Totals,
    rng: random.Random,
) -> str:
    """Main-learner opponent: 50% squared-weighted by opponent win fraction
    vs me (seeks counters), else variance-weighted (even = learning-rich)."""
    pool = _lobby(learner_id, candidates)
    if rng.random() < MAIN_SQUARED_PROB:
        weights = [
            boosted(squared(win_fraction(c, learner_id, records)), c, total_games)
            for c in pool
        ]
    else:
        weights = [
            boosted(variance(win_fraction(c, learner_id, records)), c, total_games)
            for c in pool
        ]
    return _weighted_pick(pool, weights, rng)


def me_sample(
    learner_id: str,
    main_id: str,
    candidates: list[str],
    records: Records,
    total_games: Totals,
    rng: random.Random,
) -> str:
    """ME opponent: main while my win-rate vs main > 0.1, else
    variance-weighted over historicals by own win fraction (seeks easier,
    learning-rich games). A fresh ME with no main games rates 0.5 and
    therefore starts on main."""
    if win_fraction(learner_id, main_id, records) > ME_STICK_THRESHOLD:
        return main_id
    pool = [c for c in candidates if c not in (learner_id, main_id)]
    if not pool:
        return main_id
    weights = [
        boosted(variance(win_fraction(learner_id, c, records)), c, total_games)
        for c in pool
    ]
    return _weighted_pick(pool, weights, rng)


def le_sample(
    learner_id: str,
    candidates: list[str],
    records: Records,
    total_games: Totals,
    rng: random.Random,
) -> str:
    """LE opponent: linear_capped over all historicals by own win fraction
    (seeks victims/holes; the cap prevents single-opponent domination)."""
    pool = _lobby(learner_id, candidates)
    weights = [
        boosted(linear_capped(win_fraction(learner_id, c, records)), c, total_games)
        for c in pool
    ]
    return _weighted_pick(pool, weights, rng)
