# Ideas

Write the doctrine first. Write the code second.
Keep the list in order. Refill the list from `RESEARCH.md` after each
bold iteration.

## Doctrine

1. Food is the economy. An ant eats one food each turn.
   More food and shorter trips give more ants.
2. Combat needs numbers. One attacker kills one defender. Both die.
   Attack only with more ants than the defender.
3. A hill makes ants. Keep your hills.
   Take an enemy hill when the trade is good.
4. Time is food. Send each ant to the nearest useful food.
   Do not walk past food.
5. The engine is deterministic. The same seeds give the same game.
   Read the replay and find the exact error.
6. Change one thing in one commit. A mixed commit teaches nothing.

## Starter bot

The starter moves each ant in the order `n`, `e`, `s`, `w`.
It ignores food, hills, and the enemy. Most single ideas beat it.
Do not stop after the first win.

## Backlog

Mark an idea `open`, `trying`, `done`, `dropped`, or `parked`.

- [ ] Closest food: each ant moves to the nearest visible food.
- [ ] Collision: two ants do not target the same food.
- [ ] Hill attack: attack an enemy hill with a local majority.
- [ ] Hill defense: keep ants near your hills when the enemy is close.
- [ ] Combat: do not move an ant into certain death.
- [ ] Exploration: send spare ants to unseen squares.
- [ ] Flood: move a group of ants to one target.
- [ ] Food denial: hold a contested food field.
- [ ] Opponent model: read the enemy target from the enemy moves.
- [ ] Endgame: hold most hills until the turn limit.
- [ ] Time: use the turn time for search.
