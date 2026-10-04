# FlagCapper (Canada) — 8th of 7897, 2011 AI Challenge

C bot by "flagcapper". Final score 85.73, rank #8.

## Provenance

- Recovered 2026-10-04 via Wayback:
  `https://web.archive.org/web/2012id_/http://flagcapper.com/code/FlagCapper_Ants.zip`
  (md5 `d83b358ae4714e4b564178c7e5539b35`)
- Postmortem: `https://web.archive.org/web/20131101052116/http://flagcapper.com/?c2`
  ("Moving Up: 8th of 7800").
- Sources copied verbatim from `vendor/ants-topbots/flagcapper/` on `main`,
  except the one-word deviation below. Reference: vendor `README.md`.

## Build

`run.sh` mirrors the upstream `Makefile`:

- compile: `gcc -O3 -funroll-loops -c` each of `MyBot.c`, `YourCode.c`, `ants.c`
- link: `gcc -O2 … -o MyBot -lm`

It recompiles only when a source (`.c`/`.h`) is newer than `./MyBot`,
then `exec ./MyBot`. The binary and `.o` files are gitignored.

Note: `Exploration.c` and `BattleResolution.c` look like spare modules —
they are absent from the Makefile `SOURCES` — but `YourCode.c` pulls both
in with `#include "Exploration.c"` / `#include "BattleResolution.c"`
(lines 488–489), so they are required at compile time and are shipped here.

## Deviations (one)

1. `MyBot.c`: `inline int distance(...)` → `int distance(...)`
   (one word dropped). The 2011 `gcc` used GNU89 `inline` semantics, which
   emit a standalone symbol; modern `gcc` (C99 and later) does not, so
   `Exploration.c`'s calls to `distance()` failed at link time with
   `undefined reference to 'distance'`. Everything else — including the
   remaining `inline int abs` and all warnings (implicit declarations,
   one `%g`/`int` format mismatch in a debug `fprintf`) — is untouched
   2011 code; the warnings do not stop the build.

## Rebuild

```sh
cd bots/flagcapper
rm -f MyBot MyBot.o YourCode.o ants.o
bash run.sh   # recompiles, then waits on stdin for engine orders
```
