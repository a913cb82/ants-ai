"""Red-first tests for the 7-curve progress board (impl/curves).

Every new computation gets a test before the implementation exists:
BT-Elo fit, knock/conversion windows, decisiveness, margin quantiles,
PG ratio, value slope, tenure strip, crown typing, regime boundary.
R1/R2/R3 revisions: train+eval BT duel, knock marks, entropy norm.
"""
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))


def _h(challenger, champion="g000", promoted=False, wins=0, draws=0,
       games=0, margins=None, train=None, nash=None):
    margins = margins if margins is not None else [0] * games
    ev = {"wins": wins, "draws": draws, "games": games,
          "win_rate": (wins + 0.5 * draws) / games if games else 0.0,
          "margins": margins,
          "mean_margin": sum(margins) / len(margins) if margins else 0.0}
    return {"challenger": challenger, "champion": champion,
            "promoted": promoted, "train": train or {},
            "eval": ev, "nash": nash or {}, "config": {}}


def test_running_elo_orders_transitive_panel():
    import dashboard

    ids = ["g000", "a", "b", "c"]
    per_gen = [{(1, 2): [3.0, 0.0]}, {(2, 3): [3.0, 0.0]}]
    hist = [{"challenger": "a", "champion": "g000"},
            {"challenger": "b", "champion": "g000"}]
    s = dashboard.running_elo(hist, ids, per_gen)
    assert s["cand"][0] > s["cand"][1] > 0  # a beat b, b beat c


def test_running_elo_draws_shrink_and_empty_stays_zero():
    import dashboard

    ids = ["g000", "a", "b", "lonely"]
    per_gen = [{(1, 2): [2.0, 2.0]}, {}]
    hist = [{"challenger": "a", "champion": "g000"},
            {"challenger": "lonely", "champion": "g000"}]
    s = dashboard.running_elo(hist, ids, per_gen)
    assert s["cand"][0] == s["champ"][0] == 0.0  # all-square draw
    assert s["cand"][1] == 0.0  # lonely never plays: exactly zero


def test_running_elo_zero_is_g000_pinned():
    import dashboard

    ids = ["g000", "x"]
    per_gen = [{(0, 1): [0.0, 4.0]}]  # x sweeps g000 4-0
    hist = [{"challenger": "x", "champion": "g000"}]
    s = dashboard.running_elo(hist, ids, per_gen)
    assert s["refs"]["g000"] == [0.0]  # pinned zero never moves
    assert s["cand"][0] > 100  # decisive sweep reads as a large gap


def test_panel_is_bc_plus_last_three_deposed():
    import dashboard

    hist = [_h("g001", "g000"), _h("g002", "g000", True, 4, 0, 6),
            _h("g003", "g002"), _h("g004", "g002", True, 5, 0, 6),
            _h("g005", "g004", True, 5, 0, 6),
            _h("g006", "g005", True, 5, 0, 6)]
    panel = dashboard.panel_ids(hist)
    assert panel[0] == "g000"
    assert panel[1:] == ["g002", "g004", "g005"]  # last three deposed


def test_knock_conversion_windowing():
    import dashboard

    hist = [_h(f"g{i:03d}", wins=3, draws=0, games=6,
               margins=[1] * 3 + [-1] * 3,  # eff .50 -> knock
               ) for i in range(4)]
    hist[1]["promoted"] = True
    hist[3]["promoted"] = True
    k = dashboard.knock_conversion(hist, window=4)
    assert k["rate"][-1] == 1.0
    assert k["conv"][-1] == 0.5  # 2 promos of 4 knocks
    assert k["lo"][-1] <= 1.0 <= k["hi"][-1]
    assert k["clo"][-1] <= 0.5 <= k["chi"][-1]


def test_conversion_none_without_knocks():
    import dashboard

    hist = [_h(f"g{i:03d}", wins=0, draws=0, games=6,
               margins=[-1] * 6) for i in range(3)]
    k = dashboard.knock_conversion(hist, window=3)
    assert k["rate"][-1] == 0.0
    assert k["conv"][-1] is None


