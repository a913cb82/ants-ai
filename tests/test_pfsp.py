"""PFSP opponent sampling (phase 1 of ml/runs/plan-league.md).

Pins the mini-AlphaStar role policies of ml/pfsp.py on synthetic
matrices: weighting functions, main 3-branch dispatch (squared /
verification / self-play-curriculum), ME live-main threshold +
variance fallback, LE capped challenge-seeking, seeded determinism.
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
    assert pfsp.squared(0.5) == pytest.approx(0.25)
    assert pfsp.variance(0.5) == pytest.approx(0.25)
    # MAS linear_capped: min(0.5, 1-p) -- challenges, capped.
    assert pfsp.linear_capped(0.9) == pytest.approx(0.1)
    assert pfsp.linear_capped(0.5) == pytest.approx(0.5)
    assert pfsp.linear_capped(0.1) == pytest.approx(0.5)


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
    records.update(rec("me", "counter", 2, 8))  # opp wins 80%: my counter
    records.update(rec("me", "victim", 8, 2))  # opp wins 20%: my victim
    return ("me", "main", ["counter", "victim"], [], [], records)


def test_main_branch1_draws_counters_over_victims():
    # branch 1 (coin < 0.5) is squared-UCB: counters dominate victims.
    # Other branches return live main / snapshots, so pin the ratio
    # within the frozen draws, not the overall share.
    draws = sample_many(pfsp.main_sample, _main_args(), seed=7, n=2000)
    frozen = [d for d in draws if d in ("counter", "victim")]
    assert len(frozen) > 0.3 * len(draws)  # branch 1 fires its ~half
    assert frozen.count("counter") > 0.65 * len(frozen)


def test_main_splits_unseen_evenly():
    # unseen trio ties in branch 1 (equal UCB) and in branch-2 checks;
    # self-play adds live main. Pin the trio's internal split.
    draws = sample_many(
        pfsp.main_sample, ("me", "main", ["a", "b", "c"], [], [], {}),
        seed=11, n=3000)
    assert "main" in draws  # self-play/curriculum branch fires
    trio = [d for d in draws if d in ("a", "b", "c")]
    for opp in ("a", "b", "c"):
        assert 0.28 * len(trio) < trio.count(opp) < 0.39 * len(trio)


def test_main_verification_hunts_exploiter_threat():
    # main loses to admitted e1 (mean 2/12 < 0.3): verification fires.
    records = {}
    records.update(rec("me", "e1", 1, 9))
    args = ("me", "main", ["e1"], [], ["e1"], records)
    draws = sample_many(pfsp.main_sample, args, seed=5, n=1)
    assert draws == ["e1"]  # seed 5 opens in the [0.5, 0.65) window


def test_main_verification_stands_down_when_safe():
    # e1 beaten (mean 10/12): no trigger, falls through to self-play.
    records = {}
    records.update(rec("me", "e1", 9, 1))
    args = ("me", "main", ["e1"], [], ["e1"], records)
    draws = sample_many(pfsp.main_sample, args, seed=5, n=1)
    assert draws == ["main"]


def test_main_verification_checks_forgetting():
    # snapshots s1 beaten?? no: s1 beats main (mean 10/12 for s1... see
    # below); rising suffix [s1-loses, s2-wins]... construct: main vs s1
    # mean 0.167 (main loses), vs s2 mean 0.833 (main wins): suffix
    # [0.167, 0.833] rises -> keep both -> min 0.167 < 0.7 -> fire.
    records = {}
    records.update(rec("me", "s1", 1, 9))  # main mean 2/12
    records.update(rec("me", "s2", 9, 1))  # main mean 10/12
    args = ("me", "main", ["s1", "s2"], ["s1", "s2"], [], records)
    draws = sample_many(pfsp.main_sample, args, seed=5, n=400)
    assert set(draws) <= {"s1", "s2", "main"}
    assert draws.count("s1") > draws.count("s2")  # squared seeks s1


def test_main_selfplay_faces_live_main():
    args = ("me", "main", ["counter"], [], [], {})
    draws = sample_many(pfsp.main_sample, args, seed=0, n=1)
    assert draws == ["main"]  # seed 0 opens past 0.65; self-rate 0.5


# ----------------------------------------------------------------------- ME


def test_me_stays_on_live_main_when_winning():
    records = rec("me", "main", 8, 2)  # smoothed 9/12 > 0.1
    for seed in range(20):
        rng = random.Random(seed)
        assert pfsp.me_sample("me", "main", [], records, rng) == "main"


def test_me_stays_on_live_main_with_no_games():
    assert pfsp.me_sample("me", "main", [], {},
                          random.Random(7)) == "main"


def test_me_drops_to_snapshots_when_losing():
    records = {}
    records.update(rec("me", "main", 0, 10))  # smoothed 1/12 < 0.1
    records.update(rec("me", "s1", 5, 5))  # even: variance 0.25
    records.update(rec("me", "s2", 0, 10))  # nemesis: variance ~0.08
    args = ("me", "main", ["s1", "s2"], records)
    draws = sample_many(pfsp.me_sample, args, seed=7, n=1500)
    assert "main" not in draws
    assert draws.count("s1") > draws.count("s2")


def test_me_drops_at_exact_boundary():
    # smoothed (0+1)/(8+2) = exactly 0.1: not > 0.1, so drop.
    records = {}
    records.update(rec("me", "main", 0, 8))
    records.update(rec("me", "s1", 5, 5))
    rng = random.Random(7)
    assert pfsp.me_sample("me", "main", ["s1"], records, rng) == "s1"


def test_me_empty_snapshots_stays_on_main():
    records = rec("me", "main", 0, 10)
    assert pfsp.me_sample("me", "main", [], records,
                          random.Random(7)) == "main"


# ----------------------------------------------------------------------- LE


def test_le_seeks_challenges_not_victims():
    # MAS orientation: min(0.5, 1-mean) -- weight peaks where the LE
    # loses or splits, victims sink.
    records = {}
    records.update(rec("le", "nemesis", 0, 10))  # mean ~0.08 -> 0.5
    records.update(rec("le", "even", 5, 5))  # mean 0.5 -> 0.5
    records.update(rec("le", "victim", 9, 1))  # mean ~0.92 -> ~0.08
    cands = ["nemesis", "even", "victim", "unseen"]  # unseen -> 0.5
    draws = sample_many(pfsp.le_sample, ("le", cands, records), seed=7,
                        n=3000)
    assert draws.count("victim") < 0.15 * len(draws)
    trio = [d for d in draws if d != "victim"]
    for opp in ("nemesis", "even", "unseen"):
        assert 0.28 * len(trio) < trio.count(opp) < 0.39 * len(trio)


# --------------------------------------------- UCB exploration (was newcomer boost)


def test_ucb_explores_newcomers_over_known_even():
    # unseen (max uncertainty) vs well-evaluated even: the newcomer wins
    # draws without any game-count special case.
    records = {}
    records.update(rec("me", "vet", 50, 50))
    draws = sample_many(
        pfsp.main_sample, ("me", "main", ["new", "vet"], [], [], records),
        seed=7, n=1500
    )
    frozen = [d for d in draws if d != "main"]
    assert frozen.count("new") > frozen.count("vet")


# ------------------------------------------------------------ determinism


def test_seeded_determinism():
    records = {}
    records.update(rec("me", "counter", 2, 8))
    records.update(rec("me", "victim", 8, 2))
    records.update(rec("me", "main", 0, 10))

    main_args = ("me", "main", ["counter", "victim"], [], [], records)
    me_args = ("me", "main", [], records)
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
        pfsp.le_sample("me", [], {}, rng)


def test_main_empty_pool_falls_back_to_live_main():
    # a lone main still trains: the degenerate pool faces live main.
    rng = random.Random(7)
    assert pfsp.main_sample("me", "main", [], [], [], {}, rng) == "main"
