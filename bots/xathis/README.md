# xathis

Port of **xathis** — 1st place, score 90.79, 2011 AI Challenge (Ants).

- Author: xathis (http://xathis.com/posts/ai-challenge-2011-ants.html)
- Reference tree: `T-Py-T/AntsAIBot`, `docs/reference/xathis/`
  (authoritative `Strategy.java` ~1773 lines + `postmortem.txt`).
- Local read-only source for this port:
  `vendor/ants-topbots/xathis/` (branch `main`) — 8 files:
  `Ant.java`, `Connection.java`, `Direction.java`, `Logger.java`,
  `MyBot.java`, `Strategy.java`, `Tile.java`, `Type.java`.

## Assembly

All 8 reference `.java` files are copied verbatim into this dir.
No starter-framework files were needed: xathis ships its own
complete engine harness (`Connection.java` speaks the raw
`ready`/`go` text protocol on stdin/stdout; `MyBot.main` calls
`Connection.run(new Strategy())`). `Strategy.java` imports only
`java.text` + `java.util`, so there is nothing to merge.

Name-collision audit (xathis vs the standard 2011 Java starter
`Aim.java / Ants.java / Bot.java / Ilk.java / Tile.java`):

| Name      | Winner  | Reason                                              |
|-----------|---------|-----------------------------------------------------|
| Ant       | xathis  | Only xathis defines it; starter has no `Ant`.       |
| Direction | xathis  | Only xathis defines it; starter uses `Aim`.         |
| Tile      | xathis  | xathis `Tile` is a rich value object (neighbors,    |
|           |         | dist/prev, explore/A\* fields); starter `Tile`      |
|           |         | (row/col only) is unused by this bot.               |
| Type      | xathis  | Only xathis defines it; starter uses `Ilk`.         |
| Ants/Bot/ | neither | Not referenced by any xathis file; omitted.         |
| Aim/Ilk   |         |                                                     |

Entry point: `MyBot` (`java -cp build MyBot`).

## Deviations from reference

None. Zero compiler fixes were required (`javac 17` clean);
no logic, protocol, or file was modified. `md5sum` of each
`.java` file here matches `vendor/ants-topbots/xathis/`.

## Rebuild / run

The engine runs each bot from its own dir:

```sh
cd bots/xathis
bash xathis.sh            # javac -d build *.java when stale, then java -cp build MyBot
```

`xathis.sh` recompiles only when a `.java` file is newer than
`build/`; `build/` is gitignored (see `.gitignore` in this dir).
The `xathis.bot` manifest contains exactly the run command
(`bash xathis.sh`).
