# Worklog (corr round)

## Setup (2026-10-04)
- Archived the MSE round to `placement/archive/mse-round/` (champion iter 133, sel 197.7410).
- New metric: corr(recorded mu, mu_true) over 1000 bots, seeds 0-4. Higher wins.
- Baseline is the MSE-champion shape, unchanged in `strategy.py`. Iteration 1 measures its corr.
- Rules carried over: confirmation on seeds 5-9 for thin margins; pooled + fresh must agree.

## Iter 1: baseline corr of MSE-champion shape
- Score: corr 0.9870 (0.9876, 0.9869, 0.9857, 0.9867, 0.9882) over seeds 0-4.
- Strategy unchanged from archive. First corr row sets the bar.
- Next: uncertainty-hunting opener (backlog row 2).
