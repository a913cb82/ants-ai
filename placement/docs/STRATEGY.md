# Strategy

Champion is iter 30 (corr 0.9904 over seeds 0-4, held-out 0.9910 over
seeds 5-9, fresh 0.9919 over seeds 10-14, pooled-15 0.9911): pool-range
census opener, 6p refine (5 rulers) at `N(mu, 1.0 sigma)` from the
low-sigma tertile of the last 400 arrivals, then 7 tail duels by
argmax predict_draw + 0.02 sigma over the 40 nearest rulers. Info
targeting sharpens positioned tails; it hurt openers (iter 10) but
helps finishers. Duel openers stay dead (iters 2/10/11). History lives
in `WORKLOG.md`. Prior round record lives in
`placement/archive/mse-round/`. Update this file when the champion
moves.
