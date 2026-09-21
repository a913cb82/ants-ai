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

## 12 — escape to most open space (2026-09-20)
- commit: 2f107a0
- start: 858bf3b (champion code)
- budget: 5 duels, 3 FFA
- score: mu 32.01, sigma 3.96, lb 20.12
- champion lb: 44.03
- verdict: discard
- games: 2-3, FFA ranks 5p:2 7p:4 8p:1
- what changed: Battling as Houdini in Houdini.bot + Houdini.py; the spare-ant fallback ranks safe exits by open space behind them (BFS 8, friends x3, enemies x-3) with visits only breaking ties.
- what you learned: Space-seeking lost twice to LeftyBot and fell to 4/7 in a weak 7p; ranking space above food-proximity wanders ants away from the economy, so lb collapsed from 44.03 to 20.12.
- next: Aggressive combat — trade 1-for-1 when 14+ friends near the fight.

## 13 — aggressive combat with 14+ friends near (2026-09-20)
- commit: 117f54a
- start: 858bf3b (champion code)
- budget: 5 duels, 3 FFA
- score: mu 61.04, sigma 3.83, lb 49.55
- champion lb: 44.03
- verdict: keep
- games: 5-0, FFA ranks 5p:1 7p:1 8p:1
- what changed: Battling as Berserker in Berserker.bot + Berserker.py; equal trades are accepted when 14+ friends stand within 10 steps, outnumbered moves still refused.
- what you learned: Controlled aggression swept every game including a 7p with five past selves and an 8p head-to-head over the champion; piling in with numbers lifts lb from 44.03 to 49.55.
- next: Hill-first order — hunt hills before food.

## 14 — hill-first attackers draft before food (2026-09-20)
- commit: 190c3db
- start: 117f54a (champion code)
- budget: 5 duels, 3 FFA
- score: mu 48.96, sigma 3.85, lb 37.41
- champion lb: 49.55
- verdict: discard
- games: 5-0, FFA ranks 4p:1 6p:5 10p:1
- what changed: Battling as Crusader in Crusader.bot + Crusader.py; each hill drafts up to 4 closest ants within 20 steps before food, only undrafted ants claim food.
- what you learned: Drafting swept duels 5-0 and won the 4p and 10p, but ranked 5/6 behind four weak past selves that just ate; hills-first starves the economy, so lb fell from 49.55 to 37.41.
- next: Opponent model — read the enemy target from the enemy moves.

## 15 — opponent model read enemy headings (2026-09-20)
- commit: 79bbd16
- start: 117f54a (champion code)
- budget: 5 duels, 3 FFA
- score: mu 63.80, sigma 3.88, lb 52.15
- champion lb: 49.55
- verdict: keep
- games: 5-0, FFA ranks 5p:1 7p:1 8p:1
- what changed: Battling as Oracle in Oracle.bot + Oracle.py; enemies matched to last-turn positions give headings, and a home hill counts threatened at 16 steps when an enemy closes on it.
- what you learned: Early warning swept every game including head-to-head wins over NoCamping and Berserker; meeting razers halfway lifts lb from 49.55 to 52.15.
- next: Endgame — hold most hills until the turn limit.

## 16 — endgame rally to hold hills (2026-09-20)
- commit: f1107b0
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 54.15, sigma 3.69, lb 43.07
- champion lb: 52.15
- verdict: discard
- games: 5-0, FFA ranks 5p:1 7p:1 8p:5
- what changed: Battling as Lockdown in Lockdown.bot + Lockdown.py; with 150 turns left, spare ants rally to the nearest home hill, or all-out attack with no hills left.
- what you learned: Rallying swept duels and the small FFAs but ranked 5/8 behind three past selves that kept razing; holding forfeits the late raze race that decides FFAs, so lb fell from 52.15 to 43.07.
- next: Time — use the turn time for search.

## 17 — time-aware BFS search budget (2026-09-20)
- commit: 71bf7c1
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 56.99, sigma 3.85, lb 45.45
- champion lb: 52.15
- verdict: discard
- games: 5-0, FFA ranks 4p:1 6p:2 10p:2
- what changed: Battling as Clockwork in Clockwork.bot + Clockwork.py; each ant's BFS budget follows the clock (800/250/60) so early ants search deep.
- what you learned: Deeper early search swept duels 5-0 and took two 2nds, but lost the 6p to Crusader and the 10p to Elephant; depth without direction just finds longer walks, so lb fell from 52.15 to 45.45.
- next: BOLD — two discards in a row, research a different design.

