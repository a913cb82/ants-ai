# CURVES verify — 7-curve progress board (impl/curves)

Worktree `/tmp/impl-curves`, branch `impl/curves`, base `ml/alphastarzero`
`6e385c4`. Venv `/home/abrai/projects/ants-ai/.venv/bin/python`.
Live archive `/home/abrai/projects/ants-ai/ml/archive` was never written:
all serves were GET routes; `games.jsonl`/`matrix.json`/`history.jsonl`
mtimes still `2026-10-31 14:49/14:50`; `git status` in the live repo clean.

## What changed

- `ml/dashboard.py` (single file, stdlib-only, same STYLES/SCRIPT/poll-tick
  structure, no new ports/flags/deps):
  - New pure computations: `wilson_bounds`, `_hinges` (Tukey),
    `roll_median`/`roll_mean`, `bt_fit` (sparse Bradley-Terry MM, Laplace
    +1/+1 prior like `archive._head_to_head` + one virtual win/loss vs a
    rating-0 opponent), `_bt_cached`/`_sparse_bt` (eval-digest cache, same
    key as Nash), `panel_ids` (g000 + last 3 deposed), `anchored_elo`
    (panel-mean zero, ×400/ln10), `elo_series`, `knock_conversion`,
    `decisiveness` (train from grouped games, eval from duel margins),
    `margin_band` (pooled 15-gen median±IQR), `pg_signal` (10-gen median,
    ratio labelled EXPERIMENTAL), `value_slope`, `reign_strip`
    (tenure/turnover/Nash entropy), `nplayer_start` (derived from grouped
    games), `crown_type` (complete = promoted AND wins>losses AND
    mean_margin>0, else soft; held gens wear "—"), `build_board`.
  - `snapshot()` gains `board` (7 curves, x = challenger ids) and per-gen
    `crown`; old `curves.loss/ret/ids` keys kept stable (page no longer
    plots them).
  - Page: 7 new canvases replace policy-loss/mean-return cards; generations
    table gains a crown column; new `frame/lineInto/plotLines/plotBand/
    plotBars/plotDual/plotStrip` JS; dead `plot/deltaChip` removed; poll
    tick (5s active / 15s idle), Nash display, population, maps, games
    untouched.
  - STOP list honored: mean policy loss + raw mean return cards deleted;
    kl_anchor has no series anywhere (nothing to skip); jury band omitted
    with a code comment (no jury field/regime in training data — notes-only
    proposal, will not invent); no `ledger_version` touched, no training
    code touched.
- `tests/test_curves.py`: 16 tests, one per computation + snapshot wiring.

## Verify evidence

- `pytest tests/ -q -m "not slow"` (worktree): **370 passed**, 2 failed —
  both pre-exist on base, confirmed via `git stash`:
  `league/test_pool.py::test_pool_matches_golden` (golden drift) and
  `test_advantage_freeze.py` (env-dependent). No new failures.
- `ruff check tests/test_curves.py`: clean. `ml/dashboard.py` ruff set
  identical to base (12 pre-existing).
- `node --check` on extracted SCRIPT: OK.
- Synthetic archive (`/tmp/synth_build.py`: 60 gens, staircase crowns at
  5/10/18/24/44/52/60, drought gens 25–40, turtle climb 45–60, one 3p game
  at gen 30): snapshot 200, all 9 board keys present, lengths 60.
  - Elo staircase with jumps at crowns; knock.rate 1.0 in turtle stretch
    with Wilson whiskers inside [0,1]; conversion low; decisive.train 0.75;
    margin band q1/q3 −2/+1; pg ratio falling .063→.053; vslope +0.6;
    tenure resets at turnovers; reign.entropy rising; regimes
    `{nplayer: 29, nplayer_gen: c030}`; crowns include a `soft` (c018).
  - `/` 200 (all 8 canvas ids, no `ch-loss`/`ch-ret`), `/api/games` 200.
- Real archive, served read-only: `/api/snapshot` 200 (1.8MB), `/` 200,
  `/api/games` 200, no 500s. Curve lengths 1690 across the board;
  pg.ratio nonnull 1375/1690 (pre-pg_abs gens → None, never 0);
  knock.conv null in 96 drought windows; panel
  `['g000','g1658','g1660','g1718']`, champ Elo 42.8 rising across thrones
  (−44.5 → −8.2 → 11.2 → 41.6 → 42.8); crowns 64 complete / 1626 held-blank;
  regimes `{nplayer: 1689, nplayer_gen: g1732}`; tenure last 11.

## Perf (real 1690-gen archive)

- BT fit standalone cold: **0.08s** (100 MM sweeps × ~6k played pairs).
- Full snapshot cold: **4.42s** (grouping 80k rows + 22MB history parse
  dominate; BT + Nash cached thereafter). Warm: **0.37s**.
- Synth (60 gens) cold 0.04s, warm 0.005s.

## Follow-ups (not in this branch)

- BT Elo is global-fit-then-slice: a champ's rating absorbs late-field
  strength. A per-era refit would read truer but costs cold-start budget.
- Real-archive crowns are 64/64 complete — the soft tag is proven only by
  the synthetic case; fine, the rule is documented in code.
- Old `plot` delta chips removed with the cards; `.delta` CSS left
  harmlessly in place.
