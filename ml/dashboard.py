"""Training dashboard: key stats, population, games, replay links.

Stdlib only. Serves a live page over HTTP so it works from a Windows
browser against WSL (open http://localhost:PORT; WSL2 forwards
localhost automatically). Polls the archive; no restart needed between
generations.

  .venv/bin/python ml/dashboard.py [--port 8080] [--archive ml/archive]

Routes: / (page), /api/snapshot (everything as JSON),
/api/games?member=<id> (game index), /replay?f=<archive-relative
replay> (visualizer page, opens in a new tab),
/static/v/<path> (visualizer js/data/img).
"""

from __future__ import annotations

import argparse
import functools
import html
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

import archive
import selfplay

VIS_DIR = ROOT / "tools" / "visualizer"
TEMPLATE = (VIS_DIR / "replay.html.template").read_text()


def snapshot(base: Path) -> dict:
    """Everything the page needs, in one JSON-able dict."""
    archive.init(base)
    champ = archive.get_champion(base)
    mix = archive.nash_mixture(base)
    games = archive.list_games(base)
    members = []
    for m in archive.members(base):
        cid = m["id"]
        w = l = 0
        for g in games:
            mine, theirs = (g["score_a"], g["score_b"]) if g["a"] == cid else (
                (g["score_b"], g["score_a"]) if g["b"] == cid else (None, None))
            if mine is None:
                continue
            w += mine > theirs
            l += mine < theirs
        members.append({
            "id": cid, "role": m["role"], "parent": m["parent"],
            "nash": round(mix.get(cid, 0.0), 4),
            "wins": w, "losses": l,
        })
    return {
        "champion": champ,
        "members": members,
        "history": selfplay.read_history(base),
        "games": archive.list_games(base)[:50],
        "status": archive.read_status(base),
        "counts": {
            "generations": len(selfplay.read_history(base)),
            "games": len(archive.list_games(base)),
        },
    }


def replay_page(base: Path, rel: str) -> str | None:
    """Visualizer HTML with the replay inlined. None if unsafe/missing."""
    target = (base / rel).resolve()
    if not str(target).startswith(str(base.resolve())) or not target.is_file():
        return None
    data = target.read_text()
    try:
        data = json.dumps(json.loads(data), separators=(",", ":"))
        data = data.replace("\\", "\\\\").replace("'", "\\'")
    except ValueError:
        data = data.replace("\n", "\\\\n").replace("'", "\\'")
    page = TEMPLATE.replace("## PATH PLACEHOLDER ##", "/static/v/")
    return page.replace("## REPLAY PLACEHOLDER ##", data)


def make_handler(base: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, body: bytes, ctype: str):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send(PAGE.encode(), "text/html")
            elif parsed.path == "/api/snapshot":
                self._send(json.dumps(snapshot(base)).encode(), "application/json")
            elif parsed.path == "/api/games":
                member = parse_qs(parsed.query).get("member", [None])[0]
                self._send(
                    json.dumps(archive.list_games(base, member)).encode(),
                    "application/json",
                )
            elif parsed.path == "/replay":
                rel = parse_qs(parsed.query).get("f", [None])[0]
                page = replay_page(base, rel) if rel else None
                if page is None:
                    self.send_error(404, "no such replay")
                else:
                    self._send(page.encode(), "text/html")
            elif parsed.path.startswith("/static/v/"):
                target = (VIS_DIR / parsed.path[len("/static/v/"):]).resolve()
                if not str(target).startswith(str(VIS_DIR.resolve())) or not target.is_file():
                    self.send_error(404, "no such file")
                else:
                    ctype = "application/javascript" if target.suffix == ".js" else (
                        "text/html" if target.suffix in (".html", ".htm") else
                        "image/png" if target.suffix == ".png" else "application/octet-stream")
                    self._send(target.read_bytes(), ctype)
            else:
                self.send_error(404, "unknown route")

    return Handler


PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>AlphaStarZero training</title>
<style>
body{font-family:system-ui,sans-serif;margin:2em;max-width:1000px}
table{border-collapse:collapse;margin:1em 0}td,th{border:1px solid #ccc;padding:.3em .7em;text-align:left}
canvas{border:1px solid #ccc;margin:.5em 0}
select,button{font-size:1em}
.muted{color:#666}
</style></head><body>
<h1>AlphaStarZero training</h1>
<div id="head" class="muted">loading…</div>
<h2>Training curves</h2>
<canvas id="loss" width="480" height="160"></canvas>
<canvas id="ret" width="480" height="160"></canvas>
<h2>Population</h2>
<table id="pop"><tr><th>id</th><th>role</th><th>parent</th><th>nash</th><th>W-L (eval)</th></tr></table>
<h2>Recent games</h2>
<div><select id="member"><option value="">all members</option></select>
<button id="refresh">refresh</button></div>
<table id="games"><tr><th>gen</th><th>kind</th><th>matchup</th><th>score</th><th>replay</th></tr></table>
<script>
let S=null;
function line(id,data,color){const c=document.getElementById(id),x=c.getContext('2d');
x.clearRect(0,0,c.width,c.height);if(!data.length)return;
const mn=Math.min(...data),mx=Math.max(...data),rg=(mx-mn)||1;
x.strokeStyle=color;x.beginPath();
data.forEach((v,i)=>{const px=i/(data.length-1||1)*c.width,py=c.height-((v-mn)/rg)*c.height;
i?x.lineTo(px,py):x.moveTo(px,py)});x.stroke();
x.fillStyle='#666';x.fillText(id+' last='+data[data.length-1].toFixed(3),8,12);}
async function load(){const r=await fetch('/api/snapshot');S=await r.json();
const st=S.status||{};
let prog='idle';
if(st.phase==='train')prog=`training ${st.challenger||''}: game ${st.done}/${st.total} (last mean return ${(st.last_mean_return||0).toFixed(2)})`;
else if(st.phase==='eval')prog=`evaluating ${st.challenger||''}: duel ${st.done}/${st.total} (${st.wins||0}W ${st.draws||0}D so far)`;
else if(st.phase==='done')prog=`generation done: ${st.challenger||''} ${st.promoted?'promoted ★':'held'} (champion ${st.champion||''})`;
document.getElementById('head').textContent=
`champion ${S.champion||'—'} · ${S.counts.generations} generations · ${S.counts.games} games · ${prog}`;
const losses=S.history.flatMap(h=>h.train?h.train.losses:[]);
line('loss',losses,'#c00');
line('ret',S.history.map(h=>h.train?h.train.mean_return:0),'#080');
const pop=document.getElementById('pop');
pop.innerHTML='<tr><th>id</th><th>role</th><th>parent</th><th>nash</th><th>W-L (eval)</th></tr>'+
S.members.map(m=>`<tr><td>${m.id}${m.id===S.champion?' ★':''}</td><td>${m.role}</td><td>${m.parent||'—'}</td><td>${m.nash}</td><td>${m.wins}-${m.losses}</td></tr>`).join('');
const sel=document.getElementById('member'),cur=sel.value;
sel.innerHTML='<option value="">all members</option>'+
S.members.map(m=>`<option ${m.id===cur?'selected':''}>${m.id}</option>`).join('');
loadGames();}
async function loadGames(){const m=document.getElementById('member').value;
const r=await fetch('/api/games'+(m?('?member='+m):''));const g=await r.json();
document.getElementById('games').innerHTML=
'<tr><th>gen</th><th>kind</th><th>matchup</th><th>score</th><th>replay</th></tr>'+
g.slice(0,100).map(x=>`<tr><td>${x.gen}</td><td>${x.kind}</td><td>${x.a} vs ${x.b}</td><td>${x.score_a}-${x.score_b}</td><td><a href="/replay?f=${encodeURIComponent(x.replay)}" target="_blank" rel="noopener">open</a></td></tr>`).join('');}
document.getElementById('member').onchange=loadGames;
document.getElementById('refresh').onclick=load;
load();setInterval(load,5000);
</script></body></html>
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Serve the training dashboard.")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--archive", default="ml/archive")
    args = p.parse_args(argv)
    base = (ROOT / args.archive).resolve() if not Path(args.archive).is_absolute() else Path(args.archive)
    server = ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(base))
    print(f"dashboard: http://localhost:{args.port}/  (archive: {base})")
    print("WSL note: open the localhost URL in your Windows browser.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
