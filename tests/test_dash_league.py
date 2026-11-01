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


def _game(a, sa, b, sb, kind="eval", gen="main"):
    ra = "win" if sa > sb else ("draw" if sa == sb else "loss")
    rb = "win" if sb > sa else ("draw" if sb == sa else "loss")
    return {
        "gen": gen, "kind": kind, "map": "m", "n": 2,
        "replay": f"games/{gen}/logs/0.replay",
        "seats": [{"id": a, "score": sa, "result": ra},
                  {"id": b, "score": sb, "result": rb}],
        "pairs": [{"a": a, "b": b, "score_a": sa, "score_b": sb}],
    }


def _league_base(base, k=4, anchors=("g000", "g009"), games=8,
                 behavior=True):
    """Synthetic league archive: league.json + logged learner games."""
    import archive

    archive.init(base)
    archive.save_checkpoint(base, {}, role="main", parent=None)
    archive.init_league(base, "live-main", list(anchors))
    st = archive.load_league(base)
    st["snapshot_every"] = k
    # production ensure fills bare slot ids (see ensure_league top-up).
    for _slot, _exp in st.get("exploiters", {}).items():
        _exp["id"] = _slot
    archive.save_league(base, st)
    for i in range(games):
        learner = "main" if i % 2 == 0 else "me"
        kw = {} if not behavior else {
            "tick": i, "food": [2, 1], "kills": [1, 0],
            "army": [5, 4], "length": 120}
        archive.log_game(base, learner, "eval", learner, "g000",
                         3 if i % 3 else 1, 1,
                         f"games/g{i}/logs/0.replay", map="m",
                         game=f"gid-{i}", **kw)
        archive.record_result(base, learner, "g000", 3 if i % 3 else 1, 1)
    return base


def _replaydata():
    """One synthetic 2-seat game: seat 0 gathers 2, kills 1, keeps 1
    alive; seat 1 gathers 1, kills 1, keeps 1 alive; length 10."""
    return {
        "map": {"rows": 8, "cols": 8},
        "food": [[1, 1, 5, 10, 0], [2, 2, 6, 12, 0], [3, 3, 7, 14, 1],
                 [4, 4, 8, 20]],
        "ants": [
            [0, 0, 0, 11, 0, "nnnnnnnnnn"],  # seat 0 survives
            [1, 1, 0, 6, 0, "eeeeee"],  # seat 0 dies on turn 6
            [2, 2, 0, 8, 1, "wwwwwwww"],  # seat 1 dies on turn 8
            [3, 3, 1, 11, 1, "nnnnnnnnn"],  # seat 1 survives (9 moves)
        ],
        "hills": [[0, 0, 0, 11], [7, 7, 1, 11]],
    }


# --- interval bucketing contract (unchanged) ---

def test_buckets_key_on_game_order_over_k():
    import dashboard

    games = [_game("m", 3, "o", 1) for _ in range(9)]  # newest-first
    batches = dashboard.interval_batches(games, 4)
    assert [len(b) for b in batches] == [4, 4, 1]
    assert batches[0][0] is games[-1]  # interval 0 opens at the oldest game
    assert dashboard.interval_labels(games, 4) == ["0–3", "4–7", "8–8"]


def test_buckets_generalize_gen_pairs_to_interval_keys():
    import dashboard

    pos = {"m": 0, "o": 1}
    # newest-first: the draw then the win are the OLDEST games.
    games = [_game("m", 3, "o", 1), _game("o", 2, "m", 2),
             _game("m", 1, "stranger", 0), _game("m", 1, "m", 1)]
    empty, mixed = dashboard.interval_pair_buckets(games, 2, pos)
    assert empty == {}  # stranger/self pairs skipped
    assert mixed[(0, 1)] == [1.5, 0.5]  # win + draw, train+eval together


