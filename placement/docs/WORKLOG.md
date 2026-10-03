# Worklog

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

## 1 — duel the highest sigma opponent (2026-10-03)
- commit: 244a46b
- score: mean 30.4425 over seeds 0-4 (31.0441, 31.2195, 30.0309, 29.8662, 30.0520)
- champion mean: 28.9678 (cf594fd, baseline row)
- verdict: discard
- what changed: dueled the most uncertain pool opponent instead of the closest mu.
- what you learned: chasing sigma cost about 1.47 mean error; uncertain opponents are often misrated newcomers, so updates are noisier than evenly matched duels.
- next: duel the strongest pool estimate.

## 2 — duel the strongest pool estimate (2026-10-03)
- commit: 6a22f9f
- score: mean 36.2194 over seeds 0-4 (36.8132, 36.5501, 35.9308, 35.5078, 36.2949)
- champion mean: 28.9678 (cf594fd)
- verdict: discard
- what changed: dueled the highest-mu pool opponent every game instead of the closest mu.
- what you learned: always playing the best cost about 7.25 mean error; one-sided matchups carry almost no information about the new bot's level.
- next: all duels versus mixed FFA schedule.

## 3 — full-budget FFA-10 versus closest mus (2026-10-03)
- commit: 295530c
- score: mean 20.3876 over seeds 0-4 (18.7491, 22.0658, 23.0779, 18.0182, 20.0270)
- champion mean: 20.3876 (295530c, new best; prior 28.9678 cf594fd)
- verdict: keep (new champion)
- what changed: every game takes the 9 closest-mu pool opponents, spending 30 slots on 3 ten-player games.
- what you learned: comparison efficiency beats update count by about 8.58 mean error; seed spread (18.02 to 23.08) is wider than the baseline, so later mixes should chase stability too.
- next: duels first, then FFA with late budget.

## 4 — duels first, then FFA with late budget (2026-10-03)
- commit: 7e70bcb
- score: mean 16.6448 over seeds 0-4 (16.0763, 17.9013, 18.6619, 14.4283, 16.1560)
- champion mean: 16.6448 (7e70bcb, new best; prior 20.3876 295530c)
- verdict: keep (new champion)
- what changed: 5 closest-mu duels on the first 10 slots, then two FFA-10s against the 9 closest opponents.
- what you learned: positioning mu with early sequential duels before bulk FFA updates gained about 3.74 mean error over pure FFA-10.
- next: size from budget_left — big games early, duels late (mirror schedule).

## 5 — big games early, duels late (2026-10-03)
- commit: 7486a9f
- score: mean 22.0400 over seeds 0-4 (22.4263, 20.0545, 30.9643, 18.4762, 18.2788)
- champion mean: 16.6448 (7e70bcb)
- verdict: discard
- what changed: two FFA-10s on the first 20 slots, then closest-mu duels on the last 10 (mirror of iteration 4).
- what you learned: order matters more than the mix; unpositioned early FFAs waste comparisons and seed 2 blew up to 30.96, so late bulk updates need an already-placed mu.
- next: judge bold line 1 and refine the champion split (duel/FFA slot boundary).

## 6 — champion split with 3 duels then FFA bulk (2026-10-03)
- commit: ff659d3
- score: mean 17.4371 over seeds 0-4 (16.8072, 18.0924, 21.3628, 14.9999, 15.9230)
- champion mean: 16.6448 (7e70bcb)
- verdict: discard
- what changed: cut the duel phase to 3 games (boundary 24), leaving 24 slots for FFA bulk.
- what you learned: fewer positioning duels cost about 0.79 mean error and seed 2 regressed to 21.36, so 5 duels position mu better than 3.
- next: champion split with 7 duels then FFA bulk (boundary 16).

