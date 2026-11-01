"""League dashboard contracts (build/dashboard2): new snapshot shape.

Backend logging (tick/food/kills/army/length on games.jsonl rows, tick
on anchor rows) plus the board facts the page reads: H0, anchors,
standings, bars, pairs, behavior, games, alerts. Pure-math tests that
survived the rework (interval bucketing, anchor panel, window records)
are unchanged; everything pinning retired keys is rewritten.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))


def _league_base(base, games=8, behavior=True):
    """Synthetic archive: state.json + logged mirror games, no engine."""
    import archive

    archive.init(base)
    archive.save_state(base, {"tick": games, "next_tick": games, "micro": 0})
    for i in range(games):
        kw = (
            {}
            if not behavior
            else {
                "tick": i,
                "food": [2, 1],
                "kills": [1, 0],
                "army": [5, 4],
                "length": 120,
            }
        )
        archive.log_game(
            base,
            ["main", "main"], [3 if i % 3 else 1, 1],
            f"games/g{i}/logs/0.replay",
            map="m",
            game=f"gid-{i}",
            **kw,
        )
    return base


def _replaydata():
    """One synthetic 2-seat game: seat 0 gathers 2, kills 1, keeps 1
    alive; seat 1 gathers 1, kills 1, keeps 1 alive; length 10."""
    return {
        "map": {"rows": 8, "cols": 8},
        "food": [[1, 1, 5, 10, 0], [2, 2, 6, 12, 0], [3, 3, 7, 14, 1], [4, 4, 8, 20]],
        "ants": [
            [0, 0, 0, 11, 0, "nnnnnnnnnn"],  # seat 0 survives
            [1, 1, 0, 6, 0, "eeeeee"],  # seat 0 dies on turn 6
            [2, 2, 0, 8, 1, "wwwwwwww"],  # seat 1 dies on turn 8
            [3, 3, 1, 11, 1, "nnnnnnnnn"],  # seat 1 survives (9 moves)
        ],
        "hills": [[0, 0, 0, 11], [7, 7, 1, 11]],
    }


def test_log_game_carries_tick_and_behavior(tmp_path):
    import archive

    base = tmp_path / "a"
    archive.log_game(
        base,
        ["main", "main"], [3, 1],
        "games/g0/logs/0.replay",
        game="gid-0",
        tick=41,
        food=[2, 1],
        kills=[1, 0],
        army=[5, 4],
        length=120,
    )
    (row,) = archive.list_games(base)
    assert row["tick"] == 41
    assert row["food"] == [2, 1] and row["kills"] == [1, 0]
    assert row["army"] == [5, 4] and row["length"] == 120


def test_log_game_old_callers_keep_working(tmp_path):
    import archive

    base = tmp_path / "a"
    archive.log_game(base, ["main", "main"], [3, 1], "games/g/logs/0.replay")
    (row,) = archive.list_games(base)
    assert row.get("tick") is None and row.get("food") is None


def test_behavior_extraction_from_replay():
    import archive

    got = archive.behavior_from_replay(_replaydata(), n=2, length=10)
    assert got == {"food": [2, 1], "kills": [1, 1], "army": [1, 1], "length": 10}
    assert archive.behavior_from_replay(None) is None
    assert archive.behavior_from_replay({}) is None


def test_behavior_aggregates_rows(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "a", games=8)
    rows = {r["id"]: r for r in dashboard.snapshot(base)["behavior"]}
    assert set(rows) == {"main"}
    main = rows["main"]
    assert main["food"] == 1.5 and main["kills"] == 0.5
    assert main["army_pct"] == 50  # mean of 5/9 and 4/9 shares, 0dp
    assert main["length"] == 120 and main["n"] == 16
    assert main["spark"]["food"] == [2.0, 1.0] * 8  # oldest-first


def test_behavior_spark_series_capped_oldest_first(tmp_path):
    import archive
    import dashboard

    base = tmp_path / "a"
    archive.init(base)
    archive.save_state(base, {"tick": 45, "next_tick": 45, "micro": 0})
    for i in range(45):
        archive.log_game(
            base,
            ["main", "main"], [1, 0],
            f"games/g{i}/logs/0.replay",
            map="m",
            game=f"gid-{i}",
            tick=i,
            food=[i, 0],
            kills=[0, 0],
            army=[5, 4],
            length=100,
        )
    rows = {r["id"]: r for r in dashboard.snapshot(base)["behavior"]}
    sp = rows["main"]["spark"]["food"]
    assert len(sp) == dashboard.SPARK_MAX
    assert sp[0] == 25.0 and sp[-1] == 0.0  # last 40, oldest first


def test_spark_svg_shapes():
    import dashboard

    assert dashboard.spark_svg([]) == ""
    assert dashboard.spark_svg([None, "x"]) == ""
    flat = dashboard.spark_svg([3, 3, 3])
    assert "polyline" in flat and flat.count(",") == 3
    rising = dashboard.spark_svg([0, 10])
    assert "0.0,16.0" in rising and "90.0,2.0" in rising


def test_behavior_rows_html_has_sparklines():
    import dashboard

    rows = [
        {
            "id": "main",
            "food": 2.0,
            "kills": 1.0,
            "army_pct": 56,
            "length": 120,
            "n": 4,
            "spark": {
                "food": [1.0, 2.0, 3.0],
                "kills": [],
                "army": [50, 56],
                "length": [120],
            },
        }
    ]
    html = dashboard.behavior_rows_html(rows, 0)
    assert html.count("<svg") == 3  # kills empty: no spark, — only
    assert "polyline" in html


def test_behavior_unknown_when_no_stats(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "a", games=2, behavior=False)
    rows = {r["id"]: r for r in dashboard.snapshot(base)["behavior"]}
    assert rows["main"]["food"] is None


def test_games_newest_first_with_tick_ids(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "a", games=4)
    snap = dashboard.snapshot(base)
    assert snap["game_total"] == 4
    gs = snap["games"]
    assert [g["tick"] for g in gs] == [3, 2, 1, 0]
    assert all(
        set(g)
        == {"tick", "learner", "seats", "scores", "stats", "length", "result", "replay"}
        for g in gs
    )
    assert gs[0]["learner"] == "main" and gs[0]["seats"] == ["main", "main"]
    assert gs[0]["result"] in ("win", "draw", "loss")
    page = dashboard.render_page(snap)
    assert ">t3<" in page  # the tick is the game number


def test_alerts_all_clear_single_line(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "a", games=4)
    snap = dashboard.snapshot(base)
    assert snap["alerts"] == [
        {"level": "ok", "msg": "all clear", "tick": snap["h0"]["tick"]}
    ]


def test_h0_strip_shows_mirror_facts():
    import dashboard

    html = dashboard.h0_strip_html(
        {
            "tick": 3,
            "games": 10,
            "updates": 1,
            "micro": 2,
            "games_per_h": None,
            "secs_since_game": 4,
            "last_result": "win",
            "last_length": 150,
            "decisive": 0.5,
        }
    )
    assert "main" in html and "micro" in html
    assert ">t" not in html or "game</b> 3" in html


def test_build_game_carries_per_seat_behavior():
    import dashboard

    row = {
        "seats": ["main", "main0"],
        "scores": [5, 3],
        "food": [8, 26],
        "kills": [23, 7],
        "army": [2, 4],
        "length": 150,
    }
    row["tick"] = 9
    g = dashboard.build_game(row)
    assert g["learner"] == "main" and g["tick"] == 9
    assert g["seats"] == ["main", "main0"] and g["scores"] == [5, 3]
    assert g["result"] == "win"  # seat-0 perspective
    assert g["stats"][0]["food"] == 8.0
    assert g["stats"][0]["kills"] == 23.0
    assert g["stats"][0]["army_pct"] == 33  # 2 of 2+4 alive
    assert g["stats"][1]["food"] == 26.0
    assert g["length"] == 150


def test_build_game_supports_three_seats():
    import dashboard

    row = {"seats": ["main", "main", "main"], "scores": [5, 3, 1],
           "food": [8, 26, 0], "kills": [23, 7, 0], "army": [2, 4, 6],
           "length": 150, "tick": 9}
    g = dashboard.build_game(row)
    assert g["seats"] == ["main", "main", "main"]
    assert g["scores"] == [5, 3, 1] and g["result"] == "win"
    assert g["stats"][2]["food"] == 0.0
    assert g["stats"][0]["army_pct"] == 17  # 2 of 2+4+6 alive


def test_panel_row_shows_behavior():
    import dashboard

    row = {
        "seats": ["main", "main0"],
        "scores": [5, 3],
        "food": [8, 26],
        "kills": [23, 7],
        "army": [2, 4],
        "length": 150,
        "replay": "r",
        "tick": 9,
    }
    g = dashboard.build_game(row)
    assert g["length"] == 150
    assert g["stats"][0]["food"] == 8.0
    html = dashboard.game_row_html(g)
    assert "12" not in html  # placeholder guard: real numbers below
    assert "8.0f" in html and "23.0k" in html and "33%" in html
    assert "<td>150</td>" in html.replace(' class="num"', "")


def test_build_game_missing_behavior_reads_unknown():
    import dashboard

    row = {"seats": ["main", "main0"], "scores": [5, 3]}
    g = dashboard.build_game(row)
    assert all(s["food"] is None for s in g["stats"])
    assert g["length"] is None and g["tick"] is None
    assert dashboard.build_game({"seats": ["main"]}) is None  # bad facts drop


def test_training_panel_reports_latest_updates(tmp_path):
    import archive
    import dashboard

    base = _league_base(tmp_path / "a", games=0)
    for i in range(3):
        archive.log_update(
            base,
            {
                "tick": i * 8,
                "rows": 100,
                "mean_return": 1.5,
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
    assert snap["h0"]["updates"] == 3
    rows = snap["training"]
    assert [r["tick"] for r in rows] == [16, 8, 0]  # newest first
    html = dashboard.training_rows_html(rows)
    assert "0.10" in html and "no updates yet" not in html
    assert dashboard.training_rows_html([]).count('colspan="8"') == 1


def test_snapshot_contract_is_pure_az(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "a", games=4)
    snap = dashboard.snapshot(base)
    assert sorted(snap.keys()) == [
        "alerts",
        "behavior",
        "game_total",
        "games",
        "h0",
        "mtime",
        "training",
    ]
    h0 = snap["h0"]
    assert h0["tick"] == 4 and h0["games"] == 4
    assert h0["micro"] == 0 and h0["updates"] == 0
