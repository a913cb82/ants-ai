# Idea queue

Statuses: open (live backlog), trying (this round's idea — one only),
done (kept, with the round that proved it), dropped (tested, failed,
with reason), parked (doctrine says not now).

Doctrine (autoresearch-inspired): one idea per round, a fixed exam
(15 gens, train 60 games / 30 opponents since round 71, eval 20,
Wilson bar > 0.5, borderline repeats),
a written plan with falsification criteria before launch, results
appended after. Rounds stay sequential (single champion lineage).
Pool entry/exit runs on the promotion/demotion rules in
tools/maps/curriculum/README.md.

## trying

- Round 93 done: revert CLEAN (no whiplash, ≈r91 baseline).
  Recount verdict: NEITHER line slice-knocked (main best
  slice .417 g1448; rival best .458 g1441) nor total-knocked
  (both best .475) — jury-split teeth only (g1451 2-0 vs
  rivals; rivals .50-.688 vs jurors). NO strike count
  (needs main-knockless + rival-KNOCK; rival didn't knock
  in any countable unit). NO tripwire (contact everywhere
  except the champ's slice). ALIVE-quiet. 0 promos (10th
  straight). Champ g1287 tenure 162 — watched, no gate.
- Round 94 done: NO-SIGNAL-YET (first half). Best .50
  one-off, no sustained ≥.40. Tenure 177, 11th straight
  quiet. Tool gaps flagged (no kill counters, no slice
  fields — standardize slice source for r95 verdict).
- Round 95 done: ACQUITTED (slice never ≥.40 sustained,
  decisiveness +.034). Channels stay; HANDS next.
- Hands BUILT+MERGED (smoke: blocked 0.093, 9x threshold).
  Round 96 done: TRIPWIRE (no total-knock either line),
  ANSWERED by swaps (r87 precedent). Smoke stands
  uncontradicted. Swaps builder dispatched (wild-rate
  grounding first). Round 97 = mechanics.
- Swaps BUILT+MERGED (wild 0.379 blocked, fix →0.049,
  cycles 20.5%). Round 97 done: HANDS-CONFIRMED
  (decisive .773, rival knock .525 held). Round 98 done:
  STILL-CONFIRMED (decisive .737, slices flat, rival
  slice .500 borderline ⇒ STRIKE-ONE, ladder spent).
  OVERRIDE: water-stuck outranks coordination retry.
  LOS-F1 builder dispatched; round 99 = ghost-fill fix.
- LOS F1 BUILT+MERGED (probe 1.0→0.0, D4 proven).
  Round 99 done: GHOST-KILLED (lake gap closed .439
  vs .429, decisive .78; main flat, rivals knock x4).
  Stall-memory builder dispatched; round 100 = MEMORY.
- Stall-memory BUILT+MERGED (ch9 rate 0.050 on smoke,
  9ch-compat byte-identical). Round 100 done:
  MEMORY-ACQUITTED (dwell 4.81% in band, uniform;
  main knock g1554 one-off). Shaping builder dispatched;
  round 101 = STAY-VS-WATER TAX (Goodhart-guarded).
- Shaping BUILT+MERGED (-0.05 same-turn, main-only,
  enemy-near exempt; 12 tests green) + lead plumbing
  (--water-stall-tax, default off). Round 101 = TAX LIVE
  (dwell drops AND capture holds → works; dwell drops +
  wins drop → GOODHART revert; dwell flat → axis closes).
- Round 101 done: SHAPING-ACQUITTED (dwell +0.14pp
  noise, trapped flat). AXIS CLOSED. Tax OFF r102
  (acquittal test: climb continues → tax inert;
  collapse → tax mattered unseen). Dwell probe in repo.
- Round 102 done: JURY-PROMO g1585 (.675, jury-carried,
  SOFT) + TAX-INERT (climb held, acquittal validated).
  Champ g1585 tenure 0. Round 103 = vs new champ:
  does the throne harden or correct?
- Round 103 done: DOUBLE CROWN g1593 (.700) → g1596
  (.650), both complete (slice .625 + jury). Jury
  EXONERATED (soft throne self-corrected in one round).
  Champ g1596. Round 104 = harden or 4th turnover?
- Round 104 done: HARDENED (g1596 holds 15, tenure 14;
  main 3 slice-knocks held). Round 105 = crown watch
  on main line, same vs g1596.
- Round 105 done: TURNOVER — main g1629 crowns .725
  (first main crown since g913). 4 crowns/4 rounds:
  no stable throne. Champ g1629. Round 106 = does
  a main champ harden?
- Round 106 done: MAIN-HARDENS (g1629 holds 15;
  surge mid-round all held, fade late). Round 107 =
  surge or fade, same vs g1629.

## open (ordered — rethought every round boundary; a priority
list, not a schedule. Skip-the-queue rules in runs README.)

