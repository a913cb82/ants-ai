"""Dashboard page contract: new snapshot keys, cards, replay links, poll.

New contract (build/dashboard2): snapshot keys are exactly
{h0, anchors, standings, bars, pairs, behavior, games, game_total,
alerts, mtime}. Legacy keys (board/members/pool/history/anchor_trend/
league/admissions/maps/main/counts/status, train_return/train_loss/
champ/cand/top20/newcomer/whisker) are gone. Page cards: sticky H0
strip, anchor ladder canvas, standings+bars, attention queue,
pair matrix + behavior table, recent games. Zero-JS first paint.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

NEW_KEYS = {"h0", "anchors", "standings", "bars", "pairs", "behavior",
            "games", "game_total", "alerts", "mtime"}
LEGACY_KEYS = {"main", "members", "league", "admissions", "anchor_trend",
               "pool", "intervals", "board", "history", "maps", "status",
               "counts", "train_return", "train_loss", "champ", "cand",
               "top20", "newcomer", "whisker", "conv", "decisive", "margin"}


def _league_base(base, games=4):
    import archive

    archive.init(base)
    archive.save_checkpoint(base, {}, role="main", parent=None)
    archive.init_league(base, "live-main", ["g000"])
    st = archive.load_league(base)
    for _slot, _exp in st.get("exploiters", {}).items():
        _exp["id"] = _slot
    archive.save_league(base, st)
    for i in range(games):
        learner = "main" if i % 2 == 0 else "me"
        archive.log_game(base, learner, "eval", learner, "g000",
                         3 if i % 3 else 1, 1,
                         f"games/g{i}/logs/0.replay", map="m",
                         game=f"gid-{i}", tick=i,
                         food=[2, 1], kills=[1, 0], army=[5, 4],
                         length=120)
        archive.record_result(base, learner, "g000", 3 if i % 3 else 1, 1)
    return base


def test_archive_mtime_missing_is_zero(tmp_path):
    import dashboard

    assert dashboard.archive_mtime(tmp_path / "nope") == 0


def test_snapshot_keys_new_only(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "archive")
    snap = dashboard.snapshot(base)
    assert set(snap) == NEW_KEYS
    assert not (set(snap) & LEGACY_KEYS)


def test_snapshot_h0_shape(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "archive")
    h0 = dashboard.snapshot(base)["h0"]
    assert set(h0) == {"tick", "learners",
                       "games_per_h", "secs_since_game",
                       "anchor_verdict"}
    assert h0["tick"] == 0
    assert h0["learners"] == ["main"]
    assert h0["anchor_verdict"] in ("new-high", "flat", "down")


def test_first_paint_has_new_cards_and_named_replays(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "archive")
    snap = dashboard.snapshot(base)
    page = dashboard.render_page(snap)
    for cid in ("h0", "ch-ladder", "standings-body", "bars-body",
                "alerts", "behavior-body", "games-body"):
        assert cid in page, cid
    # no legacy cards survive
    for cid in ("ch-conv", "ch-dec", "ch-marg", "league-body",
                "admit-body", "pool-summary", "pop-body", "hist-body",
                "maps-body", "ch-elo", "ch-anchor"):
        assert cid not in page, cid
    # replay links name the bots (display == id) and open in a new tab
    assert "main" in page and "g000" in page
    assert 'target="_blank"' in page
    # server-rendered without JS: H0 numbers and a game row are inline
    assert "games/g0/logs/0.replay" in page


def test_first_paint_empty_archive_has_skeleton(tmp_path):
    import dashboard

    page = dashboard.render_page(None)
    assert "loading" in page
    assert "h0" in page and "ch-ladder" in page


def test_is_fresh_logic(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "archive")
    mtime = dashboard.archive_mtime(base)
    assert dashboard.is_fresh(base, mtime) is True
    assert dashboard.is_fresh(base, mtime - 1) is False
    assert dashboard.is_fresh(base, None) is False
    assert dashboard.is_fresh(base, "bogus") is False


def test_http_since_shortcircuit_and_member_empty(tmp_path):
    import http.server
    import threading
    import urllib.request

    import dashboard

    base = _league_base(tmp_path / "archive")
    srv = dashboard.make_handler(base)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), srv)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        root = f"http://127.0.0.1:{httpd.server_address[1]}"
        snap = json.load(urllib.request.urlopen(root + "/api/snapshot",
                                                timeout=5))
        assert set(snap) == NEW_KEYS
        tiny = json.load(urllib.request.urlopen(
            root + f"/api/snapshot?since={snap['mtime']}", timeout=5))
        assert tiny == {"unchanged": True, "mtime": snap["mtime"]}
        stale = json.load(urllib.request.urlopen(
            root + "/api/snapshot?since=1", timeout=5))
        assert stale["h0"]["learners"] == ["main"]
        empty = json.load(urllib.request.urlopen(
            root + "/api/games?member=nobody-here", timeout=5))
        assert empty == {"total": 0, "rows": []}
        full = json.load(urllib.request.urlopen(
            root + "/api/games?member=main", timeout=5))
        assert full["total"] == 2  # main seats 2 of the 4 games
        with urllib.request.urlopen(root + "/", timeout=5) as r:
            body = r.read().decode()
        assert 'id="h0"' in body  # server-rendered first paint
    finally:
        httpd.shutdown()


def test_replay_page_title_names_replay(tmp_path):
    import dashboard

    base = tmp_path / "archive"
    (base / "games").mkdir(parents=True)
    (base / "games" / "0.replay").write_text("{}")
    page = dashboard.replay_page(base, "games/0.replay")
    assert "<title>" in page and "0.replay" in page.split("</title>")[0]
