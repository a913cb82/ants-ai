# Strategy

This file shows how the bot plays now, and how good play looks.
Update this file when the behavior of the bot changes.
This file describes the current champion only. History lives in
`WORKLOG.md`.

## Current bot

Iteration 4 (5478c43), the current champion, assigns food by global
distance and guards home hills with spare ants. The bot sorts every
ant-food pair by distance. It claims the closest unclaimed pair
first, so the closest pairs win whatever the ant order. No two ants
chase the same food region. Ants with no food claim step toward a
home hill with a visible enemy within 10 steps, else the nearest
visible enemy hill, else step n, e, s, w. Recorded score: mu 47.08,
sigma 4.27, lb 34.28 (5 duels + 3 FFA).

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
