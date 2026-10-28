# tools/mapgen runner notes (3-file scope)

All commands run from `tools/mapgen/`, headless, map on stdout, exit 0.
2p checks use `ml.mapgen.is_playable_2p` (see `tests/test_mapgen.py`).

| script | smoke command |
|---|---|
| random_map.py | `python random_map.py --rows 40 --cols 40 --players 2 --seed 1` (2p playable); bare `python random_map.py` for defaults |
| heightmap.py | `python heightmap.py --seed 1` (single-start map only: 2p tiling is disabled upstream, so not 2p-playable) |
| McMaps.py | `python McMaps.py` (40x40 cells maze, no player starts: no hill-entry path upstream, so not 2p-playable) |

Other generators (walk/cell_maze/symmetric/cavemap/asymmetric 2p work
and *.java) belong to sibling builders — not touched here.
