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

## 31 — cowardice only on hill marches (2026-09-21)
- commit: e389466
- start: 6d0db87 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 52.56, sigma 3.54, lb 41.95
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 5-0, FFA ranks 5p:2 7p:2 8p:3
- what changed: Battling as Pilgrim in Pilgrim.bot + Pilgrim.py; kill-zone skipping applies only to hill-hunt paths, food and defense stay greedy.
- what you learned: Scoped cowardice steadied to straight podiums (2/5, 2/7, 3/8 behind Cavalry and Boone) but never wins; hunters survive the march yet arrive too late and too few, so lb reached 41.95 against 52.15.
- next: Tolls — pay +3 per kill-zone tile instead of skipping.

## 32 — danger tolls instead of walls (2026-09-21)
- commit: 19b129c
- start: e389466 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 29.32, sigma 3.63, lb 18.43
- champion lb: 52.15
- verdict: drop the routing line (bold 3 of 3)
- games: 3-2, FFA ranks 5p:1 7p:7 8p:2
- what changed: Battling as Tariff in Tariff.bot + Tariff.py; Dijkstra charges +3 a kill-zone tile on every path, never walled off.
- what you learned: Tolls went 3-2 losing twice to Hunter and finished 7/7 in a cell-maze 7p; bending every path makes ants late to food and fights everywhere, so lb collapsed from 52.15 to 18.43.
- next: BOLD — new line, research first.

## 33 — floodgates turtle then swarm at 15 (2026-09-21)
- commit: 3a17be9
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 40.58, sigma 3.70, lb 29.48
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 5-0, FFA ranks 4p:3 6p:1 10p:7
- what changed: Battling as Floodgate in Floodgate.bot + Floodgate.py; no hill-hunting below 15 ants, then every spare swarms the nearest remembered hill.
- what you learned: Gates swept duels 5-0 and a weak 6p, but finished 7/10 behind six of its own descendants; turtling cedes the map and the swarm opens onto enemy ground, so lb reached 29.48 against 52.15.
- next: Lower gate — swarm at 8 ants.

## 34 — lower floodgate to 8 ants (2026-09-21)
- commit: e974d2c
- start: 3a17be9 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 43.64, sigma 3.65, lb 32.70
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 4-1, FFA ranks 5p:5 7p:1 8p:1
- what changed: Battling as Sluice in Sluice.bot + Sluice.py; the swarm gates on 8 ants instead of 15.
- what you learned: The low gate went 4-1 losing a duel to Detour, won the 7p and 8p over Floodgate itself, then finished 5/5 in a 5p behind Detour and Floodgate; gate timing is feast or famine, so lb reached 32.70 against 52.15.
- next: Posse — hunt only hills with 3+ spares nearby.

## 35 — posse rides only with 3+ spares (2026-09-21)
- commit: a64a938
- start: e974d2c (bold line)
- budget: 5 duels, 3 FFA
- score: mu 39.97, sigma 3.56, lb 29.28
- champion lb: 52.15
- verdict: drop the floodgate line (bold 3 of 3)
- games: 5-0, FFA ranks 5p:3 7p:6 8p:2
- what changed: Battling as Posse in Posse.bot + Posse.py; the gate moves to the target — spares march only hills with 3+ spares inside 12.
- what you learned: The posse swept duels 5-0 and took 2nd in a weak 8p, but finished 6/7 in a maze 7p behind Bookmaker and Floodgate; local gates reproduce the family mediocrity, so lb reached 29.28 against 52.15.
- next: BOLD — new line, research first.

## 36 — militia defends before food (2026-09-21)
- commit: 153fc6a
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 35.44, sigma 3.53, lb 24.85
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 5-0, FFA ranks 5p:2 7p:4 8p:8
- what changed: Battling as Militia in Militia.bot + Militia.py; the 4 closest ants per threatened hill defend and eat nothing, food drafts from the rest.
- what you learned: The militia swept duels 5-0 and took 2nd in the 5p, but finished 8/8 in a cell-maze 8p behind Floodgate and Detour; drafting defenders first starves the army because threats never stop, so lb reached 24.85 against 52.15.
- next: Volunteer militia — defenders drafted from spares only.

