# Worklog (MSE round)

One entry per iteration:

```
## <n> — <idea> (<date>)
- commit: <sha>
- score: mean <x> over seeds 0-4
- champion mean: <x>
- verdict: keep or discard
- what changed: <one sentence>
- what you learned: <one sentence with numbers>
- next: <next idea>
```

`mean` is mean squared error. Prior round record is archived at
`placement/archive/mae-round/`.

## 1 — wide bound 1.5 then 0.5 (2026-10-03)
- commit: ed16e2d
- score: mean 319.4704 over seeds 0-4 (286.8453, 378.2883, 356.0608, 262.0017, 314.1560)
- champion mean: 323.1547 (dfe56ea)
- verdict: keep
- what changed: first FFA spread widened from 1.0 to 1.5 sigma; duels and 0.5 refine unchanged.
- what you learned: wins by 3.68 with seeds 0/2/3 improving and seed 2 fixed as predicted, but seeds 1/4 regressed; wider bounds trade typical precision for tail coverage.
- next: wider still (2.0 bound) to trace the gradient.

## 2 — wider bound 2.0 then 0.5 (2026-10-03)
- commit: c05a544
- score: mean 316.7159 over seeds 0-4 (287.7754, 367.1452, 364.8904, 257.6713, 306.0971)
- champion mean: 319.4704 (ed16e2d)
- verdict: keep
- what changed: first FFA spread widened from 1.5 to 2.0 sigma.
- what you learned: wins by 2.75 with seeds 1/3/4 improving (seed 1 down 11), but seed 2 regressed 8.8; the width optimum differs per seed, gradient still descends overall.
- next: 2.5 bound to find the top of the gradient.

## 3 — bound 2.5 then 0.5 (2026-10-03)
- commit: c0d2e7b
- score: mean 317.8334 over seeds 0-4 (286.6899, 380.7460, 367.9831, 246.7392, 307.0087)
- champion mean: 316.7159 (c05a544)
- verdict: discard
- what changed: first FFA spread widened from 2.0 to 2.5 sigma.
- what you learned: cost about 1.12 with seeds 1/2 regressing while seed 3 hit a round-best 246.74; width optimum sits between 2.0 and 2.5 and differs per seed.
- next: interleaved bulk retest from the archive trawl.

## 4 — interleaved bulk 3d wide 2d narrow (2026-10-03)
- commit: e9d728c
- score: mean 311.2044 over seeds 0-4 (273.0052, 357.2504, 363.7061, 258.3359, 303.7243)
- champion mean: 316.7159 (c05a544)
- verdict: keep
- what changed: 2 duels moved between the FFAs (3d, 2.0-sigma 10p, 2d, 0.5-sigma 10p).
- what you learned: wins by 5.51 with every seed improving (seed 0 down 14.8); mid re-positioning before the refine FFA cuts tails under MSE.
- next: bracket duels retest, the other archive-mined idea.

## 5 — bracket mid duel pair above below (2026-10-03)
- commit: 814c58d
- score: mean 302.9460 over seeds 0-4 (268.5222, 354.2697, 352.7147, 246.8385, 292.3848)
- champion mean: 311.2044 (e9d728c)
- verdict: keep
- what changed: mid duel pair changed from closest to nearest-above then nearest-below.
- what you learned: wins by 8.26 with every seed improving (seeds 2/3/4 down about 11 each); deliberate two-sided tests beat closest rematches under MSE.
- next: edge-conditional narrow bound for extreme bots.

## 6 — edge conditional narrow bound (2026-10-03)
- commit: 253157d
- score: mean 302.9460 over seeds 0-4 (268.5222, 354.2697, 352.7147, 246.8385, 292.3848)
- champion mean: 302.9460 (814c58d)
- verdict: discard
- what changed: wide FFA narrows to 0.5 sigma when bot mu lies outside the anchor mu range.
- what you learned: bit-identical to champion on all 5 seeds; the tertile always spans bot mu so the trigger never fires, and one-sided pools pick identically anyway.
- next: Approach 1 pipeline retest for seed stability.

## 7 — Approach 1 pipeline retest (2026-10-03)
- commit: b67c787
- score: mean 395.4306 over seeds 0-4 (375.3920, 371.6470, 572.0059, 312.3252, 345.7831)
- champion mean: 302.9460 (814c58d)
- verdict: discard
- what changed: percentile duels, 5p cluster, 10p deciles, tight 5p, 3 precision duels.
- what you learned: cost about 92.5 with seed 2 catastrophic at 572; large-first percentile openers poison positioning harder under MSE, and tight clusters cannot catch tails.
- next: bold idea required (two misses in a row); coverage-maximalist twin-wide 10ps.

## 8 — twin-wide 10ps bold 1 (2026-10-03)
- commit: 07e94d0
- score: mean 302.2418 over seeds 0-4 (260.2761, 346.6090, 366.1758, 240.0556, 298.0927)
- champion mean: 302.9460 (814c58d)
- verdict: keep
- what changed: refine 10p widened from 0.5 to 2.0 sigma (twin-wide bulk).
- what you learned: wins by 0.70 with seeds 0/1/3 improving but seed 2 regressing 13.5; the refine pulls weight on hard seeds, so this lead is fragile.
- next: quartile anchors retest for cleaner thresholds.

## 9 — quartile anchors retest (2026-10-03)
- commit: 3e4db33
- score: mean 305.3390 over seeds 0-4 (280.7635, 349.6873, 372.7065, 248.9563, 274.5812)
- champion mean: 302.2418 (07e94d0)
- verdict: discard
- what changed: anchor cutoff from low-sigma tertile to quartile.
- what you learned: cost about 3.10 with every seed but seed 4 regressing; stricter rulers thin the pool too far and wide targets overshoot sparser anchors.
- next: symmetric pairs recheck under MSE.

## 10 — 3p opening closest pair (2026-10-03)
- commit: 0302394
- score: mean 304.1436 over seeds 0-4 (272.7167, 355.9928, 368.1019, 235.8973, 288.0093)
- champion mean: 302.2418 (07e94d0)
- verdict: discard
- what changed: opening 3 duels swapped for two 3p games with the closest pair.
- what you learned: cost about 1.90 with only seed 3 improving (round-best 235.90); sequential updates position better than richer-but-fewer opening games.
- next: bold idea required (two misses); tail-chasing one-sided spread.

## 11 — tail-chasing one-sided spread bold 2 (2026-10-03)
- commit: 9fc35aa
- score: mean 364.2914 over seeds 0-4 (403.3422, 411.7953, 390.9876, 279.7335, 335.5986)
- champion mean: 302.2418 (07e94d0)
- verdict: discard
- what changed: FFA targets one-sided toward the tail for bots a full sigma from the median.
- what you learned: cost about 62 with every seed regressing; two-sided bounds are load-bearing even for tail bots, concentration loses more than it buys.
- next: 4p mid game (bot plus above, below, closest).

## 12 — 4p mid game above below closest (2026-10-03)
- commit: 2b369bc
- score: mean 333.7663 over seeds 0-4 (383.0104, 372.0348, 397.4840, 242.9642, 273.3379)
- champion mean: 302.2418 (07e94d0)
- verdict: discard
- what changed: mid bracket pair merged into one 4p game with above, below, closest.
- what you learned: cost about 31.5 with seeds 0/1/2 blowing up; one parallel game cannot replace two sequential bracket duels, and the lost update hurts everywhere.
- next: judge bold 1 after iter 14 window; meanwhile all-3p schedule.

## 13 — all-3p schedule closest pair (2026-10-03)
- commit: a55d3fa
- score: mean 806.4453 over seeds 0-4 (846.4554, 898.4526, 771.6011, 716.9007, 798.8168)
- champion mean: 302.2418 (07e94d0)
- verdict: discard
- what changed: all 30 slots as ten 3p games with the closest pair.
- what you learned: cost about 504 with every seed catastrophic; sequential updates cannot replace threshold coverage, and unspread fields let tails drift to pool edges.
- next: judge bold 1 (confirmed by adoption, fragile lead); judge bold 2 (refuted).

## 14 — adaptive refine width by sigma (2026-10-03)
- commit: 752442e
- score: mean 302.9460 over seeds 0-4 (268.5222, 354.2697, 352.7147, 246.8385, 292.3848)
- champion mean: 302.2418 (07e94d0)
- verdict: discard (null experiment)
- what changed: second 10p at 2.0 iff refine-time sigma above 6.5 else 0.5.
- what you learned: bit-identical to champion on all 5 seeds; a sigma probe showed refine-time sigma averages 3.9 (209 of 211 below 6.5), so the threshold never bites and the branch is dead code.
- next: adaptive refine at 4.0, or bounty sniper from the docket.

## 15 — bounty sniper opener (2026-10-03)
- commit: 2816950
- score: mean 302.7300 over seeds 0-4 (272.2795, 342.0151, 358.0327, 248.1882, 293.1344)
- champion mean: 302.2418 (07e94d0)
- verdict: discard
- what changed: first game duels the max-sigma pool member; other 28 slots champion.
- what you learned: cost about 0.49 with only seed 1 improving (down 12); the bounty eats the best positioning duel and pool gains do not repay within 1000 bots.
- next: push-fold routing (adaptive schedules by stack).

## 16 — push-fold routing by stack (2026-10-03)
- commit: 8ffc9d7
- score: mean 404.5076 over seeds 0-4 (410.1610, 460.2390, 524.5075, 288.3950, 339.2354)
- champion mean: 302.2418 (07e94d0)
- verdict: discard
- what changed: after 2 duels, short stacks played twin 2.5-sigma full-pool 10ps plus brackets while settled bots played duels plus a narrow 6p.
- what you learned: cost about 102 with seed 2 at 524; routing starves settled bots of bulk precision and the full-pool wide fields are too wild.
- next: forward bracketing from the archive docket.

## 17 — forward bracketing duels 1-3 (2026-10-03)
- commit: 5f464d3
- score: mean 308.2583 over seeds 0-4 (268.5208, 359.3840, 376.7973, 234.1801, 302.4094)
- champion mean: 302.2418 (07e94d0)
- verdict: discard
- what changed: opening duels changed from 3 closest to closest, above, below.
- what you learned: cost about 6.02 with seeds 1/2/4 regressing while seed 3 hit 234.18; early brackets fire before mu is positioned and waste duels on hard seeds.
- next: median anchors under twin-wide spreads.

## 18 — median anchors under twin-wide (2026-10-03)
- commit: 29052db
- score: mean 313.4292 over seeds 0-4 (264.8612, 391.6077, 385.2124, 243.0696, 282.3951)
- champion mean: 302.2418 (07e94d0)
- verdict: discard
- what changed: anchor cutoff from low-sigma tertile to median.
- what you learned: cost about 11.19 with seeds 1/2 blowing up; looser rulers poison wide fields on hard seeds, completing the MSE anchor ladder (median +11.2, quartile +3.1, tertile best).
- next: positioning depth 6/7 duels with twin bulk kept.

## 19 — 4 opening duels twin-wide closing duel (2026-10-03)
- commit: e6f29fa
- score: mean 339.8900 over seeds 0-4 (345.7774, 288.1528, 533.1337, 255.7368, 276.6492)
- champion mean: 302.2418 (07e94d0)
- verdict: discard
- what changed: 4 opening duels and a closing duel replaced the mid bracket pair.
- what you learned: cost about 37.6 with seed 2 catastrophic at 533; the mid bracket pair is load-bearing and extra opening depth cannot replace mid re-positioning.
- next: World Cup pots (cross-pot FFA fields).

## 20 — bulk-only three 10ps bold 3 (2026-10-03)
- commit: bd32cd8
- score: mean 290.3357 over seeds 0-4 (258.7701, 324.0591, 375.1257, 229.4492, 264.2746)
- champion mean: 302.2418 (07e94d0)
- verdict: keep
- what changed: all duels removed; three spread 10ps at 2.0 sigma from the prior.
- what you learned: wins by 11.91 with seeds 0/1/3/4 improving (seeds 1/4 down ~30/28) while seed 2 regressed 22.4; wide fields bound directly from the prior and positioning duels are expendable under MSE.
- next: bulk-only width sweep (first 10p at 2.5).

## 21 — bulk-only first 10p at 2.5 (2026-10-03)
- commit: 9e87b2c
- score: mean 253.2682 over seeds 0-4 (220.9625, 319.0903, 301.0831, 168.8851, 256.3198)
- champion mean: 290.3357 (bd32cd8)
- verdict: keep
- what changed: first of three bulk 10ps widened from 2.0 to 2.5 sigma.
- what you learned: wins by 37.07 with every seed improving (seeds 2/3 down 74/61); first-10p width is the big lever once duels are gone.
- next: first 10p at 3.0 to trace the new gradient.

## 22 — bulk-only first 10p at 3.0 (2026-10-03)
- commit: 04eeed2
- score: mean 235.2613 over seeds 0-4 (215.5600, 267.6422, 294.4307, 161.0474, 237.6262)
- champion mean: 253.2682 (9e87b2c)
- verdict: keep
- what changed: first bulk 10p widened from 2.5 to 3.0 sigma.
- what you learned: wins by 18.01 with every seed improving (seed 1 down 51); the first-10p gradient still climbs.
- next: first 10p at 3.5.

## 23 — bulk-only first 10p at 3.5 (2026-10-03)
- commit: 034a1f9
- score: mean 239.6700 over seeds 0-4 (209.9613, 318.3675, 292.8458, 145.0876, 232.0876)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: first bulk 10p widened from 3.0 to 3.5 sigma.
- what you learned: cost about 4.41 with seed 1 blowing up 51 while seeds 0/3 hit round bests; first-width optimum sits between 3.0 and 3.5 and differs per seed.
- next: second-10p width sweep under bulk-only.

