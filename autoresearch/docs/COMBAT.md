# Combat program ledger

The 8-approach fan-out, round-robin by most remaining iterations.
Exam order rule: always examine the approach with the most remaining
iterations next (ties cycle in approach order).

Champion: Crowd (mu 67.9, `champion/main = a9d4173`).

## Scoreboard

| Approach | Used | Left | Scores (mu) | Best | Status |
|---|---|---|---|---|---|
| xathis 1-ply | 4+0 | 3 | 25.2 / 27.0 / 30.7 / 16.5 | Xathis3 30.7 | bold1 coded, queued |
| dirichlet sampling | 4+0 | 3 | 26.3 / 36.4 / 37.2 / 27.2 | Dirichlet3 37.2 | bold1 coded, queued |
| influence (Memetix) | 3 | 1 | 28.8 / 29.5 / 34.4 | Influence3 34.4 | tune3 coded, queued |
| greedy fields | 2 | 2 | 16.1 / 26.6 | Greedy2 26.6 | tune2 coded, queued |
| softmax 1-ply | 1 | 3 | 41.5 | Softmax 41.5 | tune1 coding |
| sequential fixing | 1 | 3 | 49.7 | Fixing 49.7 | tune1 coding |
| precomputed tables | 1 | 3 | 55.5 | Tables 55.5 | tune1 coding |
| two-stage | 0 | 4 | — | — | committed, queued |

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
