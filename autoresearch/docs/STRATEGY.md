# Strategy

This file shows how the bot plays now, and how good play looks.
Update this file when the behavior of the bot changes.
This file describes the current champion only. History lives in
`WORKLOG.md`.

## Current bot

Iteration 43 (a9d4173), the current champion, battles as Crowd in
Crowd.bot + Crowd.py + shared combat.py. It is Denial's economy
(contested clusters draw two ants) with a combat chain: idle ants
advance on enemies within 8 steps when 3+ friends stand within 10,
second ants join committed pair attacks, lone 1v1s engage only when
the visible army leads, extra guards screen razers at the halfway
square, equal trades go at 10 near friends — and advances run
fearless with fewer than 10 enemies visible, full safety in crowds.
Recorded score: mu 67.9, sigma 3.89 (10p census, 6p refine, 7 duels).

## Good play

- Economy first. Take the nearest food. Do not waste a turn.
  One lost food turn is one lost ant.
- Fight with a majority. Attack only when your ants outnumber the
  defenders. Do not move an ant into certain death.
- Press small fights. Advance fearlessly when few enemies show;
  keep full safety in crowds.
- Hold and take hills. A hill makes ants. Take a weak enemy hill.
  Keep spare ants near your own hills.
- Use the map. Food near home is gone first. Send spare ants out.
- Watch the clock. Search is possible in 1000 ms each turn.
  A timeout loses the game.

## Open questions

- What is the best start on each map family?
- When is a hill attack worth the ants?
- How many ants stay home?
