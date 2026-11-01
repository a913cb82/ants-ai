"""Dashboard page contract: pure-AZ snapshot keys, cards, replay links.

Snapshot keys are exactly
{h0, training, behavior, games, game_total, alerts, mtime}.
Page cards: sticky H0 strip, training vitals, attention queue,
behavior table, recent games. Zero-JS first paint.
"""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

NEW_KEYS = {"h0", "training", "behavior", "games", "game_total", "alerts", "mtime", "trace_miss"}
LEGACY_KEYS = {
    "anchors",
    "standings",
    "bars",
    "pairs",
    "learners",
    "anchor_verdict",
    "league",
    "admissions",
    "anchor_trend",
    "pool",
    "intervals",
    "board",
    "history",
    "maps",
    "status",
    "counts",
    "members",
    "main",
    "conv",
    "margin",
    "whisker",
    "champ",
    "cand",
    "top20",
    "newcomer",
    "decisive",
}


def _league_base(base, games=4):
    import archive

    archive.init(base)
    archive.save_state(base, {"tick": games, "next_tick": games, "micro": 0})
    for i in range(games):
        archive.log_game(
            base,
            ["main", "main"], [3 if i % 3 else 1, 1],
            f"games/g{i}/logs/0.replay",
            map="m",
            game=f"gid-{i}",
            tick=i,
            food=[2, 1],
            kills=[1, 0],
            army=[5, 4],
            length=120,
        )
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
    assert set(h0) == {
        "tick",
        "games",
        "updates",
        "micro",
        "games_per_h",
        "secs_since_game",
        "last_result",
        "last_length",
        "decisive",
    }
    assert h0["tick"] == 4 and h0["games"] == 4
    assert h0["updates"] == 0 and h0["micro"] == 0


def test_first_paint_has_new_cards_and_named_replays(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "archive")
    snap = dashboard.snapshot(base)
    page = dashboard.render_page(snap)
    for cid in ("h0", "training-body", "alerts", "behavior-body", "games-body"):
        assert cid in page, cid
    # no league cards survive
    for cid in (
        "ch-ladder",
        "standings-body",
        "bars-body",
        "ch-pairs",
        "ladder-fallback",
        "pairs-fallback",
        '<select id="learner"',
    ):
        assert cid not in page, cid
    # replay links open in a new tab
    assert 'target="_blank"' in page
    # server-rendered without JS: H0 numbers and a game row are inline
    assert "games/g0/logs/0.replay" in page


def test_first_paint_empty_archive_has_skeleton(tmp_path):
    import dashboard

    page = dashboard.render_page(None)
    assert "loading" in page
    assert "h0" in page and "training-body" in page


def test_is_fresh_logic(tmp_path):
    import dashboard

    base = _league_base(tmp_path / "archive")
    mtime = dashboard.archive_mtime(base)
    assert dashboard.is_fresh(base, mtime) is True
    assert dashboard.is_fresh(base, mtime - 1) is False
    assert dashboard.is_fresh(base, None) is False
    assert dashboard.is_fresh(base, "bogus") is False


def test_http_since_shortcircuit_and_games_paging(tmp_path):
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
        snap = json.load(urllib.request.urlopen(root + "/api/snapshot", timeout=5))
        assert set(snap) == NEW_KEYS
        tiny = json.load(
            urllib.request.urlopen(
                root + f"/api/snapshot?since={snap['mtime']}", timeout=5
            )
        )
        assert tiny == {"unchanged": True, "mtime": snap["mtime"]}
        stale = json.load(
            urllib.request.urlopen(root + "/api/snapshot?since=1", timeout=5)
        )
        assert stale["h0"]["games"] == 4
        full = json.load(
            urllib.request.urlopen(root + "/api/games?limit=100&offset=0", timeout=5)
        )
        assert full["total"] == 4
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


def test_dashboard_script_parses_as_javascript(tmp_path):
    """The page SCRIPT must parse: one syntax error kills every live
    update (server twins keep first paint alive, masking it). Skipped
    where node is unavailable."""
    import shutil
    import subprocess

    if shutil.which("node") is None:
        pytest.skip("node unavailable")
    import dashboard

    src = Path(dashboard.__file__).read_text()
    m = re.search(r'^SCRIPT = """\n(.*?)^""",?\s*$', src, re.S | re.M)
    assert m, "SCRIPT block not found"
    js = tmp_path / "dash.js"
    js.write_text(m.group(1))
    r = subprocess.run(
        ["node", "--check", str(js)], capture_output=True, text=True, timeout=60
    )
    assert r.returncode == 0, r.stderr[-2000:]