def test_interval_size_prefers_league_json():
    import tempfile

    import archive
    import dashboard
    base = Path(tempfile.mkdtemp()) / "a"
    archive.init(base)
    assert dashboard.interval_size(base) == 80
    archive.init_league(base, "m", [])
    st = archive.load_league(base)
    st["snapshot_every"] = 17
    archive.save_league(base, st)
    assert dashboard.interval_size(base) == 17


# --- anchor panel contract (unchanged) ---

def test_league_panel_is_anchors_from_league_json(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "a", anchors=["g000", "g009"])
    assert dashboard.league_panel(base) == ["g000", "g009"]


def test_league_panel_empty_without_league_json(tmp_path):
    import archive
    import dashboard

    base = tmp_path / "a"
    archive.init(base)
    assert dashboard.league_panel(base) == []


def test_tracked_members_are_main_live_slots_plus_anchors(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "a", anchors=["g000", "g009"])
    grouped = dashboard.cached_grouped(base)
    assert dashboard.tracked_members(base, grouped) == \
        ["main", "me", "le-a", "le-b", "g000", "g009"]


# --- backend: behavior fields on game rows ---

def test_log_game_carries_tick_and_behavior(tmp_path):
    import archive

    base = tmp_path / "a"
    archive.log_game(base, "main", "eval", "main", "g000", 3, 1,
                     "games/g0/logs/0.replay", game="gid-0", tick=41,
                     food=[2, 1], kills=[1, 0], army=[5, 4], length=120)
    (row,) = archive.list_games(base)
    assert row["tick"] == 41
    assert row["food"] == [2, 1] and row["kills"] == [1, 0]
    assert row["army"] == [5, 4] and row["length"] == 120


def test_log_game_old_callers_keep_working(tmp_path):
    import archive

    base = tmp_path / "a"
    archive.log_game(base, "g001", "eval", "g000", "g001", 3, 1,
                     "games/g/logs/0.replay")
    (row,) = archive.list_games(base)
    assert row.get("tick") is None and row.get("food") is None


def test_anchor_rows_carry_tick(tmp_path):
    import archive

    base = tmp_path / "a"
    archive.init(base)
    row = archive.record_anchor(base, "s1", "m", "g000", 2, 0, 0, tick=7)
    assert row["tick"] == 7
    assert archive.list_anchors(base)[0]["tick"] == 7
    legacy = archive.record_anchor(base, "s1", "m", "g000", 2, 0, 0)
    assert legacy.get("tick") is None


def test_behavior_extraction_from_replay():
    import archive

    got = archive.behavior_from_replay(_replaydata(), n=2, length=10)
    assert got == {"food": [2, 1], "kills": [1, 1], "army": [1, 1],
                   "length": 10}
    assert archive.behavior_from_replay(None) is None
    assert archive.behavior_from_replay({}) is None


# --- anchors card: ladder per snapshot (new shape) ---

def test_anchor_trend_main_vs_ladder_per_snapshot(tmp_path):
    import archive
    import dashboard

    base = _league_base(tmp_path / "a", anchors=["g000", "g009"])
    state = archive.load_league(base)
    state["main_snapshots"] = ["s1", "s2"]
    archive.save_league(base, state)
    archive.record_anchor(base, "s1", "live-main", "g000", 2, 0, 0, tick=1)
    archive.record_anchor(base, "s2", "live-main", "g000", 1, 0, 1, tick=2)
    archive.record_anchor(base, "s2", "live-main", "g009", 0, 2, 0, tick=2)
    trend = dashboard.anchor_trend(base, archive.load_league(base))
    assert trend["snapshots"] == ["s1", "s2"]
    assert trend["series"]["g000"] == [1.0, 0.75]
    assert trend["series"]["g009"] == [None, 0.0]  # unmeasured: gap


# --- standings: 4 live rows ---

