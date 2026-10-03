"""One autoresearch iteration: play the fixed 3x10p budget, score it.

Every game enters league/games.jsonl. The harness rebuilds the ratings
from that log at the start, so the log is the single source of truth.
The score is the snapshot mu - 3 * sigma at the end of the budget, and
the harness appends it to docs/PROGRESS.jsonl. Later games may move a
bot's live rating; the recorded score never moves.

The budget, maps, seeds, and selection are fixed. No flag changes
them. A commit cannot play more than one budget. A completed commit
plays no game on a second run and prints the recorded score; a run
stopped part-way plays the games that remain.

Usage:
  python autoresearch/iteration.py --bot autoresearch/bot/main.bot
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "league"))

import ratings as R  # noqa: E402
from matchmake import (  # noqa: E402
    MAPS_ROOT,
    assign_positions,
    maps_for_players,
    read_log,
)
from play import play_match  # noqa: E402
from pool import (  # noqa: E402
    WORKBASE,
    bot_id,
    content_hash,
    engine_on_main,
    is_clean,
    last_touch,
    main_merged,
    parse_id,
    prune_replays,
    prune_worktrees,
    short,
)
from pool import (  # noqa: E402
    pool as pool_ids,
)

GAMES_LOG = ROOT / "league" / "games.jsonl"
RATINGS_PATH = ROOT / "league" / "ratings.json"
RUNS = ROOT / "autoresearch" / "runs"
PROGRESS = ROOT / "autoresearch" / "docs" / "PROGRESS.jsonl"
DEFAULT_BOT = "autoresearch/bot/main.bot"

# Binding numbers. The harness fixes them; no flag changes them.
# The budget is 3 games of 10 players: a pool-range census skeleton,
# then spreads at 1.25 and 1.875 off the recent low-sigma tertile
# (placement champion iter 133). 30 slots, same as the old budget.
GAMES = 3
GAME_SIZE = 10
STAGE_WIDTHS: tuple[float | None, ...] = (None, 1.25, 1.875)
TURNS = 1000
TURNTIME = 1000
LOADTIME = 3000
SEED = 0

# One tag for one budget. PROGRESS.jsonl is append-only; rows with an
# older tag stay in the file and are ignored for the champion.
BUDGET = f"games={GAMES}x{GAME_SIZE}p,turns={TURNS},sel=census-tertile1,score=mu"

# Anchor pool: recent arrivals only. Rulers calcify, so old ratings
# cannot anchor new bots (placement iters 124/133/147/148).
RECENT_WINDOW = 400


def candidate_id(root: str | Path, botfile: str, rev: str | None = None) -> str:
    """The bot id a manifest has. Default rev: the newest commit that
    changed the bot's directory, so later commits cannot shift it."""
    root = Path(root)
    p = Path(botfile)
    if not p.is_absolute():
        p = root / p
    rel = p.resolve().relative_to(root.resolve())
    sha = short(root, rev) if rev else last_touch(root, rel.parent.as_posix())
    return bot_id(rel.as_posix(), sha)


def counts(records: list[dict], bid: str) -> dict:
    """Budget games already played by a candidate (10p fields only)."""
    return {
        "games": sum(
            1 for r in records if bid in r["field"] and len(r["field"]) == GAME_SIZE
        )
    }


def planned(records: list[dict], bid: str, games: int) -> int:
    """Budget left: games without a result yet."""
    return max(0, games - counts(records, bid)["games"])


def recent_window(
    cands: list[str], ratings: dict, window: int = RECENT_WINDOW
) -> list[str]:
    """Candidates oldest first by first appearance in the ratings log.
    Unrated ids sort newest, tie-broken by id."""
    order = {bid: i for i, bid in enumerate(ratings)}
    fresh = len(ratings)
    ranked = sorted(cands, key=lambda c: (order.get(c, fresh), c))
    return ranked[-window:] if window < len(ranked) else ranked


