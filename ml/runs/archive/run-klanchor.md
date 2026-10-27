# Run: KL anchor to supervised base (round 17) — PLAN

AlphaStar bounds its agents to the supervised base with KL
throughout fine-tuning; ours drifted 100+ gens unleashed.

- Hypothesis: unbounded drift wastes wins (champs wander off the
  competent manifold); a light leash keeps adaptation near pro play.
- Config: --kl-anchor-beta 0.01, anchor = g000 (BC-from-pros) for
  every gen, same 8-board pool. Smoke: kl_anchor 0 -> 0.002.
- Acceptance: promotions continue with less drift (kl_anchor small
  and bounded across gens); falsified if it shackles adaptation
  (margins freeze, 0 promotions, policies collapse onto BC).
- Success criteria: >= 1 promotion; kl_anchor bounded.
- Failure criteria: 0 promotions + frozen margins -> cut the leash,
  keep drift.
- Results: pending.
- Verdict: pending.
