# Run: continuous main lineage (round 14) — PLAN

AlphaStar baseline: one main that trains continuously and never
resets; periodic exploiters reset to supervised; PFSP-lite memory.
No branch caps, no prune rules (doctrine).

- Hypothesis: resetting to champ every gen + fresh Adam + 4 games
  then discard is amnesia; a main that accumulates across gens
  crosses valleys the reset regime cannot. Parent chains fall out
  automatically (snapshot parent = last main, not champ).
- Design (minimal diff, role names kept — "challenger" still
  challenges; the continuity is in weights/optimizer, not labels):
  - archive.get_main/set_main pointer (mirror of champion).
  - train_generation takes incoming opt state, returns outgoing;
    optimizer state persists in {id}.opt.json next to weights.
  - run_generation: main trains from own weights+opt; snapshot
    saved with parent=old-main; eval vs champ; promotion moves the
    champ pointer only — the main never resets, never dies.
  - Bootstrap (first gen): main = champ copy. Exploiters unchanged
    (supervised reset, one-shot, parent=champ — stars are fine for
    scouts).
  - No collapse guard: a rotted main keeps training (AlphaStar
    accepts this; PFSP gives it winnable opponents). The verdict
    judges; the champ pointer never moves backward.
- Success criteria: promotion rate up vs rounds 12-13 on same pool
  (0/15, 2/15); parent chains visible in manifest (depth > 1);
  no eval-floor collapse across the round.
- Failure criteria: main rots (eval wr falls gen over gen with no
  recovery) -> revert to reset-regime (one commit, pointer delete);
  0 promotions with flat peace -> the stall is elsewhere (actor?).
- Pool: same 8 boards (comparison stability). Graduation still
  deferred (rung 3 needs drill-reservation first).
- Results (g217-g231): ONE PROMOTION — g222 (EXPLOITER,
  kill-heavy) over g212, wr 0.625. First exploiter promotion ever.
  Main gens: best wr 0.60 (g230, below Wilson bar), no promotion.
  Champ g212 -> g222. Teeth vindicated: the valley is crossable by
  invasion (exploiter joined the podium, not just the population).
- Lineage mechanics CONFIRMED: parent chains depth 13 -> 21+ in
  manifest (chains, not stars). No rot: worst eval wr 0.375, draws
  throughout, v healthy. Accumulation NOT yet evident: main returns
  noisy (.52 -> 1.50 -> .33 ... spikes only), no monotonic climb —
  10 main gens is a short sample for a compounding effect.
- Boards: funnels still the battlegrounds (gap 0.00-0.13 peace,
  caves low); opens peaceful (0.5-0.8). Pattern stable 2 rounds.
- Verdict: lineage KEPT as infrastructure (chains + no-rot proven).
  Round 15 = continuation on same pool: accumulation needs a longer
  sample; no new variable while the slow effect is mid-read.
