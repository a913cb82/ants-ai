"""PFSP opponent sampling (phase 1 of ml/runs/plan-league.md).

Pins the role-appropriate distributions of ml/pfsp.py on synthetic
matrices: weighting functions, main/victim-counter behavior, Bayesian UCB
exploration (replaces unseen=0.5 + newcomer boost), ME 0.1 stick/drop
boundary, LE spread, seeded determinism.
"""

import random
import sys
from pathlib import Path

import math

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

import pfsp


def rec(a, b, wins_a, wins_b):
    """One pair-record entry: (id_a, id_b) -> [wins_a, wins_b]."""
    return {(a, b): [wins_a, wins_b]}


def sample_many(sampler, args, seed, n):
    rng = random.Random(seed)
    return [sampler(*args, rng) for _ in range(n)]


# ---------------------------------------------------------------- weighting


def test_weighting_functions():
    assert pfsp.linear(0.75) == pytest.approx(0.75)
    assert pfsp.squared(0.5) == pytest.approx(0.25)
    assert pfsp.variance(0.5) == pytest.approx(0.25)
    assert pfsp.linear_capped(0.9) == pytest.approx(0.5)
    assert pfsp.linear_capped(0.3) == pytest.approx(0.3)


def test_variance_peaks_at_even():
    assert pfsp.variance(0.5) > pfsp.variance(0.9)
    assert pfsp.variance(0.5) > pfsp.variance(0.1)
    assert pfsp.variance(0.5) > pfsp.variance(0.0)
    assert pfsp.variance(0.5) > pfsp.variance(1.0)


def test_unseen_pairs_rate_at_prior_mean():
    # posterior mean under the uniform prior: strangers rate even.
    assert pfsp.win_fraction("me", "ghost", {}) == pytest.approx(0.5)


def test_ucb_unseen_is_prior_mean_plus_max_bonus():
    # Beta(1,1): mean 0.5, std sqrt(1/12) -- maximum uncertainty.
    assert pfsp.ucb("me", "ghost", {}) == pytest.approx(
        0.5 + math.sqrt(1 / 12))
    assert pfsp.ucb("me", "ghost", {}) <= 1.0


def test_ucb_bonus_decays_with_games():
    fresh = pfsp.ucb("me", "new", {})
    few = pfsp.ucb("me", "old", {("me", "old"): [5, 5]})
    many = pfsp.ucb("me", "vet", {("me", "vet"): [50, 50]})
    assert fresh > few > many > 0.5  # optimism fades toward the mean


def test_ucb_prefers_winners_at_equal_uncertainty():
    good = pfsp.ucb("me", "good", {("me", "good"): [3, 1]})
    bad = pfsp.ucb("me", "bad", {("me", "bad"): [1, 3]})
    assert good > bad


def test_win_fraction_reads_both_key_orders():
    # Laplace-smoothed posterior mean: (3+1)/(10+2), not raw 0.3.
    fwd = pfsp.win_fraction("me", "opp", {("me", "opp"): [3, 7]})
    rev = pfsp.win_fraction("me", "opp", {("opp", "me"): [7, 3]})
    assert fwd == pytest.approx(4 / 12)
    assert rev == pytest.approx(4 / 12)


# --------------------------------------------------------------------- main


def _main_args():
    records = {}
    records.update(rec("me", "counter", 2, 8))  # opponent wins 80%: my counter
    records.update(rec("me", "victim", 8, 2))  # opponent wins 20%: my victim
    return ("me", ["counter", "victim"], records)


def test_main_draws_counters_over_victims():
    draws = sample_many(pfsp.main_sample, _main_args(), seed=7, n=2000)
    n_counter = draws.count("counter")
    n_victim = draws.count("victim")
    assert n_counter > n_victim
    assert n_counter > 0.65 * len(draws)


def test_main_splits_unseen_evenly():
    draws = sample_many(pfsp.main_sample, ("me", ["a", "b", "c"], {}), seed=11, n=3000)
    for opp in ("a", "b", "c"):
        assert 700 < draws.count(opp) < 1300


# ----------------------------------------------------------------------- ME


def test_me_sticks_with_main_above_threshold():
    records = rec("me", "main", 2, 8)  # smoothed (2+1)/12 = 0.25 > 0.1
    for seed in range(20):
        rng = random.Random(seed)
        assert pfsp.me_sample("me", "main", ["main", "hist"], records, rng) == "main"


def test_me_fresh_with_no_games_starts_on_main():
    # no record at all: prior mean 0.5 clears the 0.1 bar.
    rng = random.Random(7)
    assert pfsp.me_sample("me", "main", ["main", "hist"], {}, rng) == "main"


def test_me_drops_main_below_threshold():
    records = {}
    records.update(rec("me", "main", 0, 10))  # my win-rate 0.0
    records.update(rec("me", "hist", 5, 5))
    draws = sample_many(
        pfsp.me_sample, ("me", "main", ["main", "hist"], records), seed=7, n=50
    )
    assert all(d == "hist" for d in draws)


