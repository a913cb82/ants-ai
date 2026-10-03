# Research

Write notes from the web and from the repo. Give the source for each
note. Start a bold iteration here, not in the code.

Use this format.

```
## <topic> (<date>)
- source: <url or repo path>
- claim: <one sentence>
- evidence: <what the source shows>
- idea: <what it suggests for the bot>
```

## Log

## Census-tertile selection (2026-10-04)
- source: placement round iters 126-200, champion iter 133
- claim: the MSE-optimal opponent policy is wrong for the lb loop.
- evidence: synthetic validation (200 bots, seeds 0-2, real selection
  code both sides) gives census-tertile rating MSE 551 vs info-score
  679, but mean budget-end lb 5.72 vs 9.76 and rank correlation 0.940
  vs 0.957, all seeds. Package retest (each exam with its native
  score): corr(mu,true) is 0.949 new vs 0.965 old, corr(lb,true) is
  0.946 new vs 0.959 old. The score change helps both exams a little;
  the exam gap dominates. Info-score collapses sigma faster, and lb
  punishes sigma threefold.
- idea: keep info-score selection. Do not port MSE policies without
  validating on lb and rank correlation first.

## Census-tertile harness (2026-10-04)
- source: placement round champion iter 133; validation scripts
  /tmp/validate_harness.py (faithful 30-slot shapes, seeds 0-5)
- claim: the 3x10p census-tertile exam with mu scoring ranks bots
  truer than the duel+FFA info-score exam with lb scoring.
- evidence: corr(recorded score, true skill) is 0.964 new vs 0.962
  old across 6 seeds; new wins 5 of 6 (loses seed 3 only). Full 2x2:
  corr(mu) is 0.9654 new vs 0.9655 old (exam tie), corr(lb) is
  0.9632 new vs 0.9619 old. Sigma-discount ladder (means): old
  0.9655/0.9650/0.9638/0.9619, new 0.9654/0.9655/0.9648/0.9632
  for k=0/1/2/3. Every discount step costs ranking; mu and mu-1s
  tie best, so the shipped mu stands.
- idea: shipped as the harness. Old-budget rows stay filed under
  their tag and no longer count for champion.
