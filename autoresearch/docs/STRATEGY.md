# Strategy

How the bot plays now, and what good play looks like.
Update this file when the bot's behavior changes.

## Current bot

The seed is a copy of the py3 starter. Each ant steps in the fixed order
`n, e, s, w`. It ignores food, hills, and the enemy.
It almost always loses to a food-seeking bot.

## What good play looks like

- **Economy first.** Take the nearest food. Do not waste a turn.
  A missed food turn is a lost ant.
- **Fight with a majority.** Attack a target only when your local ants
  outnumber the defenders. Avoid walking into certain death.
- **Hold and take hills.** A hill produces ants. Take a weak enemy hill.
  Defend your own hills with spare ants.
- **Use the whole map.** Food runs out near home. Send spare ants out.
- **Watch the clock.** Search is allowed inside 1000 ms per turn.
  A timeout loses the game.

## Open questions

- What is the best early opening on each map family?
- When is a hill attack worth the ants?
- How many ants should stay home?
