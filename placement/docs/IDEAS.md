# Ideas

Doctrine: estimate first, refine later. Size trades update count
against looks per update. Early slots cut `sigma`. Late slots fix bias.

Two dimensions, varied one at a time. Dimension 1 is opponent
selection (closest, spread, anchors, widths). Dimension 2 is the
match-size schedule. The champion locks dimension 1 (closest duels,
tertile-anchored quantile spread, positional 1.0/0.5 widths) while
dimension-2 sweeps run.

## Backlog

Status is `open`, `trying`, `done`, `dropped`, or `parked`.
A refinement is a new row. Leave old rows as they were.

| status | idea |
|---|---|
| done | Duel the closest `mu` (baseline). |
| dropped | Duel the highest `sigma` opponent. |
| dropped | Duel the strongest pool estimate. |
| open | All duels versus mixed FFA schedule. |
| dropped | Approach 1: 5-phase pipeline 2p/5p/10p/5p/2p with percentile brackets. |
| dropped | Champion with 5th duel moved late (4 early + 1 late). |
| done | Low-sigma-only FFA anchors (median-sigma cutoff, full-pool fallback). |
| dropped | Low-sigma-only duel opponents (anchors everywhere). |
| dropped | Mid-size late games: 4x5p spread instead of 2x10p. |
| dropped | Late mix: 10p then two 5ps (split only the second 10p). |
| dropped | Sigma-triggered duel-to-FFA switch (duel while sigma above 5.0). |
| dropped | Bookend FFAs: 10p opener, 5 duels, 10p closer. |
| dropped | Deep positioning: 10 duels then one spread 10p (bold 2). |
| done | Stricter anchors: low-sigma tertile cutoff. |
| dropped | Even stricter anchors: low-sigma quartile cutoff. |
| dropped | 4 early + 1 late duel retest under tertile anchors. |
| done | Wide-then-narrow late FFAs (1.0 sigma, then 0.5 sigma). |
| dropped | Refine width 0.3 sigma (1.0 then 0.3). |
| dropped | Bound width 1.5 sigma (1.5 then 0.5). |
| dropped | 3 duels plus 4p bridge plus two 10ps (2p,2p,2p,4p,10p,10p). |
| dropped | Dim-2 sweep B: 6 duels plus 8p plus 10p (fixed opponent rules). |
| dropped | Dim-2 sweep C: 6 duels plus 10p plus 8p (fixed opponent rules). |
| dropped | Edge-conditional narrow bound (0.5 when outside anchor range). |
| dropped | Bracket duels 4-5 (closest 1-3, then above/below). |
| dropped | Inverted widths: 0.5-sigma FFA then 1.0-sigma FFA. |
| dropped | Interleaved bulk: 3 duels, wide 10p, 2 duels, narrow 10p. |
| trying | Sparsity fallback: unrated member when anchors farther than 1 sigma. |
| open | Approach 2: zooming bracket 10p/5p/5p/2p x5, spread mu+-k·sigma, low-sigma anchors. |
| open | Approach 3: 10p/6p/2p x7, quantile spread at 1.0 sigma, large-first coarse-to-fine. |
| done | Champion order with spread FFA opponents (quantiles of N(mu, sigma), low-sigma ties). |
| dropped | Approach 3 schedule exact: 10p, 6p, then duels, all spread. |
| dropped | Sandwich: duels, one spread FFA-10, precision duels last. |
| dropped | Champion spread width 0.5 sigma (tighter late thresholds). |
| dropped | Champion spread width 1.5 sigma (wider late thresholds). |
| dropped | Champion duel count 7 (boundary 16) with 10p plus 6p late. |
| dropped | Champion split: 3 duels then FFA bulk (boundary 24). |
| done | Full-budget FFA-10 versus closest mus (bold: 3 updates per bot). |

## Bold lines

Two misses in a row (sigma duel, strongest duel) force a bold idea.
Bold line 1 (2026-10-03): comparison efficiency beats update count.
One 10-player game buys 9 pairwise looks for 10 slots; duels buy 1 look
per 2 slots. Test the size-axis endpoint first (all FFA-10), then mix.
Judge after iteration 5: confirmed. Duels-first mix (16.64) beats pure
FFA-10 (20.39) beats the mirror schedule (22.04). Order matters more
than the mix; bulk updates need an already-positioned `mu`.

