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
- Results: pending.
- Verdict: pending.
