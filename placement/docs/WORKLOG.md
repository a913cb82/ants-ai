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

## Iter 39: 8p refine + 6 info duels
- Quantile opener + 8p (7 rulers) at 1.0 + 6 info duels.
- Score: corr 0.9919 (-0.0011).
- Verdict: DISCARD. The 7-duel count stands under quantile regime too.
- Misses: 5.

## Iter 40 (bold 11): slim 7-site skeleton + 8p refine
- 8p quantile skeleton + 8p (7 rulers) at 1.0 + 7 info duels.
- Score: corr 0.9909 (-0.0021).
- Verdict: DISCARD. Bold 11 judged: refuted. Nine skeleton looks are load-bearing even mass-spaced.
- Misses: 6.

## Iter 41: colour-balance refine
- Quantile opener + side-constrained 1.0 refine + info tail.
- Score: corr 0.9929 (-0.0001, exact tie).
- Verdict: DISCARD (tie keeps incumbent). Greedy snap already balances sides; forced alternation displaces nothing and gains nothing.
- Misses: 7.

## Iter 42: micro-dithered refine
- Quantile opener + +-0.15 sigma jittered 1.0 refine + info tail.
- Score: corr 0.9929 (-0.0001, exact tie).
- Verdict: DISCARD (tie keeps incumbent). Sub-threshold jitter moves no snaps that matter; tie entropy is not the lever.
- Misses: 8.

## Iter 43: proportional-strata refine — CHAMPION
- Quantile opener + 5 rulers across below/peer/above bins by pool mass (min 1 each) + 7 info tail duels.
- Selection: corr 0.9932 (+0.0002, 3/5). Held-out 5-9: 0.9939 (+0.0007). Fresh 10-14: 0.9939. Pooled-15: 0.9937.
- Verdict: ADOPT. Spending refine looks where the voters are beats the Gaussian grid; forced 3-3-3 stays dead but proportional quota wins.
- Misses reset to 0.

## Iter 44: strata bins at +-1.5 sigma
- Champion shape with wider peer bin.
- Score: corr 0.9931 (-0.0001, exact tie).
- Verdict: DISCARD (tie keeps incumbent). Bin width carries nothing; mass already concentrates in the peer bin.
- Misses: 1.

## Iter 45: pure proportional strata (no floor)
- Champion shape with min-1-per-bin removed.
- Score: corr 0.9930 (-0.0001, exact tie).
- Verdict: DISCARD (tie keeps incumbent). The floor costs nothing and buys tail insurance; keep it.
- Misses: 2.

## Iter 46 (bold 12): 8p strata refine + 6 info duels
- Quantile opener + 8p (7 rulers) proportional strata + 6 info duels.
- Score: corr 0.9929 (-0.0003).
- Verdict: DISCARD. Bold 12 judged: refuted. Five strata rulers plus 7 duels is the shape; extra refine rulers cost tail length.
- Misses: 3.

## Iter 47: bell-projection census
- Bell-decile opener + champion rest.
- Score: corr 0.9898 (-0.0034).
- Verdict: DISCARD. Empirical pool deciles beat parametric bell deciles; the pool is not Gaussian.
- Misses: 4.

## Iter 48: calibration-anchored opener
- Range sites snapped to tertile-only rulers + champion rest.
- Score: corr 0.9921 (-0.0011).
- Verdict: DISCARD. The opener needs the wild pool; calibrated-only sites starve tail pins.
- Misses: 5.

## Iter 49: full-pool grid refine (one-shot retest)
- Quantile opener + full-pool 1.0 grid refine + info tail.
- Score: corr 0.9924 (-0.0008).
- Verdict: DISCARD. Calibrated rulers matter in the refine under every regime; one-shot row spent.
- Misses: 6.

## Iter 50: range census + strata + info (control, halfway)
- Range-skeleton opener + strata refine + info tail.
- Score: corr 0.9924 (-0.0008).
- Verdict: DISCARD. Quantile opener stands with the new rest; mass beats range in both regimes.
- Halfway: 50/100. Champion iter 43 (pooled-15 0.9937).
- Misses: 7.

## Iter 51 (bold 13): quantile skeleton + 10 info duels, no refine
- No mid refine; 10-duel info tail.
- Score: corr 0.9911 (-0.0021).
- Verdict: DISCARD. Bold 13 judged: refuted. The strata refine matters under info tails too.
- Misses: 8.