## 18 — standing orders keep targets (2026-09-20)
- commit: 7edaf62
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 44.42, sigma 3.61, lb 33.58
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 5-0, FFA ranks 4p:1 6p:6 10p:1
- what changed: Battling as Steward in Steward.bot + Steward.py; ants hold food and hill missions across turns with proximity handoff, only missionless ants bid.
- what you learned: Missions swept duels and won the 4p and 10p but finished 6/6 behind weak old selves; hill-mission ants march past fresh food, breaking food-first economy, so lb fell from 52.15 to 33.58.
- next: Mission detour — hill ants grab food within 3 steps without losing missions.

## 19 — mission detour to nearby food (2026-09-20)
- commit: 3a1dd60
- start: 7edaf62 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 38.14, sigma 3.79, lb 26.76
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 4-1, FFA ranks 4p:1 6p:1 10p:8
- what changed: Battling as Grazer in Grazer.bot + Grazer.py; hill-mission ants step to unclaimed food within 3 squares, mission kept.
- what you learned: Detours won duels 4-1 and the small FFAs but ranked 8/10 behind every past self; one-off snacks dither marches into wandering, worse than ignoring the food, so lb fell from 52.15 to 26.76.
- next: Stale missions — re-bid food when a new claim is 5+ closer.

## 20 — stale missions re-bid on big gains (2026-09-21)
- commit: 9eea381
- start: 3a1dd60 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 41.26, sigma 3.74, lb 30.03
- champion lb: 52.15
- verdict: drop the missions line (bold 3 of 3)
- games: 4-1, FFA ranks 5p:1 7p:4 8p:4
- what changed: Battling as Goldilocks in Goldilocks.bot + Goldilocks.py; no detour, but food missions re-bid when an unclaimed food is 5+ closer.
- what you learned: Hysteresis went 4-1 but lost to its parent Grazer and placed 4/7 and 4/8; three strikes (33.58, 26.76, 30.03) prove stateful assignment loses to greedy re-bidding at this strength, so the line is dropped.
- next: BOLD — new line, research first (border missions candidate).

## 21 — frontier marches for idle ants (2026-09-21)
- commit: 5abaee6
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 44.32, sigma 3.75, lb 33.07
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 5-0, FFA ranks 4p:1 6p:3 10p:7
- what changed: Battling as Boone in Boone.bot + Boone.py; seen squares grow a frontier of unseen neighbors, and spare ants march the nearest frontier square instead of wandering.
- what you learned: Marches swept duels 5-0 and the 4p but ranked 7/10 in a Crusader-led 10p; pushing every spare to the edge scatters the army piecemeal, so lb fell from 52.15 to 33.07.
- next: March in company — frontier ants move in buddy pairs.

## 22 — buddy-pair frontier marches (2026-09-21)
- commit: bb88a63
- start: 5abaee6 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 37.84, sigma 3.62, lb 26.98
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 5-0, FFA ranks 5p:3 7p:7 8p:1
- what changed: Battling as Wingman in Wingman.bot + Wingman.py; spare ants join a same-turn buddy march within 12 squares or start their own.
- what you learned: Pairs swept duels 5-0 and a weak 8p but finished 7/7 behind Boone itself; clumping covers less ground and still starves, so lb fell from 52.15 to 26.98.
- next: Vanguard — only edge ants march, the rest stay home.

## 23 — vanguard only edge ants march (2026-09-21)
- commit: 9c2ea2c
- start: bb88a63 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 43.19, sigma 3.68, lb 32.15
- champion lb: 52.15
- verdict: drop the frontier line (bold 3 of 3)
- games: 5-0, FFA ranks 5p:2 7p:5 8p:3
- what changed: Battling as Vanguard in Vanguard.bot + Vanguard.py; buddy marches only start with the nearest frontier within 15 squares, the rest wander home ground.
- what you learned: Gating swept duels 5-0 and beat Wingman twice, but the family still trails badly (33.07, 26.98, 32.15); directed exploration loses to wandering at this strength, so the line is dropped.
- next: BOLD — new line, research first.

## 24 — formation defense on corner posts (2026-09-21)
- commit: 376b39f
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 53.46, sigma 3.73, lb 42.27
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 5-0, FFA ranks 4p:1 6p:4 10p:1
- what changed: Battling as Phalanx in Phalanx.bot + Phalanx.py; threatened home hills post closest spares on passable diagonals, held instead of stacking the hill.
- what you learned: Posts swept duels 5-0 and won the 4p and a weak-field 10p, but ranked 4/6 in a maze 6p; formations hold big fields yet bicker over small ones, so lb reached 42.27 against 52.15.
- next: Second ring — double-distance posts when heavily threatened.

