# Run: seed-7 baseline (30 gens, full pool)

- Hypothesis: random-init self-play on the real map pool learns
  to play Ants.
- Config: ml/archive, seed 7, turns 250, train 4 / eval 20 games,
  workers 8, base arch, commit on. Random champion g000.
- Success criteria: sustained eval wins, first promotion.
- Results: train returns flat 0.15-0.18; eval 5W/595D (99.2%
  draws); v_loss flat ~0.78; 0 promotions in 30 gens.
- Verdict: rejected. Champion stuck at random init — 30 gens were
  30 independent random walks, nothing accumulated.
- Failure chain (verified end to end): reset critic every gen +
  per-minibatch normalization amplifying noise + flat walk-back
  credit + random-init champion + frozen behavior (0 razes in
  96 games, ~0.5 deaths/side: random-walk foraging, never fighting).
- Next: probes to isolate each link (shaping, normalization,
  critic continuity, horizon).