## Iter 52: slim 7-site skeleton + 5-strata + 8 duels
- 8p quantile skeleton + 6p strata + 8 info duels.
- Score: corr 0.9897 (-0.0034).
- Verdict: DISCARD. Extra tail cannot pay for lost skeleton density; 9 opener looks irreplaceable.
- Misses: 9.

## Iter 53: above/below alternating tail duels
- Champion shape with side-forced (above/below) tail targeting.
- Score: corr 0.9932 (+0.0001, exact tie).
- Verdict: DISCARD (tie keeps incumbent). Info targeting already balances sides; forcing adds nothing.
- Misses: 10.

## Iter 54: 4p strata + 8 info duels
- Quantile opener + 4p (3 rulers) strata + 8 info duels.
- Score: corr 0.9926 (-0.0006).
- Verdict: DISCARD. The 6p/7-duel split re-confirmed under strata targeting.
- Misses: 11. Second brainstorm wave launched (miser/taxonomist/locksmith/physicist/jeweler/bookkeeper).

## Iter 55: quota-split refine (bookkeeper D4)
- 3 census-center + 2 live-mu targets through strata quota + info tail.
- Score: corr 0.9924 (-0.0008).
- Verdict: DISCARD. The prior reserve buys nothing even quota-constrained; split-center family closed for good.
- Misses: 12.

## Iter 56 (bold 15): 3-stage depth
- Quantile + 6p strata + 4p strata + 5 info duels.
- Score: corr 0.9932 (+0.0000, exact tie).
- Verdict: DISCARD (tie keeps incumbent). Bold 15 judged: refuted as gain, priced as trade — the mid layer costs exactly what 2 duels buy. Depth closed at 30 slots.
- Misses: 13.

## Iter 57: peer-pinned skeleton (bookkeeper D1)
- 8 deciles + nearest-tertile pin + champion rest.
- Score: corr 0.9913 (-0.0019).
- Verdict: DISCARD. The top-decile pin binds extremes; trading it for a peer pin loses. Skeleton-pin family closed.
- Misses: 14.

## Iter 58: narrow-peer strata +-0.5 sigma
- Champion shape with tight peer bin.
- Score: corr 0.9931 (-0.0001, exact tie).
- Verdict: DISCARD (tie keeps incumbent). Bin edge width is a free parameter from 0.5 to 1.5; quota does the work.
- Misses: 15.

## Iter 59 (bold 16): refine-heavy 10+10+10
- Quantile + 9-ruler strata + 5 info duels.
- Score: corr 0.9882 (-0.005).
- Verdict: DISCARD. Bold 16 judged: refuted. Nine refine rulers cannot buy back 2 lost duels; the tail-length wall holds. Split frontier closed: 10+6+14 priced optimum.
- Misses: 16.

## Iter 60: tail weight descent 0.05/0.02/0
- Champion shape with per-duel weight schedule.
- Score: corr 0.9932 (-0.0000, exact tie).
- Verdict: DISCARD (tie keeps incumbent). Per-duel weight schedules closed; flat 0.02 stands.
- Misses: 17.

## Iter 61: 6 info + closest closer
- 6 info duels + closest-mu closing duel.
- Score: corr 0.9932 (+0.0000, exact tie).
- Verdict: DISCARD (tie keeps incumbent). Explore-then-pin phases tie flat info; no 5+2 escalation.
- Misses: 18.

## Iter 62: 6 info + credible-pin closer
- 6 info duels + lowest-sigma-of-10-nearest closer.
- Score: corr 0.9933 (+0.0001, exact tie).
- Verdict: DISCARD (tie keeps incumbent). J3 and J4 both tie: proximity and credibility coincide too often to matter. Closing-specialist family closed; flat info stands.
- Misses: 19.

## Iter 63 (bold 17): 4-stage micro-layers
- Quantile + three 4p strata + 4 info duels.
- Score: corr 0.9931 (-0.0001, exact tie, expected kill missed).
- Verdict: DISCARD (tie keeps incumbent). Bold 17 judged: refuted as kill, priced as trade. 2/3/4 stages all tie: meso granularity is free, the refine's existence is load-bearing. Depth closed for good.
- Misses: 20.

## Iter 64: 4-bin signed-peer strata
- Champion shape with peer bin split by sign.
- Selection: corr 0.9934 (+0.0002, 4/5). Held-out 5-9: tie.
- Verdict: DISCARD per row falsification: drop-best-seed kills the lead (flex-tax noise). 3 bins stand.
- Misses: 21.