def test_me_drops_main_at_exact_boundary():
    records = {}
    # smoothed (0+1)/(8+2) = exactly 0.1: not > 0.1, so drop.
    records.update(rec("me", "main", 0, 8))
    records.update(rec("me", "hist", 5, 5))
    rng = random.Random(7)
    assert pfsp.me_sample("me", "main", ["main", "hist"], records, rng) == "hist"


def test_me_fallback_prefers_even_matchups():
    records = {}
    records.update(rec("me", "main", 0, 10))  # dropped
    records.update(rec("me", "even", 5, 5))  # variance 0.25
    records.update(rec("me", "hard", 1, 9))  # variance 0.09
    records.update(rec("me", "victim", 9, 1))  # variance 0.09
    cands = ["main", "even", "hard", "victim"]
    draws = sample_many(pfsp.me_sample, ("me", "main", cands, records), seed=7, n=2000)
    assert "main" not in draws
    assert draws.count("even") > draws.count("hard")
    assert draws.count("even") > draws.count("victim")


def test_me_with_no_historicals_falls_back_to_main():
    records = rec("me", "main", 0, 10)
    rng = random.Random(7)
    assert pfsp.me_sample("me", "main", ["main"], records, rng) == "main"


# ----------------------------------------------------------------------- LE


def test_le_seeks_victims_but_does_not_obsess():
    records = {}
    records.update(rec("le", "nemesis", 0, 10))  # own ~0.08: avoided
    records.update(rec("le", "even", 5, 5))  # own 0.5 -> capped 0.5
    records.update(rec("le", "victim", 9, 1))  # own ~0.94 -> capped 0.5
    cands = ["nemesis", "even", "victim", "unseen"]  # unseen UCB -> capped 0.5
    draws = sample_many(pfsp.le_sample, ("le", cands, records), seed=7, n=3000)
    assert draws.count("victim") > draws.count("nemesis")
    assert draws.count("victim") < 0.45 * len(draws)
    assert draws.count("nemesis") < 0.15 * len(draws)


# --------------------------------------------- UCB exploration (was newcomer boost)


def test_ucb_explores_newcomers_over_known_even():
    # unseen (max uncertainty) vs well-evaluated even: the newcomer wins
    # draws without any game-count special case.
    records = {}
    records.update(rec("me", "vet", 50, 50))
    draws = sample_many(
        pfsp.main_sample, ("me", ["new", "vet"], records), seed=7, n=1500
    )
    assert draws.count("new") > draws.count("vet")


def test_ucb_me_fallback_shares_evenly_with_newcomers():
    # the even branch uses the posterior mean: a stranger (0.5) ties a
    # known-even veteran, so newcomers get fair share -- never
    # anti-explored, never force-boosted.
    records = {}
    records.update(rec("me", "main", 0, 10))
    records.update(rec("me", "vet", 50, 50))
    draws = sample_many(
        pfsp.me_sample,
        ("me", "main", ["main", "new", "vet"], records),
        seed=7,
        n=1500,
    )
    assert abs(draws.count("new") - draws.count("vet")) < 0.12 * len(draws)


def test_ucb_le_explores_newcomers():
    records = {}
    records.update(rec("le", "vet", 5, 50))  # known bad: avoided either way
    records.update(rec("le", "even", 50, 50))  # known even: capped 0.5
    draws = sample_many(
        pfsp.le_sample, ("le", ["new", "even", "vet"], records), seed=7, n=1500
    )
    assert draws.count("new") > draws.count("vet")
    assert draws.count("even") > draws.count("vet")


# ------------------------------------------------------------ determinism


def test_seeded_determinism():
    records = {}
    records.update(rec("me", "counter", 2, 8))
    records.update(rec("me", "victim", 8, 2))
    records.update(rec("me", "main", 0, 10))

    main_args = ("me", ["counter", "victim"], records)
    me_args = ("me", "main", ["main", "counter", "victim"], records)
    le_args = ("me", ["counter", "victim"], records)

    assert sample_many(pfsp.main_sample, main_args, 1234, 30) == sample_many(
        pfsp.main_sample, main_args, 1234, 30
    )
    assert sample_many(pfsp.me_sample, me_args, 1234, 30) == sample_many(
        pfsp.me_sample, me_args, 1234, 30
    )
    assert sample_many(pfsp.le_sample, le_args, 1234, 30) == sample_many(
        pfsp.le_sample, le_args, 1234, 30
    )


def test_empty_pool_raises():
    rng = random.Random(7)
    with pytest.raises(ValueError):
        pfsp.main_sample("me", [], {}, rng)
    with pytest.raises(ValueError):
        pfsp.le_sample("me", [], {}, rng)
