"""Engine wrapper: run a match, parse the replay, rank slots."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "league"))

REPLAY = Path(__file__).with_name("replay_fixture.json")


def test_bind_maps_python_to_absolute_interpreter():
    from play import bind
    assert bind("python A.py --x 1", "/abs/py") == "/abs/py A.py --x 1"
    assert bind("python3 A.py", "/abs/py") == "/abs/py A.py"


def test_bind_leaves_other_runtimes_verbatim():
    from play import bind
    assert bind("php Bot.php", "/abs/py") == "php Bot.php"


def test_parse_replay_without_score_is_loud(tmp_path):
    import pytest
    from play import EngineError, parse_replay
    p = tmp_path / "0.replay"
    p.write_text('{"playernames": [null], "error": "boom"}')
    with pytest.raises(EngineError):
        parse_replay(p)


def test_parse_replay_scores_and_status():
    from play import parse_replay
    scores, statuses = parse_replay(REPLAY)
    assert scores == [4, 2, 2, 1]
    assert statuses == ["survived", "survived", "eliminated", "crashed"]


def test_rank_slots_score_then_status():
    from play import rank_slots
    assert rank_slots([4, 2, 2, 1],
                      ["survived", "survived", "eliminated", "crashed"]) == [0, 1, 2, 3]


def test_rank_slots_tiebreaks_status():
    from play import rank_slots
    # equal score: survivor beats eliminated
    assert rank_slots([2, 2], ["eliminated", "survived"]) == [1, 0]


def test_rank_slots_stable_ties_share_order():
    from play import rank_slots
    assert rank_slots([1, 1], ["survived", "survived"]) == [0, 1]


def test_tiny_real_game_produces_record(tmp_path):
    import sys as _sys
    from play import play_match, ROOT
    rec = play_match(ROOT, _sys.executable,
                     field=["bots/py3_starter/main.bot-HEAD",
                            "bots/pas11/main.bot-HEAD"],
                     map_rel="tools/maps/example/tutorial1.map",
                     turns=2, turntime=200, loadtime=500,
                     pseed=1, eseed=2, log_dir=tmp_path)
    assert rec["map"] == "tools/maps/example/tutorial1.map"
    assert rec["turns"] == 2 and rec["pseed"] == 1 and rec["eseed"] == 2
    assert sorted(rec["field"]) == sorted(rec["result"])
    assert len(rec["result"]) == 2
    assert all(isinstance(b, str) and "-" in b for b in rec["field"])
