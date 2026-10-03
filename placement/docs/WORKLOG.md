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
