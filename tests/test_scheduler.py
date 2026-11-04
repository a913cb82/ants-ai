import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "ml"))

import archive
import selfplay
import train


def _maps(tmp_path, *names, players=2):
    """Real map files for the dispatcher: seats come from headers."""
    out = []
    for name in names:
        path = tmp_path / name
        path.write_text(f"players {players}\nrows 3\ncols 3\n" + "...\n" * 3)
        out.append(str(path))
    return out


def _cfg(tmp_path, **over):
    cfg = selfplay.default_config()
    cfg.update(
        {
            "maps": _maps(tmp_path, "m.map"),
            "turns": 2,
            "seed": 0,
            "lr": 1e-3,
            "epochs": 1,
            "archive": str(tmp_path / "archive"),
        }
    )
    cfg.update(over)
    return cfg


def _setup(tmp_path, monkeypatch, scores=(3, 1), rets=(1.0, 1.0), scoreless=False, **cfg_over):
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
                {"window": [[[0.0] * 9] * 9] * 13, "action": "stay"},
                {"window": [[[0.0] * 9] * 9] * 13, "action": "stay"},
            ],
            "rets": list(rets),
            "scores": [scores[0], scores[1]],
            "game": {"score": [scores[0], scores[1]]},
            "scoreless": scoreless,
        }

    monkeypatch.setattr(train, "_play_one", fake_play_one)
    return base, cfg, live


def test_tick_plays_mirror_and_banks_batch(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    rep = selfplay.run_tick(cfg, base, live)
    assert rep["tick"] == 0
    assert rep["scores"] == [3, 1]
    assert not rep["update"]  # micro 1/16: banked, no update yet
    games = archive.list_games(base)
    assert len(games) == 1
    assert games[0]["seats"] == ["main", "main"]
    assert games[0]["tick"] == 0
    assert len(live["pending"]) == 2  # both seats train
    bank = selfplay.load_pending(base, "base")
    assert len(bank) == 2  # banked for a restart


def test_scoreless_tick_logs_history_but_banks_nothing(tmp_path, monkeypatch):
    base, cfg, live = _setup(
        tmp_path, monkeypatch, rets=[0.0, 0.0], scoreless=True
    )
    rep = selfplay.run_tick(cfg, base, live)
    assert rep["tick"] == 0 and not rep["update"]
    assert len(archive.list_games(base)) == 1  # draws stay visible
    assert live["pending"] == []  # nothing to train
    assert selfplay.load_pending(base, "base") == []  # nothing banked
    state = archive.load_state(base)
    assert state["tick"] == 1 and state["micro"] == 0  # cadence untouched


def test_cadence_counts_scoring_games_only(tmp_path, monkeypatch):
    base, cfg, live = _setup(
        tmp_path, monkeypatch, rets=[0.0, 0.0], scoreless=True
    )
    for _ in range(15):
        assert not selfplay.run_tick(cfg, base, live)["update"]
    assert archive.load_state(base)["micro"] == 0
    assert len(archive.list_games(base)) == 15


def test_update_fires_every_sixteenth_game(tmp_path, monkeypatch):
    base, cfg, live = _setup(tmp_path, monkeypatch)
    updates = [selfplay.run_tick(cfg, base, live)["update"] for _ in range(16)]
    assert updates == [False] * 15 + [True]
    assert live["pending"] == []  # consumed by the update
    assert not selfplay._pending_path(base).exists()  # bank cleared
    assert archive.list_updates(base) != []  # measurements logged
    state = archive.load_state(base)
    assert state["tick"] == 16 and state["micro"] == 16


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
        maps=_maps(tmp_path, *[f"m{i}.map" for i in range(nmaps)]),
        concurrency=concurrency,
        epochs=1,
    )
    live = selfplay.ensure(base, cfg)
    seen = []

    def fake_play_one(c, b, weights, map_path):
        import time as _time

        _time.sleep(0.05)  # let the pool spread work across threads
        tick = c["tick"]
        seen.append(
            (tick, threading.get_ident(),
             Path(map_path).name, _time.perf_counter())
        )
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
            "rows": [{"window": [[[0.0] * 9] * 9] * 13, "action": "stay"}],
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
    assert len({tid for _, tid, _, _ in seen}) > 1  # really parallel
    for tick, _, name, _ in seen:
        assert name == Path(_expected_map(0, tick, maps)).name


