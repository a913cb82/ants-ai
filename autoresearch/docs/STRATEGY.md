# Strategy

This file shows how the bot plays now, and how good play looks.
Update this file when the behavior of the bot changes.

## Current bot

Iteration 2 (9031b00) assigns food by global distance. Every ant-food pair is sorted and claimed greedily, so the closest pairs win regardless of ant order and no two ants chase the same food region. Movement and fallback match iteration 1: step toward the assigned food with destination dedup, else step n-e-s-w. It ignores hills and the enemy. Recorded score: mu 43.73, sigma 4.94, lb 28.91 (baseline, 5 duels + 3 FFA).

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
