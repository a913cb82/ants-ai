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
- Bold triggers: 2 quiet rounds -> try something different;
40 gens on a rung -> diagnose, don't advance blind.

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
