# Run: retreat to the known 8 (round 24) — PLAN + RESULT

Sharp test: does conversion resume on known boards (disease is
generalization -> rotating windows next) or stay dead (disease is
learning -> learning-side work)?

- Config: rounds 19-21 exactly (8 boards, DEATH -2, kl 0.01).
- Results (g383-g397): 0 PROMOTIONS. Conversion 7.5-12.5%,
  rung1 only (50-75%); 6-7 maps sterile. Mains 10/15 all-draws.
  Champ g314. Retreat did NOT restore conversion.
- Verdict: the runner says learning-itself (critic resets, pg
  cancels) and rejects windows — agreed on windows (rounds 22-23
  settled that). But the SPECIFIC disease is horizon, not critic
  mechanics: GAMMA 0.97 over ~100-turn hill walks discounts a +10
  raze to ~+0.5, which cannot compete with an immediate -2 death —
  so gather-now + survive-now is the rational policy and draws are
  CORRECT per the rewards. Rung1 converts because its hills sit
  inside the effective horizon (~30 turns). The WIN outcome never
  fires because razes never happen: a circle that needs breaking
  from the near end. Round 25: hill-approach shaping (same-turn,
  immediate) shortens the horizon by paying hillward motion now.
  (Critic resets are structural to on-policy values under a
  changing actor, not a bug to fix first.)