## 24 — bulk widths 3.0 2.5 2.0 (2026-10-03)
- commit: ebfcc0b
- score: mean 249.3073 over seeds 0-4 (224.2195, 328.2947, 291.5314, 170.1917, 232.2991)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: second bulk 10p widened from 2.0 to 2.5 sigma.
- what you learned: cost about 14.05 with every seed regressing; the second bulk wants 2.0, so wide-then-narrower holds across all three bulks.
- next: third-10p width sweep (1.0 or 1.5 refine under bulk-only).

## 25 — bulk widths 3.0 2.0 1.0 (2026-10-03)
- commit: c4c3d14
- score: mean 251.5510 over seeds 0-4 (213.5372, 323.1962, 304.4905, 167.0818, 249.4491)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: third bulk 10p narrowed from 2.0 to 1.0 sigma.
- what you learned: cost about 16.29 with every seed regressing; later bulks want the full 2.0 width, so only the opener zooms wider.
- next: World Cup pots (cross-pot FFA composition).

## 26 — World Cup pots cross-pot fields (2026-10-03)
- commit: a5d20db
- score: mean 350.5191 over seeds 0-4 (340.0084, 426.6418, 403.9221, 257.8552, 324.1678)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: each 10p forced 3 opponents from each mu third of the pool.
- what you learned: cost about 115 with every seed regressing; pot quotas break target proximity, and far opponents on near targets waste thresholds.
- next: gatekeeper FFA (second 10p shifted a tier stronger).

## 27 — gatekeeper second 10p shifted up (2026-10-03)
- commit: 397b740
- score: mean 251.4521 over seeds 0-4 (226.2027, 293.7582, 301.4661, 179.6260, 256.2074)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: second 10p targets shifted 1 sigma stronger than mu.
- what you learned: cost about 16.19 with every seed regressing; shifted fields bias estimates upward and symmetric coverage is load-bearing.
- next: gradient fields (weak heat, peer semi, shark final).

## 28 — wide-grid quantiles 0.05 0.95 (2026-10-03)
- commit: 0181492
- score: mean 242.8302 over seeds 0-4 (209.1506, 334.4954, 290.6181, 126.7537, 253.1332)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: spread targets moved from (j+1)/(k+1) to a wider (j+0.5)/k CDF grid.
- what you learned: cost about 7.57 with violent seed splits (seed 3 down 34 to 126.75, seed 1 up 67); wider grids redistribute coverage without adding it and destabilize hard seeds.
- next: equal-bits ladder 2+4+6+8+10.

## 29 — equal-bits ladder 2 4 6 8 10 (2026-10-03)
- commit: 4b65ae9
- score: mean 343.8911 over seeds 0-4 (382.1917, 331.9569, 481.8846, 232.2811, 291.1413)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: bulk fragmented into 4p, 6p, 8p, 10p after one duel, all at 2.0.
- what you learned: cost about 108.63 with seed 2 at 481.88; mid-size fragments cannot bound tails and per-slot efficiency theory fails on tail risk.
- next: Swiss 12 duels no-rematch, then two 10p finals.

## 30 — Swiss walk-out duels then bulks (2026-10-03)
- commit: 599afa9
- score: mean 309.5240 over seeds 0-4 (277.2032, 380.6048, 343.6314, 242.8154, 303.3651)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: 5 opening duels walking outward by closeness rank, then 3.0 and 2.0 10ps.
- what you learned: cost about 74.26 with every seed regressing; duels cost a whole bulk and outward walks spend games on ever-worse opponents.
- next: successive-halving duel tournament with FFA confirmation.

## 31 — shrinking zoom bold 4 (2026-10-03)
- commit: f353b7f
- score: mean 327.2455 over seeds 0-4 (351.1262, 281.1943, 516.0806, 219.9872, 267.8392)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: duel plus 9p at 2.0, 9p at 1.0, 10p at 0.5.
- what you learned: cost about 91.98 with seed 2 at 516.08; size and width zoom have no redeeming interaction, uniform wide bulk stands.
- next: successive-halving duel tournament with FFA confirmation.

## 32 — mixed final 10p closest plus spread (2026-10-03)
- commit: 9c7f58d
- score: mean 251.9776 over seeds 0-4 (211.6670, 306.3179, 375.3259, 140.2548, 226.3223)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: final 10p mixed 3 closest opponents with a 6-target spread ring.
- what you learned: cost about 16.72 with seeds 1/2 blowing up while seeds 0/3/4 improved; closest-core crowds out the far thresholds hard seeds need.
- next: deterministic UCB rotation under bulk-only.

## 33 — UCB rotation duels then bulks (2026-10-03)
- commit: 2564fc2
- score: mean 308.8207 over seeds 0-4 (287.0037, 379.1673, 342.3745, 236.1024, 299.4558)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: 5 opening duels cycling top-6 by -dist + 0.5 sigma, then 3.0 and 2.0 10ps.
- what you learned: cost about 73.56 with every seed regressing; 5 duels cost a whole bulk and the sigma bonus drags noisy opponents into positioning.
- next: D-optimal 4-duel screen, or accept the bulk-only shape.

## 34 — unfiltered bulk-only bold 5 (2026-10-03)
- commit: 729db95
- score: mean 273.4087 over seeds 0-4 (257.1242, 327.4912, 384.5589, 158.6783, 239.1909)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: tertile anchor filter removed; full-pool spreads at 3.0/2.0/2.0.
- what you learned: cost about 38.15 with seeds 0/1/2/4 regressing (seed 2 up 90) while seed 3 improved; calibrated rulers matter with or without duels.
- next: Augusta Cut fixed (four 6p opens plus 3 closing duels).

## 35 — Augusta Cut four 6ps closing duels (2026-10-03)
- commit: 63f5411
- score: mean 409.9362 over seeds 0-4 (402.6176, 462.8777, 489.0574, 312.7057, 382.4224)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: four 6p spreads at 2.0 followed by 3 closing closest duels.
- what you learned: cost about 174.67 with every seed catastrophic; 6p fragments cannot bound tails and closing duels cannot rescue unpositioned mus.
- next: D-optimal 4-duel screen at +- {0.5, 1.5} sigma.

## 36 — D-optimal 4-duel screen (2026-10-03)
- commit: 2c6d7c2
- score: mean 326.8473 over seeds 0-4 (322.8224, 300.9601, 505.1301, 250.5289, 254.7951)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: 4 opening duels at fixed mu +- {0.5, 1.5} sigma points, then 3.0/2.0 10ps plus a closer.
- what you learned: cost about 91.59 with seed 2 at 505; fixed design points from an unpositioned prior misfire and duels cost bulk.
- next: split-budget recenter (2+3+10 halves, then 5+10).

## 37 — split-budget recenter halves (2026-10-03)
- commit: a2f0846
- score: mean 335.4714 over seeds 0-4 (374.7197, 330.0085, 441.3099, 269.9206, 261.3985)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: confirm half (duel, 3p cluster, wide 10p) then exploit half (5p, narrow 10p).
- what you learned: cost about 100.21 with every seed regressing; small sizes cannot recenter what they cannot bound, and narrow late widths collapse under MSE.
- next: candidates double round-robin (rematch-heavy positioning).

## 38 — 8p refine plus closing duel (2026-10-03)
- commit: 86c6e90
- score: mean 262.9913 over seeds 0-4 (237.9805, 322.7906, 307.9894, 175.6756, 270.5202)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: third bulk shrunk to 8p at 2.0 plus a final closest duel.
- what you learned: cost about 27.73 with every seed regressing; the 2 lost bulk looks outweigh one precision duel, full 10ps stand.
- next: adaptive refine at 4.0 (probe says refine-time sigma mean is 3.9).

## 39 — pool-size-adaptive opener bold 6 (2026-10-03)
- commit: 760b114
- score: mean 242.9232 over seeds 0-4 (227.6190, 322.6718, 287.4612, 151.3065, 225.5575)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: first 10p at 4.0 sigma while pool under 200, else 3.0.
- what you learned: cost about 7.66 with seeds 2/3/4 improving (seed 3 down 10) but seeds 0/1 regressing hard; pool size misconditions width, overshoot hurts more than reach helps.
- next: adaptive refine at 4.0 (probe-calibrated threshold).

## 40 — adaptive refine at 4.0 (2026-10-03)
- commit: 72deb88
- score: mean 247.8303 over seeds 0-4 (207.8530, 326.4933, 306.6815, 147.9795, 250.1443)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: third 10p narrowed to 1.0 for bots at or below sigma 4.0.
- what you learned: cost about 12.57 with seed 1 blowing up 59 while seeds 0/3 improved; narrowing for settled bots destabilizes hard seeds.
- next: judge bold 6 (refuted); symmetric pairs recheck under bulk-only.

## 41 — uniform 2.0 bulk no wide opener (2026-10-03)
- commit: 142897a
- score: mean 290.3357 over seeds 0-4 (258.7701, 324.0591, 375.1257, 229.4492, 264.2746)
- champion mean: 235.2613 (04eeed2)
- verdict: discard (duplicate)
- what changed: intended as the untested uniform cell, but it replays iteration 20 exactly.
- what you learned: bit-identical to iteration 20 on all 5 seeds, revalidating determinism; the 3.0 opener buys 55 points over uniform 2.0. Bold 6 judged refuted (iter 39).
- next: stop grid-filling; only probe-driven or docket-novel ideas.

## 42 — tail-skewed two-sided grid bold 7 (2026-10-03)
- commit: b44e155
- score: mean 255.4596 over seeds 0-4 (219.1812, 333.5048, 302.8655, 165.5483, 256.1983)
- champion mean: 235.2613 (04eeed2)
- verdict: discard
- what changed: spread grid mass shifted 0.05 toward the bot tail side, both sides kept.
- what you learned: cost about 20.20 with every seed regressing; even soft skew displaces load-bearing median-side thresholds, symmetric grids stand.
- next: mixed anchors per game (full-pool opener, tertile rest).

## 43 — mixed anchors full-pool opener (2026-10-03)
- commit: a607580
- score: mean 228.3885 over seeds 0-4 (179.0323, 254.2174, 368.3620, 136.1036, 204.2272)
- champion mean: 235.2613 (04eeed2)
- verdict: keep
- what changed: first 10p spread from the full pool; later 10ps stay tertile-anchored.
- what you learned: wins by 6.87 with seeds 0/1/3/4 improving hugely (seed 0 down 36, seed 4 down 33) while seed 2 regressed 74; opener reach beats calibration, later bulks still need rulers.
- next: judge bold 7 (refuted); no-rematch diversity across bulks.

## 44 — full-pool first two 10ps (2026-10-03)
- commit: 020c0ee
- score: mean 245.8308 over seeds 0-4 (201.2458, 281.8275, 412.1120, 126.9929, 206.9758)
- champion mean: 228.3885 (a607580)
- verdict: discard
- what changed: full-pool spreads extended from the opener to the second 10p.
- what you learned: cost about 17.44 with only seed 3 improving (down 9 to round-best 126.99); reach helps only the unpositioned opener, game 2 needs rulers. Bold 7 judged refuted (iter 42).
- next: tertile opener with full-pool rest (invert the mix).

## 45 — inverted mix tertile opener (2026-10-03)
- commit: ebd464c
- score: mean 282.7469 over seeds 0-4 (268.3774, 336.6876, 399.6590, 163.9528, 245.0577)
- champion mean: 228.3885 (a607580)
- verdict: discard
- what changed: tertile-anchored opener with full-pool later bulks.
- what you learned: cost about 54.36 with every seed regressing; the anchor factorial reads TT 235.26, FT 228.39, TF 282.75, FF 273.41, so reach-then-calibrate wins both margins near-additively.
- next: opener width re-sweep under full-pool (3.0 may not be optimal unfiltered).

## 46 — full-pool opener at 3.5 (2026-10-03)
- commit: 95e521f
- score: mean 223.8133 over seeds 0-4 (178.0182, 258.1805, 364.6575, 119.7851, 198.4253)
- champion mean: 228.3885 (a607580)
- verdict: keep
- what changed: unfiltered opener widened from 3.0 to 3.5 sigma.
- what you learned: wins by 4.58 with seeds 0/2/3/4 improving (seed 3 down 16 to 119.79) and only seed 1 regressing slightly; unfiltered reach pays wider than anchored reach.
- next: full-pool opener at 4.0.

## 47 — full-pool opener at 4.0 (2026-10-03)
- commit: 0d52b79
- score: mean 222.4811 over seeds 0-4 (190.7783, 271.6876, 344.8539, 117.0290, 188.0568)
- champion mean: 223.8133 (95e521f)
- verdict: keep
- what changed: unfiltered opener widened from 3.5 to 4.0 sigma.
- what you learned: wins by 1.33 with seeds 2/3/4 improving (seed 2 down 20, seed 3 at 117.03) while seeds 0/1 regressed; gradient diminishing, top near.
- next: full-pool opener at 4.5.

## 48 — full-pool opener at 4.5 (2026-10-03)
- commit: f03d99e
- score: mean 226.5758 over seeds 0-4 (193.2400, 273.4025, 352.9703, 121.5482, 191.7182)
- champion mean: 222.4811 (0d52b79)
- verdict: discard
- what changed: unfiltered opener widened from 4.0 to 4.5 sigma.
- what you learned: cost about 4.09 with every seed regressing slightly; unfiltered optimum sits at 4.0, overshoot clips pool edges uniformly.
- next: held-out validation on seeds 5-9, then reassess the docket.

## Validation — held-out seeds 5-9 (2026-10-03, measurement only)
- champion 0d52b79 (4.0 opener): 156.2611, 245.6530, 242.9705, 222.0143, 177.3267, mean 208.8451
- rival iter-46 replica (3.5 opener): 156.8524, 252.1356, 261.8108, 206.1967, 175.6301, mean 210.5251
- verdict: champion wins by 1.68 on unseen seeds (selection margin was 1.33); 4.0 over 3.5 generalizes, no overfit. Only seed 8 flips.

