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
