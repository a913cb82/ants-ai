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

## Tripwire: guards answer at 8 (2026-09-21)
- source: defense-radius audit at iter 98 (static 10 untouched on wall base)
- claim: Bulwark over-defends; closer tripwire frees hunters.
- evidence: Bloodhound proved the static radius load-bearing by dropping it (11.94); narrowing was never tried. Bulwark's wound is FFA 2nds, a pressure shortfall.
- idea: Tripwire — static threatened radius 10 to 8 on Bulwark base.

## Field drift: the bar is frozen, the pool hardened (2026-09-21)
- source: iter 108 diagnostic (Oracle 79bbd16 tactics re-run as 56d358c)
- claim: 52.15 was set against HunterBot-era fields; modern children beat champion-style play.
- evidence: Identical code scored 52.15 at iter 15, 13.09 today (2-3 duels, 7/7 FFA). Duel foes and FFA fields are all descendants now.
- idea: Keep hunting Bulwark-family gains; 49.78-modern needs ~2.4, and the number is regime-noisy. No re-tag without beating 52.15.

## Odds: equal trades at 10 (2026-09-21)
- source: aggression audit at iter 120 (14-rule tuned champion-era, never on wall)
- claim: Cheaper equals mean more pressure where Bulwark is short.
- evidence: Berserker-line set 14 on the champion base; Bulwark's wound is FFA 2nds.
- idea: Odds — 14-rule at 10 on Bulwark base.

## Relief: fearless reinforce (2026-09-21)
- source: Homeward 67c7703 wounds (three 2nds, reinforcements late)
- claim: Late reinforcements never win; fearless ones arrive.
- evidence: Homeward's safe reinforce podiums everywhere but wins nowhere (35.31).
- idea: Relief — reinforce step skips safety.

## Alarum: walk-off reinforces defense (2026-09-21)
- source: walk-off audit at iter 135 (threatened hill never targeted)
- claim: Holders should reinforce the wall, not wander.
- evidence: Walk-off mapped default/hills/food/enemy; defense-reinforce untried. Bulwark's wall wants bodies.
- idea: Alarum — walk-off heads to nearest threatened hill.

## Crowd: fearless under ten enemies (2026-09-21)
- source: rematch tape reread (Bulwark 86 to 20 donating into crowds)
- claim: Hunters should press small fights and survive big ones.
- evidence: Dragnet's safe hunters grew 62 to 131 while Bulwark's fearless ones melted; donations happen in crowds, not duels.
- idea: Crowd — fearless ahead unless 10+ enemies visible.

## Legion: press needs ten ants (2026-09-21)
- source: Recruit cb5e229 wounds (3-2 duels; growing-true from turn 1)
- claim: Early growth is spawns, not winning; fearless babies donate in duels.
- evidence: Army grows monotonically early (no combat yet) so growing is always true; Recruit's duels bled while its FFAs thrived.
- idea: Legion — fearless ahead, or growing with 10+ ants.

## Avenge: total press when bleeding (2026-09-21)
- source: dynamics audit at iter 126 (levels used, trends never)
- claim: Lost hills should trigger desperation, not routine.
- evidence: Frontrunner used hill levels; no bot reacts to LOSING hills. Bulwark bled out late in its 8p loss without changing gear.
- idea: Avenge — below max hills held, hunt full-fearless.

## Gang: hunt only with a pack (2026-09-21)
- source: rematch tape of Bulwark's 8p loss (maze_p08_07, pseed 97628294)
- claim: 86 ants with zero razes in 670 turns means trickle-donation, not bad luck.
- evidence: Bulwark killed Closer by t252 (9 pts), peaked 86 army at t700, razed nothing until t923, melted to 20 while Dragnet grew 62 to 131 and razed 8 more hills. Fearless solo hunters donate into crowds.
- idea: Gang — hunt iff 3+ friends within 10, else pack up toward nearest friend.

## Shortfuse: closing threats at 14 (2026-09-21)
- source: defense-number audit at iter 117 (closing-16 untouched since iter 15)
- claim: Later warnings free hunters without losing hills.
- evidence: Static radius mapped 8/10/12 with peak at 10; closing radius never tuned. Bulwark's wound is FFA 2nds.
- idea: Shortfuse — closing threatened radius 16 to 14 on Bulwark base.

