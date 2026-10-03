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
        {"field": ["a", "b", "c"]},
        {"field": ["a", "b", "c"]},
        {"field": ["a", "b", "c", "d", "e"]},
        {"field": ["x", "y"]},
    ]
    assert counts(recs, "a") == {"duels": 1, "ffa": {3: 2, 5: 1}}


def test_planned_leaves_the_right_budget():
    from iteration import planned

    recs = [{"field": ["a", "b"]}, {"field": ["a", "b", "c"]}]
    duels_left, sizes = planned(recs, "a", 3, [3, 4])
    assert duels_left == 2 and sizes == [4]


def test_planned_never_negative():
    from iteration import planned

    recs = [{"field": ["a", "b"]} for _ in range(5)]
    duels_left, sizes = planned(recs, "a", 3, [4])
    assert duels_left == 0 and sizes == [4]


def test_duel_opponent_picks_nearest_skill():
    from iteration import duel_opponent
    from matchmake import new_model

    ratings = {
        "cand": {"mu": 25, "sigma": 8.33, "games": 0},
        "near": {"mu": 25, "sigma": 8.0, "games": 0},
        "far": {"mu": 60, "sigma": 2.0, "games": 20},
    }
    opp = duel_opponent(
        new_model(),
        "cand",
        ["near", "far"],
        ratings,
        random.Random(0),
        eps=0.0,
        breadth=3,
    )
    assert opp == "near"


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


def test_ffa_sizes_for_is_stable_and_from_the_sets():
    from iteration import ffa_sizes_for

    bid = "autoresearch/bot/main.bot-abc1234"
    sizes = ffa_sizes_for(bid)
    assert sizes == ffa_sizes_for(bid)
    assert sizes in ([4, 6, 10], [5, 7, 8])


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
    monkeypatch.setattr(iteration, "ffa_sizes_for", lambda bid: [])
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
    monkeypatch.setattr(
        iteration, "pool_ids", lambda root, ratings=None: [bid, "rival"]
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
    assert len((tmp_path / "games.jsonl").read_text().splitlines()) == 1
    rows = iteration.read_progress(tmp_path / "PROGRESS.jsonl")
    assert len(rows) == 1 and rows[0]["bot"] == bid
    assert iteration.main([]) == 0
    assert len((tmp_path / "games.jsonl").read_text().splitlines()) == 1
    assert len(iteration.read_progress(tmp_path / "PROGRESS.jsonl")) == 1


def _rated(mu, sigma, games=20):
    return {"mu": mu, "sigma": sigma, "games": games}


def test_census_field_spans_full_pool_mass():
    from iteration import census_field

    ratings = {"cand": _rated(50, 8.0, 0)}
    for i, mu in enumerate([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]):
        ratings[f"r{i}"] = _rated(mu, 2.0)
    cands = [k for k in ratings if k != "cand"]
    field = census_field("cand", cands, ratings, 6)
    assert len(field) == 6 and field[0] == "cand"
    mus = sorted(ratings[c]["mu"] for c in field[1:])
    assert mus[0] <= 10 and mus[-1] >= 90


def test_census_quality_snap_prefers_low_sigma():
    from iteration import census_field

    ratings = {
        "cand": _rated(50, 8.0, 0),
        "noisy": _rated(10.0, 6.0),
        "solid": _rated(10.1, 1.0),
        "top": _rated(90.0, 1.0),
    }
    cands = ["noisy", "solid", "top"]
    field = census_field("cand", cands, ratings, 3)
    assert "solid" in field and "noisy" not in field


def test_strata_field_covers_all_three_bins_from_calibrated_rulers():
    from iteration import strata_field

    ratings = {"cand": _rated(50, 8.0, 0)}
    pool = []
    for i in range(60):
        ratings[f"cal{i}"] = _rated(i * 1.5, 1.0)
        pool.append(f"cal{i}")
    for i in range(30):
        ratings[f"raw{i}"] = _rated(i * 3.0, 7.0)
        pool.append(f"raw{i}")
    field = strata_field("cand", pool, ratings, 7)
    assert len(field) == 7 and field[0] == "cand"
    sigmas = [r["sigma"] for r in ratings.values() if r["games"] > 0]
    cutoff = sorted(sigmas)[len(sigmas) // 3]
    assert all(ratings[c]["sigma"] <= cutoff for c in field[1:])
    mus = [ratings[c]["mu"] for c in field[1:]]
    assert any(m < 42 for m in mus) and any(m > 58 for m in mus)


def test_strata_quota_follows_bin_mass():
    from iteration import strata_field

    ratings = {"cand": _rated(50, 8.0, 0)}
    pool = []
    for i in range(40):
        ratings[f"peer{i}"] = _rated(48.0 + i * 0.1, 1.0)
        pool.append(f"peer{i}")
    for name, mu in (("lo", 10.0), ("hi", 90.0)):
        ratings[name] = _rated(mu, 1.0)
        pool.append(name)
    field = strata_field("cand", pool, ratings, 6)
    peer = [c for c in field[1:] if 42 <= ratings[c]["mu"] <= 58]
    assert len(peer) >= 3


def test_ffa_field_uses_census_then_strata_then_propose(monkeypatch):
    import iteration

    calls = []

    def rec(name, val):
        calls.append(name)
        return val

    monkeypatch.setattr(
        iteration, "census_field", lambda bid, c, r, n: rec("census", [bid])
    )
    monkeypatch.setattr(
        iteration, "strata_field", lambda bid, c, r, n: rec("strata", [bid])
    )
    monkeypatch.setattr(iteration, "propose", lambda *a, **k: rec("propose", ["x"]))
    ratings = {"cand": _rated(50, 8.0, 0)}
    iteration.ffa_field(None, "cand", [], ratings, 4, 0, None)
    iteration.ffa_field(None, "cand", [], ratings, 4, 1, None)
    iteration.ffa_field(None, "cand", [], ratings, 4, 2, None)
    assert calls == ["census", "strata", "propose"]


def test_budget_selects_census_strata_and_scores_mu():
    from iteration import BUDGET

    assert "score=mu" in BUDGET
    assert "sel=census-strata" in BUDGET


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
                "budget": "duels=5,ffa=3,turns=1000,score=mu",
            }
        )
        + "\n"
    )
    row, prior, appended = iteration.record_report("new-2", 30.0, 5.0, 30.0, 8, path=p)
    assert appended and prior is None
