# AntsAI

This repo plays the Ants game from the 2011 AI Challenge.
See http://ants.aichallenge.org/ for the source game.
It holds the game engine and bots.
The engine runs a match and records a replay.

## Layout

- `tools/` holds the upstream engine. Treat it as read-only. Never edit files here.
- `bots/` holds one dir per bot. Each bot dir runs stand-alone. The engine runs each bot from its own dir.
- `vendor/` holds the source archives.

## Requirements

- The engine needs Python 3.
- Run all commands from the repo root.

## Use

1. Run the engine with a map, one bot command per player, and a replay dir outside `tools/`.
2. Open the replay in the visualizer.

## Example

Play one game between two copies of the starter bot with this command:

```sh
python3 tools/playgame.py \
  --map_file tools/maps/example/tutorial1.map \
  --turns 100 --log_dir replays \
  "python3 bots/py3_starter/MyBot.py" \
  "python3 bots/py3_starter/MyBot.py"
```

The command records the game. It opens the replay in a browser page. Add `--nolaunch` to play without the visualizer.
