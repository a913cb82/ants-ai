# Strategy

Champion is duels-first then spread FFA-10 with late budget
(2026-10-03, mean 16.0723 over seeds 0-4). While more than 20 slots
remain it duels the closest `mu`; with the last 20 slots it plays two
ten-player games against opponents spread at the quantiles of
`N(mu, sigma)`, low `sigma` first on ties. Early sequential duels
position `mu`, then threshold-spread FFAs bound it. History lives in
`WORKLOG.md`. Update this file when the champion moves.
