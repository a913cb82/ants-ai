"""Progress-board curves for the continuous league (phase 4).

Pure-computation tests: K-game interval bucketing, the running BT pass
over intervals, conversion/decisiveness/margin windows, PG signal +
value slope (main-only), snapshot memo. The throne-era curves (knock
marks, reign strip, crowns, N-player boundary, turn confounds, Nash)
retired with the duel framing and have no tests here.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))


def _game(a, sa, b, sb, kind="eval", gen="main"):
    """One grouped 2-seat game dict (build_game shape)."""
    ra = "win" if sa > sb else ("draw" if sa == sb else "loss")
    rb = "win" if sb > sa else ("draw" if sb == sa else "loss")
    return {
        "gen": gen, "kind": kind, "map": "m", "n": 2,
        "replay": f"games/{gen}/logs/0.replay",
        "seats": [{"id": a, "score": sa, "result": ra},
                  {"id": b, "score": sb, "result": rb}],
        "pairs": [{"a": a, "b": b, "score_a": sa, "score_b": sb}],
    }


def _h(challenger, champion="g000", train=None, margins=None):
    return {"challenger": challenger, "champion": champion,
            "train": train or {}, "eval": {"margins": margins or []}}


# --- interval bucketing ---

def test_interval_batches_oldest_first_and_partial_tail():
    import dashboard

    games = [_game("a", 3, "b", 1) for _ in range(5)]  # newest-first input
    batches = dashboard.interval_batches(games, 2)
    assert len(batches) == 3  # 2 + 2 + 1 (live tail kept)
    assert [len(b) for b in batches] == [2, 2, 1]
    assert batches[0][0] is games[-1]  # oldest game opens interval 0


def test_interval_pair_buckets_sum_kinds_skip_strays():
    import dashboard

    pos = {"a": 0, "b": 1, "c": 2}
    games = [
        _game("a", 3, "b", 1, kind="eval"),
        _game("b", 3, "a", 1, kind="train"),  # same pair, other kind: adds
        _game("a", 1, "ghost", 0),  # unknown member: skipped
        _game("a", 2, "a", 2),  # self-pair: skipped
    ]
    (buck,) = dashboard.interval_pair_buckets(games, 100, pos)
    assert buck[(0, 1)] == [1.0, 1.0]  # train+eval together, outcomes
    assert len(buck) == 1


def test_interval_size_reads_league_snapshot_every(tmp_path):
    import archive
    import dashboard

    base = tmp_path / "archive"
    archive.init(base)
    assert dashboard.interval_size(base) == 80  # scheduler cadence fallback
    archive.init_league(base, "m", ["g000"])
    assert dashboard.interval_size(base) == 80
    st = archive.load_league(base)
    st["snapshot_every"] = 25
    archive.save_league(base, st)
    assert dashboard.interval_size(base) == 25
    st["snapshot_every"] = "junk"
    archive.save_league(base, st)
    assert dashboard.interval_size(base) == 80  # junk guards to cadence


# --- running Elo over intervals: same math, per-learner readout ---

def test_intervals_transitive_panel():
    import dashboard

    ids = ["g000", "a", "b", "c"]
    per = [{(1, 2): [3.0, 0.0]}, {(2, 3): [3.0, 0.0]}]
    s = dashboard.running_elo_intervals(ids, per, ["a", "b", "c"])
    assert s["series"]["a"][0] > s["series"]["b"][0]  # a beat b
    assert s["series"]["b"][1] > s["series"]["c"][1]  # b beat c


def test_intervals_draws_shrink_and_empty_stays_zero():
    import dashboard

    ids = ["g000", "a", "b", "lonely"]
    per = [{(1, 2): [2.0, 2.0]}, {}]
    s = dashboard.running_elo_intervals(ids, per, ["a", "b", "lonely"])
    assert s["series"]["a"][0] == s["series"]["b"][0] == 0.0  # all-square
    assert s["series"]["lonely"] == [0.0, 0.0]  # known, unplayed: zero


def test_intervals_g000_pinned():
    import dashboard

    ids = ["g000", "x"]
    per = [{(0, 1): [0.0, 4.0]}]  # x sweeps g000 4-0
    s = dashboard.running_elo_intervals(ids, per, ["g000", "x"])
    assert s["series"]["g000"] == [0.0]  # pinned zero never moves
    assert s["series"]["x"][0] > 100  # decisive sweep reads as a large gap


def test_intervals_seed_indifferent():
    import dashboard

    ids = ["g000", "a", "b", "c"]
    per = [{(0, 1): [0.0, 4.0]}, {(1, 2): [3.0, 1.0]}, {(2, 3): [1.0, 3.0]}]
    plain = dashboard.running_elo_intervals(ids, per, ["a", "b", "c"])
    seeded = dashboard.running_elo_intervals(
        ids, per, ["a", "b", "c"],
        parents={"a": "c", "b": "c", "c": "c"})
    for m in ("a", "b", "c"):
        for p, q in zip(plain["series"][m], seeded["series"][m],
                         strict=True):
            assert abs(p - q) < 5.0  # sub-display agreement, hostile seeds


def test_intervals_unplayed_tracker_carries_parent():
    import dashboard

    ids = ["g000", "par", "kid"]
    per = [{(0, 1): [0.0, 4.0]}, {}]
    assert dashboard.running_elo_intervals(
        ids, per, ["kid"])["series"]["kid"] == [0.0, 0.0]  # at anchor
    s = dashboard.running_elo_intervals(
        ids, per, ["par", "kid"], parents={"par": "g000", "kid": "par"})
    assert abs(s["series"]["kid"][1] - s["series"]["par"][0]) < 1e-9
    assert s["series"]["kid"][1] > 100


def test_intervals_prefix_stable():
    import dashboard

    ids = ["g000", "a", "b"]
    full = [{(0, 1): [3.0, 1.0]}, {(0, 2): [0.0, 4.0]}, {(1, 2): [2.0, 2.0]}]
    a = dashboard.running_elo_intervals(ids, full, ["a", "b"])
    b = dashboard.running_elo_intervals(ids, full[:2], ["a", "b"])
    # later games never move earlier intervals (bitwise: same trajectory).
    assert a["series"]["a"][:2] == b["series"]["a"]
    assert a["series"]["b"][:2] == b["series"]["b"]


# --- interval curves ---

def test_conversion_pools_window_with_wilson():
    import dashboard

    batches = [
        [_game("m", 3, "o", 1), _game("m", 2, "o", 2)],  # 1.5/2
        [_game("m", 0, "o", 5)],  # 0/1
        [_game("m", 1, "o", 0, kind="train")],  # practice: ignored
    ]
    c = dashboard.conversion(batches, window=2)
    assert c["conv"][0] == 0.75
    assert c["conv"][1] == 0.5  # pooled 1.5/3 over the window
    assert c["conv"][2] == 0.0  # window still holds the eval loss
    assert c["clo"][1] <= 0.5 <= c["chi"][1]
    assert dashboard.conversion([[]])["conv"] == [None]  # gaps, not zeros


def test_decisiveness_per_interval_split_by_kind():
    import dashboard

    batches = [
        [_game("a", 3, "b", 1, kind="train"),
         _game("a", 2, "b", 2, kind="train")],
        [_game("a", 3, "b", 1, kind="eval"),
         _game("a", 1, "b", 1, kind="eval"),
         _game("a", 1, "b", 1, kind="eval")],
    ]
    d = dashboard.decisiveness(batches, window=2)
    assert d["train"] == [0.5, None]
    assert d["eval"] == [None, 1 / 3]
    assert d["train_ma"][0] == 0.5
    assert d["eval_ma"][1] == 1 / 3


def test_margin_band_pools_trailing_windows():
    import dashboard

    batches = [
        [_game("m", 10, "o", 0), _game("m", 0, "o", 10)],
        [_game("m", 4, "o", 1, kind="train")],  # practice: not a margin
        [_game("m", 6, "o", 0), _game("m", 0, "o", 0, kind="train")],
    ]
    m = dashboard.margin_band(batches, window=2)
    assert m["med"][0] == 0.0  # +10, -10 pool to zero
    assert m["med"][1] == 0.0  # train-only interval pools empty window-mate
    assert m["med"][2] == 6.0
    assert m["q1"][0] == -10.0 and m["q3"][0] == 10.0


def test_game_margin_seat0_minus_seat1_and_nplayer_none():
    import dashboard

    assert dashboard.game_margin(_game("m", 5, "o", 2)) == 3.0
    three = dict(_game("m", 5, "o", 2))
    three["seats"] = three["seats"] + [{"id": "z", "score": 0}]
    assert dashboard.game_margin(three) is None  # no single training edge


def test_pg_signal_ratio_last_epoch():
    import dashboard

    hist = [_h("g001", train={"pg_loss": [0.5, 0.2], "pg_abs": [1.0, 0.8],
                              "entropies": [0.9, 0.7]})]
    p = dashboard.pg_signal(hist, window=2)
    assert abs(p["ratio"][0] - 0.25) < 1e-9
    assert p["entropy"][0] == 0.7
    assert p["ratio_med"][0] == p["ratio"][0]


def test_pg_signal_missing_or_zero_abs_is_none():
    import dashboard

    hist = [_h("g001", train={"pg_loss": [0.2], "pg_abs": [0.0]}),
            _h("g002", train={"pg_loss": [0.2]})]
    p = dashboard.pg_signal(hist, window=2)
    assert p["ratio"] == [None, None]


def test_value_slope():
    import dashboard

    hist = [_h("g001", train={"v_loss": [1.0, 0.6, 0.4]}),
            _h("g002", train={"v_loss": [0.0, 0.0]}),
            _h("g003")]
    v = dashboard.value_slope(hist)
    assert abs(v[0] - 0.6) < 1e-9
    assert v[1] is None and v[2] is None


def test_main_history_filters_exploiter_rows():
    import dashboard

    hist = [{"learner": "main"}, {"learner": "me"}, {"challenger": "g001"}]
    assert dashboard.main_history(hist) == [hist[0], hist[2]]


def test_norm01_spans_min_max():
    import dashboard

    got = dashboard.norm01([0.004, 0.2, 3.891, None])
    assert got[0] == 0.0 and got[2] == 1.0 and got[3] is None
    assert abs(got[1] - 0.0504) < 1e-3  # (0.2-0.004)/(3.891-0.004)
    assert dashboard.norm01([5.0, 5.0]) == [0.5, 0.5]  # constant: mid-lane
    assert dashboard.norm01([None, None]) == [None, None]


def test_merge_pairs_sums_overlap():
    import dashboard

    ev = {"a vs b": [3.0, 1.0]}
    tr = {"a vs b": [1.0, 1.0], "b vs c": [2.0, 0.0]}
    m = dashboard.merge_pairs(ev, tr)
    assert m["a vs b"] == [4.0, 2.0]
    assert m["b vs c"] == [2.0, 0.0]


# --- snapshot board ---

def _mini_league(base, n_games=12, k=4, learners=("main", "me"), start=0):
    """Synthetic league archive: league.json + logged learner games."""
    import archive

    archive.init(base)
    g000 = archive.save_checkpoint(base, {}, role="main", parent=None)
    archive.set_champion(base, g000)
    archive.init_league(base, "live-main", ["g000"])
    st = archive.load_league(base)
    st["snapshot_every"] = k
    archive.save_league(base, st)
    for j in range(n_games):
        i = start + j
        learner = learners[j % len(learners)]
        archive.log_game(base, learner, "eval", learner, "g000",
                         3 if i % 3 else 1, 1,
                         f"games/g{i}/logs/0.replay", map="m",
                         game=f"gid-{i}")
        archive.record_result(base, learner, "g000", 3 if i % 3 else 1, 1)
    return base


def test_snapshot_board_present_and_interval_shaped(tmp_path):
    import dashboard

    base = _mini_league(tmp_path / "archive")
    snap = dashboard.snapshot(base)
    board = snap["board"]
    for key in ("k", "labels", "elo", "conv", "decisive", "margin",
                "pg", "vslope"):
        assert key in board, key
    assert board["k"] == 4
    assert len(board["labels"]) == 3  # 12 games, K=4
    elo = board["elo"]
    assert elo["tracked"][:2] == ["main", "me"]
    assert set(elo["series"]) == set(elo["tracked"])
    assert all(len(v) == 3 for v in elo["series"].values())
    assert snap["main"] == "live-main"  # league working id, not a champion
    assert all("nash" not in m for m in snap["members"])  # Nash retired
    assert snap["members"][0]["role"] in ("main", "challenger")
    assert "share" in snap["members"][0]


def test_snapshot_memo_reuses_and_invalidates(tmp_path):
    import archive
    import dashboard

    base = _mini_league(tmp_path / "archive")
    first = dashboard.snapshot(base)
    assert dashboard.snapshot(base) == first  # memo hit: same content
    archive.log_game(base, "main", "eval", "main", "g000", 2, 2,
                     "games/g9/logs/0.replay", map="m", game="gid-new")
    second = dashboard.snapshot(base)
    assert second["game_total"] == first["game_total"] + 1  # miss: rebuilt


def test_running_elo_streaming_extend_matches_rebuild(tmp_path):
    import dashboard

    base = _mini_league(tmp_path / "archive", n_games=8, k=4)
    s1 = dashboard.snapshot(base)["board"]["elo"]
    _mini_league(base, n_games=4, k=4, start=100)  # same dir, more games
    # league.json rewrite resets snapshot_every identically; games append.
    s2 = dashboard.snapshot(base)["board"]["elo"]
    assert s2["series"]["main"][:2] == s1["series"]["main"]
    assert len(s2["series"]["main"]) == 3


@pytest.mark.slow
def test_running_board_perf_real_archive():
    import time

    import dashboard

    base = Path("/home/abrai/projects/ants-ai/ml/archive")
    if not (base / "history.jsonl").exists():
        pytest.skip("no live archive here")
    for c in (dashboard._interval_elo_cache, dashboard._snapshot_cache,
              dashboard._games_cache,
              dashboard._grouped_cache, dashboard._history_cache):
        c.clear()
    t0 = time.time()
    snap = dashboard.snapshot(base)
    cold = time.time() - t0
    n_interval = snap["intervals"]["n"]
    assert n_interval > 100
    t0 = time.time()
    dashboard.snapshot(base)
    warm = time.time() - t0
    print(f"\nrunning board: cold {cold:.1f}s warm {warm:.2f}s")
    assert cold < 60  # cold-start budget; actuals reported at review
    assert warm < 10


def test_concurrent_snapshots_never_race(tmp_path):
    """ThreadingHTTPServer polls in threads: concurrent snapshots must
    queue, never KeyError on a half-cleared memo."""
    from concurrent.futures import ThreadPoolExecutor

    import dashboard

    base = tmp_path / "arch"
    base.mkdir()
    _mini_league(base, n_games=16, k=4)
    dashboard._interval_elo_cache.clear()
    dashboard._snapshot_cache.clear()
    with ThreadPoolExecutor(max_workers=4) as ex:
        boards = list(ex.map(lambda _: dashboard.snapshot(base)["board"],
                             range(4)))
    first = json.dumps(boards[0], sort_keys=True)
    assert all(json.dumps(b, sort_keys=True) == first for b in boards)
