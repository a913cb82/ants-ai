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

- Round 12: tiebreak reverted, back to rung 2 (round-9 rewards).
  Pool 10 boards (rung 1 + rung2a-d/f/g/h/i/j, all train).
  Tests whether removing the pacifism incentive + duds restores
  promotions on proven small ground with new textures.

## open (ordered)

Each experiment ships with acceptance/falsification criteria in its
plan file before launch. See Discard bar below for what it takes
to drop one.

- BC-base + kill-heavy exploiters (round 13 TRYING): AlphaStar base
  reset + TStar-school role shaping (attribution corrected — the
  shaping is not AlphaStar's; they keep one reward). Acceptance:
  exploiters win duels / promotion / champ margins compress.
- Continuous main lineage (AlphaStar baseline, round 14 candidate):
  ONE main that trains continuously and never resets — parent chains
  fall out automatically, no branch caps, no prune rules. Round-13
  manifest proved the need: 19/20 members parented to g160, one-step
  mutations from one point cannot walk away from it. Periodic
  exploiters (supervised reset, live) + PFSP-lite (live) complete the
  shape. Deviations need justification + a path back (doctrine).
  Acceptance: promotion rate up vs reset-regime on same pool;
  falsified if the main rots (eval floor falls over gens).
- KL anchor to supervised base: penalty toward g000 weights during
  training (AlphaStar bounds main drift; ours drifted 100+ gens
  unleashed). Acceptance: promotions continue past current stall
  with less drift; falsified if it shackles adaptation (margins
  freeze).
- Three-role asymmetry: exploiters face mains only, never each
  other; beaten mains join a permanent league sampled by PFSP
  (AlphaStar ME/LE). Only if cycles appear (rock-paper-scissors
  in the matrix: A beats B beats C beats A). Watch item, not live.
- Nash-main selection: promote the least-exploitable (Nash mixture
  weight) instead of Wilson-vs-champ. Only if Wilson promotes
  specialists that later collapse. Watch item.

- BC-base exploiters (round 13 candidate): exploiter gens spawn
  from BC-from-pros weights instead of random init (AlphaStar:
  exploiters reset to the supervised base). Fresh eyes, competent
  hands — turns 0-7 target practice into selection pressure.
  One-line change; small and safe.
- Exact D4 symmetrization in forward(): average all 8 dihedral
  orientations inside the model (probe: 41% agreement, east bias).
  Weight-compatible, train=act coherent. Acceptance 100% by
  construction + promotion rate vs control.
- Asymmetric league matchmaking: exploiters face mains only, never
  each other (AlphaStar ME/LE structure). Only if cycles appear.
- Hill-approach shaping: reward closing distance to the enemy hill.
  Only if exploiters don't bite.
- Kill/death removal ablation: HILL + outcome only. Queued behind
  the food verdict (food proved load-bearing; kills untested).
- Rung 3 = full real pool (148 maps): needs 2-in-10 on rung 2,
  then train-slot reservation for curriculum drills (each board
  trains every ~37 gens otherwise) + held-out evals return (13+
  same-rung boards earn the split back).
- Remaining generator survey: symmetric_mapgen small-2p driver,
  McMaps verdict (likely skip — image-based), random/heightmap
  drivers, Java Test run. Parked until round 12 lands; winners
  displace, pool caps at 12 (no split).

## done

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
- Draw-as-loss: per-minibatch norm washes constants. Stays dropped.
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
- Medium architectures: capacity is not the constraint. Revisit
  after 3 promotions stall anywhere.
- Asymmetric upstream maps in curriculum: asymmetry belongs to
  rung 3 real pools, not the symmetric curriculum. Don't generate;
  rung 3 covers it.
- McMaps generator: image-based tooling, likely skip. Verdict
  pending a 5-minute check, not a project.
