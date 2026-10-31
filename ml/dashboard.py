"""Training dashboard: key stats, population, games, replay links.

Stdlib only. Serves a live page over HTTP so it works from a Windows
browser against WSL (open http://localhost:PORT; WSL2 forwards
localhost automatically). Polls the archive; no restart needed between
generations.

  .venv/bin/python ml/dashboard.py [--port 8080] [--archive ml/archive]

Routes: / (page), /api/snapshot (everything as JSON),
/api/games?member=&limit=&offset= (game index slice + total),
/replay?f=<archive-relative replay> (visualizer page, new tab per link),
/static/v/<path> (visualizer js/data/img).
"""

from __future__ import annotations

import argparse
import functools
import html
import json
import os
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

import archive
import selfplay

VIS_DIR = ROOT / "tools" / "visualizer"
TEMPLATE = (VIS_DIR / "replay.html.template").read_text()

_nash_cache: dict = {}
def _memo(cache: dict, key, thunk):
    """One-slot memo: recompute only when the key changes."""
    if cache.get("key") != key:
        cache.clear()
        cache["key"] = key
        cache["value"] = thunk()
    return cache["value"]


_games_cache: dict = {}
_grouped_cache: dict = {}


def cached_games(base: Path) -> list[dict]:
    """Parsed games.jsonl, re-parsed only when the file changes.

    snapshot() and /api/games share one parse per poll cycle."""
    path = base / "games.jsonl"
    try:
        st = path.stat()
    except OSError:
        return []
    return _memo(
        _games_cache,
        (str(base.resolve()), st.st_mtime_ns, st.st_size),
        lambda: archive.list_games(base),
    )


def cached_grouped(base: Path) -> list[dict]:
    """Pair rows -> per-game dicts, re-grouped only when games.jsonl
    changes. Grouping 80k rows costs ~1.5s; snapshot polls every few
    seconds, so this shares one grouping per file version like
    cached_games shares one parse."""
    path = base / "games.jsonl"
    try:
        st = path.stat()
    except OSError:
        return []
    return _memo(
        _grouped_cache,
        (str(base.resolve()), st.st_mtime_ns, st.st_size),
        lambda: group_games(cached_games(base)),
    )


def _eval_digest(base: Path) -> tuple:
    """Cache key that ignores train-only churn (Nash reads eval only)."""
    try:
        data = json.loads((base / "matrix.json").read_text())
    except (OSError, ValueError):
        return (None, None)
    return (tuple(data.get("ids", [])), json.dumps(data.get("eval", {}), sort_keys=True))


_history_cache: dict = {}


def cached_history(base: Path) -> list[dict]:
    """Parsed history.jsonl, re-parsed only when the file changes.

    snapshot() runs on every page poll; without this each poll re-reads
    ~12MB of generation summaries."""
    path = base / "history.jsonl"
    try:
        st = path.stat()
    except OSError:
        return []
    return _memo(
        _history_cache,
        (str(base.resolve()), st.st_mtime_ns, st.st_size),
        lambda: selfplay.read_history(base),
    )


def _split_pair(key: str, pos: dict) -> tuple[int, int] | None:
    """Indexes of an eval-matrix 'a vs b' key. Tries every split so ids
    containing ' vs ' still resolve; unknown ids return None."""
    parts = key.split(" vs ")
    for k in range(1, len(parts)):
        a, b = " vs ".join(parts[:k]), " vs ".join(parts[k:])
        if a in pos and b in pos:
            return pos[a], pos[b]
    return None


def _nash_cached(base: Path) -> dict:
    """Fictitious play is O(iters*n^2): redo only when eval data changes."""
    key = (str(base.resolve()), _eval_digest(base))
    return _memo(_nash_cache, key, lambda: _sparse_nash(base))


def _sparse_nash(base: Path, iters: int = 2000) -> dict[str, float]:
    """Fictitious play with the same result as archive.nash_mixture.

    The dense version matvecs a 1216x1216 numpy matrix 4000 times (~90%
    of cold first-load). The eval matrix is ~99.8% Laplace-prior zeros
    (unplayed pairs read as exactly 0.5-0.5=0), so each iteration walks
    only the few thousand played entries. Best responses use pre-update
    averages with first-index-wins ties, values reuse archive's exact
    mine/total-0.5 formula in ascending-index order, and the all-zero
    shortcut matches np.any (NaN counts, -0.0 does not): output is
    bit-identical to archive.nash_mixture on the 1200-gen archive,
    ~25x faster, with no new dependencies."""
    data = json.loads((base / "matrix.json").read_text())
    ids = data["ids"]
    n = len(ids)
    if not n:
        return {}
    pos = {cid: i for i, cid in enumerate(ids)}
    ev = data["eval"]
    rows: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    seen: set[tuple[int, int]] = set()
    any_nonzero = False
    for key, w in ev.items():
        pair = _split_pair(key, pos)
        if pair is None:
            continue
        i, j = pair
        if i == j or (j, i) in seen:
            continue
        seen.add((i, j))
        wba = ev.get(f"{ids[j]} vs {ids[i]}", [0.0, 0.0])
        mine = w[0] + wba[1] + 1.0
        theirs = w[1] + wba[0] + 1.0
        total = mine + theirs
        vij = mine / total - 0.5
        vji = theirs / total - 0.5
        if vij != 0.0 or vji != 0.0:
            any_nonzero = True
        rows[i].append((j, vij))
        rows[j].append((i, vji))
    if not any_nonzero:
        return {cid: round(1.0 / n, 4) for cid in ids}  # all draws: split evenly
    for r in rows:
        r.sort()
    trips = [(i, j, v) for i, r in enumerate(rows) for (j, v) in r]
    avg_r = [1.0 / n] * n
    avg_c = [1.0 / n] * n
    strat_r = [0] * n
    strat_c = [0] * n
    total_r = 0
    total_c = 0
    for _ in range(iters):
        best = 0
        best_val = None
        for i, r in enumerate(rows):
            s = 0.0
            for j, v in r:
                s += v * avg_c[j]
            if best_val is None or s > best_val:
                best_val = s
                best = i
        br_r = best
        col = [0.0] * n
        for i, j, v in trips:
            a = avg_r[i]
            if a:
                col[j] += v * a
        br_c = 0
        best_val = col[0]
        for j in range(1, n):
            if col[j] < best_val:
                best_val = col[j]
                br_c = j
        strat_r[br_r] += 1
        total_r += 1
        inv = 1.0 / total_r
        for i, c in enumerate(strat_r):
            avg_r[i] = c * inv
        strat_c[br_c] += 1
        total_c += 1
        inv = 1.0 / total_c
        for i, c in enumerate(strat_c):
            avg_c[i] = c * inv
    return {cid: (avg_r[i] + avg_c[i]) / 2 for i, cid in enumerate(ids)}


