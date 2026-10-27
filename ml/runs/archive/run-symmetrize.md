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
- Results (g247-g261): ONE PROMOTION — g253 over g246 (0.625).
  No slowdown (8x forward invisible, engine-bound). Margins narrow
  (±3 max, five straight all-draw evals). Score-peace deepens
  0.27 -> 0.14, BUT forensics overturn the narrative: funnel
  "draws" include 44-death bloodbaths (pond), 18-22 death wars
  (gap, caves) alongside bloodless standoffs. Score margin
  measures RAZES, not combat — hill-taking declined, fighting
  persists. Corrected pattern: opens convert (razes), funnels
  brawl without breakthrough (attack conversion problem, not
  pacifism).
- Verdict: hygiene CONFIRMED (100% agreement, bias gone, free),
  leverage UNPROVEN (promotion unattributable — lineage compounding
  explains g253 as well). Kept as infrastructure. Doctrine fix:
  demotion bar goes contact-based (deaths + razes from sampled
  replays), not score-based — score peace conflates bloodbaths
  with standoffs. Next variable: KL anchor (round 17).
