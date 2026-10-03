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
| trying | Twin-wide 10ps 2.0/2.0, no narrow refine (bold 1). |
| open | Symmetric pairs recheck under MSE (0.5/0.5, 1.0/1.0). |
| open | Quartile anchors retest (cleaner thresholds for hard seeds). |

## Bold lines

Two misses in a row (iters 6-7) force bold line 1 (2026-10-03):
coverage-maximalist. Under MSE the refine 10p polishes typical bots
while wide coverage catches extremes; drop the narrow refine and
run twin-wide 10ps. Predicts seeds 1/2 fall and seeds 0/3 hold.
Judge after iteration 11.
| done | Interleaved bulk retest (3d, wide 10p, 2d, narrow 10p): lost MAE by 0.009; mid re-positioning may cut tails. |
| done | Bracket duels retest (closest 1-3, then above/below): deliberate tail insurance. |