# ---------------------------------------------------------------- DATA


def rank_of(scores: list) -> list[int]:
    """Per-seat rank with the engine's formula (tools/engine.py): each seat
    takes the index of its score in the descending sort, so ties share a
    rank and the next rank skips ([10,10,5] -> [0,0,2])."""
    ordered = sorted(scores, reverse=True)
    return [ordered.index(s) for s in scores]


def _fallback_game_key(replay) -> str:
    """Per-game key for rows logged before the `game` id existed: every
    pair of one play shares its replay path, so the game directory (or the
    raw path when it has no /logs/ suffix) groups them back together."""
    text = replay if isinstance(replay, str) else str(replay)
    suffix = "/logs/0.replay"
    return text[:-len(suffix)] if text.endswith(suffix) else text


def game_key_of(row: dict) -> str:
    """Grouping key: the explicit per-play id when present, else the
    replay-derived fallback (covers all pre-id history)."""
    return row.get("game") or _fallback_game_key(row.get("replay", ""))


def _norm_row(row: dict) -> tuple:
    """Order-independent pair identity + aligned scores. Self-pairs sort
    their two scores so (X,X,2,3) and (X,X,3,2) dedupe: one unordered
    seat-pair, one logical row."""
    a, b, sa, sb = row["a"], row["b"], row["score_a"], row["score_b"]
    if a == b:
        return (a, b, min(sa, sb), max(sa, sb))
    if a <= b:
        return (a, b, sa, sb)
    return (b, a, sb, sa)


def _realize(normed: list[tuple]) -> list[list] | None:
    """Assign pair rows to numbered seat positions, fewest possible.

    Returns [[id, score], ...] in first-seen order, or None when the rows
    cannot share one game. Members drawn into several seats (mixture
    sampling is with replacement) get one position each; a repeated
    unordered seat-pair with different scores forces either extra seats
    or, failing that, a split by partition_group."""
    best: list | None = None

    def dfs(k: int, positions: list, used: set) -> None:
        nonlocal best
        if best is not None and len(positions) >= len(best):
            return
        if k == len(normed):
            if best is None or len(positions) < len(best):
                best = [list(p) for p in positions]
            return
        lo, hi, slo, shi = normed[k]
        if lo == hi and slo == shi:
            pairs = [ (i, i) for i, p in enumerate(positions)
                      if p[0] == lo and p[1] in (None, slo)]
            pairs.append(("new", "new"))
        else:
            pairs = []
            pa_list = [i for i, p in enumerate(positions)
                       if p[0] == lo and p[1] in (None, slo)] + ["new"]
            for pa in pa_list:
                pb_list = [i for i, p in enumerate(positions)
                           if i != pa and p[0] == hi
                           and p[1] in (None, shi)] + ["new"]
                for pb in pb_list:
                    pairs.append((pa, pb))
        for pa, pb in pairs:
            pos = [list(p) for p in positions]
            if pa == "new":
                pa = len(pos)
                pos.append([lo, None])
            if pb == "new":
                pb = len(pos)
                pos.append([hi, None])
            if pos[pa][1] is None:
                pos[pa][1] = slo
            if pos[pb][1] is None:
                pos[pb][1] = shi
            key = (min(pa, pb), max(pa, pb))
            if key in used:
                continue
            dfs(k + 1, pos, used | {key})

    dfs(0, [], set())
    return best


def _partition_exact(uniq: list[tuple]) -> list[list[tuple]]:
    """Best set partition: fewest total seat positions wins; ties split
    toward more games (a re-run collision costs 2+2 = 4 either way, while
    a true N-player game always merges strictly cheaper)."""
    n = len(uniq)
    realize: dict[int, int] = {}

    def cost(mask_rows: tuple) -> int:
        key = hash(mask_rows)
        if key not in realize:
            got = _realize(list(mask_rows))
            realize[key] = len(got) if got is not None else 10 ** 9
        return realize[key]

    best_assign: list[int] | None = None
    best_cost = (10 ** 9, 0)

    def rec(i: int, cur: list[int], mx: int) -> None:
        nonlocal best_assign, best_cost
        if i == n:
            blocks: dict[int, list] = {}
            for idx, b in enumerate(cur):
                blocks.setdefault(b, []).append(uniq[idx])
            total = sum(cost(tuple(b)) for b in blocks.values())
            key = (total, -len(blocks))
            if key < best_cost:
                best_cost = key
                best_assign = list(cur)
            return
        for b in range(mx + 1):
            cur.append(b)
            rec(i + 1, cur, mx)
            cur.pop()
        cur.append(mx + 1)
        rec(i + 1, cur, mx + 1)
        cur.pop()

    rec(0, [], -1)
    blocks = {}
    for idx, b in enumerate(best_assign or []):
        blocks.setdefault(b, []).append(uniq[idx])
    return [blocks[b] for b in sorted(blocks)]


def _partition_greedy(uniq: list[tuple]) -> list[list[tuple]]:
    """Best-effort split for pathological groups (>6 rows; all real
    history is <= 6): earliest block whose seat count would not grow,
    else a new block. Deterministic."""
    blocks: list[list[tuple]] = []
    for r in uniq:
        for b in blocks:
            before = _realize(b)
            after = _realize(b + [r])
            if after is not None and before is not None \
                    and len(after) <= len(before):
                b.append(r)
                break
        else:
            blocks.append([r])
    return blocks


def partition_group(normed: list[tuple]) -> list[list[tuple]]:
    """Split normalized pair rows into per-game blocks: exact-duplicate
    rows merge, conflicting re-runs of one replay path split (see
    _partition_exact), duplicate-seat games stay whole."""
    uniq = list(dict.fromkeys(normed))  # dedupe, first-seen order
    if not uniq:
        return []
    if len(uniq) <= 6:
        return _partition_exact(uniq)
    return _partition_greedy(uniq)


