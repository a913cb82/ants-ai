# Run: lineage accumulation sample (round 15) — PLAN

Round 14 proved the mechanics (chains, no rot) but 10 main gens
cannot show compounding. This round changes nothing: same pool,
same code, longer sample for the slow effect.

- Hypothesis: the continuous main's returns/wr trend up over a
  25-gen window (rounds 14-15); reset-regime could not compound.
- Config: identical to round 14 (8 boards, lineage + teeth live,
  evals on train). No new variable by design.
- Success criteria: main-gen wr trend positive across the round;
  another promotion (any role); chains deepen past 25.
- Failure criteria: main wr flat-or-falling across 25 gens with
  no promotion -> accumulation falsified; move to symmetrization
  (next variable) and treat lineage as neutral plumbing.
- Results (g232-g246): THREE PROMOTIONS — g236 over g222 (0.675,
  main), g245 over g236 (0.65, main), g246 over g245 (0.70,
  EXPLOITER takes the crown — second exploiter champ). Champ
  g222 -> g246. Main wr trend UP (.42-.60 -> .50-.65, ends .65);
  first-5 main mean 0.505 vs last-5 0.615. Chains depth 33/34.
- Verdict: accumulation CONFIRMED. Lineage joins teeth as live
  infrastructure. Next variable: symmetrization (round 16).
