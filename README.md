# AntsAI

This repo plays the Ants game from the 2011 AI Challenge.
See http://ants.aichallenge.org/ for the source game.
It holds the game engine and two Python bots.
The engine runs a match and records a replay.

## Layout

- `tools/` holds the upstream engine. Treat it as read-only. Never edit files here.
- `bots/pas11/` holds the Pas11 bot with its `ants.py`. It runs stand-alone.
- `bots/py3_starter/` holds the Python 3 starter bot with its `ants.py`. It runs stand-alone.
- `vendor/` holds the source archives.
- Each dir under `bots/` is stand-alone. Each dir has all files the engine needs.

## Requirements

- Use Python 3.
- Run all commands from the repo root.

## Use

1. Run the engine with a map, two bot commands, and a replay dir outside `tools/`.
2. Open the replay in the visualizer.

## Example

Record one game between two copies of the starter bot:

```sh
python3 tools/playgame.py \
  --map_file tools/maps/example/tutorial1.map \
  --nolaunch --turns 100 --log_dir replays \
  "python3 bots/py3_starter/MyBot.py3" \
  "python3 bots/py3_starter/MyBot.py3"
```

Open the replay in the visualizer:

```sh
python3 tools/playgame.py \
  --map_file tools/maps/example/tutorial1.map \
  --turns 100 --log_dir replays \
  "python3 bots/py3_starter/MyBot.py3" \
  "python3 bots/py3_starter/MyBot.py3"
```

The engine writes the replay and opens a browser page.

The engine sets the bot work dir to the bot file dir.