## 37 — volunteer militia from spares only (2026-09-21)
- commit: f12c5f5
- start: 153fc6a (bold line)
- budget: 5 duels, 3 FFA
- score: mu 40.27, sigma 3.80, lb 28.86
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 5-0, FFA ranks 4p:4 6p:1 10p:3
- what changed: Battling as Minuteman in Minuteman.bot + Minuteman.py; food pairs draft first, then the 4 closest spares per threatened hill take exclusive duty.
- what you learned: Volunteers swept duels 5-0, won a weak 6p, and took 3rd in the 10p, but finished 4/4 in a maze 4p behind Militia itself; exclusive duty underperforms the champion's pile-on, so lb reached 28.86 against 52.15.
- next: Sentry — lighter watch, 2 volunteers per hill.

## 38 — sentry posts 2 volunteers per hill (2026-09-21)
- commit: bce3e11
- start: f12c5f5 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 37.39, sigma 3.58, lb 26.66
- champion lb: 52.15
- verdict: drop the militia line (bold 3 of 3)
- games: 4-1, FFA ranks 4p:1 6p:1 10p:9
- what changed: Battling as Sentry in Sentry.bot + Sentry.py; 2 spares per threatened hill take exclusive duty instead of 4.
- what you learned: Sentries went 4-1 losing a duel to Militia, won the 4p and a 6p over the whole militia family, then finished 9/10 in a Vanguard-led 10p; two defenders cannot hold big-field chaos, so lb reached 26.66 against 52.15.
- next: BOLD — new line, research first.

## 39 — locavores eat within 15 steps (2026-09-21)
- commit: 7d05034
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 51.74, sigma 3.54, lb 41.12
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 4-1, FFA ranks 5p:2 7p:1 8p:4
- what changed: Battling as Locavore in Locavore.bot + Locavore.py; food pairs claim only within 15 steps, distant food waits.
- what you learned: Locavores went 4-1 losing a duel to Sentry, won a 7p over Bookmaker and the militia family, and took 4/8 behind Boone and Pilgrim; concentration works in crowds but cedes too much elsewhere, so lb reached 41.12 against 52.15.
- next: Nibbler — tighten the radius to 10.

## 40 — nibblers eat within 10 steps (2026-09-21)
- commit: 9786ff7
- start: 7d05034 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 36.76, sigma 3.66, lb 25.77
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 4-1, FFA ranks 4p:3 6p:1 10p:6
- what changed: Battling as Nibbler in Nibbler.bot + Nibbler.py; the forage radius tightens from 15 to 10.
- what you learned: Nibblers went 4-1 losing another duel to Sentry, won a weak 6p, but finished 3/4 and 6/10 in the militia fields; tighter starves, so lb fell from 52.15 to 25.77.
- next: Flexitarian — radius grows with the army.

## 41 — flexitarian radius grows with army (2026-09-21)
- commit: dfce6c0
- start: 9786ff7 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 56.42, sigma 3.55, lb 45.78
- champion lb: 52.15
- verdict: drop the food line (bold 3 of 3)
- games: 5-0, FFA ranks 5p:2 7p:1 8p:3
- what changed: Battling as Flexitarian in Flexitarian.bot + Flexitarian.py; food claims reach 8 + army size.
- what you learned: Flexitarians swept duels 5-0 over Nibbler twice, won the 7p, and took 3rd in the 8p behind Cartographer and Cavalry; adaptive radius is the best idea since Oracle at lb 45.78, yet still 6 points short, so the line is dropped.
- next: BOLD — new line, research first.

## 42 — wolfpack gangs shared prey (2026-09-21)
- commit: 1f98078
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 41.00, sigma 3.49, lb 30.55
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 3-2, FFA ranks 5p:1 7p:3 8p:4
- what changed: Battling as Wolfpack in Wolfpack.bot + Wolfpack.py; ants gang the foe with the most friends near it inside 12, and committed buddies join equal trades.
- what you learned: The pack went 3-2 losing twice to Tariff, won a weak 5p, and took mid-pack 3/7 and 4/8; shared targeting pulls ants off food into losing fights, so lb reached 30.55 against 52.15.
- next: Lone-wolf gate — gang only with 3+ buds at the prey.

