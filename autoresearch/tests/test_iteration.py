"""Autoresearch iteration: budget counting, selection, scoring."""

import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "autoresearch"))
sys.path.insert(0, str(ROOT / "league"))


def test_counts_splits_duels_and_ffa():
    from iteration import counts

    recs = [
        {"field": ["a", "b"]},
        {"field": ["a"] + ["x"] * 9},
        {"field": ["a"] + ["x"] * 9},
        {"field": ["a"] + ["x"] * 5},
        {"field": ["x", "y"]},
    ]
    assert counts(recs, "a") == {"duels": 1, "ffa": {10: 2, 6: 1}}


def test_planned_leaves_the_right_budget():
    from iteration import planned

    recs = [{"field": ["a", "b"]}, {"field": ["a"] + ["x"] * 9}]
    duels_left, sizes = planned(recs, "a", 7, [10, 6])
    assert duels_left == 6 and sizes == [6]


def test_planned_never_negative():
    from iteration import planned

    recs = [{"field": ["a", "b"]} for _ in range(9)]
    duels_left, sizes = planned(recs, "a", 7, [10, 6])
    assert duels_left == 0 and sizes == [10, 6]


def test_info_duel_picks_best_draw_over_40_nearest():
    from iteration import info_duel_opponent
    from matchmake import new_model

    ratings = {"cand": {"mu": 25, "sigma": 8.33, "games": 0}}
    cands = []
    for i in range(50):
        ratings[f"peer{i}"] = {"mu": 25.0, "sigma": 1.0, "games": 20}
        cands.append(f"peer{i}")
    ratings["close-noisy"] = {"mu": 25.0, "sigma": 8.0, "games": 1}
    ratings["far-solid"] = {"mu": 60, "sigma": 2.0, "games": 20}
    opp = info_duel_opponent(
        new_model(), "cand", cands, ratings, {c: i for i, c in enumerate(cands)}
    )
    assert opp == "peer0"
    opp = info_duel_opponent(
        new_model(),
        "cand",
        ["close-noisy", "far-solid"],
        ratings,
        {"close-noisy": 0, "far-solid": 1},
    )
    assert opp == "close-noisy"


def test_pick_maps_are_distinct():
    from iteration import pick_maps

    maps = [f"tools/maps/m{i}.map" for i in range(10)]
    picked = pick_maps(random.Random(0), maps, 5)
    assert len(picked) == 5 and len(set(picked)) == 5


def test_pick_maps_caps_at_pool_size():
    from iteration import pick_maps

    maps = ["tools/maps/a.map", "tools/maps/b.map"]
    assert len(pick_maps(random.Random(0), maps, 5)) == 2


def test_score_is_mu():
    from iteration import score

    ratings = {"x": {"mu": 30.0, "sigma": 4.0, "games": 10}}
    assert score(ratings, "x") == (30.0, 4.0, 30.0)


def test_unseen_bot_scores_at_the_prior():
    from iteration import score

    mu, sigma, sc = score({}, "fresh")
    assert (mu, sigma, sc) == (25.0, 25.0 / 3, 25.0)


def test_candidate_id_is_path_plus_sha():
    from iteration import ROOT as AROOT
    from iteration import candidate_id

    bid = candidate_id(AROOT, "autoresearch/bot/main.bot")
    assert bid.startswith("autoresearch/bot/main.bot-")


def test_short_name_labels_main_manifests_by_dir():
    from iteration import short_name

    assert short_name("autoresearch/bot/main.bot-abc1234") == "autoresearch/bot"
    assert short_name("tools/sample_bots/python/GreedyBot.bot-abc1234") == "GreedyBot"


def test_budget_tags_the_score():
    from iteration import BUDGET

    assert "score=mu" in BUDGET


def test_ffa_sizes_are_the_champion_schedule():
    from iteration import DUELS, FFA_SIZES

    assert DUELS == 7
    assert list(FFA_SIZES) == [10, 6]


def test_result_line_marks_candidate_and_disambiguates():
    from iteration import result_line

    rec = {
        "result": [
            "tools/sample_bots/python/GreedyBot.bot-abc1234",
            "tools/sample_bots/python/GreedyBot.bot-def5678",
        ]
    }
    assert (
        result_line(rec, "tools/sample_bots/python/GreedyBot.bot-def5678")
        == "GreedyBot@abc1234 > *GreedyBot@def5678"
    )
    assert result_line(rec) == "GreedyBot@abc1234 > GreedyBot@def5678"


