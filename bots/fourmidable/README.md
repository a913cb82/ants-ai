# fourmidable

Port of **fourmidable** — ranked 9th of 7897 entries in the 2011 Google AI
Challenge (Ants), Java. Original source lives read-only under
`vendor/ants-topbots/fourmidable/` on `main` (26 files, entry point
`MyBot.java`); the `.java` files here are verbatim copies.

Main class: `MyBot` (has `public static void main`, extends `Bot`).

## Deviations

None. The sources compile cleanly under `javac 17` with no changes.

## Rebuild / run

The bot runs stand-alone from its own directory. `fourmidable.sh` recompiles with
`javac 17` into `build/` whenever a `.java` file is newer than `build/`,
then runs the bot:

```sh
cd bots/fourmidable
bash fourmidable.sh            # compiles to build/ if stale, then: java -cp build MyBot
```

From the repo root (as the engine invokes it):

```sh
bash bots/fourmidable/fourmidable.sh
```

`build/` is gitignored build output, not committed.
`fourmidable.bot` holds the run command (`bash fourmidable.sh`).

Smoke test (50 turns vs the Python starter bot):

```sh
.venv/bin/python tools/playgame.py \
  --map_file tools/maps/example/tutorial1.map \
  --turns 50 --nolaunch \
  "bash bots/fourmidable/fourmidable.sh" \
  "python bots/py3_starter/MyBot.py"
```

Requires: JDK 17 (`javac`/`java` on PATH). No external libraries.