def build_game(gen: str, kind: str, map: str | None, replay: str,
               items: list[tuple[tuple, dict]]) -> dict | None:
    """One visual game from a consistent block: every seat with score,
    rank, margin vs field-best, effective points and outcome; the pair
    rows as detail. None when the block cannot be one game."""
    pos = _realize([n for n, _ in items])
    if pos is None:
        return None
    # Seat order follows the logged field order (seat 0 first), not the
    # normalized pair order: eval seats 0/1 are challenger/champion and the
    # page/tally read the default view off seats[0]. Duplicate-seat
    # positions share an id, so key on (id, score) by first appearance.
    seen: dict[tuple, int] = {}
    for r in [r for _, r in items]:
        for cid, sc in ((r["a"], r["score_a"]), (r["b"], r["score_b"])):
            seen.setdefault((cid, sc), len(seen))
    pos.sort(key=lambda p: seen.get((p[0], p[1]), len(seen)))
    scores = [s for _, s in pos]
    ranks = rank_of(scores)
    top = max(scores)
    ntop = sum(1 for s in scores if s == top)
    seats = []
    for k, (cid, sc) in enumerate(pos):
        others = [s for j, s in enumerate(scores) if j != k]
        margin = sc - (max(others) if others else sc)
        result = "win" if sc == top and ntop == 1 else \
            ("draw" if sc == top else "loss")
        seats.append({
            "id": cid, "score": sc, "rank": ranks[k],
            "margin": margin, "pts": 1.0 if result == "win" else
            (0.5 if result == "draw" else 0.0), "result": result,
        })
    return {
        "gen": gen, "kind": kind, "map": map, "replay": replay,
        "n": len(seats), "seats": seats,
        "pairs": [{"a": r["a"], "b": r["b"],
                    "score_a": r["score_a"], "score_b": r["score_b"]}
                   for _, r in items],
    }


def group_games(rows: list[dict]) -> list[dict]:
    """Pair rows -> per-game dicts, newest game first.

    Rows sharing a `game` id (one play, one id) group exactly; older rows
    fall back to the replay path, then split on conflicting re-runs and
    dedupe double-logs. Input newest-first (as from list_games) sets game
    order; seats/pairs build oldest-first for a stable picture."""
    keyed: dict[str, list] = {}
    meta: dict[str, dict] = {}
    for r in rows:
        key = game_key_of(r)
        keyed.setdefault(key, []).append(r)
        meta.setdefault(key, r)
    games = []
    for key, rs in keyed.items():
        oldest = rs[::-1]
        raws: dict[tuple, dict] = {}
        for r in oldest:
            raws.setdefault(_norm_row(r), r)
        m0 = meta[key]
        for block in partition_group([_norm_row(r) for r in oldest]):
            g = build_game(m0["gen"], m0["kind"], m0.get("map"),
                           m0["replay"], [(n, raws[n]) for n in block])
            if g is not None:
                games.append(g)
    return games


def member_game_result(game: dict, ref: str) -> str | None:
    """Ref's per-game outcome: best seat wins when a member holds several
    (duplicate-seat extras)."""
    order = {"win": 0, "draw": 1, "loss": 2}
    outs = [s["result"] for s in game["seats"] if s["id"] == ref]
    return min(outs, key=order.__getitem__) if outs else None


def tally_eval(games: list[dict]) -> dict[str, list[int]]:
    """Per-member W-D-L, one entry per eval GAME (win = sole top score,
    draw = tied top). Pairwise 2p history tallies exactly as before."""
    tally: dict[str, list[int]] = {}
    for g in games:
        if g["kind"] != "eval":
            continue
        for cid in dict.fromkeys(s["id"] for s in g["seats"]):
            w, d, l = tally.get(cid, [0, 0, 0])
            r = member_game_result(g, cid)
            tally[cid] = [w + (r == "win"), d + (r == "draw"),
                          l + (r == "loss")]
    return tally


def summarize_maps(games: list[dict]) -> list[dict]:
    """Per (map, seat-count): train/eval game counts plus the eval
    challenger-vs-champion record (fixed seats 0/1, valid for N seats)."""
    acc: dict[tuple, dict] = {}
    for g in games:
        key = (g.get("map"), g["n"])
        m = acc.setdefault(key, {"map": g.get("map"), "n": g["n"],
                                 "train": 0, "eval": 0,
                                 "cw": 0, "cd": 0, "cl": 0})
        if g["kind"] == "train":
            m["train"] += 1
        elif g["kind"] == "eval":
            m["eval"] += 1
            if g["n"] >= 2:
                a, b = g["seats"][0]["score"], g["seats"][1]["score"]
                m["cw"] += a > b
                m["cd"] += a == b
                m["cl"] += a < b
    return sorted(acc.values(),
                  key=lambda m: ((m["map"] or ""), m["n"]))


def snapshot(base: Path) -> dict:
    """Everything the page needs, in one JSON-able dict. One read per file."""
    archive.init(base)
    champ = None
    try:
        champ = archive.get_champion(base)
    except (OSError, ValueError, KeyError, TypeError):
        champ = None
    try:
        mix = _nash_cached(base)
    except (OSError, ValueError, KeyError, TypeError):
        mix = {}
    history = cached_history(base)
    grouped = cached_grouped(base)
    tally = tally_eval(grouped)
    members = []
    for m in archive.members(base):
        cid = m["id"]
        w, d, l = tally.get(cid, [0, 0, 0])
        members.append({
            "id": cid, "role": m["role"], "parent": m["parent"],
            "nash": round(mix.get(cid, 0.0), 4),
            "wins": w, "draws": d, "losses": l,
        })
    gens = []
    for h in history:
        ev = h.get("eval", {}) or {}
        tr = h.get("train", {}) or {}
        losses = tr.get("losses", []) or []
        thr = (h.get("config", {}) or {}).get("promote_threshold", 0.5)
        draws = ev.get("draws", 0)
        ngames = ev.get("games", 0)
        wr = ev.get("win_rate", 0.0)
        lower = archive.wilson_lower(ev.get("wins", 0) + 0.5 * draws, ngames)
        cfg = h.get("config", {}) or {}
        if not ev:
            reason = "held: waiting on first eval"
        elif h.get("promoted"):
            reason = f"promoted: lower {lower:.2f} clears threshold {thr:.2f}"
        else:
            reason = f"held: lower {lower:.2f} vs threshold {thr:.2f}"
        gens.append({
            "id": h.get("challenger", h.get("id", "?")),
            "champion": h.get("champion"),
            "train_return": tr.get("mean_return", 0.0),
            "train_loss": (sum(losses) / len(losses)) if losses else 0.0,
            "eval_w": ev.get("wins", 0), "eval_d": draws,
            "eval_games": ngames, "win_rate": wr,
            "wilson_lower": round(lower, 3),
            "threshold": thr,
            "promoted": bool(h.get("promoted")),
            "reason": reason,
            "arch": cfg.get("arch", "base"),
            "turns": cfg.get("turns", 0),
            "gamma": cfg.get("gamma", 0.0),
            "mean_margin": ev.get("mean_margin", 0.0),
            "margins": ev.get("margins", []),
            "exploiter": bool(h.get("exploiter")),
            "started_at": h.get("started_at"),
            "finished_at": h.get("finished_at"),
            "duration_s": h.get("duration_s"),
        })
    gens.reverse()
    durs = [h.get("duration_s") for h in history
            if isinstance(h.get("duration_s"), (int, float))]
    recent = durs[-5:]
    avg = sum(recent) / len(recent) if recent else None
    plan = {}
    try:
        plan = json.loads((base / "run_plan.json").read_text())
    except (OSError, ValueError):
        plan = {}
    target = plan.get("target_gens")
    run = {
        "finished": len(history),
        "target": target if isinstance(target, int) else None,
        "avg_s": round(avg, 1) if avg else None,
        "last_finished_at": history[-1].get("finished_at") if history else None,
    }
    losses = []
    for h in history:
        ls = ((h.get("train", {}) or {}).get("losses", []) or [])
        losses.append(sum(ls) / len(ls) if ls else None)
    curves = {
        "loss": losses,
        "ret": [((h.get("train", {}) or {}).get("mean_return", 0.0)) for h in history],
        "ids": [h.get("challenger", "") or "" for h in history],
    }
    return {
        "champion": champ,
        "members": members,
        "run": run,
        "curves": curves,
        "generations": gens,
        "games": grouped[:50],
        "game_total": len(grouped),
        "maps": summarize_maps(grouped),
        "status": archive.read_status(base),
        "counts": {"generations": len(history), "games": len(grouped)},
    }