def test_decisiveness_train_and_eval():
    import dashboard

    games = [
        {"gen": "g001", "kind": "train",
         "seats": [{"id": "a", "score": 3}, {"id": "b", "score": 1}]},
        {"gen": "g001", "kind": "train",
         "seats": [{"id": "a", "score": 2}, {"id": "b", "score": 2}]},
        {"gen": "g002", "kind": "train",
         "seats": [{"id": "a", "score": 1}, {"id": "b", "score": 1},
                   {"id": "c", "score": 1}]},
    ]
    hist = [_h("g001", margins=[2, 0, -1]), _h("g002", margins=[0, 0])]
    d = dashboard.decisiveness(hist, games, window=2)
    assert d["train"][0] == 0.5 and d["train"][1] == 0.0
    assert d["eval"][0] == 2 / 3 and d["eval"][1] == 0.0
    assert d["train_ma"][1] == 0.25  # mean of last two windows-worth


def test_margin_quantiles():
    import dashboard

    hist = [_h("g001", margins=[-3, -1, 0, 2, 4])]
    m = dashboard.margin_band(hist, window=1)
    assert m["med"][0] == 0
    assert m["q1"][0] == -2.0 and m["q3"][0] == 3.0  # linear interp


def test_margin_band_pools_window():
    import dashboard

    hist = [_h("g001", margins=[10, 10]), _h("g002", margins=[-10, -10])]
    m = dashboard.margin_band(hist, window=2)
    assert m["med"][1] == 0.0


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


def test_tenure_resets_on_turnover_and_entropy():
    import dashboard

    hist = [_h("g001", nash={"a": 1.0}),
            _h("g002", promoted=True, nash={"a": 0.5, "b": 0.5}),
            _h("g003", nash={"a": 0.5, "b": 0.5})]
    t = dashboard.reign_strip(hist)
    assert t["tenure"] == [1, 0, 1]
    assert t["turnover"] == [0, 1, 0]
    assert t["entropy"][0] == 0.0
    assert abs(t["entropy"][1] - math.log(2)) < 1e-9


def test_crown_typing():
    import dashboard

    complete = _h("g010", promoted=True, wins=4, draws=1, games=6,
                  margins=[2, 1, 0, 3, -1, 1])
    soft_drawish = _h("g011", promoted=True, wins=1, draws=5, games=6,
                      margins=[1, 0, 0, 0, 0, -1])
    soft_negative = _h("g012", promoted=True, wins=3, draws=0, games=6,
                       margins=[1, 1, 1, -2, -2, -2])
    held = _h("g013", wins=1, draws=1, games=6,
              margins=[1, -1, 0, 0, -2, -3])
    assert dashboard.crown_type(complete) == "complete"
    assert dashboard.crown_type(soft_drawish) == "soft"
    assert dashboard.crown_type(soft_negative) == "soft"
    assert dashboard.crown_type(held) == "—"


def test_nplayer_boundary_from_grouped_games():
    import dashboard

    games = [
        {"gen": "g001", "kind": "train",
         "seats": [{"id": "a", "score": 1}, {"id": "b", "score": 0}]},
        {"gen": "g002", "kind": "train",
         "seats": [{"id": "a", "score": 1}, {"id": "b", "score": 0},
                   {"id": "c", "score": 2}]},
    ]
    hist = [_h("g001"), _h("g002")]
    assert dashboard.nplayer_start(hist, games) == 1


