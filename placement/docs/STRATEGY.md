# Strategy

Baseline is the MAE champion carried over (2026-10-03): 5 closest-`mu`
duels, then a spread 10p at `N(mu, 1.0 sigma)`, then a spread 10p at
`N(mu, 0.5 sigma)`, FFA opponents from the low-`sigma` tertile. Its
MAE mean was 14.8370; its MSE score is not yet measured — the first
full run sets the number to beat. History lives in `WORKLOG.md`.
Update this file when the champion moves.
