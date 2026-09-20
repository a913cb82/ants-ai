"""One autoresearch iteration: play the fixed duel + FFA budget, score it.

Every game enters league/games.jsonl; ratings rebuild from that log.
The budget is per candidate commit, and a fresh commit is a fresh bot
id, so a candidate can never be ground past its budget: a second run
finds nothing left to play and only prints the score.

Usage:
  python autoresearch/iteration.py --bot autoresearch/bot/main.bot
  python autoresearch/iteration.py --bot autoresearch/bot/main.bot --dry-run
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "league"))

import ratings as R  # noqa: E402
from matchmake import (MAPS_ROOT, assign_positions, info_score,  # noqa: E402
                       maps_for_players, new_model, propose, read_log)
from play import play_match  # noqa: E402
from pool import (WORKBASE, bot_id, is_clean, parse_id, pool as pool_ids,  # noqa: E402
                  prune_replays, prune_worktrees, short)

GAMES_LOG = ROOT / "league" / "games.jsonl"
RATINGS_PATH = ROOT / "league" / "ratings.json"
RUNS = ROOT / "autoresearch" / "runs"
DEFAULT_BOT = "autoresearch/bot/main.bot"


def candidate_id(root: str | Path, botfile: str, rev: str) -> str:
    """The bot id a manifest would have at a revision."""
    root = Path(root)
    p = Path(botfile)
    if not p.is_absolute():
        p = root / p
    return bot_id(p.resolve().relative_to(root.resolve()).as_posix(),
                  short(root, rev))


def counts(records: list[dict], bid: str) -> dict:
    """Games already played by a candidate: duels (2p) and FFA per size."""
    out = {"duels": 0, "ffa": {}}
    for r in records:
        if bid not in r["field"]:
            continue
        n = len(r["field"])
        if n == 2:
            out["duels"] += 1
        else:
            out["ffa"][n] = out["ffa"].get(n, 0) + 1
    return out


def planned(records: list[dict], bid: str, duels: int,
            ffa_sizes: list[int]) -> tuple[int, list[int]]:
    """Budget left: duels remaining and sizes without a game yet."""
    done = counts(records, bid)
    return (max(0, duels - done["duels"]),
            [n for n in ffa_sizes if done["ffa"].get(n, 0) < 1])


def duel_opponent(model, bid: str, cands: list[str], ratings: dict,
                  rng: random.Random, eps: float,
                  breadth: int) -> str:
    """Opponent with the best information score, epsilon-random among
    the top breadth."""
    scored = sorted(cands, key=lambda k: -info_score(model, [bid, k], ratings))
    top = scored[:max(1, min(breadth, len(scored)))]
    return rng.choice(top) if rng.random() < eps else top[0]


def pick_maps(rng: random.Random, candidates: list[str], k: int) -> list[str]:
    """k distinct maps, shuffled. Fewer only if the pool is smaller."""
    pool = list(candidates)
    rng.shuffle(pool)
    return pool[:k]


def score(ratings: dict, bid: str) -> tuple[float, float, float]:
    """The objective: mu - 3 sigma, the conservative ordinal."""
    e = R.for_id(ratings, bid)
    return e["mu"], e["sigma"], e["mu"] - 3 * e["sigma"]


def result_line(rec: dict) -> str:
    return " > ".join(Path(b.rsplit("-", 1)[0]).name for b in rec["result"])


def play_one(root: Path, field: list[str], map_rel: str, args,
             log_dir: Path, rng: random.Random) -> dict:
    rec = play_match(root, sys.executable, field, map_rel,
                     args.turns, args.turntime, args.loadtime,
                     rng.randrange(10 ** 9), rng.randrange(10 ** 9),
                     log_dir, timeout=args.timeout, workbase=args.workbase)
    rec["replay"] = (log_dir.relative_to(root) / "0.replay").as_posix()
    return rec


def split_ints(s: str) -> list[int]:
    return [int(x) for x in s.split(",")]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot", default=DEFAULT_BOT)
    ap.add_argument("--rev", default="HEAD")
    ap.add_argument("--duels", type=int, default=16)
    ap.add_argument("--ffa-sizes", type=split_ints, default=[4, 5, 6, 7, 8, 9, 10])
    ap.add_argument("--turns", type=int, default=1000)
    ap.add_argument("--turntime", type=int, default=1000)
    ap.add_argument("--loadtime", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--games", default=str(GAMES_LOG))
    ap.add_argument("--ratings", default=str(RATINGS_PATH))
    ap.add_argument("--runs", default=str(RUNS))
    ap.add_argument("--epsilon", type=float, default=0.2)
    ap.add_argument("--breadth", type=int, default=3)
    ap.add_argument("--sigma-weight", type=float, default=0.02)
    ap.add_argument("--workbase", default=str(WORKBASE))
    ap.add_argument("--max-worktree-gb", type=float, default=1.0)
    ap.add_argument("--max-replay-gb", type=float, default=0.5)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    root = ROOT
    if not is_clean(root):
        print("bot tree is dirty; commit before logged play", file=sys.stderr)
        return 2
    bid = candidate_id(root, args.bot, args.rev)
    records = read_log(args.games)
    done = counts(records, bid)
    ratings = R.load(args.ratings)
    mu, sigma, lb = score(ratings, bid)
    print(f"candidate {bid}", flush=True)
    print("duels %d/%d  ffa %s" % (
        done["duels"], args.duels,
        " ".join(f"{n}p {min(done['ffa'].get(n, 0), 1)}/1"
                 for n in args.ffa_sizes)), flush=True)
    print(f"mu {mu:.1f}  sigma {sigma:.2f}  lb {lb:.1f}", flush=True)

    duels_left, sizes_left = planned(records, bid, args.duels, args.ffa_sizes)
    if args.dry_run:
        print(f"planned: {duels_left} duels, ffa {sizes_left}", flush=True)
        return 0

    if bid not in set(pool_ids(root, ratings)):
        print(f"{bid} duplicates a rated bot; make a real change",
              file=sys.stderr)
        return 1

    runs = Path(args.runs)
    sha = parse_id(bid)[1]
    prune_worktrees(args.workbase, int(args.max_worktree_gb * 1e9))
    prune_replays(runs, int(args.max_replay_gb * 1e9),
                  protect={str(runs / sha)})
    rng = random.Random(f"{args.seed}:{bid}:{done['duels']}:"
                        f"{sum(done['ffa'].values())}")
    model = new_model()
    used = {r["map"] for r in records if bid in r["field"]}

    with open(args.games, "a") as fh:
        if duels_left:
            maps = [f"tools/maps/{m}" for m in maps_for_players(MAPS_ROOT, 2)]
            maps = [m for m in maps if m not in used]
            if len(maps) < duels_left:
                raise ValueError(f"only {len(maps)} unused 2p maps")
            for map_rel in pick_maps(rng, maps, duels_left):
                cands = [c for c in pool_ids(root, ratings) if c != bid]
                opp = duel_opponent(model, bid, cands, ratings, rng,
                                    args.epsilon, args.breadth)
                field = [bid, opp] if rng.random() < 0.5 else [opp, bid]
                done["duels"] += 1
                log_dir = runs / sha / f"duel_{done['duels']:02d}"
                rec = play_one(root, field, map_rel, args, log_dir, rng)
                ratings = R.update(ratings, rec["field"], rec["result"])
                R.save(args.ratings, ratings)
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                print(f"duel {done['duels']}/{args.duels} "
                      f"{Path(map_rel).name} {result_line(rec)}", flush=True)

        for n in sizes_left:
            maps = [f"tools/maps/{m}" for m in maps_for_players(MAPS_ROOT, n)]
            maps = [m for m in maps if m not in used]
            if not maps:
                raise ValueError(f"no unused {n}p map")
            map_rel = rng.choice(maps)
            field = propose(model, pool_ids(root, ratings), ratings, n,
                            rng, eps=args.epsilon, breadth=args.breadth,
                            seed_bot=bid)
            if len(field) != n:
                raise ValueError(f"pool too small: wanted {n}, got {len(field)}")
            field = assign_positions(field, rng)
            done["ffa"][n] = done["ffa"].get(n, 0) + 1
            log_dir = runs / sha / f"ffa_{n:02d}"
            rec = play_one(root, field, map_rel, args, log_dir, rng)
            ratings = R.update(ratings, rec["field"], rec["result"])
            R.save(args.ratings, ratings)
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            print(f"ffa {n}p {Path(map_rel).name} {result_line(rec)}",
                  flush=True)

    mu, sigma, lb = score(ratings, bid)
    print(f"mu {mu:.1f}  sigma {sigma:.2f}  lb {lb:.1f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
