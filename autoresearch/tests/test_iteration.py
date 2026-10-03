"""Autoresearch iteration: budget counting, selection, scoring."""

import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "autoresearch"))
sys.path.insert(0, str(ROOT / "league"))


def test_counts_ten_player_games():
    from iteration import counts

    recs = [
        {"field": ["a", "b"]},
        {"field": ["a", "b", "c", "d"]},
        {"field": ["a", "x", "y", "z", "w", "v", "u", "t", "s", "r"]},
    ]
    assert counts(recs, "a") == {"games": 1}


def test_planned_leaves_the_right_budget():
    from iteration import planned

    recs = [{"field": ["a"] + ["x"] * 9}]
    assert planned(recs, "a", 3) == 2


def test_planned_never_negative():
    from iteration import planned

    recs = [{"field": ["a"] + ["x", "y", "z"] * 3} for _ in range(5)]
    assert planned(recs, "a", 3) == 0


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


def test_budget_is_three_ten_player_games():
    from iteration import BUDGET, GAME_SIZE, GAMES

    assert (GAMES, GAME_SIZE) == (3, 10)
    assert "3x10p" in BUDGET and "score=mu" in BUDGET


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


def test_iteration_summary_reports_ten_p_ranks():
    from iteration import iteration_summary

    ten = ["c", "a", "b", "d", "e", "f", "g", "h", "i", "j"]
    recs = [
        {"field": ten, "result": ten},
        {"field": ten, "result": list(reversed(ten))},
    ]
    assert iteration_summary(recs, "c") == "games: 2, ranks 10p:1 10p:10"


def test_progress_roundtrip_and_champion(tmp_path):
    from iteration import read_progress, record_report

    p = tmp_path / "PROGRESS.jsonl"
    row, prior, appended = record_report("a-1", 30.0, 3.0, 30.0, 3, path=p)
    assert appended and prior is None and row["score"] == 30.0
    row, prior, appended = record_report("b-2", 35.0, 4.0, 35.0, 3, path=p)
    assert appended and prior is not None
    assert prior["bot"] == "a-1"
    row, prior, appended = record_report("b-2", 1.0, 1.0, 1.0, 3, path=p)
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

    monkeypatch.setattr(iteration, "GAMES", 3)
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
    rivals = [f"rival{i}" for i in range(9)]
    monkeypatch.setattr(
        iteration, "pool_ids", lambda root, ratings=None: [bid] + rivals
    )
    monkeypatch.setattr(
        iteration,
        "maps_for_players",
        lambda root, n: [f"map{i}.map" for i in range(5)],
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
    assert len((tmp_path / "games.jsonl").read_text().splitlines()) == 3
    rows = iteration.read_progress(tmp_path / "PROGRESS.jsonl")
    assert len(rows) == 1 and rows[0]["bot"] == bid
    assert rows[0]["games"] == 3
    assert iteration.main([]) == 0
    assert len((tmp_path / "games.jsonl").read_text().splitlines()) == 3
    assert len(iteration.read_progress(tmp_path / "PROGRESS.jsonl")) == 1


def _ratings(entries):
    return {bid: {"mu": mu, "sigma": sig, "games": g} for bid, mu, sig, g in entries}


def test_recent_window_orders_by_first_appearance():
    from iteration import recent_window

    ratings = _ratings(
        [("old", 20.0, 2.0, 30), ("mid", 25.0, 3.0, 10), ("new", 30.0, 5.0, 2)]
    )
    cands = ["new", "old", "mid", "unseen"]
    assert recent_window(cands, ratings, window=400) == ["old", "mid", "new", "unseen"]


def test_recent_window_caps_at_window_size():
    from iteration import recent_window

    ratings = _ratings([(f"b{i}", 25.0, 3.0, 1) for i in range(6)])
    cands = [f"b{i}" for i in range(6)]
    assert recent_window(cands, ratings, window=4) == ["b2", "b3", "b4", "b5"]


def test_tertile_anchors_returns_lowest_sigma_third():
    from iteration import tertile_anchors

    ratings = _ratings(
        [
            ("a", 10.0, 1.0, 20),
            ("b", 20.0, 2.0, 20),
            ("c", 30.0, 3.0, 20),
            ("d", 40.0, 4.0, 20),
            ("e", 50.0, 5.0, 20),
            ("f", 60.0, 6.0, 20),
        ]
    )
    assert tertile_anchors(["a", "b", "c", "d", "e", "f"], ratings) == ["a", "b"]


def test_tertile_anchors_never_empty():
    from iteration import tertile_anchors

    ratings = _ratings([("solo", 25.0, 8.0, 1)])
    assert tertile_anchors(["solo"], ratings) == ["solo"]
    assert tertile_anchors([], ratings) == []


def test_census_opponents_span_the_range():
    from iteration import census_opponents

    ratings = _ratings(
        [
            ("bid", 25.0, 8.0, 0),
            ("lo", 0.0, 2.0, 20),
            ("midlo", 15.0, 2.0, 20),
            ("mid", 30.0, 2.0, 20),
            ("midhi", 45.0, 2.0, 20),
            ("hi", 60.0, 2.0, 20),
        ]
    )
    opps = census_opponents("bid", ["lo", "midlo", "mid", "midhi", "hi"], ratings, 9)
    assert len(opps) == 5 and len(set(opps)) == 5 and "bid" not in opps
    mus = sorted(ratings[o]["mu"] for o in opps)
    assert mus[0] <= 15.0 and mus[-1] >= 45.0


def test_spread_field_starts_with_candidate_and_prefers_anchors():
    from iteration import spread_field

    ratings = _ratings(
        [
            ("bid", 25.0, 8.0, 0),
            ("calm", 25.0, 1.0, 20),
            ("wild", 25.0, 8.0, 1),
        ]
    )
    field = spread_field("bid", ["calm", "wild"], ratings, 3, 1.25)
    assert field == ["bid", "calm", "wild"]
