# Worklog (MSE round)

One entry per iteration:

```
## <n> — <idea> (<date>)
- commit: <sha>
- score: mean <x> over seeds 0-4
- champion mean: <x>
- verdict: keep or discard
- what changed: <one sentence>
- what you learned: <one sentence with numbers>
- next: <next idea>
```

`mean` is mean squared error. Prior round record is archived at
`placement/archive/mae-round/`.

## 1 — wide bound 1.5 then 0.5 (2026-10-03)
- commit: ed16e2d
- score: mean 319.4704 over seeds 0-4 (286.8453, 378.2883, 356.0608, 262.0017, 314.1560)
- champion mean: 323.1547 (dfe56ea)
- verdict: keep
- what changed: first FFA spread widened from 1.0 to 1.5 sigma; duels and 0.5 refine unchanged.
- what you learned: wins by 3.68 with seeds 0/2/3 improving and seed 2 fixed as predicted, but seeds 1/4 regressed; wider bounds trade typical precision for tail coverage.
- next: wider still (2.0 bound) to trace the gradient.

## 2 — wider bound 2.0 then 0.5 (2026-10-03)
- commit: c05a544
- score: mean 316.7159 over seeds 0-4 (287.7754, 367.1452, 364.8904, 257.6713, 306.0971)
- champion mean: 319.4704 (ed16e2d)
- verdict: keep
- what changed: first FFA spread widened from 1.5 to 2.0 sigma.
- what you learned: wins by 2.75 with seeds 1/3/4 improving (seed 1 down 11), but seed 2 regressed 8.8; the width optimum differs per seed, gradient still descends overall.
- next: 2.5 bound to find the top of the gradient.

## 3 — bound 2.5 then 0.5 (2026-10-03)
- commit: c0d2e7b
- score: mean 317.8334 over seeds 0-4 (286.6899, 380.7460, 367.9831, 246.7392, 307.0087)
- champion mean: 316.7159 (c05a544)
- verdict: discard
- what changed: first FFA spread widened from 2.0 to 2.5 sigma.
- what you learned: cost about 1.12 with seeds 1/2 regressing while seed 3 hit a round-best 246.74; width optimum sits between 2.0 and 2.5 and differs per seed.
- next: interleaved bulk retest from the archive trawl.

## 4 — interleaved bulk 3d wide 2d narrow (2026-10-03)
- commit: e9d728c
- score: mean 311.2044 over seeds 0-4 (273.0052, 357.2504, 363.7061, 258.3359, 303.7243)
- champion mean: 316.7159 (c05a544)
- verdict: keep
- what changed: 2 duels moved between the FFAs (3d, 2.0-sigma 10p, 2d, 0.5-sigma 10p).
- what you learned: wins by 5.51 with every seed improving (seed 0 down 14.8); mid re-positioning before the refine FFA cuts tails under MSE.
- next: bracket duels retest, the other archive-mined idea.