def test_standings_four_live_rows(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "a", games=8)
    snap = dashboard.snapshot(base)
    rows = {r["id"]: r for r in snap["standings"]}
    assert set(rows) == {"main", "me", "le-a", "le-b"}
    assert rows["main"]["class"] == "main"
    assert rows["me"]["class"] == "me"
    assert rows["le-a"]["class"] == "le"
    for r in rows.values():
        assert set(r) == {"id", "class", "elo", "w", "d", "l", "n",
                          "last_tick", "spark", "micro"}
    assert rows["main"]["n"] == 4 and rows["me"]["n"] == 4
    assert rows["le-a"]["n"] == 0  # never played: unknown, not zero-elo lie
    assert rows["le-a"]["elo"] is None
    assert isinstance(rows["main"]["elo"], int)
    assert rows["main"]["last_tick"] == 6  # newest main game


# --- bars: distance-to-bar per live exploiter ---

def test_bars_window_rate_and_eligible_in(tmp_path):
    import archive
    import dashboard

    base = _league_base(tmp_path / "a", games=0)
    for o in [1.0] * 10 + [0.5] * 4 + [0.0] * 6:
        archive.note_exploiter_game(base, "me", o, target="live-main")
    snap = dashboard.snapshot(base)
    bar = next(b for b in snap["bars"] if b["id"] == "me")
    assert bar["target"] == "live-main"
    assert bar["record_wdl"] == "10-4-6"
    assert bar["rate"] == (10 + 0.5 * 4) / 20
    assert bar["eligible_in"] == 20  # 40-window minus 20 games
    assert bar["spark"][0] == 1.0  # expanding rate: first 10 all wins
    assert bar["spark"][10] == round(10.5 / 11, 3)  # first draw dents it
    assert bar["spark"][-1] == bar["rate"]  # converges to the window rate
    assert len(bar["spark"]) == 20
    le = next(b for b in snap["bars"] if b["id"] == "le-a")
    assert le["eligible_in"] == 40 and le["rate"] is None


def test_standings_spark_tracks_each_game(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "a", games=8)
    rows = {r["id"]: r for r in dashboard.snapshot(base)["standings"]}
    sp = rows["main"]["spark"]
    assert len(sp) == 8  # one headline-history point per game end
    assert all(isinstance(v, float) for v in sp)
    assert sp[-1] != sp[0]  # the line moves with the games
    assert int(round(sp[-1])) == rows["main"]["elo"]  # ends at it
    assert all(isinstance(v, (int, float)) for v in sp)
    assert len(sp) <= dashboard.SPARK_MAX


def test_standings_rows_html_has_sparklines():
    import dashboard

    rows = [{"id": "main", "class": "main", "elo": 42, "w": 1,
             "d": 0, "l": 0, "n": 1, "last_tick": 3,
             "spark": [0.0, 42.0]}]
    html = dashboard.standings_rows_html(rows, 3)
    assert "<svg" in html and "polyline" in html


def test_window_record_counts_wdl():
    import dashboard

    assert dashboard.window_record([1.0, 1.0, 0.5, 0.0]) == ("2-1-1", 0.625)
    assert dashboard.window_record([]) == ("0-0-0", None)


# --- behavior card: per snapshot id + live slots ---

def test_behavior_aggregates_rows(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "a", games=8)
    rows = {r["id"]: r for r in dashboard.snapshot(base)["behavior"]}
    assert {"main", "me", "le-a", "le-b"} <= set(rows)
    main = rows["main"]
    assert main["food"] == 2.0 and main["kills"] == 1.0
    assert main["army_pct"] == 56  # 5/9 seats alive, 0dp
    assert main["length"] == 120 and main["n"] == 4
    assert rows["le-a"]["food"] is None  # unplayed: null, not zero
    assert main["spark"]["food"] == [2.0] * 4  # oldest-first series
    assert rows["le-a"]["spark"]["food"] == []