## 7 — champion order with spread FFA opponents (2026-10-03)
- commit: f2a2568
- score: mean 16.0723 over seeds 0-4 (15.4395, 17.3075, 18.7232, 13.3421, 15.5492)
- champion mean: 16.0723 (f2a2568, new best; prior 16.6448 7e70bcb)
- verdict: keep (new champion)
- what changed: kept duels-first order but picked FFA opponents at quantiles of N(mu, sigma) with low-sigma tiebreaks instead of closest mus.
- what you learned: threshold spread gained about 0.57 mean error; 4 of 5 seeds improved, so spread opponents bound mu better than a clustered field.
- next: full Approach 3 schedule (10p, 6p, then duels) with spread opponents.

## 8 — Approach 3 schedule exact with spread opponents (2026-10-03)
- commit: 490e97a
- score: mean 19.7573 over seeds 0-4 (19.4066, 19.1767, 24.2760, 18.1491, 17.7780)
- champion mean: 16.0723 (f2a2568)
- verdict: discard
- what changed: large-first 10p then 6p with quantile-spread opponents, duels last.
- what you learned: large-first loses with or without spread (19.76 vs 16.07) and seed 2 blew up to 24.28 again; duels-first ordering is confirmed, so the outside advice optimises a different objective (final sigma, not mu error).
- next: Approach 2 schedule (10p, 5p, 5p, then duels) or refine champion duel count/spread width.

## 9 — sandwich duels, spread FFA, precision duels (2026-10-03)
- commit: 5cc4575
- score: mean 17.0155 over seeds 0-4 (16.1090, 17.7366, 19.8270, 14.6591, 16.7458)
- champion mean: 16.0723 (f2a2568)
- verdict: discard
- what changed: 5 duels, one spread FFA-10, then 5 closest-mu precision duels on the last 10 slots.
- what you learned: swapping the second FFA for late duels cost about 0.94 mean error; bulk comparisons fix bias better than precision duels on this objective.
- next: refine champion spread width (0.5 and 1.5 sigma).

## 10 — champion spread width 0.5 sigma (2026-10-03)
- commit: ed16c5d
- score: mean 16.3460 over seeds 0-4 (15.6233, 17.4027, 19.0588, 14.0089, 15.6361)
- champion mean: 16.0723 (f2a2568)
- verdict: discard
- what changed: shrank FFA opponent spread from quantiles of N(mu, sigma) to N(mu, 0.5 sigma).
- what you learned: tighter late thresholds cost about 0.27 mean error with seed 2 regressing to 19.06; the wider 1.0 spread bounds outliers better.
- next: champion spread width 1.5 sigma (wider late thresholds).

## 11 — champion spread width 1.5 sigma (2026-10-03)
- commit: cef8296
- score: mean 16.1694 over seeds 0-4 (16.2593, 17.7112, 17.5223, 13.7726, 15.5818)
- champion mean: 16.0723 (f2a2568)
- verdict: discard
- what changed: widened FFA opponent spread from quantiles of N(mu, sigma) to N(mu, 1.5 sigma).
- what you learned: wider spread fixed seed 2 (17.52 vs 18.72) but cost seeds 0-1, net about 0.10 worse; 1.0 sigma is the balanced width.
- next: champion duel count 7 (boundary 16) with 10p plus 6p late.

## 12 — champion duel count 7 with 10p plus 6p late (2026-10-03)
- commit: 1cab46b
- score: mean 18.5864 over seeds 0-4 (21.8836, 18.0122, 20.4557, 16.1167, 16.4637)
- champion mean: 16.0723 (f2a2568)
- verdict: discard
- what changed: 7 positioning duels (boundary 16), leaving 10p plus 6p late instead of two 10ps.
- what you learned: shrinking late bulk cost about 2.51 mean error; two full 10ps beat extra duels plus a 6p, so late bulk size is critical.
- next: low-sigma-preferring duel opponents, or FFA opponent sets anchored on low-sigma pool only.

