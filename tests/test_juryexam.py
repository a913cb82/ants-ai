"""Stage 1 jury exam: challenger faces champ + PFSP/counter jury.

Flag-gated by cfg["exam_jury_size"] (0 = champ-only legacy).
TDD: these tests are written first and must fail before evaluate.py
grows plan_exam_opponents/select_jury + the jury path.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))


def _weights():
    return {"a": [1.0]}


def _seed_archive(base, n_members=6):
    """Fresh archive with n_members mains + champ = newest; even split
    eval draws between champ and each older member (rated frontier)."""
    import archive

    ids = [archive.save_checkpoint(base, _weights(), "main", None)
           for _ in range(n_members)]
    champ = ids[-1]
    archive.set_champion(base, champ)
    for oid in ids[:-1]:
        archive.record_result(base, champ, oid, 1.0, 1.0, kind="eval")
        archive.record_result(base, oid, champ, 1.0, 1.0, kind="eval")
    return ids, champ


def test_flag_off_opponent_list_byte_identical():
    """(a) jury disabled -> every exam game is vs the champ, exactly as
    today (byte-identical opponent list)."""
    import evaluate

    base = Path("/tmp/jury-a")
    opponents = evaluate.plan_exam_opponents(
        base, "g099", "g007", 20, jury_size=0, seed=0)
    assert opponents == ["g007"] * 20


def test_flag_off_evaluate_plays_champ_only(tmp_path, monkeypatch):
    """(a2) evaluate() without the flag plays all games vs the champ."""
    import archive
    import evaluate
    import game_if

    base = tmp_path / "archive"
    w = _weights()
    champ = archive.save_checkpoint(base, w, role="main", parent=None)
    seen = []

    def fake_play(root, python, wa, wb, gcfg, outdir, **kwargs):
        seen.append((kwargs.get("name_a"), kwargs.get("name_b")))
        (outdir / "logs").mkdir(parents=True, exist_ok=True)
        (outdir / "logs" / "0.replay").write_text(
            '{"game_length": 10, "score": [1, 1], "replaydata": {}}')
        return {"game": {"game_length": 10, "score": [1, 1],
                         "replaydata": {}},
                "records_a": [], "records_b": []}

    monkeypatch.setattr(game_if, "play", fake_play)
    cfg = {"eval_games": 6, "maps": ["m.map"], "turns": 5,
           "temperature": 0.0, "seed": 0, "workers": 1}
    evaluate.evaluate(cfg, base, "gchal", w, champ, w)
    assert len(seen) == 6
    for a, b in seen:
        assert set((a, b)) == {"gchal", champ}


def test_flag_on_jury_shape_and_determinism(tmp_path):
    """(b) jury on -> 20 games, 12 vs champ, jurors from the frontier,
    identical given the same seed."""
    import evaluate

    base = tmp_path / "archive"
    ids, champ = _seed_archive(base)
    chal = "g099"
    first = evaluate.plan_exam_opponents(
        base, chal, champ, 20, jury_size=4, seed=7)
    second = evaluate.plan_exam_opponents(
        base, chal, champ, 20, jury_size=4, seed=7)
    assert first == second  # deterministic given seed
    assert len(first) == 20
    assert first.count(champ) == 12  # champ keeps the majority share
    jurors = sorted(set(first) - {champ})
    assert 1 <= len(jurors) <= 4  # 8 jury games across 3-4 members
    assert chal not in jurors  # never face yourself
    frontier = set(ids[:-1])
    assert set(jurors) <= frontier  # jurors are rated population members


def test_counter_inclusion_giant_killer(tmp_path):
    """(c) a recorded giant-killer outside the frontier window still
    makes the jury (mandatory until dethroned)."""
    import evaluate

    base = tmp_path / "archive"
    ids, champ = _seed_archive(base, n_members=6)
    killer = ids[0]
    import archive
    # Giant-killer: old, outside a tight window, but banks win after
    # win over the champ (and draws elsewhere so Nash mass concentrates).
    for _ in range(6):
        archive.record_result(base, killer, champ, 3.0, 1.0, kind="eval")
    for oid in ids[1:-1]:
        archive.record_result(base, killer, oid, 3.0, 1.0, kind="eval")
        archive.record_result(base, oid, killer, 1.0, 1.0, kind="eval")
    jury = evaluate.select_jury(
        base, "g099", champ, 3, seed=0, window=2)
    assert killer in jury


def test_promotion_math_unchanged():
    """(d) same W/D/L -> same verdict; the jury only changes WHO the
    games are against, never the bar."""
    import evaluate

    assert evaluate.should_promote(10, 0, 10)
    assert evaluate.should_promote(7, 0, 10)
    assert not evaluate.should_promote(6, 0, 10)
    assert evaluate.should_promote(6, 2, 10)
    assert not evaluate.should_promote(5, 2, 10)
    # Jury-shaped aggregate (12 champ + 8 jury games, one tally).
    assert evaluate.should_promote(14, 2, 20)
    assert not evaluate.should_promote(9, 2, 20)


def test_scratch_end_to_end_jury_path(tmp_path, monkeypatch):
    """(e) 1-2 evals on a scratch archive run the jury path (mocked
    engine) without crashing; game totals add up."""
    import archive
    import evaluate
    import game_if

    base = tmp_path / "scratch"
    w = _weights()
    ids = [archive.save_checkpoint(base, w, "main", None) for _ in range(4)]
    champ = ids[-1]
    archive.set_champion(base, champ)

    def fake_play(root, python, wa, wb, gcfg, outdir, **kwargs):
        (outdir / "logs").mkdir(parents=True, exist_ok=True)
        (outdir / "logs" / "0.replay").write_text(
            '{"game_length": 10, "score": [2, 1], "replaydata": {}}')
        return {"game": {"game_length": 10, "score": [2, 1],
                         "replaydata": {}},
                "records_a": [], "records_b": []}

    monkeypatch.setattr(game_if, "play", fake_play)
    cfg = {"eval_games": 20, "maps": ["m.map"], "turns": 5,
           "temperature": 0.0, "seed": 1, "workers": 1,
           "exam_jury_size": 4}
    ev = evaluate.evaluate(cfg, base, "gchal", w, champ, w)
    assert ev["games"] == 20
    assert ev["wins"] + ev["draws"] <= 20
    assert len(archive.list_games(base, member="gchal")) == 20