def test_behavior_spark_series_capped_oldest_first(tmp_path):
    import archive
    import dashboard

    base = tmp_path / "a"
    archive.init(base)
    archive.save_checkpoint(base, {}, role="main", parent=None)
    archive.init_league(base, "live-main", ["g000"])
    for i in range(45):
        archive.log_game(base, "main", "eval", "main", "g000", 1, 0,
                         f"games/g{i}/logs/0.replay", map="m",
                         game=f"gid-{i}", tick=i, food=[i, 0],
                         kills=[0, 0], army=[5, 4], length=100)
        archive.record_result(base, "main", "g000", 1, 0)
    rows = {r["id"]: r for r in dashboard.snapshot(base)["behavior"]}
    sp = rows["main"]["spark"]["food"]
    assert len(sp) == dashboard.SPARK_MAX
    assert sp[0] == 5.0 and sp[-1] == 44.0  # last 40, oldest first


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

    rows = [{"id": "main", "food": 2.0, "kills": 1.0,
             "army_pct": 56, "length": 120, "n": 4,
             "spark": {"food": [1.0, 2.0, 3.0], "kills": [],
                       "army": [50, 56], "length": [120]}}]
    html = dashboard.behavior_rows_html(rows, 0)
    assert html.count("<svg") == 3  # kills empty: no spark, — only
    assert "polyline" in html
def test_behavior_unknown_when_no_stats(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "a", games=2, behavior=False)
    rows = {r["id"]: r for r in dashboard.snapshot(base)["behavior"]}
    assert rows["main"]["food"] is None


# --- pairs: Laplace share + last tick ---

def test_pairs_share_and_last_tick(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "a", games=8)
    pairs = dashboard.snapshot(base)["pairs"]
    # canonical order follows matrix ids ([main, g000, me]): g000 sorts first.
    assert {(p["a"], p["b"]) for p in pairs} == {("main", "g000"),
                                                ("g000", "me")}
    # main games: i=0 draw, i=2 win, i=4 win, i=6 draw → 2W-2D-0L.
    # Laplace share: (2 + 0.5*2 + 1) / (4 + 2) = 4/6 → 67%.
    mg = next(p for p in pairs if p["a"] == "main")
    assert mg["n"] == 4
    assert mg["share"] == 67  # Laplace-smoothed, 0dp
    assert mg["last_tick"] == 6


# --- games: newest first with dual time ---

def test_games_newest_first_with_tick_ids(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "a", games=4)
    snap = dashboard.snapshot(base)
    assert snap["game_total"] == 4
    gs = snap["games"]
    assert [g["tick"] for g in gs] == [3, 2, 1, 0]
    assert all(set(g) == {"tick", "learner", "seats", "scores",
                          "result", "replay"} for g in gs)
    assert gs[0]["learner"] == "me" and gs[0]["seats"] == ["me", "g000"]
    assert gs[0]["result"] in ("win", "draw", "loss")
    page = dashboard.render_page(snap)
    assert ">t3<" in page  # the tick is the game number


# --- alerts rules ---

def test_alerts_all_clear_single_line(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "a", games=4)
    snap = dashboard.snapshot(base)
    assert snap["alerts"] == [{"level": "ok", "msg": "all clear",
                               "tick": snap["h0"]["tick"]}]


def test_alerts_drought_and_timeouts(tmp_path):
    import archive
    import dashboard

    base = _league_base(tmp_path / "a", games=0)
    for _ in range(121):
        archive.note_exploiter_game(base, "me", 0.0, target="live-main")
    for i in range(3):
        archive.log_game(base, "main", "eval", "main", "g000", 0, 0,
                         f"games/z{i}/logs/0.replay", game=f"z-{i}",
                         tick=100 + i, length=0)
    snap = dashboard.snapshot(base)
    msgs = [a["msg"] for a in snap["alerts"]]
    assert any("drought" in m and "me" in m for m in msgs)
    assert any("timeout" in m for m in msgs)
    assert len(snap["alerts"]) <= 5


