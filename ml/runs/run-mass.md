# Run: concentrate force (round 27) — PLAN

Round-26 forensics: lakes wins are SOLO hill-races (speed), while
funnels stay sterile. HA-as-min-nearest splits forces (each ant
closes its own nearest hill) — open ground rewards solos, funnels
kill them piecemeal. Military principle: concentrate force.

- Hypothesis: HA paying closing to the FIRST enemy hill only (a
  shared convention — same list for all ants) concentrates attacks
  into breakthroughs on funnels while keeping races viable (raze
  reward unchanged; racers just lose HA subsidy).
- Config: one-line change (min over foes -> foes[0]). Same 8-board
  pool, kl 0.01, everything else identical.
- Acceptance: funnel conversion rises (gap/caves/pond) with lakes
  intact; promotions.
- Success criteria: >= 1 promotion AND (funnel conversion up OR
  lakes sustained).
- Failure criteria: lakes collapses (solos broken and nothing
  replaces them) + 0 promotions -> revert to min-nearest; the
  split/concentrate axis is neutral, look elsewhere (coordination
  may need the visibility channel to mature, not reward surgery).
  SUICIDE-WATCH: cross-map marches die (-2 each) -> death spike.
- Results: pending.
- Verdict: pending.
