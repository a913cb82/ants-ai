# Run: BC init (30 gens, seed 456)

- Hypothesis: starting from imitated pro play plus an unshared
  critic trunk breaks the chicken-and-egg (competent behavior from
  step one gives the critic something predictable to fit).
- Config: fresh ml/archive (seed-7 kept in ml/archive_seed7),
  --init-weights /tmp/bcpros/bc_weights.json (xathis 6 games ->
  70,585 rows, val acc 0.462 vs 0.20 chance; live gate 23-4 vs
  random), split value trunk (vconv*), continuity, shaping,
  batch-norm, turns 60.
- Success criteria: v_loss sustained < 0.7, train-return ascent,
  first promotion.
- Results: ret 0.19-0.22 flat (2x random level, no ascent);
  v 0.64-0.92 flicker (dips never hold); eval 0W/600D, all margins
  0.0; 0 promotions. Train games show 4-4/5-5 (combat!), evals
  1-1 (symmetric peace at 60t truncation).
- Verdict: rejected as sufficient. BC + critic work mechanically
  (gen-1 starts where 10 random gens couldn't reach) but nothing
  compounds and 60-turn evals are blind by truncation.
- Diagnosed during: full-trunk banking bug (saved only value.*,
  critic reset every gen — fixed), evals must run longer than
  training, actor frozen at BC weights (0.006 moves).
- Next: bank the full critic, ENGAGE shaping, --eval-turns 150,
  exploration up (temp 2.0, entropy 0.05).