## 49 — game-2 conditional reach off-median (2026-10-03)
- commit: 85cd81f
- score: mean 239.6201 over seeds 0-4 (193.5417, 282.4494, 384.7677, 121.7424, 215.5992)
- champion mean: 222.4811 (0d52b79)
- verdict: discard
- what changed: second 10p went full-pool at 2.5 whenever bot mu sat a full sigma from the anchor median.
- what you learned: cost about 17.14 with every seed regressing (seed 2 up 40); conditional reach destabilizes mid-schedule, only the opener wants the wild pool.
- next: quartile anchors under the 4.0-opener shape.

## 50 — quartile anchors 4.0-opener shape (2026-10-03)
- commit: ea83bc9
- score: mean 226.4948 over seeds 0-4 (197.2486, 271.6056, 356.5259, 119.4636, 187.6302)
- champion mean: 222.4811 (0d52b79)
- verdict: discard
- what changed: anchor cutoff from low-sigma tertile to quartile.
- what you learned: cost about 4.01 with seeds 0/2 regressing; tertile optimum holds under the 4.0-opener shape.
- next: second-10p width re-sweep under 4.0 opener.

## 51 — widths 4.0 2.5 2.0 mixed anchors (2026-10-03)
- commit: 9680f44
- score: mean 232.6733 over seeds 0-4 (199.1817, 281.9042, 358.4098, 125.5233, 198.3476)
- champion mean: 222.4811 (0d52b79)
- verdict: discard
- what changed: second bulk 10p widened from 2.0 to 2.5 under the 4.0 opener.
- what you learned: cost about 10.19 with every seed regressing; the second bulk wants 2.0 under mixed anchors too.
- next: third-10p 1.5 under mixed anchors, then docket triage.

## 52 — widths 4.0 2.0 1.5 mixed anchors (2026-10-03)
- commit: d64947b
- score: mean 224.3975 over seeds 0-4 (183.2662, 271.7627, 357.3339, 117.7020, 191.9227)
- champion mean: 222.4811 (0d52b79)
- verdict: discard
- what changed: third bulk 10p narrowed from 2.0 to 1.5 sigma.
- what you learned: cost about 1.92 with seed 2 regressing 12.5 while seed 0 improved; the third bulk wants 2.0, completing the width grid under mixed anchors.
- next: docket triage, then a fresh probe for the remaining error.

## 53 — hollow-spread opener bold 8 (2026-10-03)
- commit: 90ce055
- score: mean 267.6182 over seeds 0-4 (270.9846, 313.4050, 354.2070, 159.8596, 239.6346)
- champion mean: 222.4811 (0d52b79)
- verdict: discard
- what changed: opener targets replaced with 8 edge quantiles plus one center pin.
- what you learned: cost about 45.14 with every seed regressing; middle thresholds are load-bearing, hollowing them starves the middle game.
- next: game-3 full-pool (last anchor-factorial cell).

## 54 — game-3 full-pool factorial cell (2026-10-03)
- commit: abde3b4
- score: mean 267.8132 over seeds 0-4 (257.2095, 318.8450, 395.3134, 139.8094, 227.8885)
- champion mean: 222.4811 (0d52b79)
- verdict: discard
- what changed: third 10p spread from the full pool instead of tertile anchors.
- what you learned: cost about 45.33 with every seed regressing; only the opener wants the wild pool, later games need rulers everywhere.
- next: opener at 4.25 (gradient-top micro-probe).

## 55 — full-pool opener at 4.25 (2026-10-03)
- commit: 9b38f80
- score: mean 221.5778 over seeds 0-4 (186.5514, 274.5606, 339.4188, 120.5184, 186.8396)
- champion mean: 222.4811 (0d52b79)
- verdict: keep
- what changed: unfiltered opener widened from 4.0 to 4.25 sigma.
- what you learned: wins by 0.90 with seeds 0/2/4 improving while seeds 1/3 regressed slightly; gradient top is flattening near the seed-generalization floor.
- next: opener at 4.375 to bisect the top.

## 56 — full-pool opener at 4.375 (2026-10-03)
- commit: 569703d
- score: mean 226.7590 over seeds 0-4 (196.4257, 274.2454, 354.6921, 115.1684, 193.2632)
- champion mean: 221.5778 (9b38f80)
- verdict: discard
- what changed: unfiltered opener widened from 4.25 to 4.375 sigma.
- what you learned: cost about 5.18 with seed 2 regressing 15 while seed 3 improved to 115.17; the top sits at 4.25, overshoot clips edges. Bold 8 judged refuted (iter 53).
- next: game-2 width micro-probe at 2.25, then accept the shape.

## 57 — widths 4.25 2.25 2.0 (2026-10-03)
- commit: 59100c7
- score: mean 228.1484 over seeds 0-4 (193.9969, 273.3836, 352.7951, 128.6346, 191.9318)
- champion mean: 221.5778 (9b38f80)
- verdict: discard
- what changed: second bulk 10p widened from 2.0 to 2.25 sigma.
- what you learned: cost about 6.57 with seed 2 regressing 13; game-2 wants exactly 2.0, micro-wider fails the same way macro-wider did.
- next: accept the shape (4.25/2.0/2.0, full/tertile/tertile) or find genuinely new data.

## 58 — split bulks 5p 5p 10p 10p bold 9 (2026-10-03)
- commit: e620ed3
- score: mean 256.6085 over seeds 0-4 (211.9821, 320.1560, 347.8332, 160.9739, 242.0973)
- champion mean: 221.5778 (9b38f80)
- verdict: discard
- what changed: opener split into two 5p spreads (4.25 full-pool, 2.0 tertile) before two 10ps.
- what you learned: cost about 35.03 with every seed regressing; 4 opener looks cannot bound and the 9-threshold opener stands.
- next: opener at 4.125 (bisect down from 4.25).

## 59 — full-pool opener at 4.125 (2026-10-03)
- commit: 5d51245
- score: mean 224.4548 over seeds 0-4 (189.9996, 274.5994, 351.2539, 116.0737, 190.3476)
- champion mean: 221.5778 (9b38f80)
- verdict: discard
- what changed: unfiltered opener narrowed from 4.25 to 4.125 sigma.
- what you learned: cost about 2.88, worse than both 4.0 and 4.25 neighbors; the width top is flat-topped noise, stop bisecting.
- next: judge bold 9 (refuted); third validation on seeds 5-9 for the 4.25 champion.

## 60 — game-2 quartile anchors (2026-10-03)
- commit: 1d58e54
- score: mean 225.9611 over seeds 0-4 (196.7094, 268.9228, 342.0734, 120.4885, 201.6113)
- champion mean: 221.5778 (9b38f80)
- verdict: discard
- what changed: second 10p drew from low-sigma quartile instead of tertile.
- what you learned: cost about 4.38 with seeds 0/4 regressing hard; game-2 wants tertile too, per-game strictness buys nothing. Bold 9 judged refuted (iter 58).
- next: third validation (4.25 champion vs 4.0 rival) on seeds 5-9.

## Validation — 4.25 champion vs 4.0 rival, seeds 5-9 (2026-10-03)
- champion 9b38f80 (4.25): 166.3530, 256.0795, 244.2667, 222.0000, 188.2779, mean 215.3954
- rival 0d52b79 (4.0): 156.2611, 245.6530, 242.9705, 222.0143, 177.3267, mean 208.8451
- verdict: rival wins by 6.55 on unseen seeds (4 of 5 seeds, seed 8 ties); the 0.90 selection margin was noise.
- pooled 10-seed means: 4.0 = 215.6631, 4.25 = 218.4866. Reverting champion to 4.0 on all available evidence.

## 61 — sizes 9p 9p 10p closing duel (2026-10-03)
- commit: 797e33d
- score: mean 258.6554 over seeds 0-4 (234.2471, 298.8569, 377.1949, 146.9238, 236.0544)
- champion mean: 222.4811 selection, 215.6631 pooled (84b606d)
- verdict: discard
- what changed: first two bulks shrunk to 9p (8 targets) with a closing duel spending the freed slots.
- what you learned: cost about 36.17 with every seed regressing; 9 opener thresholds are load-bearing and the duel does not compensate.
- next: opener at 3.75 with held-out confirmation ready (confirmation rule).

## 62 — full-pool opener at 3.75 with confirmation (2026-10-03)
- commit: 7e8ca31
- score: selection mean 221.6532 over seeds 0-4 (198.7400, 253.9607, 352.2130, 112.6283, 190.7241)
- champion selection mean: 222.4811 (84b606d)
- confirmation: 209.6234 over seeds 5-9 (160.9519, 247.1511, 245.1461, 217.3538, 177.5143) vs 4.0 held-out 208.8451
- verdict: discard
- what changed: unfiltered opener narrowed from 4.0 to 3.75 sigma.
- what you learned: won selection by 0.83 but lost held-out by 0.78; pooled 10-seed means tie at 215.64 vs 215.66. The confirmation rule earns its keep; the width top is flat and the incumbent holds ties.
- next: hunt outside width-space; widths are priced.

## 63 — front-loaded mop-up 10 10 6 4 bold 10 (2026-10-03)
- commit: e786a6e
- score: mean 290.6161 over seeds 0-4 (253.5299, 323.4906, 448.0187, 170.6047, 257.4367)
- champion mean: 222.4811 selection, 215.6631 pooled (84b606d)
- verdict: discard
- what changed: third 10p replaced with a 6p spread plus a 4p above/below/closest closer.
- what you learned: cost about 68.13 with every seed regressing; small games stay weak as closers and the third 10p is load-bearing.
- next: uniform small bulks (5x6p) to close the size book.

## 64 — five uniform 6p spreads (2026-10-03)
- commit: 0a30b60
- score: mean 344.9974 over seeds 0-4 (330.7500, 404.0225, 445.6413, 239.8667, 304.7066)
- champion mean: 222.4811 selection, 215.6631 pooled (84b606d)
- verdict: discard
- what changed: three 10p bulks replaced with five 6p spreads (4.0 full-pool opener, 2.0 tertile rest).
- what you learned: cost about 122.52 with every seed regressing; comparisons-per-slot dominate update count and the size book closes monotonic (3p +504, 6p +123, 10p champion).
- next: judge bold 10; then a mechanism hunt outside schedule-space.

## 65 — game-2 at 1.5 with confirmation (2026-10-03)
- commit: 43b260f
- score: selection mean 221.8680 over seeds 0-4 (182.8709, 262.3690, 360.7857, 113.4359, 189.8785)
- prior champion selection mean: 222.4811 (84b606d)
- confirmation: 202.0228 over seeds 5-9 (151.9866, 238.7065, 237.5904, 217.0294, 164.8009), all five improve
- pooled: 211.9454 vs 215.6631
- verdict: keep
- what changed: second bulk 10p narrowed from 2.0 to 1.5 sigma.
- what you learned: game-2 optimum is interior at 1.5 (ladder 1.5 < 2.0 < 2.25 < 2.5); the confirmation rule converts a 0.61 margin into a 3.7 pooled win. Bold 10 judged refuted (iter 63).
- next: game-3 width re-sweep under the 1.5-second shape.

## 66 — game-3 at 2.5 with confirmation (2026-10-03)
- commit: d6766a0
- score: selection mean 219.9983 over seeds 0-4 (185.5725, 259.7036, 358.7914, 108.1958, 187.7284)
- champion selection mean: 221.8680 (43b260f)
- confirmation: 202.1480 over seeds 5-9 (150.9431, 237.3434, 236.8614, 221.1624, 164.4296) vs champion held-out 202.0228
- verdict: discard
- what changed: third bulk 10p widened from 2.0 to 2.5 sigma.
- what you learned: won selection by 1.87 but lost held-out by 0.13 (seed 8 regressed 4.1); game-3 wants 2.0 and the incumbent holds ties.
- next: game-3 at 1.5 under the 1.5-second shape (narrow closer).

## 67 — game-3 at 1.5 with confirmation (2026-10-03)
- commit: e6e67e6
- score: selection mean 218.2927 over seeds 0-4 (175.9532, 256.0168, 364.1397, 111.7475, 183.6062)
- champion selection mean: 221.8680 (43b260f)
- confirmation: 204.5965 over seeds 5-9 (153.9223, 249.9861, 239.3522, 214.6594, 165.0626) vs champion held-out 202.0228
- verdict: discard
- what changed: third bulk 10p narrowed from 2.0 to 1.5 sigma.
- what you learned: won selection by 3.58 but lost held-out by 2.57 with only seed 8 improving; selection wins keep fitting selection-set quirks. Game-3 wants 2.0.
- next: opener anchor re-check under 4.0/1.5/2.0, then an outside-schedule hunt.

## 68 — young-pool full game-2 bold 11 (2026-10-03)
- commit: 118929d
- score: mean 225.9936 over seeds 0-4 (172.4220, 265.5133, 414.2154, 102.1492, 175.6683)
- champion mean: 221.8680 selection, 211.9454 pooled (43b260f)
- verdict: discard
- what changed: game-2 drew full-pool when the pool was under 300, tertile otherwise.
- what you learned: cost about 4.13 with seed 2 destabilized plus 53; pool age does not matter, young full-pool adds noise. Also caught an inverted anchors flag before scoring.
- next: game-2 at 1.0 (narrow-side gradient step).

## 69 — game-2 at 1.0 with confirmation (2026-10-03)
- commit: a42f8be
- score: selection mean 219.5651 over seeds 0-4 (181.3488, 254.2048, 369.6941, 111.3997, 181.1781)
- champion selection mean: 221.8680 (43b260f)
- confirmation: 204.4396 over seeds 5-9 (153.3340, 239.1761, 251.0751, 217.3397, 161.2729) vs champion held-out 202.0228
- verdict: discard
- what changed: second bulk 10p narrowed from 1.5 to 1.0 sigma.
- what you learned: won selection by 2.30 but lost held-out by 2.42 with only seed 9 improving; the narrow trend stops at 1.5 and game-2 optimum is interior.
- next: judge bold 11; opener width re-check under 4.0/1.5/2.0.

