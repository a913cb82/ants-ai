"""Dashboard UI beauty pass: pagination, ?since=, first paint, crowns.

Pure-logic tests (TDD red first) + HTTP protocol tests against tmp archives.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))


def _h(challenger, champion="m", promoted=False, wins=3, draws=0, games=6,
       margins=None, mean_margin=0.0, ret=1.23456, loss=0.123456,
       finished_at=None, duration_s=None):
    margins = margins if margins is not None else [0] * games
    return {
        "challenger": challenger, "champion": champion, "promoted": promoted,
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
    _write_hist(base, [_h("g001")])
    (base / "games.jsonl").write_text("{}\n")
    first = dashboard.archive_mtime(base)
    assert first > 0
    (base / "matrix.json").write_text("{}")
    assert dashboard.archive_mtime(base) >= first


def test_snapshot_carries_mtime_and_rounded_numbers(tmp_path):
    import dashboard

    base = tmp_path / "archive"
    _write_hist(base, [_h("g001")])
    snap = dashboard.snapshot(base)
    assert snap["mtime"] == dashboard.archive_mtime(base)
    g = snap["generations"][0]
    assert g["train_return"] == 1.23  # 2dp server-side
    assert g["train_loss"] == 0.123  # 3dp server-side
    assert g["mean_margin"] == round(0.0, 2)


def test_is_fresh_logic(tmp_path):
    import dashboard

    base = tmp_path / "archive"
    _write_hist(base, [_h("g001")])
    mtime = dashboard.archive_mtime(base)
    assert dashboard.is_fresh(base, mtime) is True
    assert dashboard.is_fresh(base, mtime - 1) is False
    assert dashboard.is_fresh(base, None) is False
    assert dashboard.is_fresh(base, "bogus") is False


def test_page_slice_protocol():
    import dashboard

    rows = list(range(250))
    assert dashboard.page_slice(rows, 0) == rows[:100]
    assert dashboard.page_slice(rows, 2) == rows[200:]
    assert dashboard.page_slice(rows, 9) == []
    assert dashboard.page_slice([], 0) == []


def test_filter_generations_matches_challenger_or_champion():
    import dashboard

    gens = [{"id": "g1", "champion": "m"}, {"id": "g2", "champion": "g1"},
            {"id": "g9", "champion": "zz"}]
    assert [g["id"] for g in dashboard.filter_generations(gens, "")] == \
        ["g1", "g2", "g9"]
    assert [g["id"] for g in dashboard.filter_generations(gens, "g1")] == \
        ["g1", "g2"]
    assert dashboard.filter_generations(gens, "nobody") == []


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


def test_first_paint_has_champion_games_and_crowns(tmp_path):
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
        "train": {"losses": [0.4], "mean_return": 1.0},
        "eval": {"wins": 4, "draws": 0, "games": 6, "win_rate": 4 / 6,
                 "margins": [2, 1, 3, -1, 2, 1], "mean_margin": 1.0},
        "config": {}})
    snap = dashboard.snapshot(base)
    page = dashboard.render_page(snap)
    assert a in page  # champion id in raw HTML, no JS needed
    assert "games/g001/eval0/logs/0.replay" in page  # first game rows
    assert "complete" in page  # crown column value server-rendered
    assert "ch-elo" in page  # canvases still present


def test_first_paint_empty_archive_has_skeleton():
    import dashboard

    page = dashboard.render_page(None)
    assert "loading" in page  # skeleton/fallback copy, layout intact
    assert "ch-elo" in page


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
        assert stale["champion"] == a
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
