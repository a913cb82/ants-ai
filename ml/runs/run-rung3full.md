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
- Results: pending.
- Verdict: pending.