## Usher: route spawns to the front (2026-09-21)
- source: tools/ants.py do_spawn (least-recently-touched first, standing blocks)
- claim: Spawns should arrive at the front hill, not the safest back hill.
- evidence: Walk-off opens all hills; spawn location is emergent. Engine docstring says standing controls it. Never tried in 114 iterations.
- idea: Usher — sitters hold back hills, front hill stays open.

## Elastic: Bulwark plus adaptive food (2026-09-21)
- source: Flexitarian dfce6c0 (reach 8+army, lb 45.78) + Bulwark 6329ae1 (lb 49.78)
- claim: Local gathering feeds the wall; reach grows with the army.
- evidence: Best-pedigree untried combo; food-radius tuning never touched the wall base.
- idea: Elastic — Bulwark with reach-filtered food claims.

## Ram: all hunters one hill (2026-09-21)
- source: concentration audit at iter 104 (per-ant-nearest trickles in big fields)
- claim: One rammed hill falls; five tickled hills hold.
- evidence: Hunters split across remembered hills nearest-first; Bulwark's 2nds come in big fields with many hills. Concentration was never tried on the wall base.
- idea: Ram — all hunters target the hill nearest the army centroid.

## Mugger: hunt the strongest hill (2026-09-21)
- source: target-axis audit at iter 101 (nearest held, weakest failed)
- claim: Concentration beats trickle; gang the most-defended hill.
- evidence: Hunters split across remembered hills nearest-first; weakest-first scattered pressure (25.51). Strongest-first is the untested cell.
- idea: Mugger — hunters target the hill with most enemies near it.

## Redoubt: two guards per hill (2026-09-21)
- source: guard-branch audit at iter 95 (unbounded pile-on since iter 4)
- claim: The third guard on a hill is a wasted hunter.
- evidence: Every foodless ant marches on the nearest threatened hill; over-defense starves pressure while one razer ties down five ants.
- idea: Redoubt — max 2 guards per threatened hill per turn, the rest hunt.

## Trawl: Dragnet grows teeth (2026-09-21)
- source: Bulwark 6329ae1 wounds (both FFA 2nds behind Dragnet 35daee3)
- claim: Pack-screening plus fearless-ahead hunting beats either alone.
- evidence: Dragnet 39.80 (safe hunt + pack screen) beat Bulwark 49.78 head-to-head twice; fearless-ahead is the load-bearing half of every wall.
- idea: Trawl — Dragnet base with fearless-ahead hunting.

## Anchor: safe hunt behind the wall (2026-09-21)
- source: Bulwark 6329ae1 ablation (fearless-ahead cost 7 on champion base)
- claim: The wall works; fearlessness may be dead weight on it.
- evidence: Bulwark 49.78 carries Closer hunting, but safe-hunting beat fearless-hunting 52.15 to 45.13 on the champion base.
- idea: Anchor — Bulwark defense with safe-always hunting.

## Onslaught: fearless hunt meets interception (2026-09-21)
- source: best-mechanism audit at iter 86 (Closer 45.13 + Screen 39.04, never combined)
- claim: Total pressure — fearless-ahead hunters plus intercepting guards.
- evidence: The two best post-Oracle mechanisms are both pressure-flavored; previous synthesis mixed caution mechanisms. Pressure may compound instead.
- idea: Onslaught — Closer base with Screen interception defense.

## Screen: intercept razers off the hill (2026-09-21)
- source: defense-branch audit at iter 83 (guards walk at the hill since iter 4)
- claim: Meeting the razer away keeps the hill spawnable and unrazed.
- evidence: Guards pile onto threatened hills, blocking our own spawns while the razer picks fights; interception was never tried.
- idea: Screen — defense branch targets the enemy nearest the threatened hill.

## Hotspot: most-visited explore (2026-09-21)
- source: knob audit at iter 80 (explore least-visited unchallenged since iter 6)
- claim: Spreading thin loses big fields; massing wins them.
- evidence: Every challenger spreads via least-visited explore; late-game ants trek to corners while fights rage center. Most-visited was never tried as a pure explore rule.
- idea: Hotspot — explore fallback prefers most-visited neighboring squares.

## Surge: ahead means fearless everywhere (2026-09-21)
- source: Closer e170c5f wounds (2/5 behind Bodyguard, duel loss to Hornet)
- claim: Closer presses with hunters only; gatherers stay careful while ahead.
- evidence: Fearless-ahead hunting won two FFAs (lb 45.13, best in 60); nothing covers the economy side of a lead.
- idea: Surge — food branch also skips safety when ahead on hills.