## 25 — second ring posts when heavily hit (2026-09-21)
- commit: 95ba976
- start: 376b39f (bold line)
- budget: 5 duels, 3 FFA
- score: mu 44.66, sigma 3.56, lb 33.99
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 5-0, FFA ranks 5p:1 7p:2 8p:8
- what changed: Battling as Saturn in Saturn.bot + Saturn.py; hills with 4+ enemies inside 20 post a double-distance second ring from remaining spares.
- what you learned: Rings swept duels 5-0 and took 2nd in the 7p, but finished 8/8 in a maze 8p won by Elephant; post-holders never eat, so over-garrisoning starves the army, lb fell from 52.15 to 33.99.
- next: Hungry posts — defenders snack unclaimed food within 4 steps.

## 26 — hungry posts snack within 4 (2026-09-21)
- commit: 00fbdbb
- start: 95ba976 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 49.22, sigma 3.80, lb 37.83
- champion lb: 52.15
- verdict: drop the formation line (bold 3 of 3)
- games: 5-0, FFA ranks 4p:3 6p:2 10p:1
- what changed: Battling as Garrison in Garrison.bot + Garrison.py; defenders step to unclaimed food within 4 squares first, posts re-draft next turn.
- what you learned: Eating defenders swept duels 5-0 and won the 10p with Saturn 2nd, but lost the 4p to Grazer; the family (42.27, 33.99, 37.83) never threatens the champion, so the line is dropped.
- next: BOLD — new line, research first.

## 27 — seek supported fights inside 8 (2026-09-21)
- commit: abee17e
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 48.28, sigma 3.58, lb 37.54
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 4-1, FFA ranks 5p:1 7p:1 8p:6
- what changed: Battling as Lancer in Lancer.bot + Lancer.py; between defense and hill-hunting, ants with an enemy inside 8 close on it, filter as backstop.
- what you learned: Charges swept the small fields (5p and 7p wins) but lost a duel to Vanguard and ranked 6/8 in a maze 8p behind the whole formation family; seeking fights bleeds in crowds, so lb reached 37.54 against 52.15.
- next: Supported charges — only close with 2+ friends nearby.

## 28 — charges need 2+ friends nearby (2026-09-21)
- commit: 06d253e
- start: abee17e (bold line)
- budget: 5 duels, 3 FFA
- score: mu 49.76, sigma 3.56, lb 39.08
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 5-0, FFA ranks 5p:1 7p:5 8p:3
- what changed: Battling as Cavalry in Cavalry.bot + Cavalry.py; ants close on enemies inside 8 only with 2+ friends within 10.
- what you learned: Support fixed the duel loss and the 8p (3rd behind Boone and Vanguard), but ranked 5/7 in a maze 7p behind Cartographer and Lancer itself; company helps yet still wanders into crowds, so lb reached 39.08 against 52.15.
- next: Favorites only — charge winning fights at the foe.

## 29 — charge only winning fights at foe (2026-09-21)
- commit: 6f47258
- start: 06d253e (bold line)
- budget: 5 duels, 3 FFA
- score: mu 46.72, sigma 3.66, lb 35.74
- champion lb: 52.15
- verdict: drop the offense line (bold 3 of 3)
- games: 5-0, FFA ranks 4p:1 6p:1 10p:9
- what changed: Battling as Bookmaker in Bookmaker.bot + Bookmaker.py; ants close on a foe inside 8 only when friends outnumber enemies around the foe.
- what you learned: Favorites swept duels 5-0 and won the 4p and a 6p over Cavalry and Lancer, then finished 9/10 in a Berserker-led 10p ahead of only an ErrorBot; the family (37.54, 39.08, 35.74) never threatens the champion, so the line is dropped.
- next: BOLD — new line, research first.

## 30 — danger-aware routing around kill zones (2026-09-21)
- commit: 6d0db87
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 38.50, sigma 3.73, lb 27.31
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 5-0, FFA ranks 4p:1 6p:6 10p:5
- what changed: Battling as Detour in Detour.bot + Detour.py; BFS skips tiles inside enemy attack range (goal exempt), walled-off ants fall back.
- what you learned: Detours swept duels 5-0 and the 4p, but finished 6/6 in a maze 6p behind Saturn and Bookmaker and 5/10; refusing paths near any enemy cowers the army off food and hills, so lb reached 27.31 against 52.15.
- next: Brave detours — skip kill zones only en route to hills.