def replay_page(base: Path, rel: str | None) -> str | None:
    """Visualizer HTML with the replay inlined. None if unsafe/missing."""
    if not rel or not rel.endswith(".replay"):
        return None
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


# ---------------------------------------------------------------- API


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
                    self._send(render_page().encode(), "text/html")
                elif parsed.path == "/api/snapshot":
                    _json(self, snapshot(base))
                elif parsed.path == "/api/games":
                    q = parse_qs(parsed.query)
                    member = q.get("member", [None])[0]
                    try:
                        limit = max(0, min(int(q.get("limit", ["50"])[0]), 200))
                    except ValueError:
                        limit = 50
                    try:
                        offset = max(int(q.get("offset", ["0"])[0]), 0)
                    except ValueError:
                        offset = 0
                    rows = cached_grouped(base)
                    if member is not None:
                        rows = [g for g in rows
                                if any(s["id"] == member for s in g["seats"])]
                    total = len(rows)
                    offset = min(offset, total)
                    _json(self, {"total": total,
                                 "rows": rows[offset:offset + limit]})
                elif parsed.path == "/replay":
                    rel = parse_qs(parsed.query).get("f", [None])[0]
                    page = replay_page(base, rel)
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
                    _json(self, {"error": f"unknown route: {parsed.path}"}, status=404)
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
                _json(self, {"error": f"{type(e).__name__}: {e}"}, status=500)

    return Handler


# ---------------------------------------------------------------- PAGE


STYLES = """
:root{
  --bg:#F6F7F9; --card:#FFFFFF; --border:#E3E6EA; --border-strong:#C9CFD6;
  --ink:#16191D; --secondary:#5B6470; --muted:#67707B;
  --accent:#2456E0; --success:#18794E; --danger:#C4322B; --warn:#8A5A00;
  --eval-bg:#EAF0FE; --eval-ink:#2456E0; --train-bg:#EDEFF1; --train-ink:#5B6470;
  --grid:#E9EDF1; --chart-text:#6B7480;
}
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,Roboto,"Helvetica Neue",Arial,sans-serif;
  background:var(--bg); color:var(--ink); margin:0; padding:24px max(16px,4vw) 48px;}
.wrap{max-width:1200px; margin:0 auto;}
h1{font-size:20px; margin:0 0 4px;}
.sub{color:var(--secondary); font-size:13px; margin:0 0 20px;}
.section-title{font-size:13px; font-weight:700; text-transform:uppercase; letter-spacing:.06em;
  color:var(--secondary); margin:32px 0 12px;}
.legend{font-size:12px; color:var(--muted); margin:-6px 0 12px;}
.stats{display:grid; grid-template-columns:repeat(3,1fr); gap:16px;}
.status-wide{grid-column:span 3;}
.card{background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px 20px;}
.stat-label{font-size:12px; color:var(--secondary);}
.stat-value{font-size:28px; font-weight:700; font-variant-numeric:tabular-nums; margin-top:2px;}
.stat-value .champ-star{font-size:20px;}
.champ-star{color:var(--warn); font-size:0.72em; vertical-align:1px;}
.progress{height:8px; background:var(--border); border-radius:4px; margin-top:10px; overflow:hidden;}
.progress>div{height:100%; background:var(--accent); border-radius:4px; transition:width .4s, background .4s;}
.status-line{font-size:14px; margin-top:2px;}
.charts{display:grid; grid-template-columns:repeat(auto-fit,minmax(min(340px,100%),1fr)); gap:16px;}
.chart-card h3{margin:0 0 2px; font-size:14px;}
.chart-sub{font-size:12px; color:var(--muted); margin:0 0 8px;}
.chart-head{display:flex; justify-content:space-between; align-items:baseline;}
.delta{font-size:12px; font-weight:700; padding:2px 8px; border-radius:20px;}
.delta.up{color:var(--success); background:#E6F4EC;}
.delta.down{color:var(--danger); background:#FBEAE8;}
.delta.flat{color:var(--secondary); background:var(--train-bg);}
canvas{width:100%; height:220px; display:block;}
.cols{display:grid; grid-template-columns:1fr 1.4fr; gap:16px; align-items:start;}
.table-scroll{overflow-x:auto;}
.table-tall{max-height:480px; overflow-y:auto;}
.table-tall thead th{position:sticky; top:0; z-index:1;}
table{border-collapse:collapse; width:100%; font-size:13.5px; font-variant-numeric:tabular-nums;}
th{background:#F1F3F5; text-align:left; font-size:12px; color:var(--secondary); font-weight:600;}
th,td{padding:9px 10px; border-bottom:1px solid var(--border);}
tr:last-child td{border-bottom:none;}
tbody tr:hover{background:#F8FAFC;}
td.num, th.num{text-align:right;}
.pill{display:inline-block; font-size:11px; font-weight:700; padding:2px 9px; border-radius:20px;}
.pill.eval{background:var(--eval-bg); color:var(--eval-ink);}
.pill.train{background:var(--train-bg); color:var(--train-ink);}
.badge{display:inline-block; font-size:11px; font-weight:700; padding:2px 9px; border-radius:20px;}
.badge.win{color:var(--success); background:#E6F4EC;}
.badge.loss{color:var(--danger); background:#FBEAE8;}
.badge.draw{color:var(--secondary); background:var(--train-bg);}
.badge.promoted{color:var(--success); background:#E6F4EC;}
.badge.held{color:var(--warn); background:#FBF3E2;}
.nash-wrap{display:flex; align-items:center; gap:8px;}
.nash-bar{flex:1; min-width:60px; height:6px; background:var(--border); border-radius:3px; overflow:hidden;}
.nash-bar>div{height:100%; background:var(--accent);}
.rate-wrap{display:flex; align-items:center; gap:8px;}
td.matchup, td.replay, .rate-text{white-space:nowrap;}
.pairs{font-size:12px; color:var(--muted); margin-top:3px; white-space:normal;}
.rate-bar{flex:1 1 70px; min-width:70px; height:6px; background:var(--border); border-radius:3px; position:relative; overflow:hidden;}
.rate-bar>div{height:100%; background:var(--success);}
.rate-bar{overflow:visible;}
.rate-bar>div{border-radius:3px;}
.rate-bar .marker{position:absolute;left:0;width:2px;background:var(--ink);top:-3px;bottom:-3px;box-shadow:0 0 0 1px #fff;z-index:1;}
.toolbar{display:flex; gap:10px; align-items:center; margin-bottom:10px; flex-wrap:wrap;}
.toolbar label{font-size:13px; color:var(--secondary);}
select{font-size:13px; padding:6px 10px; border:1px solid var(--border-strong); border-radius:8px; background:#fff;}
.live-toggle{display:flex; align-items:center; gap:6px; font-size:13px; color:var(--secondary);}
.pager{display:flex; gap:6px;}
.updated{font-size:12px; color:var(--muted); margin-left:auto;}
.pager button{font-size:12px; padding:5px 10px; border:1px solid var(--border-strong); border-radius:8px; background:#fff; cursor:pointer;}
.pager button:disabled{opacity:.4; cursor:default;}
#getting-started{margin-bottom:16px; font-size:14px;}
#stats-row{margin-top:0;}
.skip{position:absolute; left:-9999px; top:0; background:var(--ink); color:#fff; padding:8px 14px; z-index:99; border-radius:0 0 8px 0;}
.skip:focus{left:0; color:#fff;}
#error{display:none; background:#FBEAE8; color:var(--danger); border:1px solid #F0C4C0;
  border-radius:8px; padding:10px 14px; margin-bottom:16px; font-size:13px;}
.empty{padding:28px 20px; color:var(--secondary); font-size:14px;}
.empty code{background:#EFF1F4; padding:2px 6px; border-radius:4px; font-size:13px;}
a{color:var(--accent); text-decoration:none;}
a:hover{text-decoration:underline;}
.winner{font-weight:700;}
a:focus-visible,select:focus-visible,input:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:2px;}
@media (max-width:900px){
  .stats{grid-template-columns:repeat(2,1fr);}
  .stats>.card:nth-child(3){grid-column:span 2;}
  .status-wide{grid-column:span 2;}
  .cols{grid-template-columns:1fr;}
  body{padding:16px 16px 40px;}
}
"""