## Frontrunner: hill count is the score proxy (2026-09-21)
- source: tools/ants.py scoring (raze +2/-1, kills fractional) + game length (elimination or 1000)
- claim: Hill lead wins; hunting from ahead feeds razers for nothing.
- evidence: Score comes from razes far more than kills; bots cannot see score, but my_hills vs remembered hills is visible. Every iteration hunts unconditionally.
- idea: Frontrunner — skip hill-hunting while ahead on hills; defense and economy continue.

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

## Census-tertile selection (2026-10-04)
- source: placement round iters 126-200, champion iter 133
- claim: the MSE-optimal opponent policy is wrong for the lb loop.
- evidence: synthetic validation (200 bots, seeds 0-2, real selection
  code both sides) gives census-tertile rating MSE 551 vs info-score
  679, but mean budget-end lb 5.72 vs 9.76 and rank correlation 0.940
  vs 0.957, all seeds. Package retest (each exam with its native
  score): corr(mu,true) is 0.949 new vs 0.965 old, corr(lb,true) is
  0.946 new vs 0.959 old. The score change helps both exams a little;
  the exam gap dominates. Info-score collapses sigma faster, and lb
  punishes sigma threefold.
- idea: keep info-score selection. Do not port MSE policies without
  validating on lb and rank correlation first.

## Census-tertile harness (2026-10-04)
- source: placement round champion iter 133; validation scripts
  /tmp/validate_harness.py (faithful 30-slot shapes, seeds 0-5)
- claim: the 3x10p census-tertile exam with mu scoring ranks bots
  truer than the duel+FFA info-score exam with lb scoring.
- evidence: corr(recorded score, true skill) is 0.964 new vs 0.962
  old across 6 seeds; new wins 5 of 6 (loses seed 3 only). Full 2x2:
  corr(mu) is 0.9654 new vs 0.9655 old (exam tie), corr(lb) is
  0.9632 new vs 0.9619 old. Sigma-discount ladder (means): old
  0.9655/0.9650/0.9638/0.9619, new 0.9654/0.9655/0.9648/0.9632
  for k=0/1/2/3. Every discount step costs ranking; mu and mu-1s
  tie best, so the shipped mu stands.
- idea: shipped as the harness. Old-budget rows stay filed under
  their tag and no longer count for champion.

## Mu scoring on the old exam (2026-10-04)
- source: /tmp/validate_harness.py 2x2 plus sigma-discount ladder,
  faithful 30-slot shapes, seeds 0-5
- claim: the old exam ranks truest with mu scoring; the discount ladder
  falls monotonically under both exams.
- evidence: corr with truth is 0.9655 old+mu (tied best), 0.9654
  new+mu, 0.9632 new+lb, 0.9619 old+lb. Ladder for k=0/1/2/3 is
  0.9655/0.9650/0.9638/0.9619 old and 0.9654/0.9655/0.9648/0.9632
  new. Shipped: old exam, mu score, budget tag score=mu. Old-lb rows
  stay filed and no longer count.
- idea: keep this package unless a new exam beats 0.9655 with mu.

## Combat search: non-xathis postmortems (2026-10-04)
- source: web research (ketch search + scrape, Wayback for dead forums)
- claim: no strong bot searched deep; the field converged on 1-turn horizons with an explicit enemy reply and default-refuse 1v1s.
- evidence: 7 writeups below; deep alpha-beta absent everywhere, sampling vs 1-ply minimax genuinely contested.
- idea: scope combat work to battle-local 1-ply max-min with precompute, not depth. Reserve: pages 2-6 of both forum threads.

## a1k0n combat by random sampling (2026-10-04)
- source: https://web.archive.org/web/20130330010801/http://forums.aichallenge.org/viewtopic.php?f=24&t=2044 (top 10, Dec 2011)
- claim: sampling beats minimax, which is too conservative for simultaneous moves.
- evidence: per-ant Dirichlet(1,1,1,1,1) over 5 moves; random ant, best reply by provisional resolution until time runs out; tried sampled-minimax, worse. Weakness: accidental suicides vs cautious walls.
- idea: if 1-ply max-min stalls, try the sampler as the anytime fallback, not deeper search.

