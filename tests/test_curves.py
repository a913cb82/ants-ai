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


# --- running Elo over intervals: live entry, real archives ---

def _elo_archive(tmp_path, ids, games, K=1, parents=None, resets=(),
                 seat="t", name="elo"):
    """Minimal league archive for Elo tests: one checkpoint per id
    (returned as name -> minted-id map), one eval game per
    (a, b, result) oldest-first, league resets optional.

    result is "w"/"l"/"d" from a's side. Games log under `seat` with
    train{N} replay paths so reset entries match the live format."""
    import archive

    base = tmp_path / name
    archive.init(base)
    mid = {}
    for m in ids:
        par = (parents or {}).get(m)
        mid[m] = archive.save_checkpoint(base, {}, "main",
                                         mid[par] if par in mid else par)
    seat = mid.get(seat, seat)  # live seats are member ids
    for n, (a, b, r) in enumerate(games):
        sa, sb = {"w": (1, 0), "l": (0, 1), "d": (1, 1)}[r]
        archive.record_result(base, mid[a], mid[b], sa, sb, kind="eval")
        archive.log_game(base, seat, "eval", mid[a], mid[b], sa, sb,
                         f"games/{seat}/train{n}/logs/0.replay",
                         map="m", game=f"gid-{seat}-{n}")
    state = archive.init_league(base, mid[ids[0]], [])
    if resets:
        state["resets"] = [{**r, "seat": mid.get(r.get("seat"),
                                                 r.get("seat"))}
                           for r in resets]
        archive.save_league(base, state)
    return base, mid


def _elo_series(base, mid, tracked, K=1):
    import dashboard

    dashboard._interval_elo_cache.pop("state", None)
    raw = dashboard._interval_elo_cached(
        base, dashboard.cached_grouped(base), K,
        [mid[m] for m in tracked])["series"]
    return {m: raw[mid[m]] for m in tracked}


def test_intervals_transitive_panel(tmp_path):
    base, mid = _elo_archive(tmp_path, ["g000", "a", "b", "c"],
                        [("a", "b", "w")] * 3 + [("b", "c", "w")] * 3, K=3)
    s = _elo_series(base, mid, ["a", "b", "c"], K=3)
    assert s["a"][0] > s["b"][0]  # a beat b
    assert s["b"][1] > s["c"][1]  # b beat c


def test_intervals_draws_shrink_and_empty_stays_zero(tmp_path):
    base, mid = _elo_archive(tmp_path, ["g000", "a", "b", "lonely"],
                        [("a", "b", "d")] * 2, K=2)
    s = _elo_series(base, mid, ["a", "b", "lonely"], K=2)
    assert s["a"][0] == s["b"][0] == 0.0  # all-square
    assert s["lonely"] == [None]  # never logged: unknown gap, not zero


def test_intervals_g000_pinned(tmp_path):
    base, mid = _elo_archive(tmp_path, ["g000", "x"], [("x", "g000", "w")] * 4,
                        K=4)
    s = _elo_series(base, mid, ["g000", "x"], K=4)
    assert s["g000"] == [0.0]  # pinned zero never moves
    assert s["x"][0] > 100  # decisive sweep reads as a large gap


def test_intervals_seed_indifferent(tmp_path):
    games = ([("a", "g000", "w")] * 4 + [("a", "b", "w")] * 3 +
             [("b", "a", "w")] + [("b", "c", "w")] + [("c", "b", "w")] * 3)
    plain = _elo_archive(tmp_path, ["g000", "a", "b", "c"], games, K=4,
                         name="elo-plain")
    seeded = _elo_archive(tmp_path, ["g000", "a", "b", "c"], games, K=4,
                          parents={"a": "c", "b": "c", "c": "c"},
                          name="elo-seeded")
    p = _elo_series(*plain, ["a", "b", "c"], K=4)
    q = _elo_series(*seeded, ["a", "b", "c"], K=4)
    for m in ("a", "b", "c"):
        for u, v in zip(p[m], q[m], strict=True):
            assert abs(u - v) < 5.0  # sub-display agreement, hostile seeds


def test_intervals_unplayed_tracker_carries_parent(tmp_path):
    games = [("par", "g000", "w")] * 2 + [("kid", "g000", "l")]
    base, mid = _elo_archive(tmp_path, ["g000", "par", "kid"], games, K=1,
                        parents={"par": "g000", "kid": "par"})
    s = _elo_series(base, mid, ["par", "kid"], K=1)
    assert s["kid"][0] == 0.0  # at anchor before the parent moves
    assert s["kid"][1] == s["par"][0]  # then carries the parent's value