def test_snapshot_board_present_and_old_keys_stable(tmp_path):
    import archive
    import dashboard
    import selfplay

    base = tmp_path / "archive"
    a = archive.save_checkpoint(base, {}, role="main", parent=None)
    b = archive.save_checkpoint(base, {}, role="challenger", parent=a)
    archive.set_champion(base, a)
    archive.log_game(base, "g001", "eval", a, b, 3, 1,
                     "games/g001/eval0/logs/0.replay")
    archive.record_result(base, a, b, 3, 1)
    selfplay.append_history(base, {
        "challenger": "g001", "champion": a, "promoted": True,
        "train": {"losses": [0.5, 0.4], "mean_return": 1.0,
                  "pg_loss": [0.3, 0.2], "pg_abs": [1.0, 0.9],
                  "entropies": [0.8, 0.7], "v_loss": [1.0, 0.6]},
        "eval": {"wins": 4, "draws": 0, "games": 6, "win_rate": 4 / 6,
                 "margins": [2, 1, 3, -1, 2, 1], "mean_margin": 1.0},
        "nash": {a: 0.4, b: 0.6}, "config": {}})
    snap = dashboard.snapshot(base)
    assert {"loss", "ret", "ids"} <= set(snap["curves"])  # old keys stay
    board = snap["board"]
    for key in ("ids", "elo", "knock", "decisive", "margin", "pg",
                "vslope", "reign", "regimes"):
        assert key in board, key
    assert board["ids"] == ["g001"]
    assert board["elo"]["panel"][0] == "g000"
    assert snap["generations"][0]["crown"] == "complete"


# --- R1: train+eval BT duel ---

def test_merge_pairs_sums_overlap():
    import dashboard

    ev = {"a vs b": [3.0, 1.0]}
    tr = {"a vs b": [1.0, 1.0], "b vs c": [2.0, 0.0]}
    m = dashboard.merge_pairs(ev, tr)
    assert m["a vs b"] == [4.0, 2.0]
    assert m["b vs c"] == [2.0, 0.0]


def test_running_elo_sees_train_only_members():
    import dashboard

    ids = ["g000", "x", "lonely"]
    # lonely's only games are a 4-0 sweep of x, logged merged per gen.
    # buckets key (i,j) stores [wins_i, wins_j]: x=0, lonely=4.
    per_gen = [{(1, 2): [0.0, 4.0]}]
    hist = [{"challenger": "lonely", "champion": "g000"}]
    s = dashboard.running_elo(hist, ids, per_gen)
    assert s["cand"][0] > s["champ"][0]  # sweep moves it at once
    assert s["cand"][0] > 50


def test_running_elo_duel_candidate_above_champ_pre_promotion():
    import dashboard

    ids = ["g000", "g001", "g002", "g003"]
    per_gen = [{(0, 1): [0.0, 5.0]}, {(1, 2): [0.0, 5.0]}]
    hist = [{"challenger": "g001", "champion": "g000",
             "promoted": True},
            {"challenger": "g002", "champion": "g001"}]
    s = dashboard.running_elo(hist, ids, per_gen)
    assert s["cand"][0] > s["champ"][0]  # g001 takes the crown
    assert s["cand"][1] > s["champ"][1]  # staircase: g002 takes it


def test_turn_mismatch_ranges():
    import dashboard

    hist = [_h("g001"), _h("g002"), _h("g003")]
    hist[0]["config"] = {"turns": 60, "eval_turns": 150}
    hist[1]["config"] = {"turns": 60, "eval_turns": 150}
    hist[2]["config"] = {"turns": 150, "eval_turns": None}
    mm = dashboard.turn_mismatch(hist)
    assert mm == [{"from": "g001", "to": "g002",
                   "train_turns": 60, "eval_turns": 150}]


# --- R2: knock marks lane ---

def test_knock_marks_binary_per_gen():
    import dashboard

    hist = [_h("g001", wins=0, draws=0, games=6, margins=[-1] * 6),
            _h("g002", wins=3, draws=0, games=6, margins=[1] * 6),
            _h("g003")]  # no eval: None, not 0
    k = dashboard.knock_conversion(hist, window=2)
    assert k["knock"] == [0, 1, None]
    assert k["rate"][0] == 0.0  # drought reads zero
    assert k["rate"][1] == 0.5


# --- R3: entropy normalization + readout ---

def test_norm01_spans_min_max():
    import dashboard

    got = dashboard.norm01([0.004, 0.2, 3.891, None])
    assert got[0] == 0.0 and got[2] == 1.0 and got[3] is None
    assert abs(got[1] - 0.0504) < 1e-3  # (0.2-0.004)/(3.891-0.004)
    assert dashboard.norm01([5.0, 5.0]) == [0.5, 0.5]  # constant: mid-lane
    assert dashboard.norm01([None, None]) == [None, None]


