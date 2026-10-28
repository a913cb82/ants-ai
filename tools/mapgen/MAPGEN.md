# tools/mapgen runner notes

All commands run from `tools/mapgen/` (cavemap from `tools/mapgen/amstan/`),
headless, map on stdout, exit 0. Small 2p maps verified with
`ml.mapgen.is_playable_2p` (see `tests/test_mapgen.py`).

| script | 2p / smoke command |
|---|---|
| mapgen.py (walk Grid) | `python mapgen.py --no_players 2 --min_hills 2 --max_hills 2 --min_dimensions 32 --max_dimensions 40 --min_block_size 4 --max_block_size 4 --symmetry rotational --rotational_symmetry 3 --seed 1` (2p playable) |
| cell_maze.py | `python cell_maze.py -p 2 -g 1 2 --h_sym rotate --hills 2 -a 2500 -r 1.0 -s 1` (2p playable; needs area >= 900/player) |
| amstan/mapgen.py (cavemap) | `python mapgen.py --cols 40 --rows 40 --symmetry rotational --players 2 --hills 2 --seed 1` (2p playable) |
| symmetric_mapgen.py | `python symmetric_mapgen.py --players 2 --seed 1` (2p playable; native floor ~50px/side) |
| asymmetric_mapgen.py | `python asymmetric_mapgen.py --players 2 --min_dim 30 --max_dim 40 --min_start_distance 10 --seed 1` (2p playable; upstream minimum is 4 players) |
| random_map.py | `python random_map.py --rows 40 --cols 40 --players 2 --seed 1` (2p playable); bare `python random_map.py` for defaults |
| heightmap.py | `python heightmap.py --seed 1` (single-start map only: 2p tiling is disabled upstream, so not 2p-playable) |
| McMaps.py | `python McMaps.py` (40x40 cells maze, no player starts: no hill-entry path upstream, so not 2p-playable) |

Java files (compile: `javac -d <dir> *.java`, run with `java -cp <dir>`;
never emit `.class` into the repo):
- Test driver: `java -cp <dir> Test --players 2 --seed 1` (2p, playable;
  starts print as hills A/B; `--players 4|8` also work; sizes 80-120px)
- SymmetricMapgen: `java -cp <dir> SymmetricMapgen --players 2 --rows 40
  --cols 40 --min_start_distance 10 --seed 1` (2p, playable; starts print
  as hill digits 0/1; bare `java -cp <dir> SymmetricMapgen` keeps the
  upstream 4-10p random behavior)
