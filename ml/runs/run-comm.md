# Run: lagged intent channels (round 51+) — PLAN

User proposal: communication with ant-local state intact — new
channel(s) where an ant sees part of a friendly ant's internal
state, only where that friendly occupies a window cell.

- Hypothesis: visible intent (what my neighbors decided) buys
  coordination the hand-designed first-hill convention cannot:
  deconfliction (don't follow), follow-the-leader, massing.
  One-turn-stale intent is nearly as good as live (intents are
  sticky — marching north keeps marching north) at zero extra
  forward passes.
- Spec (code AFTER round 50 lands — bots run live code):
  - Bot keeps prev-intent map {dest-loc: 5-dim distribution}
    from last turn's masked logits at T=1.0 (temperature-free
    intent: what the net wants, not what the sampler does;
    canonical frame out of the D4-symmetrized forward).
    Keyed by dest (issued orders = 1-turn identity tracking);
    collisions average, spawns/dead absent = zeros, turn 0 zeros.
  - local_window gains 5 intent channels (7 -> 12): for each
    window cell occupied by a FRIENDLY ant present in the map,
    write its distribution; enemies/empty/unknown = zeros.
  - model conv1 7 -> 12 via zero-init pad (pad_in_channels
    precedent): behavior-identical at deploy, learns comm only
    if useful. Param-budget tests updated.
  - _rotate_item permutes intent channels by ROT_PERM per
    quarter-turn (same perm as actions); D4 forward applies the
    orientation's action perm to channels 7:12 on input
    (spatial transform covers all 12). Tests pin equivariance.
  - Training reads rec["window"] as-is (bot logs 12ch rows) —
    no replay/sidecar plumbing.
- Acceptance: ablation gap — zero intent channels at eval; a
  drop proves the policy reads them.
- Success criteria: ablation gap + any knocks/promos.
- Failure criteria: no ablation gap after a full round (policy
  ignores the channels) -> comm axis barren at this width;
  do NOT build learned messages/recurrence.
- Results: pending.
- Verdict: pending.

## Round 51 build (implemented, committed, smoke-verified)

- 12-channel windows (7 game + 5 intent), dest-keyed T=1.0
  wants, zero-init pad deploy, D4-coherent input orientation,
  AA_ZERO_INTENT ablation gate. 160 tests green. Live smoke:
  intent mass 0 at turn 0, flows thereafter.

## Round 51 results (g788-g802)

- Integration CLEAN (gen-1 12-wide rows verified, critic +
  optimizer migrated silently). 1 PROMO: g798 (exploiter)
  over g747 @ 0.625. Champ g747 -> g798.
- Breakthrough NOT retained (lakes/caves 0-1/2) — predates
  intent (rounds 48-50 already soft), not intent's damage.
- Ablation (g798 vs g720, 10 same-seed pairs): OPEN 4W/3D
  (+0.3) vs SHUT 6W/3D (+1.5). Gap -1.2: gateway reads
  NEGATIVE on the 15-gen test.
- Cheap measurements before deciding (lead analysis, not runner):
  actor intent weights 0 -> 0.040 (6% of game magnitude —
  moved, noise-phase); critic intent weights at 24% (the
  channels predict returns, or the critic overfits); intent
  occupancy DENSE (96% rows nonzero, mass ~3.7 — signal
  abundant, not sparse). Verdict: 15 gens caught mid-learning
  (weights off zero, not yet useful), NOT proven barren.
- Decision: ONE consolidation round (30 gens total exposure),
  then re-ablate with a HARD trigger: gap <= 0 after 30 gens
  -> axis barren, revert to 7ch, no third chance. Consolidation
  risks one automated round; a premature revert risks killing
  a slow-live axis the critic already prices.
