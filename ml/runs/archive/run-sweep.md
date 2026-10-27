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
- Results (g368-g382): 0 PROMOTIONS. Train decisive 0/120;
  held evals 2/300 (both one exploiter, g379, both colors — genuine
  edge, below bar). Sweep reached 128/145 (random_walk tier
  touched). Champ g314 frozen. Single new converter is an
  unpromoted exploiter win, not lineage learning.
- Verdict: RETREAT confirmed. Coverage without retention teaches
  nothing: 4 games/gen cannot accumulate board-specific lessons
  across 145 boards (36-gen revisits). Synthesis for after the
  retreat: ROTATING small windows (retention within window,
  coverage across windows) — neither one big pool (no retention)
  nor one small pool forever (overfit). Sharp test first: round 24
  retreats to the known 8; if conversion resumes immediately, the
  engine works and the disease is generalization, not learning.