def test_intervals_reset_cut_drops_theta_to_seed(tmp_path):
    games = [("me", "x", "w")] * 4 + [("me", "x", "w")] * 3 + [("x", "me",
                                                                "w")]
    plain = _elo_archive(tmp_path, ["g000", "me", "x"], games, K=4,
                         seat="me", name="elo-plain")
    cut = _elo_archive(tmp_path, ["g000", "me", "x"], games, K=4,
                       seat="me", name="elo-cut",
                       resets=[{"slot": "me", "seat": "me", "game": 3,
                                "tick": 0}])
    p = _elo_series(*plain, ["me"], K=4)
    q = _elo_series(*cut, ["me"], K=4)
    assert q["me"][0] == p["me"][0]
    assert q["me"][1] < p["me"][1]
    assert q["me"][1] > 0  # fresh wins rebuild from seed


def test_intervals_empty_resets_match_no_resets(tmp_path):
    import dashboard

    games = [("me", "x", "w")] * 4 + [("me", "x", "d")] * 2
    base, mid = _elo_archive(tmp_path, ["g000", "me", "x"], games, K=4)
    first = _elo_series(base, mid, ["me"], K=4)
    second = _elo_series(base, mid, ["me"], K=4)
    assert first == second  # no resets, deterministic rebuild


def test_intervals_prefix_stable(tmp_path):
    games = ([("g000", "a", "w")] * 3 + [("a", "g000", "w")] +
             [("b", "g000", "w")] * 4 + [("a", "b", "d")] * 2)
    full = _elo_archive(tmp_path, ["g000", "a", "b"], games, K=1,
                        name="elo-full")
    pre = _elo_archive(tmp_path, ["g000", "a", "b"], games[:4], K=1,
                       name="elo-pre")
    a = _elo_series(*full, ["a", "b"], K=1)
    b = _elo_series(*pre, ["a", "b"], K=1)
    # later games never move earlier intervals (bitwise: same trajectory).
    assert a["a"][:4] == b["a"]
    assert a["b"][:4] == [0.0] * 4  # known but unplayed: carries seed
    assert b["b"] == [None] * 4  # never logged: unknown gaps


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


def _mini_league(base, n_games=12, k=4, learners=("main", "me"),
                start=0):
    """Synthetic league archive: league.json + logged learner games.

    Live games log under bare slot ids ("main", "me"), so the fixture
    seats them directly under the slots."""
    import archive

    archive.init(base)
    archive.save_checkpoint(base, {}, role="main", parent=None)
    archive.init_league(base, "live-main", ["g000"])
    st = archive.load_league(base)
    st["snapshot_every"] = k
    st["exploiters"]["me"]["id"] = "me"
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


def test_snapshot_contract_new_keys_only(tmp_path):
    import dashboard

    base = _mini_league(tmp_path / "archive")
    snap = dashboard.snapshot(base)
    assert set(snap) == {"h0", "anchors", "standings", "bars",
                            "pairs", "behavior", "games", "game_total",
                            "alerts", "mtime"}
    for legacy in ("board", "members", "pool", "history",
                     "anchor_trend", "league", "admissions", "maps",
                     "main", "status", "counts"):
        assert legacy not in snap, legacy
    # 12 games, K=4: standings Elo still runs over 3 intervals.
    rows = {r["id"]: r for r in snap["standings"]}
    assert set(rows) == {"main", "me", "le-a", "le-b"}
    assert isinstance(rows["main"]["elo"], int)
    h0 = snap["h0"]
    assert (h0["tick"], h0["game_n"], h0["learners"]) == (0, 12, ["main"])
    assert h0["games_per_h"] is None  # no wall-clock stamps logged
    assert h0["secs_since_game"] is not None and h0["secs_since_game"] >= 0
    assert h0["anchor_verdict"] == "flat"  # no anchor rows yet
    assert snap["game_total"] == 12 and len(snap["games"]) == 12
    assert snap["pairs"]  # Laplace shares over the logged pairs
    assert snap["alerts"] == [{"level": "ok", "msg": "all clear",
                                 "tick": 0}]


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
    dashboard._interval_elo_cache.pop("state", None)
    g1 = dashboard.cached_grouped(base)
    s1 = dashboard._interval_elo_cached(base, g1, 4,
                                         ["main", "me"])["series"]
    _mini_league(base, n_games=4, k=4, start=100)  # same dir, more games
    # league.json rewrite resets snapshot_every identically; games append.
    g2 = dashboard.cached_grouped(base)
    s2 = dashboard._interval_elo_cached(base, g2, 4,
                                         ["main", "me"])["series"]
    assert s2["main"][:2] == s1["main"]  # prefix Elo never moves
    assert len(s2["main"]) == 3


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
    assert snap["game_total"] > 100
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
        boards = list(ex.map(lambda _: dashboard.snapshot(base)["standings"],
                             range(4)))
    first = json.dumps(boards[0], sort_keys=True)
    assert all(json.dumps(b, sort_keys=True) == first for b in boards)
