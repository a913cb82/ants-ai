"""Autoresearch iteration: budget counting, selection, scoring."""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "autoresearch"))
sys.path.insert(0, str(ROOT / "league"))


def test_counts_splits_duels_and_ffa():
    from iteration import counts
    recs = [{"field": ["a", "b"]},
            {"field": ["a", "b", "c"]},
            {"field": ["a", "b", "c"]},
            {"field": ["a", "b", "c", "d", "e"]},
            {"field": ["x", "y"]}]
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
    ratings = {"cand": {"mu": 25, "sigma": 8.33, "games": 0},
               "near": {"mu": 25, "sigma": 8.0, "games": 0},
               "far": {"mu": 60, "sigma": 2.0, "games": 20}}
    opp = duel_opponent(new_model(), "cand", ["near", "far"], ratings,
                        random.Random(0), eps=0.0, breadth=3)
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
    from iteration import candidate_id, ROOT as AROOT
    bid = candidate_id(AROOT, "autoresearch/bot/main.bot")
    assert bid.startswith("autoresearch/bot/main.bot-")


def test_short_name_labels_main_manifests_by_dir():
    from iteration import short_name
    assert short_name("autoresearch/bot/main.bot-abc1234") == "autoresearch/bot"
    assert short_name("tools/sample_bots/python/GreedyBot.bot-abc1234") == \
        "GreedyBot"
