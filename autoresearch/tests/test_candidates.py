"""Tests for autoresearch/candidates.py: ranked coder starts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import candidates as C


def test_champion_starts_first():
    exams = [
        ("autoresearch/bot/Tables.bot-b111111", 30.0),
        ("autoresearch/bot/Crowd.bot-c222222", 67.0),
    ]
    out = C.candidates(exams, [], {})
    assert out["starts"][0][0] == "autoresearch/bot/Crowd.bot-c222222"
    assert out["champion"] == "autoresearch/bot/Crowd.bot-c222222"
    assert out["dead"] == []


def test_champ_beater_outranks_cover():
    exams = [
        ("autoresearch/bot/Tables.bot-b111111", 30.0),
        ("autoresearch/bot/Tables2.bot-d333333", 20.0),
        ("autoresearch/bot/Crowd.bot-c222222", 67.0),
    ]
    games = [
        ["x/Tables.bot-b111111", "y/Strong.bot-9999999"],
        ["x/Tables2.bot-d333333", "y/Crowd.bot-c222222"],
    ]
    out = C.candidates(exams, games, {"Strong.bot": 60.0})
    names = [C._basename(b) for b, _ in out["starts"]]
    assert names[0] == "Crowd.bot"
    assert names[1] == "Tables2.bot", names


def test_cover_counts_breadth_not_volume():
    exams = [
        ("autoresearch/bot/Tables.bot-b111111", 30.0),
        ("autoresearch/bot/Tables2.bot-d333333", 20.0),
        ("autoresearch/bot/Crowd.bot-c222222", 67.0),
    ]
    games = [
        ["x/Tables.bot-b111111", "y/Weak.bot-1111111"],
        ["x/Tables.bot-b111111", "y/Weak.bot-1111111"],
        ["x/Tables.bot-b111111", "y/Weak.bot-1111111"],
        ["x/Tables2.bot-d333333", "y/Weak.bot-1111111"],
        ["x/Tables2.bot-d333333", "y/Mid.bot-2222222"],
    ]
    mu_of = {"Weak.bot": 10.0, "Mid.bot": 25.0}
    out = C.candidates(exams, games, mu_of)
    names = [C._basename(b) for b, _ in out["starts"]]
    assert names[1] == "Tables2.bot", names


def test_dead_lines_get_no_starts():
    exams = [
        ("autoresearch/bot/Tables.bot-b111111", 55.0),
        ("autoresearch/bot/Tables2.bot-b111111", 17.0),
        ("autoresearch/bot/Tables3.bot-b111111", 15.0),
        ("autoresearch/bot/Tables4.bot-b111111", 23.0),
        ("autoresearch/bot/Crowd.bot-c222222", 67.0),
    ]
    out = C.candidates(exams, [], {})
    assert out["dead"] == ["tables"]
    assert [b for b, _ in out["starts"]] == ["autoresearch/bot/Crowd.bot-c222222"]
