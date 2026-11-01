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
        "concurrency": 1,
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
        (c, b, chal_id, field, weights, role, map_path) = args[:7]
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
    import algorithm

    live_w = algorithm.policy_weights(live["le-a"]["policy"])
    stored = json.loads(
        (base / "learners" / "le-a" / "weights.json").read_text())
    assert stored != {} and set(stored) == set(live_w)  # re-seeded fresh
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


def test_role_init_main_resumes_exploiters_fresh(tmp_path):
    import algorithm

    base, g000, source, pool = _league_base(tmp_path)
    cfg = _cfg(tmp_path)
    opt_blob = {"arrays": {}, "params": []}
    archive.save_opt(base, source, opt_blob)
    selfplay.ensure_roles(base, cfg)
    main_w, main_opt = selfplay.load_live(base, "main")
    assert main_w == archive.load_checkpoint(base, source)
    assert main_opt == opt_blob  # banked Adam resumes
    fresh_keys = set(algorithm.policy_weights(
        algorithm.new_policy(None, "base")))
    for learner in ("me", "le-a", "le-b"):
        w, opt = selfplay.load_live(base, learner)
        assert set(w) == fresh_keys and w != {}  # own random start
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
        "concurrency": 1,
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
                # (live, live_main, snapshots, records, rng): the ME
                # takes the live main, snapshots are the fallback pool.
                assert args[1] == "main"
                seen[policy] = list(args[2])
                return args[2][0] if args[2] else args[1]
            # main: (live, live_main, candidates, ...); le: (live,
            # candidates, records, rng). Both record the frozen pool.
            idx = 2 if policy == "main" else 1
            seen[policy] = list(args[idx])
            return args[idx][0]
        return _fake

    monkeypatch.setattr(pfsp, "main_sample", fake("main"))
    monkeypatch.setattr(pfsp, "me_sample", fake("me"))
    monkeypatch.setattr(pfsp, "le_sample", fake("le"))
    state = {"main_id": source,
             "main_snapshots": [source],
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


def test_pending_bank_roundtrip_and_guards(tmp_path):
    import torch

    import algorithm

    p = tmp_path / "pending.pt"
    items = [(torch.zeros(2), 1, 0.5, [True, False], 0.1)]
    algorithm.dump_pending(p, items, "base")
    got = algorithm.read_pending(p, "base")
    assert len(got) == 1 and torch.equal(got[0][0], items[0][0])
    algorithm.dump_pending(p, items, "base", tick=7)
    assert algorithm.pending_tick(p) == 7  # bank names its tick
    assert algorithm.read_pending(p, "deep") == []  # arch switch: clean
    assert algorithm.read_pending(tmp_path / "missing.pt", "base") == []
    (tmp_path / "junk.pt").write_text("junk")
    assert algorithm.read_pending(tmp_path / "junk.pt", "base") == []


def test_run_tick_banks_pending_and_update_clears(tmp_path, monkeypatch):
    import torch

    import algorithm

    base, cfg, live = _setup(tmp_path, monkeypatch)
    item = (torch.zeros(3), 1, 0.5, [True], 0.1)
    monkeypatch.setattr(algorithm, "collect", lambda *a, **k: [item])
    seen = []
    monkeypatch.setattr(train, "ppo_update",
                        lambda *a, **k: seen.append(a[2]) or {})
    bank = selfplay._pending_path(base, "main")
    selfplay.run_tick(cfg, base, live)  # main micro 1: no update
    assert bank.exists()  # banked, not stranded in memory
    live2 = selfplay.load_live_all(cfg, base)
    assert len(live2["main"]["pending"]) == 1  # resume picks it up
    for _ in range(28):
        selfplay.run_tick(cfg, base, live)  # main reaches micro 8
    assert len(seen[-1]) == 8  # all 8 own-games trained, none orphaned
    assert not bank.exists()  # consumed: bank cleared on update


def test_reset_learner_drops_banked_batch(tmp_path, monkeypatch):
    import torch

    import algorithm

    base, cfg, live = _setup(tmp_path, monkeypatch)
    selfplay.bank_pending(base, "me", [(torch.zeros(1), 0, 0.0, [], 0.0)],
                          "base")
    assert selfplay._pending_path(base, "me").exists()
    selfplay.reset_learner(base, live, "me", "base")
    assert live["me"]["pending"] == []
    assert not selfplay._pending_path(base, "me").exists()


def test_shutdown_flag_stops_loop_between_ticks(tmp_path, monkeypatch):
    base, _, _, _ = _league_base(tmp_path)
    cfg = _cfg(tmp_path, ticks=100)
    calls = []

    def fake_tick(cfg, base, live):
        calls.append(1)
        if len(calls) == 3:
            selfplay._SHUTDOWN = True
        return {}

    monkeypatch.setattr(selfplay, "run_tick", fake_tick)
    try:
        reports = selfplay.run_loop(cfg, base)
    finally:
        selfplay._SHUTDOWN = False
    assert len(reports) == 3  # current tick finished, then stopped


def test_shutdown_flag_preset_runs_zero_ticks(tmp_path):
    base, _, _, _ = _league_base(tmp_path)
    cfg = _cfg(tmp_path, ticks=100)
    selfplay._SHUTDOWN = True
    try:
        assert selfplay.run_loop(cfg, base) == []
    finally:
        selfplay._SHUTDOWN = False


def test_concurrent_ticks_split_learners(tmp_path, monkeypatch):
    import train

    base, _, _, _ = _league_base(tmp_path)
    cfg = _cfg(tmp_path, concurrency=2)
    selfplay.ensure_roles(base, cfg)
    seen = []
    guard = __import__("threading").Lock()

    def fake_tick(cfg, base, live, rng=None, learner=None):
        __import__("time").sleep(0.005)  # force thread interleaving
        with guard:
            seen.append(learner)
        # a real tick advances its learner's game count: the dispatcher
        # steers by it, so the fake must too (else every tie repeats).
        with archive.league_lock():
            st = archive.load_league(base) or {}
            if learner == "main":
                st["main_games"] = st.get("main_games", 0) + 1
            else:
                exp = st.setdefault("exploiters", {}).setdefault(
                    learner, {})
                exp["games"] = exp.get("games", 0) + 1
            archive.save_league(base, st)
        return {"learner": learner}

    monkeypatch.setattr(selfplay, "run_tick", fake_tick)
    live = selfplay.load_live_all(cfg, base)
    reports = selfplay.run_loop(cfg, base, ticks=8)
    assert len(reports) == 8  # every claimed tick ran exactly once
    assert set(seen) == {"main", "me", "le-a", "le-b"}  # all types fed
    assert not list(base.glob("tick.*.marker"))  # markers die at tick end


def test_dispatch_feeds_most_starved_idle_learner():
    state = {"main_games": 5, "exploiters": {
        "me": {"games": 5}, "le-a": {"games": 2}, "le-b": {"games": 5}}}
    assert selfplay._dispatch_learner(state, set()) == "le-a"
    assert selfplay._dispatch_learner(state, {"le-a"}) == "main"
    assert selfplay._dispatch_learner(
        state, {"main", "me", "le-a", "le-b"}) is None


def test_pool_worker_drains_through_dispatcher(tmp_path):
    base, _, _, _ = _league_base(tmp_path)
    cfg = _cfg(tmp_path)
    selfplay.ensure_roles(base, cfg)

    seen = []
    guard = __import__("threading").Lock()

    def fake_tick(cfg, base, live, rng=None, learner=None):
        seen.append(learner)
        return {}

    real = selfplay.run_tick
    selfplay.run_tick = fake_tick
    in_flight = set()
    try:
        # static league: every dispatch ties at zero, order[0] wins.
        selfplay._pool_worker(cfg, base, {}, [3], [], guard, in_flight)
    finally:
        selfplay.run_tick = real
    assert seen == ["main"] * 3
    assert in_flight == set()  # released, never wedged


def test_claim_tick_never_reuses_across_restarts(tmp_path):
    base, _, _, _ = _league_base(tmp_path)
    cfg = _cfg(tmp_path)
    selfplay.ensure_roles(base, cfg)
    st = archive.load_league(base)
    st["tick"] = 6  # completed through tick 5
    archive.save_league(base, st)
    assert selfplay._claim_tick(base) == 6
    # crash before the tick end: league tick never advances, but the
    # number is spent (persisted at claim). No stripping exists, so
    # reuse would double-log the orphan rows.
    assert selfplay._claim_tick(base) == 7


def test_crashed_tick_rows_and_bank_survive(tmp_path):
    import torch

    base, _, _, _ = _league_base(tmp_path)
    cfg = _cfg(tmp_path)
    selfplay.ensure_roles(base, cfg)
    # simulate a tick-6 crash after every effect fired, before tick end:
    archive.log_game(base, "main", "eval", "main", "g000", 1, 0,
                     "games/x/logs/0.replay", map="m", game="gid-x",
                     tick=6)
    st = archive.load_league(base)
    st["tick"] = 6
    st["next_tick"] = 7
    st.setdefault("micro", {})["main"] = 1
    archive.save_league(base, st)
    item = (torch.zeros(2), 1, 0.5, [True], 0.1)
    selfplay.bank_pending(base, "main", [item], "base", tick=6)
    # resume = load + schedule. Nothing is stripped, shed, or replayed:
    # rows stay, the bank reloads, the next tick moves on.
    assert len(archive.list_games(base)) == 1
    assert selfplay._claim_tick(base) == 7
    live = selfplay.load_live_all(cfg, base)
    assert len(live["main"]["pending"]) == 1


def test_reset_seeds_fresh_random_not_g000(tmp_path, monkeypatch):
    import algorithm

    base, cfg, live = _setup(tmp_path, monkeypatch)
    ref = algorithm.policy_weights(algorithm.new_policy(None, "base"))
    selfplay.reset_learner(base, live, "me", "base")
    first, _ = selfplay.load_live(base, "me")
    assert set(first) == set(ref) and first != {}
    assert any(first[k] != ref[k] for k in first)  # not verbatim
    selfplay.reset_learner(base, live, "me", "base")
    second, _ = selfplay.load_live(base, "me")
    assert any(first[k] != second[k] for k in first)  # each init differs
