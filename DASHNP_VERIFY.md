# Dash-NP verify evidence (2026-10-31, branch impl/dash-np)

Servers run from this worktree (`/tmp/impl-dash-np`):
`ml/dashboard.py --port 8099 --archive /tmp/dashnp-synth` (synthetic) and
`--port 8098 --archive /home/abrai/projects/ants-ai/ml/archive` (real,
read-only). Synthetic archive built by `/tmp/dashnp-synth-build.py`.

## Synthetic archive (scripted: 2p+3p+4p × train+eval + legacy rows)

23 pair rows → **9 visual games** (6 with uuid ids, 1 legacy 2p pair, 2 from
a legacy re-run collision split). `GET /api/snapshot` → 200, 5834B, 4ms.

`counts`: `{"generations": 1, "games": 9}`, `game_total: 9`.
Every section present: champion/g000, members, run, curves, generations,
games, maps, status.

Per-game seats (`kind n [(id,score,rank,margin,pts,result)] pairs map`):

```text
eval n=2 [('g000', 3, 0, 3, 1.0, 'win'), ('g001', 0, 1, -3, 0.0, 'loss')] pairs=1 None      <- collision half A
eval n=2 [('g000', 0, 1, -3, 0.0, 'loss'), ('g001', 3, 0, 3, 1.0, 'win')] pairs=1 None      <- collision half B
eval n=2 [('g000', 2, 0, 0, 0.5, 'draw'), ('g001', 2, 0, 0, 0.5, 'draw')] pairs=1 open2.map <- legacy 2p
eval n=4 [('g000', 5, 0, 2, 1.0, 'win'), ('g001', 3, 1, -2, 0.0, 'loss'),
          ('g002', 3, 1, -2, 0.0, 'loss'), ('g003', 0, 3, -5, 0.0, 'loss')] pairs=6 cave4.map
eval n=3 [('g000', 4, 0, 3, 1.0, 'win'), ('g001', 1, 1, -3, 0.0, 'loss'),
          ('g002', 1, 1, -3, 0.0, 'loss')] pairs=3 sym3.map
eval n=2 [('g000', 3, 0, 2, 1.0, 'win'), ('g001', 1, 1, -2, 0.0, 'loss')] pairs=1 open2.map
train n=4 [...] pairs=6 cave4.map
train n=3 [...] pairs=3 sym3.map
train n=2 [...] pairs=1 open2.map
```

- Ranks use the engine formula (tied 3s share rank 1, next is 3); margin =
  score − field-best; pts = effective points (1/0.5/0).
- `maps` (per map × seats): open2.map×2 (train 1, eval 2, chal 1-1-0),
  sym3.map×3 (1/1, chal 1-0-0), cave4.map×4 (1/1, chal 1-0-0),
  unknown×2 legacy (eval 2, chal 1-0-1).
- Members W-D-L per GAME: g000 (4,1,1), g001 (1,1,4), g002 (0,0,2),
  g003 (0,0,1). Eval-only, as before.
- `GET /api/games` → total 9 (not 23). `?member=g003` → total 2, first row
  n=4 with all four seats. `?member=g002` → total 4. `?limit=2&offset=8` →
  1 row (pager protocol intact).
- `GET /replay?f=games/g009/eval4/logs/0.replay` → 200; missing file → 404.
- `GET /` → 200, contains maps-body, games-body, gen-body, pop-body,
  "N-seat games" legend, "chal W-D-L" maps header.

## Real archive (read-only)

`GET /api/snapshot` → 200, 1.2MB. No 500 on `/`, `/api/snapshot`,
`/api/games`, `/api/games?member=g1732&limit=1`, `/api/games?limit=100`.

- 80,613 rows → `game_total` **80,438** (distinct replays 80,431 + 7
  re-run-collision splits). No inflation (was: 80,613).
- Newest 50 games: 22× 3p, 12× 4p, 16× 2p — live N-player games render.
- 1690 generations, 1733 members, champion g1719; Nash/population/curves/
  generations sections unchanged in meaning.
- `maps`: 248 (map, seats) rows incl. the unknown-map legacy bucket.
- Example 4p eval game via member filter: g1732 eval n=4
  `[(g1732,1,rank1,loss),(g1719,1,rank1,loss),(g1718,3,rank0,win),\
  (g1690,0,rank3,loss)]`, 6 pairs, `mixed_064_symmetric_p4_28x36.map`
  (the live run now logs N-seat eval games too).
- Perf: cold snapshot 3.9s (parse + group + sparse Nash over
  1733 members); warm static 4ms (grouped cache); warm under live appends
  ~0.2s (file changes invalidate, same as the parse cache).
- Untouched: no `*.tmp` files in the real archive; the dashboard code
  path performs no writes (snapshot reads games/history/matrix/status/
  manifest; `archive.init` no-ops when dirs and matrix exist; replays
  only read). Server logs show no errors.

## Tests

`.venv/bin/python -m pytest tests/ -q -m "not slow"` from the worktree:
354 passed; 2 failures are PRE-EXISTING on base `b0e40da` (verified via
`git stash`: `league/test_pool.py::test_pool_matches_golden` golden drift,
`test_advantage_freeze` cwd-dependent `m.map` FileNotFoundError).
`tests/test_alphastarzero.py` alone: 191 passed, including 18 new dash-np
tests (TDD red first, all failed before the fix).
