"""Smart matchmaking: random maps, most-informative fields.

Information = close skill (high predict_draw) + high uncertainty (sigma).
Usage: python league/matchmake.py [--n ...] [--play M] [--turns T]
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

from pool import ROOT, DirtyTree, is_clean, pool as pool_ids
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


def info_score(model: BradleyTerryFull, combo: list[str],
               ratings: dict) -> float:
    teams, sig = [], 0.0
    for bid in combo:
        e = R.for_id(ratings, bid)
        teams.append([model.rating(mu=e["mu"], sigma=e["sigma"])])
        sig += e["sigma"]
    try:
        draw = model.predict_draw(teams)
    except Exception:
        draw = 0.2
    return draw + 0.02 * sig


def propose(model: BradleyTerryFull, candidates: list[str], ratings: dict,
            n: int, rng: random.Random) -> list[str]:
    cands = sorted(candidates,
                   key=lambda k: (-R.for_id(ratings, k)["sigma"], rng.random()))
    field = [cands[0]]
    rest = [c for c in cands if c != field[0]]
    while len(field) < n and rest:
        scored = sorted(rest, key=lambda k: -info_score(model, field + [k],
                                                        ratings))
        pick = (scored[0] if rng.random() < 0.8
                else rng.choice(scored[:min(3, len(scored))]))
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
    ap.add_argument("--turns", type=int, default=100)
    ap.add_argument("--players", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--games", default=str(GAMES_LOG))
    ap.add_argument("--ratings", default=str(RATINGS_PATH))
    args = ap.parse_args(argv)
    model = new_model()
    ratings = R.load(args.ratings)
    cands = pool_ids(ROOT, ratings)
    print(f"pool: {len(cands)} bots", flush=True)
    rng = random.Random(args.seed)
    if not args.play:
        n, m = pick_map(rng, MAPS_ROOT, args.players)
        field = assign_positions(propose(model, cands, ratings, n, rng), rng)
        print(f"proposed {n}p on {m}: {' '.join(field)}", flush=True)
        return 0
    import sys as _sys
    if not is_clean(ROOT):
        print("bots/ is dirty; commit or stash before logged play",
              file=_sys.stderr)
        return 2
    last: tuple | None = None
    for i in range(args.play):
        n, m = pick_map(rng, MAPS_ROOT, args.players)
        field = propose(model, cands, ratings, n, rng)
        if tuple(sorted(field)) == last:
            field = propose(model, cands, ratings, n, rng)
        last = tuple(sorted(field))
        field = assign_positions(field, rng)
        pseed, eseed = rng.randrange(10 ** 9), rng.randrange(10 ** 9)
        rec = play_match(ROOT, _sys.executable, field,
                         f"tools/maps/{m}", args.turns, 1000, 3000,
                         pseed, eseed, Path(args.games).parent / "replays")
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
