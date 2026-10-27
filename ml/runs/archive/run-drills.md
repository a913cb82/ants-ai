# Run: drill reservation + pg logging (round 21) — PLAN

Apparatus round, no behavior change. Round 20 taught two things:
keep DEATH -2 (no collapse), and the logging gaps hurt verdicts
(no elim flags, no |pg|, v start/final hand-compared).

- Drill reservation (rung-3 prerequisite): archive/next_drill_maps
  tracks last-trained gen per board in drills.json; each gen trains
  the least-recently-seen boards. Degenerates to exact round-robin
  on the current 8-board pool (verified by test). When rung 3
  lands (148 maps), coverage is guaranteed by construction instead
  of hoped-for by rotation.
- pg_abs logging: mean |per-row pg| per epoch into history, so the
  flat-gradient diagnosis uses magnitudes, not signed means.
  (v start-vs-final already exists as v_loss[0] vs v_loss[-1].)
- Config identical to rounds 19-20 (DEATH -2, kl 0.01, 8 boards):
  data keeps accumulating while the prerequisite gets built.
- Success criteria: drills.json sweeps all 8 boards every 2 gens in
  the wild; >= 0 promotions (no bar — apparatus round, but a promo
  still counts as usual).
- Results: pending.
- Verdict: pending.
