# Idea queue

Statuses: open (live backlog), trying (this round's idea — one only),
done (kept, with the round that proved it), dropped (tested, failed,
with reason), parked (doctrine says not now).

Doctrine (autoresearch-inspired): one idea per round, a fixed exam
(15 gens, train 4, eval 20, Wilson bar > 0.5, borderline repeats),
a written plan with falsification criteria before launch, results
appended after. Rounds stay sequential (single champion lineage).
Pool entry/exit runs on the promotion/demotion rules in
tools/maps/curriculum/README.md.

## trying

- Round 70: q/r/s passenger trial (idea 2, tool-built 40s).
  8-board pool + 3 passengers (c/h absent — rejoin round 71).
  Verdict REPORT-ONLY: pool FROZEN as rung1 + rung2 a-s
  existing (13 boards; c/h rejoin by definition, q/r/s
  members by legislation, stay rule moot). Tripwire
  discounted; passenger judgment leads on knowledge.
  + standing matrix-cycle diagnostic.

## open (ordered — rethought every round boundary; a priority
list, not a schedule. Skip-the-queue rules in runs README.)

- Round 51 candidate: lagged intent channels (user proposal).
  5 extra channels carrying last turn's friendly action
  distributions, visible only where friendlies stand — comms
  with ant-local state intact. Zero-init pad
  (behavior-preserving deploy). Plan in run-comm.md. Gateway:
  ablation gap decides; failure = axis barren, do not build
  bigger. Queued behind the round-50 tripwire (a knockless
  round reopens re-root-or-bank first).
- Behind the gateway, in order: pheromone map (shared decaying
  layer, 1-2ch, stigmergy); learned messages (CommNet-style,
  two-stage forward, rotates with D4); recurrent hidden state
  (needs sequence PPO — big, last resort). Frame stacking
  (last-window channels) reviewed and passed over: intent
  subsumes its motion cues where it matters (neighbors).
- Staged: rung2q/r/s (40x40, 4 hills, upstream-tool-built:
  cavemap/maze/walk). k-p batch deleted (k/l sterile, m/n
  predicted sterile, o/p scrapped for tool-built). Pool entry
  by the per-map trial rules: round 70 auditions q/r/s as
  passengers (stay >10% decisive each).
- Conditional: rung 3 = full real pool (148 maps). Needs 2-in-10 on
  current pool. NO held-out splits at any size (standing rule):
  every rung board trains and evals every gen — per-gen coverage
  arrives with the volume round; rotation covers at round level
  until then. Graduation re-decided every round.
- Conditional: kill/death removal, pure-outcome ablations —
  ESCALATED to idea 6 (last resort). Dense stalled 9 rounds
  (60-68), but gating (idea 1) is the targeted fix first;
  pure-outcome stays behind it. Note: mirrors make wins
  luck-heavy, so this one risks noise — hence last.
- Idea 5 (queued): combat-proportional draw tiebreak. The
  dropped tiebreak paid survival (perverse); this variant
  prices FIGHTING in draws (kill-scaled), which is the exact
  missing incentive in a turtle field. Applies to TRAINING
  returns first (exam integrity: promotion still reads W/D;
  revisit only if training works). Plan needed before launch.
- Queued volume fix (user-ordered, 3:1): train 4 -> 30
  opponents (60 engine games vs the sacred 20-game exam)
  + workers 8 -> 12. Tests the under-training hypothesis
  (thin education, not field ceiling, explains weak knocks).
  Exam byte-identical. Watches: wall-clock/gen, batch rows,
  pg/v health, train wins per board, knock quality. Runs
  after the 1-4 program (mid-trial changes confound). Dial
  the level from data after one round.
- Follow-up chain: if oasis (idea 2) works → generator survey
  for more mechanics (hunger/low-food boards, central-hill
  king-of-hill). If oasis fails → map-mechanic axis likely
  barren, drop it (48s + oasis both sterile = geometry won't
  fix incentives).
- Standing diagnostic: matrix-cycle check folds into round
  briefs (cheap; three lines + main may cycle).
- Watch items (symptoms first): three-role asymmetry (cycles in
  matrix), Nash-main selection (Wilson promotes collapsing
  specialists), remaining generator survey (pool has room to 12).

Each experiment ships with acceptance/falsification criteria in its
plan file before launch. See Discard bar below for what it takes
to drop one.

## done

- Rounds 17-50 (condensed; detail in run-*.md): D4
  symmetrization (round 16, kept as hygiene); KL anchor (round
  17, kept at 0.01 until round 45 proved it irrelevant either
  way, now 0.0); wide field 15x15 + own-sight (round 18, kept,
  negative verdict); DEATH -2 asymmetric base (round 19, still
  live); frontier training (rounds 39-41: window-15 rivals +
  guaranteed champ slot — ended the 94-gen drought, g611);
  persistent rival lineage (round 42+: counter-styles need
  time; 7 of 8 crowns this era rival-line; gatekeeper reframe
  round 46 — main gates ~.45, rival climbs); ledger rebalance
  (round 46: main HA 0.5 -> 0.25, rival pinned 0.5; mechanism
  wrong for the main, regime kept climbing 3/15).
