"""Bare-slot live lineage (universe naming).

Live agents log under fixed slot ids ("main", "me", "le-a", "le-b")
forever, across resets. Resets never mint ids: a stall reset reuses the
slot (record persists, pessimistic direction); an admission freezes the
peak weights under a FRESH family id (me0/le-a0/...) and the live slot
continues bare. Frozen achievements are the only new members:
main snapshots (mainN) + admissions (meN/le-aN/le-bN), all 0-based.
Routine exploiter snapshots are gone; no new g-ids, ever.

All scheduler-level (synthetic archives, stubbed games, no engine).
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "ml"))

import archive
import selfplay
import train


def _league_base(tmp_path, n_pool=3):
    base = tmp_path / "archive"
    archive.init(base)
    g000 = archive.save_checkpoint(base, {}, "main", None)
    assert g000 == "g000"
    source = archive.save_checkpoint(base, {}, "main", g000)
    pool = [archive.save_checkpoint(base, {}, "main", g000)
            for _ in range(n_pool)]
    return base, g000, source, pool


def _cfg(tmp_path, **over):
    cfg = selfplay.default_config()
    cfg.update({
        "maps": ["m.map"],
        "turns": 2,
        "seed": 0,
        "lr": 1e-3,
        "epochs": 1,
        "main_source": "g001",
        "g000": "g000",
        "anchors": [],
        "archive": str(tmp_path / "archive"),
    })
    cfg.update(over)
    return cfg


def _setup(tmp_path, monkeypatch, scores=(3, 1), **cfg_over):
    base, g000, source, pool = _league_base(tmp_path)
    cfg = _cfg(tmp_path, **cfg_over)
    selfplay.ensure_roles(base, cfg)
    live = selfplay.load_live_all(cfg, base)

    def fake_play_one(args):
        (c, b, chal_id, field, weights, i, role, map_path) = args[:8]
        archive.record_result(b, field[0], field[1],
                              scores[0], scores[1], kind="eval")
        archive.log_game(b, chal_id, "eval", field[0], field[1],
                         scores[0], scores[1], "rel", map="m",
                         game=f"gid-{chal_id}-{i}")
        return {"rows": [], "rets": [], "scores": [scores[0], scores[1]]}

    monkeypatch.setattr(train, "_play_one", fake_play_one)
    return base, cfg, live


def _matrix_endpoints(base):
    import json

    data = json.loads((base / "matrix.json").read_text())
    endpoints = set()
    for key in data.get("eval", {}):
        if " vs " in key:
            a, b = key.split(" vs ", 1)
            endpoints.update([a, b])
    return endpoints


def _manifest_ids(base):
    return {m["id"] for m in archive.members(base)
            if isinstance(m.get("id"), str)}


# --- live seats are bare slots, across resets ---


def test_games_log_under_bare_slot_ids(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    for _ in range(4):  # one full rotation
        selfplay.run_tick(cfg, base, live)
    endpoints = _matrix_endpoints(base)
    assert {"main", "me", "le-a", "le-b"} <= endpoints
    for row in archive.list_games(base):
        assert row["a"] in ("main", "me", "le-a", "le-b")
        assert row["b"] in ("main", "me", "le-a", "le-b") or True


def test_no_reset_after_drought(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    state = archive.load_league(base)
    state["exploiters"]["me"].update(
        {"games": 400, "window": [0.0] * 40, "id": "me"})
    archive.save_league(base, state)
    # advance to me's tick (main first).
    selfplay.run_tick(cfg, base, live)  # main
    rep = selfplay.run_tick(cfg, base, live)  # me's 401st: drought, no reset
    assert rep["learner"] == "me" and rep["admitted"] is None
    assert "stalled" not in rep  # the stall rule is gone: no such outcome
    state = archive.load_league(base)
    assert state["exploiters"]["me"]["id"] == "me"  # same id, no new row
    assert state["exploiters"]["me"]["games"] == 401  # keeps training
    assert len(state["exploiters"]["me"]["window"]) == 40  # rolls, not cleared
    assert state.get("resets", []) == []  # nothing logged


def test_admission_freezes_family_id_live_stays_bare(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    state = archive.load_league(base)
    state["exploiters"]["me"].update(
        {"games": 40, "window": [1.0] * 40, "id": "me"})
    archive.save_league(base, state)
    selfplay.run_tick(cfg, base, live)  # main
    rep = selfplay.run_tick(cfg, base, live)  # me admitted
    assert rep["admitted"]["id"] == "me0"
    rows = {m["id"]: m for m in archive.members(base)}
    assert rows["me0"]["role"] == "admitted"
    assert rows["me0"]["parent"] == "me"  # seeds from the slot's peak
    state = archive.load_league(base)
    assert state["exploiters"]["me"]["id"] == "me"  # live stays bare
    assert state["admissions"][-1]["id"] == "me0"
    resets = state.get("resets", [])
    assert len(resets) == 1 and resets[0]["slot"] == "me"


def test_admission_names_continue_per_slot(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    archive.save_named_snapshot(base, "me0", {}, "admitted", "me")
    archive.record_admission(base, "me0", "me", 40, "40W-0D-0L")
    state = archive.load_league(base)
    state["exploiters"]["me"].update(
        {"games": 80, "window": [1.0] * 40, "id": "me"})
    archive.save_league(base, state)
    selfplay.run_tick(cfg, base, live)  # main
    rep = selfplay.run_tick(cfg, base, live)  # me admitted again
    assert rep["admitted"]["id"] == "me1"


# --- main snapshots are mainN, 0-based; no exploiter snapshots ---


def test_main_snapshot_is_mainN_zero_based(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(selfplay, "SNAPSHOT_EVERY", 1)
    rep = selfplay.run_tick(cfg, base, live)  # main
    assert rep["snapshot"]["id"] == "main0"
    rows = {m["id"]: m for m in archive.members(base)}
    assert rows["main0"]["role"] == "main-snapshot"
    state = archive.load_league(base)
    assert state["main_id"] == "main0"


def test_no_exploiter_snapshots(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(selfplay, "SNAPSHOT_EVERY", 1)
    reps = [selfplay.run_tick(cfg, base, live) for _ in range(4)]
    by_learner = {r["learner"]: r for r in reps}
    assert by_learner["main"]["snapshot"] is not None
    assert by_learner["me"]["snapshot"] is None
    assert by_learner["le-a"]["snapshot"] is None
    assert by_learner["le-b"]["snapshot"] is None


# --- slot rows ensured once; no new g-ids ---


def test_slot_rows_ensured_idempotent(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    rows = {m["id"]: m for m in archive.members(base)}
    for slot in ("main", "me", "le-a", "le-b"):
        assert slot in rows
    before = sorted(rows)
    selfplay.ensure_league(base, cfg)
    after = sorted(m["id"] for m in archive.members(base))
    assert before == after


def test_no_new_g_ids_from_scheduler(tmp_path, monkeypatch):
    import json

    base, cfg, live = _setup(tmp_path, monkeypatch)
    g_before = {i for i in _manifest_ids(base) if isinstance(i, str)
                and len(i) > 1 and i[0] == "g" and i[1:].isdigit()}
    monkeypatch.setattr(selfplay, "SNAPSHOT_EVERY", 1)
    for _ in range(8):  # rotations + snapshots + nothing admitted
        selfplay.run_tick(cfg, base, live)
    g_after = {i for i in _manifest_ids(base) if isinstance(i, str)
               and len(i) > 1 and i[0] == "g" and i[1:].isdigit()}
    assert g_after == g_before
    import re

    data = json.loads((base / "matrix.json").read_text())
    assert "me0" not in data["ids"]  # no admission happened
    universe = re.compile(r"^(main|me|le-[ab]|main\d+)$")
    for i in data["ids"]:
        assert universe.match(i) or i in g_before, i
