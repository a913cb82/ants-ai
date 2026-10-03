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
