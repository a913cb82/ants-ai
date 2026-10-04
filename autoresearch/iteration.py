"""One autoresearch iteration: play the placement champion schedule.

The schedule is the placement champion (iter 43, corr 0.9931 over
30 seeds): one 10-player census over full-pool mass, one 6-player
refine over bot-centered below/peer/above bins by mass quota from
the low-sigma tertile of the last 400, then seven duels at the best
draw odds + 0.02 sigma over the 40 nearest rulers. Recency is
commit order, oldest first: the window is the last 400 pool
members by commit. Duels stay flat-info.

Every game enters league/games.jsonl. The harness rebuilds the ratings
from that log at the start, so the log is the single source of truth.
The score is the snapshot mu at the end of the budget, and
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
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "league"))

import ratings as R  # noqa: E402
from matchmake import (  # noqa: E402
    MAPS_ROOT,
    assign_positions,
    maps_for_players,
    new_model,
    read_log,
)
from play import play_match  # noqa: E402
from pool import (  # noqa: E402
    WORKBASE,
    all_commits,
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
# The schedule is the placement champion: 10p census, 6p refine,
# seven duels (30 slots). A commit cannot play more than one schedule.
DUELS = 7
FFA_SIZES = (10, 6)
TURNS = 1000
TURNTIME = 1000
LOADTIME = 3000
SEED = 0
SIGMA_WEIGHT = 0.02

# One tag for one schedule. PROGRESS.jsonl is append-only; rows with
# an older tag stay in the file and are ignored for the champion.
# score=mu ports the placement finding: the recorded score ranks
# truer without the sigma discount. sel=place43 is the placement
# champion opponent logic, ported exactly (quantile census, mass
# quota strata over the recency window, 40-nearest info duels).
BUDGET = f"duels={DUELS},ffa={'+'.join(map(str, FFA_SIZES))},turns=1000,score=mu,sel=place43,ord=10-6-2"


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
    """Games already played by a candidate: duels (2p) and FFA per size."""
    out: dict[str, Any] = {"duels": 0, "ffa": {}}
    for r in records:
        if bid not in r["field"]:
            continue
        n = len(r["field"])
        if n == 2:
            out["duels"] += 1
        else:
            out["ffa"][n] = out["ffa"].get(n, 0) + 1
    return out


def planned(
    records: list[dict], bid: str, duels: int, ffa_sizes: list[int]
) -> tuple[int, list[int]]:
    """Budget left: duels remaining and sizes without a game yet."""
    done = counts(records, bid)
    return (
        max(0, duels - done["duels"]),
        [n for n in ffa_sizes if done["ffa"].get(n, 0) < 1],
    )


def census_opponents(
    bid: str,
    cands: list[str],
    ratings: dict,
    k: int,
    arrival: dict[str, int],
) -> list[str]:
    """Rulers spanning full-pool mass: quantile-decile sites snapped
    to the nearest ruler. Exact port of the champion census opener.
    Ties break by arrival rank, then id."""
    others = [c for c in cands if c != bid]
    mus = sorted(R.for_id(ratings, c)["mu"] for c in others)
    k = max(0, min(k, len(others)))
    sites = (
        [mus[min(int(len(mus) * (j + 1) / (k + 1)), len(mus) - 1)] for j in range(k)]
        if mus and k
        else []
    )
    picked: list[str] = []
    used = {bid}
    for t in sites:
        live = [c for c in others if c not in used]
        if not live:
            break
        i = min(
            live,
            key=lambda c: (
                abs(R.for_id(ratings, c)["mu"] - t),
                R.for_id(ratings, c)["sigma"],
                arrival.get(c, len(arrival)),
                c,
            ),
        )
        used.add(i)
        picked.append(i)
    return picked


def recency_order(cands: list[str], commits: list[str]) -> list[str]:
    """Pool oldest first by commit order. Unknown shas count as now:
    an uncommitted bot is a recent arrival."""
    rank = {sha: i for i, sha in enumerate(commits)}
    now = len(commits)
    return sorted(cands, key=lambda c: (rank.get(parse_id(c)[1], now), c))


def strata_opponents(bid: str, ordered: list[str], ratings: dict, k: int) -> list[str]:
    """Bot-centered below/peer/above rulers by mass quota from the
    low-sigma tertile of the last 400. Exact port of the refine."""
    me = R.for_id(ratings, bid)
    window = [c for c in ordered[-400:] if c != bid]
    sigmas = sorted(R.for_id(ratings, c)["sigma"] for c in window)
    if not sigmas:
        return []
    cutoff = sigmas[len(sigmas) // 3]
    pool = [c for c in window if R.for_id(ratings, c)["sigma"] <= cutoff]
    if len(pool) < k:
        pool = [c for c in ordered if c != bid]
    pos = {c: i for i, c in enumerate(ordered)}
    k = max(0, min(k, len(pool)))
    s = max(me["sigma"], 0.5)
    bins: list[list[str]] = [[], [], []]
    for c in pool:
        d = R.for_id(ratings, c)["mu"] - me["mu"]
        bins[0 if d < -s else (2 if d > s else 1)].append(c)
    masses = [len(b) for b in bins]
    total = sum(masses) or 1
    quota = [max(1 if m else 0, round(k * m / total)) for m in masses]
    while sum(quota) > k:
        j = max(range(3), key=lambda j: quota[j] - k * masses[j] / total)
        quota[j] -= 1
    while sum(quota) < k:
        j = max(range(3), key=lambda j: k * masses[j] / total - quota[j])
        quota[j] += 1
    out: list[str] = []
    for b, q in zip(bins, quota, strict=True):
        near = sorted(
            b,
            key=lambda c: (
                abs(R.for_id(ratings, c)["mu"] - me["mu"]),
                R.for_id(ratings, c)["sigma"],
                (pos.get(c, len(pos)), c),
            ),
        )
        out += near[: max(q, 0)]
    if len(out) < k:
        rest = sorted(
            (c for c in pool if c not in set(out)),
            key=lambda c: (
                abs(R.for_id(ratings, c)["mu"] - me["mu"]),
                R.for_id(ratings, c)["sigma"],
                (pos.get(c, len(pos)), c),
            ),
        )
        out += rest[: k - len(out)]
    return out[:k]


def info_duel_opponent(
    model,
    bid: str,
    cands: list[str],
    ratings: dict,
    arrival: dict[str, int],
) -> str | None:
    """Best draw odds + 0.02 sigma over the 40 nearest rulers.
    Exact port of the champion tail duel. Ties break by arrival
    rank, then id; first wins remaining ties."""
    me = R.for_id(ratings, bid)
    order = sorted(
        (c for c in cands if c != bid),
        key=lambda c: (
            abs(R.for_id(ratings, c)["mu"] - me["mu"]),
            R.for_id(ratings, c)["sigma"],
            arrival.get(c, len(arrival)),
            c,
        ),
    )[:40]
    best = None
    best_v = None
    for c in order:
        e = R.for_id(ratings, c)
        teams = [
            [model.rating(mu=me["mu"], sigma=me["sigma"])],
            [model.rating(mu=e["mu"], sigma=e["sigma"])],
        ]
        v = model.predict_draw(teams) + SIGMA_WEIGHT * (me["sigma"] + e["sigma"])
        if best_v is None or v > best_v:
            best, best_v = c, v
    return best


def stage_field(
    model,
    bid: str,
    cands: list[str],
    ordered: list[str],
    ratings: dict,
    n: int,
    arrival: dict[str, int],
) -> list[str]:
    """Full FFA field: bid first, then champion opponents (9 census
    rulers for 10p, 5 strata rulers for 6p)."""
    if n == 10:
        return [bid] + census_opponents(bid, cands, ratings, 9, arrival)
    if n == 6:
        return [bid] + strata_opponents(bid, ordered, ratings, 5)
    raise ValueError(f"no champion stage for {n}p")


def pick_maps(rng: random.Random, candidates: list[str], k: int) -> list[str]:
    """k distinct maps, shuffled. Fewer only if the pool is smaller."""
    pool = list(candidates)
    rng.shuffle(pool)
    return pool[:k]


def score(ratings: dict, bid: str) -> tuple[float, float, float]:
    """The objective: mu, the estimated skill. The exam already prices
    uncertainty into the measurement, so no sigma discount."""
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
    """Copy-paste line for the worklog: the duel record and the rank
    of each FFA game for one candidate."""
    wins = losses = 0
    ranks = []
    for r in records:
        if bid not in r["field"]:
            continue
        rank = r["result"].index(bid) + 1
        if len(r["field"]) == 2:
            if rank == 1:
                wins += 1
            else:
                losses += 1
        else:
            ranks.append((len(r["field"]), rank))
    ranks.sort()
    ffa = " ".join(f"{n}p:{rank}" for n, rank in ranks)
    return f"games: {wins}-{losses}, FFA ranks {ffa}"


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
    ffa_sizes = list(FFA_SIZES)
    records = read_log(GAMES_LOG)
    ratings = R.rebuild(records)
    R.save(RATINGS_PATH, ratings)
    done = counts(records, bid)
    print(f"candidate {bid}", flush=True)

    duels_left, sizes_left = planned(records, bid, DUELS, ffa_sizes)

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
    rng = random.Random(f"{SEED}:{bid}:{done['duels']}:{sum(done['ffa'].values())}")
    model = new_model()
    ordered = recency_order([c for c in pool if c != bid], all_commits(root))
    arrival = {c: i for i, c in enumerate(ordered)}
    used = {r["map"] for r in records if bid in r["field"]}

    with open(GAMES_LOG, "a") as fh:
        for n in sizes_left:
            maps = [f"tools/maps/{m}" for m in maps_for_players(MAPS_ROOT, n)]
            maps = [m for m in maps if m not in used]
            if not maps:
                raise ValueError(f"no unused {n}p map")
            map_rel = rng.choice(maps)
            used.add(map_rel)
            field = stage_field(
                model, bid, pool_ids(root, ratings), ordered, ratings, n, arrival
            )
            if len(field) != n:
                raise ValueError(f"pool too small: wanted {n}, got {len(field)}")
            field = assign_positions(field, rng)
            done["ffa"][n] = done["ffa"].get(n, 0) + 1
            log_dir = runs / sha / f"ffa_{n:02d}"
            rec = play_one(root, field, map_rel, log_dir, rng, args.workbase)
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            ratings = R.update(ratings, rec["field"], rec["result"])
            R.save(RATINGS_PATH, ratings)
            rank = rec["result"].index(bid) + 1
            mu, sigma, sc = score(ratings, bid)
            print(
                f"ffa {n}p {Path(map_rel).name} {result_line(rec, bid)} "
                f"-> rank {rank}/{n}  cand mu {mu:.1f} sigma {sigma:.2f} score {sc:.1f}",
                flush=True,
            )

        if duels_left:
            maps = [f"tools/maps/{m}" for m in maps_for_players(MAPS_ROOT, 2)]
            maps = [m for m in maps if m not in used]
            if len(maps) < duels_left:
                raise ValueError(f"only {len(maps)} unused 2p maps")
            for map_rel in pick_maps(rng, maps, duels_left):
                used.add(map_rel)
                cands = [c for c in pool_ids(root, ratings) if c != bid]
                opp = info_duel_opponent(model, bid, cands, ratings, arrival)
                if opp is None:
                    raise ValueError("pool too small: no duel opponent")
                field = [bid, opp] if rng.random() < 0.5 else [opp, bid]
                done["duels"] += 1
                log_dir = runs / sha / f"duel_{done['duels']:02d}"
                rec = play_one(root, field, map_rel, log_dir, rng, args.workbase)
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                ratings = R.update(ratings, rec["field"], rec["result"])
                R.save(RATINGS_PATH, ratings)
                rank = rec["result"].index(bid) + 1
                outcome = "WIN" if rank == 1 else "LOSS"
                mu, sigma, sc = score(ratings, bid)
                print(
                    f"duel {done['duels']}/{DUELS} "
                    f"{Path(map_rel).name} {result_line(rec, bid)} -> {outcome}"
                    f"  cand mu {mu:.1f} sigma {sigma:.2f} score {sc:.1f}",
                    flush=True,
                )

    mu, sigma, sc = score(ratings, bid)
    games = done["duels"] + sum(done["ffa"].values())
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