## 43 — hyenas join only 3+ bud crowds (2026-09-21)
- commit: ba5982b
- start: 1f98078 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 42.95, sigma 3.51, lb 32.42
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 4-1, FFA ranks 5p:1 7p:5 8p:2
- what changed: Battling as Hyena in Hyena.bot + Hyena.py; the pack gangs only prey with 3+ buds already near it.
- what you learned: Hyenas went 4-1 beating Tariff and splitting Nibbler, won the 5p, and took 2nd in the 8p behind Detour, but finished 5/7 behind Wolfpack itself; crowd-gating fixes duels yet goes passive in crowds, so lb reached 32.42 against 52.15.
- next: Jackal — nearest foe, lead on majority, join on commitment.

## 44 — jackal leads majority joins commitment (2026-09-21)
- commit: 587fbb7
- start: ba5982b (bold line)
- budget: 5 duels, 3 FFA
- score: mu 27.06, sigma 3.66, lb 16.07
- champion lb: 52.15
- verdict: drop the pack line (bold 3 of 3)
- games: 3-2, FFA ranks 5p:1 7p:5 8p:7
- what changed: Battling as Jackal in Jackal.bot + Jackal.py; nearest foe inside 12, first ant leads on static majority, buddies join equal trades.
- what you learned: Jackals went 3-2 losing twice to Tariff with lb negative mid-run, won a weak 5p, then finished 5/7 and 7/8; nearest-foe targeting without crowd sense is suicide, so lb collapsed from 52.15 to 16.07.
- next: BOLD — new line, research first.

## 45 — brawler lowers equal-trade gate to 8 (2026-09-21)
- commit: 4f3f0e1
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 27.87, sigma 3.83, lb 16.39
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 2-3, FFA ranks 5p:5 7p:1 8p:1
- what changed: Battling as Brawler in Brawler.bot + Brawler.py; the equal-trade gate drops from 14 friends to 8.
- what you learned: Brawlers went 2-3 losing twice to Jackal and once to Tariff, finished 5/5 in a real 5p, and won two cripple-field FFAs; more equal trades just means more deaths, so lb collapsed from 52.15 to 16.39.
- next: Monk — raise the gate to 20, refuse equals.

## 46 — monk raises equal-trade gate to 20 (2026-09-21)
- commit: 5be0a68
- start: 4f3f0e1 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 37.09, sigma 3.72, lb 25.94
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 3-2, FFA ranks 4p:2 6p:1 8p:5
- what changed: Battling as Monk in Monk.bot + Monk.py; the equal-trade gate rises from 14 friends to 20.
- what you learned: Monks went 3-2 splitting Tariff and losing a duel to Brawler, won a weak 6p, and took 5/10; refusing equals cedes fights as surely as seeking them bleeds, so lb reached 25.94 against 52.15.
- next: Bouncer — the crowd must be within 6, not 10.

## 47 — bouncer counts crowds within 6 (2026-09-21)
- commit: a61b9be
- start: 5be0a68 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 32.41, sigma 3.84, lb 20.87
- champion lb: 52.15
- verdict: drop the aggression line (bold 3 of 3)
- games: 3-2, FFA ranks 4p:2 6p:1 10p:6
- what changed: Battling as Bouncer in Bouncer.bot + Bouncer.py; the gate stands at 14 but near tightens from 10 to 6.
- what you learned: Bouncers went 3-2 losing to Brawler and Tariff, won a weak 6p, and finished 6/10 behind Jackal and the brawl family; close crowds are not the backup that matters, so lb reached 20.87 against 52.15.
- next: BOLD — new line, research first.

## 48 — exorcist drops visible-empty hills (2026-09-21)
- commit: 5a7958a
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 35.33, sigma 3.75, lb 24.10
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 3-2, FFA ranks 4p:2 6p:3 10p:5
- what changed: Battling as Exorcist in Exorcist.bot + Exorcist.py; remembered hills visible with no enemy hill are dropped as razed ghosts.
- what you learned: Exorcists went 3-2 losing twice to Bouncer and took 2/4, 3/6, 5/10; ghost-hunting was forward deployment, not waste, so pruning scatters pressure, lb reached 24.10 against 52.15.
- next: Haunted — re-add ghosts after 50 turns unseen.

