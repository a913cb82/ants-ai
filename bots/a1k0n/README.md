# a1k0n

Port of **a1k0n** — 11th place, 2011 AI Challenge
(upstream: `github.com/a1k0n/ants`).

Gibbs-sampling tactical bot: each ant keeps a Dirichlet distribution over
its 5 moves (conditional on the nearest "up"/"left" ants), samples combat
moves against the clock (`SIGALRM`-based turn timer), then commits the
maximizing move. See the author's `notes/` in the vendor archive for the
reasoning behind the score constants in `Score.h`.

## Files

`Ant.cc/h`, `Bot.cc/h`, `Food.h`, `Grid.cc/h`, `Location.h`, `MyBot.cc`,
`Score.h`, `Square.h`, `State.cc/h` and `Makefile` are verbatim copies of
the upstream sources (reference:
`/home/acbraith/projects/ants-ai/vendor/ants-topbots/a1k0n/`, read-only).
Added here: `run.sh`, `a1k0n.bot`, `.gitignore`, this README.

## Deviations

None. The code builds cleanly with the vendored `Makefile` flags
(`-O3 -g -funroll-loops -Wall`, link `-O2 -lm`) under the repo toolchain
(g++ 11.4.0) — no source changes were needed, so there is nothing to
reconcile on future re-ports. `run.sh` invokes `make`, which honors those
flags. (GNU make prints one benign warning about the old-style
`.cc.o: *.h` suffix rule with prerequisites; it still builds correctly.)

## Rebuild / run

The engine runs each bot from its own dir. From the repo root:

```sh
bash bots/a1k0n/run.sh        # rebuilds via make if stale, then execs ./MyBot
```

or manually:

```sh
cd bots/a1k0n && make && ./MyBot
```

`a1k0n.bot` holds exactly the run command (`bash run.sh`). The compiled
`MyBot` binary and `*.o` files are gitignored.
