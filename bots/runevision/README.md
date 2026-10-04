# runevision port

C# bot by **runevision** (Rune Skovbo Johansen), placed **4th out of 7897**
in the 2011 Google AI Challenge (Ants). He described the bot's design in a
multi-part write-up starting at `blog.runevision.com` ("part I" covers the
overall strategy: influence/heat maps, combat simulation, and goal-based
planning).

## Source

Copied read-only from `vendor/ants-topbots/runevision/` on `main`:

- `MyBot.cs` (1175 lines) — the bot: heat/attack maps, combat handling,
  goal assignment, order issuing, plus `Main` which wires
  `new Ants().PlayGame(new MyBot(), args)` to the stdin/stdout engine
  protocol.
- `Ants.cs`, `Bot.cs`, `GameState.cs`, `IGameState.cs`, `Point.cs`,
  `Tile.cs`, `Direction.cs` — starter-kit framework and engine-protocol
  handling (setup/turn parsing, `go`/`ready` loop).
- `PowerCollections/` — Wintellect Power Collections library sources
  (used for `OrderedBag<GoalPointer>` in the pathfinding queue).

Only `runevision.sh`, `runevision.bot`, `README.md`, and `.gitignore` are new;
every `.cs` file is an unmodified copy.

## Deviations from the original

None. The 2011 C# builds cleanly under modern Mono (`mcs 6.8`):

```sh
mcs -out:MyBot.exe *.cs PowerCollections/*.cs
```

One pre-existing warning remains (`Ants.cs(544,9): warning CS0219`, unused
`anyDifferent`) and is left as-is. The original shipped no build script, so
`runevision.sh` compiles `PowerCollections/*.cs` from source alongside the bot
instead of referencing a prebuilt DLL. The default (non-`DEBUG`) build uses
hardcoded `FixedParametersSetup()` values and `[Conditional("DEBUG")]`
no-op logging, so the bot needs no `data/` files at runtime — it speaks the
engine protocol purely over stdin/stdout.

## Rebuild

```sh
cd bots/runevision
rm -f MyBot.exe
./runevision.sh        # recompiles (sources newer than the missing .exe), then runs
```

`runevision.sh` recompiles only when a `.cs` file is newer than `MyBot.exe`, then
`exec mono MyBot.exe`. The compiled `MyBot.exe` is gitignored (see
`.gitignore`); the manifest `runevision.bot` contains exactly `bash runevision.sh`.
