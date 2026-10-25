# Idea queue

Statuses: open (live backlog), trying (this round's idea — one only),
done (kept, with the round that proved it), dropped (tested, failed,
with reason), parked (doctrine says not now).

Borrowed from the autoresearch loop: one idea per round, a fixed exam,
a noise bar, and a written queue so reassessment picks the next idea
instead of inventing one. Not borrowed: parallel blind explorers —
rounds build on one champion lineage, so variants run sequentially,
and the round itself is the scored exam.

## trying

- Draw tiebreak by material (round 11 revised): drawn games pay
  +1.0 to the side with more ants alive, -1.0 to fewer, 0 equal.
  Draw-only, binary, undecayed. Tests whether material tiebreaks
  un-dud big peaceful boards without reopening the farming trap
  (comparative, mirrors zero it). Single experimental variable;
  the pool rebuild below is prerequisite, not variable.

## open

- Eval redesign: promotion duels on the TRAIN pool (same boards,
  full 20-duel concentration); generalization as separate
  display-only probes on held/next-rung boards. Held-out promotion
evals are board-quirks lotteries at low variety and test the wrong
skills across rungs. Implement after round 10b (no ml/*.py edits
mid-round). Then re-audit any 10b promotion board-by-board.
- Per-role exploiter rewards: kill-heavy shaping for exploiter gens
  only, main line untouched. Tests whether a killer-exploiter forces
  champion defense (arms race). Next structural idea if rung 3 stalls.
- Hill-approach shaping: reward closing distance to the enemy hill
  (most score-adjacent shaping left). Only if exploiters don't bite.
- Kill/death removal ablation: HILL + outcome only. Queued behind
  the food verdict (food proved load-bearing; kills untested).
- Pure-outcome ablation: WIN/LOSS only. Last resort; mirrors make
  wins luck-heavy, so expect this to fail — run only for the record
  if everything dense stalls for 40+ gens.

## done

- Rung 2 extended (round 11 revised prerequisite): rung 1 +
  rung2a-e (gap full-span, lakes on-corridor + edge pair, pond twin
  lakes, e = proven open) + 2 smallest real boards (gen2p_00,
  tutorial1 — drew asymmetric smoke, passengers under test).
  Tests the pool, not the variable.

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

## dropped

- Generated rung 3 (rung3a-d): wrong direction — rung 3 is real
  boards. Pond had a dry toroidal route; gap same flaw. Proven
  open map survives as rung2e; rest + generator deleted.
- Rung 3 as random_walk pool (round 10): every rw board
  zero-decisive at 150 turns — too big to meet, zero signal.
  Parked for rung 4 with longer turns/tiebreaks; rung 3 rebuilt
  as generated mid-size boards.

- APPROACH/ENGAGE shaping (probes): signal fires, no conversion;
  stacked cleverness, deleted for simplicity.
- FOOD removal (rounds 6-7): 0 promotions in 30 gens. Reverted.
- Outcome decay (round 5): unjustified discounting. Dropped.
- Draw-as-loss: per-minibatch norm washes constants. Never tried
  for cause; stays dropped.
- 60-turn evals: truncate before skill gaps compound. Dropped for
  eval-turns 150.

## parked

- Curiosity/count-based exploration: maps are small, coverage is
  free. Revisit on full-pool mazes if scouting stalls.
- Formation/cohesion rewards: constrains more than it teaches.
  Revisit if armies dissolve into skirmishers on big maps.
- Time penalty for slow wins: a win is a win; distorts nothing
  worth distorting. Revisit never unless draws return.
- Medium architectures: base and deep-narrow both move; capacity
  is not the constraint. Revisit after 3 promotions stall anywhere.