- Water-stuck axis (observed: ants idle at shores). Diver
  reports in, fixes STAGED behind hands axis (no activation
  until solution ideas + round-98 verdict):
  (a) LOS-LEAK (losleak done): ghost runs BACKWARD — unseen
  never invents enemies; teammate-seen marks in 12 B-tier
  corners look exactly like own-visible except ch6=0, a flag
  the net can't use (all 5 dest cells always ch6=1; base
  5x5 RF smears corners). B-tier water misreads as LAND
  (ch0≡0). Enemy-ON-cell reads fr=0 (safe!) + edist=0
  (here!) — maximal attack-me, no danger flag. Matches
  lakes 2x skew. Fixes ranked: F1 zero-fill B-tier entities
  (gate L226-235 on in_circle; falsifier: corner probe 0 +
  lake ghost == open); F2 fog-consistent fill (B water=0.5;
  falsifier: dead-end stay-rate rises); F3 true per-ant
  visibility (biggest shift/retrain; falsifier: ch6 varies
  across dest cells). Activate earliest round 99,
  one variable.
  (d) STUCK-RATE (stuckmine done, archived replay
  positions g1500/g1523): near-water stuck 4-5% (N=10)
  vs 0.0% open — stuck is EXCLUSIVE to shoreline.
  N=25 persists (2-4%). Trapped 74-91% (concave
  pockets), turtle minority (hill-adjacent subset).
  Starvation INVERTED: earliest-spawned stick most
  (Q1 .042 > Q4 .021) — no late-list gradient.
  Starter policy: 0 stuck in 6463 windows — stillness
  is LEARNED (or learned-era), not engine artifact.
  Analyzer at /tmp/stuck.py (re-runnable on new gens).
  (b) NO-PLANNING (planahead done): confirmed pure
  function of current window (model.py:47-48, :81/136;
  AlphaAnt.py:193-194; only cross-turn state is turn
  counter + water cache). Ranked: 1st stall-memory (1-bit
  same-cell/blocked hysteresis channel, ~0 params, D4-safe
  scalar; falsifier: dwell shifts left + water-map wins
  hold); 2nd anti-stall shaping (stay-vs-water tax;
  falsifier: dwell drops AND capture flat — else Goodhart
  per tiebreak precedent); LAST intent-channel retry
  (falsified r51-52, needs positive-signal axis first).

- Standing: map-mechanic axis MIXED (round-70 audition,
  archive/run-gated.md: q 100% decisive, r 30% weak-over-bar,
  s 0% sterile — all three members by legislation, rates banked).
  q/r/s OUT for round 81 as ordered; generator-survey follow-up
  gated on the round-81 shape. k/l sterile (archive/run-big.md),
  m/n parked without a new mechanism, o/p scrapped for tool-built.
- Conditional: rung 3 = full real pool (148 maps). Needs 2-in-10 on
  current pool. NO held-out splits at any size (standing rule):
  every rung board trains and evals every gen — per-gen coverage
  arrives with the volume round (landed round 71); rotation covers
  at round level on smaller pools. Graduation re-decided every round.
- Conditional: kill/death removal, pure-outcome ablations —
  idea 6 (last resort). Idea 1 (outcome-gated shaping) tried
  round 69: FLAT, no starvation (archive/run-gated.md) — gating
  alone doesn't break the Nash. Pure-outcome stays behind it.
  Note: mirrors make wins luck-heavy, so this one risks
  noise — hence last.
- Idea 5 (queued): combat-proportional draw tiebreak. The
  dropped tiebreak paid survival (perverse); this variant
  prices FIGHTING in draws (kill-scaled), which is the exact
  missing incentive in a turtle field. Applies to TRAINING
  returns first (exam integrity: promotion still reads W/D;
  revisit only if training works). Plan needed before launch.
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
plan file before launch. See the Discard bar in README.md for what
it takes to drop one.

