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
- Results (g818-g832): 0 PROMOTIONS. Champ g798 holds. Revert
  CLEAN (gen-1 7-wide confirmed, zero crashes, truncation
  exact). Critic wobble as predicted (one-gen re-fit bump
  v~.9, then range-bound, fitting every gen — no break).
  2 knocks (g822 .575, g827 .525). Lakes flickers (g827/g829
  sweeps — best lakes signal yet); no map 0/15. Late fade
  g832 (1W4D) bears watching.
- Verdict: ALIVE, continue same (round 54).
- Results (g833-g847): 0 PROMOTIONS. Champ g798 holds. 3
  knocks, all exploiter (g834 .53, g840 .55, g846 .60 — rising).
  Main knockless (best g839 .47); main bests declining three
  rounds (.60 -> .525 -> .47). Lakes flickers died (noise
  confirmed). No 1W collapses (min 3W — fades isolated).
- Verdict: ALIVE by the standing rule (either-line knocks =
  alive; the main-only tripwire is goalpost-moving — declined).
  But the trend is real, so a NEW rule, pre-committed before
  data: main-knockless x2 consecutive WITH rival knocks
  continuing = main-side intervention live (menu: re-root best
  recent main, or bank rival pedigree into the main slot).
  Round 54 is strike one.
- Results (g848-g862): 1 PROMO (g849 exploiter .625 over g798).
  Champ g798 -> g849. STRIKE TWO: main knockless again (best
  .45 x2, all-negative margins); rival 5/5 knocks (.60/.525/
  .575/.525 + crown). Pre-commit FIRES.
- Intervention (round 56): graft rival tip into the main slot
  (set_main g862 -> g861, weights + banked opt, one-liner,
  old tip revertible in-archive). Why the tip, not the best
  (g852 .60): the chain is cumulative, tip = most developed.
  Why not best-main (.45): recycles a loser (all-negative
  margins, .45 ceiling). Risk named: sibling-mirror draws
  (same stock, round-46 objection) — round 56 watches honeymoon
  draws vs divergence-then-win.
- Results (g863-g877): DIVERGENCE-THEN-WIN. 2 takes (g867 +
  g873, both .62). Champ g849 -> g867 -> g873. Linkage clean
  (g863<-g861, chain continues). Main knocks 4x (.53/.50/
  .53/.57) — grafted stock competitive vs .45 ceiling before.
  NOT honeymoon draws (7 knocks, decisive games throughout).
  NOT collapse (no 0-1W). Strike rule EXPIRED.
- Verdict: graft takes, continue grafted line (round 57).
  Note: takes still arrive via exploiter role; challenger
  knocks Wilson-block (correctly — .50-.57 raw isn't .65).
  The bar holds; the climb climbs.
- Results (g878-g892): 3 PROMOTIONS — g884 (main .775, 13W)
  over g873, g889 (main .650) over g884, g891 (exploiter
  .725) over g889. Champ g873 -> g884 -> g889 -> g891. Main
  knocks every block; first MAIN crowns since g655 (round 42).
  9/15 gens knock. Graft fully vindicated.
- Verdict: ALIVE, continue same (round 58). The main climbs
  again — alongside the rival, not beneath it.
- Results (g893-g907): 1 PROMO (g897 exploiter .625).
  Champ g891 -> g897. Main 4-5 knocks (.525/.575/.60/.55/
  .50-border, zero promos — knocks, not takes). Rival 5/5
  knocks. Caves late flicker (g907 mapgen1 1.0, cave1 .83);
  lakes still unsustained.
- Verdict: ALIVE, continue same (round 59).
- Results (g908-g922): 1 PROMO (g913 main .625 over g897).
  Champ g897 -> g913 (main takes again). 9 knocks both lines.
  Strike call DECLINED: strikes are round-level by definition
  (x2 consecutive knockless rounds) — this round had a main
  crown + 4 main knocks. Block-3 main fade (.375/.475/.400)
  noted as watch, not a strike. g913 won on negative train
  return (-2.47): outcome overriding dense, healthy or noise.
  First solid per-map table: mg1 .635 (best board), gap .539
  (draw-heavy positive), 2a_open .329 HOLE (24 losses).
- Verdict: ALIVE, continue same (round 60). Watches: 2a hole
  (persistent?) + block-3 fade (spread?).
- Results (g923-g937): 1 PROMO (g924 exploiter .70 over g913).
  Champ g913 -> g924. Main 2 knocks (.55/.525, no stall). Fade
  did NOT spread (block closed knocking). Rival downhill after
  crowning (.70 -> .40/.325/.475, no knocks).
- Demotion case REVIEWED, 2a STAYS: the candidate bar was
  win-rate, but the doctrine bar is CONTACT — and 2a runs 92%
  decisive (round-59 table 11/3/24). Demoting the board we
  bleed on would be training-dodging: removing the exam we
  fail. 2a stays as the open-ground whetstone. Regime fact
  banked: corridors are ours (mg1/gap), opens are theirs.
- Verdict: ALIVE, continue same (round 61).
- Results (g938-g952): 0 PROMOTIONS. Champ g924 holds. 3
  knocks (g938/g947 main-borderline .50s, g951 rival .55).
  No strike: strikes need round-level main-KNOCKLESS, and the
  main knocked twice (weakly — noted). Promo-drought is not
  knock-drought; conflating them would be goalpost-moving.
  Texture honest: main soft (.50-borderline best), rival
  stronger (.55-.70). Watch, not action.
- Verdict: ALIVE, continue same (round 62).
- Results (g953-g967): 0 PROMOTIONS. Champ g924 holds. 3
  knocks: g953 main .575 (WITH margin +0.45 — first solid
  main knock after the soft .50s), g963 rival .500 (soft),
  g966 rival .525. Softness trend NOT confirmed (one solid
  main knock breaks it). Promo drought 3 rounds — standing
  rule: not knock-drought, continue.
- Verdict: ALIVE, continue same (round 63).
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