Five misses in a row (iters 16-20) force bold line 2 (2026-10-03):
positioning depth beats bulk count. Ten sequential duels walk `mu`
to the extremes before a single full-size spread FFA corrects it.
Predicts the seed-2 gap narrows. Judge after iteration 23.
Judged: refuted at iteration 21 (18.38, seed-2 gap widened). Depth
cannot replace the second bulk update.
| done | Duels first, then FFA with late budget. |
| dropped | Size from `budget_left`: big games early, duels late. |

## External approaches (2026-10-03)

Three outside proposals, recorded verbatim in spirit. All three say
large-first; our loop says duels-first (iter 4 beat iter 5). The
gap may be the objective: they minimise final `sigma`, we score
mean `abs(mu minus mu_true)`. Test, do not assume.

### Approach 1: 5-phase pipeline (5x2p + 2x5p + 1x10p = 30 slots)

Claim: 1v1 has the best signal-to-noise per slot; large FFA bounds
the macro-quantile; small FFA tests consistency in a tight cluster.
Maximise expected entropy reduction each step.

- Stage 1, coarse binary search (matches 1-2, 1v1): M1 vs a low-`sigma`
  anchor at the 50th percentile; M2 vs 75th percentile on a win,
  25th on a loss.
- Stage 2, local cluster validation (match 3, 5p): opponents at
  estimate `+1 sigma`, 2x at estimate, `-1 sigma`.
- Stage 3, global quantile stress-test (match 4, 10p): 9 opponents
  at the 10th-90th deciles (stratified multi-threshold filter).
- Stage 4, mid-tier recalibration (match 5, 5p): all opponents
  within `+-0.3 sigma` of the updated estimate (max match quality).
- Stage 5, high-precision convergence (matches 6-8, 1v1): exact
  estimate, then `+-0.5 sigma` by M6 result, then `Q >= 0.95` vs a
  minimal-`sigma` benchmark.
- Rules: zero high-`sigma` opponents (uncertain pairs split variance
  reduction); broad spreads early, `Q ~= 1.0` late; set draw margin
  exactly since draws vs stronger opponents carry information.

### Approach 2: zooming bracket (1x10p + 2x5p + 5x2p = 30 slots)

Order: 10p, 5p, 5p, then five 1v1s. Objective is `E[sigma_final^2]`,
not rating movement. Recalculate the opponent target after every game.

- Never stack an FFA at one skill: spread opponents as thresholds
  across the uncertainty interval (2nd in a spread field bounds the
  player; 2nd among identical opponents says little).
- 1v1: opponent `mu` equals own `mu`, smallest `sigma` available.
- 5p: `mu - sigma, mu - sigma/3, mu + sigma/3, mu + sigma`.
- 6-8p: `mu +- 1.2-1.4 sigma`. 9-10p: `mu +- 1.5-1.7 sigma`
  (from the prior that is about 10.8-39.2).
- Large FFA first because early `sigma` is huge and a 1v1 at `mu=25`
  is likely mismatched; zoom in as `sigma` shrinks.
- Rejects 5x2p + 2x10p: the second 10p is redundant once uncertainty
  has collapsed; small matched 1v1s are the precise instrument late.
- Precision-only sims: 15x2p final `sigma ~1.97` beats mixed
  schedules (~2.2) beats 3x10p (~2.6); 4p FFA is the useful frontier
  size beside 1v1.
- Keep a pool of high-confidence calibration players across `mu`;
  prefer established anchors over merely close `mu`s.

### Approach 3: per-game information cap (1x10p + 1x6p + 7x2p = 30)

Claim: one game = one performance draw, so a game adds at most
`1/beta^2` precision however many opponents attend. Measured per-slot
efficiency peaks at 4p, 2p ties it, 10p is ~33% worse; 3x10p buys
~1.86 units vs ~2.7 for 15x2p. Small games win on pure information.

- Schedule buys one large FFA up front for bracketing, then
  refinement: 10p, 6p, then seven 1v1s (9 games). Cost vs pure 1v1
  is ~10-15% higher final `sigma`, paid for diversity/robustness.
- Ordering large-first is unambiguous/coarse-to-fine and not
  symmetric: early 1v1s at an untrustworthy `mu` waste their bit,
  while a wide FFA is a parallel binary search.
- Opponents at the normal quantiles of `N(mu, (1.0 sigma)^2)`;
  the 1.0 width beat 0/0.5/1.5/2.0 in sweeps. Re-centre on current
  `mu` every game; 1v1s at exactly current `mu`; lowest-`sigma`
  opponents only.
- Setup notes: `tau ~= 0` during placement; draw probability 0 when
  ties are impossible; 3p would slot between 2p and 4p.
- Caveat: the pool must span the newcomer's true skill or nothing
  recovers, `sigma` stalls.