## 49 — haunt drops ghosts after 20 turns (2026-09-21)
- commit: 080ae78
- start: 5a7958a (bold line)
- budget: 5 duels, 3 FFA
- score: mu 30.22, sigma 3.56, lb 19.53
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 4-1, FFA ranks 4p:1 6p:6 10p:5
- what changed: Battling as Haunt in Haunt.bot + Haunt.py; hills seen empty 20 straight turns are dropped, fresh kills stay rally points.
- what you learned: Haunts went 4-1 splitting Tariff, won the 4p, but finished 6/6 behind Exorcist itself and 5/10; lingering fails harder than purging, so lb reached 19.53 against 52.15.
- next: Vigil — drop ghosts after 5 turns.

## 50 — vigil drops ghosts after 5 turns (2026-09-21)
- commit: 9d26322
- start: 080ae78 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 36.58, sigma 3.69, lb 25.52
- champion lb: 52.15
- verdict: drop the ghost line (bold 3 of 3)
- games: 3-2, FFA ranks 4p:3 6p:1 10p:4
- what changed: Battling as Vigil in Vigil.bot + Vigil.py; hills seen empty 5 straight turns are dropped instead of 20.
- what you learned: Vigils went 3-2 losing twice to Haunt, took 3/4 behind Exorcist and Haunt, won a weak 6p, and took 4/10; any pruning loses, 5 turns is merely least-bad, so lb reached 25.52 against 52.15.
- next: BOLD — new line, research first.

## 51 — hearth eats local guards posts (2026-09-21)
- commit: 9a7762f
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 37.50, sigma 3.58, lb 26.75
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 5-0, FFA ranks 4p:4 6p:3 10p:4
- what changed: Battling as Hearth in Hearth.bot + Hearth.py; adaptive food reach plus ring-1 corner posts, judged as one design.
- what you learned: Hearths swept duels 5-0 but took 4/4, 3/6, 4/10, scoring below both parents (45.78, 42.27); posts eat the spares radius frees and nobody pressures, so lb reached 26.75 against 52.15.
- next: Hearth with hungry posts — defenders snack within 4.

## 52 — manor defenders snack within 4 (2026-09-21)
- commit: bfa4ed5
- start: 9a7762f (bold line)
- budget: 5 duels, 3 FFA
- score: mu 50.26, sigma 3.55, lb 39.62
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 4-1, FFA ranks 5p:1 7p:4 8p:1
- what changed: Battling as Manor in Manor.bot + Manor.py; hearth defenders snack unclaimed food within 4, post kept.
- what you learned: Manors went 4-1 losing a duel to Hearth, won the 5p and an 8p over Hearth and Goldilocks, and took 4/7; snacking fixes the starvation but not the pressure gap, so lb reached 39.62 against 52.15.
- next: Homestead — full conservative triple synthesis.

## 53 — homestead full conservative triple (2026-09-21)
- commit: f516ee2
- start: bfa4ed5 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 37.51, sigma 3.51, lb 26.99
- champion lb: 52.15
- verdict: drop the synthesis line (bold 3 of 3)
- games: 3-2, FFA ranks 5p:1 7p:2 8p:7
- what changed: Battling as Homestead in Homestead.bot + Homestead.py; radius plus snacking posts plus kill-zone avoidance on hill marches.
- what you learned: Homesteads went 3-2 losing to Haunt and Houdini, won a weak 5p, took 2/7, then finished 7/8 behind Hearth and Manor itself; cowardice re-poisons the mix, so lb reached 26.99 against 52.15.
- next: BOLD — new line, research first.

## 54 — huddle fallback masses friends (2026-09-21)
- commit: 0ee5d07
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 32.69, sigma 3.55, lb 22.03
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 3-2, FFA ranks 4p:2 6p:6 10p:1
- what changed: Battling as Huddle in Huddle.bot + Huddle.py; fallback ants step toward the nearest friend, exploring only to bootstrap.
- what you learned: Huddles went 3-2 losing to Haunt and Wolfpack, finished 6/6 in a real 6p, and won a cripple-field 10p; the ball cedes map and food and gets out-grown, so lb reached 22.03 against 52.15.
- next: Loose huddle — mass toward friends only past turn 100.

## 55 — reunion huddles past turn 100 (2026-09-21)
- commit: 5475afd
- start: 0ee5d07 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 32.36, sigma 3.60, lb 21.55
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 3-2, FFA ranks 5p:1 7p:7 8p:1
- what changed: Battling as Reunion in Reunion.bot + Reunion.py; fallback explores before turn 100, huddles after.
- what you learned: Reunions went 3-2 losing twice to Huddle, won two cripple-field FFAs, and finished 7/7 in a real 7p behind Huddle itself; phase-gating changes nothing fundamental, so lb reached 21.55 against 52.15.
- next: Intern — fallback shadows employed ants.

