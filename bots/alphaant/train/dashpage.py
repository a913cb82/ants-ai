"""Dashboard pages: first-paint HTML render from a snapshot.

Row markup here mirrors the JS renderers (any visual change needs both
sides — search for the twin name).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import html

from dashdata import spark_svg

EMPTY_GAMES = "no games logged yet \u2014 they appear here as each game finishes"



MAIN_BLUE = "#1d4ed8"



STYLES = """
:root{
  --bg:#F6F7F9; --card:#FFFFFF; --border:#E3E6EA; --border-strong:#C9CFD6;
  --ink:#16191D; --secondary:#5B6470; --muted:#67707B;
  --blue:#1d4ed8; --amber:#b45309; --green1:#047857;
  --gray:#6b7280; --red:#b91c1c;
}
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,Roboto,"Helvetica Neue",Arial,sans-serif;
  background:var(--bg); color:var(--ink); margin:0; padding:0 0 48px; font-size:13px;}
.wrap{max-width:1720px; margin:0 auto; padding:24px max(16px,4vw) 0;}
h1{font-size:22px; margin:0 0 4px;}
.sub{color:var(--secondary); font-size:13px; margin:0 0 20px;}
.h0{position:sticky; top:0; z-index:10; background:var(--card); border-bottom:1px solid var(--border-strong);
  padding:10px max(16px,4vw); display:flex; gap:18px; align-items:center; flex-wrap:wrap; font-size:13px;}