## 13 — Approach 1 pipeline with percentile brackets (2026-10-03)
- commit: 51b0a25
- score: mean 18.9461 over seeds 0-4 (19.5732, 19.4488, 19.8527, 18.0747, 18.7813)
- champion mean: 16.0723 (f2a2568)
- verdict: discard
- what changed: bold test of the full outside pipeline: percentile duels, 5p cluster, decile 10p, tight 5p, precision duels.
- what you learned: tightest seed spread yet (18.07 to 19.85) but about 2.87 worse in level; uncentered percentile/decile opponents waste the positioning that centered spreads exploit. Process: ruff-format can fail a commit after reformatting, so verify HEAD moved and re-commit.
- next: Approach 2 schedule, or low-sigma-only FFA anchors.

## 14 — champion with 5th duel moved late (2026-10-03)
- commit: b84ad7f
- score: mean 16.3484 over seeds 0-4 (16.0680, 16.8062, 19.6667, 14.3478, 14.8534)
- champion mean: 16.0723 (f2a2568)
- verdict: discard
- what changed: 4 early duels, two spread 10ps, then 1 closest-mu duel on the last 2 slots.
- what you learned: moving the 5th duel late cost about 0.28 mean error with seed 2 regressing to 19.67; all 5 positioning duels belong up front.
- next: low-sigma-only FFA anchors, or Approach 2 schedule.

## 15 — low-sigma-only FFA anchors (2026-10-03)
- commit: 2d70af7
- score: mean 15.8333 over seeds 0-4 (14.0025, 17.0179, 19.2571, 14.3675, 14.5216)
- champion mean: 15.8333 (2d70af7, new best; prior 16.0723 f2a2568)
- verdict: keep (new champion)
- what changed: spread FFA opponents must come from the low-sigma half of the pool, falling back to the full pool when too few qualify.
- what you learned: established anchors gained about 0.24 mean error; seeds 0/3/4 improved clearly while seed 2 barely moved, so anchor quality helps typical bots most.
- next: low-sigma-only duel opponents, or Approach 2 schedule.

## 16 — low-sigma-only duel opponents (2026-10-03)
- commit: bb12e0b
- score: mean 16.5232 over seeds 0-4 (16.3568, 17.0247, 18.7203, 15.0118, 15.5025)
- champion mean: 15.8333 (2d70af7)
- verdict: discard
- what changed: restricted duel opponents to the low-sigma half of the pool, same as the FFA anchors.
- what you learned: duel anchors cost about 0.69 mean error; early positioning needs mu-closeness more than anchor certainty, while late thresholds need the reverse.
- next: mid-size late games (4x5p instead of 2x10p).

## 17 — mid-size late games 4x5p spread (2026-10-03)
- commit: 4db400c
- score: mean 20.3905 over seeds 0-4 (20.5200, 21.4683, 21.4389, 18.2434, 20.2817)
- champion mean: 15.8333 (2d70af7)
- verdict: discard
- what changed: kept 5 positioning duels but played four spread 5p games late instead of two spread 10ps.
- what you learned: 4-look updates cost about 4.56 mean error versus 9-look ones despite double the updates; late bulk size dominates update count.
- next: other mid sizes (4p, 6p, 8p) or 10p plus 2x5p late mixes.

## 18 — late mix 10p then two 5ps (2026-10-03)
- commit: 68d0be9
- score: mean 16.0973 over seeds 0-4 (15.2965, 17.1124, 19.3189, 13.7855, 14.9730)
- champion mean: 15.8333 (2d70af7)
- verdict: discard
- what changed: kept 5 duels and the first 10p, but split the second 10p into two spread 5ps.
- what you learned: splitting only the second 10p cost about 0.26 mean error; every 10p split tried so far hurts, so full-size late bulk is the stable optimum.
- next: 6p/8p spot checks, or sigma-triggered duel-to-FFA switch.

## 19 — sigma-triggered duel-to-FFA switch (2026-10-03)
- commit: 1fcf6d5
- score: mean 28.6144 over seeds 0-4 (29.2866, 29.7541, 27.9897, 27.6633, 28.3783)
- champion mean: 15.8333 (2d70af7)
- verdict: discard
- what changed: dueled while bot sigma stayed above 5.0, spread FFA otherwise, with no budget boundary.
- what you learned: sigma almost never falls below 5.0, so this played near-all-duels (28.61 vs all-duel baseline 28.97); thresholds need measured sigma trajectories, not guesses.
- next: probe sigma after N duels, then retry the trigger at a measured level.

