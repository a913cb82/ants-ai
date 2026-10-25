# Run: draw tiebreak by material (round 11) — PLAN

- Hypothesis: paying the material edge in drawn games (+1.0 more
  ants alive, -1.0 fewer, 0 equal; draw-only, binary, undecayed)
  un-duds big peaceful boards — gathering becomes a contest with
  a gradient, without reopening the farming trap (comparative, so
  mirror peace still pays 0).
- Config: 9-board pool (rung 1 + rung2a-d + rung3a-d generated
  mid-boards 960-1664 tiles), all train (no split under 13 maps,
  evals on train = rounds-1-9 behavior). Turns 150, temp 2.0.
  Tiebreak is the single experimental variable; pool rebuild and
  eval-restore are fixes/prerequisites, not variables.
- Smoke pre-check (BC vs random, 150t): rung3a decisive (3-0,
  28 turns); rung3b/c/d all draw 1-1 by turn limit. Asymmetric
  smoke understates mirror contact (two seekers meet faster than
  hunter-vs-wanderer), and tiebreaks give draws signal now — so
  the boards run, and the per-map table judges them.
- Success criteria: rung3b-d show material margins (nonzero
  tiebreak mass) or decisive games within 15 gens; >= 1 promotion;
  rung-1 retention holds (peace stays low where it trains).
- Failure criteria: rung3b-d zero-decisive AND zero-margin ->
  shrink rung 3 (700-1000 tiles); tiebreak with no promotions and
  no margin separation -> drop it (draws stay 0).
- Results: pending.
- Verdict: pending.
