# Run: FOOD ablation (rounds 6-7)

- Hypothesis: FOOD credit is the Blizzard-score trap (mini-AlphaStar:
  dense game-score actively harmful, deleted for the final 96%+).
  Gathering earns strategic value through wars, not direct pay.
- Config: identical to rung-1 breakthrough minus the FOOD block
  (rewards.py deletion + zero-credit tests); rung 1 v2 (symmetric
  hills + 4 water singles) from round 7.
- Success criteria: promotions continue or accelerate without food;
  actor displacement rises (misalignment removed).
- Results: round 6: 0 promotions (best wr 0.55), peace 0.73-0.81,
  |pg| <= 0.074, actor 0.0109 frozen. Round 7: 0 promotions, eval
  wr declining 0.42 -> 0.35 -> 0.31, peace ~0.70 sustained.
  30 gens, 0 promotions, champion g083 holds throughout.
- Verdict: REJECTED. 0/30 without food vs 3/15 with it (same
  outcome scheme, same maps). Removing food removed the only
  within-game gathering gradient; outcome-only can't differentiate
  a gatherer from a wanderer inside a won game.
- Correction: kills don't score either (HILL_POINTS pays the hill
  razer, not ant kills) — score is hills only. But kill-farming
  self-terminates in victory (extermination rule) while food
  farming self-sustains in draws; food restored first, kill
  question queued.
- Next: revert the FOOD deletion (round 8), keep everything else.
