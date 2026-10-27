# Run: DEATH -2 replication (round 20) — PLAN

Round 19 resumed promotions after a 45-gen drought, but one round
is a fluke until it replicates. No new variable by design.

- Hypothesis: asymmetric death is a regime change, not luck —
  promotions continue, conversion holds, double-elims stay low.
- Config: identical to round 19 (DEATH -2, kl 0.01, 8 boards).
- Success criteria: >= 1 promotion; conversion >= 15%; no
  pacification on r1.
- Failure criteria: 0 promotions + conversion back under 12% ->
  round 19 was luck; revert DEATH to -1 and go structural (rung 3).
- Results (g323-g337): 0 PROMOTIONS. Champ g314 holds. Mains
  10/15 all-draw evals; exploiters lose but force decisive games.
  Decisive rate 13% -> 15% -> 20% (r1 28% -> 47%, opens drive it;
  caves ~0-6%). No pacification, no collapse.
- Verdict: neither bar fired (success needed >=1 promo; failure
  needed conversion <12%). Round 19 looks lucky in hindsight
  (2/30 overall), but -2 shows no harm and weak help — keep it as
  base, do NOT revert on one dry round (as superstitious as keeping
  it on one lucky round). No more pure replication: the next round
  builds rung-3 apparatus (drill reservation + pg logging) on the
  same config — data keeps accumulating while the prerequisite
  gets built.
