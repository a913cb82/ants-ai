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
