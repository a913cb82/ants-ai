# Ideas (MSE round)

Doctrine: squared error weights tails. Extremes dominate: under the
old champion a [75,100] bot errs ~28 (weight ~784) against ~25 for a
mid bot. Stability across seeds beats typical-bot level. Bound wide,
refine tight, rulers calibrated. Confirmation rule (2026-10-03):
selection margins under ~2.0 must validate on seeds 5-9; the
4.25-over-4.0 margin (0.90) was noise and cost a correction.
Overturn rule (2026-10-03): pooled and unbiased-fresh seeds must
agree; the 1.75-closer audit (fresh -3.71, pooled +0.40) keeps the
incumbent on disagreement. Prior round record lives in
`placement/archive/mae-round/`; do not relitigate settled cells
without an MSE reason.

## Backlog

Status is `open`, `trying`, `done`, `dropped`, or `parked`.
A refinement is a new row. Leave old rows as they were.

| status | idea |
|---|---|
| done | MAE champion carried as baseline (5 duels, 1.0/0.5 10ps, tertile). |
| done | Wide bound retest (1.5 then 0.5): seed-2 fixer under MAE, likely winner under MSE. |
| done | Wider still (2.0 then 0.5): trace the bound-width gradient. |
| dropped | Bound 2.5 then 0.5: find the top of the gradient. |
| dropped | Edge-conditional narrow bound (failed rarely under MAE; extremes weigh more now). |
| dropped | Approach 1 pipeline retest (tightest seed spread under MAE). |
| done | Twin-wide 10ps 2.0/2.0, no narrow refine (bold 1). |
| dropped | Symmetric pairs recheck under MSE (0.5/0.5, 1.0/1.0). |
| dropped | Tail-skewed two-sided grid toward bot tail side (bold 7). |
| done | Mixed anchors: full-pool opener, tertile later bulks. |
| dropped | Full-pool first two 10ps, tertile last: extend the reach. |
| dropped | Inverted mix: tertile opener, full-pool rest (factorial cell). |
| done | Full-pool opener at 3.5: re-sweep width unfiltered. |
| done | Full-pool opener at 4.0: climb the unfiltered gradient. |
| dropped | Full-pool opener at 4.5: top of the unfiltered gradient? |
| dropped | Game-2 conditional reach: full-pool 2.5 iff off-median (probe). |
| dropped | Quartile anchors under 4.0-opener shape (anchor ladder). |
| dropped | Widths 4.0/2.5/2.0: second-10p re-sweep under mixed anchors. |
| dropped | Widths 4.0/2.0/1.5: third-10p at 1.5 under mixed anchors. |
| dropped | Hollow-spread opener: 8 edge quantiles + center pin (bold 8). |
| dropped | Game-3 full-pool: last anchor-factorial cell (full, tertile, full). |
| done | Full-pool opener at 4.25: gradient-top micro-probe. |
| dropped | Full-pool opener at 4.375: bisect the top. |
| dropped | Widths 4.25/2.25/2.0: game-2 micro-probe. |
| dropped | Split bulks 5p+5p+10p+10p, opener 4.25 full-pool (bold 9). |
| dropped | Full-pool opener at 4.125: bisect down from 4.25. |
| dropped | Game-2 quartile anchors: per-game strictness. |
| dropped | Sizes 9p+9p+10p+duel: 9-player games with closing duel. |
| dropped | Full-pool opener at 3.75: gradient point between winners. |
| dropped | Front-loaded mop-up 10+10+6p+4p closer (bold 10). |
| dropped | Five uniform 6p spreads: close the size book. |
| done | Game-2 at 1.5: complete the game-2 width ladder. |
| dropped | Game-3 at 2.5: wider closer under the 1.5-second shape. |
| dropped | Game-3 at 1.5: narrow closer under the 1.5-second shape. |
| dropped | Young-pool full game-2: pool under 300 skips anchors (bold 11). |
| dropped | Game-2 at 1.0: narrow-side gradient step. |
| dropped | Opener 4.5 under the 1.5-second shape: interaction check. |
| dropped | Game-2 quartile under the confirmed shape: interaction check. |
| dropped | Game-3 quartile: last anchor cell. |
| dropped | Half-pool anchors games 2+3: median cutoff (bold 12). |
| done | Game-2 at 1.25: bisect the narrow side. |
| dropped | Game-2 at 1.125: continue the narrow slide. |
| done | Game-3 at 1.75: bisect 1.5 and 2.0. |
| dropped | Game-3 at 1.625: bisect 1.5 and 1.75. |
| dropped | Game-2 at 1.375: re-check from above. |
| dropped | Joint game-2+3 at 1.375/1.625: diagonal interaction (bold 13). |
| dropped | Joint game-2+3 at 1.125/1.875: steeper valley. |
| dropped | Opener 4.125 under the confirmed shape. |
| dropped | Opener 3.875: last opener micro. |
| dropped | Tertile opener under the confirmed shape (bold 14). |
| dropped | Game-2 full-pool: last factorial flip. |
| done | Game-3 at 1.875: last micro. |
| dropped | Game-3 at 1.9375: bisect 1.875 and 2.0. |
| dropped | Game-2 at 1.375 under the 1.875 closer. |
| dropped | Zoom-down rest 1.875/1.25: coarse-to-fine (bold 15). |
| dropped | Flat narrow rest 1.25/1.25: test the valley wall. |
| dropped | Game-2 at 1.1875: bisect 1.125 and 1.25. |
| dropped | Game-3 at 1.8125: bisect 1.75 and 1.875. |
| dropped | Flat wide rest 1.875/1.875 (bold 16). |
| dropped | Game-2 at 1.5 under the 1.875 closer: last interaction cell. |
| dropped | Opener 3.9375: bisect 3.875 and 4.0. |
| dropped | Game-3 at 1.5: last ladder cell. |
| dropped | Hollow opener under valley rest: division of labor (bold 17). |
| dropped | Edge-heavy opener grid: dense edges, sparse middle. |
| dropped | Split closer 5p+5p: mid-schedule update (bold 18). |
| dropped | Split game-2 5p+5p mid: complete the split family. |
| dropped | Opener 4.0625: last opener sliver. |
| dropped | Quartile anchors retest (cleaner thresholds for hard seeds). |
| dropped | 3p opening: 2x3p closest-pair instead of 3x2p (same 6 slots). |
| dropped | 4p mid game: bot plus above, below, closest replaces bracket pair. |
| dropped | All-3p schedule: ten 3p games, positioning and bulk unified. |
| parked | Duel-heavy sandwich: 4d, 10p, 2d, 6p, 2d (duels cost ~74, iters 30/33). |
| parked | Twin mid-bulk: 7 duels, 6p, 2 duels, 6p (duels cost ~74). |
| parked | Bookend brackets: closest, bracket pair, 10p, bracket pair, 10p (duels cost ~74). |
| parked | Bracket triple mid: 2d, 10p, above/below/closest, 10p (duels cost ~74). |
| parked | Opening duel ladder under MSE shape: 2, 4, 6 opening duels (duels cost ~74). |
| dropped | Adaptive refine width: 2.0 iff mid sigma above 6.5 else 0.5. |
| dropped | Adaptive refine at 4.0: sigma probe says refine-time mean is 3.9. |
| dropped | Tail-chasing spread: one-sided thresholds toward the bot tail. |
| dropped | Closing duel: 8p refine plus a final closest duel (28+2 slots). |
| dropped | Pool-size-adaptive opener: 4.0 sigma under pool 200 (bold 6). |
| dropped | Forward bracketing: duel 1 closest, duels 2-3 above/below (archive). |
| dropped | Median anchors under twin-wide 2.0 spreads (archive). |
| dropped | Positioning depth 6/7 duels with twin bulk kept (archive). |
| done | Bulk-only: three 10ps at 2.0, zero duels (bold 3). |
| done | Bulk-only width sweep: first 10p at 2.5, rest 2.0. |
| done | Bulk-only first 10p at 3.0: trace the new gradient. |
| dropped | Bulk-only first 10p at 3.5. |
| dropped | Bulk widths 3.0/2.5/2.0: sweep the second 10p. |
| dropped | Bulk widths 3.0/2.0/1.0: narrow the third 10p. |
| dropped | Equal-bits ladder 2+4+6+8+10, spread 1.0 throughout (info). |
| dropped | Zoom widths: 1 duel, 9p at 2.0, 9p at 1.0, 10p at 0.5 (info). |
| dropped | Split-budget recenter: 2+3+10 then 5+10 halves (info). |
| dropped | Augusta Cut: 2x6p open, 2x6p anchors-only, 10 closing duels (sports). |
| dropped | World Cup pots: each FFA draws 3 bottom + 3 mid + 3 top mu (sports). |
| dropped | Swiss 12 duels no-rematch, then two 10p finals (sports; fixed to 5 walk-out + 2 bulks for slots). |
| dropped | Shrinking zoom: duel, 9p at 2.0, 9p at 1.0, 10p at 0.5 (bold 4). |
| dropped | Gatekeeper FFA: second 10p shifted a tier stronger than mu (sports). |
| parked | Gradient fields: weak 10p heat, peer semi, shark-tank final (sports; gatekeeper verdict covers asymmetry). |
| dropped | Successive-halving duel tournament with FFA confirmation (bayes). |
| dropped | Deterministic UCB rotation: score -dist + 0.5 sigma, cycle top 6 (bayes). |
| dropped | Unfiltered bulk-only: full-pool spreads, no tertile (bold 5). |
| dropped | Augusta Cut fixed: four 6p spreads then 3 closing duels. |
| dropped | D-optimal 4-duel screen at mu +- {0.5, 1.5} sigma, then bulks (bayes). |
| dropped | Wide-grid quantiles: fixed CDF grid 0.05..0.95 at 2.0 sigma (bayes). |
| dropped | Push-fold routing: wide twin-10p for high-sigma, duels-only for settled (poker). |
| dropped | Bounty sniper: 1 max-sigma duel then 28-slot champion core (poker). |
| dropped | Refine at 1.0 under twin-wide: 2.0 then 1.0 widths (poker). |
| parked | Rank-entropy 4p opponent choice (info; 4p mid failed iter 12). |
| parked | Hot sigma-weighted draw targeting 0.10 (info; draw lost MSE iter). |
| parked | Conditional one-sided tail-hedge above mu 60 (bayes; bold 2 refuted). |
| parked | Expected-improvement duel filter skipping clone mus (bayes). |
| parked | Satellite lock-up: duels-only once settled (poker; needs sigma rule). |
| parked | Shot-taking directional FFA for extremes (poker; one-sided refuted). |
| dropped | Tail-chasing one-sided spread for tail bots (bold 2). |
| open | Game-3 1.8125 with two-set judging (archivist; iter 91 lost 0.07 selection-only, rules demand held-out). |
| open | Cross-bulk no-rematch valley (sports/bayes/epi/archivist consensus; disjoint ruler sets, zero slot cost). |
| open | Flat-mid rest 1.5625/1.5625 (auctioneer; missing shape-matrix cell). |
| open | Game-2 1.125 under 1.875 closer (archivist; iter 75 sel +6.62 priced under 2.0-closer only). |
| open | Per-quantile mixed anchors: inner-5 tertile, outer-4 full-pool (auctioneer; hollow without amputating center). |
| open | Opener 3.75 under valley rest (archivist; iter 62 pooled tie priced under 2.0/2.0 rest). |
| open | Closer 2.5 under 1.25-second (archivist; iter 66 held-out -0.13, thinnest cell). |
| dropped | Game-3 1.8125 with two-set judging (archivist revival). |
| dropped | Cross-bulk no-rematch valley (consensus structural). |
| dropped | Flat-mid rest 1.5625/1.5625 (auctioneer shape cell). |
| dropped | Game-2 1.125 under 1.875 closer (duplicate of iter 80). |
| dropped | Per-quantile mixed anchors games 2+3 (auctioneer S2). |
| dropped | Opener 3.75 under valley rest (archivist revival). |
| dropped | Closer 2.5 under 1.25-second (thinnest cell). |
| dropped | Chase-combining repeat-wide 4.0/4.0/1.5 (bold 19). |
| dropped | Double-tap opener 4.0/4.0/1.25 (adversary S3). |
| dropped | F1 Q2-half anchor ladder full/half/tertile (sports). |
| dropped | Stratified 3-3-3 closer (sports pots variant). |
| dropped | Game-2 halo mixture 5x1.25 plus 4x2.5 (adversary S2). |
| dropped | Game-3 mixture 5x1.25 plus 4x2.5 (bayes P3). |
| dropped | Split-middle 10+5+5+10 valley halves (info/poker). |
| dropped | Ratio upshift 1.5/2.25 rest (info P4). |
| dropped | HARQ sigma-gated closer 2.5/1.5 (bold 20). |
| dropped | Tight early-position pool-gated opener (poker P2). |
| dropped | Closest-cluster ring closer (poker/epi). |
| dropped | Mu-gated closer 2.5/1.5 on |mu-25|>25 (poker P4). |
| dropped | Undercut 0.75/2.75 rest (race A). |
| dropped | Overcut 3.0/1.0 rest (bold 21). |
| dropped | Quintile game-2 0.875 plus 1.0 closer (race D). |
| dropped | Edge-dense closer grid (adversary S1). |
| dropped | Senior-tertile anchors exclude 50 most recent (adversary S4). |
| dropped | Jittered-grid diagnostic per-bot phase (bayes/epi). |
| trying | Fixed absolute-site opener tracts (epi D3). |
| trying | Pool-range census sites (tuning 126b). |
| open | Chase-combining repeat-wide 4.0/4.0/1.5 (info; diversity-combine before zoom). |
| open | Double-tap opener 4.0/4.0/1.25 (adversary; second wide after recentering, full-pool G2 untested at 4.0). |
| open | Split-middle 10+5+5+10 valley halves (info/poker; mid-schedule re-aim, halves sandwiched not late). |
| open | Ratio upshift 1.5/2.25 rest (info; +20% power at fixed 2:3 shaping ratio). |
| open | Game-2 halo mixture 5x1.25 + 4x2.5 (adversary; narrow core plus wide halo in one 10p). |
| open | Game-3 mixture 5x1.25 + 4x2.5 model-averaged closer (bayes; straddle the flat). |
| open | F1 Q2-half anchor ladder full/half/tertile (sports; interior anchor order untested). |
| open | Stratified 3-3-3 closer relative to bot (sports/epi; forced below/peer/above balance). |
| open | Tight early-position pool-gated opener (poker; pools <90 open 1.5 tertile, inverse of failed bolds). |
| open | Closest-cluster ring closer (poker/epi; nine nearest tertile rulers, width limit test). |
| open | Mu-gated closer 2.5/1.5 on |mu-25|>25 (poker; two-sided hero-state routing). |
| open | Undercut 0.75/2.75 rest (race; exaggerated valley at unpriced widths). |
| open | Overcut 3.0/1.0 rest (race; inverted valley at unpriced widths). |
| open | Quintile game-2 0.875 + 1.0 closer (race; strictest rulers, below-ladder widths). |
| open | Fixed absolute-site opener tracts (epi; expected kill, census not case-centered). |
| open | Recency-filtered tertile refine last-400 (epi; ruler age vs sigma). |
| open | Edge-dense closer grid 0.05..0.95 (adversary; doubled edge pins, core untouched). |
| open | Senior-tertile anchors exclude 50 most recent (adversary; quarantine confident-wrong rulers). |
| open | Jittered-grid diagnostic one-uniform-jitter (bayes/epi; retire grid-phase on tie). |
| open | Positional adaptive cluster |mu-median|>1sigma trigger (epi; full-pool wide rest on ~10-15%). |
| open | Mark-recapture closer 4 recaptures + 5 fresh (epi/bayes; paired-quadrat game-3). |
| open | DPP repulsion de-collision delta 1.0 (bayes; same targets, repair pass). |
| open | HARQ sigma-gated closer 2.5/1.5 (info; redundancy only on NACK). |
| open | Repechage positional rescue 2.5 full-pool closer (sports; |mu-median|>1sigma trigger). |
| open | 8p-band sizes 8+8+8+6 (auctioneer; expected kill, prices refresh-vs-depth). |
| open | Valley-repriced closing duel 10+10+8+2 (auctioneer; expected kill, closes duel book). |
| open | Triage rapids 2+2+2+10+10+4 (epi; expected kill, prior-conditioning duels). |
| open | NYSE close 2.25 tertile (auctioneer; wide re-open after narrow game-2). |

