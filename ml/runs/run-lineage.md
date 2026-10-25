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
- Results: pending.
- Verdict: pending.
