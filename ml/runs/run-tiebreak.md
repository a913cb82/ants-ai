# Run: draw tiebreak by material (round 11 revised) — PLAN

Revised mid-plan: generated rung 3 deleted (wrong direction — rung
3 is real boards; pond and gap both had dry toroidal routes).
Pool is now rung-2-extended, tiebreak unchanged as the variable.

- Hypothesis: paying the material edge in drawn games (+1.0 more
  ants alive, -1.0 fewer, 0 equal; draw-only, binary, undecayed)
  un-duds big peaceful boards — gathering becomes a contest with
  a gradient, without reopening the farming trap (comparative, so
  mirror peace still pays 0).
- Config: 7-board pool (rung1_open + rung2a/b/c/d + gen2p_00 +
  gen2p_05 — smallest real boards ~1600 tiles), all train
  (no split, evals on train). Gap fixed with edge twin (battles on
  the dry latitude); pond twin lakes; 2d back to 4x4 texture lakes
  (variety, not funnels, per review). Turns 150, temp 2.0.
  Tiebreak is the single experimental variable; pool fixes are
  prerequisite, not variables.
- Smoke pre-check (BC vs random, 150t): gap-v2 decisive (3-0,
  13 turns); gap-v3 twin-bars drew (correct-by-construction — no
dry route except the band; asymmetric smoke understates mirror
contact). gen2p boards both draw — passengers under test
(the round judges them: decisive or material-margin, else cut).
- Success criteria: tiebreak mass separates peaceful-board games
  (material margins nonzero); >= 1 promotion; rung-1 retention
  holds (peace falls from round-10 0.68 now that it trains);
  real-board verdict (keep or cut each).
- Failure criteria: real boards zero-decisive AND zero-margin ->
  cut them (rung 2 stays curriculum); tiebreak with no promotions
  and no margin separation -> drop it.
- Results: pending.
- Verdict: pending.
