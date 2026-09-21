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

Give each idea one status: `open`, `trying`, `done`, `dropped`, or
`parked`. Keep the list in order. A refinement of an idea is a new
row. Leave the old row as it was.

| status | idea |
|---|---|
| done | Closest food: each ant moves to the nearest visible food. |
| done | Collision: one ant per food and one ant per destination square. |
| done | Collision: assign food by global ant-food distance, closest first. |
| done | Hill attack: spare ants step toward the nearest visible enemy hill. |
| done | Hill defense: spare ants guard a home hill with an enemy within 10 steps. |
| open | Hill attack: commit attackers only with a local majority. |
| open | Hill defense: keep ants near your hills when the enemy is close. |
| done | Combat: skip any step without a local majority in attack range. |
| done | Exploration: order the fallback by least-visited square first. |
| trying | Flood: move a group of ants to one target. |
| trying | Food denial: hold a contested food field. |
| done | Opponent model: threaten a home hill at 16 steps when an enemy closes. |
| trying | Endgame: hold most hills until the turn limit. |
| trying | Time: use the turn time for search. |
| done | Bold pathfinding: BFS first step around water instead of greedy steps. |
| done | Remembered hills: keep enemy hill targets across turns. |
| done | Walk off hill: never end a turn on your own hill. |
| trying | Escape space: among safe moves pick the most open space. |
| done | Aggressive combat: trade 1-for-1 when 14+ friends near the fight. |
| trying | Hill-first order: hunt hills before food. |
| dropped | Standing orders: ants keep targets across turns. |
| dropped | Mission detour: hill ants grab food within 3 steps. |
| dropped | Stale missions: re-bid food when 5+ closer. |
| dropped | Frontier marches: idle ants push the unseen edge. |
| dropped | Buddy marches: explorers move in pairs. |
| dropped | Vanguard: only edge ants march. |
| dropped | Formation defense: corner posts around threatened hills. |
| dropped | Second ring: double-distance posts when heavily hit. |
| dropped | Hungry posts: defenders snack within 4. |
| dropped | Seek fights: close on enemies inside 8. |
| dropped | Supported charges: 2+ friends nearby. |
| dropped | Favorites only: charge winning fights. |
| dropped | Danger routing: BFS skips kill zones. |
| dropped | Brave detours: cowardice on hill marches only. |
| dropped | Danger tolls: +3 a kill-zone tile. |
| dropped | Floodgates: swarm remembered hills at 15 ants. |
| dropped | Lower gate: swarm at 8 ants. |
| dropped | Posse: hunt hills with 3+ spares nearby. |
| dropped | Militia: defense drafts before food. |
| dropped | Volunteers: duty drafts from spares only. |
| dropped | Sentry: 2 volunteers per hill. |
| dropped | Locavores: food claims within 15. |
| dropped | Nibblers: radius tightens to 10. |
| dropped | Flexitarian: radius grows with army. |
| dropped | Wolfpack: gang shared prey, join equals. |
| dropped | Hyena: join only 3+ bud crowds. |
| dropped | Jackal: nearest foe, join on commitment. |
| dropped | Brawler: equal-trade gate at 8. |
| dropped | Monk: equal-trade gate at 20. |
| dropped | Bouncer: crowds count within 6. |
| dropped | Exorcist: drop visible-empty hills. |
| dropped | Haunt: drop ghosts after 20 turns. |
| dropped | Vigil: drop ghosts after 5 turns. |
| dropped | Hearth: radius plus posts synthesis. |
| dropped | Manor: snacking posts on the hearth. |
| dropped | Homestead: conservative triple. |
| dropped | Huddle: fallback masses friends. |
| dropped | Reunion: huddle past turn 100. |
| dropped | Intern: shadow employed ants. |
| dropped | Marshal: danger moves first. |
| dropped | Purser: food-claimants move first. |
| dropped | Raider: hunters move first. |
| dropped | Stoic: closing rule at 12. |
| dropped | Alarm: quorum of 2 closing. |
| dropped | Median: closing rule at 14. |
| dropped | Doormat: refuse own-hill destinations. |
| dropped | Bodyguard: defenders may stand hills. |
| dropped | Squatter: delete walk-off. |
| dropped | Grinder: 1v1 when ahead. |
| dropped | Surplus: 1v1 strictly ahead. |
| dropped | Hoard: 1v1 needs 2x. |
| dropped | Peak: hills before food. |
| dropped | Glutton: fearless food. |
| dropped | Daredevil: no safety anywhere. |
| dropped | Blitz: no food before turn 25. |
| dropped | Siege: eat at first blood. |
| dropped | Hornet: swarm turns 25-60. |
| dropped | Frontrunner: sit on hill lead. |
| dropped | Underdog: fearless behind. |
| dropped | Closer: fearless ahead. |
| dropped | Surge: fearless economy ahead. |
| dropped | Revenant: forget empty hills. |
| dropped | Overrun: no guards ahead. |
| dropped | Hotspot: most-visited explore. |
| dropped | Outpost: forward food. |
| dropped | Bloodhound: closing-only defense. |
| dropped | Screen: intercept razers. |
| dropped | Sieve: screen lone, guard pack. |
| dropped | Dragnet: screen packs. |
| dropped | Onslaught: fearless hunt + screen. |
| dropped | Picket: screen then hold. |
| dropped | Bulwark: hold then screen. |
| dropped | Anchor: safe hunt + wall. |
| dropped | Rampart: fearless wall. |
| dropped | Palisade: safe hunt + fearless wall. |
| dropped | Trawl: fearless Dragnet. |
| dropped | Fairweather: wall ahead. |
| dropped | Foulweather: wall behind. |
| dropped | Redoubt: 2 guards per hill. |
| dropped | Storm: full-fearless wall. |
| dropped | Tide: even-or-better. |
| dropped | Tripwire: guards at 8. |
| dropped | Barbwire: guards at 12. |
| dropped | Pickoff: weakest hill. |
| dropped | Mugger: strongest hill. |
| dropped | Sundown: no food past 700. |
| dropped | Dusk: fearless past 700. |
| dropped | Ram: centroid ram. |
| dropped | Muster: walk-off to war. |
| dropped | Harvest: walk-off to food. |
| dropped | Harrier: fearless split. |
| dropped | Majority: ant-count gate. |
| dropped | Seine: ant-gated split. |
| dropped | Elastic: adaptive food + wall. |
| dropped | Draft: fighters first. |
| dropped | Serve: gatherers first. |
| dropped | Usher: spawn forward. |
| dropped | Rearguard: spawn back. |
| dropped | Triage: sit hot front. |
| dropped | Shortfuse: closing at 14. |
| dropped | Counter: walk-off at enemy. |
| dropped | Longfuse: closing at 18. |
| dropped | Odds: trades at 10. |
| dropped | Evens: trades at 20. |
| dropped | Margin: strict safety. |
| dropped | Gang: quorum hunting. |
| dropped | Escort: fearless with pack. |
| dropped | LoneWolf: fearless solo. |
| dropped | Avenge: press when bleeding. |
| dropped | Entrench: turtle bleeding. |
| dropped | Recruit: press while growing. |
| trying | Legion: floor at ten. |
