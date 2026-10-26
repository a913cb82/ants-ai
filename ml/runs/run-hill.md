# Run: hill-approach shaping (round 25) — PLAN

Round 24's retreat failed to restore conversion, and the mechanism
is horizon: GAMMA 0.97 over ~100-turn hill walks discounts a +10
raze to ~+0.5, which cannot compete with an immediate -2 death.
Gather-now + survive-now is the rational policy; draws are CORRECT
per the rewards. Rung1 converts because its hills sit inside the
~30-turn effective horizon.

- Hypothesis: same-turn pay for hillward motion (+0.5/tile, unsplit,
  unconditioned, arrival excluded) shortens the horizon — hills pay
  now, not at arrival. Marching 20 turns (+10) beats one death (-2).
- Config: HILL_APPROACH 0.5 added to base + exploiter scales (same
  value both — one variable). Same 8-board retreat pool, kl 0.01.
- Acceptance: conversion rises on non-rung1 boards; promotions.
- Success criteria: >= 1 promotion AND hill_approach mass visible
  in decompose (the channel is used, not just present).
- Failure criteria: 0 promotions + flat conversion -> the horizon
  diagnosis is wrong; next is pure-outcome ablation (the other
  fired conditional). SUICIDE-WATCH: hill-approach death rate
  spikes (marching into defenders) -> cut scale to 0.2 or gate.
- Results: pending.
- Verdict: pending.
