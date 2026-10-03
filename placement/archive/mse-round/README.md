# Archive: MSE round (2026-10-03/04)

Goal was mean `(mu minus mu_true)^2` over 1000 bots, seeds 0-4.
200 iterations, branch `placement/main`, full history in git.

- Champion: iteration 133, selection mean 197.7410 over seeds 0-4
  (148.5257, 223.5037, 319.8536, 125.7155, 171.1066).
- Champion shape: pool-range census opener (9 sites, full pool,
  bot-independent), then spread 10p at `N(mu, 1.25 sigma)`, then
  spread 10p at `N(mu, 1.875 sigma)`, refines drawn from the
  low-sigma tertile of the last 400 arrivals.
- Baseline (MSE start): 323.1547. Improvement: 39%.
- Held-out check (seeds 5-9): champion 177.2165.
  Fresh audit (seeds 10-14): champion 158.5081, pooled-15 177.8219.
- Later validation work (harness comparison, seeds 0-5, faithful
  30-slot shapes): the champion exam with mu scoring reaches
  corr(mu, true) 0.9654, the starting baseline of the corr round.
- `strategy.py` here is the champion. `evaluate.py` scores MSE.
- `PROGRESS.jsonl`, `WORKLOG.md`, `IDEAS.md`, `STRATEGY.md`,
  `PROGRAM.md`, `AGENTS.md` are the round record.
