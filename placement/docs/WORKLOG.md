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

## Iter 6: equating spine (common-item link)
- Census + (3 spine + 6 even-tertile at 1.25) + (3 spine + 6 odd-tertile at 1.875).
- Score: corr 0.9854 (-0.0017, all 5 seeds regress).
- Verdict: DISCARD. The 3-slot form-link tax buys nothing; greedy personalization beats shared anchors.
- Misses: 5.

## Iter 7: split-vintage witnesses
- Census + 1.25 old-half tertile + 1.875 fresh-half tertile.
- Score: corr 0.9861 (-0.0009, only seed 3 improves).
- Verdict: DISCARD. Era-splitting starves both games of the best rulers; recency wants all 400 together.
- Misses: 6.

## Iter 8: credibility 7+2 blend closer
- Census + 1.25 tertile + 1.875 (7 tertile + 2 high-sigma-half).
- Selection: corr 0.9878 (+0.0008; seed3 +0.0044, seed2 -0.0017).
- Held-out 5-9: iter8 0.98844 vs baseline 0.98868 (-0.0002). Pooled-10 +0.0003 but fresh disagrees.
- Verdict: DISCARD per overturn rule. No dose escalation (fresh half must improve; it did not).
- Misses: 7.

## Iter 9 (bold 2): elite separator game-2
- Census + top-decile 9-ruler game + 1.875 closer.
- Score: corr 0.9784 (-0.0086, every seed regressed, seed 2 -0.0167).
- Verdict: DISCARD. Bold 2 judged: refuted with the classic one-sided signature. Separator family closed including weak S2 (no run).
- Misses: 8.

## Iter 10: full old-exam port (5 info duels + 4/6/10 propose FFAs)
- Faithful port: argmax predict_draw+0.02s duels, seed-bot greedy info FFA fields, deterministic top-1.
- Score: corr 0.9617 (-0.025, every seed regressed).
- Verdict: DISCARD. The old exam's league-harness ranking power (0.9655) does not live in the 30-slot shape; it needs the longitudinal pool structure. Component rows stay as priced (iters 2/3).
- Misses: 9.

## Iter 11 (bold 3): MAE-champion verbatim revival
- 5 closest-mu duels + 1.0/0.5 tertile 10ps.
- Score: corr 0.9644 (-0.0226, every seed regressed).
- Verdict: DISCARD. Bold 3 judged: refuted. Duel openers dead under corr in all three targeting flavors (high-sigma, info-score, closest). Family closed.
- Misses: 10.

## Iter 12: lone alibi pin closer
- Census + 1.25 tertile + (8 at 1.875 + farthest established ruler).
- Selection: corr 0.9870, exact mean tie (3/5 seeds improve).
- Held-out 5-9: 0.98804 vs 0.98868 (-0.0006). Pooled-10 loses.
- Verdict: DISCARD. The pin is pure noise; one-pin axis closed.
- Misses: 11.

## Iter 13: bad-cop/good-cop anchors at flat 1.5
- Census + full-pool 1.5 + tertile 1.5.
- Score: corr 0.9855 (-0.0015, seed 2 -0.0084).
- Verdict: DISCARD. Anchor order carries no signal; full-pool mid-game poisons hard seeds.
- Misses: 12.

## Iter 14 (bold 4): Approach-2 zooming bracket
- Personal 1.6 10p (NO census) + 5p/5p at 1.0 + 5 closest duels.
- Score: corr 0.8909 (-0.096, seed 2 0.8145).
- Verdict: DISCARD. Bold 4 judged: refuted catastrophically. The census opener is load-bearing under corr too; a personal spread cannot bind from the prior. Approach-2-as-written closed.
- Misses: 13.

## Iter 15: twin-narrow 1.25/1.25 parallel forms
- Census + 1.25 even-tertile + 1.25 odd-tertile (disjoint).
- Score: corr 0.9820 (-0.005, seed 3 -0.0148).
- Verdict: DISCARD. The 1.875 closer's reach is not MSE overhead; tails need binding for rank order too. Valley dip stands.
- Misses: 14.

## Iter 16: deferred propose-commit 1.5/1.875
- Census + 1.5 tertile + 1.875 tertile.
- Selection: corr 0.9872 (+0.0002, 3/5 improve).
- Held-out 5-9: 0.98842 vs 0.98868 (-0.0003). Pooled-10 loses by 0.00004.
- Verdict: DISCARD. Near-neighbor noise; game-2 1.25 wall stands.
- Misses: 15.

## Iter 17 (bold 5): census + 6p refine + 7-duel tail — CHAMPION
- Census opener + 6p (5 rulers) at 1.0 tertile + 7 closest-mu duels.
- Selection: corr 0.9901 (+0.0031, 4/5 improve). Held-out 5-9: 0.9905 (+0.0018). Fresh 10-14: 0.9915. Pooled-15: 0.9907.
- Verdict: ADOPT. Duel tails rank after positioning; duel openers stay dead. The 6p refine + terminal matched duels collapse sigma where corr lives.
- Bold 5 judged: confirmed. Misses reset to 0.
