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

- Round 44: climb continues (same config). Pace 4/30; watch
  whether the main can take a rival-held crown.
  (Round-35 verdict: APPARENT exhaustion, CONFOUNDED — clones'
  kl pinned 0.01, anchor dragged them to BC; see run-teeth2.md.)
- Round 28 verdict: GAP STERILE (0 promos, g441 holds). Conversion
  38.6/39.3/44.3% — holds r27 gains, no full-pool conversion:
  gap 7%/5%/0% (2/51 decisive, both 0-0 racer trades). Raze wins
  regress to lone-racer trades (Walive mostly 0-3; best 11 open,
  7 cave1 — r27's armies gone). Deaths flat (~23% unique-ant,
  vs 17-20% r27 same-metric; no 90s relapse). g455/g456 knock
  (0.575/0.60 raw, Wilson just under bar).
- Round 19 verdict: POSITIVE — 2 promotions (g313 exploiter crown,
  g314), conversion 13% -> 24% -> 19%, double-elims 22% -> 7%,
  no pacification. DEATH -2 kept as new base. Caveat: death rate
  was already low — -2 redirects combat, doesn't reduce it.
  Exploiter +3 DEATH understood as combat subsidy (load-bearing);
  do not touch unless exploiters stop biting.
- Rounds 22-23 verdict: RETREAT. Full pool draws everything
  unfamiliar (1/240 decisive); drills cover but don't retain.
  Lesson: retention beats coverage. Next synthesis: rotating
  small windows.

## open (ordered — rethought every round boundary; a priority
list, not a schedule. Skip-the-queue rules in runs README.)

- Round 16: exact D4 symmetrization in forward(). Smallest
  architectural change with a guaranteed property (probe: 41%
  agreement, east bias). Weight-compatible, train=act coherent.
  Acceptance 100% by construction + promotion rate vs rounds 12-15.
- Round 17: KL anchor to supervised base (g000). Bounds 100+ gen
  drift; AlphaStar-fine-tune practice. Small (one loss term).
  Acceptance: promotions continue with less drift; falsified if it
  shackles adaptation (margins freeze).
- Round 18: wider receptive field + visibility channel (radius
  4 -> 5/6, visibility marking mine/teammate's/unseen). Needs model
  version branch (input shape changes). Acceptance: decisiveness up
  on scouting boards. Per-ant MEMORY stays parked (new architecture).
- Conditional: rung 3 = full real pool (148 maps). Needs 2-in-10 on
  current pool PLUS drill-reservation code first. Held-out evals
  return at 13+ same-rung boards. Graduation re-decided every round.
- Conditional: kill/death removal, pure-outcome ablations — only if
  dense stalls 40+ gens. Hill-approach — only if invaders stop
  biting.
- Watch items (symptoms first): three-role asymmetry (cycles in
  matrix), Nash-main selection (Wilson promotes collapsing
  specialists), remaining generator survey (pool has room to 12).

Each experiment ships with acceptance/falsification criteria in its
plan file before launch. See Discard bar below for what it takes
to drop one.

## done

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
