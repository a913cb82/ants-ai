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

What the archives say for corr. MAE killed precision schedules for
accuracy reasons that do not transfer: duels-first won MAE outright,
and approaches 2/3 explicitly minimized final sigma, which is exactly
what ranking rewards. MSE killed duels (iters 30/33: duels cost ~74),
routing, mixtures, and displacement — those kills transfer, because
none of them teach per game. MSE priced widths under tail weights;
corr reprices them without. The main-branch exam (info-score duels
plus propose FFA) ranks at 0.9655 with mu scoring and is the package
to beat alongside the baseline.

## Backlog

Status is `open`, `trying`, `done`, `dropped`, or `parked`.
A refinement is a new row. Leave old rows as they were.

| status | idea |
|---|---|
| trying | Baseline: corr of the MSE-champion shape over seeds 0-4. |
| open | Uncertainty-hunting opener: 5 closest high-sigma duels, then 1.25/1.875 tertile 10ps (info-score flavor under corr). |
| open | Mixed exam: census skeleton game 1, info-greedy refine games 2-3 within tertile anchors. |
| open | Wider refine under corr: 1.5/2.0 rest, re-priced without MSE tail weights. |
| open | Fresh-voice anchors: least-played rulers inside the tertile (recency direction, new axis). |
| open | Duel-heavy schedule retest: duels-first shapes priced dead under MSE may rank well under corr. |
| open | MAE duels-first revival: 5 closest-mu duels + 1.0/0.5 tertile 10ps (MAE champion, untested under corr). |
| open | Bracket-duel opener: closest duel, then above/below pair, then valley bulks (deliberate tail insurance). |
| open | Interleaved bulk: 3 duels, wide 10p, 2 duels, narrow 10p (mid re-positioning for tails). |
| open | Approach 2 revival: zooming bracket 10p/5p/5p/duels, sigma-minimizing by design (corr-native objective). |
| open | Approach 3 revival: 10p/6p then seven duels at 1.0 sigma, large-first coarse-to-fine. |
| open | Greedy predict_draw FFA fields (main-branch propose rule, dropped under MAE only). |
| open | Info-score duel opener: predict_draw + 0.02 sigma, deterministic top-1 (main rule minus epsilon). |
| open | Highest-sigma-seeded FFA: propose shape with candidate plus greedy info picks (main rule). |
| open | FFA size set {4,6,10} schedule: 10p census + 6p + 4p refines (main sizes, density gradient). |
| open | Sigma-triggered duel-to-FFA switch: duels while sigma above 5.0, then bulks (MAE row, corr-relevant). |
| open | Bounty sniper opener: 1 max-sigma duel, then census + valley rest (uncertainty-first stake). |
| open | Deterministic UCB rotation: score -dist + 0.5 sigma, cycle top 6 (exploration with a floor). |
| open | D-optimal 4-duel screen at mu +- {0.5, 1.5} sigma, then valley bulks (designed experiment opener). |
| open | Rank-entropy 4p mid-game: census + 4p + valley closer (mid-size information frontier). |
| open | Twin mid-bulk: 5 duels, 6p, 2 duels, 6p, narrow closer (MAE-parked, rhythm vs density under corr). |
| open | Narrow valley re-price: 1.0/1.5 rest (MAE-winning widths, killed under MSE tail weights). |
| open | Full-pool refine retest: unfiltered spreads priced under MSE duels; corr may forgive noise. |
| open | Calibration-anchored opener: established-ruler pool across mu (Approach 2/3 calibration pool). |
| open | 4p frontier schedule: 10p census + two 4p refines + duel closer (per-slot information peak). |
| parked | MSE-settled kills that transfer: routing, mixtures, displacement, rematch bans, link surgery (see mse-round IDEAS.md). No variants without a corr reason. |
| parked | Game-count anchor axes (authority/usage): Rating is mu/sigma-only; needs harness plumbing. |

## Bold lines

Two misses in a row force a bold idea from research. Record the line
3 iterations before judgement, judge on selection + held-out + fresh
agreement. First bold due after two consecutive corr misses.
