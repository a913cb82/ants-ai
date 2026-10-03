# Archive: MAE round (2026-10-03)

Goal was mean `abs(mu minus mu_true)` over 1000 bots, seeds 0-4.
44 iterations, branch `placement/main`, full history in git.

- Champion: iteration 25, mean 14.8370 over seeds 0-4
  (13.7425, 16.1204, 16.3392, 13.0445, 14.9386).
- Champion shape: 5 closest-`mu` duels, then spread 10p at
  `N(mu, 1.0 sigma)`, then spread 10p at `N(mu, 0.5 sigma)`,
  FFA opponents from the low-`sigma` tertile.
- Baseline (closest-mu duels): 28.9678. Improvement: 49%.
- `strategy.py` here is the champion. `evaluate.py` scores MAE.
- `PROGRESS.jsonl` (45 rows incl. baseline), `WORKLOG.md`,
  `IDEAS.md`, `STRATEGY.md`, `PROGRAM.md`, `AGENTS.md` are the
  round record. Held-out check (seeds 5-9): champion 14.39 vs
  closest rival 15.07, no overfit.
