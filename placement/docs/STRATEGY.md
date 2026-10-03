# Strategy

Champion is duels-first then tertile-anchor spread FFA-10s
(2026-10-03, mean 15.1426 over seeds 0-4). While more than 20 slots
remain it duels the closest `mu`; with the last 20 slots it plays two
ten-player games against quantile-spread opponents drawn from the
low-`sigma` tertile of the pool (full-pool fallback). Cleaner
thresholds fix the hard seeds. History lives in `WORKLOG.md`.
Update this file when the champion moves.
