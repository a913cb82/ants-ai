# Worklog

Add one entry for each iteration. Do not change an old entry.
The harness writes the score to `docs/PROGRESS.jsonl`. Copy that
score here. The harness also prints a `games:` summary line to copy
into the games field. The recorded score is the source of truth.

Use this format.

```
## <number> — <idea> (<date>)
- commit: <short sha>
- start: <commit or bot id>
- budget: 5 duels, 3 FFA
- score: mu <value>, sigma <value>, lb <value>
- champion lb: <value>
- verdict: keep | discard | bold
- games: <duels won>-<duels lost>, FFA ranks <size>p:<rank> ...
- what changed: <one sentence>
- what you learned: <one or two sentences>
- next: <one idea>
```

## Log

## 1 — closest food (2026-09-20)
- commit: d02ec94
- start: da4e859 (py3 starter copy)
- budget: 16 duels, FFA 4 to 10
- score: mu 35.94, sigma 3.49, lb 25.46
- champion lb: none (baseline)
- verdict: keep
- games: 11-5, FFA ranks 2, 2, 5, 3, 6, 1, 3
- what changed: Each ant moves to its nearest visible food with one-food-per-ant claiming and destination dedup, else steps n-e-s-w.
- what you learned: Food seeking beats the starter and sets lb 25.46 as champion; early losses to older autoresearch bots show movement still wastes turns on blocked paths.
- next: Collision — assign food to ants by global distance so no two ants chase the same region.