SCRIPT = """
let S=null, seq=0, lastHash="", lastGames="", live=true, lastTick=0;
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
    const kind=r.status>=500?"dashboard error":"request failed";
    throw new Error(kind+" HTTP "+r.status+detail+" on "+url);
  }
  return r.json();
}
function ago(ts){const s=Math.max(0,Math.round((Date.now()-ts)/1000));
  return s<2?"just now":s+"s ago";}
function shortReplay(rel){const p=(rel||"").split("/").filter(Boolean);
  return p.length>=3?p[p.length-3]:(p.pop()||"").replace(/\\.replay$/,"");}
function seatBadge(result){
  return {cls:result,label:result};
}
/* Charts: titled card, gridlines, min/max labels, headroom, HiDPI. */
function plot(id,series,color,fill,labels,desc){
  const cv=$(id),ctx=cv.getContext("2d");
  cv.setAttribute("role","img");
  if(desc)cv.setAttribute("aria-label",desc+": "+series.filter(v=>v!==null).join(", "));
  const dpr=window.devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;
  cv.width=W*dpr;cv.height=H*dpr;ctx.scale(dpr,dpr);
  ctx.clearRect(0,0,W,H);
  if(!series.length){ctx.fillStyle="#8A94A0";ctx.font="12px system-ui";
    ctx.fillText("no generations yet",12,20);return;}
  const vals=series.filter(v=>v!==null&&Number.isFinite(v));
  if(!vals.length){ctx.fillStyle="#8A94A0";ctx.font="12px system-ui";
    ctx.fillText("no data yet",12,20);return;}
  let mn=Math.min(...vals),mx=Math.max(...vals);
  if(mx-mn<1e-9){mn-=1;mx+=1;}
  const pad=(mx-mn)*0.12;mn-=pad;mx+=pad;
  const prec=(mx-mn)<0.5?3:2;
  const L=48,R=8,T=8,B=20,iw=W-L-R,ih=H-T-B;
  const X=i=>L+iw*(series.length<2?0.5:i/(series.length-1));
  const Y=v=>T+ih*(1-(v-mn)/(mx-mn));
  ctx.strokeStyle="#E9EDF1";ctx.fillStyle="#6B7480";ctx.font="10px system-ui";ctx.lineWidth=1;
  for(let k=0;k<=3;k++){const v=mn+(mx-mn)*k/3,y=Y(v);
    ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(W-R,y);ctx.stroke();
    let t=v.toFixed(prec);if(t==="-0.000"||t==="-0.00")t=t.slice(1);
    ctx.fillText(t,4,y+3);}
  const x0=(labels&&labels[0])||"gen 0";
  const x1=(labels&&labels[labels.length-1])||("gen "+(series.length-1));
  ctx.fillText(x0,L,H-6);
  const w1=ctx.measureText(x1).width;
  ctx.fillText(x1,W-R-w1,H-6);
  if(mn<0&&mx>0){ctx.save();ctx.setLineDash([4,3]);ctx.strokeStyle="#C9CFD6";
    ctx.beginPath();ctx.moveTo(L,Y(0));ctx.lineTo(W-R,Y(0));ctx.stroke();ctx.restore();}
  const segs=[];let cur=[];
  series.forEach((v,i)=>{if(v===null||!Number.isFinite(v)){if(cur.length)segs.push(cur),cur=[];}else cur.push(i);});
  if(cur.length)segs.push(cur);
  if(fill){const gr=ctx.createLinearGradient(0,T,0,H-B);
    gr.addColorStop(0,fill);gr.addColorStop(1,"rgba(255,255,255,0)");
    ctx.fillStyle=gr;
    for(const s of segs){ctx.beginPath();ctx.moveTo(X(s[0]),Y(series[s[0]]));
      s.forEach(i=>ctx.lineTo(X(i),Y(series[i])));
      ctx.lineTo(X(s[s.length-1]),H-B);ctx.lineTo(X(s[0]),H-B);ctx.closePath();ctx.fill();}}
  ctx.strokeStyle=color;ctx.lineWidth=2;ctx.lineJoin="round";
  for(const s of segs){ctx.beginPath();
    s.forEach((i,k)=>k?ctx.lineTo(X(i),Y(series[i])):ctx.moveTo(X(i),Y(series[i])));ctx.stroke();}
  const li=segs.length?segs[segs.length-1].slice(-1)[0]:0;
  ctx.fillStyle=color;ctx.beginPath();ctx.arc(X(li),Y(series[li]),3.5,0,7);ctx.fill();
}
function deltaChip(vals,invert){
  if(vals.length<2) return '<span class="delta flat">—</span>';
  const d=vals[vals.length-1]-vals[vals.length-2];
  if(Math.abs(d)<1e-9) return '<span class="delta flat">±0.000</span>';
  const good=invert?d<0:d>0;
  return `<span class="delta ${good?"up":"down"}" title="vs previous generation">${d>0?"+":""}${d.toFixed(3)}</span>`;
}
function clock(ts){const d=new Date(ts*1000);return d.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});}
function renderHeader(){
  $("st-champ").innerHTML=esc(S.champion||"—")+(S.champion?' <span class="champ-star">★</span>':"");
  $("getting-started").style.display=S.counts.generations?"none":"block";
  $("st-gen").textContent=S.counts.generations;
  $("st-games").textContent=S.counts.games;
  const r=S.run||{};
  $("st-run").textContent=r.target?`gen ${r.finished} / ${r.target}`:`gen ${r.finished||0}`;
  const bits=[];
  if(r.last_finished_at) bits.push("last finished "+clock(r.last_finished_at));
  if(r.avg_s) bits.push(`avg ${r.avg_s}s/gen`);
  if(r.target&&r.avg_s&&r.target>r.finished) bits.push(`ETA ${clock(Date.now()/1000+(r.target-r.finished)*r.avg_s)}`);
  $("st-eta").textContent=bits.join(" · ")||"no timing data yet";
  const st=S.status||{},el=$("st-status"),bar=$("st-bar");
  bar.style.width="0%";bar.style.background="var(--accent)";
  if(st.phase==="train"){
    el.innerHTML=`training <b>${esc(st.challenger||"")}</b> · game ${Math.max(0,+st.done||0)}/${Math.max(0,+st.total||0)} · last mean return <b>${(+st.last_mean_return||0).toFixed(2)}</b>`;
    bar.style.width=(100*st.done/Math.max(1,st.total))+"%";
  }else if(st.phase==="eval"){
    el.innerHTML=`evaluating <b>${esc(st.challenger||"")}</b> · duel ${Math.max(0,+st.done||0)}/${Math.max(0,+st.total||0)} · <b>${Math.max(0,+st.wins||0)}W ${Math.max(0,+st.draws||0)}D</b> so far`;
    bar.style.width=(100*st.done/Math.max(1,st.total))+"%";
  }else if(st.phase==="done"){
    el.innerHTML=`last run finished: <b>${esc(st.challenger||"")}</b> `+
      (st.promoted?'<span class="badge promoted">promoted ★</span>':'<span class="badge held">held</span>')+
      ` · champion ${esc(st.champion||"")} · idle, waiting for the next run`;
    bar.style.width="100%";
    bar.style.background=st.promoted?"var(--success)":"var(--secondary)";
  }else{
    el.innerHTML=S.counts.generations?`idle · last champion ${esc(S.champion||"—")}`:"waiting for the first generation…";
  }
  $("updated").textContent="updated "+ago(lastTick)+" · "+(live?"live":"paused");
}
function renderCurves(){
  const byGen=S.curves.loss;
  const rets=S.curves.ret;
  const ids=S.curves.ids;
  const nz=byGen.filter(v=>v!==null);
  plot("ch-loss",byGen,"#C4322B","rgba(196,50,43,.12)",ids,"mean loss, "+ids.length+" generations");
  plot("ch-ret",rets,"#18794E","rgba(24,121,78,.12)",ids,"mean return, "+ids.length+" generations");
  $("loss-delta").innerHTML=deltaChip(nz,true);
  $("ret-delta").innerHTML=deltaChip(rets,false);
  $("loss-last").textContent=nz.length?nz[nz.length-1].toFixed(3):"no data";
  $("loss-last").title=nz.length?"mean loss "+nz[nz.length-1].toFixed(5):"";
  $("ret-last").textContent=rets.length?rets[rets.length-1].toFixed(2):"—";
  $("ret-last").title=rets.length?"mean return "+rets[rets.length-1].toFixed(4):"";
}
function renderPopulation(){
  const rows=S.members.map(m=>{const role=m.role==="main"?"seed":m.role;
    return `<tr><td>${esc(m.id)}${m.id===S.champion?' <span class="champ-star">★</span>':""}</td>`+
    `<td>${esc(role)}${m.role==="main"?' <span class="legend">founding weights</span>':""}</td><td>${esc(m.parent||"—")}</td>`+
    `<td><span class="nash-wrap"><span class="nash-bar"><div style="width:${(m.nash*100).toFixed(1)}%"></div></span>${m.nash.toFixed(2)}</span></td>`+
    `<td class="num">${m.wins}-${m.draws}-${m.losses}</td></tr>`}).join("");
  $("pop-body").innerHTML=rows||'<tr><td colspan="5" class="empty">no checkpoints yet — start a generation</td></tr>';
}
function renderGenerations(){
  const rows=S.generations.map(g=>{
    const pct=g.eval_games?100*(g.win_rate):0;
    return `<tr><td>${esc(g.id)}${g.finished_at?`<div class="legend">${clock(g.finished_at)}</div>`:""}${g.duration_s?`<div class="legend">${g.duration_s}s</div>`:""}</td><td class="num">${g.train_return.toFixed(2)}</td>`+
    `<td class="num">${g.train_loss.toFixed(3)}</td>`+
    `<td><span class="rate-wrap rate-text" title="Wilson lower bound (z=1.0) ${g.wilson_lower.toFixed(2)} vs promotion threshold ${g.threshold.toFixed(2)}"><span class="rate-bar"><div style="width:${pct.toFixed(0)}%"></div>`+
    `<span class="marker" style="left:${(g.threshold*100).toFixed(0)}%"></span></span>`+
    `${g.eval_w}-${g.eval_d}-${Math.max(0,g.eval_games-g.eval_w-g.eval_d)} · ${(g.win_rate*100).toFixed(0)}% (draw=&#189;) · lower ${g.wilson_lower.toFixed(2)} · margin ${g.mean_margin.toFixed(2)}</span></td>`+
    `<td>${g.promoted?'<span class="badge promoted">promoted ★</span>':'<span class="badge held">held</span>'}`+
    `<div class="legend" style="margin:4px 0 0">${esc(g.reason)}</div>`+(g.exploiter?` <span class="badge draw">exploiter</span>`:'')+`</td>`+
    `<td class="num legend">${esc(g.arch)} · ${g.turns}t · γ${g.gamma}</td></tr>`;}).join("");
  $("gen-body").innerHTML=rows||'<tr><td colspan="6" class="empty">no completed generations yet</td></tr>';
}
function memberIds(){return S.members.map(m=>m.id);}
function renderMemberOptions(){
  const sel=$("member"),cur=sel.value||new URLSearchParams(location.hash.slice(1)).get("member")||"";
  const ids=memberIds();
  if(sel.options.length-1===ids.length && ids.every((id,i)=>sel.options[i+1].text===id)){
    if(cur&&ids.includes(cur)) sel.value=cur;
    return; // unchanged: leave the open dropdown alone
  }
  sel.innerHTML='<option value="">all members</option>'+ids.map(id=>`<option>${esc(id)}</option>`).join("");
  if(cur&&ids.includes(cur)) sel.value=cur;
}
async function renderGames(my){
  const m=$("member").value;
  if(m)history.replaceState(null,"","#member="+encodeURIComponent(m));
  else history.replaceState(null,"",location.pathname);
  if($("games-body").matches(":hover")||$("games-body").contains(document.activeElement)) return true; // reader busy: retry next poll
  const qparts=[];
  if(m)qparts.push("member="+encodeURIComponent(m));
  qparts.push("limit=100","offset="+gamesOffset);
  let data;
  try{data=await fetchJSON("/api/games?"+qparts.join("&"));}
  catch(e){
    $("error").style.display="block";
    $("error").textContent="games feed failed ("+e.message+") — showing last good table. retrying…";
    return false;
  }
  if(my!==seq||$("member").value!==m) return true; // a newer poll or filter won
  const h=m+"|"+gamesOffset+"|"+JSON.stringify(data);
  if(h===lastGames) return true; // unchanged: keep focus, selection, scroll
  lastGames=h;
  const rows=data.rows.map(x=>{
    const seats=x.seats||[];
    const refS=seats.find(s=>s.id===m)||seats[0]||{id:"?",score:"?",result:"draw"};
    const o=seatBadge(refS.result);
    const label=x.gen+" · "+shortReplay(x.replay);
    const names=seats.map(s=>s.id).join(" vs ");
    let match;
    if(seats.length<=2){
      const s0=seats[0]||{id:"?",score:"?",result:"draw"};
      const s1=seats[1]||{id:"?",score:"?",result:"draw"};
      const w0=s0.result==="win",w1=s1.result==="win";
      const w0h=(w0?'<span class="winner">':'')+esc(s0.id)+(w0?'</span>':'');
      const w1h=(w1?'<span class="winner">':'')+esc(s1.id)+(w1?'</span>':'');
      match=`<td class="matchup" title="engine score">${w0h} ${s0.score} – ${s1.score} ${w1h}</td>`;
    }else{
      const line=seats.map(s=>(s.result==="win"?'<span class="winner">':'')+esc(s.id)+" "+s.score+(s.result==="win"?'</span>':'')).join(" · ");
      const pairs=(x.pairs||[]).map(p=>esc(p.a)+" "+p.score_a+"–"+p.score_b+" "+esc(p.b)).join(" · ");
      match=`<td class="matchup" title="engine scores, all ${seats.length} seats">${line}<div class="pairs">${pairs}</div></td>`;
    }
    return `<tr><td>${esc(x.gen)}</td><td><span class="pill ${esc(x.kind)}">${esc(x.kind)}</span></td>`+
    match+`<td><span class="badge ${o.cls}">${o.label}</span></td>`+
    `<td class="replay"><a href="/replay?f=${encodeURIComponent(x.replay)}" target="_blank" rel="noopener" title="${esc(names)}, gen ${esc(x.gen)} — opens in a new tab">${esc(label)}<span aria-hidden="true"> ↗</span></a></td></tr>`;}).join("");
  $("games-body").innerHTML=rows||(data.total?`<tr><td colspan="5" class="empty">no games on this page — use the pager above</td></tr>`:(m?`<tr><td colspan="5" class="empty">no games logged for ${esc(m)} yet</td></tr>`:'<tr><td colspan="5" class="empty">no games logged yet — they appear here as each finishes</td></tr>'));
  const pages=Math.max(1,Math.ceil(data.total/100));
  const page=Math.floor(gamesOffset/100)+1;
  $("games-count").textContent=`showing ${data.rows.length} of ${data.total} · page ${Math.min(page,pages)} of ${pages}`;
  $("pg-prev").disabled=gamesOffset<=0;
  $("pg-next").disabled=gamesOffset+100>=data.total;
  return true;
}
function renderMaps(){
  const rows=(S.maps||[]).map(m=>{
    return `<tr><td>${esc(m.map||"unknown")}</td><td class="num">${m.n}</td>`+
    `<td class="num">${m.train}</td><td class="num">${m.eval}</td>`+
    `<td class="num">${m.cw}-${m.cd}-${m.cl}</td></tr>`;}).join("");
  $("maps-body").innerHTML=rows||'<tr><td colspan="5" class="empty">no games logged yet — they appear here as each finishes</td></tr>';
}
async function load(){
  if(!live) return;
  const my=++seq;
  try{
    const snap=await fetchJSON("/api/snapshot");
    if(my!==seq) return; // a newer poll won
    const h=JSON.stringify(snap);
    lastTick=Date.now();
    $("error").style.display="none";
    if(h!==lastHash){lastHash=h;S=snap;
      renderHeader();renderCurves();renderPopulation();renderGenerations();renderMemberOptions();renderMaps();}
    else renderHeader();
    if(!hashSeeded){hashSeeded=true;
      const hm=new URLSearchParams(location.hash.slice(1)).get("member");
      if(hm){const sel=$("member");
        if([...sel.options].some(o=>o.text===hm)){sel.value=hm;gamesOffset=0;}
        else history.replaceState(null,"",location.pathname);}}
    const ok=await renderGames(my);
    $("updated").textContent="updated "+ago(lastTick)+" · "+(ok?"live":"games feed stale · live snapshot");
  }catch(e){
    $("error").style.display="block";
    $("error").textContent=lastTick?"connection lost ("+e.message+") — showing last good data from "+ago(lastTick)+". retrying…"
      :"connection lost ("+e.message+") — no data yet. retrying…";
  }
}
function activePhase(){const p=S&&S.status&&S.status.phase;return p==="train"||p==="eval";}
function tick(){load().finally(()=>setTimeout(tick,live?(activePhase()?5000:15000):15000));}
let gamesOffset=0,hashSeeded=false;
$("member").addEventListener("change",()=>{gamesOffset=0;++seq;renderGames(seq);});
$("pg-prev").addEventListener("click",()=>{gamesOffset=Math.max(0,gamesOffset-100);renderGames(++seq);});
$("pg-next").addEventListener("click",()=>{gamesOffset+=100;renderGames(++seq);});
$("live-toggle").addEventListener("change",e=>{live=e.target.checked;
  if(!live)seq++; // invalidate in-flight polls
  $("live-label").textContent=live?"live":"paused";
  $("updated").textContent="updated "+ago(lastTick)+" · "+(live?"live":"paused");load();});
let resizeT=0;
window.addEventListener("resize",()=>{clearTimeout(resizeT);resizeT=setTimeout(()=>{if(S)renderCurves();},150);});
load();
tick();
"""


