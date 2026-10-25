# Run notes

One file per training campaign. Every round gets a PLAN section
before launch (hypothesis, config, success criteria) and RESULTS
after (numbers, verdict, next step). Entries are append-only: never
rewrite a verdict, supersede it in the next round's file. The loop:
plan, run, record, reassess, repeat. Curriculum ladder and
 graduation rule live in tools/maps/curriculum/README.md.
The idea backlog lives in QUEUE.md (one idea per round).

## Fixed exam (every round runs the same shape)

- 15 gens, seed 456, turns 150, temp 2.0, entropy-beta 0.05.
- Train 4 games, eval 20 duels (greedy, rotated held maps).
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

## Index

- run-seed7.md — random init, full pool, 30 gens. The failure chain.
- run-probes.md — 60-turn probes: shaping, batch-norm, vf, continuity.
- run-bc.md — BC init + split critic, 30 gens. Critic moves, policy doesn't.
- run-rung1.md — tiny map breakthrough (rounds 4-5b). Environment was
  the missing piece; first promotions; rotation; undecayed outcome.
- run-nofood.md — FOOD removal ablation (rounds 6-7). Zero promotions;
  food exonerated as load-bearing.
- run-foodback.md — food restored + rung 1 v2 (round 8). Promotions resume.
- run-rung2.md — rung 2 pool graduation (round 9). IN PROGRESS.
