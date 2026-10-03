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
