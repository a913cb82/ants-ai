# Strategy

This file shows how the bot plays now, and how good play looks.
Update this file when the behavior of the bot changes.
This file describes the current champion only. History lives in
`WORKLOG.md`.

## Current bot

Iteration 3 (81771a1), the current champion, assigns food by global
distance and hunts hills with spare ants. The bot sorts every
ant-food pair by distance. It claims the closest unclaimed pair
first, so the closest pairs win whatever the ant order. No two ants
chase the same food region. Ants with no food claim step toward the
nearest visible enemy hill and avoid a used destination, else step n,
e, s, w. The bot ignores defense and the enemy. Recorded score:
mu 46.10, sigma 4.23, lb 33.39 (5 duels + 3 FFA).

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
