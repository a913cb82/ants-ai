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
        (c, b, chal_id, field, weights, i, role, map_path) = args[:8]
        return {"rows": [], "rets": [], "scores": [scores[0], scores[1]]}

    monkeypatch.setattr(train, "_play_one", fake_play_one)
    return base, cfg, live


def test_scheduler_constants_match_plan():
    assert selfplay.MICRO_BATCH == 8
    assert selfplay.SNAPSHOT_EVERY == 80
    assert selfplay.ADMISSION_RATE == 0.6
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


def test_snapshot_cadence_freezes_main_only(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(selfplay, "SNAPSHOT_EVERY", 2)
    before = len(archive.members(base))
    for _ in range(16):  # main reaches its 4th own-game
        selfplay.run_tick(cfg, base, live)
    members = archive.members(base)
    # one snapshot per main cycle, none for exploiters (they enter the
    # pool only by admission).
    assert [m["id"] for m in members[before:]] == ["main0", "main1"]
    assert [m["role"] for m in members[before:]] == \
        ["main-snapshot", "main-snapshot"]
    state = archive.load_league(base)
    assert state["main_snapshots"][-1] == "main1"
    assert state["main_id"] == "main1"
    # live slots never mint: still bare, still the same rows.
    assert state["exploiters"]["me"]["id"] == "me"


def test_admission_trigger_freezes_family_id(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch, scores=(5, 1))
    state = archive.load_league(base)
    exp = state["exploiters"]["le-a"]
    assert exp["id"] == "le-a"  # bare slot from the start
    exp.update({"games": 40, "window": [1.0] * 40})
    archive.save_league(base, state)
    g000_w = archive.load_checkpoint(base, "g000")
    before = len(archive.members(base))
    # advance the scheduler to le-a (main, me first).
    selfplay.run_tick(cfg, base, live)
    selfplay.run_tick(cfg, base, live)
    rep = selfplay.run_tick(cfg, base, live)
    assert rep["learner"] == "le-a"
    assert rep["admitted"] is not None
    assert rep["admitted"]["id"] == "le-a0"  # 0-based family id
    assert rep["snapshot"] is None  # the freeze is the record
    members = archive.members(base)
    assert len(members) == before + 1  # only the admitted copy, no mint
    assert members[-1] == {"id": "le-a0", "role": "admitted",
                           "parent": "le-a"}  # seeds from slot peak
    assert archive.load_checkpoint(base, "le-a0") is not None
    assert json.loads(
        (base / "learners" / "le-a" / "weights.json").read_text()) == g000_w
    assert not (base / "learners" / "le-a" / "opt.json").exists()
    state = archive.load_league(base)
    assert state["exploiters"]["le-a"]["window"] == []
    assert state["exploiters"]["le-a"]["id"] == "le-a"  # stays bare
    assert state["admissions"][-1]["id"] == "le-a0"
    assert state["resets"][-1]["slot"] == "le-a"  # reset logged


def test_no_reset_after_drought(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch, scores=(0, 5))
    state = archive.load_league(base)
    exp = state["exploiters"]["me"]
    assert exp["id"] == "me"  # bare slot from the start
    exp.update({"games": 399, "window": [0.0] * 40})
    archive.save_league(base, state)
    before = len(archive.members(base))
    selfplay.run_tick(cfg, base, live)  # main
    rep = selfplay.run_tick(cfg, base, live)  # me's 400th own-game
    assert rep["learner"] == "me"
    assert rep["admitted"] is None
    assert "stalled" not in rep  # the stall rule is gone
    # A drought mints nothing and clears nothing: same bare id, same
    # row, rolling window, one more game trained.
    assert len(archive.members(base)) == before
    state = archive.load_league(base)
    assert state["exploiters"]["me"]["window"] == [0.0] * 40
    assert state["exploiters"]["me"]["games"] == 400
    assert state["admissions"] == []
    assert state["exploiters"]["me"]["id"] == "me"  # id unchanged
    assert state.get("resets", []) == []  # nothing logged


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
    # ... nor touches members: bare live ids need no minting.
    assert len(archive.members(base)) == members_before
    assert {n: archive.load_league(base)["exploiters"][n]["id"]
            for n in ("me", "le-a", "le-b")} == ids_before


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


def test_select_opponent_excludes_live_ids(tmp_path, monkeypatch):
    import random

    import pfsp

    base, g000, source, pool = _league_base(tmp_path)
    live_rows = [
        {"id": "main", "role": "main", "parent": source},
        {"id": "me-1", "role": "me", "parent": g000},
        {"id": "lea-1", "role": "le", "parent": g000},
        {"id": "leb-1", "role": "le", "parent": g000},
    ]
    with open(base / "manifest.jsonl", "a") as f:
        for r in live_rows:
            f.write(json.dumps(r) + "\n")
    seen = {}

    def fake(policy):
        def _fake(*args, **kwargs):
            if policy == "me":
                # ME takes only the main id now: no candidate list.
                seen[policy] = list(args)
                return args[0]
            seen[policy] = list(args[1])
            return args[1][0]
        return _fake

    monkeypatch.setattr(pfsp, "main_sample", fake("main"))
    monkeypatch.setattr(pfsp, "me_sample", fake("me"))
    monkeypatch.setattr(pfsp, "le_sample", fake("le"))
    state = {"main_id": source,
             "exploiters": {"me": {"id": "me-1"},
                              "le-a": {"id": "lea-1"},
                              "le-b": {"id": "leb-1"}}}
    rng = random.Random(0)
    train.select_opponent(base, "main", state, {}, rng)
    train.select_opponent(base, "me", state, {}, rng)
    train.select_opponent(base, "le-a", state, {}, rng)
    assert set(seen) == {"main", "me", "le"}
    for cands in seen.values():
        assert "main" not in cands
        assert "me-1" not in cands
        assert "lea-1" not in cands
        assert "leb-1" not in cands
        assert source in cands  # frozen main snapshot stays
