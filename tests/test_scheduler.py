import json
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
    """Synthetic league archive: g000 + main source + pool, no engine."""
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
    """League ready to tick with a stubbed game (no engine)."""
    base, g000, source, pool = _league_base(tmp_path)
    cfg = _cfg(tmp_path, **cfg_over)
    selfplay.ensure_roles(base, cfg)
    live = selfplay.load_live_all(cfg, base)

    def fake_play_one(args):
        (c, b, chal_id, field, weights, i, role, map_path) = args
        return {"rows": [], "rets": [], "scores": [scores[0], scores[1]]}

    monkeypatch.setattr(train, "_play_one", fake_play_one)
    return base, cfg, live


def test_scheduler_constants_match_plan():
    assert selfplay.MICRO_BATCH == 8
    assert selfplay.SNAPSHOT_EVERY == 80
    assert selfplay.ADMISSION_RATE == 0.6
    assert selfplay.STALL_GAMES == 400
    assert archive.current_learner({"scheduler_pos": 0}) == "main"


def test_rotation_order_main_me_lea_leb(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    reports = [selfplay.run_tick(cfg, base, live) for _ in range(4)]
    assert [r["learner"] for r in reports] == ["main", "me", "le-a", "le-b"]
    state = archive.load_league(base)
    assert archive.current_learner(state) == "main"  # wrapped around
    assert state["tick"] == 4


def test_micro_batch_update_every_eighth_own_game(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    calls = []
    real_update = train.ppo_update

    def counting(policy, opt, batch, c, **k):
        calls.append(len(batch))
        return real_update(policy, opt, batch, c, **k)

    monkeypatch.setattr(train, "ppo_update", counting)
    monkeypatch.setattr(selfplay, "MICRO_BATCH", 2)
    for _ in range(8):  # two full rotations: every learner plays twice
        selfplay.run_tick(cfg, base, live)
    assert len(calls) == 4  # one update per learner on its 2nd own-game
    # progress counters keep counting past the update tick.
    for _ in range(4):
        selfplay.run_tick(cfg, base, live)
    assert len(calls) == 4  # third own-game: no update yet


def test_snapshot_cadence_freezes_permanent_members(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(selfplay, "SNAPSHOT_EVERY", 2)
    # Setup minted one incarnation per exploiter (role me/le, parent
    # g000): the live ids games log under.
    state = archive.load_league(base)
    me_inc = state["exploiters"]["me"]["id"]
    inc_row = {m["id"]: m for m in archive.members(base)}[me_inc]
    assert inc_row == {"id": me_inc, "role": "me", "parent": "g000"}
    before = len(archive.members(base))
    for _ in range(8):  # every learner reaches its 2nd own-game
        selfplay.run_tick(cfg, base, live)
    members = archive.members(base)
    assert len(members) == before + 4
    roles = [m["role"] for m in members[before:]]
    assert roles == ["main-snapshot", "me", "le", "le"]
    state = archive.load_league(base)
    assert state["main_snapshots"][-1] == members[before]["id"]
    assert state["main_id"] == members[before]["id"]
    # Snapshots parent to the live incarnation but never overwrite it:
    # the incarnation id stays stable until a reset mints a new one.
    assert state["exploiters"]["me"]["id"] == me_inc
    assert members[before + 1]["parent"] == me_inc


def test_anchor_measurement_runs_on_main_snapshot(tmp_path, monkeypatch):
    import game_if

    base, cfg, live = _setup(tmp_path, monkeypatch)
    state = archive.load_league(base)
    state["anchors"] = ["g000"]
    archive.save_league(base, state)

    def fake_play(root, python, weights, gcfg, outdir, names=None):
        outdir = Path(outdir)
        (outdir / "logs").mkdir(parents=True, exist_ok=True)
        (outdir / "logs" / "0.replay").write_text(
            json.dumps({"game_length": 2, "score": [4, 2],
                        "replaydata": {}}))
        return {"game": {"game_length": 2, "score": [4, 2],
                           "replaydata": {}},
                "records": [[], []], "retried": False}

    monkeypatch.setattr(game_if, "play", fake_play)
    monkeypatch.setattr(selfplay, "SNAPSHOT_EVERY", 1)
    rep = selfplay.run_tick(cfg, base, live)  # main's 1st own-game
    assert rep["learner"] == "main"
    assert rep["snapshot"] is not None
    rows = archive.list_anchors(base, snapshot_id=rep["snapshot"]["id"])
    assert len(rows) == 1
    assert rows[0]["anchor_id"] == "g000"
    assert (rows[0]["wins"] + rows[0]["losses"]
            + rows[0]["draws"]) == 2  # two games, no training


def test_admission_trigger_freezes_and_resets(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch, scores=(5, 1))
    state = archive.load_league(base)
    exp = state["exploiters"]["le-a"]
    old_inc = exp["id"]
    exp.update({"games": 40, "window": [1.0] * 40, "reset_at": 0})
    archive.save_league(base, state)
    g000_w = archive.load_checkpoint(base, "g000")
    before = len(archive.members(base))
    # advance the scheduler to le-a (main, me first).
    selfplay.run_tick(cfg, base, live)
    selfplay.run_tick(cfg, base, live)
    rep = selfplay.run_tick(cfg, base, live)
    assert rep["learner"] == "le-a"
    assert rep["admitted"] is not None
    assert rep["admitted"]["role"] == "le-a"
    assert rep["snapshot"] is None  # the freeze is the record, no extra copy
    members = archive.members(base)
    assert members[-2]["role"] == "admitted"
    assert members[-2]["parent"] == old_inc  # seeds from the peak
    assert len(members) == before + 2  # admitted copy + fresh incarnation
    # learner reset to a fresh incarnation: new id, parent g000.
    # learner reset to a FRESH incarnation (g000 weights + fresh Adam,
    # new member id) with a cleared window.
    assert json.loads(
        (base / "learners" / "le-a" / "weights.json").read_text()) == g000_w
    assert not (base / "learners" / "le-a" / "opt.json").exists()
    state = archive.load_league(base)
    assert state["exploiters"]["le-a"]["window"] == []
    assert state["exploiters"]["le-a"]["reset_at"] == 41
    new_inc = state["exploiters"]["le-a"]["id"]
    assert new_inc != old_inc and new_inc != members[-2]["id"]
    assert {m["id"]: m for m in archive.members(base)}[new_inc] == \
        {"id": new_inc, "role": "le", "parent": "g000"}
    assert state["admissions"][-1]["id"] == members[-2]["id"]


def test_stall_reset_after_drought(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch, scores=(0, 5))
    state = archive.load_league(base)
    exp = state["exploiters"]["me"]
    old_inc = exp["id"]
    exp.update({"games": 399, "window": [0.0] * 40, "reset_at": 0})
    archive.save_league(base, state)
    g000_w = archive.load_checkpoint(base, "g000")
    before = len(archive.members(base))
    selfplay.run_tick(cfg, base, live)  # main
    rep = selfplay.run_tick(cfg, base, live)  # me's 400th own-game
    assert rep["learner"] == "me"
    assert rep["stalled"] is True
    assert rep["admitted"] is None
    # A stall mints exactly one member: the fresh incarnation (the g000
    # weights it carries were already frozen at the previous incarnation).
    assert len(archive.members(base)) == before + 1
    assert json.loads(
        (base / "learners" / "me" / "weights.json").read_text()) == g000_w
    state = archive.load_league(base)
    assert state["exploiters"]["me"]["window"] == []
    assert state["exploiters"]["me"]["reset_at"] == 400
    assert state["admissions"] == []
    new_inc = state["exploiters"]["me"]["id"]
    assert new_inc != old_inc
    assert {m["id"]: m for m in archive.members(base)}[new_inc] == \
        {"id": new_inc, "role": "me", "parent": "g000"}


def test_role_init_main_resumes_exploiters_from_g000(tmp_path):
    base, g000, source, pool = _league_base(tmp_path)
    cfg = _cfg(tmp_path)
    opt_blob = {"arrays": {}, "params": []}
    archive.save_opt(base, source, opt_blob)
    selfplay.ensure_roles(base, cfg)
    main_w, main_opt = selfplay.load_live(base, "main")
    assert main_w == archive.load_checkpoint(base, source)
    assert main_opt == opt_blob  # banked Adam resumes
    for learner in ("me", "le-a", "le-b"):
        w, opt = selfplay.load_live(base, learner)
        assert w == archive.load_checkpoint(base, "g000")
        assert opt is None  # fresh Adam
    # second start never clobbers training progress.
    marker = {"reshaped": True}
    (base / "learners" / "me" / "weights.json").write_text(json.dumps(marker))
    members_before = len(archive.members(base))
    ids_before = {n: archive.load_league(base)["exploiters"][n]["id"]
                  for n in ("me", "le-a", "le-b")}
    selfplay.ensure_roles(base, cfg)
    assert selfplay.load_live(base, "me")[0] == marker
    # ... nor mints duplicate incarnations: the live ids are stable.
    assert len(archive.members(base)) == members_before
    assert {n: archive.load_league(base)["exploiters"][n]["id"]
            for n in ("me", "le-a", "le-b")} == ids_before


def test_role_init_mints_one_incarnation_per_exploiter(tmp_path):
    base, g000, source, pool = _league_base(tmp_path)
    cfg = _cfg(tmp_path)
    selfplay.ensure_roles(base, cfg)
    state = archive.load_league(base)
    rows = {m["id"]: m for m in archive.members(base)}
    assert state["exploiters"]["me"]["id"] is not None
    assert rows[state["exploiters"]["me"]["id"]]["role"] == "me"
    for name in ("me", "le-a", "le-b"):
        iid = state["exploiters"][name]["id"]
        assert rows[iid]["parent"] == "g000"
        assert archive.load_checkpoint(base, iid) == \
            archive.load_checkpoint(base, "g000")
    assert rows[state["exploiters"]["le-a"]["id"]]["role"] == "le"
    assert rows[state["exploiters"]["le-b"]["id"]]["role"] == "le"


@pytest.mark.slow
def test_smoke_two_real_engine_games(tmp_path):
    """Two scheduler ticks through the real engine (no mocks)."""
    base = tmp_path / "archive"
    archive.init(base)
    real_w = json.loads(
        (ROOT / "bots" / "alphaant" / "weights.json").read_text())
    archive.save_checkpoint(base, real_w, "main", None)  # g000
    source = archive.save_checkpoint(base, real_w, "main", "g000")  # g001
    archive.save_checkpoint(base, real_w, "main", "g000")  # g002 pool
    cfg = selfplay.default_config()
    cfg.update({
        "maps": ["tools/maps/example/tutorial1.map"],
        "turns": 6,
        "seed": 0,
        "lr": 1e-3,
        "epochs": 1,
        "main_source": source,
        "g000": "g000",
        "anchors": [],
        "archive": str(base),
    })
    selfplay.ensure_roles(base, cfg)
    live = selfplay.load_live_all(cfg, base)
    reports = [selfplay.run_tick(cfg, base, live) for _ in range(2)]
    assert [r["learner"] for r in reports] == ["main", "me"]
    for rep in reports:
        assert len(rep["scores"]) == 2
    games = archive.list_games(base)
    assert len(games) == 2  # one canonical row per game
    data = json.loads((base / "matrix.json").read_text())
    assert any(k.startswith("main vs ") for k in data["eval"])
    state = archive.load_league(base)
    assert state["tick"] == 2
