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

## 2 — collision via global food assignment (2026-09-20)
- commit: 9031b00
- start: d02ec94 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 43.73, sigma 4.94, lb 28.91
- champion lb: none (baseline)
- verdict: keep
- games: 5-0, FFA ranks 4p:1 6p:2 10p:3
- what changed: Sort all ant-food pairs by distance and claim greedily so the closest pairs win regardless of ant order.
- what you learned: Global assignment went 5-0 in duels and ranked 1/4, 2/6, 3/10 in FFA; exclusive claims beat per-ant greedy order on the new 5+3 budget and set lb 28.91 as baseline.
- next: Hill attack — attack an enemy hill with a local majority.

## 3 — hill attack with spare ants (2026-09-20)
- commit: 81771a1
- start: 9031b00 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 46.10, sigma 4.23, lb 33.39
- champion lb: 28.91
- verdict: keep
- games: 5-0, FFA ranks 5p:4 7p:1 8p:2
- what changed: Ants with no food claim step toward the nearest visible enemy hill before the n-e-s-w fallback.
- what you learned: Spare-ant hill hunting went 5-0 in duels and won the 7p FFA; unclaimed ants raze hills instead of walking n-e-s-w and lift lb from 28.91 to 33.39.
- next: Hill defense — keep ants near your hills when the enemy is close.

## 4 — hill defense with spare guards (2026-09-20)
- commit: 5478c43
- start: 81771a1 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 47.08, sigma 4.27, lb 34.28
- champion lb: 33.39
- verdict: keep
- games: 3-2, FFA ranks 4p:1 6p:1 10p:1
- what changed: Spare ants step toward a home hill with a visible enemy within 10 steps before hunting enemy hills.
- what you learned: Guards swept all three FFAs 1/4, 1/6, 1/10 but lost 2 maze duels to HoldBot and LeftyBot; holding hills wins crowded games and lifts lb from 33.39 to 34.28.
- next: Combat — do not move an ant into certain death.

## 5 — combat avoid certain death (2026-09-20)
- commit: 3fc5988
- start: 5478c43 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 52.78, sigma 4.04, lb 40.66
- champion lb: 34.28
- verdict: keep
- games: 5-0, FFA ranks 4p:4 6p:1 10p:1
- what changed: Every step needs a local majority (friends plus self outnumber enemies in attack range) or the ant holds instead of moving.
- what you learned: Caution went 5-0 in duels and won the 6p and 10p FFAs against three past champions; refusing 1v1 trades lifts lb from 34.28 to 40.66 despite a last-place 4p game.
- next: Exploration — send spare ants to unseen squares.
