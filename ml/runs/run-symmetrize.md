# Run: D4 symmetrization (round 16) — PLAN

Smallest architectural change with a guaranteed property.

- Hypothesis: orientation noise (41% rotation agreement, east bias
  173/500) caps performance; exact equivariance removes the lottery.
- Config: forward() averages mapped-back logits over all 8 dihedral
  orientations; values() averages (invariant). Train=act coherent
  (inside forward, all callers), weight-compatible (same params).
  Same 8-board pool, same everything else.
- Acceptance: probe agreement 100% by construction (MET: 500/500,
  histogram balanced N116/E91/S106/W94/stay93) + promotion rate vs
  rounds 12-15.
- Success criteria: >= 1 promotion; eval margins widen vs round 15.
- Failure criteria: 0 promotions + flat margins -> equivariance is
  hygiene, not leverage; move to KL anchor.
- Results: pending.
- Verdict: pending.
