# Strategy

Baseline is the MAE champion carried over (2026-10-03): 5 closest-`mu`
duels, then a spread 10p at `N(mu, 1.0 sigma)`, then a spread 10p at
`N(mu, 0.5 sigma)`, FFA opponents from the low-`sigma` tertile. Its
MAE mean was 14.8370; its MSE baseline is 323.1547 over seeds 0-4
(305.4304, 362.9823, 371.7684, 271.8279, 303.7645), recorded at
`dfe56ea`. History lives in `WORKLOG.md`.
Update this file when the champion moves.
