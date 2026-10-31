# LEAGUE.md — AlphaAnt continuous-league doctrine (steady state)

Replaces LOOP.md/rounds/promotion/exam/jury/graft/strike machinery (frozen as
record in ml/runs/). No throne, no generations-as-verdicts, no Nash solve.
Plan: ml/runs/plan-league.md. Migration: plan §Initialization.

## The 10 rules

1. **Roles + shares.** 1 main + 1 ME (`me`) + 2 LE (`le-a`, `le-b`).
   Deterministic round-robin main→me→le-a→le-b (equal shares by construction).
2. **PFSP only.** Main: 50% squared-weighted historicals (seeks counters),
   else variance-weighted; newcomer boost ×5 while <10 games. ME: locked onto
   current main while win-rate > 0.1, else variance-weighted easier
   historicals. LE: linear_capped over all historicals (seeks any hole).
   Exploiters weight by own win fraction (seek victims).
3. **Cadence.** Micro-batch PPO every 8 own-games per learner; snapshot every
   80 own-games. Snapshots are frozen pool members, never removed.
4. **No removal.** The pool only grows. Bloat is handled by weighting, not
   culling. Falsifier: top-20 members ≥80% of matches (else sampling broke).
5. **ME bar.** Sustained >60% over last 40 vs the current main → freeze copy
   (admitted), reset. Cheap errors by design.
6. **LE bar.** Sustained >60% over last 40 vs pool → freeze copy, reset.
7. **Reset = g000.** Weights + fresh Adam + FRESH incarnation id (never reuse:
   a fresh incarnation rated at its predecessor's peak is unearned).
   Stall: 400 own-games with no admission → reset.
8. **Anchors.** g000 + 5 spread frozen mains (g401/g588/g978/g1343/g1532);
   2 games each per main snapshot; NO training on anchor games. The anchor
   trend is the progress curve.
9. **Ship rule.** Publish main weights on anchor new-high (water mark, not a
   throne: no training privilege attached).
10. **Kill.** Anchor flat 2 weeks + admission drought → revisit (time-boxed
    where AlphaStar would run forever).

## Invariants (never break these)

- One game trains exactly one learner; opponents are always frozen snapshots.
- Anchor games carry no gradient (measurement only).
- Identity = incarnation: Elo/PFSP records belong to member ids, never slots.
  A reset mints a new id; the old line flatlines truthfully.
- Training core (rewards/algorithm/bot/engine) changes only with its own
  falsifier and full-suite green; league machinery never touches learning math.
