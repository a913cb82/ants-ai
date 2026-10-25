# Run: wide receptive field + visibility channel (round 18) — PLAN

Round 17 closed the loop on conversion: 97% mutual annihilation,
zero conversion on big maps, kl_anchor bounded but irrelevant.
The disease is post-battle navigation and unsupported engages —
exactly what beyond-own-LoS vision targets.

- Hypothesis: seeing what teammates see (union vision) plus knowing
  whether it is actionable now (own_sight flag) restores conversion:
  survivors find hills, engages get far-side support.
- Config: radius 4 -> 7 (15x15; corners d2=98 beyond sight 77),
  +own_sight channel (7 total). Beyond-circle cells fill entities
  from union lists, water stays unknown. Zero-pad migration: old
  6ch weights load bit-identically, lineage continues, training
  grows the new channel from zero. Same 8-board pool + kl 0.01.
- Acceptance: conversion (elim rate) up on big maps; promotions.
- Success criteria: >= 1 promotion; elim share rises on gap/caves.
- Failure criteria: 0 promotions + flat elim -> vision wasn't the
  blocker; revisit attack-conversion shaping (gated engage class).
- Results, retry (g293-g307): 15/15 clean, 0 PROMOTIONS. r1 at/
  above baseline (40-53% elim); other 7 maps still <=12% elim —
  disease intact. Mains 8/10 all-draw evals; only (losing)
  exploiters break draws. New channel no behavioral signature:
  sampled razes are hill-races/double-elims, never post-battle
  hill-finding with survivors. pg ~= 0 throughout.
- Verdict: NEGATIVE per criteria — vision wasn't the blocker.
  Fifteen gens with zero signature is enough: pg ~= 0 means no
  gradient pushes the new channel, more gens of nothing = nothing.
  Mechanism recheck: 97% death rate at net-0 means 1-for-1 trades
  are free — no incentive to preserve material, so no survivors,
  so no conversion. Fallback (round 19): break the indifference
  with asymmetric death (DEATH -2, KILL +1) — the cheapest reward
  knob left; if it fails, the next step is structural, not shaping.