def test_alerts_anchor_drop(tmp_path):
    import archive
    import dashboard

    base = _league_base(tmp_path / "a", games=0, anchors=["g000"])
    state = archive.load_league(base)
    state["main_snapshots"] = ["s1", "s2"]
    archive.save_league(base, state)
    archive.record_anchor(base, "s1", "m", "g000", 2, 0, 0, tick=1)
    archive.record_anchor(base, "s2", "m", "g000", 0, 2, 0, tick=2)
    snap = dashboard.snapshot(base)
    assert any("g000" in a["msg"] for a in snap["alerts"])


def test_active_learners_prefers_fresh_sharded_status(tmp_path):
    import os
    import time

    import archive
    import dashboard

    base = _league_base(tmp_path / "a", games=0)
    now = time.time()
    archive.write_status(base, {"learner": "main"}, learner="main")
    archive.write_status(base, {"learner": "me"}, learner="me")
    stale = archive.status_path(base, "le-a")
    archive.write_status(base, {"learner": "le-a"}, learner="le-a")
    os.utime(stale, (now - 999, now - 999))
    assert dashboard.active_learners(base, {}, now=now) == ["main", "me"]


def test_active_learners_falls_back_to_aggregate(tmp_path):
    import dashboard

    import archive

    base = _league_base(tmp_path / "a", games=0)
    archive.write_status(base, {"learner": "me"})
    assert dashboard.active_learners(base, {}, now=1e12) == ["me"]
    (base / "status.json").unlink()
    assert dashboard.active_learners(
        base, {"scheduler_pos": 7}, now=1e12) == ["le-b"]  # legacy slot


def test_h0_strip_joins_learners():
    import dashboard

    html = dashboard.h0_strip_html({"tick": 3,
                                    "learners": ["main", "me"],
                                    "games_per_h": None,
                                    "secs_since_game": 4,
                                    "anchor_verdict": "flat"})
    assert html.count("●") == 2 and "main" in html and "me" in html
    assert "micro" not in html  # micro lives per-learner in standings


def test_standings_carries_micro_progress(tmp_path):
    import dashboard

    import archive

    base = _league_base(tmp_path / "a", games=0)
    st = archive.load_league(base)
    st.setdefault("micro", {})["me"] = 5
    archive.save_league(base, st)
    rows = {r["id"]: r for r in dashboard.snapshot(base)["standings"]}
    assert rows["me"]["micro"] == 5 and rows["main"]["micro"] == 0


def test_reset_cut_keys_on_tick_not_replay_path():
    import dashboard

    def row(tick, replay="x"):
        return {"tick": tick, "replay": replay}
    grouped = [row(12), row(11), row(10)]  # newest-first
    cuts = dashboard.reset_cut_intervals(
        grouped, 2, [{"slot": "le-a", "seat": "le-a", "tick": 11}])
    assert cuts == {"le-a": {1}}  # order 1 of 3 -> cut fires at 1
    assert dashboard.reset_cut_intervals(
        grouped, 2, [{"slot": "le-a", "seat": "le-a", "tick": 99}]) == {}


def test_pair_buckets_score_losses_zero_not_draws():
    import dashboard

    def game(a, b, sa, sb):
        return {"pairs": [{"a": a, "b": b,
                            "score_a": sa, "score_b": sb}]}
    pos = {"x": 0, "y": 1}
    # Each game lands in its own interval (K=1); input is newest-first,
    # so per[0] is the oldest game (the win).
    per = dashboard.interval_pair_buckets(
        [game("x", "y", 0, 3), game("x", "y", 1, 1),
         game("x", "y", 3, 0)], 1, pos)
    assert per[0][(0, 1)] == [1.0, 0.0]  # W=1 from x's view
    assert per[1][(0, 1)] == [0.5, 0.5]  # D=0.5
    assert per[2][(0, 1)] == [0.0, 1.0]  # L=0, not a draw
    per = dashboard.interval_pair_buckets(
        [game("y", "x", 0, 3)], 1, pos)
    assert per[0][(0, 1)] == [1.0, 0.0]  # canonical flip keeps x's view


