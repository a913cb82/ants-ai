# Ideas (MSE round)

Doctrine: squared error weights tails. Extremes dominate: under the
old champion a [75,100] bot errs ~28 (weight ~784) against ~25 for a
mid bot. Stability across seeds beats typical-bot level. Bound wide,
refine tight, rulers calibrated. Prior round record lives in
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

Nineteen misses in a row (iters 23-41) force bold line 7 (2026-10-03):
tail-skewed two-sided grid. Bold 2 failed binary (one side only);
this keeps both-side coverage but shifts grid mass 0.05 toward the
bot's tail side versus the anchor median. Predicts tails gain
without the bound collapse. Judge after iteration 44.
Judged: refuted at iteration 42 (255.4596, every seed regressed);
even soft skew displaces load-bearing thresholds.
| done | Interleaved bulk retest (3d, wide 10p, 2d, narrow 10p): lost MAE by 0.009; mid re-positioning may cut tails. |
| done | Bracket duels retest (closest 1-3, then above/below): deliberate tail insurance. |
