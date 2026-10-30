"""Random mixed-generator maps: pick cavemap/walk/symmetric, roll valid args.

Contract per map: players N (2-4, default random), 1 hill per player,
tiles x*y within 25% of 250*N, aspect x/y in [0.5, 2]. Emits the map
on stdout, review row on stderr. Fails loud after 50 attempts.

Each generator's validity rule (empirical, see MAPGEN*.md):
- symmetric: rows AND cols divisible by N (translation symmetry).
- cavemap: rotational symmetry supports 2/4 players only;
  translational supports any N but needs dims divisible by N.
- walk: no exact dims (square bands only) and tile symmetry forces
  coarse tilings; small end unlocks with block size 1-2. The sampler
  sets bands around the budget and the retry harness validates output.

Usage: gen_mixed.py [--players 2|3|4] [--seed S] [--generator NAME]
"""
import argparse
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
MAPGEN = REPO / "tools" / "mapgen"
AMSTAN = MAPGEN / "amstan"

GENS = ("cavemap", "walk", "symmetric")
TOL = 0.25  # tile budget tolerance around 250*N
TRIES = 50


def pick_dims(n, rng, snap=1):
    """Draw (rows, cols) in budget and aspect range.

    snap: round dims to multiples of snap (symmetry divisibility).
    Returns ints; budget re-checked by the caller after snapping.
    """
    target = 250 * n
    for _ in range(100):
        aspect = rng.uniform(0.5, 2.0)  # cols/rows
        rows = max(8, round((target / aspect) ** 0.5))
        cols = max(8, round(rows * aspect))
        if snap > 1:
            rows = max(snap, round(rows / snap) * snap)
            cols = max(snap, round(cols / snap) * snap)
        tiles = rows * cols
        if abs(tiles - target) <= TOL * target and 0.5 <= cols / rows <= 2.0:
            return rows, cols
    # Fallback: nearest snapped grid to target at aspect 1.
    side = max(snap, round((target ** 0.5) / snap) * snap)
    return side, side


def sample_symmetric(n, rng):
    rows, cols = pick_dims(n, rng, snap=n)
    lo = 5
    hi = max(lo + 1, min(rows, cols) // 2)
    return [sys.executable, str(MAPGEN / "symmetric_mapgen.py"),
            "--players", str(n), "--rows", str(rows), "--cols", str(cols),
            "--min_start_distance", str(rng.randint(lo, hi)),
            "--seed", str(rng.randrange(1 << 30))], None


def sample_cavemap(n, rng):
    rows, cols = pick_dims(n, rng, snap=n)
    if n in (2, 4) and rng.random() < 0.5:
        sym = "rotational"
    else:
        sym = "translational"
    return [sys.executable, "mapgen.py",
            "--players", str(n), "--rows", str(rows), "--cols", str(cols),
            "--hills", "1", "--symmetry", sym,
            "--seed", str(rng.randrange(1 << 30))], AMSTAN


def sample_walk(n, rng):
    side = round((250 * n) ** 0.5)
    lo = max(10, side - 6)
    hi = side + 10
    args = [sys.executable, str(MAPGEN / "mapgen.py"),
            "--no_players", str(n),
            "--min_dimensions", str(lo), "--max_dimensions", str(hi),
            "--min_hills", "1", "--max_hills", "1",
            "--min_starting_distance", str(rng.randint(5, 12)),
            "--min_block_size", "1", "--max_block_size", "2",
            "--seed", str(rng.randrange(1 << 30))]
    if n in (2, 4) and rng.random() < 0.5:
        args += ["--symmetry", "rotational", "--rotational_symmetry", str(n)]
    return args, None


SAMPLERS = {"symmetric": sample_symmetric, "cavemap": sample_cavemap,
            "walk": sample_walk}


def validate(text, n):
    """Structural check: parseable, N players, N hills, budget, aspect."""
    lines = text.splitlines()
    try:
        rows = int(next(l for l in lines if l.startswith("rows")).split()[1])
        cols = int(next(l for l in lines if l.startswith("cols")).split()[1])
        players = int(next(l for l in lines if l.startswith("players")).split()[1])
    except (StopIteration, ValueError, IndexError):
        return False, "unparseable header"
    if players != n:
        return False, f"players {players} != {n}"
    hills = sum(l.count(str(d)) for l in lines if l.startswith("m ")
                for d in range(10))
    if hills != n:
        return False, f"hills {hills} != {n}"
    tiles = rows * cols
    if abs(tiles - 250 * n) > TOL * 250 * n:
        return False, f"tiles {tiles} outside budget"
    if not 0.5 <= cols / rows <= 2.0:
        return False, f"aspect {cols / rows:.2f} out of range"
    return True, "ok"


def generate_one(gen, n, rng):
    """Sample args for one generator until output validates (fail loud)."""
    sampler = SAMPLERS[gen]
    last = "no attempts"
    for _ in range(TRIES):
        argv, cwd = sampler(n, rng)
        try:
            proc = subprocess.run(argv, cwd=cwd, capture_output=True,
                                  text=True, timeout=120)
        except subprocess.TimeoutExpired:
            last = "timeout"
            continue
        if proc.returncode != 0:
            last = (proc.stderr.strip().splitlines() or ["exit 1"])[-1][:100]
            continue
        ok, reason = validate(proc.stdout, n)
        if ok:
            return proc.stdout
        last = reason
    raise RuntimeError(f"{gen} 2p arguments failed after {TRIES}: {last}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--players", type=int, choices=(2, 3, 4), default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--generator", choices=GENS, default=None)
    args = p.parse_args(argv)
    rng = random.Random(args.seed)
    n = args.players or rng.choice([2, 3, 4])
    gen = args.generator or rng.choice(GENS)
    text = generate_one(gen, n, rng)
    sys.stdout.write(text)
    rows = next(l for l in text.splitlines() if l.startswith("rows"))
    cols = next(l for l in text.splitlines() if l.startswith("cols"))
    print(f"{gen} {rows} {cols} players {n} hills 1", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