## 70 — opener 4.5 under 1.5-second shape (2026-10-03)
- commit: 61a6987
- score: selection mean 220.1327 over seeds 0-4 (189.1712, 255.1674, 352.3404, 119.6997, 184.2850)
- champion selection mean: 221.8680 (43b260f)
- confirmation: 209.6885 over seeds 5-9 (163.9240, 246.3285, 235.1652, 218.4663, 184.5584) vs champion held-out 202.0228
- verdict: discard
- what changed: unfiltered opener widened from 4.0 to 4.5 sigma under the 1.5-second shape.
- what you learned: won selection by 1.74 but lost held-out by 7.67 with only seed 7 improving; opener optimum stays 4.0 and dimensions stay near-orthogonal. Bold 11 judged refuted (iter 68).
- next: game-2 anchor re-check (quartile) under the confirmed shape.

## 71 — game-2 quartile confirmed shape (2026-10-03)
- commit: a559723
- score: mean 223.1147 over seeds 0-4 (179.8775, 259.9609, 362.2260, 123.0320, 190.4771)
- champion mean: 221.8680 selection, 211.9454 pooled (43b260f)
- verdict: discard
- what changed: second 10p drew from low-sigma quartile instead of tertile.
- what you learned: cost about 1.25 with seed 3 regressing hard; tertile holds under the confirmed shape, no interaction.
- next: game-3 quartile under the confirmed shape (last anchor cell).

## 72 — game-3 quartile with confirmation (2026-10-03)
- commit: b254c65
- score: selection mean 220.8092 over seeds 0-4 (182.1402, 246.0828, 376.9191, 114.0180, 184.8859)
- champion selection mean: 221.8680 (43b260f)
- confirmation: 204.2337 over seeds 5-9 (159.1224, 235.2672, 258.5877, 199.5398, 168.6516) vs champion held-out 202.0228
- verdict: discard
- what changed: third 10p drew from low-sigma quartile instead of tertile.
- what you learned: won selection by 1.06 but lost held-out by 2.21 with seed 7 regressing 21; game-3 wants tertile and the anchor factorial is complete under the confirmed shape.
- next: hunt outside priced space; misses at 70-72 need a bold line only after two in a row — this is three straight, force bold 12.

## 73 — half-pool anchors bold 12 (2026-10-03)
- commit: f3b34db
- score: selection mean 221.5242 over seeds 0-4 (189.5575, 275.5703, 334.4478, 114.5346, 193.5108)
- champion selection mean: 221.8680 (43b260f)
- confirmation: 204.1018 over seeds 5-9 (147.9814, 262.3322, 224.6566, 217.2779, 168.2610) vs champion held-out 202.0228
- verdict: discard
- what changed: games 2 and 3 drew from the low-sigma half instead of tertile.
- what you learned: won selection by 0.34 on seed 2 alone but lost held-out by 2.08; tertile strictness is exact, interior-confirmed both sides.
- next: game-2 at 1.25 (width interior micro-grid).

## 74 — game-2 at 1.25 with confirmation (2026-10-03)
- commit: d87c207
- score: selection mean 221.7594 over seeds 0-4 (182.7957, 252.1771, 372.5235, 117.5623, 183.7384)
- prior champion selection mean: 221.8680 (43b260f)
- confirmation: 198.4055 over seeds 5-9 (147.3650, 229.3517, 235.0543, 213.4387, 166.8177), four of five improve
- pooled: 210.0825 vs 211.9454
- verdict: keep
- what changed: second bulk 10p narrowed from 1.5 to 1.25 sigma.
- what you learned: selection margin was pure noise (0.11) but held-out confirms by 3.62; the confirmation rule cuts both ways. Game-2 optimum slides narrower, 1.25 beats 1.5 pooled by 1.86.
- next: game-2 at 1.125 vs game-3 micro-bisects; judge bold 12.

## 75 — game-2 at 1.125 with confirmation (2026-10-03)
- commit: 80b9141
- score: selection mean 215.1422 over seeds 0-4 (168.3608, 237.7773, 371.6021, 112.6933, 185.2773)
- champion selection mean: 221.7594 (d87c207)
- confirmation: 199.1048 over seeds 5-9 (156.7201, 242.1668, 227.5917, 212.6955, 156.3498) vs champion held-out 198.4055
- verdict: discard
- what changed: second bulk 10p narrowed from 1.25 to 1.125 sigma.
- what you learned: won selection by 6.62 but lost held-out by 0.70 with seeds 5/6 regressing hard; held-out mean stays binding and the narrow slide stops at 1.25. Bold 12 judged refuted (iter 73).
- next: game-3 micro-bisects (1.75/2.25) under the 1.25-second shape.

## 76 — game-3 at 1.75 with confirmation (2026-10-03)
- commit: f8ba828
- score: selection mean 217.5528 over seeds 0-4 (178.4882, 243.6147, 365.7396, 114.9065, 185.0152)
- prior champion selection mean: 221.7594 (d87c207)
- confirmation: 197.7054 over seeds 5-9 (154.3496, 230.3280, 228.5739, 216.3339, 158.9417), two of five improve
- pooled: 207.6291 vs 210.0825
- verdict: keep
- what changed: third bulk 10p narrowed from 2.0 to 1.75 sigma.
- what you learned: best game-3 width on both seed sets (1.5/2.0/2.5 all lose somewhere); interior optimum confirmed twice over.
- next: game-3 at 1.625 vs game-2 at 1.375; judge nothing pending.

## 77 — game-3 at 1.625 (2026-10-03)
- commit: e77848e
- score: mean 218.6192 over seeds 0-4 (173.9886, 246.1789, 375.2724, 112.4399, 185.2162)
- champion mean: 217.5528 selection, 207.6291 pooled (f8ba828)
- verdict: discard
- what changed: third bulk 10p narrowed from 1.75 to 1.625 sigma.
- what you learned: cost about 1.07 with seed 2 regressing hard; game-3 optimum stays 1.75, interior-confirmed against 1.5/1.625 below and 2.0/2.5 above.
- next: game-2 at 1.375 under the 1.75-closer shape.

## 78 — game-2 at 1.375 with confirmation (2026-10-03)
- commit: 9ad6487
- score: selection mean 215.0672 over seeds 0-4 (181.9557, 233.8812, 365.3330, 108.9731, 185.1932)
- champion selection mean: 217.5528 (f8ba828)
- confirmation: 204.7727 over seeds 5-9 (148.1683, 241.0943, 246.7642, 218.9360, 168.9006) vs champion held-out 197.7054
- verdict: discard
- what changed: second bulk 10p widened from 1.25 to 1.375 sigma.
- what you learned: won selection by 2.49 but lost held-out by 7.07 with only seed 5 improving; game-2 stays 1.25 on both sets.
- next: opener micro re-check (3.875/4.125) under the confirmed shape, then a fresh hunt.

## 79 — joint 1.375 1.625 bold 13 (2026-10-03)
- commit: dc03482
- score: selection mean 212.8835 over seeds 0-4 (178.1306, 237.6838, 353.2927, 107.8727, 187.4375)
- champion selection mean: 217.5528 (f8ba828)
- confirmation: 204.9540 over seeds 5-9 (152.1419, 249.9687, 241.3939, 217.1208, 164.1449) vs champion held-out 197.7054
- verdict: discard
- what changed: games 2 and 3 moved together to 1.375/1.625 sigma.
- what you learned: won selection by 4.67 but lost held-out by 7.25 with seeds 6/7 collapsing; no interaction, singles already price the joint.
- next: opposite diagonal (1.125/1.875) or opener micro under confirmed shape.

## 80 — joint 1.125 1.875 steeper valley (2026-10-03)
- commit: e7dd7e3
- score: mean 220.0122 over seeds 0-4 (177.6236, 261.4079, 364.0918, 113.5016, 183.4359)
- champion mean: 217.5528 selection, 207.6291 pooled (f8ba828)
- verdict: discard
- what changed: games 2 and 3 moved apart to 1.125/1.875 sigma.
- what you learned: cost about 2.46 with seed 1 regressing hard; both diagonals dead and the valley stands at 1.25/1.75.
- next: judge bold 13; opener micro under confirmed shape.

## 81 — opener 4.125 confirmed shape (2026-10-03)
- commit: 9ce0e51
- score: mean 222.4864 over seeds 0-4 (172.5484, 259.3928, 378.4707, 117.3066, 184.7135)
- champion mean: 217.5528 selection, 207.6291 pooled (f8ba828)
- verdict: discard
- what changed: unfiltered opener widened from 4.0 to 4.125 sigma.
- what you learned: cost about 4.93 with seeds 1/2 collapsing; opener stays 4.0 under every rest-shape. Bold 13 judged refuted (iter 79).
- next: opener 3.875 under confirmed shape, then a fresh-seed audit of the champion.

## 82 — opener 3.875 with confirmation (2026-10-03)
- commit: 51ebb45
- score: selection mean 215.5556 over seeds 0-4 (175.9403, 239.9743, 362.6588, 111.8455, 187.3589)
- champion selection mean: 217.5528 (f8ba828)
- confirmation: 202.7807 over seeds 5-9 (153.4281, 234.8102, 243.0993, 220.4267, 162.1394) vs champion held-out 197.7054
- verdict: discard
- what changed: unfiltered opener narrowed from 4.0 to 3.875 sigma.
- what you learned: won selection by 2.00 but lost held-out by 5.08 with only seed 5 improving; opener 4.0 interior-confirmed both sides under the confirmed shape.
- next: fresh-seed audit of the champion on seeds 10-14.

## Audit — champion vs prior shape, fresh seeds 10-14 (2026-10-03)
- champion f8ba828 (4.0/1.25/1.75): 98.0481, 177.1954, 137.5694, 178.2967, 322.5080, mean 182.7235
- rival (4.0/1.25/2.0): 94.9219, 187.7922, 134.9855, 165.5075, 311.8668, mean 179.0148
- verdict: rival wins fresh by 3.71 (4 of 5 seeds); but pooled-15 still favors champion 199.3272 vs 199.7266.
- rule: overturn iff pooled and unbiased-fresh agree (as in the 4.0 correction); here they disagree, so the incumbent holds. Game-3 width 1.75-2.0 is an unresolved flat region.
- next: hunt genuinely new mechanisms; width/anchor/size grids are priced.

## 83 — tertile opener bold 14 (2026-10-03)
- commit: 19de5fa
- score: mean 231.2862 over seeds 0-4 (212.7246, 269.8169, 309.8821, 146.1475, 217.8597)
- champion mean: 217.5528 selection, 207.6291 pooled (f8ba828)
- verdict: discard
- what changed: opener drew from low-sigma tertile instead of the full pool.
- what you learned: cost about 13.73 with only seed 2 improving; the wild pool still binds tails and the anchor factorial holds under the confirmed shape.
- next: game-2 full-pool under confirmed shape (last factorial flip).

## 84 — game-2 full-pool factorial flip (2026-10-03)
- commit: 29f04b1
- score: mean 227.3810 over seeds 0-4 (172.3783, 251.5764, 436.6887, 99.7779, 176.4835)
- champion mean: 217.5528 selection, 207.6291 pooled (f8ba828)
- verdict: discard
- what changed: second 10p spread from the full pool instead of tertile anchors.
- what you learned: cost about 9.83 with seed 2 annihilated plus 71; game-2 needs rulers and the factorial holds everywhere.
- next: judge bold 14; then price the last micro (game-3 at 1.875).

## 85 — game-3 at 1.875 with confirmation (2026-10-03)
- commit: fde75b9
- score: selection mean 216.0193 over seeds 0-4 (175.6384, 247.2637, 366.3196, 106.9506, 183.9240)
- prior champion selection mean: 217.5528 (f8ba828)
- confirmation: 195.5568 over seeds 5-9 (143.2776, 232.2666, 224.3151, 218.3629, 159.5618), two of five improve
- pooled: 205.7881 vs 207.6291
- verdict: keep
- what changed: third bulk 10p widened from 1.75 to 1.875 sigma.
- what you learned: leads selection, held-out, and pooled among all game-3 widths; the closer optimum sits between 1.75 and 2.0. Bold 14 judged refuted (iter 83).
- next: game-3 at 1.9375 vs game-2 re-verification; judge nothing pending.

## 86 — game-3 at 1.9375 with confirmation (2026-10-03)
- commit: 4760b7f
- score: selection mean 214.4760 over seeds 0-4 (177.7716, 241.3754, 364.9481, 105.5051, 182.7796)
- champion selection mean: 216.0193 (fde75b9)
- confirmation: 198.1826 over seeds 5-9 (151.1533, 235.2076, 227.5195, 212.4973, 164.5351) vs champion held-out 195.5568
- verdict: discard
- what changed: third bulk 10p widened from 1.875 to 1.9375 sigma.
- what you learned: won selection by 1.54 but lost held-out by 2.63 with only seed 8 improving; game-3 stays 1.875 on both sets.
- next: game-2 re-verification at 1.25 under the 1.875 closer, then a fresh hunt.

## 87 — game-2 1.375 under 1.875 closer (2026-10-03)
- commit: 7d96fbc
- score: selection mean 213.9205 over seeds 0-4 (177.3174, 240.0184, 360.7257, 107.1993, 184.3415)
- champion selection mean: 216.0193 (fde75b9)
- confirmation: 205.3343 over seeds 5-9 (147.4663, 244.4770, 240.6447, 222.9550, 171.1286) vs champion held-out 195.5568
- verdict: discard
- what changed: second bulk 10p widened from 1.25 to 1.375 sigma under the 1.875 closer.
- what you learned: won selection by 2.10 but lost held-out by 9.78 with every seed regressing; game-2 stays 1.25 with no closer interaction.
- next: hunt outside the priced grids; misses at 86-87 need bold 15 after one more miss.

## 88 — zoom-down rest bold 15 (2026-10-03)
- commit: 6322377
- score: mean 225.9928 over seeds 0-4 (191.1595, 267.8123, 366.8229, 116.6210, 187.5485)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: games 2 and 3 swapped to 1.875 then 1.25 sigma.
- what you learned: cost about 9.97 with every seed regressing; the valley shape is real and monotone zoom loses everywhere.
- next: flat narrow rest (1.25/1.25) to test the valley's second wall.