## Bold lines

Two misses in a row (iters 9-10) force bold line 2 (2026-10-03):
tail-chasing spread. Bots a full `sigma` from the pool median get
one-sided FFA thresholds on their tail side only; all 9 looks
concentrate where squared error lives. Predicts extreme-bot error
falls enough to pay for lost two-sided bounds. Judge after
iteration 14.
Judged: refuted at iteration 11 (364.2914, every seed regressed);
two-sided bounds are load-bearing even for tail bots.

Two misses in a row (iters 6-7) force bold line 1 (2026-10-03):
coverage-maximalist. Under MSE the refine 10p polishes typical bots
while wide coverage catches extremes; drop the narrow refine and
run twin-wide 10ps. Predicts seeds 1/2 fall and seeds 0/3 hold.
Judge after iteration 11.
Judged: confirmed at iteration 8 by adoption (302.2418, new champion);
lead fragile (seed 2 regressed 13.5), refine pulls weight on hard seeds.

Eleven misses in a row (iters 9-19) force bold line 3 (2026-10-03):
bulk-only. Three spread 10ps at 2.0 sigma with zero duels tests
whether positioning duels matter at all under MSE; wide fields from
the prior may bound directly. Predicts catastrophe or a surprise.
Judge after iteration 23.
Judged: confirmed at iteration 20 by adoption (290.3357, new
champion) and extended at 21/22; positioning duels are expendable
under MSE, wide fields bound directly from the prior.