## done

- Grafted climb (rounds 73-79, campaign.md): graft #2 takes —
  drought ends round 74 (g1162, divergence-then-win, not
  honeymoon); penalty OFF from round 74; ceiling breaks round 77
  (g1202, first .65+ since the graft); fastest rotation round 78
  (3 crowns in 15 gens); strike-one round 79 with the graft-#3
  menu pre-committed (main-life 6→5→≤4 = role change, never #4).
- Volume era (round 71, campaign.md): train 4 -> 30 opponents
  (60 games) + workers 8 -> 12 on the frozen 12-board pool.
  Landed clean (all 12 covered, pg healthy, ~63 min/round).
  Necessity testable later by dialing down.
- Rival era closed (rounds 42-68, archive/run-rival.md): 8 crowns
  all rival-line; gatekeeper reframe round 46 (main gates ~.45,
  rival climbs); graft #1 vindicated round 56
  (divergence-then-win, mains crown again by round 58); BANK
  round 68 with the turtle finding (attacking first loses, so
  mirrors turtle — the equilibrium is the result, not the failure).
- Rounds 17-50 (condensed; detail in archive/run-*.md): D4
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
- Rounds 13-16 (archive/run-exploiters.md,
  archive/run-lineage.md, archive/run-accumulate.md,
  archive/run-symmetrize.md): exploiters with teeth (BC base + kill-heavy) +
  continuous main lineage + D4 symmetrization. 7 promotions in 60
  gens (g208, g212, g236, g245, g253 + 2 exploiter crowns g222,
  g246); chains depth 34; symmetrization kept as hygiene (100%
  agreement, free). Score-peace overturned: funnel draws hide
  bloodbaths (44 deaths) — conversion problem, not pacifism.
  Demotion bar now contact-based. All live as infrastructure.

- Rung-2 extended pool (rounds 11-12; archive/run-tiebreak.md,
  archive/run-rung2back.md): rung 1 + rung2a-d, then
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

- Lagged intent channels (rounds 51-52, archive/run-comm.md):
  no ablation gap after 30 gens (gap -1.2, intent ratio flat
  6.1% vs 6.0%) → BARREN by hard trigger. Reverted to 7ch
  (truncation shim keeps 12ch weights loading). Reopen if:
  a positive intent signal on some other axis first — never
  on this width alone.
- Draw-penalty games (rounds 71-73, campaign.md): valid control
  twice, penalty flat (.277 vs .272, then .24 vs .23) → idea 3
  CLOSED (turtling is not a choice). OFF from round 74.
  Reopen if: a new mechanism makes attack cheap first.
- Spoiler line (rounds 71-72, campaign.md): naive+sparse+
  persistent flatlines (0 train wins, .30 → .075 negative
  slope) → idea 4 CLOSED and folded. Reopen if: capacity
  acquitted AND the field shown attackable.
- Second rival line B (rounds 65-68, archive/run-rival.md):
  exam FAIL (0 train wins in 16, best eval .25) → folded to
  single line A. Reopen if: single line converges AND a fresh
  predator design (not naive+kill).
- Outcome-gated shaping (round 69, archive/run-gated.md): FLAT
  (HA-on-loss → 0 mechanical, learning continues) → closed as
  a breaker; superseded by the penalty trial. Reopen if:
  knockless x3 under a live regime (softer halve-not-zero gate).
- Big-board k/l passengers (round 64, archive/run-big.md):
  0/10 draws each → sterile; scale innocent at 48px. m/n parked
  (predicted sterile, no trial without a new mechanism).
- Material tiebreak (round 11, archive/run-tiebreak.md):
  mechanism worked (draws separated
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
- Draw-as-loss (global): stays dropped — idea 3 (selective
  draw-penalty games) failed clean too (rounds 71-73, campaign.md),
  so ancestor and child are both closed. Combat-proportional
  variant (idea 5, open) is the live heir.
- 60-turn evals: truncate before skill gaps compound. Dropped for
  eval-turns 150.
- Pure-outcome ablation: still last resort (mirrors make wins
  luck-heavy). Never run; stays dropped unless dense stalls 40+.

## parked

- Comm follow-ups (archive/run-comm.md): pheromone map,
  learned messages, recurrent hidden state — parked behind
  a positive intent signal that never came. Frame stacking
  passed over (intent subsumes its cues where it matters).
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