def test_parallel_completions_fire_update_every_sixteen(tmp_path, monkeypatch):
    base, cfg, live, seen = _par_setup(
        tmp_path, monkeypatch, concurrency=2, ticks=16)
    cfg["maps"] = _maps(tmp_path, "m0.map")
    selfplay.run_loop(cfg, base, ticks=16)
    updates = archive.list_updates(base)
    assert len(updates) == 1  # 16 completions, one update
    assert updates[0]["rows"] == 16  # one stubbed row per game
    assert updates[0]["tick"] == 15  # the completing tick names it
    assert selfplay.load_pending(base, "base") == []  # bank cleared
    assert archive.load_state(base)["micro"] == 16


def test_parallel_matches_serial_results(tmp_path, monkeypatch):
    # two independent archives through the same harness shape
    outs = []
    for sub, conc in (("s1", 1), ("s2", 3)):
        d = tmp_path / sub
        d.mkdir()
        base = d / "archive"
        cfg = _cfg(d, maps=_maps(d, "m0.map", "m1.map"),
                     concurrency=conc, epochs=1)
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
                "rows": [{"window": [[[0.0] * 9] * 9] * 13, "action": "stay"}],
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


def test_update_log_carries_wall_seconds(tmp_path, monkeypatch):
    base, cfg, live, seen = _par_setup(
        tmp_path, monkeypatch, concurrency=1, ticks=16)
    selfplay.run_loop(cfg, base, ticks=16)
    updates = archive.list_updates(base)
    assert len(updates) == 1
    assert isinstance(updates[0]["update_seconds"], float)
    assert updates[0]["update_seconds"] >= 0.0


def _wrap_ppo(monkeypatch, extra_sleep):
    """Real PPO slowed down, with start/end timestamps recorded."""
    import time as _time

    import train as _train

    orig = _train.ppo_update
    marks = {}

    def slow(policy, opt, batch, cfg):
        marks["start"] = _time.perf_counter()
        _time.sleep(extra_sleep)
        try:
            return orig(policy, opt, batch, cfg)
        finally:
            marks["end"] = _time.perf_counter()

    monkeypatch.setattr(_train, "ppo_update", slow)
    return marks


def test_bg_update_overlaps_games(tmp_path, monkeypatch):
    base, cfg, live, seen = _par_setup(
        tmp_path, monkeypatch, concurrency=2, ticks=20)
    starts = {}
    marks = _wrap_ppo(monkeypatch, 1.0)
    selfplay.run_loop(cfg, base, ticks=20)
    for tick, _, _, at in seen:
        starts[tick] = at
    late = [starts[t] for t in range(16, 20)]
    assert late and max(late) < marks["end"]  # batch 2 played mid-update
    assert len(archive.list_updates(base)) == 1


def test_learner_backpressure_waits_not_drops(tmp_path, monkeypatch):
    base, cfg, live, seen = _par_setup(
        tmp_path, monkeypatch, concurrency=4, ticks=33)
    _wrap_ppo(monkeypatch, 2.0)  # learner slower than 16 instant games
    selfplay.run_loop(cfg, base, ticks=33)
    updates = archive.list_updates(base)
    assert len(updates) == 2  # second boundary waited, nothing dropped
    assert [u["rows"] for u in updates] == [16, 16]
    assert archive.load_state(base)["micro"] == 33
    assert len(selfplay.load_pending(base, "base")) == 1  # tick 32 banks


def test_second_batch_trains_on_pre_update_weights(tmp_path, monkeypatch):
    import json as _json

    base, cfg, live, seen = _par_setup(
        tmp_path, monkeypatch, concurrency=2, ticks=33)
    sums = {}
    import train as _train

    orig_play = _train._play_one

    def checksummed(c, b, weights, map_path):
        sums[c["tick"]] = _json.dumps(weights, sort_keys=True)
        return orig_play(c, b, weights, map_path)

    monkeypatch.setattr(_train, "_play_one", checksummed)
    _wrap_ppo(monkeypatch, 1.0)
    selfplay.run_loop(cfg, base, ticks=33)
    first = sums[0]
    assert all(sums[t] == first for t in range(16, 32))  # at most 1 stale
    assert (
        _json.dumps(selfplay.load_live(base)[0], sort_keys=True) != first
    )  # both updates landed