Eight misses in a row (iters 23-30) force bold line 4 (2026-10-03):
shrinking zoom. One duel plus 9p at 2.0, 9p at 1.0, 10p at 0.5
tests size and width zoom jointly against the uniform-bulk doctrine.
Predicts failure (mid sizes and narrow widths both lost alone) but
prices the interaction. Judge after iteration 33.
Judged: refuted at iteration 31 (327.2455, seed 2 at 516);
size and width zoom have no redeeming interaction.

Eleven misses in a row (iters 23-33) force bold line 5 (2026-10-03):
unfiltered bulk-only. The tertile filter was priced with duels in
the schedule; without duels the pool is the only instrument, and
full-pool spreads may reach tail thresholds anchors cannot. Three
10ps at 3.0/2.0/2.0 from the whole pool. Judge after iteration 37.
Judged: refuted at iteration 34 (273.4087, seeds 0/1/2/4 regress);
calibrated rulers matter with or without duels.

Sixteen misses in a row (iters 23-38) force bold line 6 (2026-10-03):
pool-size-adaptive opener. Early bots face anchor-poor pools, so
widen the first 10p to 4.0 sigma while the pool is under 200 and
keep 3.0 after. Predicts early-bot tails improve without hurting
late bots. Judge after iteration 41.
Judged: refuted at iteration 39 (242.9232, seeds 0/1 regress hard);
pool size misconditions width.

