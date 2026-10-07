"""Tests for autoresearch/candidate_scorer.py: the scorer queue."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import candidate_scorer as S


def test_unscored_keeps_pool_bots_without_exams():
    pool_ids = [
        "autoresearch/bot/Tables.bot-b111111",
        "autoresearch/bot/Tables2.bot-d333333",
        "bots/other/main.bot-9999999",
    ]
    out = S.unscored(pool_ids, {"Tables.bot"})
    assert out == ["autoresearch/bot/Tables2.bot-d333333"]


def test_oldest_takes_earliest_birth():
    queue = ["autoresearch/bot/B.bot-2222222", "autoresearch/bot/A.bot-1111111"]
    birth_of = {"2222222": "2026-10-02", "1111111": "2026-10-01"}
    assert S.oldest(queue, birth_of) == "autoresearch/bot/A.bot-1111111"


def test_oldest_without_dates_keeps_pool_order():
    queue = ["autoresearch/bot/B.bot-2222222", "autoresearch/bot/A.bot-1111111"]
    assert S.oldest(queue, {}) == "autoresearch/bot/B.bot-2222222"


def test_oldest_empty_is_empty():
    assert S.oldest([], {}) == ""


def test_group_by_code_merges_same_contents():
    pairs = [
        ("a/X.bot-111", "blob1"),
        ("a/X.bot-222", "blob1"),
        ("a/Y.bot-333", "blob2"),
    ]
    groups = S.group_by_code(pairs)
    assert len(groups) == 2
    assert sorted(groups["blob1"]) == ["a/X.bot-111", "a/X.bot-222"]
