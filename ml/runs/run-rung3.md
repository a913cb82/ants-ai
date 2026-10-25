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
- Results (g153-g167): ONE PROMOTION — g160 over g146 (0.625).
  AUDIT (promised, delivered): evals were 10 rung-1 + 10 held-rw32
  duels, and rw32 drew all 150 games across the round — so g160's
  wins came from rung 1 alone. Verdict: promotion STANDS as lineage
  progress (rules in force) but does NOT count toward rung-3
  graduation (zero evidence of rung-3-board skill). Rung-3
  graduation counter: 0.
- RUNG 3 AS CONSTRUCTED REJECTED: every random_walk board
  zero-decisive (train and held alike, 0.00 across the round).
  3k-5k tiles at 150 turns/temp-2.0 never meet — the pool teaches
  nothing. The ladder has a gap: 560 tiles (rung2d) -> 3000 with
  nothing between.
- FORGETTING CONFIRMED: rung 1 held-only (never trains) -> eval
  peace 0.66-0.70, up from ~0.27 when it trained every gen.
  Contact skill does not transfer by itself; early maps must TRAIN.
  rung2a/b also quiet (0/6-0/8, small samples — watch, don't conclude).
- Rotation fix confirmed: train maps varied every gen, full sweep
  across blocks. Per-map logging worked (this entire audit runs on it).
- Exploiters g158/g164 collapsed on rung 1 (0-7-3 each) — random-init
  attackers are target practice, not selection pressure (feeds the
  per-role exploiter case).
- Verdict: rung-3-rw dropped; rung 3 rebuilt as generated mid-size
  boards (1000-2000 tiles, same 4 water shapes); curriculum always
  trains (no split under 13 maps -> evals on train, rounds-1-9
  behavior restored); tiebreak rewards draws by material.
- Next: round 11 = tiebreak (single experimental variable) on the
  rebuilt pool.
