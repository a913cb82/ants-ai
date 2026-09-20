# Ceiling

This file lists the limits. Write a limit with a number and the game
that showed it. Do not work on a gain that is impossible.

## Engine limits

- Turn limit: 1000 (`--turns`). A game can end early when one side is gone.
- Turn time: 1000 ms. A slow turn is a timeout. A timeout is a loss.
- Load time: 3000 ms for the first turn.
- Players: 2 to 10. The map size and the map shape change with the family.
- Food: a fixed amount for each map. Food does not grow again.
- Combat: one attacker kills one defender. Both die.
  Equal numbers destroy both sides. The extra ant wins the fight.

## Measured limits

Empty. Write a limit when a game or a replay proves it.
