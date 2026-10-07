"""Tests for autoresearch/candidates.py: valid coder starts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import candidates as C


def _nodes(*rows):
    """rows: (sha, parents, subject), oldest first like reading history."""
    return [(s, list(p), subj) for s, p, subj in reversed(rows)]


NODES = _nodes(
    ("a000000", [], "init"),
    ("b111111", ["a000000"], "exp: tables one"),
    ("c222222", ["a000000", "b111111"], "merge tree/tables-1: one"),
    ("d333333", ["c222222"], "exp: tables two"),
    ("e444444", ["c222222", "d333333"], "merge tree/tables-2: two"),
    ("f555555", ["e444444"], "exp: tables three"),
    ("g666666", ["e444444", "f555555"], "merge tree/tables-3: three"),
)


def _exams(*rows):
    return list(rows)


def test_trend_dead_line_gets_nothing():
    exams = _exams(
        ("autoresearch/bot/Tables.bot-b111111", 55.0),
        ("autoresearch/bot/Tables2.bot-d333333", 17.0),
        ("autoresearch/bot/Tables3.bot-f555555", 15.0),
        ("autoresearch/bot/Tables4.bot-f555555", 23.0),
    )
    out = C.candidates(NODES, exams, set(), None, {"tables"}, [])
    assert out["dead"] == ["tables"]
    assert out["extend"] is None
    assert out["split"] == []
    assert out["idle"] is None


def test_live_line_extends_newest_scored_tip():
    exams = _exams(
        ("autoresearch/bot/Tables.bot-b111111", 17.0),
        ("autoresearch/bot/Tables2.bot-d333333", 55.0),
    )
    out = C.candidates(NODES, exams, set(), None, {"tables"}, [])
    assert out["dead"] == []
    assert out["extend"] == ("d333333", "tables")


def test_flight_blocks_extend_but_allows_split_parent():
    exams = _exams(
        ("autoresearch/bot/Tables.bot-b111111", 17.0),
        ("autoresearch/bot/Tables2.bot-d333333", 55.0),
    )
    out = C.candidates(NODES, exams, {"d333333"}, None, {"tables"}, [])
    assert out["extend"] is None
    assert ("b111111", "tables", "a000000") in out["split"]


def test_champion_line_never_dies_and_extends():
    exams = _exams(
        ("autoresearch/bot/Tables.bot-b111111", 55.0),
        ("autoresearch/bot/Tables2.bot-d333333", 17.0),
        ("autoresearch/bot/Tables3.bot-f555555", 15.0),
        ("autoresearch/bot/Tables4.bot-f555555", 23.0),
        ("autoresearch/bot/Crowd.bot-a9d4173", 67.0),
    )
    nodes = NODES + [("a9d4173", ["g666666"], "exp: crowd")]
    out = C.candidates(nodes, exams, set(), "a9d4173", {"tables"}, [])
    assert "champion" not in out["dead"]
    assert out["extend"] == ("a9d4173", "champion")


def test_idle_takes_oldest_unscored_leaf():
    nodes = _nodes(
        ("a000000", [], "init"),
        ("b111111", ["a000000"], "exp: tables one"),
        ("c222222", ["a000000", "b111111"], "merge tree/tables-1: one"),
        ("d333333", ["c222222"], "exp: tables two"),
        ("e444444", ["c222222", "d333333"], "merge tree/tables-2: two"),
    )
    exams = _exams(("autoresearch/bot/Tables2.bot-d333333", 55.0))
    out = C.candidates(nodes, exams, set(), None, {"tables"}, [])
    assert out["idle"] == ("b111111", "tables")


def test_short_line_is_immune():
    exams = _exams(
        ("autoresearch/bot/Tables.bot-b111111", 55.0),
        ("autoresearch/bot/Tables2.bot-d333333", 10.0),
    )
    out = C.candidates(NODES, exams, set(), None, {"tables"}, [])
    assert out["dead"] == []


def test_split_prefers_champ_beater():
    nodes = _nodes(
        ("a000000", [], "init"),
        ("b111111", ["a000000"], "exp: tables one"),
        ("c222222", ["a000000", "b111111"], "merge tree/tables-1: one"),
        ("d333333", ["c222222"], "exp: tables two"),
        ("e444444", ["c222222", "d333333"], "merge tree/tables-2: two"),
        ("f555555", ["e444444"], "exp: tables three"),
        ("g666666", ["e444444", "f555555"], "merge tree/tables-3: three"),
        ("a9d4173", ["g666666"], "exp: crowd"),
    )
    exams = _exams(
        ("autoresearch/bot/Tables.bot-b111111", 30.0),
        ("autoresearch/bot/Tables2.bot-d333333", 20.0),
        ("autoresearch/bot/Tables3.bot-f555555", 50.0),
        ("autoresearch/bot/Crowd.bot-a9d4173", 67.0),
    )
    games = [
        ["x/Tables2.bot-d333333", "y/Crowd.bot-a9d4173"],
    ]
    out = C.candidates(nodes, exams, set(), "a9d4173", {"tables"}, games)
    assert out["split"][0][0] == "d333333", out["split"]


def test_split_cover_breaks_tie():
    nodes = _nodes(
        ("a000000", [], "init"),
        ("b111111", ["a000000"], "exp: tables one"),
        ("c222222", ["a000000", "b111111"], "merge tree/tables-1: one"),
        ("d333333", ["c222222"], "exp: tables two"),
        ("e444444", ["c222222", "d333333"], "merge tree/tables-2: two"),
        ("f555555", ["e444444"], "exp: tables three"),
        ("g666666", ["e444444", "f555555"], "merge tree/tables-3: three"),
    )
    exams = _exams(
        ("autoresearch/bot/Tables.bot-b111111", 30.0),
        ("autoresearch/bot/Tables2.bot-d333333", 20.0),
        ("autoresearch/bot/Tables3.bot-f555555", 50.0),
        ("autoresearch/bot/Strong.bot-9999999", 60.0),
    )
    games = [
        ["x/Tables.bot-b111111", "y/Strong.bot-9999999"],
    ]
    out = C.candidates(nodes, exams, set(), None, {"tables"}, games)
    assert out["split"][0][0] == "b111111", out["split"]


def test_split_without_games_keeps_line_order():
    exams = _exams(
        ("autoresearch/bot/Tables.bot-b111111", 30.0),
        ("autoresearch/bot/Tables2.bot-d333333", 20.0),
        ("autoresearch/bot/Tables3.bot-f555555", 50.0),
    )
    out = C.candidates(NODES, exams, set(), None, {"tables"}, [])
    assert [s for s, _, _ in out["split"]] == ["b111111", "d333333"]


def test_split_cover_counts_breadth_not_volume():
    nodes = _nodes(
        ("a000000", [], "init"),
        ("b111111", ["a000000"], "exp: tables one"),
        ("c222222", ["a000000", "b111111"], "merge tree/tables-1: one"),
        ("d333333", ["c222222"], "exp: tables two"),
        ("e444444", ["c222222", "d333333"], "merge tree/tables-2: two"),
        ("f555555", ["e444444"], "exp: tables three"),
        ("g666666", ["e444444", "f555555"], "merge tree/tables-3: three"),
    )
    exams = _exams(
        ("autoresearch/bot/Tables.bot-b111111", 30.0),
        ("autoresearch/bot/Tables2.bot-d333333", 20.0),
        ("autoresearch/bot/Tables3.bot-f555555", 50.0),
        ("autoresearch/bot/Weak.bot-1111111", 10.0),
        ("autoresearch/bot/Mid.bot-2222222", 25.0),
    )
    games = [
        ["x/Tables.bot-b111111", "y/Weak.bot-1111111"],
        ["x/Tables.bot-b111111", "y/Weak.bot-1111111"],
        ["x/Tables.bot-b111111", "y/Weak.bot-1111111"],
        ["x/Tables2.bot-d333333", "y/Weak.bot-1111111"],
        ["x/Tables2.bot-d333333", "y/Mid.bot-2222222"],
    ]
    out = C.candidates(nodes, exams, set(), None, {"tables"}, games)
    assert out["split"][0][0] == "d333333", out["split"]
