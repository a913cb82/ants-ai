# Run: rung-1 breakthrough (rounds 4-5b)

- Hypothesis: the environment, not the algorithm, is the binding
  constraint — decisive games on a tiny board teach what draws on
  big maps cannot.
- Config: tools/maps/curriculum/rung1_open.map (12x16, no water,
  hills 8 apart in sight), turns 150, temp 2.0, entropy 0.05,
  eval-turns 150, rotation augmentation on, undecayed outcome,
  FOOD+KILL+DEATH+HILL credit.
- Success criteria: decisive train games, first promotion.
- Results: contact from gen 1 (peace 27/28 train in round 4b);
  promotions g075 (0.70), g081 (0.65), g083 (0.65) across round 5b;
  margins negative for most challengers, positive for promoters.
- Also shipped: rotation augmentation (quarter-turn window/action/
  mask), Wilson-only promotion (Nash leg dropped — star data can't
  rank), per-duel eval margins (display), eval map rotation,
  AlphaAnt rename, replay names, run timing dashboard.
- Verdict: CONFIRMED. The same algorithm that flatlined for 100+
  gens promotes 3/15 once games are decisive. Selection was never
  broken; the signal was.
- Outcome decay dropped as unjustified (time distance is not causal
distance) from round 5b on; promotions correlate with the no-decay
regime (0/5 decayed, 3/15 undecayed) but the samples are small.
- Next: FOOD ablation (is food credit Blizzard-score trap or
  load-bearing?).
