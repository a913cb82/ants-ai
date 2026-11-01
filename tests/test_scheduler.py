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
    import train as _train

    calls = []
    orig = _train._play_one

    def counting(c, b, w, m):
        calls.append(1)
        selfplay._SHUTDOWN = True
        return orig(c, b, w, m)

    monkeypatch.setattr(_train, "_play_one", counting)
    selfplay._SHUTDOWN = False
    try:
        selfplay.run_loop(cfg, base, 10)
    finally:
        selfplay._SHUTDOWN = False
    assert len(calls) == 1  # current tick finished, then stopped


def _par_setup(tmp_path, monkeypatch, nmaps=3, concurrency=3, ticks=6):
    """Loop harness with a stubbed instant game (no engine)."""
    import threading

    import train as _train

    base = tmp_path / "archive"
    cfg = _cfg(
        tmp_path,
        maps=[f"m{i}.map" for i in range(nmaps)],
        concurrency=concurrency,
        epochs=1,
    )
    live = selfplay.ensure(base, cfg)
    seen = []

    def fake_play_one(c, b, weights, map_path):
        import time as _time

        _time.sleep(0.05)  # let the pool spread work across threads
        tick = c["tick"]
        seen.append((tick, threading.get_ident(), Path(map_path).name))
        archive.log_game(
            b,
            ["main", "main"], [3, 1],
            f"games/main/tick{tick}/logs/0.replay",
            map=Path(map_path).name,
            game=f"gid-{tick}",
            tick=tick,
            t=_time.time(),
        )
        return {
            "rows": [{"window": [[[0.0] * 9] * 9] * 10, "action": "stay"}],
            "rets": [1.0],
            "scores": [3, 1],
        }

    monkeypatch.setattr(_train, "_play_one", fake_play_one)
    return base, cfg, live, seen


def _expected_map(seed, tick, maps):
    import random

    return random.Random(f"{seed}:{tick}").choice(maps)


def test_concurrency_defaults_to_serial():
    assert selfplay.default_config()["concurrency"] == 1
    assert selfplay.parse_args([])["concurrency"] == 1


def test_parallel_ticks_claim_unique_ticks_on_threads(tmp_path, monkeypatch):

    base, cfg, live, seen = _par_setup(tmp_path, monkeypatch)[:4]
    maps = cfg["maps"]
    selfplay.run_loop(cfg, base, ticks=6)
    rows = archive.list_games(base)
    assert len(rows) == 6
    assert sorted(r["tick"] for r in rows) == [0, 1, 2, 3, 4, 5]
    assert len({tid for _, tid, _ in seen}) > 1  # really parallel
    for tick, _, name in seen:
        assert name == Path(_expected_map(0, tick, maps)).name


def test_parallel_completions_fire_update_every_eight(tmp_path, monkeypatch):
    base, cfg, live, seen = _par_setup(
        tmp_path, monkeypatch, concurrency=2, ticks=8)
    cfg["maps"] = ["m0.map"]
    selfplay.run_loop(cfg, base, ticks=8)
    updates = archive.list_updates(base)
    assert len(updates) == 1  # 8 completions, one update
    assert updates[0]["rows"] == 8  # one stubbed row per game
    assert updates[0]["tick"] == 7  # the completing tick names it
    assert selfplay.load_pending(base, "base") == []  # bank cleared
    assert archive.load_state(base)["micro"] == 8


def test_parallel_matches_serial_results(tmp_path, monkeypatch):
    # two independent archives through the same harness shape
    outs = []
    for sub, conc in (("s1", 1), ("s2", 3)):
        d = tmp_path / sub
        d.mkdir()
        base = d / "archive"
        cfg = _cfg(d, maps=["m0.map", "m1.map"], concurrency=conc, epochs=1)
        selfplay.ensure(base, cfg)
        import time as _time

        import train as _train

        seen = []

        def fake_play_one(c, b, weights, map_path, _seen=seen):
            tick = c["tick"]
            _seen.append((tick, Path(map_path).name))
            archive.log_game(
                b, ["main", "main"], [3, 1],
                f"games/main/tick{tick}/logs/0.replay",
                map=Path(map_path).name, game=f"gid-{tick}", tick=tick,
                t=_time.time())
            return {
                "rows": [{"window": [[[0.0] * 9] * 9] * 10, "action": "stay"}],
                "rets": [1.0],
                "scores": [3, 1],
            }

        monkeypatch.setattr(_train, "_play_one", fake_play_one)
        selfplay.run_loop(cfg, base, ticks=4)
        rows = sorted(
            (r["tick"], r["map"], tuple(r["scores"]))
            for r in archive.list_games(base))
        outs.append((rows, len(selfplay.load_pending(base, "base"))))
    assert outs[0] == outs[1]  # same games, same banked rows
