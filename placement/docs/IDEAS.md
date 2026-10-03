# Ideas (corr round)

Doctrine: correlation grades orders, not levels. The loop keeps
champions by comparison, so rank truth beats level truth. Doubt
shuffles ranks even when estimates sit near truth: safe rulers confirm
the estimate but teach little, bunching bots where noise breaks ties.
Bold rulers overshoot sometimes yet spread bots along true gaps.
Faithful-shape validation (6 seeds, 30-slot harnesses): corr(mu) is
0.9655 old-exam vs 0.9654 new-exam (exam tie), corr(lb) lower both
sides, and the sigma-discount ladder falls monotonically. Carry the
MSE shape as the baseline, not the answer. Confirmation rule
(2026-10-03): thin margins must validate on seeds 5-9. Overturn rule
(2026-10-03): pooled and unbiased-fresh seeds must agree. MAE record
lives in `placement/archive/mae-round/`; MSE record lives in
`placement/archive/mse-round/`. Do not relitigate settled cells
without a corr reason.

Corr verdicts so far: duel openers dead in all flavors — iter 2
high-sigma duels 0.9557, iter 10 info-score full-port 0.9617, iter 11
closest-mu MAE-verbatim 0.9644. Duel-led schedules closed; mid-schedule
duel rows keep one expect-kill shot each.

## Backlog

Status is `open`, `trying`, `done`, `dropped`, or `parked`.
A refinement is a new row. Leave old rows as they were.
Source tags: PSY psychometrician, ARB chess-arbiter, SIG
signal-processor, DET detective, ACT actuary, SCO scout, POL
pollster, MAT matchmaker, ARC archivist-3.