## 89 — flat narrow rest 1.25 1.25 (2026-10-03)
- commit: de29969
- score: selection mean 215.7012 over seeds 0-4 (175.4163, 243.5805, 357.6261, 114.3843, 187.4988)
- champion selection mean: 216.0193 (fde75b9)
- confirmation: 201.1719 over seeds 5-9 (149.2020, 239.9402, 234.7598, 220.3959, 161.5618) vs champion held-out 195.5568
- verdict: discard
- what changed: third bulk 10p narrowed from 1.875 to 1.25 sigma.
- what you learned: won selection by 0.32 but lost held-out by 5.62 with every seed regressing; game-3 width does real work and the valley wall holds both sides. Bold 15 judged refuted (iter 88).
- next: hunt outside priced space; the valley (4.0/1.25/1.875) stands on all sets.

## 90 — game-2 at 1.1875 (2026-10-03)
- commit: ed581e4
- score: mean 217.4318 over seeds 0-4 (182.1040, 244.0566, 369.0152, 108.4709, 183.5122)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: second bulk 10p narrowed from 1.25 to 1.1875 sigma.
- what you learned: cost about 1.41 with seed 0 regressing hard; game-2 stays 1.25, bisection between rejected and confirmed loses.
- next: game-3 at 1.8125 (bisect 1.75/1.875); misses at 89-90 need bold 16 after one more miss.

## 91 — game-3 at 1.8125 (2026-10-03)
- commit: f9961ac
- score: mean 216.0851 over seeds 0-4 (170.5843, 245.2475, 366.2536, 112.3918, 185.9484)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: third bulk 10p narrowed from 1.875 to 1.8125 sigma.
- what you learned: cost about 0.07, a pure tie with seeds 0 and 3 canceling; game-3 1.75-1.875 is a flat floor and the incumbent holds.
- next: bold 16 territory (three straight misses at 89-91); hunt outside priced space.

## 92 — flat wide rest bold 16 (2026-10-03)
- commit: 186baa6
- score: mean 224.1766 over seeds 0-4 (186.6358, 267.6313, 357.4990, 121.7213, 187.3958)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: second bulk 10p widened from 1.25 to 1.875 sigma, matching the closer.
- what you learned: cost about 8.16 with only seed 2 improving; the valley dip is load-bearing and the shape matrix is complete.
- next: game-2 at 1.5 under the 1.875 closer (last interaction cell).

## 93 — game-2 1.5 under 1.875 closer (2026-10-03)
- commit: 14bddad
- score: mean 223.3639 over seeds 0-4 (174.1631, 264.7603, 371.9219, 120.3137, 185.6604)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: second bulk 10p widened from 1.25 to 1.5 sigma under the 1.875 closer.
- what you learned: cost about 7.34 with only seed 0 improving; 1.5 stays buried under both closers and no interaction exists.
- next: judge bold 16; opener 3.9375 micro or a fresh-seed re-audit.

## 94 — opener 3.9375 (2026-10-03)
- commit: 4fcb700
- score: mean 218.6019 over seeds 0-4 (185.9470, 240.7955, 363.0244, 118.4585, 184.7840)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: unfiltered opener narrowed from 4.0 to 3.9375 sigma.
- what you learned: cost about 2.58; opener stays 4.0 with both neighbors losing. Bold 16 judged refuted (iter 92).
- next: fresh-seed re-audit of the champion trio on seeds 10-14.

## Audit — champion trio on fresh seeds 10-14 (2026-10-03)
- champion fde75b9 (4.0/1.25/1.875): 97.0886, 176.4728, 131.3679, 172.4405, 316.0416, mean 178.6823
- prior audit: 1.75-closer 182.7235, 2.0-closer 179.0148
- verdict: champion leads fresh by 0.33 over 2.0 and 4.04 over 1.75; leads selection, held-out, fresh, and pooled-15 (196.7528 vs 199.7266) alike.
- what you learned: the 1.875 adoption survives unbiased seeds; the closer optimum is confirmed on all four sets.
- next: game-2 audit on fresh seeds (1.25 vs 1.5) or continued micros.

## Audit — game-2 on fresh seeds 10-14 (2026-10-03)
- champion fde75b9 (4.0/1.25/1.875): 178.6823 (97.0886, 176.4728, 131.3679, 172.4405, 316.0416)
- rival game-2 at 1.5: 94.7198, 182.2700, 138.9612, 165.9140, 310.9104, mean 178.5551
- verdict: fresh tie (rival by 0.13, 3 of 5 seeds); selection under the current closer favors 1.25 by 7.34. Incumbent holds on disagreement.
- what you learned: game-2 1.25-1.5 is flat on fresh seeds; the 1.25 edge lives in selection sets.
- next: iteration 95 micros or a new-mechanism hunt.

## 95 — game-3 at 1.5 last ladder cell (2026-10-03)
- commit: 0ef1ef6
- score: mean 219.2739 over seeds 0-4 (178.0474, 237.9156, 371.1181, 126.9078, 182.3804)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: third bulk 10p narrowed from 1.875 to 1.5 sigma.
- what you learned: cost about 3.25 with seed 3 regressing hard; the game-3 ladder is complete (1.25/1.5/1.625 lose below, 1.9375/2.0/2.5 lose above).
- next: opener 4.0625 micro or accept convergence.

## 96 — hollow opener valley rest bold 17 (2026-10-03)
- commit: e7c9da6
- score: mean 271.4244 over seeds 0-4 (293.9090, 306.7966, 343.6187, 182.2101, 230.5874)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: opener targets replaced with 8 edge quantiles plus one center pin.
- what you learned: cost about 55.41 with every seed regressing; middle thresholds load-bearing under every rest shape, division of labor refuted twice.
- next: judge bold 17; then dense-edge opener (keep middle, add reach).

## 97 — edge-heavy opener grid (2026-10-03)
- commit: d9a0ada
- score: mean 239.5498 over seeds 0-4 (212.1871, 269.8966, 363.0465, 142.7078, 209.9110)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: opener targets redistributed to dense edges plus sparse middle.
- what you learned: cost about 23.53 with only seed 2 improving; uniform grid stands and edge-redistribution loses. Bold 17 judged refuted (iter 96).
- next: hunt outside priced space; grids join the priced list.

## 98 — split closer 5p 5p bold 18 (2026-10-03)
- commit: d287976
- score: mean 258.2711 over seeds 0-4 (254.3655, 219.4137, 467.9758, 145.0036, 204.5967)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: third 10p split into two 5p spreads at 1.875 sigma.
- what you learned: cost about 42.25 with only seed 1 improving; 5p looks stay weak and the mid-schedule update does not compensate.
- next: split game-2 (5p+5p mid) or judge bold 18 after 100.

## 99 — split game-2 5p 5p (2026-10-03)
- commit: 228a606
- score: mean 289.0826 over seeds 0-4 (270.3518, 345.4033, 398.0208, 177.0332, 254.6039)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: second 10p split into two 5p spreads at 1.25 sigma.
- what you learned: cost about 73.06 with every seed regressing; the split family is dead in both positions.
- next: judge bold 18; iteration 100 should be commemorative micros.

## 100 — opener 4.0625 (2026-10-03)
- commit: a1d4b4a
- score: mean 220.4016 over seeds 0-4 (184.4040, 247.7915, 373.9161, 113.0384, 182.8581)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: unfiltered opener widened from 4.0 to 4.0625 sigma.
- what you learned: cost about 4.38 with only seed 4 improving; opener 4.0 interior-confirmed at plus-minus 0.0625. Bold 18 judged refuted (iter 98).
- next: coronation audit on seeds 15-19, then take stock at 100.

## Coronation — champion on virgin seeds 15-19 (2026-10-03)
- champion fde75b9 (4.0/1.25/1.875): 250.8330, 126.2147, 151.3831, 135.2721, 350.1666, mean 202.7739
- pooled-20: 198.2581 (selection 216.0193, held-out 195.5568, fresh-10-14 178.6823, virgin 202.7739)
- verdict: unbiased estimate sits inside the historical band; no correction indicated.
- take stock at 100: baseline 323.15 to 198.26 pooled (−39%). All grids priced. Loop continues on micros.

## 101 — game-3 1.8125 two-set judging (2026-10-03)
- commit: a0fb27f
- score: selection mean 216.0851, bit-identical to iter 91 (determinism revalidated)
- champion selection mean: 216.0193 (fde75b9)
- confirmation: 196.9430 over seeds 5-9 (145.3681, 229.0438, 233.5192, 213.8992, 162.8847) vs champion held-out 195.5568
- verdict: discard
- what changed: nothing new, iter 91 re-run with the held-out judging it never got.
- what you learned: selection tie (+0.07) plus held-out loss (-1.39, seed 7 regresses 9); the flat floor stands under two-set judging.
- next: cross-bulk no-rematch valley (consensus structural candidate).

## 102 — cross-bulk no-rematch valley (2026-10-03)
- commit: 5b5795a
- score: mean 230.5171 over seeds 0-4 (206.0107, 260.1334, 349.1061, 144.5218, 192.8134)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: games 2 and 3 banned rematches of earlier games via a module-global used-set.
- what you learned: cost about 14.50 with only seed 2 improving; rematches are informative replicates and ruler-noise averaging beats novelty (audit showed 1.25/3.32 dups in games 2/3).
- next: flat-mid rest 1.5625 (shape-matrix cell).

## 103 — flat-mid rest 1.5625 (2026-10-03)
- commit: 8e7810c
- score: mean 219.7002 over seeds 0-4 (182.6892, 256.8485, 361.6279, 110.9494, 186.3858)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: games 2 and 3 both at 1.5625 sigma (valley midpoint).
- what you learned: cost about 3.68 with seeds 0/1 regressing hard; the valley dip is real and the shape book closes (flat-narrow, flat-mid, flat-wide, zoom all lose).
- next: game-2 1.125 under 1.875 closer (archivist revival).

## 104 — game-2 1.125 under 1.875 closer (2026-10-03)
- commit: 97497c0
- score: mean 220.0122, bit-identical to iter 80 down to all five seeds
- verdict: discard as duplicate
- what changed: nothing, this schedule is iter 80 (joint 1.125/1.875); the archivist misfiled it as unrun.
- what you learned: determinism catches duplicates for free; the 1.125 cell stands priced under both closers. Distrust revival claims without checking WORKLOG first.
- next: per-quantile mixed anchors (auctioneer S2).

## 105 — per-quantile mixed anchors (2026-10-03)
- commit: 94cf582
- score: mean 240.7458 over seeds 0-4 (210.9220, 288.2975, 382.4147, 123.6773, 198.4175)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: games 2 and 3 matched inner-5 targets to tertile rulers and outer-4 to the full pool.
- what you learned: cost about 24.73 with every seed regressing; even anchor-mixing disturbs the center and per-game tertile stands exact.
- next: opener 3.75 under valley rest (archivist revival).

## 106 — opener 3.75 valley rest (2026-10-03)
- commit: 85017db
- score: mean 221.2858 over seeds 0-4 (182.2724, 247.5781, 367.0126, 119.6627, 189.9031)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: unfiltered opener narrowed from 4.0 to 3.75 sigma under the valley rest.
- what you learned: cost about 5.27 with every seed regressing; 3.75 stays buried under valley rest too.
- next: closer 2.5 under 1.25-second (thinnest cell).

## 107 — closer 2.5 under 1.25-second (2026-10-03)
- commit: c941d88
- score: mean 226.4249 over seeds 0-4 (204.3684, 245.8382, 372.4298, 118.4229, 191.0654)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: third bulk 10p widened from 1.875 to 2.5 sigma.
- what you learned: cost about 10.41 with only seed 1 improving; the narrower game-2 licenses no wider closer and 1.875 stands.
- next: chase-combining repeat-wide 4.0/4.0/1.5 (info P1).

## 108 — chase-combining 4.0 4.0 1.5 bold 19 (2026-10-03)
- commit: 515b11f
- score: mean 247.2454 over seeds 0-4 (226.3645, 297.6859, 357.0346, 148.1914, 206.9504)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: second 10p widened from 1.25 to 4.0 tertile, closer narrowed to 1.5.
- what you learned: cost about 31.23 with only seed 2 improving; the second wide is redundant power and narrow game-2 precision is load-bearing.
- next: double-tap opener 4.0/4.0/1.25 (adversary S3).

## 109 — double-tap 4.0 4.0 1.25 (2026-10-03)
- commit: b4c1d90
- score: mean 266.9304 over seeds 0-4 (244.5168, 329.4581, 378.3816, 150.8265, 231.4689)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: second 10p widened to full-pool 4.0, closer narrowed to 1.25.
- what you learned: cost about 50.91 with every seed regressing; the second wide re-observes clones and the closer stays load-bearing for mids.
- next: judge bold 19 after 110; F1 Q2-half anchor ladder.

## 110 — F1 Q2-half anchor ladder (2026-10-03)
- commit: 741d1c4
- score: mean 224.7467 over seeds 0-4 (176.6317, 231.6618, 417.2515, 111.0835, 187.1049)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: second 10p drew from low-sigma half instead of tertile.
- what you learned: cost about 8.73 with seed 2 annihilated plus 51; half-pool destabilizes hard seeds and tertile stands exact everywhere. Bold 19 judged refuted (iter 108).
- next: stratified 3-3-3 closer (sports pots variant).

## 111 — stratified 3-3-3 closer (2026-10-03)
- commit: 094b582
- score: mean 220.0639 over seeds 0-4 (181.8501, 248.6786, 358.9378, 117.2064, 193.6464)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: game-3 forced 3 below plus 3 above current mu, filled to 9 with nearest.
- what you learned: cost about 4.04 with only seed 2 improving; greedy quantile pulls beat forced pots and balance is not the mechanism.
- next: game-2 halo mixture 5x1.25 plus 4x2.5 (adversary S2).

