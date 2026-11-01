"""Prioritized fictitious self-play (PFSP) opponent sampling.

Phase 1 of ml/runs/plan-league.md. PURE functions only: no imports from
ml/*, no archive/disk/network access. All samplers take explicit records
arguments plus a caller-owned random.Random, and return one opponent id,
deterministic given a seeded rng. Transcribes the mini-AlphaStar
pseudocode (arXiv 2104.06890, itself from DeepMind's supplementary
pseudocode): three main branches, ME live-main threshold + fallback,
LE capped challenge-seeking.

Scores are Laplace-smoothed posterior means under a uniform Beta(1,1)
prior ((w+1)/(n+2); unseen pairs rate 0.5, as mini-AlphaStar); the
squared seeking branches add a UCB bonus (mean + UCB_C * std), our
labeled layer for small-sample exploration where DeepMind is silent.
No game-count special cases anywhere.

Weighting functions (mini-AlphaStar names and shapes):
linear p, squared p^2, variance p(1-p) (peaks at even = learning-rich),
linear_capped min(0.5, 1-p) (challenges without single-nemesis
obsession: weight peaks where the learner loses or splits, victims
sink).

Role policies (mini-AlphaStar):
- main: coin < 0.5 squared over all frozen (seeks counters); coin <
  0.65 verification (exploiter-threat squared if the worst admitted
  mean < 0.3, else forgetting-check squared over the rising suffix if
  its min < 0.7, else fall through); else self-play (live main if the
  self mean > 0.3, else variance over the main's snapshots).
- ME: the live main while the posterior-mean win-rate vs it > 0.1,
  else variance-weighted over the main's snapshots (that main's own
  children, as mini-AlphaStar).
- LE: linear_capped over all frozen by own mean (seeks even-or-stronger,
  capped; newcomers tie the max until their games resolve them)."""

from __future__ import annotations

import math
import random

# Prior mean: uniform Beta(1,1) -- strangers rate even.
PRIOR_MEAN = 0.5
# Main policy: squared branch below this coin, verification below this
# plus VERIFICATION_PROB, else self-play/curriculum.
MAIN_SQUARED_PROB = 0.5
VERIFICATION_PROB = 0.15
# Self-play branch: face the live main above this self mean, else
# variance over the main's snapshots (dead in single-main: self is 0.5).
SELFPLAY_THRESHOLD = 0.3
# Verification bars: exploiter-threat below this, forgetting below this.
VERIFY_EXPLOIT_BAR = 0.3
VERIFY_FORGET_BAR = 0.7
# ME policy: stay on the live main above this own mean, else fall back.
ME_STICK_THRESHOLD = 0.1
# UCB exploration strength (labeled layer): squared seeking branches
# score mean + UCB_C * std; checks and variance use the mean.
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
    """mini-AlphaStar linear_capped: min(0.5, 1-p). Weight peaks where
    the learner loses or splits (challenges without single-nemesis
    obsession); victims sink."""
    return min(0.5, 1.0 - p)


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


def _remove_monotonic_suffix(
    ids: list[str], rates: list[float]
) -> tuple[list[str], list[float]]:
    """Literal mini-AlphaStar trim: walk back from the end, keep through
    the last rise (rates[i-1] < rates[i]); a fully falling run trims to
    nothing (no forgetting to check)."""
    if not rates:
        return [], []
    for i in range(len(rates) - 1, 0, -1):
        if rates[i - 1] < rates[i]:
            return ids[: i + 1], rates[: i + 1]
    return [], []


def _verification(
    learner_id: str,
    admitted: list[str],
    snapshots: list[str],
    records: Records,
    rng: random.Random,
) -> str | None:
    """mini-AlphaStar verification branch: exploiter-threat squared if the
    worst admitted mean < 0.3, else forgetting-check squared over the
    rising suffix if its min < 0.7. None when nothing triggers (the
    caller falls through to self-play)."""
    if admitted:
        worst = min(win_fraction(learner_id, c, records) for c in admitted)
        if worst < VERIFY_EXPLOIT_BAR:
            return _weighted_pick(
                admitted,
                [squared(ucb(learner_id, c, records)) for c in admitted],
                rng,
            )
    if snapshots:
        rates = [win_fraction(learner_id, c, records) for c in snapshots]
        kept, kept_rates = _remove_monotonic_suffix(snapshots, rates)
        if kept and min(kept_rates) < VERIFY_FORGET_BAR:
            return _weighted_pick(
                kept,
                [squared(ucb(learner_id, c, records)) for c in kept],
                rng,
            )
    return None


def main_sample(
    learner_id: str,
    live_main: str,
    candidates: list[str],
    snapshots: list[str],
    admitted: list[str],
    records: Records,
    rng: random.Random,
) -> str:
    """mini-AlphaStar main dispatch: coin < 0.5 squared over all frozen
    (seeks counters); coin < 0.65 verification (threats, forgetting,
    else fall through); else self-play (live main above a 0.3 self mean,
    else variance over the main's snapshots)."""
    pool = [c for c in candidates if c != learner_id]
    coin = rng.random()
    if coin < MAIN_SQUARED_PROB:
        if not pool:
            return live_main
        return _weighted_pick(
            pool,
            [squared(ucb(c, learner_id, records)) for c in pool],
            rng,
        )
    if coin < MAIN_SQUARED_PROB + VERIFICATION_PROB:
        found = _verification(learner_id, admitted, snapshots, records,
                              rng)
        if found is not None:
            return found
    # Self-play / curriculum. Single-main: the self mean is the prior
    # 0.5 (no self games are recorded), so this always faces live main;
    # the variance fallback is literal transcription, unreachable here.
    if win_fraction(learner_id, live_main, records) > SELFPLAY_THRESHOLD:
        return live_main
    if snapshots:
        return _weighted_pick(
            snapshots,
            [variance(win_fraction(learner_id, c, records))
             for c in snapshots],
            rng,
        )
    return live_main


def me_sample(
    learner_id: str,
    main_id: str,
    snapshots: list[str],
    records: Records,
    rng: random.Random,
) -> str:
    """mini-AlphaStar ME: the live main while the own mean vs it > 0.1,
    else variance-weighted over the main's snapshots (that main's own
    children). Empty snapshots fall back to the live main."""
    if win_fraction(learner_id, main_id, records) > ME_STICK_THRESHOLD:
        return main_id
    if not snapshots:
        return main_id
    return _weighted_pick(
        snapshots,
        [variance(win_fraction(learner_id, c, records))
         for c in snapshots],
        rng,
    )


def le_sample(
    learner_id: str,
    candidates: list[str],
    records: Records,
    rng: random.Random,
) -> str:
    """mini-AlphaStar LE: linear_capped over all frozen by own mean
    (seeks even-or-stronger, capped; newcomers tie the max until their
    games resolve them)."""
    pool = _lobby(learner_id, candidates)
    weights = [linear_capped(win_fraction(learner_id, c, records))
               for c in pool]
    return _weighted_pick(pool, weights, rng)
