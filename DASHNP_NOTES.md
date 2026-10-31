# Dash-NP: native 2/3/4-player dashboard — survey + design

Worktree: `/tmp/impl-dash-np`, branch `impl/dash-np` (base `ml/alphastarzero`
`b0e40da`). NOTE: the task brief said `/tmp/impl-dash`, but that path is
occupied by branch `impl/dashperf`; this work uses `/tmp/impl-dash-np`.
Venv: `/home/abrai/projects/ants-ai/.venv/bin/python`. Real archive
`/home/abrai/projects/ants-ai/ml/archive` is READ-ONLY for this work.

## PHASE 1 — SURVEY (2026-10-31)

### 1.1 Every 2-player assumption in `ml/dashboard.py` (833 lines, single file)

DATA (`snapshot()`):
- D1. Eval `tally` loop iterates pair-ROWS: each side of each pair takes a
  W/D/L entry. N-player breakage: each member collects N−1 entries per game
  (a 4p game = 3 entries per member); exact-duplicate rows double-count.
- D2. `counts["games"]` / `game_total` = `len(games)` = ROW count, not game
  count. Real archive today: 80,550 rows vs 80,411 true games (and growing
  with N-player adoption).
- D3. `"games": games[:50]` serves raw pair-rows: one 4p game floods 6 of 50
  slots with identical replay links; only 2 of N seats visible per row.
- D4. `_outcome(a,sa,b,sb,ref)` (~line 203) is 2-way only AND dead code (no
  callers: snapshot inlines comparisons, the page has its own JS copy). No
  N-seat equivalent exists anywhere.
- D5. Nash (`_sparse_nash`, `_eval_digest`, `_nash_cached`): reads
  `matrix.json` pairwise `a vs b` keys. Pairwise matrix food from N-player
  games is still pairwise → UNCHANGED in meaning. Population legend already
  says display-only. No change needed.
- D6. Generations table reads `history.jsonl` eval dicts
  (wins/draws/games/win_rate/margins/mean_margin) = challenger-vs-champion
  verdict from `evaluate.py` fixed seats 0/1 → valid for N-player eval games
  as-is. No change needed. (Margin math lives in `evaluate.py`, off-limits,
  and is correct as a chal-vs-champ verdict.)
- D7. NO per-map section exists anywhere (no per-map conversion to break
  out — must be added). NO train/eval-split bug: kind pills per row and
  eval-only population W-D-L are already N-agnostic.
- D8. NO champ-slice / juror-split / champ-share / drill / held-map
  references: grep finds only "held" = promoted/held badges. Nothing dead
  from the jury-removal commit. Nothing to remove.
- D9. Status line counts GAMES from the train/eval loops (not rows) and the
  eval verdict is chal-vs-champ by seat → valid for N players. No change.

API (`make_handler`):
- A1. `/api/games` member filter `r["a"]==member or r["b"]==member` works on
  pair-rows → must become any-seat on grouped games.
- A2. `/api/games` total/rows slices pair-rows → must slice grouped games.
  Limit/offset protocol itself is fine.

PAGE (`SCRIPT`):
- P1. JS `outcome(a,sa,b,sb)` is 2-way; matchup cell renders exactly two
  seats (`A 3 – 1 B`); result badge is "first-listed side's view"
  (`ref = m || x.a`).
- P2. Replay label (`gen + shortReplay`) repeats per pair-row for N-player
  games. Replay LINKS themselves are per-game already (all pairs share one
  replay path) → grouping preserves them intact.
- P3. Curves / population-shell / generations-shell / poll tick (5s active,
  15s idle) / system fonts / ThreadingHTTPServer: N-agnostic, keep all.

### 1.2 Archive schema: overcount = YES, per-game key = NO

- `train.py::_play_one` and `evaluate.py::_play_duel` both log ONE ROW PER
  SEAT-PAIR per game (`for x: for y in x+1`), all sharing `(gen, kind,
  replay, map)`. A 4p game = 6 rows, a 3p game = 3 rows.
- Real archive today: 80,550 rows / 80,411 distinct replays. 40 genuine
  N-player train games in gen g1732 (13× 4p with 6 distinct pairs, 27× 3p
  with 3), all correctly score-consistent per seat.
- No per-game key exists: grouping must derive from `replay`
  (`<rel>/logs/0.replay`, unique per play EXCEPT re-runs, see below).