## 20 — bookend FFAs with duels between (2026-10-03)
- commit: 8044b13
- score: mean 19.4223 over seeds 0-4 (19.7350, 17.4701, 25.6917, 17.1323, 17.0826)
- champion mean: 15.8333 (2d70af7)
- verdict: discard
- what changed: 10p spread opener, 5 closest-mu duels, 10p spread closer.
- what you learned: the opener cost about 3.59 mean error with seed 2 at 25.69; an early unpositioned FFA drags mu somewhere the follow-up duels cannot recover from.
- next: 5p opener variant, or duel-opponent offsets and rematch rules.

## 21 — deep positioning 10 duels then one 10p (2026-10-03)
- commit: 2b7727a
- score: mean 18.3799 over seeds 0-4 (17.8754, 18.4674, 20.6487, 16.8597, 18.0483)
- champion mean: 15.8333 (2d70af7)
- verdict: discard
- what changed: bold line 2 test, 10 closest-mu duels then a single spread 10p on the last 10 slots.
- what you learned: halving bulk cost about 2.55 mean error and the seed-2 gap widened to 20.65, so depth cannot replace the second bulk update; bold line 2 is refuted.
- next: judge bold 2 after iter 23, meanwhile duel-opponent offsets or rematch breadth.

## 22 — stricter tertile anchors (2026-10-03)
- commit: d792747
- score: mean 15.1426 over seeds 0-4 (14.0574, 16.9858, 16.4868, 13.2970, 14.8860)
- champion mean: 15.1426 (d792747, new best; prior 15.8333 2d70af7)
- verdict: keep (new champion)
- what changed: FFA anchor pool tightened from the low-sigma half to the low-sigma tertile.
- what you learned: cleaner thresholds gained about 0.69 mean error with seed 2 collapsing from 19.26 to 16.49; hard seeds were poisoned by mid-sigma opponents.
- next: even stricter anchors (quartile), and judge bold 2 after iter 23.

## 23 — quartile anchors (2026-10-03)
- commit: dabab04
- score: mean 15.2101 over seeds 0-4 (14.2127, 16.8737, 17.2649, 13.3459, 14.3532)
- champion mean: 15.1426 (d792747)
- verdict: discard
- what changed: FFA anchor pool tightened from the low-sigma tertile to the quartile.
- what you learned: quartile cost about 0.07 with seed 2 regressing to 17.26; the tertile balances threshold cleanliness against pool breadth.
- next: duel-count re-check at tertile anchors (4 or 6 duels), or 8p late bulk.

## 24 — 4 early plus 1 late duel retest (2026-10-03)
- commit: 51768e4
- score: mean 16.4204 over seeds 0-4 (15.7205, 17.0245, 19.0967, 15.0268, 15.2337)
- champion mean: 15.1426 (d792747)
- verdict: discard
- what changed: retried 4 early duels plus 1 late duel around two spread 10ps, now under tertile anchors.
- what you learned: the late duel still cost about 1.28 with seed 2 back at 19.10; late single looks destabilize hard seeds under any anchor rule.
- next: 6-duel opener, or probe where the remaining error concentrates.

## 25 — wide-then-narrow late FFAs (2026-10-03)
- commit: 067b331
- score: mean 14.8370 over seeds 0-4 (13.7425, 16.1204, 16.3392, 13.0445, 14.9386)
- champion mean: 14.8370 (067b331, new best; prior 15.1426 d792747)
- verdict: keep (new champion)
- what changed: first late 10p spreads anchors at N(mu, sigma), second tightens to N(mu, 0.5 sigma).
- what you learned: bound-then-refine gained about 0.31 with 4 of 5 seeds improving; the second FFA works better as a precision instrument than a second bound.
- next: width pairs around it (1.5/0.5, 1.0/0.3), or 6-duel opener.

