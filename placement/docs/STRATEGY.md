# Strategy

Champion is the MSE-champion shape carried as the corr baseline
(iter 1, corr 0.9870 over seeds 0-4, held-out 0.9887 over seeds 5-9):
pool-range census opener, then `N(mu, 1.25 sigma)` and `N(mu, 1.875
sigma)` spreads from the low-sigma tertile of the last 400 arrivals.
Iter 17 took the title (corr 0.9901, pooled-15 0.9907): census opener,
6p refine (5 rulers) at `N(mu, 1.0 sigma)` from the recency tertile,
then 7 closest-mu duels. Duel tails rank after positioning; duel
openers stay dead (iters 2/10/11).
Prior round record lives in `placement/archive/mse-round/`.
Update this file when the champion moves.
