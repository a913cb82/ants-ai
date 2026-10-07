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


def test_rates_beat_totals():
    exams = [
        ("autoresearch/bot/Tables.bot-b111111", 30.0),
        ("autoresearch/bot/Tables2.bot-d333333", 20.0),
        ("autoresearch/bot/Crowd.bot-c222222", 67.0),
    ]
    farmed = [["x/Tables.bot-b111111", f"y/V{i}.bot-000000{i}"] for i in range(10)]
    games = farmed + [["x/Tables2.bot-d333333", "y/Strong.bot-9999999"]]
    mu_of = {f"V{i}.bot": 10.0 for i in range(10)}
    mu_of["Strong.bot"] = 60.0
    out = C.candidates(exams, games, mu_of)
    names = [C._basename(b) for b, _ in out["starts"]]
    assert names[1] == "Tables2.bot", names


def test_padded_rates_favor_evidence():
    exams = [
        ("autoresearch/bot/Tables.bot-b111111", 30.0),
        ("autoresearch/bot/Tables2.bot-d333333", 20.0),
        ("autoresearch/bot/Crowd.bot-c222222", 67.0),
    ]
    wonder = [["x/Tables.bot-b111111", "y/Strong.bot-9999999"]]
    solid = [["x/Tables2.bot-d333333", f"y/V{i}.bot-000000{i}"] for i in range(30)]
    games = wonder + solid
    mu_of = {"Strong.bot": 60.0}
    mu_of.update({f"V{i}.bot": 10.0 for i in range(30)})
    out = C.candidates(exams, games, mu_of)
    names = [C._basename(b) for b, _ in out["starts"]]
    assert names[1] == "Tables2.bot", names


def test_five_plus_five_seats():
    exams = [(f"autoresearch/bot/B{i}.bot-000000{i}", 10.0) for i in range(8)]
    exams.append(("autoresearch/bot/Crowd.bot-c222222", 67.0))
    games = [[f"x/B{i}.bot-000000{i}", "y/Crowd.bot-c222222"] for i in range(6)]
    out = C.candidates(exams, games, {})
    names = [C._basename(b) for b, _ in out["starts"]]
    assert names[0] == "Crowd.bot"
    assert names[1:6] == [f"B{i}.bot" for i in range(5)], names
    assert names[6:] == ["B5.bot", "B6.bot", "B7.bot"], names
