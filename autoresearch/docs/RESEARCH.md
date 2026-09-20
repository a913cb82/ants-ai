# Research

Write notes from the web and from the repo. Give the source for each
note. Start a bold iteration here, not in the code.

Use this format.

```
## <topic> (<date>)
- source: <url or repo path>
- claim: <one sentence>
- evidence: <what the source shows>
- idea: <what it suggests for the bot>
```

## Log

## Local decisions beat global plans (2026-09-20)
- source: https://github.com/T-Py-T/AntsAIBot (docs/reference/xathis/postmortem.txt, 2011 winner xathis)
- claim: The winner made every move from the ant's local environment with no game-phase logic.
- evidence: No turn counting, no win/lose detection, no saved hill locations; same logic on turn 1 and turn 999; per-turn phases initMissions, enemyHills, food, explore, fight, defence, escape.
- idea: Keep our reactive design but fix movement itself; do not add game-phase logic.

## BFS everywhere with short horizons (2026-09-20)
- source: https://github.com/T-Py-T/AntsAIBot (src/bots/xathis_bot.py, port of Strategy.java)
- claim: Every target search is a horizon-limited BFS, not a greedy step.
- evidence: Food BFS horizon 13, explore BFS 11, defence horizon 14, escape check 8; multi-source BFS from foods and hills assigns the first ant found.
- idea: Replace greedy ants.direction steps with a multi-source BFS distance field; greedy steps walk into maze walls.

## Explore value and border missions (2026-09-20)
- source: https://github.com/T-Py-T/AntsAIBot (docs/reference/xathis/postmortem.txt)
- claim: Each tile counts turns since reachable; idle ants walk to the far border.
- evidence: exploreValue resets when reachable within 10 steps; ants BFS 11 steps toward max exploreValue; surplus ants get missions to border tiles (random for fresh spawns, closest otherwise), paths recalculated with A*.
- idea: Our visit counts approximate exploreValue; add border missions for idle ants later in this bold line.

## Combat eval trades ants for position (2026-09-20)
- source: https://github.com/T-Py-T/AntsAIBot (docs/reference/xathis/postmortem.txt, combat section)
- claim: One-turn minimax with eval enemyDead*300 - myDead*180 - dist when 14+ friends near, else 512/768 with no 1v1 trades.
- evidence: Aggressive mode sacrifices 1 for 1 and 3 for 2 but never 2 for 1; passive mode refuses equal trades; distance term pulls ants toward enemies.
- idea: Our majority filter matches passive mode; add an aggressive mode when 14+ friends are near the fight.

## Escape picks max space, not any safe square (2026-09-20)
- source: https://github.com/T-Py-T/AntsAIBot (docs/reference/xathis/postmortem.txt, escaping enemies)
- claim: Among safe moves, ants pick the move with the most open space behind it.
- evidence: BFS 8 from the ant, close tiles weighted most, own ants times 3, enemies times -3; fixed ants dying in maze caves.
- idea: Replace our hold-on-unsafe and fixed fallback order with escape-to-space; explains our maze duel losses.

## Defence intercepts at half path (2026-09-20)
- source: https://github.com/T-Py-T/AntsAIBot (docs/reference/xathis/postmortem.txt, defence)
- claim: One defender per close enemy, sent to the halfway point of the enemy's path.
- evidence: BFS from own hills finds close enemies; defender travels via A* to half-dist tile; unsafe 1v1 accepted to save the hill; only defends with 4 or fewer hills.
- idea: Replace our guard-standing with half-path interception later in this bold line.

## Remembered hills with A* paths (2026-09-20)
- source: bots/pas11/Pas11.py (this repo)
- claim: Enemy hills persist across turns and ants path to them with A*.
- evidence: self.hills remembers sighted hills; A* pathfinding with time-adaptive depth; hill attack within dist 7 when ants outnumber hills 7 to 1; walks ants off own hills so spawn stays open.
- idea: Remember hills across turns and never end a turn occupying your own hill (spawn needs it open).

## Hills before food (2026-09-20)
- source: tools/sample_bots/python/GreedyBot.py (this repo)
- claim: GreedyBot hunts hills first, then food, then ants, then unseen.
- evidence: do_turn tries hunt_hills before hunt_food with standing orders; GreedyBot holds the live lb lead on the board.
- idea: Try hill-first priority order as a later bold variant if BFS movement alone does not pass the champion.
