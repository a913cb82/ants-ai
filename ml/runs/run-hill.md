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
- Results (g398-g412): ONE PROMOTION — g400 over g314 (0.625,
  EXPLOITER, 4th kamikaze crown). Champ g314 -> g400. HA channel
  IS used (mass 51-65/game, ~40-50% of death mass); deaths steady
  (93-97%, no suicide spike). Conversion: one-block spikes (2d
  75%, 2c 50%, 2b 67%) that vanish — n=4-6/map noise, not
  sustained. Marching works; razing still doesn't follow.
- Verdict: WEAK POSITIVE — both bars fired (promotion + mass),
  but conversion is spikes, not regime. Consolidate (round 26,
  same config): if spikes sustain on some board + promotions
  continue, the horizon fix is real. Pattern note: 4 of the last
  5 crowns are kamikazes — the podium may be selecting for
  suicide-racers; watch whether the main beats g400 (as g314
  beat g313) or the crown sticks.