## 112 — game-2 halo mixture (2026-10-03)
- commit: 4ffe9fe
- score: mean 232.6411 over seeds 0-4 (202.0063, 282.1212, 346.3346, 128.3128, 204.4305)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: game-2 matched 5 inner targets at 1.25 sigma and 4 extreme targets at 2.5 sigma.
- what you learned: cost about 16.62 with only seed 2 improving; the halo widens too early and precision timing stays load-bearing.
- next: game-3 mixture 5x1.25 plus 4x2.5 (bayes P3).

## 113 — game-3 mixture 1.25 2.5 (2026-10-03)
- commit: 43f3e80
- score: selection mean 217.1112 (184.0853, 251.1838, 353.8683, 112.9795, 183.4390)
- champion selection mean: 216.0193 (fde75b9)
- confirmation: 198.4788 over seeds 5-9 (153.0889, 236.8875, 227.4818, 203.5922, 171.3436) vs champion held-out 195.5568
- verdict: discard
- what changed: closer matched 5 inner targets at 1.25 sigma and 4 extreme targets at 2.5 sigma.
- what you learned: thin selection margin triggered held-out, which lost by 2.92 (only seed 8 improved); pooled loses too. Mixtures dilute both regimes instead of averaging them.
- next: split-middle 10+5+5+10 valley halves (info/poker consensus).

## 114 — split-middle 10 5 5 10 (2026-10-03)
- commit: ad2e702
- score: mean 289.0826 over seeds 0-4 (270.3518, 345.4033, 398.0208, 177.0332, 254.6039)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: game-2 split into two 4-opponent halves at 1.25 sigma.
- what you learned: cost about 73.06 with every seed crushed; halves starve the mid re-aim and 9-pull density is load-bearing.
- next: ratio upshift 1.5/2.25 rest (info P4).

## 115 — ratio upshift 1.5 2.25 (2026-10-03)
- commit: 6317bea
- score: mean 218.4251 over seeds 0-4 (185.8180, 255.4500, 357.1285, 112.3661, 181.3629)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: rest widths scaled plus 20 percent at the fixed 2:3 ratio.
- what you learned: cost about 2.41 with seeds 0/1 regressing hard; shape is fixed and extra width re-opens settled bins.
- next: HARQ sigma-gated closer (info P3); then misses force bold 20.

## 116 — HARQ sigma-gated closer bold 20 (2026-10-03)
- commit: 0508aca
- score: mean 219.2764 over seeds 0-4 (176.4843, 249.7622, 364.7295, 114.2047, 191.2012)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: game-3 played 2.5 sigma iff live bot sigma exceeded 4.0, else 1.5.
- what you learned: cost about 3.26 with only seed 2 improving; the gate misfires and sigma carries no routable signal at this threshold.
- next: judge bold 20 after 119; tight early-position pool-gated opener.

## 117 — tight early-position opener (2026-10-03)
- commit: 29b60dc
- score: mean 229.0410 over seeds 0-4 (227.7676, 261.1941, 333.8154, 122.8509, 199.5769)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: pools under 90 opened 1.5 tertile instead of 4.0 full-pool.
- what you learned: cost about 13.02 with only seed 2 improving; early tight poisons the first 90 rulers and wide-first is load-bearing for the whole pool.
- next: judge bold 20 after 119; closest-cluster ring closer.

## 118 — closest-cluster ring closer (2026-10-03)
- commit: c141382
- score: mean 221.0464 over seeds 0-4 (194.1549, 254.4704, 350.5358, 111.4706, 194.6002)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: game-3 took the 9 nearest tertile rulers to current mu.
- what you learned: cost about 5.03 with only seed 2 improving; pure proximity is an echo chamber and quantile spread stays load-bearing.
- next: judge bold 20 after 119; mu-gated closer 2.5/1.5.

## 119 — mu-gated closer 2.5 1.5 (2026-10-03)
- commit: bc7a951
- score: selection mean 213.6388 (181.7657, 238.1884, 349.6149, 111.8939, 186.7310)
- champion selection mean: 216.0193 (fde75b9)
- confirmation: 205.0800 over seeds 5-9 (158.9426, 246.4376, 239.9315, 213.4289, 166.6592) vs champion held-out 195.5568
- verdict: discard
- what changed: game-3 played 2.5 sigma when |mu-25| exceeded 25, else 1.5.
- what you learned: selection won 2.38 on two seeds but held-out lost 9.52 with one of five; pooled loses 3.57. Same seed-2-driven noise signature; confirmation rule earns its keep. Bold 20 judged refuted (iter 116).
- next: undercut 0.75/2.75 rest (race A).

## 120 — undercut 0.75 2.75 (2026-10-03)
- commit: 1a0247f
- score: mean 218.8057 over seeds 0-4 (181.2841, 243.4736, 368.3991, 118.1018, 182.7701)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: rest widths pushed to 0.75 then 2.75 sigma.
- what you learned: cost about 2.79 with two of five improving; the exaggerated valley overshoots both ends and priced widths stand.
- next: overcut 3.0/1.0 rest (race B); then misses force bold 21.

## 121 — overcut 3.0 1.0 bold 21 (2026-10-03)
- commit: ed0b19f
- score: mean 244.1784 over seeds 0-4 (217.6853, 293.4024, 362.2129, 130.5422, 217.0491)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: rest widths inverted to 3.0 then 1.0 sigma.
- what you learned: cost about 28.16 with only seed 2 improving; the dip direction matters and inversion loses everywhere else.
- next: judge bold 21 after 124; quintile game-2 0.875 plus 1.0 closer.

## 122 — quintile game-2 0.875 plus 1.0 closer (2026-10-03)
- commit: 66bb2ee
- score: mean 220.4249 over seeds 0-4 (176.9225, 258.2944, 372.0459, 116.9369, 177.9246)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: game-2 drew quintile rulers at 0.875 sigma, closer narrowed to 1.0.
- what you learned: cost about 4.41 with one of five improving; stricter rulers exclude needed coverage and below-ladder widths under-reach.
- next: judge bold 21 after 124; edge-dense closer grid.

## 123 — edge-dense closer grid (2026-10-03)
- commit: 142588e
- score: mean 218.5588 over seeds 0-4 (183.2471, 243.1468, 354.9069, 118.7610, 192.7324)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: closer targets doubled edge pins instead of uniform deciles.
- what you learned: cost about 2.54 with two of five improving; edge pins misfire on seeds 0/3/4 and the uniform grid stands.
- next: judge bold 21 after 124; senior-tertile anchors.

## 124 — senior-tertile anchors (2026-10-03)
- commit: 09a26bf
- score: mean 219.2273 over seeds 0-4 (186.3281, 251.2434, 352.2962, 120.6850, 185.5838)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: discard
- what changed: tertile anchors excluded the 50 most recent arrivals.
- what you learned: cost about 3.21 with only seed 2 improving; recent rulers carry live information and quarantine starves coverage. Bold 21 judged refuted (iter 121).
- next: jittered-grid diagnostic; then misses force bold 22.

## 125 — jittered-grid diagnostic (2026-10-03)
- commit: 651ce90
- score: selection mean 216.6464 (183.9223, 240.9799, 360.6715, 116.9437, 180.7148)
- champion selection mean: 216.0193 (fde75b9)
- confirmation: 202.3828 over seeds 5-9 (155.8424, 238.1242, 243.9655, 209.4249, 164.5570) vs champion held-out 195.5568
- verdict: discard
- what changed: per-bot grid phase shift from hashed mu/sigma.
- what you learned: selection tied plus 0.63 but held-out lost 6.83 with one of five; pooled loses too. Grid phase retires as a non-axis.
- next: fixed absolute-site opener (expected kill); then misses force bold 22.

## 126 — fixed-site opener (2026-10-03)
- commit: 34222d4
- score: mean 219.3309 over seeds 0-4 (206.3181, 250.9592, 337.9293, 122.5391, 178.9089)
- champion mean: 216.0193 selection, 205.7881 pooled (fde75b9)
- verdict: tuning (per persistence rule: big change, wild seed split, needs repairs before judging)
- what changed: game-1 matched fixed absolute sites across [-50,100] instead of case-centered 4.0 spread.
- what you learned: seed 2 improves 28 but seed 0 regresses 31; fixed [-50,100] wastes pulls on empty extremes when the pool is small. Repair first: span sites to the observed pool range.
- next: pool-range census sites (tuning 126b).

## 127 — pool-range census opener tuning 126b (2026-10-03)
- commit: 73f8050
- score: selection mean 199.7520 (148.7059, 230.0787, 326.1673, 119.9127, 173.8954)
- champion selection mean: 216.0193 (fde75b9)
- confirmation: 180.3568 over seeds 5-9 (142.2694, 206.0317, 221.8561, 176.3427, 155.2841) vs champion held-out 195.5568
- fresh audit: 161.7721 over seeds 10-14 (86.1849, 166.3903, 116.7974, 156.1757, 283.3121) vs champion fresh 178.6823
- verdict: keep, new champion
- what changed: game-1 matches pool-range census sites instead of fixed [-50,100]; bot-independent opener, case-centered valley rest unchanged.
- what you learned: repair turned plus 3.31 into minus 16.27 on selection; all three seed sets agree (14 of 15 seeds), pooled-15 180.6270 vs 196.7528. Bot-independent range coverage beats case-centered wide-first; persistence rule paid off. Seed 3 the lone selection regressor.
- next: judge bold 21 after 124 (done, refuted); probe why seed 3 resists; census-site count and spacing tuning.

## 128 — trimmed census p5-p95 tuning 126c (2026-10-03)
- commit: 89fb9fe
- score: selection mean 195.9377 (149.4642, 221.1885, 329.8018, 111.1905, 168.0434)
- champion selection mean: 199.7520 (73f8050)
- confirmation: 180.3129 over seeds 5-9 (135.0277, 208.9699, 222.1165, 180.4099, 155.0404) vs champion held-out 180.3568
- fresh audit: 162.5885 over seeds 10-14 (90.2587, 169.8062, 122.5009, 154.1512, 276.2254) vs champion fresh 161.7721
- verdict: discard
- what changed: census sites spanned pool p5-p95 instead of min-max.
- what you learned: selection won 3.81 and fixed seed 3, but held-out tied and fresh lost 0.82; pooled-15 wins ~1 point yet fresh vetoes per the overturn rule. Trimming trades tail coverage for outlier-robustness at net wash.
- next: census-site count tuning (fewer sites for small pools); recency-filtered tertile.

## 129 — double-skeleton census tuning 126d (2026-10-03)
- commit: 85a1a1e
- score: mean 252.9078 over seeds 0-4 (233.3291, 304.7799, 360.1735, 156.3136, 209.9429)
- champion mean: 199.7520 selection, 190.0544 pooled (73f8050)
- verdict: discard
- what changed: game-2 also played pool-range census instead of 1.25 spread.
- what you learned: cost about 53.16 with every seed regressing; game-2 personalization timing is load-bearing and one skeleton suffices.
- next: census-site count for small pools (tuning 126e); then misses force bold 22.

## 130 — positional adaptive cluster bold 22 (2026-10-03)
- commit: d6856ec
- score: mean 232.9551 over seeds 0-4 (212.4043, 273.9898, 335.3456, 142.9434, 200.0923)
- champion mean: 199.7520 selection, 190.0544 pooled (73f8050)
- verdict: discard
- what changed: game-3 played full-pool 2.5 when the bot sat over one pool-sigma from the pool median.
- what you learned: cost about 33.20 with every seed regressing; routing stays dead under census too and position carries no routable signal.
- next: judge bold 22 after 133; mark-recapture closer.

## 131 — mark-recapture closer (2026-10-03)
- commit: 4c8a1d4
- score: mean 235.8667 over seeds 0-4 (203.8758, 282.8012, 389.6561, 111.8930, 191.1075)
- champion mean: 199.7520 selection, 190.0544 pooled (73f8050)
- verdict: discard
- what changed: game-3 took 4 nearest tertile rulers plus 5 fresh outside-tertile beats.
- what you learned: cost about 36.11 with only seed 3 improving; fresh beats are noisy and the quantile grid stays load-bearing.
- next: judge bold 22 after 133; DPP repulsion de-collision.

## 132 — DPP repulsion games 2 3 (2026-10-03)
- commit: d5067b5
- score: selection mean 193.5777 (157.8178, 246.3507, 294.7531, 111.8003, 157.1667)
- champion selection mean: 199.7520 (73f8050)
- confirmation: 185.7001 over seeds 5-9 (153.3610, 200.3117, 232.6634, 173.4521, 168.7121) vs champion held-out 180.3568
- verdict: discard
- what changed: games 2 and 3 excluded rulers within 1.0 mu of already-picked ones.
- what you learned: selection won 6.17 on three seeds but held-out lost 5.34 with two of five; pooled ties plus 0.42. Same seed-2-driven signature; de-collision displaces needed thresholds.
- next: judge bold 22 after 133; repechage positional rescue.

## 133 — recency-filtered tertile (2026-10-03)
- commit: 5faf0b0
- score: selection mean 197.7410 (148.5257, 223.5037, 319.8536, 125.7155, 171.1066)
- champion selection mean: 199.7520 (73f8050)
- confirmation: 177.2165 over seeds 5-9 (137.8447, 199.8749, 219.3511, 174.2210, 154.7910) vs champion held-out 180.3568
- fresh audit: 158.5081 over seeds 10-14 (89.3912, 160.3722, 115.3804, 155.4522, 271.9445) vs champion fresh 161.7721
- verdict: keep, new champion
- what changed: tertile anchors drawn from the last 400 arrivals only.
- what you learned: all three sets agree, 13 of 15 seeds, pooled-15 177.8219 vs 180.6270. Old rulers go stale as anchors; the pool skeleton keeps improving while settled mus calcify. Bold 22 judged refuted (iter 130); repechage filed as its duplicate without running.
- next: recency-window tuning (200/600); census-site count for small pools.

