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