def render_page() -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AlphaAnt training</title>
<style>{STYLES}</style></head>
<body><a class="skip" href="#games-card">skip to games</a><a class="skip" href="#gen-card">skip to generations</a><div class="wrap">
<h1>AlphaAnt training</h1>
<p class="sub">mirror self-play · policy gradients · scripted promotion — nothing external, ever</p>
<div id="error" role="alert"></div>
<div class="card" id="getting-started" style="display:none"><b>No generations yet.</b> Start one with:
<code>.venv/bin/python ml/selfplay.py --train-games 4 --eval-games 6 --turns 50 --no-commit</code>
— games, curves and population appear here as it runs.</div>
<div class="stats" id="stats-row">
  <div class="card"><div class="stat-label">Champion</div><div class="stat-value" id="st-champ">—</div></div>
  <div class="card"><div class="stat-label">Generations</div><div class="stat-value" id="st-gen">0</div></div>
  <div class="card"><div class="stat-label">Games logged (train + eval)</div><div class="stat-value" id="st-games">0</div></div>
  <div class="card"><div class="stat-label">Run</div><div class="stat-value" id="st-run">—</div><div class="legend" id="st-eta"></div></div>
  <div class="card status-wide"><div class="stat-label">Status</div>
    <div class="status-line" id="st-status">loading…</div>
    <div class="progress"><div id="st-bar" style="width:0%"></div></div></div>
