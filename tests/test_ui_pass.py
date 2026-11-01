"""Dashboard UI beauty pass: pagination, ?since=, first paint, league cards.

Pure-logic tests + HTTP protocol tests against tmp archives. The throne
UI (champion hero, crowns, Nash) is retired; the league UI (live main,
history, share, scheduler strip, admissions, pool health) is pinned.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))


def _hist_snapshot(sid, learner="main", tick=0, games=80):
    return {"snapshot": sid, "learner": learner, "games": games,
            "tick": tick, "anchors": None}


def _hist_gen(challenger, champion="m", wins=3, draws=0, games=6,
              margins=None, mean_margin=0.0, ret=1.23456, loss=0.123456,
              finished_at=None, duration_s=None):
    margins = margins if margins is not None else [0] * games
    return {
        "challenger": challenger, "champion": champion,
        "train": {"losses": [loss], "mean_return": ret},
        "eval": {"wins": wins, "draws": draws, "games": games,
                 "win_rate": (wins + 0.5 * draws) / games if games else 0.0,
                 "margins": margins, "mean_margin": mean_margin},
        "config": {}, "finished_at": finished_at, "duration_s": duration_s}


def _write_hist(base, hist):
    base.mkdir(parents=True, exist_ok=True)
    with open(base / "history.jsonl", "w") as f:
        for h in hist:
            f.write(json.dumps(h) + "\n")


def test_archive_mtime_missing_is_zero(tmp_path):
    import dashboard

    assert dashboard.archive_mtime(tmp_path / "nope") == 0


def test_archive_mtime_tracks_newest_file(tmp_path):
    import dashboard

    base = tmp_path / "archive"
    _write_hist(base, [_hist_gen("g001")])
    (base / "games.jsonl").write_text("{}\n")
    first = dashboard.archive_mtime(base)
    assert first > 0
    (base / "matrix.json").write_text("{}")
    assert dashboard.archive_mtime(base) >= first


def test_snapshot_carries_mtime_and_rounded_numbers(tmp_path):
    import archive
    import dashboard

    base = tmp_path / "archive"
    a = archive.save_checkpoint(base, {}, role="main", parent=None)
    archive.save_checkpoint(base, {}, role="challenger", parent=a)
    _write_hist(base, [_hist_gen("g001")])
    snap = dashboard.snapshot(base)
    assert snap["mtime"] == dashboard.archive_mtime(base)
    g = snap["history"][0]
    assert g["train_return"] == 1.23  # 2dp server-side
    assert g["train_loss"] == 0.123  # 3dp server-side
    assert g["mean_margin"] == round(0.0, 2)
    assert "nash" not in snap["members"][0]  # Nash retired...
    assert "share" in snap["members"][0]  # ...replaced by sampling share


def test_is_fresh_logic(tmp_path):
    import dashboard

    base = tmp_path / "archive"
    _write_hist(base, [_hist_gen("g001")])
    mtime = dashboard.archive_mtime(base)
    assert dashboard.is_fresh(base, mtime) is True
    assert dashboard.is_fresh(base, mtime - 1) is False
    assert dashboard.is_fresh(base, None) is False
    assert dashboard.is_fresh(base, "bogus") is False


def test_maps_summary_pins_unlabelled_last():
    import dashboard

    games = [
        {"map": None, "n": 2, "kind": "train", "seats": [
            {"id": "a", "score": 1}, {"id": "b", "score": 0}],
         "pairs": [{"a": "a", "b": "b", "score_a": 1, "score_b": 0}]},
        {"map": "open.map", "n": 2, "kind": "train", "seats": [
            {"id": "a", "score": 1}, {"id": "b", "score": 0}],
         "pairs": [{"a": "a", "b": "b", "score_a": 1, "score_b": 0}]},
    ]
    maps = dashboard.summarize_maps(games)
    assert maps[-1]["map"] is None  # legacy nulls pin last
    assert maps[0]["map"] == "open.map"


def test_first_paint_has_main_history_and_league_cards(tmp_path):
    import archive
    import dashboard
    import selfplay

    base = tmp_path / "archive"
    a = archive.save_checkpoint(base, {}, role="main", parent=None)
    b = archive.save_checkpoint(base, {}, role="challenger", parent=a)
    archive.set_champion(base, a)
    archive.init_league(base, a, ["g000"])
    archive.log_game(base, "main", "eval", "main", b, 3, 1,
                     "games/main0/logs/0.replay")
    archive.record_result(base, "main", b, 3, 1)
    archive.record_admission(base, "adm1", "me", 240, "25-10-5")
    selfplay.append_history(base, _hist_snapshot("s1", tick=4))
    snap = dashboard.snapshot(base)
    assert snap["main"] == a  # live main, not a champion
    assert snap["league"]["learner"] == "main"
    assert snap["admissions"][0]["id"] == "adm1"
    page = dashboard.render_page(snap)
    assert a in page  # live main id in raw HTML, no JS needed
    assert "games/main0/logs/0.replay" in page  # first game rows
    assert "s1" in page  # history row server-rendered
    assert "adm1" in page  # admissions log server-rendered
    for cid in ("ch-elo", "ch-anchor", "ch-conv", "ch-dec", "ch-marg",
                "ch-pg", "ch-vslope", "league-body", "admit-body",
                "pool-summary"):
        assert cid in page, cid
    assert "ch-loss" not in page and "ch-ret" not in page
    assert "ch-knock" not in page and "ch-tenure" not in page


def test_first_paint_empty_archive_has_skeleton():
    import dashboard

    page = dashboard.render_page(None)
    assert "loading" in page  # skeleton/fallback copy, layout intact
    assert "ch-elo" in page


def test_status_html_league_and_anchor_branches():
    import dashboard

    line, pct = dashboard.status_html(
        {"phase": "league", "learner": "me", "opponent": "g003",
         "tick": 41, "own_games": 12, "micro": 4}, "m", 3)
    assert "me" in line and "g003" in line and "tick 41" in line
    assert pct == 0
    line, pct = dashboard.status_html(
        {"phase": "anchor", "snapshot": "s9", "anchor": "g000",
         "done": 1, "total": 2}, "m", 3)
    assert "s9" in line and "g000" in line
    assert pct == 50


def test_http_since_shortcircuit_and_member_empty(tmp_path):
    import http.server
    import threading
    import urllib.request

    import archive
    import dashboard

    base = tmp_path / "archive"
    a = archive.save_checkpoint(base, {}, role="main", parent=None)
    archive.set_champion(base, a)
    srv = dashboard.make_handler(base)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), srv)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        root = f"http://127.0.0.1:{httpd.server_address[1]}"
        snap = json.load(urllib.request.urlopen(root + "/api/snapshot",
                                                timeout=5))
        assert snap["mtime"] > 0
        tiny = json.load(urllib.request.urlopen(
            root + f"/api/snapshot?since={snap['mtime']}", timeout=5))
        assert tiny == {"unchanged": True, "mtime": snap["mtime"]}
        stale = json.load(urllib.request.urlopen(
            root + "/api/snapshot?since=1", timeout=5))
        assert stale["main"] == a  # legacy fallback: frozen record
        empty = json.load(urllib.request.urlopen(
            root + "/api/games?member=nobody-here", timeout=5))
        assert empty == {"total": 0, "rows": []}
        with urllib.request.urlopen(root + "/", timeout=5) as r:
            html = r.read().decode()
        assert a in html  # server-rendered first paint
    finally:
        httpd.shutdown()


def test_replay_page_title_names_replay(tmp_path):
    import dashboard

    base = tmp_path / "archive"
    (base / "games").mkdir(parents=True)
    (base / "games" / "0.replay").write_text("{}")
    page = dashboard.replay_page(base, "games/0.replay")
    assert "<title>" in page and "0.replay" in page.split("</title>")[0]