def test_elo_ranks_loser_below_splitter():
    import dashboard

    def game(a, b, sa, sb, tick):
        return {"tick": tick,
                "pairs": [{"a": a, "b": b,
                           "score_a": sa, "score_b": sb}]}
    # champ beats loser 4-1, splits 1-1 with mid; loser beats mid never.
    games = [game("champ", "loser", 3, 0, t) for t in range(4)]
    games += [game("champ", "loser", 0, 3, 4)]
    games += [game("champ", "mid", 3, 0, 5),
              game("champ", "mid", 0, 3, 6)]
    ids = ["champ", "loser", "mid"]
    pos = {c: i for i, c in enumerate(ids)}
    per = dashboard.interval_pair_buckets(games, 100, pos)
    theta = [1.0, 1.0, 1.0]
    series: dict = {}
    dashboard._interval_elo_extend(ids, per, ids, 4, 0, theta, series)
    assert series["loser"][-1] < series["mid"][-1] < series["champ"][-1]


def test_headline_history_ends_at_headline(tmp_path):
    import dashboard

    from test_curves import _elo_archive

    games = [("champ", "loser", "w")] * 8
    base, mid = _elo_archive(tmp_path, ["g000", "champ", "loser"], games,
                             K=4, seat="champ", name="elo-hist")
    grouped = dashboard.group_games(dashboard.archive.list_games(base))
    ids = dashboard.headline_ids(base, grouped)
    pair = [mid["champ"], mid["loser"]]
    hist = dashboard.headline_history(grouped, 4, ids, pair, [], {})
    champ, loser = mid["champ"], mid["loser"]
    assert len(hist[champ]) == 8  # one point per game end
    # climbs within each K-block (a fresh block starts prior-heavy);
    # the last point IS the headline number.
    blk = [hist[champ][i:i + 4] for i in range(0, 8, 4)]
    assert all(all(b > a for a, b in zip(bk, bk[1:])) for bk in blk)
    assert all(c > l for c, l in zip(hist[champ], hist[loser]))
    series = dashboard._interval_elo_cached(
        base, grouped, 4, [champ, loser])["series"]
    assert hist[champ][-1] == series[champ][-1]  # last point IS it
    assert hist[loser][-1] == series[loser][-1]


def test_headline_history_ignores_future_resets(tmp_path):
    import dashboard

    from test_curves import _elo_archive

    games = [("champ", "loser", "w")] * 4
    base, mid = _elo_archive(tmp_path, ["g000", "champ", "loser"], games,
                             K=4, seat="champ", name="elo-causal")
    grouped = dashboard.group_games(dashboard.archive.list_games(base))
    assert sorted(g["tick"] for g in grouped) == [0, 1, 2, 3]
    ids = dashboard.headline_ids(base, grouped)
    pair = [mid["champ"], mid["loser"]]
    before = dashboard.headline_history(grouped, 4, ids, pair, [], {})
    after = dashboard.headline_history(
        grouped, 4, ids, pair,
        [{"slot": "loser", "seat": mid["loser"], "tick": 3}], {})
    # points ending before the reset tick are untouched by it.
    assert before[pair[0]][:3] == after[pair[0]][:3]
    assert before[pair[1]][:3] == after[pair[1]][:3]


def test_anchor_trend_carries_snapshot_progress(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "a", games=0)
    st = dashboard.archive.load_league(base)
    st["main_snapshots"] = ["m0"]
    dashboard.archive.save_league(base, st)
    trend = dashboard.snapshot(base)["anchors"]
    assert trend["main_games"] == 0 and trend["snapshot_every"] == 4
    html = dashboard.ladder_fallback_html(trend)
    assert "first snapshot at 4 main games" in html


def test_ladder_fallback_shows_shares_once_played(tmp_path):
    import dashboard

    trend = {"snapshots": ["m0"], "series": {"g000": [0.75]},
             "main_games": 80, "snapshot_every": 80}
    html = dashboard.ladder_fallback_html(trend)
    assert "g000 75%" in html