Five misses in a row (iters 48-52) force bold line 8 (2026-10-03):
hollow-spread opener. Mid bands sit at 65-100 (solved) while tails
bleed 270-400, so middle thresholds may be dead weight: 8 edge
quantiles plus one center pin at 4.0 sigma, full pool. Predicts
tails bind and mids hold, or the middle was load-bearing. Judge
after iteration 56.
Judged: refuted at iteration 53 (267.6182, every seed regressed);
middle thresholds are load-bearing.

Two misses in a row (iters 56-57) force bold line 9 (2026-10-03):
split bulks. Two 5p spreads then two 10p spreads (5+5+10+10) tests
whether the opener needs 9 thresholds or 4 suffice; opener 5p at
4.25 full-pool, rest tertile at 2.0. Predicts the extra bulk buys
precision, or 4 looks cannot bound. Judge after iteration 60.
Judged: refuted at iteration 58 (256.6085, every seed regressed);
4 opener looks cannot bound.

Two misses in a row (iters 61-62) force bold line 10 (2026-10-03):
front-loaded mop-up. Two full bulks position, then 6p and 4p games
refine cheaply (10+10+6+4). Every size-varying test was small-first
or uniform; big-first-then-small is untested. Predicts cheap late
looks add precision, or small games stay weak as closers. Judge
after iteration 65.
Judged: refuted at iteration 63 (290.6161, every seed regressed);
small games stay weak as closers.