- Legacy pathologies in the real archive that grouping must survive:
  (a) 20 eval double-logs in gen g608: 10× exact-duplicate rows (dedupe to
  one game), 10× conflicting re-run collisions, e.g. `games/g608/eval0`
  holds (g608 vs g513, 0–3) AND (2–2) → must split into two visual games;
  (b) with-replacement duplicate seats are REAL: `train5` = 3p field
  [g1732,g1690,g1690] scores [0,2,3] incl. a distinct-score self-pair row
  (g1690,g1690,2–3); `train20` = 4p [..,g1657,g1657]; `train37` = 3p
  [..,g1714,g1714]. Seat reconstruction must be POSITION-based, not
  id-keyed. All 3 `a==b` rows in 80k are of this kind — no junk self-pairs.
- N-way outcome source: the engine replay JSON carries `score[]` + `rank[]`
  (`tools/engine.py:360`, ties share rank via sorted-index). The dashboard
  re-derives rank with the same formula from logged pair scores (replays may
  be gone; pair scores are seat-consistent).

### 1.3 Tests

- `tests/test_alphastarzero.py` (~3034 lines) holds all dashboard tests
  (snapshot empty/populated, exploiter flag, run timing, replay guards, HTTP
  API, malformed rows, poisoned index) — all 2p row-shaped. No N-player
  dashboard tests, no per-map tests. Dashboard exercised via
  `dashboard.snapshot(base)` on tmp archives + live HTTP round-trip.
- Two tests monkeypatch `archive.log_game` with `lambda *a, **k: None`
  (compatible with a new optional kwarg).

## PHASE 2 — DESIGN (frozen)

### Carve-out (ONLY training-code change)

`archive.log_game(..., game=None)`: one additive `game` field, `"<rel>#<12-hex-uuid>"`
(rel = per-game outdir e.g. `games/g1732/train5`, keeps links greppable;
uuid suffix disambiguates re-runs, which the rel alone provably does NOT —
see g608). `train.py` (1 line) + `evaluate.py` (1 line) pass it. Nothing
else in training code. `_game_row` unchanged (key optional, unvalidated);
old rows group by fallback key (replay minus `/logs/0.replay`).

Why uuid, not rel alone: rel groups dup-seat pairs correctly but collides on
re-runs; uuid makes future grouping EXACT (dup seats share it, re-runs don't,
double-logs within one call are impossible). Legacy rows (frozen 80k) use a
heuristic partition: minimize total seat-positions over row partitions,
tie-break toward MORE games. Verified against every real case: true 3p/4p
merge (3 < 5/6, 4 < splits), dup-seat train5 merges to 3 seats, g608 re-run
collisions tie (4 vs 2+2) → split, exact dupes pre-deduped → one game.

### Dashboard changes (`ml/dashboard.py` only, stdlib, single file)

- Helpers (TDD red first): `rank_of` (engine formula), `game_key_of`,
  `partition_group` (+ `_realize` backtracking position assignment),
  `build_game` (seats per-POSITION `[{id,score,rank,margin,pts,result}]`,
  pairs detail), `member_game_result` (best seat on dup), `tally_eval`
  (per-GAME W-D-L, eval only), `summarize_maps` (per map×N: train/eval
  counts + eval chal-vs-champ record from fixed seats 0/1).
- Per-seat semantics: rank = engine formula; margin = score − best-other
  (matches `rewards.py` convention, N-native); result win = sole first,
  draw = tied first, loss = else; pts = 1/0.5/0 ("effective points").
  Population W-D-L becomes per-game (2p values identical; legacy dupes
  correctly deduped — the intended de-inflation).
- `snapshot()`: grouped games (first 50), `game_total`/`counts.games` =
  game count, members from per-game tally, NEW `maps` array. Nash,
  generations table, curves, status: untouched in meaning.
- `/api/games`: grouped rows `{gen,kind,map,replay,n,seats,pairs}`,
  any-seat member filter, same limit/offset protocol.
- Page: n==2 rows render EXACTLY the current HTML (byte-identical 2p
  history); n>2 rows render all seats + pairs detail; N-way badge from ref
  (filtered member else seat 0); NEW compact Maps section (map × seats →
  train/eval games + eval chal record). Minimal CSS additions, same stack.
- Dead 2-way `_outcome` replaced by N-way helpers.

### Deliberately OUT

- `ml/probe_imitate.py::champ_owner` assumes 2 seats (returns 0/1 by a/b) —
  analysis tooling, not the dashboard; flagged as follow-up, untouched.
- No promotion/verdict math changes (Wilson chal-vs-champ stays 2-way by
  design: fixed seats 0/1, extras are shared weather).
- No kind filter, no new ports/flags; per-map eval record uses seats 0/1
  only (train has no chal/champ framing).