def test_reign_readout_names_current_and_best():
    import dashboard

    hist = [_h("g001"), _h("g002", promoted=True), _h("g003")]
    t = dashboard.reign_strip(hist)
    assert t["tenure"] == [1, 0, 1]
    assert t["readout"] == "tenure 1 · best 1"
    assert t["entropy_n"] == [None, None, None]


def test_page_has_board_canvases_and_no_old_curves():
    import dashboard

    page = dashboard.render_page()
    for cid in ("ch-elo", "ch-knock-marks", "ch-knock", "ch-dec", "ch-marg",
                "ch-pg", "ch-vslope", "ch-tenure", "ch-entlane",
                "tenure-now", "elo-turn"):
        assert cid in page, cid
    assert "ch-loss" not in page and "ch-ret" not in page


def test_snapshot_duel_cand_above_champ(tmp_path):
    import archive
    import dashboard
    import selfplay

    base = tmp_path / "archive"
    a = archive.save_checkpoint(base, {}, role="main", parent=None)
    b = archive.save_checkpoint(base, {}, role="challenger", parent=a)
    archive.set_champion(base, a)
    archive.record_result(base, b, a, 5, 1)  # eval: challenger takes it
    archive.record_result(base, b, a, 4, 0, kind="train")  # train agrees
    archive.log_game(base, b, "eval", b, a, 5, 1,
                     "games/g001/eval0/logs/0.replay", map="m",
                     game="games/g001/eval0#e1")
    archive.log_game(base, b, "train", b, a, 4, 0,
                     "games/g001/train0/logs/0.replay", map="m",
                     game="games/g001/train0#t1")
    selfplay.append_history(base, {
        "challenger": b, "champion": a, "promoted": True,
        "train": {"losses": [0.5], "mean_return": 1.0},
        "eval": {"wins": 5, "draws": 0, "games": 6, "win_rate": 5 / 6,
                 "margins": [2, 1, 3, -1, 2, 1], "mean_margin": 1.0},
        "nash": {a: 0.3, b: 0.7}, "config": {}})
    snap = dashboard.snapshot(base)
    elo = snap["board"]["elo"]
    assert elo["cand"][0] > elo["champ"][0]  # staircase: above pre-crown
    assert elo["turn_note"] == []  # matching turns: nothing to disclose


# --- running Elo: one sequential pass, gen 0 -> G (no windows/refits) ---

def _mini_history(base, n_gens, tag="c"):
    """Tiny archive: every challenger beats the champ 3-1 in train+eval."""
    import archive
    import selfplay

    g000 = archive.save_checkpoint(base, {}, role="main", parent=None)
    archive.set_champion(base, g000)
    champ = g000
    for i in range(1, n_gens + 1):
        cid = f"{tag}{i:03d}"
        archive.save_checkpoint(base, {}, role="challenger", parent=champ)
        for kind in ("train", "eval"):
            archive.log_game(base, cid, kind, cid, champ, 3, 1,
                             f"games/{cid}/{kind}0/logs/0.replay", map="m",
                             game=f"games/{cid}/{kind}0#{kind}{i}")
            archive.record_result(base, cid, champ, 3, 1,
                                  kind=kind if kind == "eval" else "train")
        promoted = (i % 2 == 0)
        selfplay.append_history(base, {
            "challenger": cid, "champion": champ, "promoted": promoted,
            "train": {"losses": [0.5], "mean_return": 1.0},
            "eval": {"wins": 1, "draws": 0, "games": 1, "win_rate": 1.0,
                     "margins": [2], "mean_margin": 2.0},
            "nash": {}, "config": {}})
        if promoted:
            champ = cid
            archive.set_champion(base, champ)
    return g000


