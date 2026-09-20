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


def test_score_is_mu_minus_three_sigma():
    from iteration import score

    ratings = {"x": {"mu": 30.0, "sigma": 4.0, "games": 10}}
    assert score(ratings, "x") == (30.0, 4.0, 18.0)


def test_unseen_bot_scores_at_the_prior():
    from iteration import score

    mu, sigma, lb = score({}, "fresh")
    assert sigma == 25 / 3 and abs(lb - (25 - 25)) < 1e-9


def test_candidate_id_is_path_plus_sha():
    from iteration import ROOT as AROOT
    from iteration import candidate_id

    bid = candidate_id(AROOT, "autoresearch/bot/main.bot")
    assert bid.startswith("autoresearch/bot/main.bot-")


def test_short_name_labels_main_manifests_by_dir():
    from iteration import short_name

    assert short_name("autoresearch/bot/main.bot-abc1234") == "autoresearch/bot"
    assert short_name("tools/sample_bots/python/GreedyBot.bot-abc1234") == "GreedyBot"


def test_progress_roundtrip_and_champion(tmp_path):
    from iteration import read_progress, record_report

    p = tmp_path / "PROGRESS.jsonl"
    row, prior, appended = record_report("a-1", 30.0, 3.0, 21.0, 23, path=p)
    assert appended and prior is None and row["lb"] == 21.0
    row, prior, appended = record_report("b-2", 35.0, 4.0, 23.0, 23, path=p)
    assert appended and prior is not None
    assert prior["bot"] == "a-1"
    row, prior, appended = record_report("b-2", 1.0, 1.0, -2.0, 23, path=p)
    assert not appended and row["lb"] == 23.0 and prior is not None
    assert prior["bot"] == "b-2"
    rows = read_progress(p)
    assert [r["bot"] for r in rows] == ["a-1", "b-2"]


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
            "games": 23,
            "champion": None,
            "date": "2026-01-01",
        }
    )
    p.write_text(good + '\nnot json\n{"bot": "bad"}\n')
    rows = read_progress(p)
    assert [r["bot"] for r in rows] == ["good"]


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


def test_main_plays_records_and_never_replays(tmp_path, monkeypatch):
    import iteration

    monkeypatch.setattr(iteration, "DUELS", 1)
    monkeypatch.setattr(iteration, "FFA_SIZES", [])
    monkeypatch.setattr(iteration, "GAMES_LOG", tmp_path / "games.jsonl")
    monkeypatch.setattr(iteration, "RATINGS_PATH", tmp_path / "ratings.json")
    monkeypatch.setattr(iteration, "PROGRESS", tmp_path / "PROGRESS.jsonl")
    monkeypatch.setattr(iteration, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(iteration, "WORKBASE", tmp_path / "work")
    # The guards have their own tests; keep this test independent of
    # the working tree.
    monkeypatch.setattr(iteration, "is_clean", lambda root: True)
    monkeypatch.setattr(iteration, "engine_on_main", lambda root: True)
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