## Iter 65: mass-anchored strata edges
- Pool-tertile bins with mass quota + champion rest.
- Score: corr 0.9921 (-0.0010).
- Verdict: DISCARD. Bot-centered sigma edges beat pool-mass edges in the refine; the iter-34 lesson does not extend inward.
- Misses: 22.

## Iter 66: 8+6+16 (bold 18) — DUPLICATE
- Staging identical to iter 52 bit-for-bit; results identical (0.9897).
- Verdict: stillborn duplicate, no information. MIS S3 stands answered by iter 52. Bold 18 unspent.
- Misses: 23.

## Iter 67: winsorized-range opener
- Uniform sites over [p10, p90] + champion rest.
- Score: corr 0.9844 (-0.0088, all regress).
- Verdict: DISCARD. Mass beats evenness everywhere; the outlier sites were binding value, not tax.
- Misses: 24.

## Iter 68: recent-400 decile opener
- Decile sites from last-400 mus, full-pool snap + champion rest.
- Score: corr 0.9932 (+0.0000, exact tie).
- Verdict: DISCARD (tie keeps incumbent). Live-window mass ties full-history mass; fossil mus warp nothing.
- Misses: 25.

## Iter 69 (bold 19): heavy-middle quantile opener
- Shaped sites 12..88 + champion rest.
- Score: corr 0.9931 (-0.0000, exact tie).
- Verdict: DISCARD (tie keeps incumbent). Uniform mass stands over shaped placement; shaping buys nothing.
- Misses: 26.

## Iter 70: calibrated-snap deciles
- Same decile sites, lowest-sigma snap within 0.15 mu.
- Score: corr 0.9933 (+0.0001, exact tie).
- Verdict: DISCARD (tie keeps incumbent). Ruler quality on near-ties buys nothing; snap axis closed, pure nearest-mu stands.
- Misses: 27.

## Iter 71: asymmetric strata -1.25/+0.75
- Down-shifted peer bin + champion rest.
- Score: corr 0.9933 (+0.0001, uniform tie).
- Verdict: DISCARD (tie keeps incumbent). Symmetry stands; direction axis closed, no mirror run.
- Misses: 28.

## Iter 72: 2-bin median-split strata
- Below/above halves with mass quota + champion rest.
- Score: corr 0.9932 (+0.0000, exact tie).
- Verdict: DISCARD (tie keeps incumbent). Bin edges are free parameters; 3-bin stands on peer insurance, not edge signal.
- Misses: 29.

## Iter 73 (bold 20): sandwich with 4p closer
- Quantile + 4p strata + 6 info duels + 4p strata closer.
- Score: corr 0.9925 (-0.0007).
- Verdict: DISCARD. Bold 20 judged: refuted. A closing refine cannot beat the 7th duel; terminal duels finish best.
- Misses: 30.

## Iter 74: rebind refine (bookkeeper D2)
- 1 nearest played site + 4 fresh strata + info tail.
- Score: corr 0.9932 (+0.0001, exact tie).
- Verdict: DISCARD (tie keeps incumbent). Scale-link buys nothing; rebind family closed.
- Misses: 31. Wave-3 brainstorm (blacksmith/midwife/glazier/shepherd/auditor) in flight.

## Iter 75: info-inside-strata refine (blacksmith F1)
- Mass quota bins, info-scored within-bin picks + champion rest.
- Score: corr 0.9931 (-0.0001, exact tie).
- Verdict: DISCARD (tie keeps incumbent). Mass quota does the work; within-bin pick rule is free.
- Misses: 32.

## Iter 76: front-loaded upset duels (glazier G4 variant)
- First 3 tail duels info-argmax over above-mu rulers only; last 4 flat info.
- Score: sel corr 0.9934 (+0.0002, 4/5 seeds) escalated to held seeds 5-9.
- Held: exp 0.9938 vs champion 0.9939 (champion wins 4/5, +0.0002). Pooled-10 exact tie.
- Verdict: DISCARD (overturn rule: fresh disagrees with selection). Front-loaded upsets add nothing; sequencing/instrument axis closed.
- Misses: 33.

## Iter 77: terminal bounty duel (shepherd S1)
- Duel 7 = max-sigma peer-banded last-400 ruler; 6 info duels + champion rest.
- Score: corr 0.9932 (+0.0000, exact tie).
- Verdict: DISCARD (tie keeps incumbent). Pool-rent invisible at 1-slot dose; S2/S4 parked per stop rules, S3 (mid-tail repair position) runs next.
- Misses: 34.
