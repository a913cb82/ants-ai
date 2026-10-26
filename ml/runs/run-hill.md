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
- Results (g413-g427): ONE PROMOTION — g422 over g400 (0.625,
  MAIN dethrones the kamikaze, crowns stop at 4). Champ g400 ->
  g422. Lakes (2d) SUSTAINS conversion all 3 blocks; 2b/2c spikes
  were noise (0 wins in 38 eval games each). v healthy, HA mass
  sustained, no suicide.
- Verdict: HORIZON FIX REAL — keep +0.5. Forensics (this turn):
  lakes wins are SOLO hill-races (12-84 turns, 2-4 deaths, 3-0) —
  speed, not breakthrough. HA-as-min-nearest subsidizes racing
  (each ant closes its own nearest = split forces), which open
  ground rewards and funnels punish. Next variable (round 27):
  HA pays closing to the FIRST enemy hill only — a shared
  convention concentrating force for breakthroughs. Risks lakes
  solos (they lose HA subsidy but keep the +10 raze); watch
  lakes + death rate.
