# Run: back to rung 2 (round 12) — PLAN

Reverted per the demotion rules: tiebreak out (pacifism incentive),
gen2p duds cut, pool back to small decisive ground.

- Hypothesis: round-9 rewards (FOOD+KILL+DEATH+HILL + undecayed
  outcome, no tiebreak) on the extended small pool resume
  promotions; the round-11 stall was the tiebreak + big duds,
  not a spent ladder.
- Config: 10-board pool (rung1_open + rung2a/b/c/d + rung2f/g/h
  mapgen + rung2i/j caves), all train (no split, evals on train
  with rotation). Turns 150, temp 2.0. Rewards identical to round 9
  (tiebreak fully removed, tests green).
- New boards f-j join as passengers (staged, smoked, validated);
  the per-map table promotes or demotes each at the 10% bar.
- Success criteria: >= 1 promotion; rung2a/d peace back under 0.5;
  rung-1 peace falls from 0.75 (no pacifism pay); new boards show
  decisive games or get cut.
- Failure criteria: 0 promotions with peace still rising ->
  the stall is deeper than incentives (actor/exploration redesign,
  per-role exploiters move up the queue).
- Results: pending.
- Verdict: pending.
