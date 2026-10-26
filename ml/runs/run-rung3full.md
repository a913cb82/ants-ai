# Run: full-pool graduation (round 22) — PLAN

The 8-board pool is exhausted: only rung 1 converts for 60+ gens,
7 boards draw. The 2-in-10 graduation bar is declared STALE — it
was a readiness heuristic for a flowing regime; in a stalled regime
it blocks the exit forever. Pool exhaustion is the stronger signal.

- Hypothesis: new boards = new selection pressure; the draw regime
  is pool-specific, not policy-terminal.
- Config: default pool (158 playable 2p: 145 train + 13 held),
  drills guarantee every board its slice (~37-gen sweep), evals
  held-out (13 boards satisfies the standing rule). Everything else
  identical: DEATH -2, kl 0.01, 15x15 + own_sight, D4, lineage,
  exploiters every 3rd gen. Graduation = dropping --maps.
- Acceptance: conversion on non-rung1 boards; promotions.
- Success criteria: >= 1 promotion OR >= 3 new boards converting.
- Failure criteria: pool-wide draws + 2x slower gens with nothing
  after 15 gens -> retreat to the 8-board pool (graduation
  reverted, bar reinstated in modified form).
- Results (g353-g367): 0 PROMOTIONS. Champ g314 holds. Train
  decisive 1/120 (0.8%) vs 13-24% on the 8-board pool; held evals
  4/300 decisive. Drills perfect (60/60 unique, no repeats).
  Gens FASTER (62-77s vs ~110s) — draws resolve quickly.
  Only converter: tutorial1 (old-pool board). Random_walk tier
  untouched (78/145 boards undrilled).
- Verdict: STAY one final round per the conjunctive bar (draws yes,
  slower no — staying is cheap). But sharpen the question: drills
  guarantee coverage, NOT retention — with 4 games/gen each board
  revisits every ~36 gens, so no board-specific learning can
  accumulate. Round 23 finishes the sweep (random_walk tier!);
  if the remaining 85 also draw, breadth is dead and we retreat —
  the lesson being retention-beats-coverage (small rotating pools,
  not one big pool).
