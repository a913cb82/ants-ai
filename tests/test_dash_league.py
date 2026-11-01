"""League dashboard contracts (phase 4 of ml/runs/plan-league.md).

Pins the backend the rework stands on, all on a synthetic league.json:
interval bucketing (game order // K, K from league.json snapshot_every),
anchor panel, anchor-trend + admissions rendering, pool-health math,
scheduler-state strip, member role + sampling share. No training code,
no live archive.
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


def _league_base(base, k=4, anchors=("g000", "g009"), games=8):
    """Synthetic league archive: league.json + logged learner games."""
    import archive

    archive.init(base)
    g000 = archive.save_checkpoint(base, {}, role="main", parent=None)
    archive.set_champion(base, g000)
    archive.init_league(base, "live-main", list(anchors))
    st = archive.load_league(base)
    st["snapshot_every"] = k
    # production ensure fills bare slot ids (see ensure_league top-up).
    for _slot, _exp in st.get("exploiters", {}).items():
        _exp["id"] = _slot
    archive.save_league(base, st)
    for i in range(games):
        learner = "main" if i % 2 == 0 else "me"
        archive.log_game(base, learner, "eval", learner, "g000",
                         3 if i % 3 else 1, 1,
                         f"games/g{i}/logs/0.replay", map="m",
                         game=f"gid-{i}")
        archive.record_result(base, learner, "g000", 3 if i % 3 else 1, 1)
    return base


# --- interval bucketing contract ---

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


# --- anchor panel contract ---

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
    import archive

    state = archive.load_league(base)
    # Fresh league.json has bare slot ids: main + slots + anchors.
    grouped = dashboard.cached_grouped(base)
    assert dashboard.tracked_members(base, grouped) == \
        ["main", "me", "le-a", "le-b", "g000", "g009"]


# --- anchor-trend card ---

def test_anchor_trend_main_vs_ladder_per_snapshot(tmp_path):
    import archive
    import dashboard

    base = _league_base(tmp_path / "a", anchors=["g000", "g009"])
    state = archive.load_league(base)
    state["main_snapshots"] = ["s1", "s2"]
    archive.save_league(base, state)
    archive.record_anchor(base, "s1", "live-main", "g000", 2, 0, 0)
    archive.record_anchor(base, "s2", "live-main", "g000", 1, 0, 1)
    archive.record_anchor(base, "s2", "live-main", "g009", 0, 2, 0)
    trend = dashboard.anchor_trend(base, archive.load_league(base))
    assert trend["snapshots"] == ["s1", "s2"]
    assert trend["anchors"] == ["g000", "g009"]
    assert trend["series"]["g000"] == [1.0, 0.75]
    assert trend["series"]["g009"] == [None, 0.0]  # unmeasured: gap


# --- admissions card ---

def test_admissions_log_flows_to_snapshot_and_page(tmp_path):
    import archive
    import dashboard

    base = _league_base(tmp_path / "a")
    archive.record_admission(base, "adm-x", "me", 240, "25-10-5")
    archive.record_admission(base, "adm-y", "le", 320, "24-8-8")
    snap = dashboard.snapshot(base)
    assert [a["id"] for a in snap["admissions"]] == ["adm-x", "adm-y"]
    assert snap["admissions"][0] == {"id": "adm-x", "role": "me",
                                     "at_game": 240, "record": "25-10-5"}
    page = dashboard.render_page(snap)
    assert "adm-x" in page and "adm-y" in page
    assert "25-10-5" in page


# --- pool-health card ---

def test_pool_health_share_newcomers_and_roles(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "a", games=8)
    snap = dashboard.snapshot(base)
    pool = snap["pool"]
    assert pool["total"] == len(snap["members"])
    assert pool["by_role"]["main"] == 1  # g000; roles flow through
    top = pool["top20"]
    assert top["top_n"] == 20
    assert top["share"] == 1.0  # 3 seated ids, all inside the top 20
    assert top["covered"] == top["total"]
    assert "g000" in pool["newcomers"]  # 8 games logged, <10: new face
    assert pool["newcomer_count"] == len(pool["newcomers"])
    page = dashboard.render_page(snap)
    assert "newcomer queue" in page


def test_sampling_share_concentration_math():
    import dashboard

    games = [_game("hot", 3, f"o{i}", 1) for i in range(8)]
    games += [_game("cold", 1, "o8", 0)]
    share = dashboard.sampling_share(games, top_n=1)
    assert share["share"] == 8 / 18  # hot's appearances over all seats


# --- scheduler-state strip ---

def test_scheduler_strip_current_learner_and_records(tmp_path):
    import archive
    import dashboard

    base = _league_base(tmp_path / "a")
    archive.note_micro_batch(base, 3)
    archive.note_exploiter_game(base, "me", 1.0, target="live-main",
                               member_id="m1")
    archive.note_exploiter_game(base, "me", 0.5, target="live-main")
    snap = dashboard.snapshot(base)
    strip = snap["league"]
    assert strip["learner"] == "main"  # scheduler_pos 0
    assert strip["main_id"] == "live-main"
    assert strip["progress"] == 3
    assert strip["micro_size"] == 8
    me = strip["exploiters"]["me"]
    assert me["id"] == "m1" and me["games"] == 2
    assert me["record"] == "1-1-0" and me["rate"] == 0.75
    page = dashboard.render_page(snap)
    assert "1-1-0" in page  # live exploiter record in the strip


def test_window_record_counts_wdl():
    import dashboard

    assert dashboard.window_record([1.0, 1.0, 0.5, 0.0]) == ("2-1-1", 0.625)
    assert dashboard.window_record([]) == ("0-0-0", None)


# --- member table: role + sampling share, no Nash ---

def test_member_table_role_and_share_no_nash(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "a", games=8)
    snap = dashboard.snapshot(base)
    assert snap["members"], "population must render"
    for m in snap["members"]:
        assert "role" in m and "share" in m
        assert "nash" not in m
    g000 = next(m for m in snap["members"] if m["id"] == "g000")
    assert g000["role"] == "main"
    assert g000["share"] == 0.5  # every game seats g000: 8/16 seats
    page = dashboard.render_page(snap)
    assert ">share</th>" in page and ">nash</th>" not in page


# --- history rows: snapshots + legacy gens ---

def test_history_rows_unify_snapshot_and_gen(tmp_path):
    import dashboard
    import selfplay

    base = _league_base(tmp_path / "a")
    selfplay.append_history(base, {"challenger": "g001", "champion": "g000",
                                   "train": {"losses": [0.5],
                                             "mean_return": 1.0},
                                   "eval": {"wins": 3, "draws": 0, "games": 6,
                                            "win_rate": 0.5, "margins": [1],
                                            "mean_margin": 1.0}})
    selfplay.append_history(base, {"snapshot": "s7", "learner": "me",
                                   "games": 40, "tick": 9, "anchors": None})
    rows = dashboard.history_rows(dashboard.cached_history(base), base)
    assert [r["kind"] for r in rows] == ["snapshot", "gen"]  # newest first
    assert rows[0]["id"] == "s7" and rows[0]["learner"] == "me"
    assert rows[1]["id"] == "g001" and rows[1]["train_return"] == 1.0
