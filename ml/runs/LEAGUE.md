# LEAGUE.md — AlphaAnt continuous-league doctrine (steady state)

Replaces LOOP.md/rounds/promotion/exam/jury/graft/strike machinery (frozen as
record in ml/runs/). No throne, no generations-as-verdicts, no Nash solve.
Plan: ml/runs/plan-league.md. Migration: plan §Initialization.

## The 10 rules

1. **Roles + shares.** 1 main + 1 ME (`me`) + 2 LE (`le-a`, `le-b`).
   Deterministic round-robin main→me→le-a→le-b (equal shares by construction).
2. **PFSP only.** Opponent scores are Bayesian UCB (Beta posterior
   mean + 1 std; strangers explored first, bonus decays with games).
   Main: 50% squared-weighted UCB (seeks counters), else
   variance-weighted posterior mean (even = learning-rich). ME: always
   the current main (no fallback since 2026-11-02). LE: linear_capped UCB over
   all historicals (seeks any hole). Exploiters weight by own score
   (seek victims). No unseen default, no newcomer boost (both replaced
   2026-11-02: optimism where the objective is monotone, mean where it
   peaks at even).
3. **Cadence.** Micro-batch PPO every 8 own-games per learner; the main
   snapshots every 80 own-games (mainN). Exploiters enter the pool ONLY
   by admission (meN/le-aN/le-bN) -- no routine exploiter snapshots.
   Frozen members are never removed.
4. **No removal.** The pool only grows. Bloat is handled by weighting, not
   culling. Falsifier: top-20 members ≥80% of matches (else sampling broke).
5. **ME bar.** Sustained >60% over last 40 vs the current main → freeze copy
   (admitted), reset. Cheap errors by design.
6. **LE bar.** Sustained >60% over last 40 vs pool → freeze copy, reset.
7. **Reset = admission only (no stall rule).** An admission freezes the
   peak under a fresh family id and resets the slot to g000 weights +
   fresh Adam under the SAME bare id, so peak-inheritance can never
   happen. A drought simply keeps training under the same id with a
   rolling window -- no timeout, no reset (removed 2026-11-02: no
   AlphaStar counterpart). Every admission appends {slot, seat, game,
   tick} to league.json resets; the Elo pass cuts the slot's theta to
   seed at each reset (no peak leaks across).
8. **Anchors.** g000 (floor) + past main snapshots; 2 games each per
   main snapshot; NO training on anchor games. The anchor trend is the
   progress curve. (Fresh league 2026-11-01: history wiped, ladder
   rebuilds from main0 onward.)
9. **Ship rule.** Publish main weights on anchor new-high (water mark, not a
   throne: no training privilege attached).
10. **Kill.** Anchor flat 2 weeks + admission drought → revisit (time-boxed
    where AlphaStar would run forever).

## Invariants (never break these)

- One game trains exactly one learner; opponents are always frozen snapshots.
- Anchor games carry no gradient (measurement only).
- Identity = bare slot, achievement = family id. Live lineages are
  `main`/`me`/`le-a`/`le-b` forever; frozen achievements are `mainN`
  snapshots and `meN`/`le-aN`/`le-bN` admissions (0-based). Elo/PFSP
  records belong to these ids; replays, tables, and code all show the
  same names (display == attribution, no mapping anywhere).
  g-ids are ported history only -- no new member will ever be called one.
- Training core (rewards/algorithm/bot/engine) changes only with its own
  falsifier and full-suite green; league machinery never touches learning math.
