# tools/mapgen fork note (vs upstream `main`)

The engine is pristine: `engine.py`, `game.py`, `ants.py`,
`playgame.py`, `sandbox.py` have zero diff vs `main`. Game rules,
protocol, and scoring are untouched.

Everything below is confined to `tools/mapgen/` (map *generators*,
never the game itself) and is kept deliberately:

## Python 3 fixes

- `map.py`: `end_locs[:]` → `list(end_locs)` (slice assumed a list).
- `McMaps.py`: `import Image` → `from PIL import ...`; `choice(dict.keys())`
  → `choice(list(...))`; dict-iteration ordering fixes.
- `amstan/cavemap.py`: bitrotted `LAND`/`WATER` import (moved to
  `terrain.py`) — one line.
- `heightmap.py`, `symmetric_mapgen.py`: py3 print/division/ordering
  cleanups (see per-file diff).

## Seedability / CLI (previously random-only output)

- `random_map.py`, `asymmetric_mapgen.py`, `symmetric_mapgen.py`:
  `--rows/--cols/--players/--seed` (`--min_start_distance` where the
  algorithm needs it). Defaults preserve old behavior.
- Java (`MapGenerator.java`, `MapWalker.java`, `SymmetricMapgen.java`,
  `Test.java`, `McMaps.java`): headless `main()` entry points
  (`--players/--seed/--rows/--cols/--out`) so they run on a modern
  JDK instead of only as 2011-era Applets.

## Performance (claimed byte-identical output)

- `symmetric_mapgen.py` internals (~2.4x in-process), walk/`Grid`
  internals, `cavemap` smooth-path dispatch. Commit messages record
  the preserved sequences (same `randint` order, same write order);
  `tests/test_mapgen*.py` pin runnable + parseable + 2p-playable.
  A per-generator seeded golden hash would strengthen this.

## Relocated, not new

- `gen_mixed.py`: moved from `tools/maps/curriculum/` (removed in
  `2a4031d`) to `tools/mapgen/` with in-process generation.
  Not upstream code — ours, kept here.

- `gen_mixed.py`: `seeded()` context manager pins global RNG for one
  in-process build and restores host state after. The generators seed
  global random themselves (upstream convention), so importers
  (`ml/mapgen.generate`, pytest) wrap generation in `seeded()` instead
  of touching 100+ call sites. Sampling RNGs (`random.Random`
  instances) stay untouched.
- `gen_mixed.py`: `generate_one()` / `_generate_deterministic()` are
  the in-process single-map path `ml/mapgen.generate()` delegates
  to (symmetric 2p, validated before return). Same code path as the
  batch/pool builders — one tested route, not two.

## Rule

Engine files must match `main`. Generator fixes above stay, and new
generator changes land here with a line in this file. The training
pool itself lives in `ml/mapgen.py` (`default_pool`); `tools/mapgen`
scripts are validated by `tests/test_mapgen*.py`.