## 134 — recency window 200 (2026-10-03)
- commit: 4ff2b08
- score: mean 229.6038 over seeds 0-4 (192.1119, 215.5058, 380.8239, 181.1587, 178.4189)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: anchor window narrowed from last-400 to last-200.
- what you learned: cost about 31.86 with only seed 1 improving and seed 2 annihilated plus 61; 200 starves the anchor pool on hard seeds.
- next: recency window 600 (tuning 133c).

## 135 — recency window 600 (2026-10-03)
- commit: bea0086
- score: mean 199.5438 over seeds 0-4 (146.3129, 227.7538, 324.3291, 122.7230, 176.6003)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: anchor window widened from last-400 to last-600.
- what you learned: cost about 1.80 with two of five improving; 600 dilutes recency and 400 stands as the window.
- next: census-site count for small pools (tuning 126e); then misses force bold 23.

## 136 — game-2 1.5 census regime (2026-10-03)
- commit: 7b7eac4
- score: mean 199.7993 over seeds 0-4 (158.6921, 232.6396, 317.6425, 115.1030, 174.9193)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: game-2 widened from 1.25 to 1.5 under the census opener.
- what you learned: cost about 2.06 with two of five improving; the rest optimum did not shift and 1.25 stands under census too.
- next: closer re-resolution under census (tuning 133e); then misses force bold 23.

## 137 — 8p-band sizes bold 23 (2026-10-03)
- commit: 0349827
- score: mean 268.3113 over seeds 0-4 (242.5680, 323.6615, 364.5916, 182.4328, 228.3025)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: four slimmer games (7+7+7+5 opponents) at champion widths.
- what you learned: cost about 70.57 with every seed regressing; per-game pull density wins and rhythm loses.
- next: judge bold 23 after 140; closer re-resolution under census (tuning 133e).

## 138 — closer 1.75 census (2026-10-03)
- commit: ad0069d
- score: selection mean 196.9624 (154.1240, 226.9506, 315.6396, 119.6134, 168.4844)
- champion selection mean: 197.7410 (5faf0b0)
- confirmation: 176.9551 over seeds 5-9 (140.6488, 192.9347, 223.8837, 176.4434, 150.8650) vs champion held-out 177.2165
- fresh audit: 160.3749 over seeds 10-14 (91.5043, 160.5469, 124.5884, 156.1891, 269.0459) vs champion fresh 158.5081
- verdict: discard
- what changed: closer narrowed from 1.875 to 1.75 under the census opener.
- what you learned: selection and held-out both favored 1.75 thinly but fresh lost 1.87 with one of five; pooled-15 loses 0.28. Fresh vetoes per the overturn rule; 1.875 stands under census too.
- next: judge bold 23 after 140; NYSE-close 2.25 tertile.

## 139 — NYSE-close 2.25 (2026-10-03)
- commit: 5d56ee8
- score: mean 198.3079 over seeds 0-4 (155.2421, 222.7220, 331.7847, 115.9131, 165.8777)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: closer widened from 1.875 to 2.25 tertile.
- what you learned: cost about 0.57 with three of five improving but seed 2 regressing 12; wide re-open after narrow game-2 loses on hard seeds.
- next: judge bold 23 after 140; valley-repriced closing duel (expected kill).

## 140 — closing duel 10 10 8 2 (2026-10-03)
- commit: c6ee93d
- score: mean 205.3830 over seeds 0-4 (166.5029, 242.1317, 335.0699, 121.8061, 161.4042)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: closer split into 7-pull 1.875 plus a final closest duel.
- what you learned: cost about 7.64 with only seed 4 improving; the duel book closes again and 9-pull closer density is load-bearing. Bold 23 judged refuted (iter 137).
- next: triage rapids 2+2+2+10+10+4 (expected kill).

## 141 — triage rapids 2 2 2 10 10 4 (2026-10-03)
- commit: 47d3f88
- score: mean 297.7350 over seeds 0-4 (288.6015, 347.0571, 353.5471, 218.9023, 280.5669)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: three opening duels, then census 10p, 1.25 10p, 1.875 4-pull closer.
- what you learned: cost about 100 with every seed crushed; prior-conditioning duels poison everything and bulks need the full budget.
- next: misses force bold 24; census-site spacing (center-dense vs edge-dense).

## 142 — recency-without-census bold 24 (2026-10-03)
- commit: bb20798
- score: mean 213.7231 over seeds 0-4 (174.3347, 242.0297, 355.3109, 109.3530, 187.5870)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: old 4.0 full-pool opener with recent-tertile rest.
- what you learned: cost about 15.98 with only seed 3 improving; recency alone gains ~2.3 over iter-85 while census plus recency gains ~18.3. Census carries the gain and recency sweetens it.
- next: judge bold 24 after 145; census-site spacing center-dense vs edge-dense.

## 143 — edge-dense census sites (2026-10-03)
- commit: a3518e8
- score: mean 241.3143 over seeds 0-4 (221.9917, 276.1001, 352.3573, 139.4152, 216.7073)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: census sites doubled edge pins instead of uniform spacing.
- what you learned: cost about 43.57 with every seed regressing; extreme noise dominates coverage and uniform spacing stands.
- next: judge bold 24 after 145; center-dense census sites (mirror test).

## 144 — center-dense census sites (2026-10-03)
- commit: 2d7df1f
- score: mean 381.4656 over seeds 0-4 (453.8583, 307.0414, 443.8386, 227.7468, 474.8430)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: census sites clustered to the middle 40 percent of the pool range.
- what you learned: cost about 184, worst spacing result on record; abandons the range coverage that drives the win. Spacing triptych complete: uniform wins, both extremes fail.
- next: judge bold 24 after 145; bookend skeleton census games 1+3.

## 145 — bookend skeleton census 1 3 (2026-10-03)
- commit: 568f2a7
- score: mean 223.4607 over seeds 0-4 (186.9383, 234.7910, 382.0785, 136.9044, 176.5911)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: game-3 played pool-range census instead of 1.875 spread.
- what you learned: cost about 25.72 with zero of five improving; the closer must personalize and a skeleton close wastes the refine. Bold 24 judged refuted (iter 142).
- next: census-plus-personal blend opener (tuning 126h); then misses force bold 25.

## 146 — blend opener 126h (2026-10-03)
- commit: 1c03fb8
- score: mean 270.7089 over seeds 0-4 (291.9749, 204.7498, 535.0515, 151.7841, 169.9844)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: game-1 mixed 5 census sites with 4 case-centered 4.0 pulls.
- what you learned: cost about 73 with seed 2 annihilated plus 215; personal pulls re-poison the skeleton and pure census stands.
- next: misses force bold 25; senior-tertile under census (retest).

## 147 — ancient-tertile bold 25 (2026-10-03)
- commit: 67c33f8
- score: mean 202.9325 over seeds 0-4 (149.8157, 230.3329, 327.3526, 130.2190, 176.9423)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: tertile anchors drawn from the first 400 arrivals.
- what you learned: cost about 5.19 with zero of five improving; recency direction is real and old anchors calcify.
- next: judge bold 25 after 150; senior-tertile under census (retest).

## 148 — senior-tertile census retest (2026-10-03)
- commit: ebeeb5f
- score: mean 197.7251 over seeds 0-4 (149.3191, 222.2601, 320.3183, 124.2503, 172.4779)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard as tie
- what changed: recent-tertile anchors excluded the 50 most recent arrivals.
- what you learned: margin 0.02 with two of five improving; quarantine changes nothing under census either and ties keep the incumbent.
- next: judge bold 25 after 150; quintile anchors under census (retest).

## 149 — quintile game-2 census retest (2026-10-03)
- commit: e19551b
- score: mean 199.4144 over seeds 0-4 (148.9262, 227.1346, 343.5536, 122.3404, 155.1172)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: game-2 drew quintile rulers at 1.25 sigma.
- what you learned: cost about 1.67 with two of five improving and seed 2 regressing 24; stricter rulers still exclude needed coverage under census.
- next: judge bold 25 after 150; half anchors under census (retest).

## 150 — half anchors census retest (2026-10-03)
- commit: 734941a
- score: mean 209.5181 over seeds 0-4 (151.4788, 223.6963, 406.5608, 104.9293, 160.9255)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: game-2 drew half rulers at 1.25 sigma.
- what you learned: cost about 11.78 with two of five improving and seed 2 annihilated plus 87; half still destabilizes hard seeds under census. Bold 25 judged refuted (iter 147).
- next: no-rematch under census (retest); then misses force bold 26.

## 151 — no-rematch census retest (2026-10-03)
- commit: 4ec19ab
- score: mean 203.4688 over seeds 0-4 (209.8697, 261.9779, 237.7019, 127.4776, 180.3168)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: games 2 and 3 banned rematches via a module-global used-set.
- what you learned: cost about 5.73 with only seed 2 improving (minus 88 there); banning the shared skeleton starves refinement and replicates stay informative.
- next: misses force bold 26; stratified closer under census (retest).

## 152 — stratified closer census bold 26 (2026-10-03)
- commit: 8db12b0
- score: mean 206.8766 over seeds 0-4 (163.2668, 235.0701, 334.6076, 131.5662, 169.8723)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: game-3 forced 3 below plus 3 above current mu, filled to 9 with nearest.
- what you learned: cost about 9.14 with only seed 4 improving; greed stands and forced balance loses with fresh anchors too.
- next: judge bold 26 after 155; halo mixture game-3 under census (retest).

## 153 — halo game-3 census retest (2026-10-03)
- commit: 1de24be
- score: selection mean 195.6969 (162.8354, 224.0302, 317.4241, 115.3265, 158.8683)
- champion selection mean: 197.7410 (5faf0b0)
- confirmation: 174.2527 over seeds 5-9 (141.2324, 196.3899, 215.0552, 165.5047, 153.0812) vs champion held-out 177.2165
- fresh audit: 159.9336 over seeds 10-14 (91.1017, 175.4374, 118.6434, 154.3851, 260.1002) vs champion fresh 158.5081
- verdict: discard
- what changed: closer matched 5 inner targets at 1.25 sigma and 4 extreme targets at 2.5 sigma.
- what you learned: selection and held-out both favored the mixture but fresh lost 1.43 with two of five; pooled-15 wins 1.19 yet fresh vetoes per the overturn rule. Second fresh veto for mixtures.
- next: judge bold 26 after 155; split-middle under census (retest).

## 154 — split-middle census retest (2026-10-03)
- commit: af098dc
- score: mean 273.5230 over seeds 0-4 (240.1423, 325.9661, 383.0585, 175.7755, 242.6728)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: game-2 split into two 4-opponent halves at 1.25 sigma.
- what you learned: cost about 75.78 with every seed regressing; halves starve the re-aim under census too and 9-pull density stands.
- next: judge bold 26 after 155; flat-mid rest under census (retest).

## 155 — flat-mid census retest (2026-10-03)
- commit: cc679fe
- score: mean 204.2161 over seeds 0-4 (166.4686, 226.1975, 338.8368, 117.2543, 172.3232)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: games 2 and 3 both at 1.5625 sigma.
- what you learned: cost about 6.48 with only seed 3 improving; the valley dip is real under census too. Bold 26 judged refuted (iter 152).
- next: ratio upshift under census (retest); then misses force bold 27.

## 156 — ratio upshift census retest (2026-10-03)
- commit: 0594487
- score: mean 198.2817 over seeds 0-4 (161.7505, 235.2713, 307.6345, 115.4203, 171.3319)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: rest widths scaled to 1.5 then 2.25 sigma.
- what you learned: cost about 0.54 with three of five improving but seeds 0/1 regressing hard; extra width re-opens settled bins under census too.
- next: misses force bold 27; per-quantile mixed anchors under census (retest).

## 157 — skeleton-second bold 27 (2026-10-03)
- commit: 91f09ff
- score: mean 272.3998 over seeds 0-4 (256.9225, 322.1529, 388.2075, 158.4564, 236.2598)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: case-centered 4.0 game-1, census game-2, 1.875 closer.
- what you learned: cost about 74.66 with every seed regressing; early skeleton timing is load-bearing and late coverage cannot repair a poisoned start.
- next: judge bold 27 after 160; per-quantile mixed anchors under census (retest).

## 158 — per-quantile mixed census retest (2026-10-03)
- commit: e3d89e6
- score: mean 212.8337 over seeds 0-4 (181.7046, 247.2153, 366.9344, 98.7569, 169.5571)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: games 2 and 3 matched inner targets to recency tertile and outer targets to the full pool.
- what you learned: cost about 15.09 with two of five improving and seeds 0/1/2 regressing hard; anchor-mixing still disturbs the center.
- next: judge bold 27 after 160; tight early-position under census (retest).

## 159 — tight early census retest (2026-10-03)
- commit: e789050
- score: mean 207.9749 over seeds 0-4 (203.8317, 235.0106, 316.8599, 113.3624, 170.8101)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: pools under 90 opened 1.5 tertile instead of census.
- what you learned: cost about 10.23 with three of five improving but seed 0 annihilated plus 55; early census for small pools matters and tight-early poisons the foundation.
- next: judge bold 27 after 160; undercut rest under census (retest).

## 160 — undercut census retest (2026-10-03)
- commit: a8629f6
- score: selection mean 190.5645 (153.9065, 216.8040, 315.7089, 118.4350, 147.9681)
- champion selection mean: 197.7410 (5faf0b0)
- confirmation: 175.8423 over seeds 5-9 (140.6238, 194.3027, 232.4284, 165.1034, 146.7532) vs champion held-out 177.2165
- fresh audit: 159.9654 over seeds 10-14 (101.3035, 177.1042, 115.6635, 154.2468, 251.5089) vs champion fresh 158.5081
- verdict: discard
- what changed: rest widths pushed to 0.75 then 2.75 sigma.
- what you learned: selection won 7.18 and held-out won 1.37 but fresh lost 1.46 with seeds 7/10/11 regressing hard; pooled-15 wins 2.36 yet fresh vetoes. The exaggerated valley is seed-fragile. Bold 27 judged refuted (iter 157).
- next: overcut rest under census (retest); then misses force bold 28.