Two misses in a row (iters 66-67) force bold line 11 (2026-10-03):
young-pool full game-2. A young tertile is nine rulers all reading
prior; the full pool at least spans. Pool under 300 takes game-2
full-pool at 1.5, else tertile. Predicts thin-tertile hurts early
bots, or pool age does not matter. Judge after iteration 70.
Judged: refuted at iteration 68 (225.9936, seed 2 plus 53);
pool age does not matter.

Three misses in a row (iters 70-72) force bold line 12 (2026-10-03):
half-pool anchors. Ruler quality trades against ruler count; tertile
beats both full and quartile, so the interior between full and
tertile may hold the optimum. Median cutoff for games 2 and 3.
Predicts a bigger clean ruler pool wins, or tertile strictness is
exact. Judge after iteration 75.
Judged: refuted at iteration 73 (221.5242 sel, 204.1018 held-out);
tertile strictness is exact.

Two misses in a row (iters 77-78) force bold line 13 (2026-10-03):
joint game-2+3 shift. Coordinate descent misses diagonal
interactions; move both together to 1.375/1.625 (flatter valley).
Predicts the valley wants flattening, or singles already price
the joint. Judge after iteration 81.
Judged: refuted at iteration 79 (212.8835 sel, 204.9540 held-out);
singles already price the joint.

