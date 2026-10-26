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
- Results (g428-g442): TWO PROMOTIONS — g438 over g422 and
  g441 over g438 (both 0.625). Champ g422 -> g441. Conversion
  12% -> 16% -> 35% across blocks: lakes 62%, pond 21%, cave1
  27%, open2 69%, rung1 75%. Death rate HALVED (~45% vs 93-97%).
  First mass razes (23/8/4 ants alive at raze — armies, not lone
  racers). Gap still 0% — the last sterile board.
- Verdict: CONCENTRATION WORKS, decisively. Shared convention ->
  massed attacks -> clean breakthroughs (fewer deaths because
  attackers win instead of dying piecemeal). Keep first-hill HA.
  Round 28 consolidates (same config, momentum round): gap-watch
  is the question — if gap falls, all 8 boards convert.
- Results (g443-g457): ZERO PROMOTIONS, champ g441 holds.
  Conversion 38.6% -> 39.3% -> 44.3% (n=140/block): open1
  78/65/82%, open2 76/71/83%, lakes 65/61/78%, pond 38/61/28%,
  caves 21-25/18-31/28-29%, mapgen1 0/6/24%. GAP 7%/5%/0%
  (2/51, both 0-0 mutual-death racer trades) — STILL STERILE.
  Raze wins are racer trades again (Walive 0-3 typical; best 11
  in g446-open, 7 in g453-cave1). Deaths flat: 24.2/24.2/22.6%
  unique-ant (r27 same-metric 17/19/20%) — no relapse, no gain.
  Train mret 2.52/1.72/1.83, pg 0.555/0.443/0.514, kl 0.68/0.49/
  0.61; v_loss falls within-gen every gen (critic learning).
  Eval per block: 11W-68D, 11W-66D, 20W-56D (mm -0.30/-0.36/
  -0.12); g455 (6W) and g456 (7W) knock, Wilson lower 0.49-0.50
  just under the bar. Exploiters (g445/g448/g451/g454/g457)
  all fail as designed (0-3W).
- Verdict: CONSOLIDATION HOLDS BUT GAP IS STRUCTURAL. Same
  config keeps r27's gains (conversion ~40%, deaths flat,
  near-miss challengers) but converts nothing new and loses
  the mass-breakthrough character. Gap sterile 30 gens running:
  no more pool-wide rounds — gap-specific forensics next.
