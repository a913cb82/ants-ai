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

## Iter 18: duel-count ablation (8p + 6 duels)
- Census + 8p (7 rulers) at 1.0 + 6 closest duels.
- Score: corr 0.9900, exact tie with champion (-0.00004).
- Verdict: DISCARD (tie keeps incumbent). The 7-duel count stands; size carries nothing either way.
- Misses: 1.

## Iter 19: refine width 1.25 under duel tail
- Census + 6p at 1.25 tertile + 7 closest duels.
- Score: corr 0.9900, second consecutive exact tie (-0.00004).
- Verdict: DISCARD (tie keeps incumbent). The 6p refine width carries nothing under a duel tail.
- Misses: 2. BOLD 6 due.

## Iter 20 (bold 6): census + 10-duel tail, no refine
- Census opener + 10 closest-mu duels, no mid refine.
- Score: corr 0.9846 (-0.0055, all 5 regress).
- Verdict: DISCARD. Bold 6 judged: refuted. The 6p refine matters; duels alone cannot finish.
- Misses: 3.

## Iter 21: 4p refine + 8-duel tail
- Census + 4p (3 rulers) at 1.0 + 8 closest duels.
- Score: corr 0.9872 (-0.0029).
- Verdict: DISCARD. The 6p/7-duel split is confirmed from both sides (8p/6d ties, 4p/8d and 0p/10d lose).
- Misses: 4.

## Iter 22: duel rank rotation in the tail
- Census + 6p at 1.0 + 7 duels at d-th nearest (d = duel index).
- Score: corr 0.9900, tie (-0.0001).
- Verdict: DISCARD (tie keeps incumbent). Forced rotation adds nothing; live-mu re-aim already varies opponents.
- Misses: 5.

## Iter 23 (bold 7): interleave census + 3d + 6p + 4d
- 3 positioning duels between census and refine, 4-duel tail.
- Score: corr 0.9871 (-0.003).
- Verdict: DISCARD. Bold 7 judged: refuted. Mid re-positioning wastes slots; the refine wants the post-census posterior directly.
- Misses: 6.

## Iter 24: likely-ruler hard-50 refine
- Census + 6p at 1.0 from 50 lowest-sigma of last-400 + 7 duels.
- Score: corr 0.9894 (-0.0007, 4/5 regress).
- Verdict: DISCARD. Tertile breadth beats the hard screen; marginal rulers still teach.
- Misses: 7.

## Iter 25: senior-25 refine
- Census + 6p at 1.0 from tertile-minus-25 + 7 duels.
- Score: corr 0.9894 (-0.0007, 4/5 regress).
- Verdict: DISCARD. Same loss as hard-50; fresh-ruler quarantine loses twice. Recency direction stands.
- Misses: 8.

## Iter 26 (bold 8): double refine + 5-duel tail
- Census + 6p at 1.0 + 4p at 1.0 + 5 closest duels.
- Score: corr 0.9893 (-0.0008).
- Verdict: DISCARD. Bold 8 judged: refuted. Tail length beats refine depth; 2 extra duels out-teach a second small refine.
- Misses: 9.

## Iter 27: comp-pick refine
- Census + 5 nearest tertile rulers (no grid) + 7 duels.
- Score: corr 0.9902 (+0.0001, exact tie).
- Verdict: DISCARD (tie keeps incumbent). Quantile grids and comp-picks are equivalent targeting; density adapts either way.
- Misses: 10.

## Iter 28: BF prior-weighted refine
- Census + 6p split-center (3 census-centroid + 2 live-mu at 1.0) + 7 duels.
- Selection: corr 0.9906 (+0.0006, 3/5 improve).
- Held-out 5-9: 0.99026 vs 0.99050 (-0.0002). Pooled-10 +0.0002 but fresh disagrees.
- Verdict: DISCARD per overturn rule. The posterior needs no reserve; G2 personalization is not chasing noise.
- Misses: 11.

## Iter 29 (bold 9): census rematch + 5-duel tail
- Census opener repeated verbatim (replicate), then 5 closest duels.
- Score: corr 0.9863 (-0.0037).
- Verdict: DISCARD. Bold 9 judged: refuted. Replicate-averaging loses to personalization; the refine's fresh thresholds matter.
- Misses: 12.

## Iter 30: info-targeted tail duels — CHAMPION
- Census + 6p at 1.0 tertile + 7 tail duels by argmax predict_draw+0.02s over 40 nearest.
- Selection: corr 0.9904 (+0.0003, 3/5). Held-out 5-9: 0.9910 (+0.0005). Fresh 10-14: 0.9919. Pooled-15: 0.9911.
- Verdict: ADOPT. Info targeting helps positioned tails; it hurt openers (iter 10) but sharpens finishers.
- Misses reset to 0.

## Iter 31: pure-draw tail (sigma weight 0)
- Champion shape with predict_draw-only tail targeting.
- Score: corr 0.9896 (-0.0009).
- Verdict: DISCARD. The 0.02 sigma weight carries signal; pure closeness under-targets uncertainty in tails.
- Misses: 1.

## Iter 32: sigma weight 0.05 in tail
- Champion shape with 0.05 uncertainty weight in tail targeting.
- Score: corr 0.9903, tie (-0.0001).
- Verdict: DISCARD (tie keeps incumbent). Weight 0.02 stands; 0 loses (iter 31), 0.05 ties.
- Misses: 2.

## Iter 33: tail prefilter 80
- Champion shape with info-duel candidate set 80 instead of 40.
- Score: corr 0.9904, exact tie to 5 decimals.
- Verdict: DISCARD. Prefilter breadth carries nothing; the argmax rarely lives past 40.
- Misses: 3.

## Iter 34: quantile-census opener — CHAMPION
- Pool-mu-decile opener (mass not range) + 6p at 1.0 tertile + 7 info tail duels.
- Selection: corr 0.9930 (+0.0026, all 5 improve). Held-out 5-9: 0.9932 (+0.0022). Fresh 10-14: 0.9935. Pooled-15: 0.9932.
- Verdict: ADOPT. Mass-weighted skeleton beats range skeleton under a duel tail: pins where bots live position better for positioned finishers.
- Misses reset to 0.

## Iter 35: sinh-warped census
- Sinh-warped opener + champion rest.
- Score: corr 0.9901 (-0.0029).
- Verdict: DISCARD. Deciles stand; smooth tail resolution buys nothing over mass spacing.
- Misses: 1.

## Iter 36: comp-pick refine under quantile regime
- Quantile opener + 5 nearest tertile rulers + info tail.
- Score: corr 0.9931 (+0.0001, exact tie).
- Verdict: DISCARD (tie keeps incumbent). Grid vs comp equivalence holds under quantile regime too.
- Misses: 2.

## Iter 37 (bold 10): skeleton-second under duel tail
- 6p refine from the prior + quantile census + 7 info duels.
- Score: corr 0.9855 (-0.0075).
- Verdict: DISCARD. Bold 10 judged: refuted. Early skeleton timing stands under duel tails too.
- Misses: 3.

## Iter 38: census-panel refine
- Quantile opener + (2 census recaptures + fresh at 1.0) + info tail.
- Score: corr 0.9927 (-0.0002, 4/5 regress).
- Verdict: DISCARD. Recaptures add nothing; fresh thresholds win every time.
- Misses: 4.
