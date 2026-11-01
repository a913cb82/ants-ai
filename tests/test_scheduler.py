import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "ml"))

import archive
import selfplay
import train


def _cfg(tmp_path, **over):
    cfg = selfplay.default_config()
    cfg.update(
        {
            "maps": ["m.map"],
            "turns": 2,
            "seed": 0,
            "lr": 1e-3,
            "epochs": 1,
            "archive": str(tmp_path / "archive"),
        }
    )
    cfg.update(over)
    return cfg


def _setup(tmp_path, monkeypatch, scores=(3, 1), **cfg_over):
    """Trainer ready to tick with a stubbed game (no engine)."""
    base = tmp_path / "archive"
    cfg = _cfg(tmp_path, **cfg_over)
    live = selfplay.ensure(base, cfg)

    def fake_play_one(c, b, weights, map_path):
        tick = c["tick"]
        archive.log_game(
            b,
            ["main", "main"], [scores[0], scores[1]],
            "games/main/logs/0.replay",
            map="m.map",
            game="gid",
            tick=tick,
        )
        return {
            "rows": [
                {"window": [[[0.0] * 9] * 9] * 10, "action": "stay"},
                {"window": [[[0.0] * 9] * 9] * 10, "action": "stay"},
            ],
            "rets": [1.0, 1.0],
            "scores": [scores[0], scores[1]],
            "game": {"score": [scores[0], scores[1]]},
        }

    monkeypatch.setattr(train, "_play_one", fake_play_one)
    return base, cfg, live


def test_tick_plays_mirror_and_banks_batch(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    rep = selfplay.run_tick(cfg, base, live)
    assert rep["tick"] == 0
    assert rep["scores"] == [3, 1]
    assert not rep["update"]  # micro 1/8: banked, no update yet
    games = archive.list_games(base)
    assert len(games) == 1
    assert games[0]["seats"] == ["main", "main"]
    assert games[0]["tick"] == 0
    assert len(live["pending"]) == 2  # both seats train
    bank = selfplay.load_pending(base, "base")
    assert len(bank) == 2  # banked for a restart


def test_update_fires_every_eighth_game(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    updates = [selfplay.run_tick(cfg, base, live)["update"] for _ in range(8)]
    assert updates == [False] * 7 + [True]
    assert live["pending"] == []  # consumed by the update
    assert not selfplay._pending_path(base).exists()  # bank cleared
    assert archive.list_updates(base) != []  # measurements logged
    state = archive.load_state(base)
    assert state["tick"] == 8 and state["micro"] == 8


def test_claim_tick_never_reuses_across_restarts(tmp_path):
    base = tmp_path / "archive"
    cfg = _cfg(tmp_path)
    selfplay.ensure(base, cfg)
    state = archive.load_state(base)
    state["tick"] = 6  # completed through tick 5
    archive.save_state(base, state)
    assert selfplay._claim_tick(base) == 6
    # crash before the tick end: league tick never advances, but the
    # number is spent (persisted at claim). No stripping exists, so
    # reuse would double-log the orphan rows.
    assert selfplay._claim_tick(base) == 7


def test_crashed_tick_rows_and_bank_survive(tmp_path, monkeypatch):
    import torch

    base, cfg, live = _setup(tmp_path, monkeypatch)
    # simulate a tick-6 crash after every effect fired, before tick end:
    archive.log_game(
        base,
        ["main", "main"], [1, 0],
        "games/main/logs/0.replay",
        map="m",
        game="gid-x",
        tick=6,
    )
    state = archive.load_state(base)
    state["tick"] = 6
    state["next_tick"] = 7
    state["micro"] = 1
    archive.save_state(base, state)
    item = (torch.zeros(2), 1, 0.5, [True], 0.1)
    selfplay.bank_pending(base, [item], "base", tick=6)
    # resume = load + schedule. Nothing is stripped, shed, or replayed:
    # rows stay, the bank reloads, the next tick moves on.
    assert len(archive.list_games(base)) == 1
    assert selfplay._claim_tick(base) == 7
    live = selfplay.ensure(base, cfg)
    assert len(live["pending"]) == 1


def test_pending_bank_roundtrip_and_guards(tmp_path):
    import algorithm
    import torch

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


def test_fresh_ensure_mints_random_net_then_resumes(tmp_path):
    base = tmp_path / "archive"
    cfg = _cfg(tmp_path)
    live = selfplay.ensure(base, cfg)
    first = dict(archive.json.loads((base / "live" / "weights.json").read_text()))
    assert first != {}
    # second start never clobbers training progress.
    live["pending"].append("x")
    live2 = selfplay.ensure(base, cfg)
    assert live2["pending"] == []
    state = archive.load_state(base)
    assert state["tick"] == 0 and state["micro"] == 0


def test_shutdown_flag_stops_loop_between_ticks(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    calls = []
    orig = selfplay.run_tick

    def counting(c, b, lv):
        calls.append(1)
        selfplay._SHUTDOWN = True
        return orig(c, b, lv)

    monkeypatch.setattr(selfplay, "run_tick", counting)
    selfplay._SHUTDOWN = False
    try:
        selfplay.run_loop(cfg, base, 10)
    finally:
        selfplay._SHUTDOWN = False
    assert len(calls) == 1  # current tick finished, then stopped