def test_iteration_summary_reports_duels_and_ffa_ranks():
    from iteration import iteration_summary

    recs = [
        {"field": ["c", "x"], "result": ["c", "x"]},
        {"field": ["y", "c"], "result": ["y", "c"]},
        {"field": ["c", "a", "b", "d"], "result": ["c", "a", "b", "d"]},
        {"field": ["a", "b", "c", "d", "e"], "result": ["a", "b", "c", "d", "e"]},
    ]
    assert iteration_summary(recs, "c") == "games: 1-1, FFA ranks 4p:1 5p:3"


def test_progress_roundtrip_and_champion(tmp_path):
    from iteration import read_progress, record_report

    p = tmp_path / "PROGRESS.jsonl"
    row, prior, appended = record_report("a-1", 30.0, 3.0, 30.0, 8, path=p)
    assert appended and prior is None and row["score"] == 30.0
    row, prior, appended = record_report("b-2", 35.0, 4.0, 35.0, 8, path=p)
    assert appended and prior is not None
    assert prior["bot"] == "a-1"
    row, prior, appended = record_report("b-2", 1.0, 1.0, 1.0, 8, path=p)
    assert not appended and row["score"] == 35.0 and prior is not None
    assert prior["bot"] == "b-2"
    rows = read_progress(p)
    assert [r["bot"] for r in rows] == ["a-1", "b-2"]


def test_progress_reads_legacy_lb_rows(tmp_path):
    import json

    from iteration import read_progress

    p = tmp_path / "PROGRESS.jsonl"
    p.write_text(
        json.dumps(
            {
                "bot": "old",
                "mu": 30.0,
                "sigma": 3.0,
                "lb": 21.0,
                "games": 8,
                "champion": None,
                "date": "2026-01-01",
                "budget": "duels=5,ffa=3,turns=1000",
            }
        )
        + "\n"
    )
    rows = read_progress(p)
    assert [r["bot"] for r in rows] == ["old"]
    assert rows[0]["score"] == 21.0


def test_progress_skips_bad_lines(tmp_path):
    import json

    from iteration import read_progress

    p = tmp_path / "PROGRESS.jsonl"
    good = json.dumps(
        {
            "bot": "good",
            "mu": 25,
            "sigma": 8.0,
            "lb": 1.0,
            "games": 8,
            "champion": None,
            "date": "2026-01-01",
        }
    )
    p.write_text(good + '\nnot json\n{"bot": "bad"}\n')
    rows = read_progress(p)
    assert [r["bot"] for r in rows] == ["good"]


def test_prior_champion_only_counts_the_same_budget(tmp_path, monkeypatch):
    import iteration

    p = tmp_path / "PROGRESS.jsonl"
    monkeypatch.setattr(iteration, "BUDGET", "old")
    iteration.record_report("old-1", 40.0, 1.0, 37.0, 8, path=p)
    monkeypatch.setattr(iteration, "BUDGET", "new")
    row, prior, appended = iteration.record_report("new-2", 30.0, 5.0, 15.0, 8, path=p)
    assert appended and prior is None
    assert row["budget"] == "new"


def test_budget_flags_are_gone():
    from iteration import main

    for flag in (
        "--duels",
        "--ffa-sizes",
        "--seed",
        "--games",
        "--ratings",
        "--timeout",
        "--turns",
        "--turntime",
        "--epsilon",
        "--breadth",
        "--sigma-weight",
        "--dry-run",
    ):
        with pytest.raises(SystemExit):
            main([flag, "1"])


def test_engine_matches_main():
    import subprocess

    from iteration import ROOT as AROOT
    from pool import engine_on_main, git_env

    # The guard only means something on a clean tree. Skip while tools/
    # is mid-change (this also covers the pre-commit hook).
    for diff in (["diff", "--quiet", "HEAD"], ["diff", "--cached", "--quiet", "HEAD"]):
        changed = subprocess.run(
            ["git", "-C", str(AROOT), *diff, "--", "tools/"],
            capture_output=True,
            env=git_env(),
        ).returncode
        if changed != 0:
            pytest.skip("tools/ has uncommitted changes")
    assert engine_on_main(AROOT)


