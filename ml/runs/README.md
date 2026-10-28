# Run notes

One file per training campaign. Every round gets a PLAN section
before launch (hypothesis, config, success criteria) and RESULTS
after (numbers, verdict, next step). The loop: plan, run, record,
reassess, repeat. Curriculum ladder and graduation rule live in
tools/maps/curriculum/README.md. The idea backlog lives in QUEUE.md.

## Ownership (one fact lives in exactly one place — others link)

| File | Owner | Role |
|---|---|---|
| README.md (this file) | program lead | doctrine + index of everything |
| QUEUE.md | coordinator | what's next: trying / open / done / dropped / parked |
| plan-next.md | program lead | staged roadmap (Stage 0/1/2) + bars |
| review-fleet.md | review fleet | FROZEN 2026-10-28 synthesis — read-only |
| campaign.md | runner | ACTIVE log (rounds 71+): volume era, grafts, strikes |
| LOOP.md | program lead | pause/resume bookmark: state + exact round command |
| archive/run-*.md | history | CLOSED topics, verbatim — verdict lines below, detail inside |

Rules: a closed idea gets one verdict line in QUEUE plus its file
moved to archive/ — never rewritten, never deleted. Round-by-round
chatter consolidates to verdict lines; the archive keeps the
receipts. New rounds append to campaign.md only. Splitting,
renaming, or reviving an archived topic needs a QUEUE entry first.

## Fixed exam (every round runs the same shape)

- 15 gens, seed 456, turns 150, temp 2.0, entropy-beta 0.05.
- Train 60 games (30 opponents, round 71+; was 4 games before the
  volume round), eval 20 duels (greedy, rotated held maps).
- Promotion bar (noise floor): Wilson lower bound > 0.5, draws
  half, head-to-head vs champion only. Borderline evals (0.48-0.55)
  earn one repeat before verdict.
## Discard bar (be sure before dropping)

An idea moves to dropped only when ALL hold:
1. A full round ran under clean conditions (no mid-round pool or
   reward edits; confounds named in the plan or absent).
2. The effect is decisive OR a repeat confirmed it: decisive means
   the headline metric moved the wrong way with margin (e.g. peace
   +0.07 with 0 promotions, not noise around the bar). Borderline
   results earn a repeat, not a verdict.
3. The mechanism is named, not just the numbers (WHY it failed).
4. Reopen conditions are written down (what evidence would revive it).

Every dropped entry carries: round, numbers, mechanism, confounds
considered, reopen conditions. Audit the list against this bar
whenever a round ends.

- Bold triggers: 2 quiet rounds -> try something different;
  40 gens on a rung -> diagnose, don't advance blind.

## Exam integrity (evals never train)

Eval games are judgment, not data — their records are discarded by
design. Training on them would (a) break the on-policy math (greedy
argmax actions aren't samples; reinforcing them collapses entropy
into imitate-the-argmax), (b) teach to the test (overfit the
promotion metric until it stops measuring), (c) narrow the
distribution (champ-only mirrors vs PFSP diversity). AlphaStar
likewise never trains on its measurement games. Want more training
data? Play more train games (costs wall time), never reuse evals.

## Reference design (AlphaStar is the baseline)

League: one main training continuously (never resets), periodic
exploiters resetting to the supervised base on promotion,
PFSP-lite opponent sampling, Nash recorded. Deviations from this
shape (thresholds, caps, extra roles, per-role rewards) need a
written justification and a path back. Simplicity first: remove
machinery before adding it.

## Template

- Hypothesis: what this round tests, in one sentence.
- Config: archive lineage, turns, maps, temperature, entropy, reward
  code state, new flags vs last round.
- Success criteria: what numbers would confirm the hypothesis
  (e.g. peace index up, first promotion, actor displacement > 0.02).
- Results: per-block numbers, promotions, wall time.
- Verdict: confirmed / rejected / inconclusive, in one sentence.
- Next: the single next step the verdict implies.

## Index — living

- QUEUE.md — backlog and verdict lines for every closed idea.
- LOOP.md — pause/resume bookmark + exact round command.
- plan-next.md — Stage-0 impl batch + Stage-1/2 mechanisms + bars.
- review-fleet.md — 8-lens synthesis; verification table + ranked work.
- campaign.md — rounds 71+: volume lands, penalty fails twice,
  spoiler flatlines, graft #2 takes (drought ends round 74),
  ceiling breaks round 77, strike-one round 79, graft-#3 gate
  round 80 (ACTIVE).

## Index — archive (closed; one verdict line each, detail inside)

- archive/run-seed7.md — 30 gens random-init, 0 promos: random
  walks don't accumulate; motivated the probes.
