"""Ratings: OpenSkill BradleyTerryFull over FFA placements. Pure functions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "league"))

import ratings as R


def test_prior_for_unseen_bot():
    m = R.new_model()
    r = R.for_id({}, "bots/x-abc1234", m)
    assert r["mu"] == m.mu and r["sigma"] == m.sigma and r["games"] == 0


def test_winner_up_loser_down_2p():
    m = R.new_model()
    before = {"a": R.prior_dict(m), "b": R.prior_dict(m)}
    after = R.update(before, field=["a", "b"], result=["a", "b"])
    assert after["a"]["mu"] > before["a"]["mu"]
    assert after["b"]["mu"] < before["b"]["mu"]
    assert after["a"]["games"] == 1 and after["b"]["games"] == 1


def test_loser_first_rank_mapping():
    # field slot order must not leak into outcome: slot 1 wins here
    m = R.new_model()
    before = {"a": R.prior_dict(m), "b": R.prior_dict(m)}
    after = R.update(before, field=["a", "b"], result=["b", "a"])
    assert after["b"]["mu"] > after["a"]["mu"]


def test_8p_first_beats_last():
    m = R.new_model()
    field = [f"bot{i}" for i in range(8)]
    result = list(reversed(field))
    after = R.update({}, field=field, result=result)
    assert after["bot7"]["mu"] > after["bot0"]["mu"]
    assert all(after[b]["games"] == 1 for b in field)


def test_tie_shares_rank():
    m = R.new_model()
    straight = R.update({}, field=["a", "b", "c"], result=["a", "b", "c"])
    tied = R.update({}, field=["a", "b", "c"], result=["a", "b", "c"],
                    ranks={"a": 1, "b": 1, "c": 3})
    assert tied["b"]["mu"] > straight["b"]["mu"]


def test_save_load_roundtrip(tmp_path):
    m = R.new_model()
    before = R.update({}, field=["a", "b"], result=["a", "b"])
    p = tmp_path / "ratings.json"
    R.save(p, before)
    assert R.load(p) == before


def test_load_missing_is_empty(tmp_path):
    assert R.load(tmp_path / "nope.json") == {}


def test_rebuild_equals_incremental():
    games = [
        {"field": ["a", "b"], "result": ["a", "b"]},
        {"field": ["a", "b", "c"], "result": ["c", "a", "b"]},
    ]
    inc = {}
    for g in games:
        inc = R.update(inc, field=g["field"], result=g["result"])
    assert R.rebuild(games) == inc