def test_running_elo_same_games_same_values():
    import dashboard

    # No windows anymore: the pass reads each gen's games at once.
    # Same games -> same values (the old step-held constancy).
    ids = ["g000", "c001", "c002"]
    per_gen = [{(0, 1): [3.0, 1.0]}, {}, {}]
    hist = [{"challenger": "c001", "champion": "g000"},
            {"challenger": "c001", "champion": "g000",
             "promoted": True},
            {"challenger": "c002", "champion": "c001"}]
    s = dashboard.running_elo(hist, ids, per_gen)
    assert s["cand"][0] == s["cand"][1]  # same games (gen 0 only)
    assert abs(s["champ"][2] - s["cand"][1]) < 0.01  # crowned converges


def test_duel_candidate_uses_own_gen_games():
    """The rail bug: a candidate whose whole career is gen G must rate
    from gen G's games, not sit at the unseen-member prior."""
    import dashboard

    ids = ["g000", "c001", "c002", "c003"]
    # c001 sweeps c002 10-0 in gen 1, c003 never plays at all.
    per_gen = [{}, {(1, 2): [10.0, 0.0]}, {}]
    hist = [{"challenger": "c001", "champion": "g000"},
            {"challenger": "c001", "champion": "g000"},
            {"challenger": "c003", "champion": "g000"}]
    s = dashboard.running_elo(hist, ids, per_gen)
    assert s["cand"][1] > 50  # 10-0 sweep rates far above any prior rail
    assert s["cand"][2] != s["cand"][1]  # gameless c003 sits elsewhere


def test_duel_champ_turnover_immediate():
    """A champ crowned mid-window rates from its games at once."""
    import dashboard

    ids = ["g000", "c001"]
    per_gen = [{}, {(0, 1): [0.0, 8.0]}]  # c001 sweeps g000 8-0 in gen 1
    hist = [{"challenger": "c001", "champion": "g000",
             "promoted": True},
            {"challenger": "c002", "champion": "c001"}]
    s = dashboard.running_elo(hist, ids, per_gen)
    assert s["champ"][1] > 50


def test_running_elo_prefix_stable():
    import dashboard

    ids = ["g000", "c001", "c002"]
    full = [{(0, 1): [3.0, 1.0]}, {(0, 2): [0.0, 4.0]}, {(1, 2): [2.0, 2.0]}]
    hist = [{"challenger": "c001", "champion": "g000"},
            {"challenger": "c002", "champion": "g000"},
            {"challenger": "c002", "champion": "g000"}]
    a = dashboard.running_elo(hist, ids, full)
    b = dashboard.running_elo(hist[:2], ids, full[:2])
    # later games never move earlier ratings (bitwise: same trajectory).
    assert a["cand"][:2] == b["cand"]
    assert a["champ"][:2] == b["champ"]


def test_running_elo_g000_pinned():
    import dashboard

    ids = ["g000", "c001"]
    per_gen = [{(0, 1): [1.0, 3.0]}]
    hist = [{"challenger": "c001", "champion": "g000"}]
    s = dashboard.running_elo(hist, ids, per_gen)
    assert s["refs"]["g000"] == [0.0]  # the zero never moves
    assert s["cand"][0] > 0  # 3-1 winner above the g000 zero


def test_running_elo_seed_indifferent():
    import dashboard

    # Same games, hostile seeds: everyone descends from the strongest
    # member. The anchor sets the scale, so seeds wash out and gaps
    # agree (the old gauge lock would have baked the seed into G0).
    ids = ["g000", "a", "b", "c"]
    per_gen = [{(0, 1): [0.0, 4.0]}, {(1, 2): [3.0, 1.0]},
               {(2, 3): [1.0, 3.0]}]
    hist = [{"challenger": "a", "champion": "g000"},
            {"challenger": "b", "champion": "g000"},
            {"challenger": "c", "champion": "g000"}]
    plain = dashboard.running_elo(hist, ids, per_gen)
    seeded = dashboard.running_elo(
        hist, ids, per_gen,
        parents={"a": "c", "b": "c", "c": "c"})
    for p, q in zip(plain["cand"], seeded["cand"]):
        assert abs(p - q) < 5.0  # sub-display agreement, hostile seeds


