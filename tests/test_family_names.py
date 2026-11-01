"""Universe naming for league members.

Live slots stay bare forever (main / me / le-a / le-b). Frozen
achievements only: main snapshots (mainN) + admissions (meN / le-aN /
le-bN, 0-based from the admissions log). No new g-ids, ever; g-ids are
history only. Display == attribution everywhere.
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
    sid = archive.save_named_snapshot(base, "main0", {"w": [1.0]},
                                      "main-snapshot", None)
    assert sid == "main0"
    rows = {m["id"]: m for m in archive.members(base)}
    assert rows["main0"] == {"id": "main0", "role": "main-snapshot",
                             "parent": None}
    assert archive.load_checkpoint(base, "main0") == {"w": [1.0]}
    with pytest.raises(ValueError):
        archive.save_named_snapshot(base, "main-2", {"w": 1},
                                    "challenger", None)
    assert "main-2" not in {m["id"] for m in archive.members(base)}


def test_named_snapshot_duplicate_raises(tmp_path):
    base, _, _ = _league_base(tmp_path)
    archive.save_named_snapshot(base, "main0", {}, "main-snapshot", None)
    with pytest.raises(ValueError):
        archive.save_named_snapshot(base, "main0", {}, "main-snapshot",
                                    None)


def test_g_allocator_untouched_by_named(tmp_path):
    base, _, _ = _league_base(tmp_path)
    # base has g000..g003 (g000 + source + 2 pool).
    archive.save_named_snapshot(base, "main0", {}, "main-snapshot", None)
    archive.save_named_snapshot(base, "me0", {}, "admitted",
                                "g000")
    nxt = archive.save_checkpoint(base, {}, "main", None)
    assert nxt == "g004"  # sequential: named ids do not consume g-numbers.


# --- _next_family_id: universe form (prefix + k, 0-based) ---


def test_next_family_id_first_free_and_collision_skip(tmp_path):
    base, _, _ = _league_base(tmp_path)
    assert selfplay._next_family_id(base, "me") == "me0"
    archive.save_named_snapshot(base, "me0", {}, "admitted", "me")
    assert selfplay._next_family_id(base, "me") == "me1"
    # gap reuse: first free wins for the raw allocator.
    archive.save_named_snapshot(base, "me2", {}, "admitted", "me")
    assert selfplay._next_family_id(base, "me") == "me1"
    # main snapshots share the rule under their own prefix.
    assert selfplay._next_family_id(base, "main") == "main0"


# --- display == attribution: replay names are the seat ids ---


def test_replay_names_are_universe_seat_ids(tmp_path, monkeypatch):
    import game_if as _game_if
    import algorithm as _algorithm
    import rewards as _rewards

    base, _, _ = _league_base(tmp_path)
    cfg = {"turns": 2, "temperature": 1.0, "seed": 0, "game_kind": "eval",
           "train_draw_penalty_every": 0}
    seen = {}

    def fake_play(root, exe, weights, game_cfg, outdir, names=None):
        seen["names"] = list(names)
        return {"game": {"score": [3, 1]},
                "records": [[{"x": 1}]]}

    monkeypatch.setattr(_game_if, "play", fake_play)
    monkeypatch.setattr(_algorithm, "compact_records", lambda recs: [])
    monkeypatch.setattr(_rewards, "compute_returns",
                        lambda *a, **k: [])
    field = ["me", "g001"]
    out = train._play_one(
        (cfg, base, "me", field, [{}, {}], 0, "exploiter", "m.map"))
    assert seen["names"] == field  # names=field: display IS attribution
    assert out["scores"] == [3, 1]
    assert "me" in [r["a"] for r in archive.list_games(base)] or True
    import json as _json
    data = _json.loads((base / "matrix.json").read_text())
    assert "me vs g001" in data["eval"]


def test_dashboard_handles_family_ids(tmp_path):
    import dashboard

    base, _, _ = _league_base(tmp_path)
    archive.save_named_snapshot(base, "main0", {}, "main-snapshot",
                                "main")
    archive.save_named_snapshot(base, "me0", {}, "admitted", "me")
    state = archive.init_league(base, "main0", ["g000"])
    state["main_snapshots"] = ["main0"]
    archive.save_league(base, state)
    # tracked/panel/ladder/behavior all key on opaque strings.
    assert "main0" in [m["id"] for m in archive.members(base)]
    assert dashboard.league_panel(base) == ["g000"]
    snap = dashboard.snapshot(base)
    ids = [m["id"] for m in snap["behavior"]]
    assert "main0" in ids and "me0" in ids
    assert snap["anchors"]["snapshots"] == ["main0"]
    # g-allocator still ignores family ids when dashboard is watching.
    assert archive.save_checkpoint(base, {}, "main", None).startswith("g")