## 56 — intern shadows employed ants (2026-09-21)
- commit: b612633
- start: 5475afd (bold line)
- budget: 5 duels, 3 FFA
- score: mu 35.76, sigma 3.60, lb 24.98
- champion lb: 52.15
- verdict: drop the cohesion line (bold 3 of 3)
- games: 4-1, FFA ranks 4p:2 6p:6 10p:1
- what changed: Battling as Intern in Intern.bot + Intern.py; fallback steps toward the nearest food-claim holder.
- what you learned: Interns went 4-1 splitting Huddle, took 2/4, finished 6/6 in a real 6p, and won a cripple-field 10p; shadowing trails gatherers, best of a bad line, so lb reached 24.98 against 52.15.
- next: BOLD — new line, research first.

## 57 — marshal orders danger first (2026-09-21)
- commit: 597cd54
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 51.45, sigma 3.53, lb 40.85
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 3-2, FFA ranks 5p:1 7p:1 8p:3
- what changed: Battling as Marshal in Marshal.bot + Marshal.py; movers sort by nearest-enemy distance, closest first.
- what you learned: Marshals went 3-2 losing duels to Intern and Reunion, won the 5p and 7p, and took 3/8 behind Garrison and Bouncer; ordering shows signal but duels bleed to clumps, so lb reached 40.85 against 52.15.
- next: Purser — food-claimants move first.

## 58 — purser moves food first (2026-09-21)
- commit: feda0a5
- start: 597cd54 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 41.86, sigma 3.55, lb 31.22
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 4-1, FFA ranks 4p:2 6p:4 10p:2
- what changed: Battling as Purser in Purser.bot + Purser.py; food-claimants move first, the rest in engine order.
- what you learned: Pursers went 4-1 losing a duel to Intern and took 2/4, 4/6, 2/10 behind Bookmaker and Brawler; consistent but flat, never winning, so lb reached 31.22 against 52.15.
- next: Raider — hunters move first, food last.

## 59 — raider moves hunters first (2026-09-21)
- commit: 2b4a04e
- start: feda0a5 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 37.35, sigma 3.52, lb 26.79
- champion lb: 52.15
- verdict: drop the ordering line (bold 3 of 3)
- games: 5-0, FFA ranks 4p:3 6p:6 10p:1
- what changed: Battling as Raider in Raider.bot + Raider.py; hunters move first and food last.
- what you learned: Raiders swept duels 5-0 but finished 3/4, 6/6 in a real 6p, and won a cripple-field 10p; pressure-first starves the economy in real fields, so lb reached 26.79 against 52.15.
- next: BOLD — new line, research first.

## 60 — stoic calms closing rule to 12 (2026-09-21)
- commit: a8245be
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 51.12, sigma 3.47, lb 40.71
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 4-1, FFA ranks 4p:4 6p:1 10p:1
- what changed: Battling as Stoic in Stoic.bot + Stoic.py; the closing-threat rule drops from 16 steps to 12.
- what you learned: Stoics went 4-1 losing a duel to Raider, won the 6p and a 10p over Jackal and Monk, but finished 4/4 behind Raider and Wolfpack; calmer threats win big fields yet sleep through small ones, so lb reached 40.71 against 52.15.
- next: Alarm — closing rule needs 2+ enemies.

## 61 — alarm needs 2+ closing enemies (2026-09-21)
- commit: 386dfbb
- start: a8245be (bold line)
- budget: 5 duels, 3 FFA
- score: mu 47.84, sigma 3.54, lb 37.22
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 4-1, FFA ranks 4p:3 6p:2 10p:1
- what changed: Battling as Alarm in Alarm.bot + Alarm.py; the closing rule needs 2+ enemies inside 16, lone scouts ignored.
- what you learned: Alarms went 4-1 losing a duel to Wolfpack and took 3/4, 2/6, then won the 10p over Exorcist and Vigil; quorum sleeps through small fields worse than Stoic, so lb reached 37.22 against 52.15.
- next: Median — closing rule at 14, the middle path.

