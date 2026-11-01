"""Family naming for new league members (plan-league.md).

Admissions take main-exploiter-{k} / league-exploiter-a-{k} /
league-exploiter-b-{k} (0-based, derived from the admissions log).
Main snapshots keep g-ids; the live head stays bare "main".
Incarnations stay g-numbered transients; the g-allocator is untouched.
Replays show role names for live seats (main / main-exploiter /
league-exploiter-a-b) and member ids for frozen opponents.
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


def _league_base(tmp_path, n_pool=2):
    base = tmp_path / "archive"
    archive.init(base)
    g000 = archive.save_checkpoint(base, {}, "main", None)
    assert g000 == "g000"
    source = archive.save_checkpoint(base, {}, "main", g000)
    for _ in range(n_pool):
        archive.save_checkpoint(base, {}, "main", g000)
    return base, g000, source


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
    base, g000, source = _league_base(tmp_path)
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


# --- save_named_snapshot ---


def test_named_snapshot_round_trips_and_validates_role(tmp_path):
    base, _, _ = _league_base(tmp_path)
    sid = archive.save_named_snapshot(base, "main-1", {"w": [1.0]},
                                      "main-snapshot", None)
    assert sid == "main-1"
    rows = {m["id"]: m for m in archive.members(base)}
    assert rows["main-1"] == {"id": "main-1", "role": "main-snapshot",
                              "parent": None}
    assert archive.load_checkpoint(base, "main-1") == {"w": [1.0]}
    with pytest.raises(ValueError):
        archive.save_named_snapshot(base, "main-2", {"w": 1},
                                    "challenger", None)
    assert "main-2" not in {m["id"] for m in archive.members(base)}


def test_named_snapshot_duplicate_raises(tmp_path):
    base, _, _ = _league_base(tmp_path)
    archive.save_named_snapshot(base, "main-1", {}, "main-snapshot", None)
    with pytest.raises(ValueError):
        archive.save_named_snapshot(base, "main-1", {}, "main-snapshot",
                                    None)


def test_g_allocator_untouched_by_named(tmp_path):
    base, _, _ = _league_base(tmp_path)
    # base has g000..g003 (g000 + source + 2 pool).
    archive.save_named_snapshot(base, "main-1", {}, "main-snapshot", None)
    archive.save_named_snapshot(base, "main-exploiter-1", {}, "admitted",
                                "g000")
    nxt = archive.save_checkpoint(base, {}, "main", None)
    assert nxt == "g004"  # sequential: named ids do not consume g-numbers.


# --- _next_family_id ---


def test_next_family_id_first_free_and_collision_skip(tmp_path):
    base, _, _ = _league_base(tmp_path)
    assert selfplay._next_family_id(base, "main-exploiter") == \
        "main-exploiter-0"
    archive.save_named_snapshot(base, "main-exploiter-0", {},
                                "admitted", None)
    assert selfplay._next_family_id(base, "main-exploiter") == \
        "main-exploiter-1"
    # gap reuse: first free wins for the raw allocator.
    archive.save_named_snapshot(base, "main-exploiter-2", {},
                                "admitted", None)
    assert selfplay._next_family_id(base, "main-exploiter") == \
        "main-exploiter-1"


# --- maybe_snapshot: main keeps a g-id (the live head is bare `main`) ---


def test_main_snapshot_keeps_g_id(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(selfplay, "SNAPSHOT_EVERY", 1)
    state = archive.load_league(base)
    assert state["main_snapshots"] == ["g001"]  # lineage of one
    rep = selfplay.run_tick(cfg, base, live)  # main's 1st own-game
    assert rep["learner"] == "main"
    sid = rep["snapshot"]["id"]
    assert sid.startswith("g") and sid != "main"
    rows = {m["id"]: m for m in archive.members(base)}
    assert rows[sid]["role"] == "main-snapshot"
    assert rows[sid]["parent"] == "g001"
    state = archive.load_league(base)
    assert state["main_id"] == sid
    assert state["main_snapshots"] == ["g001", sid]


def test_main_snapshot_g_ids_across_reload(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(selfplay, "SNAPSHOT_EVERY", 1)
    rep1 = selfplay.run_tick(cfg, base, live)  # main, 1st g-snapshot
    first = rep1["snapshot"]["id"]
    # simulate a restart: fresh live handle, state reloaded from disk.
    live2 = selfplay.load_live_all(cfg, base)
    selfplay.run_tick(cfg, base, live2)  # me
    selfplay.run_tick(cfg, base, live2)  # le-a
    selfplay.run_tick(cfg, base, live2)  # le-b
    rep = selfplay.run_tick(cfg, base, live2)  # main's 2nd own-game
    second = rep["snapshot"]["id"]
    assert second.startswith("g") and second != first
    state = archive.load_league(base)
    assert state["main_snapshots"] == ["g001", first, second]


# --- maybe_admit: per-slot family names ---


def _force_admission(tmp_path, monkeypatch, learner, scores=(5, 1)):
    base, cfg, live = _setup(tmp_path, monkeypatch, scores=scores)
    state = archive.load_league(base)
    state["exploiters"][learner].update(
        {"games": 40, "window": [1.0] * 40, "reset_at": 0})
    archive.save_league(base, state)
    # advance the scheduler to the learner.
    order = ["main", "me", "le-a", "le-b"]
    idx = order.index(learner)
    for _ in range(idx + 1):
        rep = selfplay.run_tick(cfg, base, live)
    assert rep["learner"] == learner
    assert rep["admitted"] is not None
    return base, cfg, live, rep


def test_admission_names_per_slot(tmp_path, monkeypatch):
    for slot, want in (("me", "main-exploiter-0"),
                       ("le-a", "league-exploiter-a-0"),
                       ("le-b", "league-exploiter-b-0")):
        sub = tmp_path / slot
        sub.mkdir()
        _, _, _, rep = _force_admission(sub, monkeypatch, slot)
        assert rep["admitted"]["id"] == want


def test_admission_count_derived_from_log_and_collision_skipped(
        tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch, scores=(5, 1))
    # a prior me admission + a squatter on the next name.
    archive.save_named_snapshot(base, "main-exploiter-0", {},
                                "admitted", "g000")
    archive.record_admission(base, "main-exploiter-0", "me", 40, "40W-0D-0L")
    archive.save_named_snapshot(base, "main-exploiter-1", {},
                                "admitted", "g000")
    state = archive.load_league(base)
    state["exploiters"]["me"].update(
        {"games": 40, "window": [1.0] * 40, "reset_at": 0})
    archive.save_league(base, state)
    selfplay.run_tick(cfg, base, live)  # main
    rep = selfplay.run_tick(cfg, base, live)  # me admitted
    # count says -1 next, but -1 is taken: skip to -2.
    assert rep["admitted"]["id"] == "main-exploiter-2"


def test_admitted_copy_in_manifest_and_log(tmp_path, monkeypatch):
    base, cfg, live, rep = _force_admission(tmp_path, monkeypatch, "le-a")
    sid = rep["admitted"]["id"]
    assert sid == "league-exploiter-a-0"
    rows = {m["id"]: m for m in archive.members(base)}
    assert rows[sid]["role"] == "admitted"
    state = archive.load_league(base)
    assert state["admissions"][-1]["id"] == sid
    assert state["admissions"][-1]["role"] == "le-a"
    # the admitted freeze is the record: no extra snapshot copy.
    assert rep["snapshot"] is None
    # incarnations stay g-numbered transients.
    new_inc = state["exploiters"]["le-a"]["id"]
    assert new_inc.startswith("g")
    assert new_inc not in (sid,)


def test_replay_display_names_use_roles_not_incarnations(tmp_path,
                                                        monkeypatch):
    import json

    base, cfg, live = _setup(tmp_path, monkeypatch)
    seen = []

    def rec(args):
        seen.append(args[8] if len(args) > 8 else None)
        (c, b, chal_id, field, weights, i, role, map_path) = args[:8]
        archive.record_result(b, field[0], field[1], 3, 1, kind="eval")
        return {"rows": [], "rets": [], "scores": [3, 1]}

    monkeypatch.setattr(train, "_play_one", rec)
    selfplay.run_tick(cfg, base, live)  # main
    selfplay.run_tick(cfg, base, live)  # me (live incarnation)
    disp_main, disp_me = seen
    state = archive.load_league(base)
    me_inc = state["exploiters"]["me"]["id"]
    assert me_inc.startswith("g")  # incarnations stay internal
    assert disp_main[0] == "main"
    assert disp_me[0] == "main-exploiter"  # role, not incarnation
    assert disp_me[0] != me_inc
    # opponents display as their member ids.
    assert disp_main[1] != "main" and disp_me[1] != "main-exploiter"
    # attribution still uses incarnation ids, never display names.
    data = json.loads((base / "matrix.json").read_text())
    assert "main-exploiter" not in data["ids"]
    assert me_inc in data["ids"]


def test_live_le_display_names_per_slot(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    seen = []

    def rec(args):
        seen.append(args[8] if len(args) > 8 else None)
        (c, b, chal_id, field, weights, i, role, map_path) = args[:8]
        return {"rows": [], "rets": [], "scores": [1, 3]}

    monkeypatch.setattr(train, "_play_one", rec)
    for _ in range(4):
        selfplay.run_tick(cfg, base, live)  # main, me, le-a, le-b
    assert [d[0] for d in seen] == ["main", "main-exploiter",
                                    "league-exploiter-a",
                                    "league-exploiter-b"]


def test_live_head_stays_bare_main(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    for _ in range(4):
        selfplay.run_tick(cfg, base, live)
    import json

    data = json.loads((base / "matrix.json").read_text())
    assert "main" in data["ids"]
    # main's own games log under "main", never a family id.
    endpoints = set()
    for key in data.get("eval", {}):
        if " vs " in key:
            a, b = key.split(" vs ", 1)
            endpoints.update([a, b])
    assert "main" in endpoints


def test_dashboard_handles_family_ids(tmp_path):
    import dashboard

    base, _, _ = _league_base(tmp_path)
    archive.save_named_snapshot(base, "g009", {}, "main-snapshot",
                                "g001")
    archive.save_named_snapshot(base, "main-exploiter-0", {},
                                "admitted", "g005")
    state = archive.init_league(base, "g009", ["g000"])
    state["main_snapshots"] = ["g001", "g009"]
    archive.save_league(base, state)
    # tracked/panel/anchor-trend/member table all key on opaque strings.
    assert "g009" in [m["id"] for m in archive.members(base)]
    assert dashboard.league_panel(base) == ["g000"]
    snap = dashboard.snapshot(base)
    ids = [m["id"] for m in snap["members"]]
    assert "g009" in ids and "main-exploiter-0" in ids
    assert snap["anchor_trend"]["snapshots"][:2] == ["g001", "g009"]
    # g-allocator still ignores family ids when dashboard is watching.
    assert archive.save_checkpoint(base, {}, "main", None).startswith("g")
