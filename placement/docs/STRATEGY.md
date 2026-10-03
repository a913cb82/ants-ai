# Strategy

Champion is duels-first then wide-narrow FFA-10s (2026-10-03, mean
14.8370 over seeds 0-4). Five closest-`mu` duels position the bot;
the first ten-player game spreads tertile anchors at `N(mu, sigma)`
to bound it, and the second tightens to `N(mu, 0.5 sigma)` to refine
it. History lives in `WORKLOG.md`. Update this file when the
champion moves.
