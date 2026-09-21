# Research

Write notes from the web and from the repo. Give the source for each
note. Start a bold iteration here, not in the code.

Use this format.

```
## <topic> (<date>)
- source: <url or repo path>
- claim: <one sentence>
- evidence: <what the source shows>
- idea: <what it suggests for the bot>
```

## Log

## Local decisions beat global plans (2026-09-20)
- source: https://github.com/T-Py-T/AntsAIBot (docs/reference/xathis/postmortem.txt, 2011 winner xathis)
- claim: The winner made every move from the ant's local environment with no game-phase logic.
- evidence: No turn counting, no win/lose detection, no saved hill locations; same logic on turn 1 and turn 999; per-turn phases initMissions, enemyHills, food, explore, fight, defence, escape.
- idea: Keep our reactive design but fix movement itself; do not add game-phase logic.

## BFS everywhere with short horizons (2026-09-20)
- source: https://github.com/T-Py-T/AntsAIBot (src/bots/xathis_bot.py, port of Strategy.java)
- claim: Every target search is a horizon-limited BFS, not a greedy step.
- evidence: Food BFS horizon 13, explore BFS 11, defence horizon 14, escape check 8; multi-source BFS from foods and hills assigns the first ant found.
- idea: Replace greedy ants.direction steps with a multi-source BFS distance field; greedy steps walk into maze walls.

## Explore value and border missions (2026-09-20)
- source: https://github.com/T-Py-T/AntsAIBot (docs/reference/xathis/postmortem.txt)
- claim: Each tile counts turns since reachable; idle ants walk to the far border.
- evidence: exploreValue resets when reachable within 10 steps; ants BFS 11 steps toward max exploreValue; surplus ants get missions to border tiles (random for fresh spawns, closest otherwise), paths recalculated with A*.
- idea: Our visit counts approximate exploreValue; add border missions for idle ants later in this bold line.

## Combat eval trades ants for position (2026-09-20)
- source: https://github.com/T-Py-T/AntsAIBot (docs/reference/xathis/postmortem.txt, combat section)
- claim: One-turn minimax with eval enemyDead*300 - myDead*180 - dist when 14+ friends near, else 512/768 with no 1v1 trades.
- evidence: Aggressive mode sacrifices 1 for 1 and 3 for 2 but never 2 for 1; passive mode refuses equal trades; distance term pulls ants toward enemies.
- idea: Our majority filter matches passive mode; add an aggressive mode when 14+ friends are near the fight.

## Escape picks max space, not any safe square (2026-09-20)
- source: https://github.com/T-Py-T/AntsAIBot (docs/reference/xathis/postmortem.txt, escaping enemies)
- claim: Among safe moves, ants pick the move with the most open space behind it.
- evidence: BFS 8 from the ant, close tiles weighted most, own ants times 3, enemies times -3; fixed ants dying in maze caves.
- idea: Replace our hold-on-unsafe and fixed fallback order with escape-to-space; explains our maze duel losses.

## Defence intercepts at half path (2026-09-20)
- source: https://github.com/T-Py-T/AntsAIBot (docs/reference/xathis/postmortem.txt, defence)
- claim: One defender per close enemy, sent to the halfway point of the enemy's path.
- evidence: BFS from own hills finds close enemies; defender travels via A* to half-dist tile; unsafe 1v1 accepted to save the hill; only defends with 4 or fewer hills.
- idea: Replace our guard-standing with half-path interception later in this bold line.

## Remembered hills with A* paths (2026-09-20)
- source: bots/pas11/Pas11.py (this repo)
- claim: Enemy hills persist across turns and ants path to them with A*.
- evidence: self.hills remembers sighted hills; A* pathfinding with time-adaptive depth; hill attack within dist 7 when ants outnumber hills 7 to 1; walks ants off own hills so spawn stays open.
- idea: Remember hills across turns and never end a turn occupying your own hill (spawn needs it open).

## Hills before food (2026-09-20)
- source: tools/sample_bots/python/GreedyBot.py (this repo)
- claim: GreedyBot hunts hills first, then food, then ants, then unseen.
- evidence: do_turn tries hunt_hills before hunt_food with standing orders; GreedyBot holds the live lb lead on the board.
- idea: Try hill-first priority order as a later bold variant if BFS movement alone does not pass the champion.

## Standing orders beat re-bidding (2026-09-20)
- source: tools/sample_bots/python/GreedyBot.py (this repo)
- claim: Ants keep food and hill targets across turns instead of rebidding every turn.
- evidence: standing_orders persist [ant, step, dest, type]; each turn only validates the dest still exists, then continues the same mission; our greedy re-sort can swap two ants between equidistant foods every turn.
- idea: Persistent missions keyed by ant with proximity handoff; kills oscillation churn.

