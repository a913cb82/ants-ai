# Strategy

Champion is duels-first then established-anchor spread FFA-10s
(2026-10-03, mean 15.8333 over seeds 0-4). While more than 20 slots
remain it duels the closest `mu`; with the last 20 slots it plays two
ten-player games against quantile-spread opponents drawn from the
low-`sigma` half of the pool (median cutoff, full-pool fallback).
Positioning duels first, then calibrated thresholds. History lives in
`WORKLOG.md`. Update this file when the champion moves.
