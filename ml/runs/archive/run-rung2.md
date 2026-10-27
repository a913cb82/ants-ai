# Run: rung-2 graduation (round 9) — IN PROGRESS (results filled)

- Hypothesis: promoters on tiny-symmetry transfer to scouting +
  water routing; the 4-map pool teaches without stalling.
- Config: rung2a open / rung2b pond / rung2c gap / rung2d lakes
  (16x24-20x28, hills beyond sight, all 180-symmetric), same
  rewards + rotation; turns 150, temp 2.0. MID-ROUND FIX: rung2b
  single lake -> twin lakes (edge pond blocks the wrap route);
  early pond games ran on the flawed map — pond-specific
  conclusions carry a seam, round verdict rests on all four maps.
- Success criteria: >= 1 promotion; no map provably dud
  (all-draw on one map across the round).
- Results (g133-g147): 3 PROMOTIONS — g134 (0.725), g137 (0.65),
  g146 (0.65). Champion g132 -> g146. Peace per block 16/40,
  20/40, 10/40 (block 3 quietest but still decisive every gen;
  min 1/8 train-decisive, so no map provably dud — though
  per-map attribution isn't logged, see below). Train ret mixed
  (-0.9..+2.6), |pg| still tiny (0.0002-0.01) while behavior
  promotes. v drops within every gen (critic tracks each gen).
- Verdict: CONFIRMED. 3/15 clears the 2-in-10 bar -> graduate to
  rung 3. Watch item: block-3 peace dip (10/40) — noise or early
  rung-2 mastery / one-map peace? Needs per-map logging.
- Gaps found: train/eval replays don't record WHICH map produced
  them (slot->map mapping unlogged). Before rung 3 (14 maps),
  log the map per game — else dud maps hide in aggregates.
- Next: rung 3 (round 10) + per-map game logging.