- Rounds 13-16: exploiters with teeth (BC base + kill-heavy) +
  continuous main lineage + D4 symmetrization. 7 promotions in 60
  gens (g208, g212, g236, g245, g253 + 2 exploiter crowns g222,
  g246); chains depth 34; symmetrization kept as hygiene (100%
  agreement, free). Score-peace overturned: funnel draws hide
  bloodbaths (44 deaths) — conversion problem, not pacifism.
  Demotion bar now contact-based. All live as infrastructure.

- Rung-2 extended pool (rounds 11-12): rung 1 + rung2a-d, then
  f/g/h/i/j staged in. Gap twin-bars, pond twin lakes, 2d back to
  4x4 texture, generated rung 3 deleted, e cut as redundant.
- Eval on train pool (rounds 11-12): no split under 13 maps, evals
  run the train boards with rotation. Held-out promotion evals stay
  parked until a 13+ same-rung pool.
- BC-from-pros init (round: bc-30): gen-1 starts where 10 random
  gens couldn't reach. Kept.
- Split critic trunk + full banking (round: bc-30/run2): critic
  learns across gens. Kept.
- Batch-level advantage norm (probes): events stay large, noise
  stays small. Kept.
- Rotation augmentation (round 5): quadruples directional coverage.
  Kept.
- Undecayed outcome (round 5b): win belongs to every move. Kept.
- Wilson-only promotion (round 5): Nash can't rank star data. Kept.
- Rung-1 tiny curriculum (rounds 4-5b): first promotions. Kept.
- FOOD restore (round 8): 3 promotions vs 0/30 without. Kept.
- Rung-2 pool (round 9): 3 promotions, transfer confirmed. Kept.
- Per-map game logging (round 10 prep): map basename per game row.
  Kept.
- Train-map rotation by generation (round 10): pools over 4 maps
  train fully. Kept.
- Toroidal water rule (rounds 10-11): wet both routes or span with
  an edge twin. Kept, in ladder doc.
- Upstream generator repairs: amstan import, cell_maze dict_keys,
  symmetric/asymmetric float division. Kept (generator-only).
- Cave boards via fixed amstan (round 12 staged): enclosed-arena
  texture, smokes decisive. In pool.
- Mapgen tile boards f/g/h (round 12 staged): upstream rotational
  generator at 24x24. In pool.

## dropped

- Material tiebreak (round 11): mechanism worked (draws separated
  -1.28..+1.65) but the incentive is perverse — survivors get paid,
  so not-fighting pays twice. Rung-1 peace 0.68 -> 0.75, decisive
  boards went quiet, 0 promotions. Reverted. Lesson: price winning,
  never survival. Reopen if: combat-proportional variant (tiebreak
  scaled by kills, not bodies), or small-boards-only trial.
  Single-round evidence — needs a repeat before permanent burial.
- gen2p boards (round 11): 3.3% and 5.1% decisive — cut per the
  demotion bar.
- Generated rung 3 (rung3a-d): wrong direction — rung 3 is real
  boards. Pond had a dry toroidal route; gap same flaw. Proven
  open map cut as redundant; rest + generator deleted.
- Rung 3 as random_walk pool (round 10): every rw board
  zero-decisive at 150 turns — too big to meet, zero signal.
  Parked for rung 4 with longer turns/tiebreaks.
- APPROACH/ENGAGE shaping (probes): signal fires, no conversion;
  stacked cleverness, deleted for simplicity.
- FOOD removal (rounds 6-7): 0 promotions in 30 gens. Reverted.
- Outcome decay (round 5): unjustified discounting. Dropped.
  WEAK EVIDENCE (0/5 decayed vs 3/15 undecayed, confounded) —
  kept on theory (time distance != causal distance), not data.
  Reopen if undecayed ever stalls with early-game blindness.
- Draw-as-loss (global): stays dropped — SUPERSEDED by idea 3
  (selective draw-penalty games, fraction of train games).
  If idea 3 works, this entry closes as its ancestor.
- 60-turn evals: truncate before skill gaps compound. Dropped for
  eval-turns 150.
- Pure-outcome ablation: still last resort (mirrors make wins
  luck-heavy). Never run; stays dropped unless dense stalls 40+.

## parked

- Curiosity/count-based exploration: maps are small, coverage is
  free. Revisit on full-pool mazes if scouting stalls.
- Formation/cohesion rewards: constrains more than it teaches.
  Revisit if armies dissolve into skirmishers on big maps.
- Time penalty for slow wins: a win is a win. Revisit never unless
  draws return.
- Medium architectures: capacity is not the constraint —
  trigger REFINED (round-68 bank): reopen on UNDERFITTING
  SIGNAL (train wins vanish, critic stops fitting, pg dies),
  not on promo stall (the old trigger fires on Nash ceilings
  too, where bigger nets just draw faster). Promo stall alone
  no longer reopens it.
- Asymmetric upstream maps in curriculum: asymmetry belongs to
  rung 3 real pools, not the symmetric curriculum. Don't generate;
  rung 3 covers it.
- McMaps generator: image-based tooling, likely skip. Verdict
  pending a 5-minute check, not a project.
