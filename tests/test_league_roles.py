"""League roles + admission log (phase 2 of ml/runs/plan-league.md).

Archive-side contracts for the continuous league: going-forward manifest
roles (main-snapshot/me/le/admitted), league.json scheduler state,
anchor.jsonl measurement rows, and pool game counts for the newcomer
<10-games boost. Sampling helpers live in ml/pfsp.py (untouched here).
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

import archive


@pytest.fixture
def base(tmp_path):
    b = tmp_path / "archive"
    archive.init(b)
    return b


# ------------------------------------------------------------------ roles


def test_role_constants():
    assert archive.ROLE_MAIN_SNAPSHOT == "main-snapshot"
    assert archive.ROLE_ME == "me"
    assert archive.ROLE_LE == "le"
    assert archive.ROLE_ADMITTED == "admitted"
    assert set(archive.LEAGUE_ROLES) == {"main-snapshot", "me", "le", "admitted"}


def test_save_league_snapshot_round_trips_manifest(base):
    a = archive.save_league_snapshot(base, {"w": [1.0]}, "main-snapshot", None)
    b = archive.save_league_snapshot(base, {"w": [2.0]}, "me", a)
    c = archive.save_league_snapshot(base, {"w": [3.0]}, "le", a)
    rows = {m["id"]: m for m in archive.members(base)}
    assert rows[a]["role"] == "main-snapshot" and rows[a]["parent"] is None
    assert rows[b] == {"id": b, "role": "me", "parent": a}
    assert rows[c] == {"id": c, "role": "le", "parent": a}
    assert archive.load_checkpoint(base, b) == {"w": [2.0]}


def test_save_league_snapshot_rejects_unknown_role(base):
    with pytest.raises(ValueError):
        archive.save_league_snapshot(base, {"w": [1.0]}, "challenger", None)
    assert archive.members(base) == []


# -------------------------------------------------------------- league.json


def test_init_league_schema(base):
    state = archive.init_league(base, "g005", ["g000", "g003"])
    assert state["main_id"] == "g005"
    assert state["anchors"] == ["g000", "g003"]
    assert state["admissions"] == []
    assert state["resets"] == []
    assert state["scheduler_pos"] == 0
    assert state["snapshot_counter"] == 0
    assert "micro_batch_progress" in state
    for name in ("me", "le-a", "le-b"):
        exp = state["exploiters"][name]
        assert exp["games"] == 0
        assert exp["window"] == []
        assert "target" in exp
    assert archive.load_league(base) == state


def test_league_round_trip_and_no_temp_files(base):
    archive.init_league(base, "g001", ["g000"])
    state = archive.load_league(base)
    state["scheduler_pos"] = 2
    state["snapshot_counter"] = 7
    archive.save_league(base, state)
    assert archive.load_league(base) == state
    leftovers = list(base.glob("*.tmp")) + list(base.glob("league.json.tmp*"))
    assert leftovers == []
    raw = json.loads((base / "league.json").read_text())
    assert raw == state


def test_load_league_missing_is_none(tmp_path):
    assert archive.load_league(tmp_path / "nope") is None


def test_record_admission_appends(base):
    archive.init_league(base, "g010", ["g000"])
    entry = archive.record_admission(base, "g011", "admitted", 240, "25-10-5")
    assert entry == {
        "id": "g011",
        "role": "admitted",
        "at_game": 240,
        "record": "25-10-5",
    }
    archive.record_admission(base, "g012", "me", 320, "24-8-8")
    state = archive.load_league(base)
    assert state["admissions"] == [
        {"id": "g011", "role": "admitted", "at_game": 240, "record": "25-10-5"},
        {"id": "g012", "role": "me", "at_game": 320, "record": "24-8-8"},
    ]


def test_note_reset_appends_identifiable_entry(base):
    archive.init_league(base, "g010", ["g000"])
    entry = archive.note_reset(base, "me", "me", 160)
    assert entry == {"slot": "me", "seat": "me", "tick": 160}
    state = archive.load_league(base)
    assert state["resets"] == [entry]


def test_record_admission_without_league_raises(base):
    with pytest.raises(FileNotFoundError):
        archive.record_admission(base, "g001", "admitted", 0, "0-0-0")


def test_advance_scheduler_cycles_and_persists(base):
    archive.init_league(base, "g001", ["g000"])
    order = ["main", "me", "le-a", "le-b"]
    seen = [archive.advance_scheduler(base, order) for _ in range(5)]
    assert seen == ["me", "le-a", "le-b", "main", "me"]
    assert archive.load_league(base)["scheduler_pos"] == 1
    assert archive.current_learner(archive.load_league(base), order) == "me"


def test_exploiter_window_caps_at_forty(base):
    archive.init_league(base, "g001", ["g000"])
    for i in range(45):
        archive.note_exploiter_game(base, "me", 1.0 if i % 2 else 0.0)
    exp = archive.load_league(base)["exploiters"]["me"]
    assert exp["games"] == 45
    assert len(exp["window"]) == 40
    assert exp["window"] == [1.0 if i % 2 else 0.0 for i in range(5, 45)]


# -------------------------------------------------------------- anchor.jsonl


def test_anchor_append_and_read(base):
    archive.record_anchor(base, "s1", "g010", "g000", 2, 0, 0)
    archive.record_anchor(base, "s1", "g010", "g003", 1, 1, 0)
    archive.record_anchor(base, "s2", "g011", "g000", 0, 2, 0)
    rows = archive.list_anchors(base)
    assert rows == [
        {
            "snapshot_id": "s1",
            "main_id": "g010",
            "anchor_id": "g000",
            "wins": 2,
            "losses": 0,
            "draws": 0,
        },
        {
            "snapshot_id": "s1",
            "main_id": "g010",
            "anchor_id": "g003",
            "wins": 1,
            "losses": 1,
            "draws": 0,
        },
        {
            "snapshot_id": "s2",
            "main_id": "g011",
            "anchor_id": "g000",
            "wins": 0,
            "losses": 2,
            "draws": 0,
        },
    ]
    assert len(archive.list_anchors(base, snapshot_id="s1")) == 2
    assert archive.list_anchors(base, snapshot_id="s2")[0]["anchor_id"] == "g000"


def test_anchor_reader_skips_malformed(base):
    archive.record_anchor(base, "s1", "g010", "g000", 2, 0, 0)
    with open(base / "anchor.jsonl", "a") as f:
        f.write("not json\n")
        f.write('{"snapshot_id": "s9"}\n')  # missing keys
    assert len(archive.list_anchors(base)) == 1


# ------------------------------------------------------------ game counts


def test_member_game_counts_from_matrix(base):
    a = archive.save_checkpoint(base, {}, role="main", parent=None)
    b = archive.save_checkpoint(base, {}, role="main", parent=None)
    c = archive.save_checkpoint(base, {}, role="main", parent=None)
    for _ in range(6):
        archive.record_result(base, a, b, 1.0, 0.0)
    for _ in range(4):
        archive.record_result(base, b, a, 0.5, 0.5)
    counts = archive.member_game_counts(base)
    assert counts[a] == 10
    assert counts[b] == 10
    assert counts[c] == 0  # unevaluated newcomer, no games yet