| status | idea |
|---|---|
| trying | Baseline: corr of the MSE-champion shape over seeds 0-4. |
| dropped | Uncertainty-hunting opener: 5 closest high-sigma duels, then 1.25/1.875 tertile 10ps (iter 2: 0.9557, every seed regressed). |
| open | Mixed exam: census skeleton game 1, info-greedy refine games 2-3 within tertile anchors. |
| open | Wider refine under corr: 1.5/2.0 rest, re-priced without MSE tail weights. |
| open | Deferred propose-commit 1.5/1.875 rest (MAT S3; near-neighbor of champion, stability bet). |
| open | Fisher-peak narrow valley 1.0/1.5 rest (PSY S1; item information peaks near theta). |
| open | Assortative narrow closer 1.25/1.0 (MAT S1; only the closer narrows, not flat-narrow). |
| open | Twin-narrow 1.25/1.25 parallel forms, disjoint rulers (PSY S4; closer reach as MSE overhead). |
| open | CAT gradient 10+10+6+4 at 1.5/1.0/0.75 (PSY S3; scheduled narrowing, peak-info testlets). |
| open | Audit-kicker 10+10+6+4 at 1.25/1.875/1.875 (ACT S2; audit frequency vs pull density). |
| open | Fresh-voice anchors: least-played rulers inside the tertile (recency direction, new axis). |
| open | Likely-ruler hard-50 closer: 50 lowest-sigma of last-400 at 1.875 (POL S2; count not fraction). |
| open | Kalman senior-25 closer: tertile minus 25 most recent at 1.875 (SIG S2; untested interior dose). |
| open | Equating spine: 3 fixed 25/50/75 rulers recaptured G2+G3 + 6 adaptive each (PSY S2; common-item link). |
| open | Tracking panel: 3 nearest G2 rulers re-polled in G3 + 6 fresh (POL S3; local first-difference). |
| open | Skeleton re-ask: 3 census rulers nearest post-G2 mu + 6 fresh at 1.875 (DET S5; drift survey). |
| open | Split-vintage witnesses: G2 tertile of arrivals [N-400,N-200), G3 of [N-200,N) (DET S1; decorrelated eras). |
| open | Vintage quota on all three games (MAT S4; schedule-wide diversity, not closer-only cartel). |
| open | Lone alibi pin: 8 at 1.875 + 1 farthest established ruler (DET S2; one-pin consensus break). |
| open | Bad-cop/good-cop anchors at flat 1.5: full-pool G2 then tertile G3 (DET S3; trust pairing, width held). |
| open | BF prior-weighted closer: 5 targets from census centroid + 5 from live mu at 1.875 (ACT S4; reserve vs chase). |
| open | Credibility 7+2 blend closer: 7 tertile + 2 high-sigma-half at 1.875 (ACT S1; priced dose, dose ladder starts here). |
| open | Drunk-witness closer: full high-sigma tertile at 1.875 (DET S4; bimodal bet, closes axis on clean fail). |
| open | Density tie-break closer: same 1.875 grid, near-tie snaps toward denser bins (POL S1; mass decides collisions). |
| open | Proportional-strata closer: picks across below/peer/above bins by pool mass, min 1 each (POL S4; not 3-3-3). |
| open | Comp-pick mode-seeking game-2: 9 nearest tertile rulers, no Gaussian grid (SCO S3; aim at ruler mass). |
| open | Elite separator game-2: 9 rulers from top mu decile + valley closer (SCO S1; rank probe at one end). |
| open | Weak separator game-2: mirror at bottom decile (SCO S2; pair with elite, keep at most one). |
| open | Colour-balance alternation: strict above/below target pairing G2+G3 (ARB S1; no float streaks). |
| open | Micro-dithered closer: per-target +-0.15 sigma jitter before snap, grid exact (SIG S3; tie entropy, not phase). |
| open | D-optimal antipodal closer: max-min distance from G2 picks at 1.875 (SIG S1/MAT S2; non-redundant thresholds). |
| open | Crossover valley order: even arrivals valley, odd arrivals inverted, contrast decides (ACT S3; open-loop direction test). |
| open | Cross-check twin 5s mid-split: disjoint even/odd rulers at 1.25, full census + closer kept (SCO S4; middle-only split). |
| dropped | MAE duels-first revival (iter 11: 0.9644; duel openers dead all flavors). |
| open | Bracket-duel opener (duel-led; expect kill after iters 2/10/11, lowest priority). |
| open | Interleaved bulk: 3 duels, wide 10p, 2 duels, narrow 10p (mid-schedule duels, NOT openers; expect kill). |
| open | Approach 2 revival: zooming bracket 10p/5p/5p/duels at 1.6/1.0/1.0, tertile anchors (ARC R1). |
| done | Approach 3 revival (iter 17 CHAMPION as census+6p+7-duel hybrid). |
| open | Shrinking-zoom revival (duel-led; expect kill, lowest priority). |
| dropped | D-screen opener (iters 2/10/11: duel openers dead; Fisher-per-slot priced). |
| dropped | Info-score duel opener (iter 10 full-port: 0.9617; targeting flavor irrelevant). |
| open | Highest-sigma-seeded FFA: propose shape with greedy info picks inside tertile (main rule). |
| open | FFA size set {4,6,10} schedule: 10p census + 6p + 4p refines (main sizes, density gradient). |
| dropped | D-optimal 4-duel screen (duplicate of D-screen row above). |
| open | Rank-entropy 4p mid-game: census + 4p + valley closer (mid-size information frontier). |
| open | Twin mid-bulk (duel-led schedule; expect kill, lowest priority). |
| open | Full-pool refine retest: unfiltered spreads priced under MSE duels; corr may forgive noise (one shot). |
| open | Calibration-anchored opener: established-ruler pool across mu (Approach 2/3 calibration pool). |
| open | 4p frontier schedule: 10p census + two 4p refines + duel closer (duel closer; expect kill). |
| parked | MSE-settled kills that transfer: routing/gating, mixtures, displacement, rematch bans, link surgery (transfer-kills below). No variants without a corr reason. |
| parked | Accelerated-Swiss tail gate (ARB S2; gated wide spend, routing family). |
| parked | SB +0.5 sigma closer shift (ARB S3; soft skew, bold-7 family). |
| parked | Sigma-triggered duel-to-FFA switch (gated routing per ARC). |
| open | 3-stage 10+6+4+5d: 6p strata + 4p strata + 5 info duels (PHY S1/S3; depth at fixed slots). |
| open | 4-stage micro 10+4+4+4+4d: three 4p strata + 4 info duels (PHY S2; expect kill). |
| open | 10+10+10 refine-heavy: 9-ruler strata + 5 info duels (MIS S1; refine completeness). |
| open | 8+6+16 tail-from-skeleton: 7-site skeleton + 8 info duels (MIS S3; brackets iter 52). |
| open | Narrow-peer strata +-0.5 sigma (TAX S1; Fisher peak in refine). |
| open | 4-bin signed-peer strata (TAX S3; sign insurance vs flex tax). |
| open | Mass-anchored strata edges: pool-tertile bins, no sigma (TAX S4; iter-34 lesson in refine). |
| open | Asymmetric strata -1.25/+0.75 sigma (TAX S5; one direction only). |
| open | 2-bin median-split strata (TAX S2; tests whether edges matter). |
| open | Winsorized-range opener p10-p90 (LOK L1; even thresholds, no outlier tax). |
| open | Recent-400 decile opener (LOK L2; live-window mass). |
| open | Calibrated-snap deciles: lowest-sigma within 0.15 mu (LOK L3; ruler quality on near-ties). |
| open | Heavy-middle quantiles 12..88 shaped (LOK L4; pins where ties break). |
| open | Tail weight descent 0.05/0.02/0 across 7 duels (JEW J1; explore then confirm). |
| open | 6 info + closest closer (JEW J3; phases, not whole-tail). |
| open | 6 info + credible-pin closer (JEW J4; proximity vs credibility). |
| open | Duel-7 funnel to 10 nearest (JEW J2; last, narrowest claim). |
| open | Quota-split refine: 3 census-center + 2 live-mu through strata bins (BKK D4; run first). |
| open | Peer-pinned skeleton: 8 deciles + nearest-tertile pin (BKK D1; opposite of alibi). |
| open | Rebind refine: 4 strata + nearest played site (BKK D2; cheapest scale link). |
| open | Mid-tail audit duel at position 4 (BKK D3; lowest priority). |
| open | Info-inside-strata refine: mass quota, info-scored within-bin picks (BLA F1). |
| open | Draw-snapped deciles: argmax draw over 5 nearest per site (BLA F2). |
| open | Strata-gated tail: peer/below/above duel rotation, info within gate (BLA F3). |
| open | Grid-inside-strata refine: quantile targets within each bin (BLA F4). |
| open | Duel-order instrument: 7 info picks ordered above-first (GLA G4; run early). |
| open | Upset-ladder refine: 5 nearest tertile rulers above mu (GLA G1). |
| open | Soft-witness refine: max-sigma middle-tertile within +-1 sigma (GLA G2). |
| open | Outcome-spread 2/1/2 refine + signed-triple 4p + 5 duels (GLA G3). |
| open | Terminal bounty duel 7: max-sigma peer-banded last-400 (SHE S1; run first). |
| open | Mid-tail audit duel 4: max-sigma of 10 nearest (SHE S3; after S1 ties). |
| open | Census-seat survey sniper (SHE S2; parked unless S1 alive). |
| open | Terminal double-herd duels 6+7 (SHE S4; only if S1 wins). |
| open | Range-grid early window: even arrivals <200 get range+full-pool (MID S1). |
| open | FFA-heavy early window: even arrivals <200 get 10+10+10 (MID S2). |
| open | Recapture-spine early window (MID S3; regime-flip signature). |
| open | Re-census early window: fresh skeleton from live beliefs (MID S4). |
| open | Refine-pool window ladder 200/400/800 (MET: only inherited-only constant). |
| open | Equivalence shootout: champion vs iter-70 on seeds 15-29 pooled-30 (AUD; convergence proof, run last). |
| open | Fresh-voice anchors: least-played tertile rulers (AUD; needs usage plumbing, parked until harness allows). |
| open | Antipodal info tail: max-min-distance-from-refine tail (AUD; redundancy axis, untested under corr). |
| parked | Game-count anchor axes (authority/usage): Rating is mu/sigma-only, evaluate.py frozen; proxies listed as open rows. |

## Transfer-kills (ARC; metric-independent, do not revive)

Failed because they never teach per game, displace load-bearing
thresholds, or route on signal-free gates. Corr does not repair them.
Routing/gating (116/119/130/HARQ/mu-gate/positional/push-fold/
satellite/sigma-trigger); mixtures/hollow/edge (112/170, 113/153,
105/158, 53/96 bolds 8/17, 123/166, 177, index-dither); displacement/
one-sided/asymmetric (bold 2 iter 11, bold 7 iter 42, gatekeeper,
3-3-3 twice 111/152); structural no-ops (no-rematch 102/151/196,
checksum 190, DPP 132/163, mark-recapture 131/164, antipodal-RECAPTURE
180/181/189 vs antipodal-CLOSER open row above, recenter 179);
size settles (8p-band 137, splits 98/114/154, mop-up 63, Augusta,
closing duels 140/192/193); anchor settles (quartile/half/median/
senior-25/50, ancient-tertile bold 25, full-pool rest 34/142 except
the one-shot row above).

## Bold lines

Two misses in a row force a bold idea. Bold 5 (iter 17) confirmed as
champion. Misses reset: 0.
