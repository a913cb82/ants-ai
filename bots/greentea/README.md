# GreenTea bot

Port of **GreenTea** by **brunneng** — 2nd place (score 89.98) in the
2011 AI Challenge Ants competition.

Source: read-only reference at
`/home/acbraith/projects/ants-ai/vendor/ants-topbots/greentea/`
(26 Java files, `MyBot.java` 2502 lines).

## Layout

- `*.java` — copied verbatim from the original (do not move them out;
  the engine runs the bot from its own dir).
- `greentea.sh` — compiles with `javac -d build *.java` when `build/` is
  missing, empty, or older than any source, then `exec java -cp build MyBot`.
- `greentea.bot` — manifest containing exactly `bash greentea.sh`.
- `build/` — compiled classes (gitignored, rebuilt automatically).

## Deviations from the original

None. The 2011 Java-6-era code compiles clean under `javac 17`
with plain `javac -d build *.java` — no source changes were needed.

## Protocol

`MyBot` is the main class. The bundled `Ants.java` already speaks the
Ants stdin/stdout protocol our engine uses, and `greentea.sh` wires the
classpath (`-cp build`) so `MyBot` starts directly.

## Rebuild

```sh
cd bots/greentea
rm -rf build
bash greentea.sh        # recompiles, then waits on stdin (Ctrl-C to stop)
javac -d build *.java   # manual recompile without running
javac -version     # must be 17 (tested with 17.0.20.1)
```
