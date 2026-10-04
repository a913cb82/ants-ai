# lazarant

Port of **lazarant** — 6th place, Java entry in the 2011 AI Challenge
(Ants). Source copied verbatim (not moved) from the read-only reference
`vendor/ants-topbots/lazarant/` on `main` (17 `*.java` files; the
reference dir's remaining files are `META-INF/MANIFEST.MF` packaging
metadata and the `make.cmd` build script, neither needed to run).

Main class: `MyBot` (contains `public static void main`).

## Deviations from upstream

None. The sources compile cleanly under `javac 17` with a single
deprecation warning (`Bot.java:235`, `new Integer(String)`, deprecated
for removal). The warning is harmless and the code was left untouched
per the "fix only what the compiler rejects" rule.

## Rebuild / run

The engine runs the bot with this directory as the working directory.
`run.sh` recompiles into `build/` whenever a `*.java` file is newer
than `build/MyBot.class` (or the class is missing), then execs the bot:

```sh
cd bots/lazarant
./run.sh            # or: bash run.sh
```

Manual rebuild:

```sh
cd bots/lazarant
rm -rf build
javac -d build *.java
java -cp build MyBot
```

The manifest `lazarant.bot` holds the one-line run command (`bash
run.sh`), following the `bots/*/` manifest pattern (one-line command,
run with the bot directory as cwd). `build/` is gitignored.
