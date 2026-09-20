"""Leaderboard renders from the games log (ratings rebuild + stats)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "league"))

GAMES = [
    {"field": ["a", "b"], "result": ["a", "b"]},
    {"field": ["a", "b", "c"], "result": ["c", "a", "b"]},
    {"field": ["a", "c"], "result": ["a", "c"]},
]


def test_table_sorts_by_mu_desc():
    from board import table

    rows = table(GAMES)
    mus = [r["mu"] for r in rows]
    assert mus == sorted(mus, reverse=True)
    assert [r["id"] for r in rows] == ["a", "c", "b"]


def test_table_counts_games_and_wins():
    from board import table

    rows = {r["id"]: r for r in table(GAMES)}
    assert rows["a"]["games"] == 3 and rows["a"]["wins"] == 2
    assert rows["c"]["games"] == 2 and rows["c"]["wins"] == 1
    assert rows["b"]["games"] == 2 and rows["b"]["wins"] == 0


def test_render_contains_header_and_ids(capsys):
    from board import render

    render(GAMES)
    out = capsys.readouterr().out
    assert "mu" in out and "sigma" in out
    for bid in ("a", "b", "c"):
        assert bid in out