- archive/run-probes.md — 60-turn probes: no single mechanism
  unsticks learning; shipped APPROACH, batching, persistent critic.
- archive/run-bc.md — BC init + split critic: critic moves, policy
  frozen (actor 0.006); evals must outrun training.
- archive/run-rung1.md — tiny-map breakthrough (rounds 4-5b):
  environment was the blocker; first promotions, rotation,
  undecayed outcome.
- archive/run-nofood.md — FOOD ablation (rounds 6-7): 0/30 without;
  food exonerated as load-bearing.
- archive/run-foodback.md — food restored (round 8): 3/15, graduate.
- archive/run-rung2.md — rung-2 graduation (round 9): 3/15, transfer
  confirmed; found the per-map-logging gap.
- archive/run-rung3.md — random-walk rung 3 REJECTED: zero-decisive
  at 150 turns; forgetting confirmed (held rung-1 peace 0.7);
  eval-on-train restored, no splits under 13 maps.
- archive/run-tiebreak.md — material tiebreak (round 11): mechanism
  worked, incentive perverse (pays survival); reverted.
- archive/run-rung2back.md — retreat (round 12): stall deeper than
  incentives; exploiters-with-teeth next.
- archive/run-exploiters.md — teeth (round 13): invasion crosses the
  valley (2 promos); funnels load-bearing, opens suspect.
- archive/run-lineage.md — continuous main (round 14): chains work,
  no rot; first exploiter crown g222.
- archive/run-accumulate.md — accumulation sample (round 15):
  CONFIRMED (3 promos, chains to 34).
- archive/run-symmetrize.md — D4 (round 16): hygiene kept (100%
  agreement, free); score-peace overturned (bloodbaths, not
  pacifism); demotion bar goes contact-based.
- archive/run-klanchor.md — KL anchor 0.01 (round 17): bounded drift;
  proved irrelevant round 45, now 0.0.
- archive/run-wide.md — 15x15 + own-sight (round 18): NEGATIVE, no
  signature; next is asymmetric death.
- archive/run-pain.md — DEATH -2 (round 19): 2 promos, conversion up;
  kept as the new base.
- archive/run-replicate.md — replication (round 20): 0 promos, no
  harm; keep -2, build apparatus instead of re-replicating.
- archive/run-drills.md — drill reservation + pg_abs (round 21):
  apparatus for the breadth test.
- archive/run-rung3full.md — full pool (round 22): 0.8% decisive;
  drills cover but don't retain; conjunctive bar holds one round.
- archive/run-sweep.md — sweep finished (round 23): 0/120; RETREAT;
  retention beats coverage (rotating small windows, never one pool).
- archive/run-retreat.md — known-8 (round 24): conversion not
  restored; disease is horizon, not learning.
- archive/run-hill.md — hill-approach +0.5 (round 25): HORIZON FIX,
  keep; lakes wins are solo races → first-hill convention next.
- archive/run-mass.md — first-hill HA (round 27): CONCENTRATION
  WORKS (2 promos, deaths halved); gap reframed as defense school.
- archive/run-plateau.md — plateau watch (rounds 29-34): pace ~1/15;
  n=20 needs ~65% effective (bar stands); trigger → teeth diversity.
- archive/run-teeth2.md — origin diversity (rounds 35-36): clones
  crushed even unanchored; teeth exhausted; horizon arbitration next.
- archive/run-long.md — turns 250 (round 37): HORIZON INNOCENT;
  cap back to 150; breadth as optimum-escape, not curriculum.
- archive/run-near.md — frontier training (rounds 39-41): MISMATCH
  FIXED, 94-gen drought ends g611; champ-slot bug → guaranteed slot.
- archive/run-rival.md — persistent rival (rounds 42-68): styles need
  time (8 crowns, all rival-line); gatekeeper reframe (round 46);
  anchor relief 0.0 (round 45); graft #1 vindicated (round 56);
  line-B exam FAILS, folded; BANK (round 68) with the turtle
  finding: attacking first loses, so mirrors turtle — equilibrium,
  not failure.
- archive/run-ledger.md — ledger rebalance (round 46): mechanism
  WRONG for the main (0/10 knocks); regime climbed 3/15 anyway.
- archive/run-big.md — big-board passengers (round 64): k/l sterile
  (0/10 draws each); scale innocent; m/n parked without a mechanism.
- archive/run-comm.md — lagged intent (rounds 51-52): BARREN by hard
  trigger (gap -1.2, intent ratio flat); reverted to 7ch; bigger
  comm stays parked behind a signal that never came.
- archive/run-gated.md — outcome-gated shaping (round 69): FLAT, no
  starvation; q/r/s audition MIXED (q 100%, r 30%, s 0% — members
  by legislation, rates banked).
