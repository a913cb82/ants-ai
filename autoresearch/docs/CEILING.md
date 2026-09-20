# Ceiling

Measured limits. Record a limit with a number and the game that showed it.
Do not spend iterations on an impossible gain.

## Engine limits

- Turn cap: 1000 (`--turns`). A game can end early when one side is gone.
- Turn time: 1000 ms. A slow turn is a timeout, and a timeout is a loss.
- Load time: 3000 ms for the first turn.
- Players: 2 to 10. Map size and shape vary by family.
- Food: finite per map. It does not grow back.
- Combat: one attacker kills one defender. Both die.
  Equal numbers annihilate. The extra ant decides the fight.

## Known bounds

(empty — record a bound when a game or a replay proves it)
