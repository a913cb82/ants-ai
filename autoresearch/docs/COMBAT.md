# Combat program ledger

The 8-approach fan-out, round-robin by most remaining iterations.
Exam order rule: always examine the approach with the most remaining
iterations next (ties cycle in approach order).

Champion: Crowd (mu 67.9, `champion/main = a9d4173`).

## Milestone 1: beat the ported 2011 bots

Conceptual target, no measurement. The ports play on as rulers
through iteration.py. We know it is met when the leaderboard
shows the ports with many games and mu below our champions.

## Scoreboard

| Approach | Used | Left | Scores (mu) | Best | Status |
|---|---|---|---|---|---|
| xathis 1-ply | 6+0 | 0 | 25.2 / 27.0 / 30.7 / 16.5 / 28.8 / 28.6 | Xathis3 30.7 | DEAD (no new best in last 3) |
| dirichlet sampling | 5+0 | 0 | 26.3 / 36.4 / 37.2 / 27.2 / 28.3 | Dirichlet3 37.2 | DEAD (no new best in last 3) |
| influence (Memetix) | 10 | 0 | 28.8 / 29.5 / 34.4 / 26.9 / 38.4 / 28.4 / 41.9 / 45.9 / 38.7 / 32.4 | Influence8 45.9 | priced-KILL middles, alive (45.9 best of last 3) |
| greedy fields | 9+0 | 0 | 16.1 / 26.6 / 41.4 / 39.1 / 35.7 / 47.7 / 16.4 / 13.3 / 18.4 | Greedy6 47.7 | DEAD (no new best in last 3); G10/G11/G12 orphaned |
| softmax 1-ply | 6+0 | 0 | 41.5 / 12.4 / 41.9 / 9.1 / 1.8 / 2.6 | Softmax3 41.9 | DEAD (no new best in last 3); S7/S8/S9 orphaned |
| sequential fixing | 4+0 | 0 | 49.7 / 10.3 / 44.4 / 42.5 | Fixing 49.7 | DEAD (no new best in last 3) |
| precomputed tables | 4+0 | 0 | 55.5 / 17.4 / 15.8 / 23.0 | Tables 55.5 | DEAD (no new best in last 3); Tables5 orphaned |
| two-stage | 4 | 0 | 13.7 / 43.2 / 38.4 / 18.9 | TwoStage2 43.2 | tie-break backfires, alive (43.2 best of last 3) |

Used counts the 4-per-approach budget; xathis/dirichlet were granted +3
bold iterations each.

## Working hypotheses

- Priority, not weights: combat moves fire only when food/guard/muster
  fail. Bold fixes reorder phases (fight-first, fight pre-pass).
- Territory density (user): simple local rules should yield minimal
  LOS density inside territory, density growth at contact, pushes at
  n+1 vs n. Emergent, never encoded. Missions + BFS + contact rules.
- xathis lore corrections (from source research): two gates (14 for
  groups, 6 for detached 1-for-1s); "never 2-for-1" is emergent from
  the eval, not a rule; strict phase order is load-bearing.
