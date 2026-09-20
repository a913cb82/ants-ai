"""Smart matchmaking: random maps, most-informative fields.

Information = close skill (high predict_draw) + high uncertainty (sigma).
Usage: python league/matchmake.py [--players N] [--play M]
  (proposal only by default; --play runs games and logs them)
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

from openskill.models import BradleyTerryFull

from pool import (ROOT, WORKBASE, is_clean, pool as pool_ids,
                  prune_worktrees)
from play import play_match
import ratings as R

MAPS_ROOT = ROOT / "tools" / "maps"
GAMES_LOG = ROOT / "league" / "games.jsonl"
RATINGS_PATH = ROOT / "league" / "ratings.json"


def new_model() -> BradleyTerryFull:
    return BradleyTerryFull()


def players_of(path: Path) -> int | None:
    with open(path) as fh:
        for i, line in enumerate(fh):
            if i > 60:
                break
            m = re.match(r"^players\s+(\d+)\s*$", line)
            if m:
                return int(m.group(1))
    return None


def maps_for_players(maps_root: str | Path, n: int) -> list[Path]:
    """Map paths (relative to maps_root) supporting exactly n players."""
    maps_root = Path(maps_root)
    return sorted(p.relative_to(maps_root)
                  for p in maps_root.rglob("*.map")
                  if players_of(p) == n)


def available_counts(maps_root: str | Path) -> list[int]:
    counts = set()
    for p in Path(maps_root).rglob("*.map"):
        n = players_of(p)
        if n is not None:
            counts.add(n)
    return sorted(counts)


def pick_map(rng: random.Random, maps_root: str | Path,
             n: int | None = None) -> tuple[int, Path]:
    n = n if n is not None else rng.choice(available_counts(maps_root))
    return n, rng.choice(maps_for_players(maps_root, n))


def info_score(model: BradleyTerryFull, combo: list[str], ratings: dict,
               sigma_weight: float = 0.02) -> float:
    teams, sig = [], 0.0
    for bid in combo:
        e = R.for_id(ratings, bid)
        teams.append([model.rating(mu=e["mu"], sigma=e["sigma"])])
        sig += e["sigma"]
    return model.predict_draw(teams) + sigma_weight * sig


def propose(model: BradleyTerryFull, candidates: list[str], ratings: dict,
            n: int, rng: random.Random, eps: float = 0.2,
            breadth: int = 3) -> list[str]:
    cands = sorted(candidates,
                   key=lambda k: (-R.for_id(ratings, k)["sigma"], rng.random()))
    field = [cands[0]]
    rest = [c for c in cands if c != field[0]]
    while len(field) < n and rest:
        scored = sorted(rest, key=lambda k: -info_score(model, field + [k],
                                                        ratings))
        pick = (rng.choice(scored[:min(breadth, len(scored))])
                if rng.random() < eps else scored[0])
        field.append(pick)
        rest = [c for c in rest if c != pick]
    return field


def assign_positions(field: list[str], rng: random.Random) -> list[str]:
    return rng.sample(field, len(field))


def read_log(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--play", type=int, default=0)
    ap.add_argument("--turns", type=int, default=1000)
    ap.add_argument("--turntime", type=int, default=1000)
    ap.add_argument("--loadtime", type=int, default=3000)
    ap.add_argument("--players", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--games", default=str(GAMES_LOG))
    ap.add_argument("--ratings", default=str(RATINGS_PATH))
    ap.add_argument("--log-dir", default=str(ROOT / "league" / "replays"))
    ap.add_argument("--epsilon", type=float, default=0.2)
    ap.add_argument("--breadth", type=int, default=3)
    ap.add_argument("--sigma-weight", type=float, default=0.02)
    ap.add_argument("--workbase", default=str(WORKBASE))
    ap.add_argument("--max-worktree-gb", type=float, default=1.0)
    args = ap.parse_args(argv)
    model = new_model()
    ratings = R.load(args.ratings)
    cands = pool_ids(ROOT, ratings)
    print(f"pool: {len(cands)} bots", flush=True)
    rng = random.Random(args.seed)
    if not args.play:
        n, m = pick_map(rng, MAPS_ROOT, args.players)
        field = assign_positions(
            propose(model, cands, ratings, n, rng,
                    eps=args.epsilon, breadth=args.breadth), rng)
        print(f"proposed {n}p on {m}: {' '.join(field)}", flush=True)
        return 0
    if not is_clean(ROOT):
        print("bot tree is dirty; commit or stash before logged play",
              file=sys.stderr)
        return 2
    prune_worktrees(args.workbase, int(args.max_worktree_gb * 1_000_000_000))
    for i in range(args.play):
        n, m = pick_map(rng, MAPS_ROOT, args.players)
        field = assign_positions(
            propose(model, cands, ratings, n, rng,
                    eps=args.epsilon, breadth=args.breadth), rng)
        pseed, eseed = rng.randrange(10 ** 9), rng.randrange(10 ** 9)
        rec = play_match(ROOT, sys.executable, field,
                         f"tools/maps/{m}", args.turns, args.turntime,
                         args.loadtime, pseed, eseed, args.log_dir,
                         workbase=args.workbase)
        ratings = R.update(ratings, rec["field"], rec["result"])
        R.save(args.ratings, ratings)
        with open(args.games, "a") as fh:
            fh.write(json.dumps(rec) + "\n")
        order = sorted(range(len(rec["field"])),
                       key=lambda s: rec["result"].index(rec["field"][s]))
        print(f"game {i + 1}: " + " ".join(rec["field"][s] for s in order),
              flush=True)
    print("ratings saved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
