"""Prioritized fictitious self-play (PFSP) opponent sampling.

Phase 1 of ml/runs/plan-league.md. PURE functions only: no imports from
ml/*, no archive/disk/network access. All samplers take explicit records
arguments plus a caller-owned random.Random, and return one opponent id,
deterministic given a seeded rng.

Uncertainty is Bayesian UCB: each pair carries a Beta(w+1, l+1)
posterior under a uniform prior, scored as mean + UCB_C * std. The UCB
feeds the monotone branches (squared, linear_capped), where optimism
points at discovery; the even-seeking variance branches use the
posterior mean (best estimate of evenness -- optimism would push
strangers away from 0.5 and anti-explore). No game-count special cases
anywhere.

Weighting functions take a score p (UCB for monotone branches,
posterior mean for the even-seeking branch):
linear p, squared p^2 (seeks counters/nemeses), variance p(1-p)
(peaks at even = learning-rich), linear_capped min(p, 0.5)
(no single-nemesis obsession). The cap binds optimism above 0.5: for LE
that strong a pull still only ties the best known victims, and the
first games resolve it.

Role policies (mini-AlphaStar league sampling):
- main: with probability 0.5 squared-weighted by opponent UCB vs
  me (seeks counters), else variance-weighted.
- ME: always the current main (no fallback, no threshold -- the ME's
  whole job is exploiting the main; blowout windows are the honest
  price).
- LE: linear_capped over all historicals by own UCB (seeks
  victims/holes without single-opponent domination)."""

from __future__ import annotations

import math
import random

# Prior mean: uniform Beta(1,1) -- strangers rate even.
PRIOR_MEAN = 0.5
# Main policy: probability of the squared (counter-seeking) branch.
MAIN_SQUARED_PROB = 0.5
# UCB exploration strength: score = posterior mean + UCB_C * std.
UCB_C = 1.0

# Records map (id_a, id_b) -> [wins_a, wins_b].
Records = dict[tuple[str, str], list[int]]
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
    """Posterior mean of a vs b under a uniform Beta(1,1) prior.
    (wins_a + 1) / (total + 2): unseen/scoreless pairs rate 0.5
    (the prior mean, no special case). Record keys read either order."""
    if (a, b) in records:
        wins_a, wins_b = records[(a, b)]
    elif (b, a) in records:
        wins_b, wins_a = records[(b, a)]
    else:
        return PRIOR_MEAN
    return (wins_a + 1) / (wins_a + wins_b + 2)


def ucb(a: str, b: str, records: Records, c: float = UCB_C) -> float:
    """Bayesian UCB score of a vs b: posterior mean + c * posterior std.
    Beta(wins_a + 1, wins_b + 1) under the uniform prior, clipped to
    [0, 1]. Unseen pairs score highest (maximum uncertainty); the bonus
    decays as games accumulate. Feeds the weighting functions below."""
    if (a, b) in records:
        wins_a, wins_b = records[(a, b)]
    elif (b, a) in records:
        wins_b, wins_a = records[(b, a)]
    else:
        wins_a, wins_b = 0, 0
    alpha, beta = wins_a + 1, wins_b + 1
    total = alpha + beta
    mean = alpha / total
    var = alpha * beta / (total * total * (total + 1))
    return min(1.0, mean + c * math.sqrt(var))


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
    rng: random.Random,
) -> str:
    """Main-learner opponent: 50% squared-weighted by opponent win fraction
    vs me (seeks counters), else variance-weighted (even = learning-rich)."""
    pool = _lobby(learner_id, candidates)
    if rng.random() < MAIN_SQUARED_PROB:
        weights = [squared(ucb(c, learner_id, records)) for c in pool]
    else:
        weights = [variance(win_fraction(c, learner_id, records))
                   for c in pool]
    return _weighted_pick(pool, weights, rng)


def me_sample(main_id: str) -> str:
    """ME opponent: always the current main. No fallback, no threshold."""
    return main_id


def le_sample(
    learner_id: str,
    candidates: list[str],
    records: Records,
    rng: random.Random,
) -> str:
    """LE opponent: linear_capped over all historicals by own UCB
    (seeks victims/holes; the cap prevents single-opponent domination
    and binds optimism above 0.5 -- newcomers tie the best known
    victims until their first games resolve them)."""
    pool = _lobby(learner_id, candidates)
    weights = [linear_capped(ucb(learner_id, c, records)) for c in pool]
    return _weighted_pick(pool, weights, rng)
