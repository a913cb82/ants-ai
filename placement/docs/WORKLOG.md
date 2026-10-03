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

## Iter 3: highest-sigma-seeded refines (mixed exam)
- Census opener; G2/G3 first pick = highest-sigma tertile ruler, rest quantile fills.
- Selection: corr 0.9874 (+0.0004 over baseline, 4/5 seeds improve).
- Held-out seeds 5-9: iter3 0.98836 vs baseline 0.98868 (-0.0003). Pooled-10 ties +0.00005.
- Verdict: DISCARD per overturn rule (pooled+fresh disagree). Main-branch seed rule does not transfer.
- Seeds 5-9 baselines recorded: 0.9898, 0.9843, 0.9908, 0.9885, 0.9900.
- Misses: 2. BOLD LINE 1 due.

## Iter 4 (bold 1): drunk-witness high-sigma-tertile closer
- Census + 1.25 tertile + 1.875 high-sigma-tertile G3.
- Score: corr 0.9870 (0.9864, 0.9845, 0.9829, 0.9914, 0.9897). Baseline 0.9870.
- Verdict: DISCARD. Dead tie on mean with seed variance up = the predicted pure-noise signature. Full high-sigma-anchor axis closed; 7+2 dose row stays open (smaller claim).
- Bold 1 judged: refuted. Misses: 3.

## Iter 5: Fisher-peak narrow valley 1.0/1.5
- Census + 1.0 tertile + 1.5 tertile.
- Score: corr 0.9860 (-0.0010, only seed 4 improves).
- Verdict: DISCARD per row falsification. The MSE valley widths are not tail-weight overhead; reach separates ranks too.
- Misses: 4.
