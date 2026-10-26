# Run: finish the sweep (round 23) — PLAN

Round 22 drilled 60/145 boards: perfect coverage, zero new
converters. The failure bar needs a final answer on the remaining
85 (including the whole random_walk tier).

- Hypothesis: the undrilled majority contains converters; the
  round-22 zeros are sampling, not policy-terminal draws.
- Config: identical to round 22 (full pool, drills, held evals,
  DEATH -2, kl 0.01). Finish the sweep (~127/145 drilled).
- Success criteria: >= 3 new converters OR >= 1 promotion.
- Failure criteria: conversion still ~0 on the remaining 85 ->
  RETREAT to the 8-board pool. Lesson: retention beats coverage;
  future variety comes from rotating small pools, never one big
  pool (4 games/gen cannot teach 145 boards).
- Results: pending.
- Verdict: pending.