## Memetix influence combat (2026-10-04)
- source: https://web.archive.org/web/20130122064921/http://forums.aichallenge.org/viewtopic.php?f=24&t=2083 (beat a1k0n head-to-head, Dec 2011)
- claim: single-pass influence maps decide SAFE/KILL/DIE in 3-5 ms; allow KILL (expect 1-for-1) only to break deadlocks.
- evidence: influence[p][r][c] = ants that could attack each tile after 1 move; in-thread refinement for one-ant-per-tile overcounting.
- idea: precompute influence as the cheap combat path; conflicts with xathis on trades (permits 1-for-1 KILL), agrees on 1-turn horizon.

## delineate heuristic combat (2026-10-04)
- source: https://www.decompilinglife.com/post/14396418230/2011-google-ai-challenge-ants (top 10, briefly top 3)
- claim: zero search can reach top 3; kill bonus only with strict local superiority, conservative at equality.
- evidence: greedy 5-move scoring from BFS feature fields 1/(1+d^2); biggest Elo jump came from persistent exploration paint, not combat.
- idea: keep a strict-superiority gate as the floor; economy/exploration may outrank combat tweaks.

## nhaehnle tactical 1-ply max-min (2026-10-04)
- source: http://nhaehnle.blogspot.com/2011/12/ai-challenge-look-back.html (top 20, src https://github.com/nhaehnle/aiant)
- claim: 1-ply max-min over sampled enemy moves with probabilistic aggression is xathis with a softer trade gate, plus per-opponent strategy selection.
- evidence: Tactical module carves combat submaps, iterates until time out, no lookahead; overvalues own ants by default, aggressive mode with logistic probability in log(own/enemy); a1k0n sampling tried, worse than his tactical code.
- idea: closest template for our General iteration; add opponent-specific arbitration later, not first.

## anthonyvh greedy fixing (2026-10-04)
- source: https://www.anthonyvh.com/2013/03/27/ai_challenge-ants/ (53rd/7897)
- claim: exact search rejected past 10-ant zones; Memetix influence plus greedy sequential fixing, suicide only to unblock hill rush.
- evidence: combat eval 200 ms to 5-10 ms via local updates and lazy bucketed queue; stationary enemies pinned during eval.
- idea: sequential pin-and-reevaluate fits our per-ant move order; pin stationary enemies first.

## codetiger Python time datapoint (2026-10-04)
- source: https://codetiger.in/blog/google-ai-challenge-ants-2011-post-mortem (127th, Python bot)
- claim: full search infeasible in Python under the turn limit; precomputed resolutions end 1v1 deaths.
- evidence: timed out with 2-radii battle resolution; switched to precalculated tables; sacrifices 1v1s only near own hills (radius 14) to hide them.
- idea: our combat must precompute; never resolve live per ant. Hill-radius-gated sacrifice matches xathis's distance exception.

## Michigan battle resolution (2026-10-04)
- source: https://nickb.dev/blog/engr151-google-ai-challenge/writeup.pdf (claimed top 25)
- claim: 2-stage static/threatened analysis with stay/advance enemy model and fewest-ants preference approximates 1-ply cheaply.
- evidence: recursive per-ant search over desired squares, +1 moved / -1 new enemy drawn in; early exit; crashes only past 20 ants a side.
- idea: coarser enemy model is viable if best-response min proves too slow; fewest-ants preference is another no-1v1 gate.

## xathis source corrections (2026-10-04)
- source: T-Py-T/AntsAIBot Strategy.java (1773 lines, authoritative; xathis_bot.py is a stub, do not quote it)
- claim: two gates exist (14 for groups, 6 for detached 1-for-1s), "never 2-for-1" is emergent from the eval, and strict phase order is load-bearing.
- evidence: beAgressive = max Chebyshev-5 friend count >= 14 over the whole fight; detached attacks use >= 6 with eval +/-5000; 1-ply minimax with alpha-cut and best-reply enemy produces refusals from constants, no veto; do_turn order initMissions/enemyHills/food/initExplore/createAreas/fight/defence/approachEnemies/attackDetachedEnemies/escapeEnemies/distribute/explore/missions; hill/food claimants are hasMoved and skip combat grouping; single-ant prec groups skipped (1v1s fall to escape/approach).
- idea: port the 6-gate for detached attacks; try fight-as-phase (claimants excluded from combat) instead of our interleaved per-ant loop.

