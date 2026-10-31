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
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
MAPGEN = HERE.parent
AMSTAN = MAPGEN / "amstan"

GENS = ("cavemap", "walk", "symmetric")
TOL = 0.25  # tile budget tolerance around 250*N
TRIES = 50

_GENMODS = {}


def _load_genmods():
    """Import generator modules in-process (once, before any fork).

    Top modules load under unique keys; the amstan chain takes the plain
    dependency keys its absolute imports expect ('map' is amstan's here -
    nothing else in this process wants it). Plain keys are snapshotted
    before loading and restored after: the import statements only need
    them at exec time (later calls use already-bound references), so a
    host process (e.g. pytest) never sees the shadowing. Without this,
    tools/mapgen/random_map's `from map import` resolves to amstan's Map
    in the same session. Call before creating any
    fork-based pool so workers inherit the loaded modules.
    """
    if _GENMODS:
        return
    import importlib.util
    plain = ("util", "terrain", "map", "symmetricmap", "cavemap")
    saved = {k: sys.modules[k] for k in plain if k in sys.modules}

    def load(key, path):
        spec = importlib.util.spec_from_file_location(key, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        spec.loader.exec_module(mod)
        return mod

    _GENMODS["walk"] = load("walk_mapgen", str(MAPGEN / "mapgen.py"))
    _GENMODS["symmetric"] = load("symmetric_mapgen",
                                   str(MAPGEN / "symmetric_mapgen.py"))
    for key, name in (("util", "util.py"), ("terrain", "terrain.py"),
                      ("map", "map.py"),
                      ("symmetricmap", "symmetricmap.py"),
                      ("cavemap", "cavemap.py")):
        load(key, str(AMSTAN / name))
    _GENMODS["cavemap"] = load("amstan_mapgen", str(AMSTAN / "mapgen.py"))
    for k in plain:
        if k in saved:
            sys.modules[k] = saved[k]
        else:
            sys.modules.pop(k, None)


def _run_in_process(gen, argv, cwd=None):
    """Run the generator's main() in-process: (returncode, stdout, stderr).

    Same code, same seed, same random-call order as the old subprocess
    path, so output is byte-identical (pinned by
    test_inprocess_matches_subprocess). argv mirrors the old invocation
    ([python, script, *flags]); mains read flags via patched sys.argv.
    Never raises: crashes and SystemExit become (1, "", reason).
    No timeout: every loop in these scripts is iteration-bounded. cwd is
    accepted and ignored (in-process execution has no working directory;
    kept so callers mirror the old subprocess invocation).
    """
    _load_genmods()
    import io
    from contextlib import redirect_stderr, redirect_stdout
    mod = _GENMODS[gen]
    out, err = io.StringIO(), io.StringIO()
    old_argv = sys.argv
    sys.argv = [Path(argv[1]).name, *argv[2:]]
    try:
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = mod.main(None)
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 1
            if rc is None:
                rc = 0
    except Exception as e:  # noqa: BLE001 - crash becomes a reason
        err.write(f"{type(e).__name__}: {e}")
        rc = 1
    finally:
        sys.argv = old_argv
    return rc, out.getvalue(), err.getvalue()


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
    # No exact dims (square bands only) and tile symmetry forces coarse
    # tilings; small end unlocks with block size 1-2. The sampler sets
    # bands around the budget and the retry harness validates output.
    # min_starting_distance is d2 units: 25-64 means d 5-8.
    side = round((250 * n) ** 0.5)
    lo = max(10, side - 6)
    hi = side + 10
    args = [sys.executable, str(MAPGEN / "mapgen.py"),
            "--no_players", str(n),
            "--min_dimensions", str(lo), "--max_dimensions", str(hi),
            "--min_hills", "1", "--max_hills", "1",
            "--min_starting_distance", str(rng.randint(25, 64)),
            "--min_block_size", "1", "--max_block_size", "2",
            "--seed", str(rng.randrange(1 << 30))]
    if n in (2, 4) and rng.random() < 0.5:
        args += ["--symmetry", "rotational", "--rotational_symmetry", str(n)]
    return args, None


SAMPLERS = {"symmetric": sample_symmetric, "cavemap": sample_cavemap,
            "walk": sample_walk}


def validate(text, n, min_hill_dist=4.0):
    """Structural check: parseable, N players, N hills, budget, aspect.

    min_hill_dist: minimum pairwise toroidal hill distance. Kills
    corner-touching degeneracy (e.g. rotational twins landing one
    diagonal step apart through the wrap); default 4.0 passes every
    healthy demo map (floor 5.0) and rejects the 1.4 case.
    """
    lines = text.splitlines()
    try:
        rows = int(next(l for l in lines if l.startswith("rows")).split()[1])
        cols = int(next(l for l in lines if l.startswith("cols")).split()[1])
        players = int(next(l for l in lines if l.startswith("players")).split()[1])
    except (StopIteration, ValueError, IndexError):
        return False, "unparseable header"
    if players != n:
        return False, f"players {players} != {n}"
    hills = [(r, c) for r, row in enumerate(
        [l[2:] for l in lines if l.startswith("m ")])
        for c, ch in enumerate(row) if ch.isdigit()]
    if len(hills) != n:
        return False, f"hills {len(hills)} != {n}"
    import math
    for i in range(len(hills)):
        for j in range(i + 1, len(hills)):
            dr = abs(hills[i][0] - hills[j][0]) % rows
            dc = abs(hills[i][1] - hills[j][1]) % cols
            d = math.sqrt(min(dr, rows - dr) ** 2 + min(dc, cols - dc) ** 2)
            if d < min_hill_dist:
                return False, f"hills {d:.1f} apart < {min_hill_dist}"
    tiles = rows * cols
    if abs(tiles - 250 * n) > TOL * 250 * n:
        return False, f"tiles {tiles} outside budget"
    if not 0.5 <= cols / rows <= 2.0:
        return False, f"aspect {cols / rows:.2f} out of range"
    return True, "ok"


def _generate_deterministic(gen, n, subseed, min_hill_dist=4.0):
    """Pure function of (gen, n, subseed): every draw comes from a private
    Random(subseed), so retries advance a deterministic stream and the
    same inputs always emit the same map. Parallel-safe by construction.
    Returns (map_text, argv, workdir)."""
    srng = random.Random(subseed)
    sampler = SAMPLERS[gen]
    last = "no attempts"
    for _ in range(TRIES):
        argv, cwd = sampler(n, srng)
        rc, out_text, err_text = _run_in_process(gen, argv)
        if rc != 0:
            last = (err_text.strip().splitlines() or ["exit 1"])[-1][:100]
            continue
        ok, reason = validate(out_text, n, min_hill_dist)
        if ok:
            return out_text, argv, cwd
        last = reason
    raise RuntimeError(f"{gen} {n}p arguments failed after {TRIES}: {last}")


def generate_one(gen, n, rng, min_hill_dist=4.0):
    """Sample args for one generator until output validates (fail loud).

    Returns (map_text, argv, workdir): argv mirrors the old subprocess
    invocation (with its --seed), workdir the cwd or None for repo root.
    Deterministic in rng: draws one subseed, everything else derives.
    """
    return _generate_deterministic(gen, n, rng.randrange(1 << 30),
                                   min_hill_dist)


def render(text, argv, cwd, seed_note):
    """Prepend the # metadata header (parser-safe by repo convention)."""
    script = Path(argv[1]).name
    meta = [f"# generator: {script}",
            f"# args: {' '.join(argv[2:])}"]
    if cwd is not None:
        meta.append(f"# cwd: {cwd.relative_to(REPO)}")
    meta.append(f"# gen_mixed seed: {seed_note}")
    return "\n".join(meta) + "\n" + text


def _batch_task(plan):
    """Top-level for pickling: pure function of the plan tuple.

    Returns (filename, content). Raises on exhaustion (the pool
    propagates it, so a failed batch writes nothing: all-or-nothing).
    """
    i, gen, n, subseed, min_hill_dist, note = plan
    text, argv, cwd = _generate_deterministic(gen, n, subseed,
                                              min_hill_dist)
    dims = {}
    for line in text.splitlines():
        if line.startswith("rows ") or line.startswith("cols "):
            k, v = line.split()
            dims[k] = v
    name = f"mixed_{i:03d}_{gen}_p{n}_{dims['rows']}x{dims['cols']}.map"
    return name, render(text, argv, cwd, note)


def run_batch(count, out_dir, seed, gen_pin, n_pin, min_hill_dist, jobs):
    """Generate count maps into out_dir (descriptive filenames, headers).

    Per-map (gen, n, subseed) triples are pre-drawn serially from the
    master RNG, so worker execution order cannot affect output: the same
    seed emits byte-identical batches with jobs=1 or jobs=N. Workers are
    forked processes running the generators in-process (no per-map
    interpreter startup); failures propagate and the batch writes
    nothing (all-or-nothing)."""
    rng = random.Random(seed)
    plans = []
    for _ in range(count):
        gen = gen_pin or rng.choice(GENS)
        n = n_pin or rng.choice([2, 3, 4])
        plans.append((gen, n, rng.randrange(1 << 30)))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _load_genmods()  # before any fork: workers inherit loaded modules
    plans = [(i, gen, n, sub, min_hill_dist,
              f"{seed} batch {i}/{count}")
             for i, (gen, n, sub) in enumerate(plans)]
    if jobs == 1:
        results = [_batch_task(p) for p in plans]
    else:
        import multiprocessing
        ctx = multiprocessing.get_context("fork")
        with ctx.Pool(processes=max(1, jobs)) as pool:
            results = pool.map(_batch_task, plans)
    for name, content in results:
        (out / name).write_text(content)
        print(f"wrote {name}", file=sys.stderr)
    return [name for name, _ in results]


def fresh_pool(n_train_games, n_eval_games, out_dir, seed, min_hill_dist=4.0,
             jobs=8):
    """Generate until n_train_games+n_eval_games 2p maps are collected.

    No-args draws (random type, random 2-4 players). Non-2p maps are
    written alongside and set aside for the >2p discussion, never
    returned: the 2-bot engine rejects hill digits >= num_players at
    parse time, so only 2p boards can host games today. Deterministic
    in seed; bounded (fail loud past the draw cap). Returns
    (train_paths, eval_paths) as strings, 1:1 with games.
    """
    need = n_train_games + n_eval_games
    _load_genmods()  # before any fork: workers inherit loaded modules
    rng = random.Random(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    two_p: list[str] = []
    idx = draws = 0
    use_pool = jobs != 1
    pool = None
    if use_pool:
        import multiprocessing
        pool = multiprocessing.get_context("fork").Pool(
            processes=max(1, jobs))
    try:
        while len(two_p) < need:
            if draws >= 10 * need + 64:
                raise RuntimeError(
                    f"fresh_pool: only {len(two_p)}/{need} 2p maps "
                    f"in {draws} draws (seed {seed})")
            batch = []
            for _ in range(max(8, need)):
                gen = rng.choice(GENS)
                n = rng.choice([2, 3, 4])
                batch.append((idx, gen, n, rng.randrange(1 << 30)))
                idx += 1
            draws += len(batch)
            plans = [(i, g, n, s, min_hill_dist, f"{seed} fresh draw {i}")
                     for i, g, n, s in batch]
            if pool is None:
                results = [_batch_task(p) for p in plans]
            else:
                results = pool.map(_batch_task, plans)
            for (name, content), (_, _, pn, _, _, _) in zip(results,
                                                              plans):
                (out / name).write_text(content)
                if pn == 2:
                    two_p.append(str(out / name))
    finally:
        if pool is not None:
            pool.close()
            pool.join()
    return two_p[:n_train_games], two_p[n_train_games:need]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--players", type=int, choices=(2, 3, 4), default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--generator", choices=GENS, default=None)
    p.add_argument("--min-hill-dist", type=float, default=4.0,
                     help="minimum pairwise toroidal hill distance")
    p.add_argument("--count", type=int, default=1,
                     help="maps per invocation; >1 writes files to --out-dir")
    p.add_argument("--out-dir", default=None,
                     help="required with --count > 1")
    p.add_argument("--jobs", type=int, default=8,
                     help="batch workers (execution order cannot affect output)")
    args = p.parse_args(argv)
    if args.count > 1:
        if args.out_dir is None:
            p.error("--count > 1 requires --out-dir")
        run_batch(args.count, args.out_dir, args.seed, args.generator,
                  args.players, args.min_hill_dist, args.jobs)
        return 0
    rng = random.Random(args.seed)
    n = args.players or rng.choice([2, 3, 4])
    gen = args.generator or rng.choice(GENS)
    text, argv, cwd = generate_one(gen, n, rng, args.min_hill_dist)
    sys.stdout.write(render(text, argv, cwd,
                            f"{args.seed} (players {n}, type {gen},"
                            f" min-hill-dist {args.min_hill_dist})"))
    rows = next(l for l in text.splitlines() if l.startswith("rows"))
    cols = next(l for l in text.splitlines() if l.startswith("cols"))
    print(f"{gen} {rows} {cols} players {n} hills 1", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
