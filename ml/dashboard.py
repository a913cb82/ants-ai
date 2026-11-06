"""Training dashboard: mirror self-play stats, games, replay links.

Stdlib only. Serves a live page over HTTP so it works from a Windows
browser against WSL (open http://localhost:PORT; WSL2 forwards
localhost automatically). Polls the archive; no restart needed as
training runs.

  .venv/bin/python ml/dashboard.py [--port 8080] [--archive ml/archive]

Routes: / (page), /api/snapshot (everything as JSON),
/api/games?limit=&offset= (game index slice + total),
/replay?f=<archive-relative replay> (visualizer page, new tab per link),
/static/v/<path> (visualizer js/data/img).

Thin server (routes + main). Data lives in ml/dashdata.py, first-paint
HTML in ml/dashpage.py; names are re-exported here so
``import dashboard`` keeps working.
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

from dashdata import (
    PAGE_SIZE,
    SPARK_MAX,
    alerts_panel,
    archive_mtime,
    behavior_panel,
    build_game,
    cached_games,
    cached_panel,
    group_games,
    h0_panel,
    is_fresh,
    limit_hits,
    pending_gb,
    rank_of,
    rate_window,
    replay_page,
    snapshot,
    spark_svg,
    trace_miss_mean,
    training_panel,
)
from dashpage import (
    alerts_html,
    behavior_rows_html,
    fmt_age,
    fmt_rate,
    fmt_share100,
    fmt_tick,
    game_row_html,
    h0_strip_html,
    render_page,
    training_rows_html,
)
from dashdata import VIS_DIR

__all__ = [
    "PAGE_SIZE",
    "SPARK_MAX",
    "VIS_DIR",
    "alerts_html",
    "alerts_panel",
    "archive_mtime",
    "behavior_panel",
    "behavior_rows_html",
    "build_game",
    "cached_games",
    "cached_panel",
    "fmt_age",
    "fmt_rate",
    "fmt_share100",
    "fmt_tick",
    "game_row_html",
    "group_games",
    "h0_panel",
    "h0_strip_html",
    "is_fresh",
    "limit_hits",
    "pending_gb",
    "rank_of",
    "rate_window",
    "render_page",
    "replay_page",
    "snapshot",
    "spark_svg",
    "trace_miss_mean",
    "training_panel",
    "training_rows_html",
]


def _json(handler: BaseHTTPRequestHandler, obj: object, status: int = 200) -> None:
    body = json.dumps(obj).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)



def make_handler(base: Path):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AZDash"

        def log_message(self, *args):
            pass

        def _send(self, body: bytes, ctype: str):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/":
                    # Server-rendered first paint (P0-1): live stats, counts,
                    # status and the first table pages inline, no JS needed.
                    # On failure fall back to the skeleton shell; the poll
                    # tick heals it on the next cycle.
                    try:
                        first = snapshot(base)
                    except Exception:
                        first = None
                    self._send(render_page(first).encode(), "text/html")
                elif parsed.path == "/api/snapshot":
                    q = parse_qs(parsed.query)
                    since = q.get("since", [None])[0]
                    if since is not None and is_fresh(base, since):
                        _json(self, {"unchanged": True, "mtime": archive_mtime(base)})
                    else:
                        _json(self, snapshot(base))
                elif parsed.path == "/api/games":
                    q = parse_qs(parsed.query)
                    try:
                        limit = max(0, min(int(q.get("limit", ["100"])[0]), 200))
                    except ValueError:
                        limit = 100
                    try:
                        offset = max(int(q.get("offset", ["0"])[0]), 0)
                    except ValueError:
                        offset = 0
                    rows = cached_panel(base)
                    total = len(rows)
                    offset = min(offset, total)
                    _json(self, {"total": total, "rows": rows[offset : offset + limit]})
                elif parsed.path == "/replay":
                    rel = parse_qs(parsed.query).get("f", [None])[0]
                    page = replay_page(base, rel)
                    if page is None:
                        self.send_error(404, "no such replay")
                    else:
                        self._send(page.encode(), "text/html")
                elif parsed.path.startswith("/static/v/"):
                    target = (VIS_DIR / parsed.path[len("/static/v/") :]).resolve()
                    if (
                        not str(target).startswith(str(VIS_DIR.resolve()))
                        or not target.is_file()
                    ):
                        self.send_error(404, "no such file")
                    else:
                        ctype = (
                            "application/javascript"
                            if target.suffix == ".js"
                            else (
                                "text/html"
                                if target.suffix in (".html", ".htm")
                                else "image/png"
                                if target.suffix == ".png"
                                else "application/octet-stream"
                            )
                        )
                        self._send(target.read_bytes(), ctype)
                else:
                    _json(self, {"error": f"unknown route: {parsed.path}"}, status=404)
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
                _json(self, {"error": f"{type(e).__name__}: {e}"}, status=500)

    return Handler



def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Serve the training dashboard.")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--archive", default="ml/archive")
    args = p.parse_args(argv)
    base = (
        (ROOT / args.archive).resolve()
        if not Path(args.archive).is_absolute()
        else Path(args.archive)
    )
    server = ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(base))
    print(f"dashboard: http://localhost:{args.port}/  (archive: {base})")
    print("WSL note: open the localhost URL in your Windows browser.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0