## GreenTea exhaustive safest-then-nastiest (2026-10-04)
- source: git.code.sf.net/p/ants2011/code (MyBot.java 2502 lines, BattleCalculator.java 1003 lines); brunneng postmortem (2nd-3rd/7897)
- claim: exhaustive joint-move minimax over local battles capped at 7 ants total, keep only moves no reply wipes out, then most aggressive tiebreak.
- evidence: connectivity grouping within attackRange, smallest-first with committed destinations constraining later battles; eval modes Aggressive mine/theirs ratio, Exchange 0.75*mine-theirs near own hills, Defensive 2*mine-theirs; learned per-complexity time model (run only if timeLeft > 2x avg); food-aware re-fight (survivors on food spawn, re-fight); isMoveDanger counterfactual + rescue ants; 76 tracked improvements 3-15% each.
- idea: implement capped-7 exhaustive with safest-then-nastiest tiebreak as a 9th approach; reuse its Exchange-near-hills switching.

## lazarant intention propagation (2026-10-04)
- source: lazarant.zip via Wayback forums (19 Java files, ranked 2nd at write time, #6 final)
- claim: per-ant ATTACK/SUPPORT/ESCAPE/IGNORE/SKIP intentions propagate over friend links with ESCAPE frozen; no search.
- evidence: ATTACK iff (my1st+my2nd > en1st+en2nd) AND (my1st > en1st); angryMode (+1 first line) at 67% visible + 2x ants; 1v1 per-color history exploits escapers (10+ samples, escapes > 9x attacks -> IGNORE and walk away); coordinated direction flood-fill; priority chain waitFood > hill-hold > hillAttack3 > combat > food25 > explore25 > control45.
- idea: implement intention propagation as a 10th approach; the escaper-exploit is unique (model the opponent, not just the board).

## runevision need-based resolution (2026-10-04)
- source: blog.runevision.com Part I + MyBot.cs 1175 lines (rank 4-11)
- claim: per-ant 5-move combat scores plus goal bonuses, contested squares resolved to whoever needs them most.
- evidence: exact goal costs (defense 12% of ants, enemy hills 1/3 army, food cost 4, explore 25, enemy ants 20 at cost 42 maxdist 13); flood-fill pathing with ants as high cost; DEBUG build auto-tuned parameters overnight over hundreds of games (a 2011 harness like ours).
- idea: replace binary safe/unsafe veto with additive combat+goal scoring + need-based arbitration; copy the goal table as starter numbers.

## Memetix homepage numbers (2026-10-04)
- source: blackmoor.org.uk/AI.htm (climbed to 2nd)
- claim: stagnation-gated breakthrough + push-without-swap queueing were the biggest jumps.
- evidence: gravity weights (food 8, unexplored 3, enemy hill 16, own hill 3, enemy ant 1); breakthrough gate = growth positive over 10 turns AND 32+ unmoved ants (16 late-game); move order lowest-total-first with push (never into death tiles); stuck-5-turns +5 cost.
- idea: key aggression to growth-plus-idleness (deadlock detection), not static friend counts.

## MBCook priority chain (2026-10-04)
- source: foobarsoft.com postmortem (2nd-best Clojure, 1335th)
- claim: unhesitating hill suicide + 8-square flee beats trade-gate tuning; exclusive food reservations gather less than shared claims.
- evidence: chain defend > emergency > capture-hill (suicide charges) > run-away (flee within 8) > food > random; reservations measured worse than greedy sharing.
- idea: test whether our exclusive food claims are the reservation mistake; try capture-outranks-survival ordering.

## Parasprites worst-case bounties (2026-10-04)
- source: forums t=2169 via Wayback (27th)
- claim: 5-scenario worst-case (enemies move together) with living-enemy bounty of half an ant, constraint-solved per island.
- evidence: score = casualties + bounties, take the WORST scenario; constraints no-collide/no-swap/no-possible-enemy-squares; arc-consistency + island split + time-shared greedy.
- idea: worst-case (not best-reply) enemy model with fractional bounties prices caution without full minimax.

## fourmidable probabilistic trades (2026-10-04)
- source: forums t=2161 attachment via Wayback (13th at post, #9 final)
- claim: 3-tier combat with probabilistic trade tags p=(n/(0.6e))^3 and exhaustive subgroup minimax at tier 1.
- evidence: tier 1 subgroup combat, tier 2 pathfinding, tier 3 probabilistic tags with density-estimated enemy counts.
- idea: probabilistic (not binary) trade acceptance scaled by local odds.
