# Java map generators (tools/mapgen)

Build once: `javac -d /tmp/mjclasses tools/mapgen/*.java` (from repo root).

| File | Role | Command (exit 0, prints parseable map) |
|---|---|---|
| MapGenerator.java | Random mirrored symmetric map, 2/4/8 players | `java -cp /tmp/mjclasses MapGenerator --players 2 --seed 7 --rows 34 --cols 40 --out /tmp/mj2p.map` |
| MapWalker.java | Land-fill library; demo emits a small 2p map | `java -cp /tmp/mjclasses MapWalker --seed 7 --out /tmp/mjwalk.map` |
| SymmetricMapgen.java | Translation-symmetric map, 4-10 players (not 2p) | `java -cp /tmp/mjclasses SymmetricMapgen --seed 7 --out /tmp/mjsym.map` |
| Test.java | Thin driver over MapGenerator (default 8 players) | `java -cp /tmp/mjclasses Test 2 7 --out /tmp/mjtest2p.map` (also: `Test` alone, `Test 8`) |

Flags: `--players 2|4|8`, `--seed N`, `--rows R --cols C`, `--out FILE`
(Test/MapWalker/SymmetricMapgen use the obvious subset; Test takes
positional `[players [seed [outfile]]]`).

Checks: the 2p outputs pass `ml.mapgen.is_playable_2p` (start squares are
hills `0`/`1`, one per player) and load in the engine (`tools/ants.py`
`Ants({"map": text, ...})`). SymmetricMapgen output is parseable,
connected, and gives every player an ant+hill (`A`-`J`).
