# Strategy

This file shows how the bot plays now, and how good play looks.
Update this file when the behavior of the bot changes.

## Current bot

Iteration 1 (d02ec94) seeks the closest food. Each ant picks its nearest
visible food, one ant claims one food, and no two ants enter the same
destination square. When the target is blocked or no food is visible,
the ant steps in the order `n`, `e`, `s`, `w`. It ignores hills and
the enemy. Recorded score: mu 35.94, sigma 3.49, lb 25.46 (baseline).

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