def test_running_elo_unplayed_challenger_carries_parent():
    import dashboard

    # par sweeps g000 4-0, then kid challenges but logs no games.
    # With lineage, kid reads par's carried level (continuing entity),
    # not the 0.0 default.
    ids = ["g000", "par", "kid"]
    per_gen = [{(0, 1): [0.0, 4.0]}, {}]
    hist = [{"challenger": "par", "champion": "g000"},
            {"challenger": "kid", "champion": "g000"}]
    assert dashboard.running_elo(hist, ids, per_gen)["cand"][1] == 0.0
    s = dashboard.running_elo(hist, ids, per_gen,
                               parents={"par": "g000", "kid": "par"})
    assert abs(s["cand"][1] - s["cand"][0]) < 1e-9
    assert s["cand"][1] > 100  # par's swept level, carried forward


def test_running_elo_twin_archives_agree_on_shared_gens(tmp_path):
    import dashboard

    full = tmp_path / "full"
    trunc = tmp_path / "trunc"
    full.mkdir()
    trunc.mkdir()
    _mini_history(full, 35)
    _mini_history(trunc, 20)
    sf = dashboard.snapshot(full)
    st = dashboard.snapshot(trunc)
    ef, et = sf["board"]["elo"], st["board"]["elo"]
    for k in ("cand", "champ"):
        for a, b in zip(ef[k][:20], et[k][:20]):
            assert (a is None and b is None) or abs(a - b) < 1e-9
    # staircase: every challenger beats the champ 3-1, so the candidate
    # reads above the champ at the shared gens (no window lag anymore).
    assert ef["cand"][30] > ef["champ"][30]


@pytest.mark.slow
def test_running_elo_board_perf_real_archive():
    import time

    import dashboard

    base = Path("/home/abrai/projects/ants-ai/ml/archive")
    if not (base / "history.jsonl").exists():
        pytest.skip("no live archive here")
    for c in (dashboard._elo_cache, dashboard._nash_cache,
              dashboard._games_cache,
              dashboard._grouped_cache, dashboard._history_cache):
        c.clear()
    t0 = time.time()
    snap = dashboard.snapshot(base)
    cold = time.time() - t0
    assert len(snap["board"]["elo"]["cand"]) > 1000
    t0 = time.time()
    dashboard.snapshot(base)
    warm = time.time() - t0
    print(f"\nrunning board: cold {cold:.1f}s warm {warm:.2f}s")
    assert cold < 60  # cold-start budget; actuals reported at review
    assert warm < 10


def test_running_elo_streaming_extend_matches_rebuild(tmp_path):
    import dashboard

    base = tmp_path / "arch"
    base.mkdir()
    _mini_history(base, 20, tag="c")
    s1 = dashboard.snapshot(base)["board"]["elo"]
    _mini_history(base, 15, tag="d")  # same dir, more gens (d016..d030)
    s2 = dashboard.snapshot(base)["board"]["elo"]
    assert s2["cand"][:20] == s1["cand"][:20]  # extend continues theta
    assert s2["champ"][:20] == s1["champ"][:20]
    assert len(s2["cand"]) == 35


def test_concurrent_snapshots_never_race(tmp_path):
    """ThreadingHTTPServer polls in threads: concurrent snapshots must
    queue, never KeyError on a half-cleared memo (the 10s cold build
    widens the old clear-then-fill race into a certainty)."""
    import dashboard
    from concurrent.futures import ThreadPoolExecutor

    base = tmp_path / "arch"
    base.mkdir()
    _mini_history(base, 12)
    dashboard._nash_cache.clear()
    dashboard._elo_cache.clear()
    with ThreadPoolExecutor(max_workers=4) as ex:
        boards = list(ex.map(lambda _: dashboard.snapshot(base)["board"],
                             range(4)))
    first = json.dumps(boards[0], sort_keys=True)
    assert all(json.dumps(b, sort_keys=True) == first for b in boards)
