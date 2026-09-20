# Strategy

This file shows how the bot plays now, and how good play looks.
Update this file when the behavior of the bot changes.

## Current bot

The seed is a copy of the py3 starter. Each ant steps in the order
`n`, `e`, `s`, `w`. It ignores food, hills, and the enemy.
It usually loses to a bot that looks for food.

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
