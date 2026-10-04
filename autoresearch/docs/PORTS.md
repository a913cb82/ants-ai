# Porting recovered top-bots into the pool

Goal: every recovered 2011 top-bot runs in our engine from `bots/`,
joining the opponent pool on `main`.

## Pool mechanics (why this works)

- `league/pool.py`: a bot is any `*.bot` manifest under root `bots/`.
  The manifest text is the shell command; the engine runs it from the
  bot's own dir. `all_commits` (`--branches --tags`) picks up any
  `main` commit that adds one — no registration step.
- Engine defaults: turntime 1000ms, loadtime 3000ms (`tools/playgame.py`).
  `iteration.py` game length is 1000 turns.

## Per-bot plan

| Bot | Lang | Toolchain | Route |
|---|---|---|---|
| GreenTea (#2) | Java | javac + java OK | `bots/greentea/`: source + `<name>.sh` launcher (compile-if-stale, `exec java -cp build MyBot`) + `greentea.bot` (`bash <name>.sh`) |
| lazarant (#6) | Java | javac + java OK | same wrapper pattern |
| fourmidable (#9) | Java | javac + java OK | same wrapper pattern |
| runevision (#4) | C# | NO mono/dotnet/go only | Python port by coder agents, behavior-checked on scenario benchmarks; original stays in `vendor/` as spec |
| xathis (#1) | Java (Strategy.java) | javac OK | needs Ants.java harness shim from the reference tree; same wrapper once it compiles |

## Rules for each port (main-branch work, one bot per commit)

1. Copy source from `vendor/ants-topbots/<name>` (never from /tmp).
2. No binaries in git: the wrapper builds on first run, `build/` is gitignored.
3. Manifest `.bot` holds exactly the run command.
4. Smoke test before merge: 50-turn game vs RandomBot, no timeout, no crash.
   Java cold start must fit loadtime 3000ms (measure it; `java -Xshare:on` if tight).
5. `bots/<name>/README.md` notes provenance + every deviation from the original.
6. TDD per repo rules: port checks live in `tests/league/test_ported_bots.py`.

## Order

greentea -> lazarant -> fourmidable -> runevision-port -> xathis-shim ->
whatever the missing-hunt wave recovers (#3 protocolocon, #5
teapotahedron, #7 ChrisH, #8 FlagCapper).

## Why bother

Strata/duel rulers drawn from real 2011 top-bots replace our inbred
rulers: stronger selection pressure, and direct historical benchmarking
(can our champion beat GreenTea?).

## Launcher rule
Name the launcher `<bot>.sh`, never `run.sh`: the viewer names each
player from the command basename, so `run.sh` shows as "run.sh" for
every bot. The manifest holds `bash <bot>.sh`.
