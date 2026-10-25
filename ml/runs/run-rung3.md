# Run: rung-3 scale-up (round 10) — IN PROGRESS

- Hypothesis: rung-2 promoters transfer to scale and variety;
  early rungs in the pool prevent forgetting.
- Config: 19-board pool (rung 1 + rung2a-d + 14 random_walk),
  split 17-18 train + 2 held (rung 1 held = retention exam);
  train games rotate across the pool by generation (fixed the
  first-4-maps pinning bug); per-game map logging on.
  Turns 150, temp 2.0. Same rewards + rotation.
- Success criteria: >= 1 promotion; per-map peace table shows no
  dud boards; rung-1 held evals hold (retention).
- Design dispute (mid-round): held-out promotion evals questioned
  — low-variety held sets are board-quirk lotteries, cross-rung
  evals test the wrong skills. Queued redesign: promote on train
  pool, probe generalization display-only. Any 10b promotion gets
  a board-by-board audit before it counts.
- Results: pending.
- Verdict: pending.
- Next: pending (eval redesign + audit, then round 11 per rule).