## 161 — overcut census retest (2026-10-03)
- commit: 52e5559
- score: mean 230.8843 over seeds 0-4 (202.7991, 276.5662, 330.4988, 136.1680, 208.3893)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: rest widths inverted to 3.0 then 1.0 sigma.
- what you learned: cost about 33.14 with zero of five improving; inversion loses under census too and dip direction stands confirmed.
- next: misses force bold 28; chase-combining under census (retest).

## 162 — wide-second skeleton bold 28 (2026-10-03)
- commit: b9d6f1f
- score: mean 259.3278 over seeds 0-4 (243.1342, 308.6750, 364.9644, 156.5428, 223.3226)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: census opener, full-pool 4.0 game-2, 1.5 closer.
- what you learned: cost about 61.59 with every seed regressing; wide re-observe stays redundant after any skeleton.
- next: judge bold 28 after 165; double-tap census under census (retest).

## 163 — DPP census retest (2026-10-03)
- commit: a275e19
- score: mean 199.0069 over seeds 0-4 (172.4176, 236.3517, 302.8221, 118.7453, 165.6980)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: games 2 and 3 excluded rulers within 1.0 mu of already-picked ones.
- what you learned: cost about 1.27 with three of five improving but seeds 0/1 regressing hard; de-collision still displaces needed thresholds. Note: 200-bot quick matched iter-132 code bit-identically (game-1 rarely binds differently at small pools); full runs diverge properly.
- next: judge bold 28 after 165; mark-recapture under census (retest).

## 164 — mark-recapture census retest (2026-10-03)
- commit: 8cd9eed
- score: mean 235.2649 over seeds 0-4 (205.7786, 282.7948, 386.8603, 111.5144, 189.3766)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: game-3 took 4 nearest recency rulers plus 5 fresh outside beats.
- what you learned: cost about 37.52 with only seed 3 improving; fresh beats are noisy under census too.
- next: judge bold 28 after 165; ring closer under census (retest).

## 165 — ring closer census retest (2026-10-03)
- commit: 1b664cb
- score: mean 207.0027 over seeds 0-4 (170.0855, 237.7435, 326.0768, 124.7858, 176.3221)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: game-3 took the 9 nearest recency rulers to current mu.
- what you learned: cost about 9.26 with only seed 3 improving; proximity stays an echo chamber under census. Bold 28 judged refuted (iter 162).
- next: edge-dense closer under census (retest); then misses force bold 29.

## 166 — edge-dense closer census retest (2026-10-03)
- commit: be1f83a
- score: selection mean 196.4037 (154.9306, 219.8363, 328.9402, 115.9324, 162.3789)
- champion selection mean: 197.7410 (5faf0b0)
- confirmation: 176.4300 over seeds 5-9 (138.8372, 193.8538, 223.0692, 175.9542, 150.4354) vs champion held-out 177.2165
- fresh audit: 159.0896 over seeds 10-14 (90.5502, 172.3770, 117.5565, 151.9718, 262.9923) vs champion fresh 158.5081
- verdict: discard
- what changed: closer targets doubled edge pins instead of uniform deciles.
- what you learned: selection and held-out both favored edge pins thinly but fresh lost 0.58 with seed 11 regressing 6; pooled-15 wins 0.51 yet fresh vetoes. Fourth fresh veto; uniform grid stands confirmed.
- next: misses force bold 29; F1 Q2-half ladder under census (retest).

## 167 — F1 ladder stillborn duplicate (2026-10-03)
- commit: 0212daf
- score: none (duplicate caught by bit-identical quick 277.3875)
- verdict: stillborn
- what changed: nothing, the schedule duplicates iter 150 (census opener is full-pool; half game-2 plus 1.875 closer).
- what you learned: determinism catches duplicates before full runs; check WORKLOG compositionally (census equals full-pool anchor) not just by label.
- next: misses force a real bold 29; chase-combining under census.

## 168 — chase census bold 29 (2026-10-03)
- commit: 38febaa
- score: mean 236.2941 over seeds 0-4 (204.8877, 279.0377, 338.6049, 141.5260, 217.4140)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: census opener, tertile 4.0 game-2, 1.5 closer.
- what you learned: cost about 38.55 with zero of five improving; wide stays redundant with settled rulers too.
- next: judge bold 29 after 171; double-tap under census.

## 169 — double-tap census (2026-10-03)
- commit: c103203
- score: mean 256.4387 over seeds 0-4 (242.5555, 315.0962, 358.7818, 145.5765, 220.1833)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: census opener, full-pool 4.0 game-2, 1.25 closer.
- what you learned: cost about 58.70 with every seed regressing; the second wide re-observes clones under census too.
- next: judge bold 29 after 171; halo game-2 under census.

## 170 — halo game-2 census (2026-10-03)
- commit: 81ae84a
- score: mean 220.8627 over seeds 0-4 (174.4641, 272.7090, 329.0324, 128.6227, 199.4855)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: game-2 matched 5 inner targets at 1.25 sigma and 4 extreme targets at 2.5 sigma.
- what you learned: cost about 23.12 with zero of five improving; the halo widens too early under census too.
- next: judge bold 29 after 171; quintile-0.875 combo under census (last open row).

## 171 — quintile-0.875 census (2026-10-03)
- commit: cdac921
- score: mean 204.8743 over seeds 0-4 (154.1628, 217.9350, 360.6005, 123.3677, 168.3056)
- champion mean: 197.7410 selection, 187.4788 pooled (5faf0b0)
- verdict: discard
- what changed: game-2 drew quintile rulers at 0.875 sigma, closer narrowed to 1.0.
- what you learned: cost about 7.13 with three of five improving but seed 2 annihilated plus 41; strictest rulers under-reach on hard seeds. Bold 29 judged refuted (iter 168). Backlog zero open rows.
- next: fresh brainstorm needed; declare convergence if nothing new.

## Iter 172: equal-area census (carto S1)
- Score: sel 209.9581 (174.90, 232.37, 347.24, 110.75, 184.54) vs champ 197.7410 (+12.22). Only seed 3 improves.
- Verdict: DISCARD. Uniform-of-range spacing stands; pool-mass spacing wastes looks in clumps.
- Learned: opener geometry settled further; try sinh-warp next (keeps uniform base, smooth tail emphasis).
- Next: iter 173 sinh-warped census.

## Iter 173: sinh-warped census (carto S2)
- Score: sel 214.7910 (181.69, 231.51, 347.81, 133.09, 179.86) vs champ 197.7410 (+17.05). All seeds regress.
- Verdict: DISCARD. Even center-preserving tail emphasis loses; uniform-of-range exact.
- Learned: opener site geometry closed (uniform > quantile > sinh); try bell-projection then move on.
- Next: iter 174 bell-projection census.

## Iter 174: bell-projection census (carto S3)
- Score: sel 210.6309 (165.23, 235.83, 341.38, 128.31, 182.41) vs champ 197.7410 (+12.89).
- Verdict: DISCARD. Opener site geometry closed: uniform 197.74 > quantile 209.96 > bell 210.63 > sinh 214.79.
- Learned: cartographer family done save re-projected game-2 (different axis: timing not geometry).
- Next: iter 175 mercy-rule clipping (referee S2, novel axis).

## Iter 175: mercy-rule clipping (referee S2) — STILLBORN
- Bind rate 3.5% of targets yet greedy match bit-identical to iter-174 on seeds 0 and 2.
- Verdict: STILLBORN per 167 rule (reverted, no full runs). Used-set already spreads void looks; clipping adds nothing.
- Learned: discrete matching absorbs small target shifts; target-side micro-fixes are dead unless they change matches.

## Iter 176: damped undercut 1.0/2.375 (archivist2 S1)
- Score: sel 196.5615 vs 197.7410 (-1.18, seeds 0/2 regress +7.6/+5.5); held 177.6734 vs 177.2165 (+0.46).
- Verdict: DISCARD. Confirmation fails; undercut direction seed-fragile at both amplitudes.
- Learned: undercut family closed (0.75 and 1.0 both vetoed); valley dip direction settled at 1.25.
- Next: iter 177 halo-lite closer.

## Iter 177: halo-lite closer (archivist2 S2)
- Score: sel 195.4937 vs 197.7410 (-2.25) but seed 2 regresses +10.3; held 177.8594 vs 177.2165 (+0.64).
- Verdict: DISCARD. Held-out vetoes; easy-seed gains fund hard-seed losses, the 160/166 disease.
- Learned: mixture/edge family closed (153 halo, 166 edge, 177 halo-lite all vetoed). No further mixture variants.
- Next: iter 178 integral residual closer (control S2, novel center axis).

## Iter 178: integral residual closer (control S2)
- Score: sel 214.8565 (188.62, 242.76, 338.07, 132.10, 172.74) vs champ 197.7410 (+17.11). All seeds regress.
- Verdict: DISCARD. Outward kick extrapolates past tails; integrator windup in the open loop too.
- Learned: spread CENTER must stay on bot mu (outward dead); inward receiver-centering (seismo S4) is the remaining center cell.
- Next: iter 179 receiver-centered closer.

## Iter 179: receiver-centered closer (seismo S4)
- Score: sel 198.3764 vs 197.7410 (+0.64); seed 1 -16.5 but seed 2 +20.3, seeds 0/3 regress.
- Verdict: DISCARD. Recenter chases noise; no drift-correction signal in G2 landing.
- Learned: spread-center axis closed (outward 178, receiver 179). Center stays on bot mu.
- Next: iter 180 antipodal closer (period review at 180).

## Iter 180: antipodal closer (seismo S1) + PERIOD REVIEW
- Score: sel 261.2163 (246.03, 299.52, 375.07, 169.94, 215.51) vs champ 197.7410 (+63.48). Every seed crushed.
- Verdict: DISCARD. Forcing distance destroys the grid; proximity is load-bearing, not incidental.
- PERIOD REVIEW (172-180, second wave): 9 tests, all discard/stillborn. Site geometry (quantile/sinh/bell) closed.
  Center axis (kick/recenter) closed. Crossing-antipodal dead. Mixture third veto. Survivor: mirror-cross
  (preserves greedy distances) + cohort-cartel + derby-day + survey/calibration + Kelly/E1-E4 + S3/S4 scheduled.
- Learned: greedy nearest-to-uniform-target is the mechanism; every displacement scheme pays.
- Next: iter 181 mirror-cross closer.

## Iter 181: mirror-cross closer (seismo S2)
- Score: sel 199.6217 (169.61, 232.50, 316.57, 116.76, 162.66) vs champ 197.7410 (+1.88). Seed 0 +21.1.
- Verdict: DISCARD. Opposite-side forcing displaces needed thresholds despite matched ranges.
- Learned: crossing family closed (antipodal 180, mirror 181). Same-side greed stands.
- Next: iter 182 cohort-cartel breaker (librarian S4).

## Iter 182: cohort-cartel breaker (librarian S4)
- Score: sel 199.6775 (159.40, 242.35, 310.19, 115.00, 171.45) vs champ 197.7410 (+1.94).
- Verdict: DISCARD. Forcing vintage spread costs proximity on seeds 0/1; seed 2/3 gains don't compensate.
- Learned: error axis is threshold position, not arrival vintage. Librarian family done save survey.
- Next: iter 183 survey closer.

## Iter 183: survey closer (librarian S3 proxy)
- Score: sel 226.5246 (184.18, 220.80, 398.35, 143.73, 185.56) vs champ 197.7410 (+28.78). Seed 2 +78.5.
- Verdict: DISCARD. Shared yardstick fails: closer must personalize; seed-specific drift is the load, not noise.
- Learned: librarian family closed (authority needs plumbing; cohort/survey dead as proxies).
- Next: iter 184 known-good calibration game-2 (crypto S2).

## Iter 184: calibration game-2 (crypto S2)
- Score: sel 250.3945 vs champ 197.7410 (+52.65). All seeds regress.
- Verdict: DISCARD. Bot-independent game-2 burns the re-aim window; calibration without targeting is noise.
- Learned: every game must target the bot; bot-independence only works for the census skeleton.
- Next: iter 185 scheduled re-widen 2.0 (control S1) + period review at 185.

## Iter 185: scheduled re-widen 2.0 (control S1) + PERIOD REVIEW
- Score: sel 195.3167 (-2.42, 4/5 improve); held 177.0116 (-0.20); fresh 159.7510 (+1.24 veto); pooled-15 177.3598 vs 177.8219 (-0.46).
- Verdict: DISCARD per overturn rule (pooled wins, fresh disagrees -> incumbent stands, 1.75-closer precedent).
- PERIOD REVIEW (181-185): mirror, cohort, survey, calibration, re-widen — all discard. Fresh vetoes again (185).
  Remaining open: derby-day, home/away, round-robin, moveout, checksum, insurance, Kelly, E1/E2, dither,
  clipped-undercut, senior-25, mu-gate, split-closer, re-projected-G2, bell/sinh followups (dead), halo (dead).
- Learned: 1.875 closer confirmed on 3 sets jointly (2.0 re-opens settled bins on fresh seeds).
- Next: iter 186 derby-day closer (referee S4).

## Iter 186: derby-day closer (referee S4)
- Score: sel 198.8222 (161.08, 224.60, 324.52, 120.54, 163.37) vs champ 197.7410 (+1.08).
- Verdict: DISCARD. Representation pins cost precision; all 9 closer looks must personalize.
- Learned: bookend axis dead in both strengths (full 145, lite 186). Referee family: home/away + round-robin left.
- Next: iter 187 home/away split (referee S3).

## Iter 187: home/away split (referee S3)
- Score: sel 228.8651 vs champ 197.7410 (+31.12). All seeds regress.
- Verdict: DISCARD. Forcing fresh rulers into every game poisons both refine stages.
- Learned: tertile purity stands; any crew-mixing (vintage 182, home/away 187) loses big.
- Next: iter 188 round-robin whistle (referee S1).
