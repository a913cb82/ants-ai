# Run: persistent rival (round 42) — PLAN

Tripwire fired (round 41 knockless dry). Pre-committed variable.
The program eats disruption and returns to draws; disposable
exploiters never develop past target practice. Counter-styles
need time — so stop reseeding and let one rival develop.

- Hypothesis: a chaining rival (own weights + optimizer,
  kill-scales, unanchored) develops a genuinely different style
  over several gens; the main training against it (recent-window
  inclusion is automatic) learns to beat styles, not just the
  champ's mirror — and that transfers to champ-beating.
- Config: exploiter gens continue last exploiter (parent chain +
  banked opt); first seeds from the founding/champ alternation,
  then the chain owns it. Same 8 boards, formula, anchor rules.
  Manual watch (not code): if the rival never exceeds 2W over a
  full round, reseed (degeneration rule for round 43).
- Acceptance: rival wins decisively (>= 5W) at least twice;
  promotions resume.
- Success criteria: >= 1 promotion OR rival >= 5W twice.
- Failure criteria: rival crushed every gen (0-2W, degenerate
  noise) AND 0 promos -> the main beats everything we can field;
  next is capacity (bigger net) or acceptance (bank the plateau).
- Results (g653-g667): TWO PROMOTIONS — g655 over g611 (0.65,
  main) and g666 over g655 (0.625, RIVAL crown — 5th kamikaze
  crown but first EARNED through development). Drought over at
  41 gens. Champ g611 -> g655 -> g666. Rival trajectory: 8W,
  7W, 8W, 10W, 8W — never ≤2W, positive margins throughout,
  decisive style (4-9 draws vs mains' 7-13). Chain verified:
  last exploiter g666, parent links intact, opt banked.
- Verdict: RIVAL DEVELOPS. Persistence is the missing ingredient
  — counter-styles need time, exactly as hypothesized. The
  program's meta-pattern (disruption eaten, draws return) breaks
  when the disruption keeps developing. Consolidate (round 43
  same): the rival chain continues vs the new champ.
- Results (g668-g682): TWO MORE PROMOTIONS — g669 over g666
  (0.675) and g681 over g669 (0.625), both rival-line. Champ
  g666 -> g669 -> g681. Rival keeps developing (exploiter->
  exploiter parent g678->g681 confirmed); worst rival gen still
  3W+11D, no re-absorption. Main knocks continue (g671 .575).
- Verdict: REGIME HEALTHY, climb pace 4/30. Keep riding same
  config (round 44). Watch: main hasn't taken a rival-held
  crown yet (last three crowns all rival-line) — if the main
  becomes a permanent sparring partner, the podium is just the
  rival lineage and pressure is one-directional again.
- Results (g743-g757): ALIVE — 1 PROMO (g747 exploiter .800,
  14W/4D, most decisive crown of the rival era) + 4 rival
  knocks (g744/g750/g753/g756). Champ g720 -> g747. Main
  wobbles (.20-.425, no collapse, no knocks in 10). Doctrine
  vindicated: the dry round bought the dominant crown.
- Results (g758-g772): 0 PROMOTIONS. Champ g747 DEFENDS the
  dominant crown (concedes two rival knocks g765 .600 / g768
  .575, no challenger above .325). Main gate HOLDS (.20-.45
  band, min W=1 once, no repeated 0-1W). Rival wave
  rises-then-fades (.400 -> .450 -> .600 -> .575 -> .475).
  Correction for the record: exploiters are NOT role-locked
  (7 of 8 crowns this era are exploiter-line) — g765/g768 just
  fell short of Wilson, the bar working as designed.
- Verdict: ALIVE, continue same (round 50). Era pace: 8 crowns
  in ~120 gens (~1/15) — back to the historical baseline pace,
  now via the rival line.
- Verdict: ALIVE, continue same (round 49). Rival owns the
  podium (7 crowns); main owns the gate (.20-.45). Staleness
  watch noted, no action — the main provides frontier variety
  + benchmark, and staleness isn't a tripwire.
- Results (g773-g787): 0 PROMOTIONS. Champ g747 HOLDS (second
  defense, 15/15 — entrenched AND tested, pushed to .475 four
  times but never breached). 6 knocks (4 at .475, one draw
  short, both lines). Main gate HOLDS (.20-.475, never 0-1W).
  Rival pressure persistent (.450 -> .475 x3 -> .400 -> .475).
- Verdict (round 50): ALIVE (knocks, no tripwire). NOT
  knockless -> the queued plan fired: round 51 lagged intent
  channels (run-comm.md), reverted round 53 (barren).
- Results (g728-g742): 0 PROMOTIONS. Champ g720 holds. Two
  rival knocks (g732 .60, g735 .575 — correctly unpromoted:
  Wilson lower, not raw eff, is the bar; no anomaly). Main
  gatekeeper soft (mean .29, best .475, worst .175 — below the
  .40-.50 band, wobbling not collapsed). Drift measured: 21
  entries over ids, STABLE (constant offset, not a leak —
  hygiene deprioritized).
- Verdict: DRY-BUT-ALIVE (knocks exist). Dry-after-promo is the
  era's norm (r42:2, r43:2, r44:0, r45:0, r46:3, r47:0) —
  quitting after one dry round would have missed r46's three
  crowns. Continue same (round 48). Tripwire trips ONLY on a
  knockless round (nothing >= .50 either line). Watch: main
  softness (collapse = repeated 0-1W, not met) + rival fade
  (g738 .325 — noise or peak?).
- Results (g683-g697): 0 PROMOTIONS. Champ g681 holds. Main
  best .45 (zero knocks, margins all negative); rival knocks
  twice (g687 .60, g690 .55) then fades (.475, .40 — peaked
  mid-round). Per-map: turtle maps sterile, decisive maps split.
- Verdict: MAIN STALLED (one round after knocks — mechanism is
  structural, not form): the main pays KL 0.8-2.3 toward BC
  (g000, 200+ gens stale) while fighting a g681-era rival. The
  anchor no longer binds (drift happened anyway) and now only
  drags — toward obsolescence. Exploiters prove freedom works
  (unanchored, thriving). Round 45: anchor relief
  (--kl-anchor-beta 0.0, flag flip, no code). Success = main
  knocks return; failure (collapse/flat + rival fades) =
  structural -> re-root or bank.
