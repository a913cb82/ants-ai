"""Mirror loop plumbing: game_if, archive, snapshot, dashboard, dispatch.

Split from the test_alphastarzero monolith; no behavior change.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "bots" / "alphaant" / "train"))

import pytest

import features

_C = features.INPUT_CHANNELS
_S = 2 * features.DEFAULT_RADIUS + 1


class FakeAnts:
    """Minimal stub of the Ants API used by features/model."""

    def __init__(self):
        self.rows = 10
        self.cols = 10
        self._water = {(2, 2)}
        self._food = [(5, 5)]
        self._mine = [(4, 4)]
        self._enemy = [((4, 6), 1)]
        self._my_hills = [(3, 3)]
        self._enemy_hills = [((6, 6), 1)]
        self.viewradius2 = 77

    def destination(self, loc, direction):
        d = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}[direction]
        return ((loc[0] + d[0]) % self.rows, (loc[1] + d[1]) % self.cols)

    def passable(self, loc):
        return loc not in self._water

    def distance(self, a, b):
        dr = min(abs(a[0] - b[0]), self.rows - abs(a[0] - b[0]))
        dc = min(abs(a[1] - b[1]), self.cols - abs(a[1] - b[1]))
        return dr + dc

    def food(self):
        return list(self._food)

    def my_ants(self):
        return list(self._mine)

    def enemy_ants(self):
        return list(self._enemy)

    def my_hills(self):
        return list(self._my_hills)

    def enemy_hills(self):
        return list(self._enemy_hills)




@pytest.mark.slow
def _tmp_2p_map(tmp_path, name="e.map"):
    p = tmp_path / name
    p.write_text("rows 16\ncols 24\nplayers 2\n" + "m " + "." * 24 + "\n")
    return str(p)



def _tmp_3p_map(tmp_path, name="e3.map"):
    p = tmp_path / name
    p.write_text("rows 16\ncols 24\nplayers 3\n" + "m " + "." * 24 + "\n")
    return str(p)



def _big_game(monkeypatch, tmp_path, n_rows=5000):
    """Stub engine game: n_rows priced rows, returns stay attached."""
    import game_if
    import rewards as _rewards
    import train as _train

    rec = {
        "turn": 2,
        "loc": [1, 1],
        "dest": [1, 1],
        "action": "stay",
        "window": [[[0.0] * 9] * 9] * 10,
    }
    land = ["." * 8 for _ in range(8)]
    game = {
        "score": [1, 2],
        "game_length": 10,
        "replaydata": {
            "map": {"rows": 8, "cols": 8, "data": land},
            "viewradius2": 77,
            "attackradius2": 5,
            "food": [],
            "ants": [[1, 1, 1, 10, 0, "-" * 9], [2, 2, 1, 10, 1, "-" * 9]],
            "hills": [],
        },
    }
    mapp = tmp_path / "m.map"
    mapp.write_text("rows 8\ncols 8\nplayers 2\n" + "m " + "." * 8 + "\n")

    def fake_play(*a, **k):
        return {"game": game, "records": [[dict(rec) for _ in range(n_rows)]] * 2}

    monkeypatch.setattr(game_if, "play", fake_play)
    monkeypatch.setattr(
        _rewards, "compute_returns", lambda g, s, r, sc: [float(i) for i in range(len(r))]
    )
    cfg = {"tick": 4, "turns": 10, "temperature": 1.0, "seed": 7}
    return _train._play_one(cfg, tmp_path, {}, str(mapp))



def _trace_game():
    import rewards  # noqa: F401  (keeps the one-diet import idiom)

    game = _game()
    rows = [".........." for _ in range(10)]
    rows[5] = "......%..."
    game["replaydata"]["map"] = {"rows": 10, "cols": 10, "data": rows}
    game["replaydata"]["ants"] = [[5, 5, 1, 6, 0, "----"]]
    game["playerturns"] = [3, 3]
    return game



def _trace_game_status(status):
    game = _trace_game()
    game["status"] = status
    return game



def _timeout_game():
    game = _trace_game()
    game["status"] = ["timeout", "timeout"]
    return game



def _game(**kw):
    """Minimal 0.replay-shaped game: 10x10, 2 players, 10 turns."""
    base = {
        "score": [0, 0],
        "status": ["survived", "survived"],
        "length": 10,
        "replaydata": {
            "map": {"rows": 10, "cols": 10},
            "viewradius2": 77,
            "attackradius2": 5,
            "food": [],
            "ants": [],
            "hills": [],
        },
    }
    base.update(kw)
    return base



def test_game_if_mirror_plays_and_prices(tmp_path):
    import game_if
    import rewards

    out = game_if.play(
        ROOT,
        sys.executable,
        [
            json.loads((ROOT / "bots" / "alphaant" / "weights.json").read_text()),
            json.loads((ROOT / "bots" / "alphaant" / "weights.json").read_text()),
        ],
        game_if.GameConfig(
            map="tools/maps/example/tutorial1.map",
            turns=10,
            temperature=1.0,
            player_seed=0,
            engine_seed=0,
        ),
        tmp_path / "g0",
    )
    assert out["game"]["game_length"] == 10
    assert out["records"][0] and out["records"][1]
    r = rewards.compute_returns(out["game"], 0, out["records"][0])
    assert len(r) == len(out["records"][0])




def test_cli_defaults_match_default_config():
    import selfplay

    cfg = selfplay.parse_args([])
    assert cfg == selfplay.default_config()




def test_cli_overrides():
    import selfplay

    cfg = selfplay.parse_args(
        ["--ticks", "7", "--turns", "20", "--maps", "tools/maps/example/tutorial1.map"]
    )
    assert cfg["ticks"] == 7
    assert cfg["turns"] == 20
    # No separate exam: custom maps are used directly, nothing held out.
    assert cfg["maps"] == ["tools/maps/example/tutorial1.map"]




def test_game_if_cleanup_keeps_replay_drops_sides(tmp_path):
    import game_if

    outdir = tmp_path / "g0"
    (outdir / "side_a" / "records").mkdir(parents=True)
    (outdir / "side_b").mkdir(parents=True)
    (outdir / "logs").mkdir(parents=True)
    (outdir / "logs" / "0.replay").write_text("{}")
    game_if.cleanup(outdir)
    assert (outdir / "logs" / "0.replay").exists()
    assert not (outdir / "side_a").exists()
    assert not (outdir / "side_b").exists()




def test_games_index_roundtrip_and_filter(tmp_path):
    import archive

    base = tmp_path / "archive"
    archive.log_game(base, ["main", "main"], [3, 1], "games/g001/t0/logs/0.replay")
    archive.log_game(base, ["main", "main"], [2, 2], "games/g001/e0/logs/0.replay")
    all_games = archive.list_games(base)
    assert len(all_games) == 2
    assert [r["replay"] for r in all_games] == [
        "games/g001/e0/logs/0.replay",
        "games/g001/t0/logs/0.replay",
    ]




def test_log_game_records_map_name(tmp_path):
    import archive

    base = tmp_path / "archive"
    archive.log_game(
        base, ["main", "main"], [3, 1], "games/g001/t0/logs/0.replay", map="rung2c_gap.map"
    )
    archive.log_game(base, ["main", "main"], [2, 2], "games/g001/e0/logs/0.replay")
    rows = {r["replay"]: r for r in archive.list_games(base)}
    assert rows["games/g001/t0/logs/0.replay"]["map"] == "rung2c_gap.map"
    assert rows["games/g001/e0/logs/0.replay"]["map"] is None




def test_snapshot_empty_and_populated(tmp_path):
    import archive
    import dashboard

    base = tmp_path / "archive"
    snap = dashboard.snapshot(base)
    assert snap["games"] == [] and snap["game_total"] == 0
    assert snap["behavior"] == [
        {
            "id": "main",
            "food": None,
            "kills": None,
            "army_pct": None,
            "length": None,
            "n": 0,
            "spark": {"food": [], "kills": [], "army": [], "length": []},
        }
    ]
    assert snap["alerts"] == [{"level": "ok", "msg": "all clear", "tick": 0}]
    archive.save_state(base, {"tick": 1, "next_tick": 1, "micro": 0})
    archive.log_game(
        base,
        ["main", "main"], [3, 1],
        "games/g000/e0/logs/0.replay",
        game="gid-0",
        tick=0,
        food=[2, 1],
        kills=[1, 0],
        army=[5, 4],
        length=120,
    )
    snap = dashboard.snapshot(base)
    assert snap["game_total"] == 1
    assert snap["games"][0]["replay"].endswith("0.replay")
    assert snap["h0"]["games"] == 1




def test_snapshot_games_carry_dual_time(tmp_path):
    import archive
    import dashboard

    base = tmp_path / "archive"
    archive.log_game(
        base, ["main", "main"], [3, 1], "games/g0/logs/0.replay", game="g#0", tick=7
    )
    archive.log_game(
        base, ["main", "main"], [0, 5], "games/g1/logs/0.replay", game="g#1", tick=9
    )
    snap = dashboard.snapshot(base)
    assert [g["tick"] for g in snap["games"]] == [9, 7]  # newest first
    assert all(
        set(g)
        == {"tick", "learner", "map", "seats", "scores", "stats",
            "length", "trace_miss", "timeouts", "breaks",
            "result", "replay"}
        for g in snap["games"]
    )




def test_snapshot_h0_tracks_scheduler_state(tmp_path):
    import archive
    import dashboard

    base = tmp_path / "archive"
    archive.save_state(base, {"tick": 5, "next_tick": 5, "micro": 3})
    archive.log_update(
        base,
        {
            "tick": 0,
            "rows": 8,
            "mean_return": 1.0,
            "explained_var": 0.5,
            "loss": 0.1,
            "entropy": 0.9,
            "kl": 0.01,
            "clipfrac": 0.1,
            "pg_loss": -0.2,
            "v_loss": 0.3,
        },
    )
    snap = dashboard.snapshot(base)
    h0 = snap["h0"]
    assert (h0["tick"], h0["micro"], h0["updates"]) == (5, 3, 1)




def test_replay_page_guards_traversal(tmp_path):
    import dashboard

    base = tmp_path / "archive"
    (base / "games").mkdir(parents=True)
    (base / "games" / "0.replay").write_text("{}")
    assert dashboard.replay_page(base, "games/0.replay") is not None
    assert dashboard.replay_page(base, "games/r.json") is None  # not a replay
    assert dashboard.replay_page(base, "../../etc/passwd") is None
    assert dashboard.replay_page(base, "missing.json") is None




def test_snapshot_retires_status_and_members(tmp_path):
    import dashboard

    base = tmp_path / "archive"
    snap = dashboard.snapshot(base)
    assert "status" not in snap and "members" not in snap
    assert "standings" not in snap and "learner" not in snap["h0"]
    assert set(snap["h0"]) == {
        "tick",
        "games",
        "updates",
        "micro",
        "games_per_h",
        "secs_since_game",
        "last_result",
        "last_length",
        "decisive",
    }




def test_dashboard_http_api(tmp_path):
    import json
    import threading
    import urllib.request

    import archive
    import dashboard

    base = tmp_path / "archive"
    archive.save_state(base, {"tick": 0, "next_tick": 0, "micro": 0})
    srv = dashboard.make_handler(base)
    import http.server

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), srv)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        root = f"http://127.0.0.1:{httpd.server_address[1]}"
        snap = json.load(urllib.request.urlopen(root + "/api/snapshot", timeout=5))
        assert snap["h0"]["tick"] == 0 and snap["game_total"] == 0
        assert "history" not in snap and "status" not in snap
        archive.log_game(base, ["main", "main"], [1, 1], "games/g/e/logs/0.replay")
        page = json.load(urllib.request.urlopen(root + "/api/games?limit=1", timeout=5))
        assert page["total"] == 1 and len(page["rows"]) == 1
        with urllib.request.urlopen(root + "/", timeout=5) as r:
            assert "no-store" in r.headers.get("Cache-Control", "")
    finally:
        httpd.shutdown()




def test_list_games_skips_malformed_rows(tmp_path):
    import archive

    base = tmp_path / "archive"
    archive.init(base)
    with open(base / "games.jsonl", "w") as f:
        f.write("{not json\n")
        f.write('{"seats":["main"]}\n')  # missing keys
        f.write(
            '{"seats":["main","main"],"scores":[null,1],"replay":"r"}\n'
        )
        f.write(
            '{"seats":["main","main"],"scores":[2,1],"replay":"r"}\n'
        )
    rows = archive.list_games(base)
    assert len(rows) == 1 and rows[0]["scores"] == [2, 1]




def test_snapshot_survives_poisoned_index(tmp_path):
    import archive
    import dashboard

    base = tmp_path / "archive"
    archive.init(base)
    with open(base / "games.jsonl", "w") as f:
        f.write('{"a":"main","b":"main"}\n')
    snap = dashboard.snapshot(base)
    assert snap["game_total"] == 0




def test_game_timeouts_raised_and_retry_flagged():
    import game_if

    cfg = game_if.GameConfig(map="m", turns=10)
    assert cfg.turntime_ms == 5000 and cfg.loadtime_ms == 15000
    assert game_if.GameConfig(map="m", turns=1).timeout == 600




def test_snapshot_window_matches_direct():
    import features
    import torch

    ants = FakeAnts()
    ants._mine = [(4, 4), (0, 0), (9, 9)]
    view = features.snapshot(ants)
    for loc in ants.my_ants():
        assert torch.equal(
            features.local_window(ants, loc),
            features.local_window(ants, loc, view=view),
        )




def test_play_one_marks_scoreless_and_hill_games(tmp_path, monkeypatch):
    import game_if
    import train

    base = tmp_path / "archive"
    cfg = {"seed": 0, "turns": 5, "temperature": 0.0, "tick": 7}

    def fake_play(hills):
        def go(*a, **k):
            game = {
                "game_length": 10,
                "score": [3, 1, 0],
                "replaydata": {
                    "map": {
                        "rows": 10,
                        "cols": 10,
                        "data": [".........." for _ in range(10)],
                    },
                    "viewradius2": 77,
                    "attackradius2": 5,
                    "food": [],
                    "ants": [
                        [4, 4, 1, 10, 0, "--"],
                        [6, 6, 1, 10, 1, "--"],
                        [5, 5, 1, 3, 2, "--"],
                    ],
                    "hills": hills,
                },
            }
            recs = [
                [{"turn": 3, "loc": [4, 4], "dest": [4, 4], "action": "stay",
                  "window": [[[0.0]]] }],
                [{"turn": 3, "loc": [6, 6], "dest": [6, 6], "action": "stay",
                  "window": [[[0.0]]] }],
                [{"turn": 3, "loc": [5, 5], "dest": [5, 5], "action": "stay",
                  "window": [[[0.0]]] }],
            ]
            return {"game": game, "records": recs}
        return go

    monkeypatch.setattr(game_if, "play", fake_play([]))
    out = train._play_one(cfg, base, {}, _tmp_3p_map(tmp_path))
    assert out["rets"] == [0.0, 0.0, 0.0]
    assert out["scoreless"] is True  # kill-only: nothing pays now
    assert len(out["rows"]) == 3  # rows still flow to the log path

    monkeypatch.setattr(game_if, "play", fake_play([[5, 5, 1, 3]]))
    out = train._play_one(cfg, base, {}, _tmp_3p_map(tmp_path))
    assert out["scoreless"] is False  # razed hill pays someone
    assert any(r != 0.0 for r in out["rets"])




def test_play_one_learns_from_every_seat(tmp_path, monkeypatch):
    import game_if
    import train

    base = tmp_path / "archive"
    cfg = {"seed": 0, "turns": 5, "temperature": 0.0, "tick": 7}

    def fake_play(*a, **k):
        assert isinstance(a[2], list) and len(a[2]) == 3  # one entry per seat
        game = {
            "game_length": 10,
            "score": [3, 1, 0],
            "replaydata": {
                "map": {
                    "rows": 10,
                    "cols": 10,
                    "data": [".........." for _ in range(10)],
                },
                "viewradius2": 77,
                "attackradius2": 5,
                "food": [],
                "ants": [
                    [4, 4, 1, 10, 0, "--"],
                    [6, 6, 1, 10, 1, "--"],
                    [5, 5, 1, 3, 2, "--"],
                ],
                "hills": [],
            },
        }
        # Each seat's record traces to its own staying ant, so the join
        # is exact. The owner-2 ant died: kills stay [1, 1, 0].
        recs = [
            [{"turn": 3, "loc": [4, 4], "dest": [4, 4], "action": "stay",
              "window": [[[0.0]]]}],
            [{"turn": 3, "loc": [6, 6], "dest": [6, 6], "action": "stay",
              "window": [[[0.0]]]}],
            [{"turn": 3, "loc": [5, 5], "dest": [5, 5], "action": "stay",
              "window": [[[0.0]]]}],
        ]
        return {"game": game, "records": recs}

    monkeypatch.setattr(game_if, "play", fake_play)
    out = train._play_one(cfg, base, {}, _tmp_3p_map(tmp_path))
    assert len(out["rows"]) == 3  # one decision row per seat
    assert out["rets"] == [0, 0, 0]  # nothing pays in a hill-less game
    (row,) = __import__("archive").list_games(base)
    assert row["seats"] == ["main", "main", "main"]
    assert row["scores"] == [3, 1, 0]
    assert row["food"] == [0, 0, 0] and row["kills"] == [1, 1, 0]




def test_cached_panel_shares_one_build_per_poll(tmp_path):
    import archive
    import dashboard

    base = tmp_path / "archive"
    archive.log_game(base, ["main", "main"], [1, 0], "games/g/e0/logs/0.replay", game="g#1")
    first = dashboard.cached_panel(base)
    assert dashboard.cached_panel(base) is first  # no rebuild on repoll
    assert len(first) == 1 and set(first[0]) == {
        "tick", "learner", "map", "seats", "scores", "stats",
        "length", "trace_miss", "timeouts", "breaks",
        "result", "replay"}
    assert first[0]["result"] == "win"  # seat-0 perspective
    archive.log_game(base, ["main", "main"], [0, 1], "games/g/e1/logs/0.replay", game="g#2")
    second = dashboard.cached_panel(base)
    assert len(second) == 2  # file change rebuilds
    assert second[0]["result"] == "loss"  # newest first, seat-0 lost




def test_run_once_discards_engine_stdout_off_ram(tmp_path, monkeypatch):
    import subprocess
    import sys

    import game_if

    seen = {}
    real = subprocess.run

    def spy(cmd, **kw):
        seen.update(kw)
        assert kw.get("capture_output") is not True  # never buffer stdout in RAM
        assert kw.get("stdout") == subprocess.DEVNULL
        assert kw.get("stderr") == subprocess.PIPE
        return real([sys.executable, "-c", "pass"], cwd=kw.get("cwd"), env=kw.get("env"))

    monkeypatch.setattr(subprocess, "run", spy)
    game_if._run_once([sys.executable, "-c", "print('x' * 100)"], tmp_path, {}, 60)




def test_run_once_failure_reports_stderr_tail(tmp_path):
    import sys

    import game_if

    try:
        game_if._run_once(
            [sys.executable, "-c", "import sys; sys.stderr.write('boom' * 100); sys.exit(3)"],
            tmp_path, {}, 60,
        )
    except RuntimeError as e:
        assert "boom" in str(e)
    else:
        raise AssertionError("failing engine must raise")




def test_play_one_caps_rows_per_game(tmp_path, monkeypatch):
    out = _big_game(monkeypatch, tmp_path)
    assert len(out["rows"]) == 4096 and len(out["rets"]) == 4096
    out2 = _big_game(monkeypatch, tmp_path)
    assert list(out2["rets"]) == list(out["rets"])  # seed:tick stable
    assert out["rets"] != [float(i) for i in range(4096)]  # subsampled, not truncated




def test_play_one_keeps_small_games_whole(tmp_path, monkeypatch):
    out = _big_game(monkeypatch, tmp_path, n_rows=100)
    assert len(out["rows"]) == 200 and len(out["rets"]) == 200  # 2 seats x 100




def test_trace_report_flags_water_breach():
    import rewards

    game = _trace_game()
    recs = [{"turn": 3, "loc": [5, 5], "dest": [5, 6], "action": "e"}]
    miss, problems = rewards.trace_report(game, 0, recs)
    assert miss == 1.0 and len(problems) == 1 and "water" in problems[0]




def test_trace_report_clean_when_matched():
    import rewards

    game = _trace_game()
    recs = [{"turn": 3, "loc": [5, 5], "dest": [5, 5], "action": "stay"}]
    assert rewards.trace_report(game, 0, recs) == (0.0, [])




def test_trace_report_flags_food_breach_and_ghost():
    import rewards

    game = _trace_game()
    game["replaydata"]["food"] = [[5, 4, 2, 5, 1]]
    recs = [{"turn": 3, "loc": [5, 5], "dest": [5, 4], "action": "w"}]
    miss, problems = rewards.trace_report(game, 0, recs)
    assert miss == 1.0 and len(problems) == 1 and "food" in problems[0]
    lonely = [{"turn": 9, "loc": [5, 5], "dest": [5, 4], "action": "w"}]
    miss, problems = rewards.trace_report(game, 0, lonely)
    assert miss == 1.0 and len(problems) == 1 and "ghost" in problems[0]




def test_trace_report_needs_map_data():
    import rewards

    game = _game()
    game["replaydata"]["ants"] = [[5, 5, 1, 6, 0, "----"]]
    recs = [{"turn": 3, "loc": [5, 5], "dest": [5, 6], "action": "e"}]
    with pytest.raises(ValueError):  # a miss with no grid to classify it
        rewards.trace_report(game, 0, recs)
    assert rewards.trace_report(game, 0, []) == (0.0, [])  # vacuous: clean




def test_resolve_stranded_rewrites_dest_not_action():
    import rewards

    game = _timeout_game()
    recs = [{"turn": 3, "loc": [5, 5], "dest": [5, 4], "action": "w"}]
    out = rewards.resolve_stranded(game, 0, recs)
    assert out[0]["dest"] == [5, 5]  # stranded ≡ stay: joinable
    assert out[0]["action"] == "w"  # intent stays honest for PPO
    assert recs[0]["dest"] == [5, 4]  # input untouched: pure return




def test_resolve_stranded_leaves_the_rest_for_trace():
    import rewards

    game = _timeout_game()
    matched = {"turn": 3, "loc": [5, 5], "dest": [5, 5], "action": "stay"}
    assert rewards.resolve_stranded(game, 0, [matched])[0]["dest"] == [5, 5]
    water = {"turn": 3, "loc": [5, 5], "dest": [5, 6], "action": "e"}
    assert rewards.resolve_stranded(game, 0, [water])[0]["dest"] == [5, 6]
    ghost = {"turn": 9, "loc": [5, 5], "dest": [5, 4], "action": "w"}
    assert rewards.resolve_stranded(game, 0, [ghost])[0]["dest"] == [5, 4]
    # Off the timeout turn even passable loss stays put: trace raises.
    game["playerturns"] = [5, 5]
    calm = {"turn": 3, "loc": [5, 5], "dest": [5, 4], "action": "w"}
    assert rewards.resolve_stranded(game, 0, [calm])[0]["dest"] == [5, 4]
    assert rewards.resolve_stranded(game, 0, []) == []




def test_play_one_resolves_stranded_orders_on_timeout_turns(tmp_path, monkeypatch):
    import archive
    import game_if
    import train as _train

    base = tmp_path / "archive"
    cfg = {"seed": 0, "turns": 5, "temperature": 0.0, "tick": 7}
    land = ["." * 10 for _ in range(10)]

    def fake_play(*a, **k):
        game = {
            "game_length": 10,
            "score": [3, 1],
            "status": ["timeout", "survived"],
            "playerturns": [3, 0],
            "replaydata": {
                "map": {"rows": 10, "cols": 10, "data": land},
                "viewradius2": 77,
                "attackradius2": 5,
                "food": [],
                "ants": [
                    [4, 4, 1, 10, 0, "-" * 9],
                    [6, 6, 1, 10, 1, "-" * 9],
                ],
                "hills": [],
            },
        }
        recs = [
            [{"turn": 3, "loc": [4, 4], "dest": [5, 4], "action": "e",
              "window": [[[0.0]]]}],
            [{"turn": 3, "loc": [6, 6], "dest": [6, 6], "action": "stay",
              "window": [[[0.0]]]}],
        ]
        return {"game": game, "records": recs}

    monkeypatch.setattr(game_if, "play", fake_play)
    out = _train._play_one(cfg, base, {}, _tmp_2p_map(tmp_path))
    assert out["rows"][0]["dest"] == [4, 4]  # stranded ≡ stay: joinable
    assert out["rows"][0]["action"] == "e"  # intent stays honest
    assert out["rows"][1]["dest"] == [6, 6]
    (row,) = archive.list_games(base)
    assert row["trace_miss"] == 0.0  # resolved before audit, not tolerated




def test_trace_report_excuses_mass_timeout_turn():
    import rewards

    game = _game()
    game["status"] = ["timeout", "survived", "timeout", "timeout"]
    game["playerturns"] = [140, 140, 140, 140]
    land = ["." * 24 for _ in range(48)]
    game["replaydata"]["map"] = {"rows": 48, "cols": 24, "data": land}
    game["replaydata"]["ants"] = [[0, 20, 130, 145, 1, "-" * 11]]
    recs = [{"turn": 140, "loc": [0, 20], "dest": [47, 20], "action": "n"}]
    miss, problems = rewards.trace_report(game, 1, recs)
    assert miss == 1.0 and problems == []  # tick635: survived seat, cutoff turn




def test_take_batch_caps_at_whole_games():
    import selfplay

    assert selfplay._take_batch([4000, 4096, 100], 8192) == (2, 8096)
    assert selfplay._take_batch([9000], 8192) == (1, 9000)  # at least one
    assert selfplay._take_batch([], 8192) == (0, 0)
    assert selfplay._take_batch([100, 200], 10000) == (2, 300)




def test_select_dispatch_holds_when_seats_full(tmp_path):
    import archive
    import selfplay

    base = tmp_path / "archive"
    archive.init(base)
    archive.save_state(base, {"tick": 0, "next_tick": 0, "micro": 0})
    four = tmp_path / "four.map"
    four.write_text("players 4\nrows 3\ncols 3\n" + "...\n" * 3)
    cfg = {"seed": 0, "maps": [str(four)], "seat_budget": 16}
    assert selfplay._select_dispatch(base, cfg, 16) is None
    assert selfplay._select_dispatch(base, cfg, 15) is None  # 15+4 overflows
    tick, _map, seats = selfplay._select_dispatch(base, cfg, 12)
    assert (tick, seats) == (0, 4)




def test_select_dispatch_holds_when_backlog_full(tmp_path):
    import archive
    import selfplay

    base = tmp_path / "archive"
    archive.init(base)
    archive.save_state(base, {"tick": 0, "next_tick": 0, "micro": 0})
    two = tmp_path / "two.map"
    two.write_text("players 2\nrows 3\ncols 3\n" + "...\n" * 3)
    cfg = {"seed": 0, "maps": [str(two)], "pending_cap_rows": 4}
    assert selfplay._select_dispatch(base, cfg, 0, pending_rows=4) is None
    assert selfplay._select_dispatch(base, cfg, 0, pending_rows=3) is not None




def test_bot_break_logs_decided_counts_to_stderr(tmp_path, monkeypatch, capsys):
    import AlphaAnt

    monkeypatch.setenv("AA_RECORD_DIR", str(tmp_path))

    class SlowAnts:
        rows, cols = 10, 10
        viewradius2 = 77
        _t = [0]

        def my_ants(self):
            return [(4, 4), (4, 5), (4, 6)]

        def enemy_ants(self):
            return []

        def food(self):
            return []

        def my_hills(self):
            return []

        def enemy_hills(self):
            return []

        def destination(self, loc, d):
            return (loc[0] + 1, loc[1])

        def passable(self, loc):
            return True

        def distance(self, a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        def issue_order(self, order):
            pass

        def time_remaining(self):
            return self._t.pop(0) if self._t else 0

    bot = AlphaAnt.AlphaAntBot()
    bot.do_setup(SlowAnts())
    bot.do_turn(SlowAnts())
    err = capsys.readouterr().err
    assert "BREAK" in err and "decided=1/3" in err




def test_parse_breaks_reads_bot_break_lines():
    import game_if

    raw = b"o 1 2 n\nBREAK side=side_0 turn=3 decided=5/9\ngarbage\n"
    assert game_if._parse_breaks(raw) == [
        {"side": "side_0", "turn": 3, "decided": 5, "live": 9}
    ]
    assert game_if._parse_breaks(b"no breaks here\n") == []




def test_play_persists_break_lines_to_logs(tmp_path, monkeypatch):
    import game_if

    base = tmp_path / "archive"
    outdir = tmp_path / "tick0"

    def fake_run(cmd, root, env, timeout):
        log_dir = Path(cmd[cmd.index("--log_dir") + 1])
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "0.replay").write_text(
            '{"game_length": 1, "score": [0, 0], "status": ["survived", "survived"],'
            ' "playerturns": [1, 1], "replaydata": {"map": {"rows": 3, "cols": 3,'
            ' "data": ["...", "...", "..."]}, "viewradius2": 77,'
            ' "attackradius2": 5, "food": [], "ants": [], "hills": []}}'
        )
        return b"BREAK side=side_1 turn=1 decided=0/2\n"

    monkeypatch.setattr(game_if, "_run_once", fake_run)
    cfg = game_if.GameConfig(map="m.map", turns=1)
    game_if.play(
        Path("."), sys.executable,
        [{}, {}], cfg, outdir, names=["side_0", "side_1"],
    )
    import json

    lines = (outdir / "logs" / "breaks.jsonl").read_text().strip().splitlines()
    assert [json.loads(l) for l in lines] == [
        {"attempt": 0, "breaks": [
            {"side": "side_1", "turn": 1, "decided": 0, "live": 2}
        ]}
    ]




def test_log_game_stores_time_limit_hits(tmp_path):
    import archive

    base = tmp_path / "archive"
    archive.log_game(
        base, ["main", "main"], [1, 0], "g/e/logs/0.replay",
        game="g#1", tick=0, timeouts=2, breaks=1,
    )
    (row,) = archive.list_games(base)
    assert row["timeouts"] == 2 and row["breaks"] == 1
    archive.log_game(base, ["main", "main"], [1, 0], "g/e/logs/0.replay", game="g#2")
    assert "timeouts" not in archive.list_games(base)[0]  # unknown, not zero




def test_play_one_logs_timeout_seats(tmp_path, monkeypatch):
    import archive
    import game_if
    import train

    base = tmp_path / "archive"
    cfg = {"seed": 0, "turns": 5, "temperature": 0.0, "tick": 7}

    def fake_play(*a, **k):
        return {
            "game": _trace_game_status(["timeout", "survived"]),
            "records": [[], []],
        }

    monkeypatch.setattr(game_if, "play", fake_play)
    train._play_one(cfg, base, {}, _tmp_2p_map(tmp_path))
    (row,) = archive.list_games(base)
    assert row["timeouts"] == 1




def test_play_returns_break_total(tmp_path, monkeypatch):
    import game_if

    outdir = tmp_path / "tick0"

    def fake_run(cmd, root, env, timeout):
        log_dir = Path(cmd[cmd.index("--log_dir") + 1])
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "0.replay").write_text(
            '{"game_length": 1, "score": [0, 0], "replaydata": {}}'
        )
        return b"BREAK side=side_0 turn=3 decided=5/9\nBREAK side=side_0 turn=4 decided=2/9\n"

    monkeypatch.setattr(game_if, "_run_once", fake_run)
    cfg = game_if.GameConfig(map="m.map", turns=1)
    out = game_if.play(
        Path("."), sys.executable, [{}, {}], cfg, outdir,
        names=["side_0", "side_1"],
    )
    assert out["breaks"] == 2