Two misses in a row (iters 86-87) force bold line 15 (2026-10-03):
zoom-down rest. Swap the valley to 1.875 then 1.25: classic
coarse-to-fine, the canonical MAE shape never tested under MSE.
Predicts monotone zoom beats the valley, or the valley shape is
real. Judge after iteration 89.
Judged: refuted at iteration 88 (225.9928, every seed regressed);
the valley shape is real.

Three misses in a row (iters 93-95) force bold line 17 (2026-10-03):
hollow opener under the valley rest. Fresh probe shows mids solved
(16-134) and tails bleeding (200-800): division of labor, opener
binds tails with 8 edges plus a center pin, narrow rest refines
mids. Bold 8 failed this under twin-wide; the valley rest may
complement it. Predicts tails bind and mids hold, or middle
thresholds load-bearing again. Judge after iteration 97.
Judged: refuted at iteration 96 (271.4244, every seed regressed);
middle load-bearing under every rest shape.

Two misses in a row (iters 96-97) force bold line 18 (2026-10-03):
split closer. Two 5p spreads (10+10+5+5): a mid-schedule update
sharpens the second half. Splits the closer, not the opener.
Predicts fresher mus compensate fewer looks, or 5p looks stay
weak. Judge after iteration 100.
Judged: refuted at iteration 98 (258.2711, only seed 1 improved);
5p looks stay weak.

Two misses in a row (iters 106-107) force bold line 19 (2026-10-03):
chase-combining repeat-wide. Two 4.0 openers (full-pool, then tertile)
diversity-combine the coarse bin before a 1.5 narrow refine; the second
wide differs in ruler SNR, not reach. Predicts mis-centered narrow
grids were the outage, or the second wide is redundant power. Judge
after iteration 110.
Judged: refuted at iteration 108 (247.2454, only seed 2 improved);
the second wide is redundant power.

Five misses in a row (iters 111-115) force bold line 20 (2026-10-03):
HARQ sigma-gated closer. Game-3 plays 2.5 sigma iff the bot's live
sigma after game-2 exceeds 4.0 (NACK), else 1.5; wide redundancy only
where uncertainty remains. Predicts the gate spends wide on the
right bots, or sigma carries no routable signal. Judge after
iteration 119.
Judged: refuted at iteration 116 (219.2764, only seed 2 improved);
the gate misfires.

Three misses in a row (iters 117-119 plus 120) force bold line 21
(2026-10-03): overcut 3.0/1.0 rest. Inverts the valley entirely, wide
game-2 then narrow closer; tests whether the dip direction or only
its existence matters. Predicts symmetry breaks toward the valley,
or inversion wins somewhere. Judge after iteration 124.
Judged: refuted at iteration 121 (244.1784, only seed 2 improved);
dip direction matters.

Three misses in a row (iters 89-91) force bold line 16 (2026-10-03):
flat wide rest. Both rest games at 1.875: the rest may do one job
(refine against rulers) and game-2 narrowness may be selection-set
overfit. Completes the shape matrix with flat-narrow and zoom.
Predicts one rest width suffices, or the valley dip is load-bearing.
Judge after iteration 94.
Judged: refuted at iteration 92 (224.1766, only seed 2 improved);
the valley dip is load-bearing.

Two misses in a row (iters 81-82) force bold line 14 (2026-10-03):
tertile opener under the confirmed shape. The anchor factorial
gave full-opener a mild 7-point edge under the old shape; the
narrower rest may have shifted it. Predicts the wild pool still
binds tails, or rulers suffice from game one. Judge after
iteration 85.
Judged: refuted at iteration 83 (231.2862, only seed 2 improved);
the wild pool still binds tails.

Nineteen misses in a row (iters 23-41) force bold line 7 (2026-10-03):
tail-skewed two-sided grid. Bold 2 failed binary (one side only);
this keeps both-side coverage but shifts grid mass 0.05 toward the
bot's tail side versus the anchor median. Predicts tails gain
without the bound collapse. Judge after iteration 44.
Judged: refuted at iteration 42 (255.4596, every seed regressed);
even soft skew displaces load-bearing thresholds.
| done | Interleaved bulk retest (3d, wide 10p, 2d, narrow 10p): lost MAE by 0.009; mid re-positioning may cut tails. |
| done | Bracket duels retest (closest 1-3, then above/below): deliberate tail insurance. |