def test_iteration_refuses_when_main_not_merged(monkeypatch):
    import iteration

    monkeypatch.setattr(iteration, "engine_on_main", lambda root: True)
    monkeypatch.setattr(iteration, "main_merged", lambda root: False)
    assert iteration.main([]) == 4


def test_main_plays_records_and_never_replays(tmp_path, monkeypatch):
    import iteration

    monkeypatch.setattr(iteration, "DUELS", 1)
    monkeypatch.setattr(iteration, "FFA_SIZES", [6])
    monkeypatch.setattr(iteration, "GAMES_LOG", tmp_path / "games.jsonl")
    monkeypatch.setattr(iteration, "RATINGS_PATH", tmp_path / "ratings.json")
    monkeypatch.setattr(iteration, "PROGRESS", tmp_path / "PROGRESS.jsonl")
    monkeypatch.setattr(iteration, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(iteration, "WORKBASE", tmp_path / "work")
    # The guards have their own tests; keep this test independent of
    # the working tree.
    monkeypatch.setattr(iteration, "is_clean", lambda root: True)
    monkeypatch.setattr(iteration, "engine_on_main", lambda root: True)
    monkeypatch.setattr(iteration, "main_merged", lambda root: True)
    bid = iteration.candidate_id(iteration.ROOT, iteration.DEFAULT_BOT)
    rivals = [f"rival{i}-abc1234" for i in range(9)]
    monkeypatch.setattr(
        iteration, "pool_ids", lambda root, ratings=None: [bid] + rivals
    )

    def fake_play_one(root, field, map_rel, log_dir, rng, workbase):
        return {
            "v": 1,
            "map": map_rel,
            "turns": 1000,
            "turntime": 1000,
            "loadtime": 3000,
            "engine": "test",
            "pseed": 1,
            "eseed": 2,
            "field": list(field),
            "result": list(field),
            "length": 10,
        }

    monkeypatch.setattr(iteration, "play_one", fake_play_one)
    assert iteration.main([]) == 0
    assert len((tmp_path / "games.jsonl").read_text().splitlines()) == 2
    rows = iteration.read_progress(tmp_path / "PROGRESS.jsonl")
    assert len(rows) == 1 and rows[0]["bot"] == bid
    assert iteration.main([]) == 0
    assert len((tmp_path / "games.jsonl").read_text().splitlines()) == 2
    assert len(iteration.read_progress(tmp_path / "PROGRESS.jsonl")) == 1


def _rated(mu, sigma, games=20):
    return {"mu": mu, "sigma": sigma, "games": games}


def test_census_field_spans_full_pool_mass():
    from iteration import census_opponents

    ratings = {"cand": _rated(50, 8.0, 0)}
    for i, mu in enumerate([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]):
        ratings[f"r{i}"] = _rated(mu, 2.0)
    cands = [k for k in ratings if k != "cand"]
    opps = census_opponents(
        "cand", cands, ratings, 9, {c: i for i, c in enumerate(cands)}
    )
    assert len(opps) == 9 and "cand" not in opps
    mus = sorted(ratings[c]["mu"] for c in opps)
    assert mus[0] <= 10 and mus[-1] >= 90


def test_census_nearest_snap_ignores_sigma():
    from iteration import census_opponents

    # H owns its site but a lower-sigma neighbor sits within 0.30:
    # nearest-mu keeps H, quality snap would steal it for P.
    mus = [0, 10, 20, 30, 40, 50.0, 50.05, 60, 70, 80, 90]
    ratings = {"cand": _rated(50, 8.0, 0)}
    cands = []
    for i, mu in enumerate(mus):
        name = f"r{i}"
        ratings[name] = _rated(mu, 6.0 if mu == 50.0 else 1.0)
        cands.append(name)
    opps = census_opponents(
        "cand", cands, ratings, 9, {c: i for i, c in enumerate(cands)}
    )
    assert "r5" in opps


def test_strata_field_uses_recency_window_and_calibrated_rulers():
    from iteration import strata_opponents

    ratings = {"cand": _rated(50, 8.0, 0)}
    ordered = []
    for i in range(100):
        ratings[f"old{i}"] = _rated(i * 0.9, 0.5)
        ordered.append(f"old{i}")
    for i in range(400):
        ratings[f"new{i}"] = _rated(i * 0.25, 1.0)
        ordered.append(f"new{i}")
    for i in range(50):
        ratings[f"raw{i}"] = _rated(i * 2.0, 7.0)
        ordered.append(f"raw{i}")
    opps = strata_opponents("cand", ordered, ratings, 5)
    assert len(opps) == 5 and "cand" not in opps
    assert not any(c.startswith("old") for c in opps)
    assert all(ratings[c]["sigma"] <= 1.0 for c in opps)
    mus = [ratings[c]["mu"] for c in opps]
    assert any(m < 42 for m in mus) and any(m > 58 for m in mus)


def test_strata_quota_follows_bin_mass():
    from iteration import strata_opponents

    ratings = {"cand": _rated(50, 8.0, 0)}
    ordered = []
    for i in range(40):
        ratings[f"peer{i}"] = _rated(48.0 + i * 0.1, 1.0)
        ordered.append(f"peer{i}")
    for name, mu in (("lo", 10.0), ("hi", 90.0)):
        ratings[name] = _rated(mu, 1.0)
        ordered.append(name)
    opps = strata_opponents("cand", ordered, ratings, 5)
    peer = [c for c in opps if 42 <= ratings[c]["mu"] <= 58]
    assert len(peer) >= 3


def test_stage_field_sizes_map_to_census_and_strata(monkeypatch):
    import iteration

    calls = []

    def rec(name, val):
        calls.append(name)
        return val

    monkeypatch.setattr(
        iteration,
        "census_opponents",
        lambda bid, c, r, k, rk: rec("census", ["o"] * k),
    )
    monkeypatch.setattr(
        iteration, "strata_opponents", lambda bid, o, r, k: rec("strata", ["o"] * k)
    )
    field = iteration.stage_field(None, "cand", ["o"], [], {}, 10, {})
    assert calls == ["census"] and len(field) == 10
    field = iteration.stage_field(None, "cand", ["o"], [], {}, 6, {})
    assert calls == ["census", "strata"] and len(field) == 6


def test_budget_is_the_champion_schedule():
    from iteration import BUDGET

    assert BUDGET == "duels=7,ffa=10+6,turns=1000,score=mu,sel=place43,ord=10-6-2"


def test_previous_budget_rows_are_ignored(tmp_path):
    import json

    import iteration

    p = tmp_path / "PROGRESS.jsonl"
    p.write_text(
        json.dumps(
            {
                "bot": "old-1",
                "mu": 60.0,
                "sigma": 1.0,
                "score": 60.0,
                "games": 8,
                "champion": None,
                "date": "2026-01-01",
                "budget": "duels=5,ffa=3,turns=1000,score=mu,sel=census-strata",
            }
        )
        + "\n"
    )
    row, prior, appended = iteration.record_report("new-2", 30.0, 5.0, 30.0, 8, path=p)
    assert appended and prior is None


def test_recency_order_uses_commit_order_oldest_first():
    from iteration import recency_order

    cands = ["b-ccc", "a-aaa", "c-bbb"]
    assert recency_order(cands, ["aaa", "bbb", "ccc"]) == [
        "a-aaa",
        "c-bbb",
        "b-ccc",
    ]


def test_recency_order_puts_unknown_shas_last():
    from iteration import recency_order

    assert recency_order(["new-zzz", "old-aaa"], ["aaa"]) == ["old-aaa", "new-zzz"]


def test_main_plays_census_then_refine_then_duels(tmp_path, monkeypatch):
    import iteration

    monkeypatch.setattr(iteration, "DUELS", 2)
    monkeypatch.setattr(iteration, "FFA_SIZES", [10, 6])
    monkeypatch.setattr(iteration, "GAMES_LOG", tmp_path / "games.jsonl")
    monkeypatch.setattr(iteration, "RATINGS_PATH", tmp_path / "ratings.json")
    monkeypatch.setattr(iteration, "PROGRESS", tmp_path / "PROGRESS.jsonl")
    monkeypatch.setattr(iteration, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(iteration, "WORKBASE", tmp_path / "work")
    monkeypatch.setattr(iteration, "is_clean", lambda root: True)
    monkeypatch.setattr(iteration, "engine_on_main", lambda root: True)
    monkeypatch.setattr(iteration, "main_merged", lambda root: True)
    bid = iteration.candidate_id(iteration.ROOT, iteration.DEFAULT_BOT)
    rivals = [f"rival{i}-abc1234" for i in range(12)]
    monkeypatch.setattr(
        iteration, "pool_ids", lambda root, ratings=None: [bid] + rivals
    )
    sizes = []

    def fake_play_one(root, field, map_rel, log_dir, rng, workbase):
        sizes.append(len(field))
        return {
            "v": 1,
            "map": map_rel,
            "turns": 1000,
            "turntime": 1000,
            "loadtime": 3000,
            "engine": "test",
            "pseed": 1,
            "eseed": 2,
            "field": list(field),
            "result": list(field),
            "length": 10,
        }

    monkeypatch.setattr(iteration, "play_one", fake_play_one)
    assert iteration.main([]) == 0
    assert sizes == [10, 6, 2, 2]


def _legacy_census_opponents(bid, cands, ratings, k, arrival):
    """Exact pre-newcomer-slot census (commit dc44516): quantile-decile
    sites snapped to the nearest ruler. Differential reference only."""
    import ratings as R

    others = [c for c in cands if c != bid]
    mus = sorted(R.for_id(ratings, c)["mu"] for c in others)
    k = max(0, min(k, len(others)))
    sites = (
        [mus[min(int(len(mus) * (j + 1) / (k + 1)), len(mus) - 1)] for j in range(k)]
        if mus and k
        else []
    )
    picked = []
    used = {bid}
    for t in sites:
        live = [c for c in others if c not in used]
        if not live:
            break
        i = min(
            live,
            key=lambda c: (
                abs(R.for_id(ratings, c)["mu"] - t),
                R.for_id(ratings, c)["sigma"],
                arrival.get(c, len(arrival)),
                c,
            ),
        )
        used.add(i)
        picked.append(i)
    return picked


def test_census_newcomer_slot_selects_zero_game_bot():
    from iteration import census_opponents

    ratings = {"cand": _rated(50, 8.0, 0)}
    cands = []
    for i, mu in enumerate([0, 10, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100]):
        ratings[f"r{i}"] = _rated(mu, 1.0)
        cands.append(f"r{i}")
    ratings["newbie"] = {"mu": 25.0, "sigma": 8.33, "games": 0}
    cands.append("newbie")
    arrival = {c: i for i, c in enumerate(cands)}
    opps = census_opponents("cand", cands, ratings, 9, arrival)
    assert len(opps) == 9
    assert "newbie" in opps


def test_census_without_newcomers_matches_legacy_selection():
    import ratings as R
    from iteration import census_opponents, recency_order
    from matchmake import read_log
    from pool import all_commits
    from pool import pool as pool_ids

    live = R.rebuild(read_log(ROOT / "league" / "games.jsonl"))
    pool = pool_ids(str(ROOT), live)
    assert len(pool) > 100
    # No newcomers present: everyone rated, so the slot falls back.
    ratings = {
        c: {
            "mu": R.for_id(live, c)["mu"],
            "sigma": min(R.for_id(live, c)["sigma"], 1.0),
            "games": max(R.for_id(live, c)["games"], 5),
        }
        for c in pool
    }
    ordered = recency_order(pool, all_commits(str(ROOT)))
    arrival = {c: i for i, c in enumerate(ordered)}
    for bid in (ordered[0], ordered[len(ordered) // 2], ordered[-1]):
        assert census_opponents(
            bid, pool, ratings, 9, arrival
        ) == _legacy_census_opponents(bid, pool, ratings, 9, arrival)


def test_census_veteran_with_three_games_is_not_newcomer_eligible():
    from iteration import census_opponents

    ratings = {"cand": _rated(50, 8.0, 0)}
    cands = []
    for i, mu in enumerate([0, 10, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100]):
        ratings[f"r{i}"] = _rated(mu, 1.0)
        cands.append(f"r{i}")
    ratings["vet"] = {"mu": 25.0, "sigma": 7.0, "games": 3}
    cands.append("vet")
    arrival = {c: i for i, c in enumerate(cands)}
    opps = census_opponents("cand", cands, ratings, 9, arrival)
    assert "vet" not in opps
    assert opps == _legacy_census_opponents("cand", cands, ratings, 9, arrival)
