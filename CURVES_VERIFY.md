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

## R1/R2/R3 revisions (lead review, 2026-10-31)

### R1 — BT-Elo on train+eval, candidate vs champion
- `merge_pairs` sums per-key wins across the eval (5.7k keys) + train
  (22.4k keys, incl. N-player seat-pairs) matrices; overlap adds.
  `bt_fit` itself unchanged, docstring now names the fit and the
  confound. Unknown ids still skipped (same as Nash).
- `elo_duel`: cand = this gen's challenger, champ = defending throne;
  crossovers read as throne changes. `turn_mismatch` scans configs for
  `eval_turns != turns` eras and `snapshot` exposes them as
  `board.elo.turn_note`; the card legend renders them dynamically
  ("turn confound (g031–g045: train 60 vs eval 150 turns) — mixed, not
  corrected") or "turn counts match across eras" when empty.
- Confound disclosed in code (`bt_fit` + `elo_duel` docstrings) and in
  one legend line; no correction attempted, per direction.
- Perf: merged fit standalone 0.19s cold at 100 iters (0.11s at 50;
  g000 −0.080 vs −0.074 — converged). Full snapshot cold 4.44s
  (unchanged: grouping + 22MB history parse dominate), warm 0.39s.
- Tests: `test_merge_pairs_sums_overlap`,
  `test_bt_fit_sees_train_only_members` (train-only member rates 0.0
  eval-only, nonzero merged), `test_elo_duel_candidate_above_champ`,
  `test_turn_mismatch_ranges`, `test_snapshot_duel_cand_above_champ`
  (tmp archive: b beats a 5–1 eval + 4–0 train → cand > champ).
- Real archive: crossovers at 36/64 promotions (jury-carried thrones
  legitimately sit below); synth staircase: cand −46.3 > champ −103.9
  pre-promotion.

### R2 — knock legibility
- `knock_conversion` gains the raw per-gen `knock` lane (1/0/None).
  Card is now twin panels: `plotTicks` marks lane (1 tick/gen, blue
  full-height alpha .55 = knock, gray nub = held, gap = no eval; same
  L/R x-geometry as the rate panel so marks line up with curves) over a
  shared-frame rate panel (`plotKnock`: knock blue + conversion green
  lines with Wilson bands). `plotBand` refactored onto shared `band()`.
- Tests: drought stretch marks all 0 / rate 0.0; turtle stretch marks
  all 1 / rate 1.0 (synth + unit). DOM: `ch-knock-marks` present.

### R3 — tenure/entropy legibility
- Diagnosed on the real archive: tenure max 295 (idx 1543) crushes the
  current 11 to ~7px; entropy spans 0.004–3.891 globally but the mid
  era sits 0.14–0.26 (flat line); turnover diamonds were 4px, regime
  shade 0.07.
- Fixes: `norm01` min-max lane + `plotNorm` labels the TRUE min/max on
  the axis (scale never a lie); server-side `reign.readout`
  ("tenure 11 · best 295") rendered into the card head via
  `<span id="tenure-now">`; tenure bars min-width 2px, diamonds 6px
  with white stroke, regime shade 0.12.
- Real archive: `readout: tenure 11 · best 295`, entropy_n 0.00–1.00,
  raw range labeled max 3.89 / min 0.00.
- Caught by a node DOM-stub harness (all render paths incl.
  renderBoard/renderGenerations executed against the synth snapshot):
  `F.H-T-B` parsed as `F.H - T - B` with bare `B` undefined — fixed to
  `F.H-F.T-F.B`. Harness rerun: BOARD RUNTIME OK.

### R4 — causal Elo (quantized refits, g000 anchor)

- `gen_pair_buckets` aggregates per-gen unordered pairs from the grouped
  game log (train+eval; game log used because only it carries gen
  attribution — record_result/log_game fire together per seat-pair, so
  the multiset matches matrix.json except legacy double-logs, which the
  matrix counts twice and grouping dedupes once; documented in code).
- `causal_refits`: 113 refits (every 15 gens, aligned to knock windows),
  each using pairs with gen <= refit gen, warm-started MM
  (shared `_mm_run` core with the one-shot `bt_fit`, tol 3e-5, cap 100).
  Plotted value at G is refits[G//15] (step-held). Zero = g000 only
  (known at gen 0); panel members ride as faint reference trajectories
  from the same refits (membership from full history is a display
  choice; every value uses games <= G). Turn confound note unchanged.
- Correctness proof: twin synthetic archives (35 vs 20 gens) agree
  bitwise on shared gens; streaming-extend (snapshot, append, snapshot)
  reuses stored refits bitwise. Early flat-zero Elo is real: the first
  70 archive gens are near-all draws (matrix confirms 5-5/2-2), so the
  old global fit's early -44.5 for g000 was pure late-field leak.
- Cost (explicitly reported, design kept per the fallback clause): full
  cold build ~7s for the refits (tol 3e-5; tol 0 costs ~10s, tol 1e-3
  costs ~2s but leaves 13 Elo tracking error). Worst plotted-series
  deviation vs the fully-converged reference: 0.41 Elo (p99 0.25,
  median 0.0002). Full snapshot cold 9.1-9.3s / warm 0.39-0.65s on the
  real archive (slow-marked perf test asserts < 60s / < 10s).
- Streamable: `_causal_cached` keeps (challengers, ids, buckets, totals,
  theta, refits); append-only training extends them — one cheap refit
  per poll instead of 113. Any rewrite falls back to a full rebuild.
  In-progress gen games join at its history append and move plotted Elo
  at its window's refit, by design. New tests: step-held constancy,
  truncated-window prefix property, g000 anchor, twin archives,
  streaming extend, real-archive perf.
