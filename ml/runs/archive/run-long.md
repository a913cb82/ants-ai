# Run: longer games (round 37) — PLAN

Diagnostic arbitration overrode the rung-3 pre-commit (documented
in run-teeth2.md): round-36 eval draws run the full 150 with armies
alive near hills — truncation, not breadth, is the prime suspect.
The retention objection to the pool jump stands unrebutted, so the
cheap, mechanism-backed test goes first.

- Hypothesis: 150 turns truncates big-board marches mid-stride;
  250 (pro median 229) lets them complete — HILL and OUTCOME fire,
  draws resolve, promotions resume.
- Config: --turns 250 (train AND eval — same horizon both sides;
  mixed horizons would exam what training never experiences).
  Everything else identical (8 boards, HA +0.5 first-hill, DEATH
  -2, kl 0.01, unanchored exploiters alternating). Expect slower
  gens (~1.5-2x); other cutoffs still end dead games early.
- Acceptance: decisive share up on big boards; game lengths spread
  past 150 (resolving, not stalling); promotions.
- Success criteria: >= 1 promotion OR big-board conversion up
  decisively vs rounds 34-36.
- Failure criteria: same draws at higher turn counts (games run
  250 and still 1-1 with armies parked) -> horizon is NOT the
  blocker; rung-3-with-formula next, for real (retention doubt
  and all — breadth becomes the only untested axis).
- Results: pending.
- Verdict: pending.
- Results (g578-g592): 0 PROMOTIONS. Drought 79 gens. Champ
  g513 holds. Draws piled at the new cap (111/136 @250);
  decisive curve untouched (median ~40, only ~9/block >150).
  Train conversion strong (most maps 50-100%); evals draw-or-
  worse vs the champ (margins negative almost everywhere).
  Gap ~10% (slight lift, still lowest).
- Verdict: HORIZON INNOCENT — longer games buy nothing (same
  draws, 1.3x cost). Cap back to 150. Mechanism reframe for the
  committed pool jump: breadth as OPTIMUM-ESCAPE, not curriculum.
  The champ is unbeatable on 8 learned boards (train 50-100%,
  evals draw-or-better); new boards are the only new information
  that can break the local optimum. Retention worry stands but
  exhaustion weighs heavier: nothing left to learn on 8.