## 62 — median sets closing rule at 14 (2026-09-21)
- commit: 97b8ac4
- start: 386dfbb (bold line)
- budget: 5 duels, 3 FFA
- score: mu 52.69, sigma 3.49, lb 42.22
- champion lb: 52.15
- verdict: drop the threat line (bold 3 of 3)
- games: 5-0, FFA ranks 4p:1 6p:5 10p:1
- what changed: Battling as Median in Median.bot + Median.py; the closing rule fires at 14 steps, quorum dropped.
- what you learned: Medians swept duels 5-0, won the 4p and a 10p over Sentry and Stoic, but finished 5/6 behind Hearth and Manor; 14 splits 12 and 16 honestly yet still trails, so lb reached 42.22 against 52.15.
- next: BOLD — new line, research first.

## 63 — doormat refuses own-hill destinations (2026-09-21)
- commit: 093f546
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 36.74, sigma 3.45, lb 26.40
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 4-1, FFA ranks 5p:4 7p:1 8p:5
- what changed: Battling as Doormat in Doormat.bot + Doormat.py; try_step and explore refuse own-hill destinations.
- what you learned: Doormats went 4-1 losing to Intern, won a weak 7p, and took 4/5 and 5/8; standing on hills body-blocks razers, so full refusal loses more spawns than it saves, lb reached 26.40 against 52.15.
- next: Bodyguard — defenders may stand hills, others refuse.

## 64 — bodyguard stands threatened hills (2026-09-21)
- commit: c5b0aa1
- start: 093f546 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 38.71, sigma 3.55, lb 28.05
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 3-2, FFA ranks 5p:2 7p:1 8p:8
- what changed: Battling as Bodyguard in Bodyguard.bot + Bodyguard.py; defenders marching to threatened hills may stand them, others refuse.
- what you learned: Bodyguards went 3-2 losing to Haunt and Intern, took 2/5, won the 7p over the brawl family, then finished 8/8 behind Sluice and Median; splitting the difference splits results, so lb reached 28.05 against 52.15.
- next: Squatter — remove walk-off, test standing.

## 65 — squatter deletes walk-off (2026-09-21)
- commit: c6b15ff
- start: 79bbd16 (champion base)
- budget: 5 duels, 3 FFA
- score: mu 47.51, sigma 3.58, lb 36.79
- champion lb: 52.15
- verdict: drop the stand line (bold 3 of 3)
- games: 5-0, FFA ranks 4p:4 6p:2 10p:1
- what changed: Battling as Squatter in Squatter.bot + Squatter.py; the walk-off loop is deleted, held ants stay.
- what you learned: Squatters swept duels 5-0 over Doormat twice and Bodyguard, took 2/6, and won the 10p, but finished 4/4 behind Locavore and Bodyguard; standing beats refusing yet the champion's held-only mix beats both, so lb reached 36.79 against 52.15.
- next: BOLD — new line, research first.

## 66 — grinder trades 1v1 when ahead (2026-09-21)
- commit: 48311cb
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 34.33, sigma 3.53, lb 23.74
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 3-2, FFA ranks 5p:5 7p:1 8p:1
- what changed: Battling as Grinder in Grinder.bot + Grinder.py; friendless 1v1 engages when our visible army is at least theirs.
- what you learned: Grinders went 3-2 losing twice to Bodyguard, finished 5/5 in a real 5p, and won two cripple-field FFAs; visible counts lie and parity trades lose tempo, so lb reached 23.74 against 52.15.
- next: Strict grinder — 1v1 only when strictly ahead.

## 67 — surplus trades 1v1 strictly ahead (2026-09-21)
- commit: 30261d8
- start: 48311cb (bold line)
- budget: 5 duels, 3 FFA
- score: mu 34.63, sigma 3.50, lb 24.14
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 3-2, FFA ranks 5p:1 7p:4 8p:5
- what changed: Battling as Surplus in Surplus.bot + Surplus.py; the 1v1 trade needs strictly more visible ants than enemies.
- what you learned: Surpluses went 3-2 losing to Intern and Bodyguard, won a weak 5p, and took 4/7 and 5/8 in real FFAs; strictness barely helps, the axis is dead, so lb reached 24.14 against 52.15.
- next: Hoard — 1v1 needs 2x visible surplus.