## Capped influence spreads ants (2026-09-20)
- source: /tmp/antsresearch/src/bots/influence_bot.py (Whitson influence bot, cloned)
- claim: Each food influences exactly 1 ant, each wave 2, each home hill 4.
- evidence: number_of_influences caps BFS spread per item; emergent spreading without assignment code; our exclusive claims are the same idea done greedily.
- idea: Keep exclusivity; the spreading problem is already solved on our line.

## Waves attack at ant thresholds (2026-09-20)
- source: /tmp/antsresearch/src/bots/influence_bot.py (Whitson influence bot, cloned)
- claim: At 10+ ants, moving wave influencers herd a cohesive unit at the enemy spawn.
- evidence: Wave lines spawn and march toward the enemy hill while momentum keeps ants alive and gathering; our unconditional flood failed at lb 37.87.
- idea: Parked — retry coordinated pushes only with a numbers gate, after missions land.

## Approach forms fighting lines (2026-09-21)
- source: /tmp/antsresearch/docs/reference/xathis/postmortem.txt (approaching enemies)
- claim: Ants near enemies advance on them and form lines, second rank filling gaps.
- evidence: A* to the closest enemy (free tiles first, then through occupied), so rear ants close through holes in the front line; our ants only ever walk to food, hills, or empty ground and never at the enemy.
- idea: Seek-enemy branch between defense and hill-hunting, gated by proximity, safety filter as backstop.

## Corner-post formations around hills (2026-09-21)
- source: bots/pas11/Pas11.py (this repo, HILL DEFEND section)
- claim: Defenders hold diagonal corner posts at distance 1 and 2, not the hill itself.
- evidence: Four corners assigned to the closest free ants per threatened hill, second ring at double distance when heavily threatened; ants already on posts stay; our guards pile onto the hill square and block spawning.
- idea: Formation defense — precompute posts, assign closest spares, hold posts.

## Mission lifecycle: random spawn, closest otherwise, refresh (2026-09-21)
- source: /tmp/antsresearch/docs/reference/xathis/postmortem.txt (missions section)
- claim: Idle ants hold persistent border targets that refresh, never re-bid.
- evidence: Fresh-spawn mission target is a random border tile, otherwise the closest; paths recalculated with A*; interrupted ants discard missions; targets re-searched every turn when time allows, at least every 10 turns; areas come from simultaneous BFS (20-step) with borders where areas meet.
- idea: Frontier missions for idle ants only (food/hill paths untouched); frontier equals unseen neighbors of seen squares, no full-map areas needed.

## Opportunistic eating: forage radius (2026-09-21)
- source: loss-mode analysis over iters 30-38 (dispersed armies, late arrivals)
- claim: Marathon food walks disperse the army and end in death or theft.
- evidence: Global pairs claim food at any distance, so ants cross the map for crumbs while hills burn and crowds form; every FFA collapse features our army scattered and late.
- idea: Locavores — claim only food within 15 steps; distant food waits for wanderers.

## Defense before food: guard first, eat later (2026-09-21)
- source: loss-mode analysis over iters 24-35 (razed while gathering)
- claim: Food-first ordering leaves hills defended by leftovers; threats should draft first.
- evidence: Every challenger keeps food pairs first, so gatherers keep gathering while hills burn; our FFA losses feature opponents razing us mid-gather.
- idea: Militia — closest 4 ants per threatened hill defend and eat nothing; food drafts from the rest.

## Floodgates: mass assault on army size (2026-09-21)
- source: autoresearch/docs/RESEARCH.md (Waves attack at ant thresholds) + iter 7 flood (lb 37.87, gate missing)
- claim: Trickle hunting feeds razers piecemeal; a gated swarm razes and lives.
- evidence: Unconditional flood failed because ants marched from turn 1 in ones; influence waves only march at 10+ ants with momentum; our hunters still trickle one-by-one at the nearest hill.
- idea: No hill-hunting below 15 ants (explore instead); at 15+, every spare marches the oldest remembered hill.

## Routing around kill zones (2026-09-21)
- source: /tmp/antsresearch/src/bots/influence_bot.py (combat_map die_locs)
- claim: Paths should bend around squares the enemy can kill, not just refuse the last step.
- evidence: Die_locs mark enemy reach + kill radius 2 with -150; our BFS walks the shortest path through those squares and the majority test only vetoes the destination, so ants die en route.
- idea: Danger-aware first_step — skip tiles inside enemy attack range (goal exempt), fall back when walled off.

## Combat fields mark death squares (2026-09-20)
- source: /tmp/antsresearch/src/bots/influence_bot.py (Whitson influence bot, cloned)
- claim: Squares the enemy can reach-and-kill get -150, ally-supported ones +100.
- evidence: combat_map precomputes die_locs from enemy reach + kill radius 2, then offsets squares touching grouped allies; movement just climbs the field.
- idea: Our per-move majority test is the equivalent logic; no change needed.
