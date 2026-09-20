# Strategy

This file shows how the bot plays now, and how good play looks.
Update this file when the behavior of the bot changes.
This file describes the current champion only. History lives in
`WORKLOG.md`.

## Current bot

Iteration 13 (117f54a), the current champion, battles as Berserker
in Berserker.bot + Berserker.py. It assigns food by global distance,
guards threatened home hills, and marches on remembered enemy hills
until razed. Food and hill moves follow the first step of a BFS
shortest path around water. Moves need a local majority, except
equal trades are accepted when 14+ friends stand within 10 steps.
Spare ants explore least-visited squares, and no ant ends a turn
sitting on its own hill so spawning stays open. Recorded score:
mu 61.04, sigma 3.83, lb 49.55 (5 duels + 3 FFA).

## Good play

- Economy first. Take the nearest food. Do not waste a turn.
  One lost food turn is one lost ant.
- Fight with a majority. Attack only when your ants outnumber the
  defenders. Do not move an ant into certain death.
- Hold and take hills. A hill makes ants. Take a weak enemy hill.
  Keep spare ants near your own hills.
- Use the map. Food near home is gone first. Send spare ants out.
- Watch the clock. Search is possible in 1000 ms each turn.
  A timeout loses the game.

## Open questions

- What is the best start on each map family?
- When is a hill attack worth the ants?
- How many ants stay home?
