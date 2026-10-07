"""Tests for autoresearch/candidates.py: ranked coder starts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import candidates as C


def _nodes(*rows):
    """rows: (sha, parents, subject), oldest first like reading history."""
    return [(s, list(p), subj) for s, p, subj in reversed(rows)]


def _exams(*rows):
    return list(rows)


NODES = _nodes(
    ("a000000", [], "init"),
    ("b111111", ["a000000"], "exp: tables one"),
    ("c222222", ["a000000"], "exp: crowd"),
)


def test_champion_is_first_start():
    exams = _exams(
        ("autoresearch/bot/Tables.bot-b111111", 30.0),
        ("autoresearch/bot/Crowd.bot-c222222", 67.0),
    )
    out = C.candidates(NODES, exams, set(), "c222222", [], {})
    assert out["starts"][0][0] == "c222222"
    assert out["dead"] == []


def test_champ_beater_outranks_cover():
    exams = _exams(
        ("autoresearch/bot/Tables.bot-b111111", 30.0),
        ("autoresearch/bot/Tables2.bot-d333333", 20.0),
        ("autoresearch/bot/Crowd.bot-c222222", 67.0),
        ("autoresearch/bot/Strong.bot-9999999", 60.0),
        ("autoresearch/bot/Weak.bot-1111111", 10.0),
    )
    nodes = NODES + [("d333333", ["a000000"], "exp: tables two")]
    games = [
        ["x/Tables.bot-b111111", "y/Strong.bot-9999999"],
        ["x/Tables2.bot-d333333", "y/Crowd.bot-c222222"],
    ]
    out = C.candidates(nodes, exams, set(), "c222222", games, {})
    names = [n for _, n in out["starts"]]
    assert names[0] == "Crowd.bot"
    assert names[1] == "Tables2.bot", names


def test_cover_counts_breadth_not_volume():
    exams = _exams(
        ("autoresearch/bot/Tables.bot-b111111", 30.0),
        ("autoresearch/bot/Tables2.bot-d333333", 20.0),
        ("autoresearch/bot/Weak.bot-1111111", 10.0),
        ("autoresearch/bot/Mid.bot-2222222", 25.0),
    )
    nodes = NODES + [("d333333", ["a000000"], "exp: tables two")]
    games = [
        ["x/Tables.bot-b111111", "y/Weak.bot-1111111"],
        ["x/Tables.bot-b111111", "y/Weak.bot-1111111"],
        ["x/Tables.bot-b111111", "y/Weak.bot-1111111"],
        ["x/Tables2.bot-d333333", "y/Weak.bot-1111111"],
        ["x/Tables2.bot-d333333", "y/Mid.bot-2222222"],
    ]
    mu_of = {"Weak.bot": 10.0, "Mid.bot": 25.0}
    out = C.candidates(nodes, exams, set(), None, games, mu_of)
    names = [n for _, n in out["starts"]]
    assert names[0] == "Tables2.bot", names


def test_dead_lines_get_no_starts():
    exams = _exams(
        ("autoresearch/bot/Tables.bot-b111111", 55.0),
        ("autoresearch/bot/Tables2.bot-b111111", 17.0),
        ("autoresearch/bot/Tables3.bot-b111111", 15.0),
        ("autoresearch/bot/Tables4.bot-b111111", 23.0),
    )
    out = C.candidates(NODES, exams, set(), None, [], {})
    assert out["dead"] == ["tables"]
    assert out["starts"] == []


def test_flight_removes_start():
    exams = _exams(
        ("autoresearch/bot/Tables.bot-b111111", 30.0),
        ("autoresearch/bot/Tables2.bot-d333333", 20.0),
    )
    nodes = NODES + [("d333333", ["a000000"], "exp: tables two")]
    out = C.candidates(nodes, exams, {"d333333"}, None, [], {})
    assert [s for s, _ in out["starts"]] == ["b111111"]


def test_unscored_lists_oldest_first():
    nodes = _nodes(
        ("a000000", [], "init"),
        ("b111111", ["a000000"], "exp: tables one"),
        ("c222222", ["a000000", "b111111"], "merge tree/tables-1: one"),
        ("d333333", ["c222222"], "exp: tables two"),
        ("e444444", ["c222222", "d333333"], "merge tree/tables-2: two"),
    )
    exams = _exams(
        ("autoresearch/bot/Tables2.bot-d333333", 20.0),
    )
    out = C.candidates(nodes, exams, set(), None, [], {})
    assert out["unscored"] == [("b111111", "tables one")]