## 68 — hoard needs 2x surplus to trade (2026-09-21)
- commit: 19d6984
- start: 30261d8 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 51.12, sigma 3.59, lb 40.36
- champion lb: 52.15
- verdict: drop the trade line (bold 3 of 3)
- games: 4-1, FFA ranks 5p:1 7p:1 8p:5
- what changed: Battling as Hoard in Hoard.bot + Hoard.py; friendless 1v1 needs 2x visible ants over enemies.
- what you learned: Hoards went 4-1 losing a duel to Surplus, won the 5p and 7p over the trade family, but finished 5/8 behind NoCamping and Squatter; the fog margin is real (23.74, 24.14, 40.36) yet still 12 short, so the line is dropped.
- next: BOLD — new line, research first.

## 69 — peak puts hills before food (2026-09-21)
- commit: 7b55c9c
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 31.66, sigma 3.48, lb 21.23
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 3-2, FFA ranks 5p:3 7p:2 8p:7
- what changed: Battling as Peak in Peak.bot + Peak.py; the hill branch runs before the food branch, claims persist.
- what you learned: Peaks went 3-2 losing twice to Grinder and took 3/5, 2/7, then 7/8 behind Locavore and Surplus; hill-first starves on a strong base just like Crusader, so lb reached 21.23 against 52.15.
- next: Fearless food — gatherers skip the safety filter.

## 70 — glutton gathers without safety (2026-09-21)
- commit: d641251
- start: 7b55c9c (bold line)
- budget: 5 duels, 3 FFA
- score: mu 36.72, sigma 3.57, lb 26.03
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 3-2, FFA ranks 5p:5 7p:1 8p:1
- what changed: Battling as Glutton in Glutton.bot + Glutton.py; food branch skips the safety filter, rest careful.
- what you learned: Gluttons went 3-2 splitting Peak, finished 5/5 in a real 5p, and won two weak-field FFAs; fearless food recovers gathering but dies in real fights, so lb reached 26.03 against 52.15.
- next: Daredevil — drop the safety filter everywhere.

## 71 — daredevil deletes safety filter (2026-09-21)
- commit: d350bc2
- start: d641251 (bold line)
- budget: 5 duels, 3 FFA
- score: mu 32.65, sigma 3.53, lb 22.07
- champion lb: 52.15
- verdict: drop the tape line (bold 3 of 3)
- games: 3-2, FFA ranks 4p:2 6p:6 10p:1
- what changed: Battling as Daredevil in Daredevil.bot + Daredevil.py; is_safe deleted, all moves fearless.
- what you learned: Daredevils went 3-2 losing twice to Grinder, took 2/4, finished 6/6 in a real 6p, and won a cripple-field 10p; full fear is worst of the line, so lb reached 22.07 against 52.15.
- next: BOLD — new line, research first.

## 72 — blitz skips food before turn 25 (2026-09-21)
- commit: 63558af
- start: 79bbd16 (champion code)
- budget: 5 duels, 3 FFA
- score: mu 38.03, sigma 3.55, lb 27.38
- champion lb: 52.15
- verdict: discard (bold 1 of 3)
- games: 3-2, FFA ranks 5p:3 7p:4 8p:1
- what changed: Battling as Blitz in Blitz.bot + Blitz.py; no food claims before turn 25, full early pressure.
- what you learned: Blitzes went 3-2 losing to Peak and Daredevil, took 3/5 and 4/7, then won a real 8p over Reunion and Glutton; the all-in gamble feasts or famines, so lb reached 27.38 against 52.15.
- next: Siege — blitz only until first blood.

## 73 — siege eats at first blood (2026-09-21)
- commit: 64f97f5
- start: 63558af (bold line)
- budget: 5 duels, 3 FFA
- score: mu 38.77, sigma 3.54, lb 28.17
- champion lb: 52.15
- verdict: discard (bold 2 of 3)
- games: 3-2, FFA ranks 5p:1 7p:2 8p:7
- what changed: Battling as Siege in Siege.bot + Siege.py; food claims start at first blood or turn 25.
- what you learned: Sieges went 3-2 losing twice to Daredevil, won the 5p, took 2/7 behind Bookmaker, then finished 7/8; first blood comes fast so it eats early anyway, lb reached 28.17 against 52.15.
- next: Crusade — timed swarm turns 25 to 60.