## 26 — refine width 0.3 sigma (2026-10-03)
- commit: 5a362ea
- score: mean 15.2847 over seeds 0-4 (13.6544, 17.1910, 16.4306, 13.7159, 15.4318)
- champion mean: 14.8370 (067b331)
- verdict: discard
- what changed: second late FFA tightened from N(mu, 0.5 sigma) to N(mu, 0.3 sigma).
- what you learned: extra-tight refine cost about 0.45 with seeds 1 and 4 regressing; 0.5 keeps enough threshold breadth for the second look.
- next: bound width 1.5 with refine 0.5, or 6-duel opener.

## 27 — bound width 1.5 sigma (2026-10-03)
- commit: 14f0f83
- score: mean 14.9433 over seeds 0-4 (13.5724, 16.8481, 15.7891, 12.9882, 15.5187)
- champion mean: 14.8370 (067b331)
- verdict: discard
- what changed: first late FFA widened from N(mu, sigma) to N(mu, 1.5 sigma), refine fixed at 0.5.
- what you learned: wider bound cost about 0.11 net with seed 2 improving but seeds 1 and 4 regressing; 1.0 is the balanced bound width.
- next: 6-duel opener, or asymmetric bound for edge bots.

## 28 — 3 duels plus 4p bridge plus two 10ps (2026-10-03)
- commit: 7669007
- score: mean 15.2384 over seeds 0-4 (13.9724, 16.8346, 16.3326, 13.1993, 15.8530)
- champion mean: 14.8370 (067b331)
- verdict: discard
- what changed: 3 positioning duels, one spread 4p bridge, then 1.0-sigma and 0.5-sigma 10ps.
- what you learned: the 4p bridge cost about 0.40 net; fewer duels hurt more than a transition game helps.
- next: 6 duels plus 8p plus 10p, then 6 duels plus 10p plus 8p.

## 29 — dim-2 sweep B 6 duels 8p 10p (2026-10-03)
- commit: 53b5fca
- score: mean 16.8185 over seeds 0-4 (16.2288, 18.0913, 17.9690, 14.8103, 16.9929)
- champion mean: 14.8370 (067b331)
- verdict: discard
- what changed: dimension-2 only, 6 closest duels then spread 8p at 1.0 sigma then spread 10p at 0.5 sigma, opponent rules fixed.
- what you learned: extra duel plus smaller first bulk cost about 1.98; the first bulk game wants the full 10 seats.
- next: dim-2 sweep C, 6 duels plus 10p plus 8p.

## 30 — dim-2 sweep C 6 duels 10p 8p (2026-10-03)
- commit: 21a397e
- score: mean 15.6025 over seeds 0-4 (14.5647, 16.8330, 17.0597, 13.4606, 16.0945)
- champion mean: 14.8370 (067b331)
- verdict: discard
- what changed: dimension-2 only, 6 closest duels then spread 10p at 1.0 sigma then spread 8p at 0.5 sigma.
- what you learned: cost about 0.77 with seeds 1/2/4 regressing; across the sweep (A 15.24, B 16.82, C 15.60) every move from 5 duels plus two full 10ps hurts, so the size schedule is a robust optimum.
- next: back to dimension 1, probe-informed ideas for extreme bots.

## 31 — edge-conditional narrow bound (2026-10-03)
- commit: 91c0074
- score: mean 14.9736 over seeds 0-4 (13.7425, 16.5938, 16.5891, 13.0040, 14.9386)
- champion mean: 14.8370 (067b331)
- verdict: discard
- what changed: first late FFA narrowed to 0.5 sigma whenever bot mu sat outside the anchor mu range.
- what you learned: two seeds came out bit-identical and the mean cost about 0.14; after 5 duels bot mu sits inside the anchor range almost always, so threshold clustering is not the extreme-error driver.
- next: duel heterogeneity (bracket duels 4-5), or accept the extreme floor.

