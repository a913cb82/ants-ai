"""Per-incarnation member ids (exploiter reset bugfix).

Exploiter games used to log under slot names ("me"/"le-a"/"le-b"), so a
reset kept the SAME id: fresh g000 weights inherited the old
incarnation's peak Elo and polluted PFSP records, and admitted frozen
copies were indistinguishable from the live slot. Every init/reset now
mints a fresh manifest member (role me/le, parent g000); games log under
the incarnation id. Main keeps logging under "main" forever.

All scheduler-level (synthetic archives, stubbed games, no engine);
the Elo assertion is pure (dashboard pass over a crafted matrix).
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
        # Like the real _play_one: record the canonical game under the
        # seat ids (incarnation ids for exploiters, "main" for main).
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


# --- games attribute per incarnation, never the slot name ---


def test_games_log_under_incarnation_ids_not_slot_names(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    state = archive.load_league(base)
    incs = {n: state["exploiters"][n]["id"] for n in ("me", "le-a", "le-b")}
    assert all(isinstance(i, str) for i in incs.values())
    for _ in range(4):  # one full rotation
        selfplay.run_tick(cfg, base, live)
    endpoints = _matrix_endpoints(base)
    assert not (set(incs) & endpoints)  # no slot name in the matrix...
    assert set(incs.values()) <= endpoints  # ...but every incarnation is
    for row in archive.list_games(base):
        assert row["a"] not in incs and row["b"] not in incs


def test_reset_freezes_old_incarnation_record(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    for _ in range(4):
        selfplay.run_tick(cfg, base, live)
    state = archive.load_league(base)
    old_inc = state["exploiters"]["me"]["id"]
    old_count = archive.member_game_counts(base)[old_inc]
    assert old_count > 0
    # Force a stall on me's next tick (scheduler is back at main).
    exp = state["exploiters"]["me"]
    exp.update({"games": 400, "window": [0.0] * 40, "reset_at": 0})
    archive.save_league(base, state)
    selfplay.run_tick(cfg, base, live)  # main
    rep = selfplay.run_tick(cfg, base, live)  # me stalls
    assert rep["stalled"] is True
    state = archive.load_league(base)
    new_inc = state["exploiters"]["me"]["id"]
    assert new_inc != old_inc
    counts = archive.member_game_counts(base)
    # The stalling tick's own game was played by the old incarnation, so
    # it lands there; the reset only diverts LATER games.
    assert counts[old_inc] == old_count + 1
    # The new incarnation restarts empty (g000's ancient games belong to
    # g000 the pool member, never to the live slot).
    assert counts[new_inc] == 0
    # ...and later games land under the new id only: the old record is
    # frozen from here on.
    for _ in range(4):  # le-a, le-b, main, me-under-the-new-id
        selfplay.run_tick(cfg, base, live)
    counts = archive.member_game_counts(base)
    assert counts[old_inc] == old_count + 1
    assert counts[new_inc] == 1


# --- fresh incarnation Elo restarts near zero (synthetic, no engine) ---


def test_fresh_incarnation_elo_restarts_near_zero_after_peak():
    import dashboard

    # Old incarnation g010 peaks (40-0 vs pool g001); the reset mints
    # g011 (parent g000) which draws g000 once. Same pass, same field.
    ids = ["g000", "g001", "g010", "g011"]
    parents = {"g001": "g000", "g010": "g000", "g011": "g000"}
    per_interval = [{(1, 2): [0.0, 40.0]}, {(0, 3): [0.5, 0.5]}]
    out = dashboard.running_elo_intervals(ids, per_interval,
                                          ["g010", "g011"], parents=parents)
    peak = out["series"]["g010"][-1]
    fresh = out["series"]["g011"]
    assert peak > 3.0  # the old incarnation peaked...
    assert fresh[0] == pytest.approx(0.0, abs=1e-9)  # ...unplayed reads 0
    assert abs(fresh[-1]) < 0.5  # ...and the reset restarts near 0.0
    # The retired incarnation flatlines: no new games, no new Elo.
    assert out["series"]["g010"][0] == pytest.approx(
        out["series"]["g010"][-1])


# --- admission windows stay per-cycle ---


def test_admission_window_is_per_cycle_not_lifetime(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch, scores=(5, 1))
    state = archive.load_league(base)
    exp = state["exploiters"]["le-a"]
    exp.update({"games": 40, "window": [1.0] * 40, "reset_at": 0})
    archive.save_league(base, state)
    selfplay.run_tick(cfg, base, live)  # main
    selfplay.run_tick(cfg, base, live)  # me
    rep = selfplay.run_tick(cfg, base, live)  # le-a admitted
    assert rep["admitted"] is not None
    state = archive.load_league(base)
    assert state["exploiters"]["le-a"]["window"] == []
    at = state["exploiters"]["le-a"]["games"]
    # 38 more wins + the tick's own game = 39: not enough, no admission.
    state["exploiters"]["le-a"]["window"] = [1.0] * 38
    state["exploiters"]["le-a"]["games"] = at + 38
    archive.save_league(base, state)
    for _ in range(4):
        rep = selfplay.run_tick(cfg, base, live)
        if rep["learner"] == "le-a":
            assert rep["admitted"] is None
            break
    else:
        pytest.fail("le-a never ticked")
    # The next in-cycle win (40th) admits again: the window counted only
    # post-reset games.
    for _ in range(4):
        rep = selfplay.run_tick(cfg, base, live)
        if rep["learner"] == "le-a":
            assert rep["admitted"] is not None
            break
    else:
        pytest.fail("le-a never ticked")


# --- main trajectory uninterrupted by exploiter resets ---


def test_main_logging_uninterrupted_across_exploiter_resets(
        tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    for _ in range(4):
        selfplay.run_tick(cfg, base, live)
    main_before = archive.member_game_counts(base)["main"]
    assert main_before > 0
    main_id_before = archive.load_league(base)["main_id"]
    state = archive.load_league(base)
    state["exploiters"]["me"].update(
        {"games": 400, "window": [0.0] * 40, "reset_at": 0})
    archive.save_league(base, state)
    for _ in range(4):
        selfplay.run_tick(cfg, base, live)
    counts = archive.member_game_counts(base)
    assert counts["main"] > main_before  # main keeps accumulating
    assert "main" in _matrix_endpoints(base)
    state = archive.load_league(base)
    assert state["main_id"] == main_id_before  # resets never touch main
    assert state["main_games"] == 2


# --- tracked panel follows live incarnations ---


def test_tracked_follows_live_ids_across_reset(tmp_path, monkeypatch):
    import dashboard

    base, cfg, live = _setup(tmp_path, monkeypatch)
    grouped = dashboard.cached_grouped(base)
    state = archive.load_league(base)
    old_inc = state["exploiters"]["me"]["id"]
    assert old_inc in dashboard.tracked_members(base, grouped)
    state["exploiters"]["me"].update(
        {"games": 400, "window": [0.0] * 40, "reset_at": 0})
    archive.save_league(base, state)
    selfplay.run_tick(cfg, base, live)  # main
    selfplay.run_tick(cfg, base, live)  # me stalls -> new incarnation
    state = archive.load_league(base)
    new_inc = state["exploiters"]["me"]["id"]
    assert new_inc != old_inc
    assert dashboard.tracked_members(base, grouped) == \
        ["main", new_inc, state["exploiters"]["le-a"]["id"],
         state["exploiters"]["le-b"]["id"]]


# --- admitted copies seed from the incarnation peak ---


def test_admitted_copy_parents_to_live_incarnation(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch, scores=(5, 1))
    state = archive.load_league(base)
    old_inc = state["exploiters"]["le-a"]["id"]
    state["exploiters"]["le-a"].update(
        {"games": 40, "window": [1.0] * 40, "reset_at": 0})
    archive.save_league(base, state)
    selfplay.run_tick(cfg, base, live)  # main
    selfplay.run_tick(cfg, base, live)  # me
    rep = selfplay.run_tick(cfg, base, live)  # le-a admitted
    rows = {m["id"]: m for m in archive.members(base)}
    assert rows[rep["admitted"]["id"]]["parent"] == old_inc


# --- PFSP reads the incarnation record, not the slot ---


def test_select_opponent_uses_sample_id_for_records(tmp_path):
    import random

    base = tmp_path / "archive"
    archive.init(base)
    g000 = archive.save_checkpoint(base, {}, "main", None)
    inc = archive.save_checkpoint(base, {}, "me", g000)
    main_snap = archive.save_checkpoint(base, {}, "main-snapshot", g000)
    state = archive.init_league(base, main_snap, [])
    # The incarnation crushes main: ME must stay locked onto main.
    archive.record_result(base, inc, main_snap, 9.0, 1.0)
    totals = archive.member_game_counts(base)
    rng = random.Random(0)
    opp = train.select_opponent(base, "me", state,
                                selfplay.pair_records(base), totals, rng,
                                sample_id=inc)
    assert opp == main_snap
    # Backward compat: without a sample id the slot still samples.
    opp2 = train.select_opponent(base, "me", state,
                                 selfplay.pair_records(base), totals, rng)
    assert isinstance(opp2, str)
