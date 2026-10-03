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

## Iter 2: uncertainty-hunting opener (info-score flavor)
- 5 closest high-sigma-half duels, then 1.25/1.875 tertile 10ps.
- Score: corr 0.9557 (0.9544, 0.9539, 0.9526, 0.9774, 0.9403). Baseline 0.9870.
- Verdict: DISCARD. Every seed regressed; duels cost ranking power just as they cost MSE.
- Strategy reverted to baseline. Misses: 1.