</div>
<div class="section-title">Training curves</div>
<div class="legend">mean policy loss per generation (down is good) · mean episode return per generation (up is good) · one point per generation, oldest → newest · axes span the data range</div>
<div class="charts">
  <div class="card chart-card"><div class="chart-head"><h3>Policy loss <span id="loss-last"></span></h3><span id="loss-delta"></span></div>
    <p class="chart-sub">mean REINFORCE loss per generation</p><canvas id="ch-loss"></canvas></div>
  <div class="card chart-card"><div class="chart-head"><h3>Mean return <span id="ret-last"></span></h3><span id="ret-delta"></span></div>
    <p class="chart-sub">discounted episode return, one point per generation</p><canvas id="ch-ret"></canvas></div>
</div>
<div class="section-title">Generations</div>
<div class="legend">why each challenger was promoted or held — challenger W-D-L · score counts a draw as half a win · green fill is win rate, tick is the promotion threshold</div>
<div class="card table-scroll table-tall" id="gen-card"><table>
<tr><th>challenger</th><th class="num">train return</th><th class="num">train loss</th><th>eval vs champion</th><th>result</th><th class="num">config</th></tr>
<tbody id="gen-body"></tbody></table></div>
<div class="cols">
<div>
<div class="section-title">Population</div>
<div class="legend">nash = mixture share, display only (challengers only face the champion, so it cannot rank them) · W-D-L counts eval games: one entry per game (win = sole top score, draw = tied top)</div>
<div class="card table-scroll table-tall"><table>
<tr><th>id</th><th>role</th><th>parent</th><th>nash</th><th class="num">W-D-L (eval)</th></tr>
<tbody id="pop-body"></tbody></table></div>
</div>
<div>
<div class="section-title">Recent games</div>
<div class="legend">train = practice (may include self-play) · eval = promotion duels vs champion · matchup scores are engine points · N-seat games list every seat, pair scores below</div>
<div class="card" id="games-card">
<div class="toolbar">
<label for="member">member</label>
<select id="member"><option value="">all members</option></select>
<label class="live-toggle"><input type="checkbox" id="live-toggle" checked> <span id="live-label">live</span></label>
<span class="pager"><button id="pg-prev" type="button">← newer</button><button id="pg-next" type="button">older →</button></span>
<span class="legend" id="games-count" style="margin:0"></span>
<span class="updated" id="updated" title="page refresh time — data may be older while the run is idle"></span>
</div>
<div class="table-scroll" style="max-height:480px; overflow-y:auto;"><table>
<caption class="legend" style="text-align:left; padding:0 0 6px">result is the first-listed side's view · switches to the filtered member when filtered</caption>
<tr><th>gen</th><th>kind</th><th>matchup</th><th>result</th><th>replay</th></tr>
<tbody id="games-body"></tbody></table></div>
</div>
</div>
<div class="section-title">Maps</div>
<div class="legend">per board and seat count — games logged per phase · chal is challenger-vs-champion on eval (fixed seats 0/1, extras are shared weather)</div>
<div class="card table-scroll table-tall"><table>
<tr><th>map</th><th class="num">seats</th><th class="num">train</th><th class="num">eval</th><th class="num">chal W-D-L (eval)</th></tr>
<tbody id="maps-body"></tbody></table></div>
</div>
</div>
<script>{SCRIPT}</script></body></html>
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