def tertile_anchors(
    cands: list[str], ratings: dict, window: int = RECENT_WINDOW
) -> list[str]:
    """Lowest-sigma third of the recent window, sigma order. Stale
    rulers carry old errors, so only calibrated rulers anchor."""
    recent = recent_window(cands, ratings, window)
    ranked = sorted(recent, key=lambda c: (R.for_id(ratings, c)["sigma"], c))
    return ranked[: max(1, len(ranked) // 3)]


def census_opponents(bid: str, cands: list[str], ratings: dict, k: int) -> list[str]:
    """k distinct opponents spanning the pool mu range, nearest ruler
    to each evenly spaced site. Bot-independent skeleton: it binds
    the tails before any refine game. Short pools return all."""
    mus = [R.for_id(ratings, c)["mu"] for c in cands]
    mus.append(R.for_id(ratings, bid)["mu"])
    lo, hi = min(mus), max(mus)
    opps: list[str] = []
    used = {bid}
    for j in range(k):
        t = lo if hi - lo < 1e-9 else lo + (hi - lo) * (j + 1) / (k + 1)
        rest = [c for c in cands if c not in used]
        if not rest:
            break
        pick = min(
            rest,
            key=lambda c: (
                abs(R.for_id(ratings, c)["mu"] - t),
                R.for_id(ratings, c)["sigma"],
                c,
            ),
        )
        used.add(pick)
        opps.append(pick)
    return opps


def spread_field(
    bid: str, cands: list[str], ratings: dict, n: int, width: float
) -> list[str]:
    """Field: the candidate plus n-1 rulers near Gaussian quantiles of
    N(mu, width*sigma), matched inside the recent-tertile anchors
    first and the full pool after. Greedy proximity stands."""
    e = R.for_id(ratings, bid)
    dist = NormalDist(e["mu"], max(width * e["sigma"], 0.5))
    anchors = tertile_anchors([c for c in cands if c != bid], ratings)
    field = [bid]
    used = {bid}
    for j in range(n - 1):
        t = dist.inv_cdf((j + 1) / n)
        rest = [c for c in anchors if c not in used] or [
            c for c in cands if c not in used
        ]
        if not rest:
            break
        pick = min(
            rest,
            key=lambda c: (
                abs(R.for_id(ratings, c)["mu"] - t),
                R.for_id(ratings, c)["sigma"],
                c,
            ),
        )
        used.add(pick)
        field.append(pick)
    return field


def pick_maps(rng: random.Random, candidates: list[str], k: int) -> list[str]:
    """k distinct maps, shuffled. Fewer only if the pool is smaller."""
    pool = list(candidates)
    rng.shuffle(pool)
    return pool[:k]


def score(ratings: dict, bid: str) -> tuple[float, float, float]:
    """The objective: mu, the estimated skill. The exam behind it
    (census-tertile 3x10p) already prices uncertainty into the
    measurement, so no sigma discount."""
    e = R.for_id(ratings, bid)
    return e["mu"], e["sigma"], e["mu"]


def result_line(rec: dict, bid: str | None = None) -> str:
    """The ranked result, best first. A duplicate label gets a short
    sha suffix; the candidate is marked with an asterisk."""
    names = [short_name(b) for b in rec["result"]]
    counts = Counter(names)
    parts = []
    for b, name in zip(rec["result"], names, strict=True):
        if counts[name] > 1:
            name = f"{name}@{parse_id(b)[1]}"
        if bid is not None and b == bid:
            name = f"*{name}"
        parts.append(name)
    return " > ".join(parts)


def iteration_summary(records: list[dict], bid: str) -> str:
    """Copy-paste line for the worklog: games played and the rank of
    each budget game for one candidate."""
    ranks = []
    for r in records:
        if bid not in r["field"]:
            continue
        ranks.append((len(r["field"]), r["result"].index(bid) + 1))
    ranks.sort()
    games = " ".join(f"{n}p:{rank}" for n, rank in ranks)
    return f"games: {len(ranks)}, ranks {games}"


def short_name(bid: str) -> str:
    """Readable label: the dir for main.bot, the manifest stem otherwise."""
    path = Path(bid.rsplit("-", 1)[0])
    return path.parent.as_posix() if path.name == "main.bot" else path.stem


def read_progress(path: str | Path | None = None) -> list[dict]:
    """Recorded iteration scores, one JSON object per line. A bad
    line is skipped, so an edit cannot corrupt the record."""
    p = Path(path) if path is not None else PROGRESS
    if not p.exists():
        return []
    rows = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            # Legacy rows recorded lb; the score column carries both.
            sc = row.get("score", row.get("lb"))
            rows.append(
                {
                    "date": row["date"],
                    "bot": row["bot"],
                    "mu": float(row["mu"]),
                    "sigma": float(row["sigma"]),
                    "score": float(sc),
                    "games": int(row["games"]),
                    "champion": row["champion"],
                    "budget": row.get("budget"),
                }
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    return rows


def record_report(
    bid: str,
    mu: float,
    sigma: float,
    sc: float,
    games: int,
    path: str | Path | None = None,
) -> tuple[dict, dict | None, bool]:
    """Append one score row, once. Returns (row, prior champion, appended).
    The prior champion is the best recorded score before this run."""
    p = Path(path) if path is not None else PROGRESS
    rows = read_progress(p)
    same = [r for r in rows if r["budget"] == BUDGET]
    prior = max(same, key=lambda r: r["score"]) if same else None
    for r in rows:
        if r["bot"] == bid:
            return r, prior, False
    row = {
        "date": date.today().isoformat(),
        "bot": bid,
        "mu": mu,
        "sigma": sigma,
        "score": sc,
        "games": games,
        "champion": prior["bot"] if prior else None,
        "budget": BUDGET,
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as fh:
        fh.write(json.dumps(row) + "\n")
    return row, prior, True


def canonical_duplicate(
    root: str | Path, bid: str, candidates: list[str]
) -> str | None:
    """The candidate id that shares this code, if any. The bot pool
    keeps one id per content hash, so a duplicate hides the older id."""
    path, sha = parse_id(bid)
    wanted = content_hash(root, sha, path)
    for c in candidates:
        cpath, csha = parse_id(c)
        if content_hash(root, csha, cpath) == wanted:
            return c
    return None


def play_one(
    root: Path,
    field: list[str],
    map_rel: str,
    log_dir: Path,
    rng: random.Random,
    workbase: str | Path,
) -> dict:
    rec = play_match(
        root,
        sys.executable,
        field,
        map_rel,
        TURNS,
        TURNTIME,
        LOADTIME,
        rng.randrange(10**9),
        rng.randrange(10**9),
        log_dir,
        workbase=workbase,
    )
    p = log_dir
    if p.is_relative_to(root):
        p = p.relative_to(root)
    rec["replay"] = (p / "0.replay").as_posix()
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot", default=DEFAULT_BOT)
    ap.add_argument("--rev", default=None)
    ap.add_argument("--runs", default=str(RUNS))
    ap.add_argument("--workbase", default=str(WORKBASE))
    ap.add_argument("--max-worktree-gb", type=float, default=1.0)
    ap.add_argument("--max-replay-gb", type=float, default=5.0)
    args = ap.parse_args(argv)

    root = ROOT
    if not engine_on_main(root):
        print("tools/ diverges from branch main; the engine is fixed", file=sys.stderr)
        return 3
    if not main_merged(root):
        print("main is not merged; run `git merge main`", file=sys.stderr)
        return 4
    if not is_clean(root):
        print("bot tree is dirty; commit before logged play", file=sys.stderr)
        return 2
    bid = candidate_id(root, args.bot, args.rev)
    records = read_log(GAMES_LOG)
    ratings = R.rebuild(records)
    R.save(RATINGS_PATH, ratings)
    done = counts(records, bid)["games"]
    print(f"candidate {bid}", flush=True)

    games_left = planned(records, bid, GAMES)

    pool = pool_ids(root, ratings)
    if bid not in set(pool):
        dup = canonical_duplicate(root, bid, pool)
        games = R.for_id(ratings, dup)["games"] if dup else 0
        if games:
            print(
                f"{bid} duplicates rated bot {dup} ({games} games); make a real change",
                file=sys.stderr,
            )
            return 1

    runs = Path(args.runs)
    sha = parse_id(bid)[1]
    prune_worktrees(args.workbase, int(args.max_worktree_gb * 1e9))
    prune_replays(runs, int(args.max_replay_gb * 1e9), protect={str(runs / sha)})
    rng = random.Random(f"{SEED}:{bid}:{done}")
    used = {r["map"] for r in records if bid in r["field"]}

    with open(GAMES_LOG, "a") as fh:
        maps = [f"tools/maps/{m}" for m in maps_for_players(MAPS_ROOT, GAME_SIZE)]
        maps = [m for m in maps if m not in used]
        if len(maps) < games_left:
            raise ValueError(f"only {len(maps)} unused {GAME_SIZE}p maps")
        for map_rel in pick_maps(rng, maps, games_left):
            used.add(map_rel)
            stage = done
            cands = [c for c in pool_ids(root, ratings) if c != bid]
            width = STAGE_WIDTHS[stage % len(STAGE_WIDTHS)]
            if width is None:
                opps = census_opponents(bid, cands, ratings, GAME_SIZE - 1)
            else:
                opps = spread_field(bid, cands, ratings, GAME_SIZE, width)[1:]
            if len(opps) != GAME_SIZE - 1:
                raise ValueError(
                    f"pool too small: wanted {GAME_SIZE - 1}, got {len(opps)}"
                )
            field = [bid] + assign_positions(opps, rng)
            done += 1
            log_dir = runs / sha / f"game_{done:02d}"
            rec = play_one(root, field, map_rel, log_dir, rng, args.workbase)
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            ratings = R.update(ratings, rec["field"], rec["result"])
            R.save(RATINGS_PATH, ratings)
            rank = rec["result"].index(bid) + 1
            mu, sigma, sc = score(ratings, bid)
            print(
                f"game {done}/{GAMES} "
                f"{Path(map_rel).name} {result_line(rec, bid)} "
                f"-> rank {rank}/{GAME_SIZE}  cand mu {mu:.1f} "
                f"sigma {sigma:.2f} score {sc:.1f}",
                flush=True,
            )

    mu, sigma, sc = score(ratings, bid)
    games = done
    row, prior, appended = record_report(bid, mu, sigma, sc, games)
    print(f"score {bid}  mu {mu:.1f}  sigma {sigma:.2f}  score {sc:.1f}", flush=True)
    if not appended:
        best = prior or row
        print(
            f"recorded earlier; best is {best['bot']} score {best['score']:.1f}",
            flush=True,
        )
    elif prior is None:
        print("report: first recorded score for this budget (baseline)", flush=True)
    elif sc > prior["score"]:
        print(
            f"report: beats champion {prior['bot']} score {prior['score']:.1f}",
            flush=True,
        )
    else:
        print(
            f"report: below champion {prior['bot']} score {prior['score']:.1f}",
            flush=True,
        )
    print(iteration_summary(read_log(GAMES_LOG), bid), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