.live-pill{font-size:11px; font-weight:700; padding:2px 10px; border-radius:20px; white-space:nowrap;}
.live-pill.ok{color:var(--green1); background:#E6F4EC;}
.live-pill.stale{color:var(--amber); background:#FBF3E2;}
.live-pill.paused{color:var(--secondary); background:#EDEFF1;}
.section-title{font-size:16px; font-weight:700; margin:32px 0 12px;}
.legend{font-size:11px; color:var(--muted); margin:-6px 0 12px;}
.card{background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px 20px;}
.grid12{display:grid; grid-template-columns:repeat(12,1fr); gap:16px; align-items:stretch;}
.span7{grid-column:span 7;} .span5{grid-column:span 5;} .span6{grid-column:span 6;} .span12{grid-column:span 12;}
.tcell{display:flex; flex-direction:column; min-width:0;}
.tcell>.card{flex:1 1 auto;}
.spk{width:90px;height:18px;vertical-align:middle;margin-left:8px;}
.spk polyline{fill:none;stroke:#64748b;stroke-width:1.2;}
.alert-alert{color:var(--red); font-size:13px; padding:4px 0;}
.alert-ok{font-size:13px; padding:4px 0;}
.stale{opacity:.55;}
table{border-collapse:collapse; width:100%; font-size:13px; font-variant-numeric:tabular-nums;}
th{background:#F1F3F5; text-align:left; font-size:11px; color:var(--secondary); font-weight:600;}
th,td{padding:9px 10px; border-bottom:1px solid var(--border);}
tr:last-child td{border-bottom:none;}
tbody tr:hover{background:#F8FAFC;}
td.num, th.num{text-align:right;}
td.truncate,.truncate{max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
.badge{display:inline-block; font-size:11px; font-weight:700; padding:2px 9px; border-radius:20px;}
.badge.win{color:var(--green1); background:#E6F4EC;}
.badge.loss{color:var(--red); background:#FBEAE8;}
.badge.draw{color:var(--blue); background:#EAF0FE;}
td.replay{white-space:nowrap;}
.toolbar{display:flex; gap:10px; align-items:center; margin-bottom:10px; flex-wrap:wrap;}
.toolbar label{font-size:13px; color:var(--secondary);}
input{font-size:13px; padding:6px 10px; border:1px solid var(--border-strong); border-radius:8px; background:#fff;}
input#member{min-width:140px;}
.clear-link{font-size:12px; white-space:nowrap;}
.live-toggle{display:flex; align-items:center; gap:6px; font-size:13px; color:var(--secondary);}
.pager{display:flex; gap:6px;}
.pager button{font-size:12px; padding:5px 10px; border:1px solid var(--border-strong); border-radius:8px; background:#fff; cursor:pointer;}
.pager button:disabled{opacity:.4; cursor:default;}
.updated{font-size:11px; color:var(--muted); margin-left:auto;}
.table-scroll{overflow-x:auto;}
.table-tall{max-height:480px; overflow-y:auto;}
.table-tall thead th{position:sticky; top:0; z-index:1;}
.empty{padding:28px 20px; color:var(--secondary); font-size:13px;}
a{color:var(--blue); text-decoration:none;}
a:hover{text-decoration:underline;}
a:focus-visible,input:focus-visible,button:focus-visible{outline:2px solid var(--blue); outline-offset:2px;}
.skip{position:absolute; left:-9999px; top:0; background:var(--ink); color:#fff; padding:8px 14px; z-index:99; border-radius:0 0 8px 0;}
.skip:focus{left:0; color:#fff;}
.footer{margin-top:40px; padding-top:12px; border-top:1px solid var(--border);
  font-size:11px; color:var(--muted); display:flex; gap:8px; flex-wrap:wrap;}
.footer .sep{opacity:.5;}
.skel td{color:transparent !important;}
.skel td span{display:block; height:12px; border-radius:6px;
  background:linear-gradient(90deg,var(--border) 25%,#F1F3F5 50%,var(--border) 75%);
  background-size:200% 100%; animation:shimmer 1.2s infinite;}
@keyframes shimmer{to{background-position:-200% 0;}}
@media (max-width:1100px){
  .span7,.span5,.span6{grid-column:span 12;}
}
"""



SCRIPT = """
let S=null, seq=0, lastSnap="", lastGames="", live=true, lastTick=0;
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
async function fetchJSON(url){
  let r;
  try{r=await fetch(url);}
  catch(e){throw new Error("connection lost: "+e.message);}
  if(!r.ok){
    let detail="";
    try{const body=await r.json();if(body&&body.error)detail=": "+String(body.error).slice(0,140);}
    catch(e){}
    throw new Error("request failed HTTP "+r.status+detail+" on "+url);
  }
  return r.json();
}
function fmtAge(s){
  if(s===null||s===undefined||!Number.isFinite(+s))return "—";
  s=Math.max(0,Math.round(+s));
  if(s<60)return s+"s ago";
  return Math.floor(s/60)+"m "+String(s%60).padStart(2,"0")+"s ago";
}
function fmtRate(h){return (h===null||h===undefined||!Number.isFinite(+h))?"—":Math.round(h)+"/h";}
function fmtShare(s){return (s===null||s===undefined||!Number.isFinite(+s))?"—":Math.round(s)+"%";}
function fmtTick(t){return (t===null||t===undefined)?"t—":"t"+t;}
function dot(){return '<span aria-hidden="true" style="color:#1d4ed8">●</span> ';}
function tableBusy(id){
  const el=$(id);
  return el.matches(":hover")||el.contains(document.activeElement);
}
function keepScroll(scroller,fn){
  const top=scroller?scroller.scrollTop:0;
  fn();
  if(scroller)scroller.scrollTop=top;
}
function renderH0(){
  const h=S.h0;
  const dec=(typeof h.decisive==="number")?Math.round(h.decisive*100)+"%":"—";
  const last=h.last_result||"—";
  const lastLen=(h.last_length===null||h.last_length===undefined)?"—":h.last_length;
  $("h0").innerHTML=
    "<span><b>game</b> "+esc(h.tick)+"</span>"+
    "<span>"+dot()+"main</span>"+
    "<span><b>updates</b> "+esc(h.updates)+"</span>"+
    "<span><b>micro</b> "+esc(h.micro)+"/16</span>"+
    "<span><b>decisive÷40</b> "+dec+"</span>"+
    "<span><b>last</b> "+esc(last)+" "+lastLen+"</span>"+
    "<span><b>rate</b> "+fmtRate(h.games_per_h)+"</span>"+
    "<span><b>last game</b> "+fmtAge(h.secs_since_game)+"</span>";
}
function num(v,dp){
  return (v===null||v===undefined||!Number.isFinite(+v))?"—":Number(v).toFixed(dp===undefined?3:dp);
}
function renderTraining(){
  const h="t|"+JSON.stringify(S.training);
  if(h===renderTraining._last)return;
  renderTraining._last=h;
  $("training-body").innerHTML=(S.training||[]).map(u=>
    "<tr><td class=num>"+fmtTick(u.tick)+'</td><td class="num">'+esc(u.rows)+
    '</td><td class="num">'+num(u.mean_return,2)+'</td><td class="num">'+num(u.explained_var,2)+
    '</td><td class="num">'+num(u.loss)+'</td><td class="num">'+num(u.entropy)+
    '</td><td class="num">'+num(u.kl)+'</td><td class="num">'+num(u.clipfrac,2)+'</td><td class="num">'+num(u.update_seconds,1)+"</td></tr>"
  ).join("")||'<tr><td colspan="9" class="empty">no updates yet — the first lands after 16 games</td></tr>';
}
function renderAlerts(){
  const h="a|"+JSON.stringify(S.alerts);
  if(h===renderAlerts._last)return;
  renderAlerts._last=h;
  $("alerts").innerHTML=S.alerts.map(a=>
    '<div class="alert-'+esc(a.level)+'">'+esc(a.msg)+' <span class="legend">'+fmtTick(a.tick)+"</span></div>"
  ).join("");
}
function spark(vals){
  const p=(vals||[]).filter(v=>typeof v==="number");
  if(!p.length)return "";
  const lo=Math.min.apply(null,p),hi=Math.max.apply(null,p),sp=(hi-lo)||1;
  const w=90,h=18,n=p.length;
  const pts=p.map((v,i)=>((i*w/Math.max(n-1,1)).toFixed(1))+","+(h-2-(v-lo)*(h-4)/sp).toFixed(1)).join(" ");
  return '<svg class="spk" width="'+w+'" height="'+h+'" viewBox="0 0 '+w+' '+h+'" aria-hidden="true"><polyline points="'+pts+'"/></svg>';
}
function renderBehavior(){
  const h="bh|"+JSON.stringify(S.behavior);
  if(h===renderBehavior._last)return;
  renderBehavior._last=h;
  const cell=(v,sp,fmt)=>'<td class="num">'+v+sp+"</td>";
  $("behavior-body").innerHTML=S.behavior.map(r=>{
    const sp=r.spark||{};
    return "<tr><td>"+dot()+esc(r.id)+"</td>"+
    cell(typeof r.food==="number"?r.food.toFixed(1):"—",spark(sp.food))+
    cell(typeof r.kills==="number"?r.kills.toFixed(1):"—",spark(sp.kills))+
    cell(fmtShare(r.army_pct),spark(sp.army))+
    cell(r.length===null||r.length===undefined?"—":esc(r.length),spark(sp.length))+
    '<td class="num">'+esc(r.n)+"</td></tr>";
  }).join("");
}
/* Canvas frame: shared geometry, gridlines, HiDPI. Direct end labels —
   no legends for ≤4 series (and none above either: labels ride the lines). */
function seatList(stats,key,fmt){return (stats||[]).map(st=>{const v=st?st[key]:null;return (v==null||v===undefined)?"—":fmt(v);}).join(",");}
function gameRow(g){
  const res=g.result||"draw";
  const seats=g.seats||[];
  const names=seats.join(" vs ");
  const scoreline=(g.scores||[]).join("-");
  const stats=g.stats||[];
  const food=seatList(stats,"food",v=>Math.round(v));
  const kills=seatList(stats,"kills",v=>Math.round(v));
  const army=seatList(stats,"army_pct",v=>v+"%");
  const len=(g.length==null?"—":g.length);
  const map=(g.map==null?"—":esc(g.map));
  return "<tr><td class=num>"+fmtTick(g.tick)+"</td><td>"+dot()+esc(g.learner)+"</td>"+
    '<td class="num">'+seats.length+'</td><td class="truncate">'+map+'</td><td>'+(food||"—")+'</td><td>'+(kills||"—")+'</td><td>'+(army||"—")+'</td>'+
    '<td class="num">'+len+'</td><td><span class="badge '+res+'">'+res+"</span> "+esc(scoreline)+"</td>"+
    '<td class="replay"><a href="/replay?f='+encodeURIComponent(g.replay)+'" target="_blank" rel="noopener" title="'+esc(names)+' — opens in a new tab">replay<span aria-hidden="true"> ↗</span></a></td></tr>';
}
async function renderGames(my){
  if(tableBusy("games-body"))return true;
  const qparts=["limit=100","offset="+gamesOffset];
  let data;
  try{data=await fetchJSON("/api/games?"+qparts.join("&"));}
  catch(e){
    $("error").style.display="block";
    $("error").textContent="games feed failed ("+e.message+") — showing last good table. retrying…";
    return false;
  }
  if(my!==seq)return true;
  const h=gamesOffset+"|"+JSON.stringify(data);
  if(h===lastGames)return true;
  lastGames=h;
  keepScroll($("games-scroll"),()=>{
    $("games-body").innerHTML=data.rows.map(gameRow).join("")||(data.total
      ?'<tr><td colspan="10" class="empty">no games on this page — use the pager above</td></tr>'
      :'<tr><td colspan="10" class="empty">no games logged yet — they appear here as each game finishes</td></tr>');
  });
  const pages=Math.max(1,Math.ceil(data.total/100));
  const page=Math.min(Math.floor(gamesOffset/100)+1,pages);
  $("games-count").textContent="showing "+data.rows.length+" of "+data.total+" · page "+page+" of "+pages;
  $("pg-prev").disabled=gamesOffset<=0;
  $("pg-next").disabled=gamesOffset+100>=data.total;
  return true;
}
function renderPill(){
  const el=$("live-pill");
  if(!el)return;
  const ageS=Math.max(0,Math.round((Date.now()-lastTick)/1000));
  if(!live){el.className="live-pill paused";el.textContent="○ paused";return;}
  if(ageS>30){el.className="live-pill stale";el.textContent="▲ stale "+ageS+"s";}
  else{el.className="live-pill ok";el.textContent="● live · "+ageS+"s";}
  $("updated").textContent="updated "+ageS+"s ago · "+(live?"live":"paused");
}
async function load(){
  if(!live)return;
  const my=++seq;
  try{
    const url=(S&&S.mtime)?"/api/snapshot?since="+encodeURIComponent(S.mtime):"/api/snapshot";
    const snap=await fetchJSON(url);
    if(my!==seq)return;
    lastTick=Date.now();
    $("error").style.display="none";
    if(!(snap.unchanged&&S)){
      S=snap.unchanged?S:snap;
      const h=JSON.stringify(snap);
      if(h!==lastSnap){lastSnap=h;
        renderH0();renderAlerts();renderBehavior();renderTraining();}
      else renderH0();
    }
    renderPill();
    await renderGames(my);
  }catch(e){
    $("error").style.display="block";
    $("error").textContent=lastTick?"connection lost ("+e.message+") — showing last good data. retrying…"
      :"connection lost ("+e.message+") — no data yet. retrying…";
  }
}
let gamesOffset=0;
$("pg-prev").addEventListener("click",()=>{gamesOffset=Math.max(0,gamesOffset-100);renderGames(++seq);});
$("pg-next").addEventListener("click",()=>{gamesOffset+=100;renderGames(++seq);});
$("live-toggle").addEventListener("change",e=>{live=e.target.checked;
  if(!live)seq++;
  $("live-label").textContent=live?"live":"paused";
  renderPill();load();});
function tick(){renderPill();load().finally(()=>setTimeout(tick,live?10000:10000));}
load();
tick();
"""



def _esc(x) -> str:
    return html.escape("" if x is None else str(x), quote=True)



def _dot() -> str:
    return f'<span aria-hidden="true" style="color:{MAIN_BLUE}">●</span> '



def fmt_age(secs) -> str:
    """Recency: `12s ago`, past 60s `3m 04s ago`, unknown `—`."""
    if not isinstance(secs, (int, float)):
        return "—"
    s = max(0, int(round(secs)))
    if s < 60:
        return f"{s}s ago"
    return f"{s // 60}m {s % 60:02d}s ago"



def fmt_rate(games_per_h) -> str:
    if not isinstance(games_per_h, (int, float)):
        return "—"
    return f"{games_per_h:.0f}/h"



def fmt_share100(share) -> str:
    """A 0-100 share to 0dp, unknown to a dash."""
    return f"{share:.0f}%" if isinstance(share, (int, float)) else "—"



def fmt_tick(t) -> str:
    return f"t{t}" if isinstance(t, (int, float)) else "t—"



def h0_strip_html(h0: dict | None) -> str:
    """Twin of JS renderH0."""
    if h0 is None:
        return '<span class="stat-label">loading…</span>'
    last = h0.get("last_result") or "—"
    last_len = h0.get("last_length")
    last_len = last_len if isinstance(last_len, (int, float)) else "—"
    dec = h0.get("decisive")
    dec = f"{dec:.0%}" if isinstance(dec, (int, float)) else "—"
    return (
        f"<span><b>game</b> {_esc(h0.get('tick', 0))}</span>"
        f"<span>{_dot()}main</span>"
        f"<span><b>updates</b> {_esc(h0.get('updates', 0))}</span>"
        f"<span><b>micro</b> {_esc(h0.get('micro', 0))}/16</span>"
        f"<span><b>decisive÷40</b> {dec}</span>"
        f"<span><b>last</b> {_esc(last)} {last_len}</span>"
        f"<span><b>rate</b> {fmt_rate(h0.get('games_per_h'))}</span>"
        f"<span><b>last game</b> {fmt_age(h0.get('secs_since_game'))}</span>"
    )



def alerts_html(alerts: list | None) -> str:
    """Twin of JS renderAlerts: red text lines, or one all-clear."""
    if not alerts:
        return '<div class="empty">loading…</div>'
    return "".join(
        f'<div class="alert-{a.get("level", "ok")}">'
        f'{_esc(a.get("msg"))} <span class="legend">'
        f"{fmt_tick(a.get('tick'))}</span></div>"
        for a in alerts
    )



def behavior_rows_html(rows: list | None, h0_tick) -> str:
    """Twin of JS behaviorRow."""
    if not rows:
        return (
            '<tr><td colspan="6" class="empty">no behavior yet — '
            "games log food/kills/army as they finish</td></tr>"
        )
    out = []
    for r in rows:
        # behavior rows carry means, not ticks: never stale by recency.
        food = r.get("food")
        kills = r.get("kills")
        sp = r.get("spark") or {}
        out.append(
            f"<tr><td>{_dot()}{_esc(r.get('id'))}</td>"
            f'<td class="num">'
            f"{f'{food:.1f}' if isinstance(food, (int, float)) else '—'}"
            f"{spark_svg(sp.get('food') or [])}</td>"
            f'<td class="num">'
            f"{f'{kills:.1f}' if isinstance(kills, (int, float)) else '—'}"
            f"{spark_svg(sp.get('kills') or [])}</td>"
            f'<td class="num">{fmt_share100(r.get("army_pct"))}'
            f"{spark_svg(sp.get('army') or [])}</td>"
            f'<td class="num">{_esc(r.get("length")) if r.get("length") is not None else "—"}'
            f"{spark_svg(sp.get('length') or [])}</td>"
            f'<td class="num">{_esc(r.get("n"))}</td></tr>'
        )
    return "".join(out)



def _seat_list(stats: list, key: str, fmt) -> str:
    """Comma-separated per-seat facts: `44,59`, unknown seats read —."""
    return ",".join(
        "—" if (v := s.get(key)) is None else fmt(v) for s in stats
    )



def game_row_html(g: dict) -> str:
    """Twin of JS gameRow: tick · learner · players · map · food ·
    kills · army · len · result(scores) · replay."""
    res = g.get("result") or "draw"
    seats = g.get("seats") or []
    names = " vs ".join(_esc(s) for s in seats)
    scores = g.get("scores") or []
    scoreline = "-".join(str(s) for s in scores)
    stats = g.get("stats") or []
    food = _seat_list(stats, "food", lambda v: f"{v:.0f}")
    kills = _seat_list(stats, "kills", lambda v: f"{v:.0f}")
    army = _seat_list(stats, "army_pct", lambda v: f"{v}%")
    length = g.get("length")
    game_map = g.get("map")
    return (
        f'<tr><td class="num">{fmt_tick(g.get("tick"))}</td>'
        f"<td>{_dot()}{_esc(g.get('learner'))}</td>"
        f'<td class="num">{len(seats)}</td>'
        f'<td class="truncate">{_esc(game_map) if game_map else "—"}</td>'
        f"<td>{food or '—'}</td>"
        f"<td>{kills or '—'}</td>"
        f"<td>{army or '—'}</td>"
        f'<td class="num">{length if isinstance(length, (int, float)) else "—"}</td>'
        f'<td><span class="badge {res}">{res}</span> {_esc(scoreline)}</td>'
        f'<td class="replay"><a href="/replay?f={_esc(g.get("replay"))}" '
        f'target="_blank" rel="noopener" '
        f'title="{names} — opens in a new tab">'
        f'replay<span aria-hidden="true"> ↗</span></a></td></tr>'
    )



def training_rows_html(rows: list | None) -> str:
    """Twin of JS renderTraining."""
    if not rows:
        return (
            '<tr><td colspan="9" class="empty">no updates yet — '
            "the first lands after 16 games</td></tr>"
        )
    out = []
    for u in rows:
        out.append(
            '<tr><td class="num">' + fmt_tick(u.get("tick")) + "</td>"
            '<td class="num">' + _esc(u.get("rows")) + "</td>"
            '<td class="num">' + _num(u.get("mean_return"), 2) + "</td>"
            '<td class="num">' + _num(u.get("explained_var"), 2) + "</td>"
            '<td class="num">' + _num(u.get("loss")) + "</td>"
            '<td class="num">' + _num(u.get("entropy")) + "</td>"
            '<td class="num">' + _num(u.get("kl")) + "</td>"
            '<td class="num">' + _num(u.get("clipfrac"), 2) + "</td>"
            '<td class="num">' + _num(u.get("update_seconds"), 1) + "</td></tr>"
        )
    return "".join(out)



def _num(v, dp: int = 3) -> str:
    """Number to dp places, unknown to a dash."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    if f != f or f in (float("inf"), float("-inf")):
        return "—"
    return f"{f:.{dp}f}"



def render_page(snap: dict | None = None) -> str:
    """Full page. With a snapshot the H0 strip and all table cards are
    server-rendered (zero JS required to read); without one the shell
    carries shimmer rows so layout doesn't jump."""
    if snap is None:
        skel3 = "".join(
            '<tr class="skel">' + "<td><span></span></td>" * 5 + "</tr>"
            for _ in range(3)
        )
        skel8 = "".join(
            '<tr class="skel">' + "<td><span></span></td>" * 8 + "</tr>"
            for _ in range(3)
        )
        h0 = h0_strip_html(None)
        training = skel8
        alerts = '<div class="empty">loading…</div>'
        behavior = skel3
        games = skel3
        game_count = "loading…"
        footer_counts = "0 games"
    else:
        h0 = h0_strip_html(snap.get("h0"))
        tick = (snap.get("h0") or {}).get("tick", 0)
        training = training_rows_html(snap.get("training"))
        alerts = alerts_html(snap.get("alerts"))
        behavior = behavior_rows_html(snap.get("behavior"), tick)
        games = "".join(game_row_html(g) for g in snap.get("games", [])) or (
            f'<tr><td colspan="10" class="empty">{EMPTY_GAMES}</td></tr>'
        )
        total = snap.get("game_total", len(snap.get("games", [])))
        game_count = (
            f"showing {len(snap.get('games', []))} of {total} · "
            f"page 1 of {max(1, (total + 99) // 100)}"
        )
        footer_counts = f"{total} games"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AlphaAnt training</title>
<style>{STYLES}</style></head>
<body><a class="skip" href="#games-card">skip to games</a>
<div class="h0" id="h0">{h0}
<span class="live-pill ok" id="live-pill">● live</span>
<span class="updated" id="updated" title="page refresh time"></span></div>
<div class="wrap">
<h1>AlphaAnt mirror self-play</h1>
<p class="sub">one net · latest vs latest · every 16th game trains · 2-10p maps</p>
<div id="error" role="alert" style="display:none"></div>
<div class="grid12">
<div class="tcell span12">
<div class="section-title">Training</div>
<div class="legend">PPO vital signs per update, newest first · flat or rising loss with collapsing entropy means learning stopped · clipfrac near 1 means the clip binds every step · explained variance tracks the value head (1 is perfect)</div>
<div class="card table-scroll"><table>
<caption style="display:none">Training updates, newest first</caption>
<tr><th scope="col">update</th><th scope="col" class="num">rows</th><th scope="col" class="num">mean ret</th><th scope="col" class="num">expl var</th><th scope="col" class="num">loss</th><th scope="col" class="num">entropy</th><th scope="col" class="num">kl</th><th scope="col" class="num">clipfrac</th><th scope="col" class="num">upd s</th></tr>
<tbody id="training-body">{training}</tbody></table></div>
</div>
<div class="tcell span12">
<div class="section-title">Attention queue</div>
<div class="card" id="alerts">{alerts}</div>
</div>
<div class="tcell span12">
<div class="section-title">Behavior</div>
<div class="legend">per-game means: food · kills · army share · length · games · sparks cover the member's last 40 games</div>
<div class="card table-scroll"><table>
<caption style="display:none">Behavior</caption>
<tr><th scope="col">id</th><th scope="col" class="num">food</th><th scope="col" class="num">kills</th><th scope="col" class="num">army</th><th scope="col" class="num">len</th><th scope="col" class="num">n</th></tr>
<tbody id="behavior-body">{behavior}</tbody></table></div>
</div>
<div class="tcell span12">
<div class="section-title">Recent games</div>
<div class="legend">tick is the game number · all seats run the same net · result carries per-seat scores · food/kills/army list every seat · map mixes 2-10 players</div>
<div class="card" id="games-card">
<div class="toolbar">
<label class="live-toggle"><input type="checkbox" id="live-toggle" checked> <span id="live-label">live</span></label>
<span class="pager"><button id="pg-prev" type="button" aria-label="newer games page">← newer</button><button id="pg-next" type="button" aria-label="older games page">older →</button></span>
<span class="legend" id="games-count" style="margin:0">{game_count}</span>
</div>
<div class="table-scroll table-tall" id="games-scroll"><table>
<caption style="display:none">Recent games, newest first</caption>
<tr><th scope="col">game</th><th scope="col">learner</th><th scope="col" class="num">players</th><th scope="col">map</th><th scope="col">food</th><th scope="col">kills</th><th scope="col">army</th><th scope="col" class="num">len</th><th scope="col">result</th><th scope="col">replay</th></tr>
<tbody id="games-body">{games}</tbody></table></div>
</div>
</div>
</div>
<div class="footer"><span>archive bots/alphaant/archive</span><span class="sep">·</span><span>{footer_counts}</span><span class="sep">·</span><span>polls every 10s, values replace in place</span></div>
</div>
<script>{SCRIPT}</script></body></html>
"""

