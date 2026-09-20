# Ideas

Doctrine first, code second. Keep the backlog ordered. Refill it from
`RESEARCH.md` after every bold iteration.

## Doctrine

1. **Food is the economy.** Ants eat one food per turn. A bot with more
   food fields and shorter trips fields more ants.
2. **Combat needs numbers.** One attacker kills one defender, both die.
   Attack only with more ants than the enemy can defend with.
3. **A hill is a spawn point.** Own hills produce ants. Take enemy hills
   when the trade wins. Never lose your last hill for free.
4. **Tempo matters.** Time spent walking to food is food lost.
   Prefer the nearest useful food. Do not walk past food.
5. **Determinism.** The engine is deterministic given the seeds.
   A loss is reproducible. Read the replay and find the exact mistake.
6. **One change at a time.** A commit is one idea. A mixed commit
   teaches nothing.

## Starter bot (seed)

The seed walks every ant in the fixed order `n, e, s, w`.
It ignores food, combat, hills, and the enemy.
Most single ideas beat it. Do not stop at the first win.

## Backlog

Mark an idea `open`, `trying`, `done`, `dropped`, or `parked`.

- [ ] closest-food movement (each ant walks to the nearest visible food)
- [ ] collision handling (two ants must not target the same food)
- [ ] hill capture (attack an enemy hill with a local majority)
- [ ] hill defense (keep ants near own hills when the enemy is close)
- [ ] combat awareness (avoid moves that walk into certain death)
- [ ] exploration (send spare ants to unseen squares)
- [ ] combat floods (move a group at a target together)
- [ ] food denial (camp contested food fields)
- [ ] opponent modeling (read the enemy's target from its moves)
- [ ] endgame (hold the majority of hills until the turn cap)
- [ ] time budget (use the turn time for search, not for sleeping)
