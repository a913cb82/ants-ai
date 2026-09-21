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

## Aggression gate tuning: 14 is not gospel (2026-09-21)
- source: autoresearch loss-mode analysis (Berserker lb 49.55, closest line, never varied)
- claim: xathis tuned 14+ friends for its scale; our crowds differ and the gate is untested.
- evidence: Berserker swept everything (5-0 + three FFA wins) with the champion's borrowed 14; no iteration ever moved the number.
- idea: Brawler — lower the equal-trade gate to 8 friends, then follow the results.

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

## Blitz: full pressure before turn 25 (2026-09-21)
- source: autoresearch loss-mode analysis (enemies scale while we gather; duel pool is incest RPS)
- claim: Nobody defends early; a full-army rush razes before enemies scale.
- evidence: All our bots gather first and hunt with leftovers, so early razes never happen; sample bots and our kids grow untouched for 100+ turns while we duel over crumbs.
- idea: Blitz — no food claims before turn 25, every ant hunts, guards, or explores.

## Big tapes: hills first, fear verified useless (2026-09-21)
- source: league/games.jsonl big-field podiums (GreedyBot 8) + tools/ants.py finish_turn order
- claim: Hill-first ordering wins big fields; fearless gathering banks nothing.
- evidence: GreedyBot hunts hills before food with zero safety; engine runs orders, battle, raze, spawn, THEN gather — dead gatherers bank nothing, so the wins come from hill pressure, not fearlessness.
- idea: Peak — hill branch before food branch in the ant loop, claims persist.

## Focus battle: 1v1 is mutual death, trade down (2026-09-21)
- source: tools/ants.py do_attack_focus (default engine battle) + spawnradius2=1
- claim: Under focus, 1v1 always kills both; refusing every 1v1 cedes tempo when ahead.
- evidence: Ant dies iff min enemy weakness <= own weakness; lone pair both have weakness 1. Our is_safe refuses all friendless fights, so lone ants dance around lone enemies while losing food and ground.
- idea: Grinder — allow friendless 1v1 engagement when our visible army >= theirs.

## NoCamping is half-applied: moved ants block spawns (2026-09-21)
- source: full re-read of Oracle 79bbd16 (233 lines, first since iter 15)
- claim: Walk-off only iterates held ants; ants that move onto home hills stay.
- evidence: try_step and the explore branch both allow destinations on own hills; guards stepping onto threatened hills and explorers passing over block spawning until something moves them.
- idea: Doormat — refuse own-hill destinations in try_step and explore; nobody ends on a home hill.

## Loss tapes: the threat rule is Berserker's only delta (2026-09-21)
- source: league/games.jsonl (Oracle beaten by Berserker x2) + diff 117f54a..79bbd16
- claim: Oracle IS Berserker plus the closing-16 threat rule; that rule is untuned.
- evidence: The diff shows zero other changes; Berserker (10-only) beats Oracle head-to-head but trails on average (49.55 vs 52.15) — the 16-range inflates threats and wastes guards, while 10-only reacts late.
- idea: Stoic — closing rule at 12 steps, between twitchy and blind.

## Urgency ordering: danger moves first (2026-09-21)
- source: autoresearch loss-mode analysis (contested tiles go to arbitrary engine order)
- claim: First pick of contested destinations should go to ants in danger, not engine order.
- evidence: try_step hands conflicts to whoever moves first; xathis phases food before fight before defence, but our per-ant loop interleaves everything in arbitrary order.
- idea: Marshal — sort movers by nearest-enemy distance, closest first.

## Cohesion fallback: huddle, don't wander (2026-09-21)
- source: autoresearch loss-mode analysis (scatter + late arrivals in every FFA collapse)
- claim: Least-visited wandering sends lone ants to the edges where they die; mass survives.
- evidence: Influence waves herd cohesive units with momentum; our fallback is the only scatter source left untested — every FFA collapse features our army spread thin.
- idea: Huddle — fallback ants step toward the nearest friend (explore only to bootstrap).

## Conservative synthesis: radius plus posts (2026-09-21)
- source: autoresearch loss-mode analysis (Flexitarian 45.78 + Phalanx 42.27, top partials)
- claim: The best failed ideas compose: radius concentrates the army, posts spend the freed spares.
- evidence: Every single-mechanism line loses, but the top three all share a conservative flavor (eat local, guard posts, brave detours); radius leaves more spares, posts need spares.
- idea: Hearth — adaptive food reach plus ring-1 corner posts, judged as one design.

## Ghost hills eat hunters forever (2026-09-21)
- source: autoresearch/bot memory code (remembered_hills) vs xathis re-search rule
- claim: Remembered hills are only dropped when WE own them; razed empty hills haunt memory forever.
- evidence: Discard fires only on my_set, never on visible-and-empty; xathis re-searches targets every turn (at least every 10). Our hunters march on ghosts all game.
- idea: Exorcist — drop remembered hills that are visible with no enemy hill.

## Committed-join pack attacks (2026-09-21)
- source: bots/pas11/Pas11.py (do_move_direction danger_list + potential_orders)
- claim: Lone ants should refuse suicide, but the second ant to a fight releases both.
- evidence: Moves landing near enemies queue as potential until 2+ commit to the same foe, then both orders issue; our is_safe judges static positions, so nobody ever joins an attack in progress.
- idea: Wolfpack — gang the foe with the most friends near it; equal trades allowed when a buddy already committed this turn.

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