def test_bank_shards_per_tick_and_drop_consumed(tmp_path):
    import torch

    def items(v):
        return [(torch.zeros(2), 1, v, [True, False], 0.1)]

    base = tmp_path / "archive"
    selfplay.bank_pending(base, items(0.5), "base", tick=3)
    selfplay.bank_pending(base, items(1.5), "base", tick=7)
    shards = sorted(p.name for p in selfplay._pending_path(base).glob("*.pt"))
    assert shards == ["tick3.pt", "tick7.pt"]  # one file per tick, no whole-list rewrite
    got = selfplay.load_pending(base, "base")
    assert [it[2] for it in got] == [0.5, 1.5]  # completion order kept
    selfplay._drop_banked(base, [3])
    assert [p.name for p in selfplay._pending_path(base).glob("*.pt")] == ["tick7.pt"]
    assert [it[2] for it in selfplay.load_pending(base, "base")] == [1.5]


def test_load_pending_reads_legacy_bank_file(tmp_path):
    import algorithm
    import torch

    base = tmp_path / "archive"
    legacy = base / "live" / "pending.pt"
    items = [(torch.zeros(2), 1, 0.5, [True, False], 0.1)]
    algorithm.dump_pending(legacy, items, "base")
    selfplay.bank_pending(base, items, "base", tick=9)
    got = selfplay.load_pending(base, "base")
    assert len(got) == 2  # legacy rows first, then shards


def test_bg_start_trains_capped_oldest_prefix(tmp_path, monkeypatch):
    import train as _train

    import selfplay

    base = tmp_path / "archive"
    cfg = _cfg(tmp_path)
    live = selfplay.ensure(base, cfg)
    seen = {}

    def fake_ppo(policy, opt, batch, cfg):
        seen["rows"] = len(batch)
        return {
            "rows": len(batch),
            "mean_return": 0.0,
            "explained_var": 0.0,
            "losses": [0.0],
            "entropies": [0.0],
            "kl": [0.0],
            "clipfrac": [0.0],
            "pg_loss": 0.0,
            "v_loss": 0.0,
        }

    monkeypatch.setattr(_train, "ppo_update", fake_ppo)
    row = ([[0.0]], 0, 1.0, [True] * 5, 0.0)
    live["pending"] = [row] * 70000
    live["banked"] = [(100, 40000), (101, 30000)]
    selfplay._bg_start(cfg, live, 101)
    assert seen["rows"] == 40000  # oldest whole games up to the cap
    assert live["banked"] == [(101, 30000)]  # remainder stays banked
    assert selfplay._bg_swap(cfg, base, live, block=True) is True
    assert len(live["pending"]) == 30000  # consumed prefix dropped
    import archive

    (upd,) = archive.list_updates(base)
    assert upd["rows"] == 40000


def test_backlogged_loop_drains_and_completes(tmp_path, monkeypatch):
    import archive
    import train as _train

    import selfplay

    base = tmp_path / "archive"
    cfg = _cfg(
        tmp_path,
        maps=_maps(tmp_path, "m0.map"),
        concurrency=1,
        epochs=1,
        pending_cap_rows=5,
    )
    live = selfplay.ensure(base, cfg)

    def fake_play_one(c, b, weights, map_path):
        tick = c["tick"]
        archive.log_game(
            b, ["main", "main"], [3, 1],
            f"games/main/tick{tick}/logs/0.replay",
            map="m0.map", game=f"gid-{tick}", tick=tick,
        )
        return {
            "rows": [{"window": [[[0.0] * 9] * 9] * 13, "action": "stay"}] * 2,
            "rets": [1.0, 1.0],
            "scores": [3, 1],
        }

    monkeypatch.setattr(_train, "_play_one", fake_play_one)
    selfplay.run_loop(cfg, base, ticks=4)
    assert len(archive.list_games(base)) == 4  # stalled, drained, finished
    assert len(archive.list_updates(base)) >= 1  # forced drain landed