## 32 — bracket duels 4-5 (2026-10-03)
- commit: 0c332f6
- score: mean 15.0209 over seeds 0-4 (13.4684, 16.8905, 16.6369, 12.8460, 15.2628)
- champion mean: 14.8370 (067b331)
- verdict: discard
- what changed: duels 1-3 stayed closest-mu, duels 4-5 bracketed with the nearest above then below.
- what you learned: bracketing cost about 0.18 with seeds 1/2/4 regressing; symmetric closest duels position better than forced asymmetry.
- next: accept the extreme floor, or candidates-promoted alternates.

## 33 — inverted widths narrow then wide (2026-10-03)
- commit: 23ca1c6
- score: mean 15.3179 over seeds 0-4 (14.3032, 16.5516, 16.3780, 14.1952, 15.1617)
- champion mean: 14.8370 (067b331)
- verdict: discard
- what changed: first late FFA at 0.5 sigma, second at 1.0 sigma.
- what you learned: inverted order cost about 0.48 with seeds 1/3/4 regressing; bound-then-refine beats refine-then-bound, so the wide game must come first.
- next: first-duel versus established median, or candidates-track alternates.

## 34 — interleaved bulk 3d 10p 2d 10p (2026-10-03)
- commit: 09ab49e
- score: mean 14.8462 over seeds 0-4 (13.4802, 15.7403, 16.9839, 13.8977, 14.1287)
- champion mean: 14.8370 (067b331)
- verdict: discard
- what changed: 3 duels, wide 10p, 2 repositioning duels, narrow 10p.
- what you learned: missed by 0.009 with seeds 0/3/4 level and 1/2 worse; 5 positioning duels total is what matters, split or upfront.
- next: first-duel versus established median, or pool-service game.

## 35 — sparsity fallback in spread (2026-10-03)
- commit: 2e64e03
- score: mean 16.2028 over seeds 0-4 (15.7610, 17.4979, 18.4609, 13.7258, 15.5682)
- champion mean: 14.8370 (067b331)
- verdict: discard
- what changed: per threshold, took a closer unrated pool member when the nearest anchor sat farther than 1 sigma.
- what you learned: cost about 1.37 with every seed regressing; unrated mus are unreliable thresholds even when nearer, so anchor reliability beats proximity.
- next: first-duel versus established median, or pool-service game.

## 36 — factorial S0xB1 no anchor filter (2026-10-03)
- commit: c411a66
- score: mean 16.2270 over seeds 0-4 (15.8540, 17.4213, 18.8015, 13.4905, 15.5675)
- champion mean: 14.8370 (067b331)
- verdict: discard
- what changed: factorial cell S0xB1, champion sizes with the tertile filter removed (tiebreaks only).
- what you learned: no filter cost about 1.39 with every seed regressing; the anchor filter is strongly load-bearing.
- next: factorial S1xB1 to test orthogonality.

## 37 — factorial S1xB1 no anchor filter (2026-10-03)
- commit: ac74aa2
- score: mean 16.3950 over seeds 0-4 (16.2868, 18.1202, 18.0790, 13.3153, 16.1737)
- champion mean: 14.8370 (067b331)
- verdict: discard
- what changed: factorial cell S1xB1, 3 duels plus 4p bridge plus two 10ps with no anchor filter.
- what you learned: completes the square (14.837, 16.227 / 15.238, 16.395); the no-filter penalty is +1.39 under S0 but +1.16 under S1, so the dimensions are near-orthogonal and single-side sweeps stay valid.
- next: first-duel versus established median, or pool-service game.

## 38 — first duel versus median anchor (2026-10-03)
- commit: 94b0359
- score: mean 15.0615 over seeds 0-4 (14.1481, 16.8617, 16.5148, 12.8330, 14.9497)
- champion mean: 14.8370 (067b331)
- verdict: discard
- what changed: opening duel played the pool median instead of the closest mu, rest champion.
- what you learned: cost about 0.22 with seeds 1/2/4 regressing; the closest opener positions better than any fixed anchor.
- next: pool-service game, the last bold candidate.
