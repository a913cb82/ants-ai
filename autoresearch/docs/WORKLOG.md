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

## 6 — exploration prefer unvisited squares (2026-09-20)
- commit: e830cd3
- start: 3fc5988 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 56.50, sigma 4.22, lb 43.82
- champion lb: 40.66
- verdict: keep
- games: 5-0, FFA ranks 4p:1 6p:1 10p:2
- what changed: The bot counts visits per square and orders the n-e-s-w fallback by least-visited first.
- what you learned: Spreading went 5-0 in duels and beat two past champions in the 6p FFA; unvisited-first fallback finds food and hills faster and lifts lb from 40.66 to 43.82.
- next: Flood — move a group of ants to one target.

## 7 — flood one enemy hill with attackers (2026-09-20)
- commit: a16039f
- start: e830cd3 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 49.64, sigma 3.92, lb 37.87
- champion lb: 43.82
- verdict: discard
- games: 4-1, FFA ranks 5p:1 7p:1 8p:4
- what changed: All hill attackers converge on the single enemy hill closest to any of my ants instead of each ant hunting its own nearest hill.
- what you learned: Flooding won the 5p and 7p FFAs but ranked 4/8 in the 8p and lost a duel to HunterBot; piling every attacker onto one hill leaves other hills and food open, so lb fell from 43.82 to 37.87.
- next: Food denial — hold a contested food field.

## 8 — food denial claim contested fields first (2026-09-20)
- commit: 4a8afa1
- start: e830cd3 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 49.36, sigma 3.79, lb 37.99
- champion lb: 43.82
- verdict: discard
- games: 4-1, FFA ranks 5p:1 7p:3 8p:4
- what changed: Battling as NoLunchForYou; foods with a visible enemy within 8 steps sort as 4 steps closer so our closest ants hold the contested field.
- what you learned: Denial won duels 4-1 and the 5p FFA but trailed two past champions in the 7p and 8p; the bonus pulls ants off nearby safe food into blocked 1v1s, so lb fell from 43.82 to 37.99.
- next: BOLD — two discards in a row, research a different design.

## 9 — bold pathfinding BFS first step (2026-09-20)
- commit: e18ca85
- start: e830cd3 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 50.06, sigma 4.03, lb 37.97
- champion lb: 43.82
- verdict: discard (bold 1 of 3)
- games: 5-0, FFA ranks 4p:1 6p:1 10p:5
- what changed: Battling as Cartographer in Cartographer.py; food and hill moves follow the first step of a BFS shortest path around water instead of a greedy compass step.
- what you learned: Pathfinding swept all 5 duels including 4 maze maps and won the 4p and 6p FFAs, but ranked 5/10 in a champion-heavy 10p; movement is fixed, positioning needs the bold follow-ups (remembered hills, walk-off, escape space).
- next: Remembered hills — keep enemy hill targets across turns.

## 10 — remembered hills across turns (2026-09-20)
- commit: bb19f16
- start: e18ca85 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 51.20, sigma 3.87, lb 39.60
- champion lb: 43.82
- verdict: discard (bold 2 of 3)
- games: 4-1, FFA ranks 5p:1 7p:1 8p:4
- what changed: Battling as Elephant in Elephant.py; sighted enemy hills persist until one of my ants stands on them, so attackers march through fog.
- what you learned: Memory won the 5p and a 7p stacked with four past selves but lost a duel to RandomBot and ranked 4/8 behind the champion; marching on stale hills wastes attackers when the fog hides the real fight.
- next: Walk off hill — never end a turn on your own hill (plus .bot filename sync).

## 11 — walk off own hill to keep spawn open (2026-09-20)
- commit: 858bf3b
- start: bb19f16 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 56.08, sigma 4.02, lb 44.03
- champion lb: 43.82
- verdict: keep (bold 3 of 3, line wins)
- games: 5-0, FFA ranks 4p:1 6p:1 10p:2
- what changed: Battling as NoCamping in NoCamping.bot + NoCamping.py; any ant still holding on a home hill after the main pass steps off s-e-w-n so the hill stays open for spawning.
- what you learned: Open hills swept duels 5-0 and both small FFAs and took 2nd in a GreedyBot-led 10p; the bold line (pathfinding, memory, walk-off) lifts lb from 43.82 to 44.03 and takes the crown.
- next: Escape space — among safe moves pick the most open space.
