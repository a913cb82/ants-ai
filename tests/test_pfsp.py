"""PFSP opponent sampling (phase 1 of ml/runs/plan-league.md).

Pins the role-appropriate distributions of ml/pfsp.py on synthetic
matrices: weighting functions, main/victim-counter behavior, unseen=0.5,
ME 0.1 stick/drop boundary, LE spread, newcomer boost, seeded determinism.
"""

import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

import pfsp


def rec(a, b, wins_a, wins_b):
    """One pair-record entry: (id_a, id_b) -> [wins_a, wins_b]."""
    return {(a, b): [wins_a, wins_b]}


def totals(**kwargs):
    return dict(kwargs)


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


def test_unseen_pairs_rate_at_half():
    assert pfsp.win_fraction("me", "ghost", {}) == pytest.approx(0.5)
    # variance is maximal there: unseen pairs are learning-rich
    assert pfsp.variance(pfsp.win_fraction("me", "ghost", {})) == pytest.approx(
        pfsp.variance(0.5)
    )


def test_win_fraction_reads_both_key_orders():
    fwd = pfsp.win_fraction("me", "opp", {("me", "opp"): [3, 7]})
    rev = pfsp.win_fraction("me", "opp", {("opp", "me"): [7, 3]})
    assert fwd == pytest.approx(0.3)
    assert rev == pytest.approx(0.3)


# --------------------------------------------------------------------- main


def _main_args():
    records = {}
    records.update(rec("me", "counter", 2, 8))  # opponent wins 80%: my counter
    records.update(rec("me", "victim", 8, 2))  # opponent wins 20%: my victim
    tot = totals(me=100, counter=100, victim=100)
    return ("me", ["counter", "victim"], records, tot)


def test_main_draws_counters_over_victims():
    draws = sample_many(pfsp.main_sample, _main_args(), seed=7, n=2000)
    n_counter = draws.count("counter")
    n_victim = draws.count("victim")
    assert n_counter > n_victim
    assert n_counter > 0.65 * len(draws)


def test_main_splits_unseen_evenly():
    tot = totals(me=100, a=100, b=100, c=100)
    draws = sample_many(pfsp.main_sample, ("me", ["a", "b", "c"], {}, tot), seed=11, n=3000)
    for opp in ("a", "b", "c"):
        assert 700 < draws.count(opp) < 1300


# ----------------------------------------------------------------------- ME


def test_me_sticks_with_main_above_threshold():
    records = rec("me", "main", 2, 8)  # my win-rate 0.2 > 0.1
    tot = totals(me=100, main=500, hist=100)
    for seed in range(20):
        rng = random.Random(seed)
        assert pfsp.me_sample("me", "main", ["main", "hist"], records, tot, rng) == "main"


def test_me_drops_main_below_threshold():
    records = {}
    records.update(rec("me", "main", 0, 10))  # my win-rate 0.0
    records.update(rec("me", "hist", 5, 5))
    tot = totals(me=100, main=500, hist=100)
    draws = sample_many(
        pfsp.me_sample, ("me", "main", ["main", "hist"], records, tot), seed=7, n=50
    )
    assert all(d == "hist" for d in draws)


def test_me_drops_main_at_exact_boundary():
    records = {}
    records.update(rec("me", "main", 1, 9))  # my win-rate exactly 0.1: not > 0.1
    records.update(rec("me", "hist", 5, 5))
    tot = totals(me=100, main=500, hist=100)
    rng = random.Random(7)
    assert pfsp.me_sample("me", "main", ["main", "hist"], records, tot, rng) == "hist"


def test_me_fallback_prefers_even_matchups():
    records = {}
    records.update(rec("me", "main", 0, 10))  # dropped
    records.update(rec("me", "even", 5, 5))  # variance 0.25
    records.update(rec("me", "hard", 1, 9))  # variance 0.09
    records.update(rec("me", "victim", 9, 1))  # variance 0.09
    tot = totals(me=100, main=500, even=100, hard=100, victim=100)
    cands = ["main", "even", "hard", "victim"]
    draws = sample_many(pfsp.me_sample, ("me", "main", cands, records, tot), seed=7, n=2000)
    assert "main" not in draws
    assert draws.count("even") > draws.count("hard")
    assert draws.count("even") > draws.count("victim")


def test_me_with_no_historicals_falls_back_to_main():
    records = rec("me", "main", 0, 10)
    tot = totals(me=100, main=500)
    rng = random.Random(7)
    assert pfsp.me_sample("me", "main", ["main"], records, tot, rng) == "main"


# ----------------------------------------------------------------------- LE


def test_le_seeks_victims_but_does_not_obsess():
    records = {}
    records.update(rec("le", "nemesis", 1, 9))  # own 0.1 -> weight 0.1
    records.update(rec("le", "even", 5, 5))  # own 0.5 -> weight 0.5
    records.update(rec("le", "victim", 9, 1))  # own 0.9 -> capped 0.5
    tot = totals(le=100, nemesis=100, even=100, victim=100, unseen=100)
    cands = ["nemesis", "even", "victim", "unseen"]  # unseen -> weight 0.5
    draws = sample_many(pfsp.le_sample, ("le", cands, records, tot), seed=7, n=3000)
    assert draws.count("victim") > draws.count("nemesis")
    assert draws.count("victim") < 0.45 * len(draws)
    assert draws.count("nemesis") < 0.15 * len(draws)


# --------------------------------------------------------- newcomer boost


def test_newcomer_boost_main():
    records = {}
    records.update(rec("me", "new", 5, 5))
    records.update(rec("me", "old", 5, 5))
    tot = totals(me=100, new=3, old=100)
    draws = sample_many(
        pfsp.main_sample, ("me", ["new", "old"], records, tot), seed=7, n=1500
    )
    assert draws.count("new") > 0.75 * len(draws)


def test_newcomer_boost_me_fallback():
    records = {}
    records.update(rec("me", "main", 0, 10))
    records.update(rec("me", "new", 5, 5))
    records.update(rec("me", "old", 5, 5))
    tot = totals(me=100, main=500, new=3, old=100)
    draws = sample_many(
        pfsp.me_sample,
        ("me", "main", ["main", "new", "old"], records, tot),
        seed=7,
        n=1500,
    )
    assert draws.count("new") > 0.75 * len(draws)


def test_newcomer_boost_le():
    records = {}
    records.update(rec("le", "new", 5, 5))
    records.update(rec("le", "old", 5, 5))
    tot = totals(le=100, new=3, old=100)
    draws = sample_many(
        pfsp.le_sample, ("le", ["new", "old"], records, tot), seed=7, n=1500
    )
    assert draws.count("new") > 0.75 * len(draws)


# ------------------------------------------------------------ determinism


def test_seeded_determinism():
    records = {}
    records.update(rec("me", "counter", 2, 8))
    records.update(rec("me", "victim", 8, 2))
    records.update(rec("me", "main", 0, 10))
    tot = totals(me=100, main=500, counter=100, victim=100)

    main_args = ("me", ["counter", "victim"], records, tot)
    me_args = ("me", "main", ["main", "counter", "victim"], records, tot)
    le_args = ("me", ["counter", "victim"], records, tot)

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
    tot = totals(me=100)
    rng = random.Random(7)
    with pytest.raises(ValueError):
        pfsp.main_sample("me", [], {}, tot, rng)
    with pytest.raises(ValueError):
        pfsp.le_sample("me", [], {}, tot, rng)
