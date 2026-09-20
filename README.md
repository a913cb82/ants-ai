# AntsAI

This repo plays the Ants game from the 2011 AI Challenge.
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

Play one game between two copies of the starter bot:

1. Run the engine with a map and two bot commands.
2. Store the replay outside `tools/`.
3. Open the replay in the visualizer.

Example:

```sh
python3 tools/playgame.py \
  --map_file tools/maps/example/tutorial1.map \
  --nolaunch --turns 100 --log_dir replays \
  "python3 bots/py3_starter/MyBot.py3" \
  "python3 bots/py3_starter/MyBot.py3"
```

Play the Pas11 bot against the starter bot:

```sh
python3 tools/playgame.py \
  --map_file tools/maps/example/tutorial1.map \
  --nolaunch --turns 100 --log_dir replays \
  "python3 bots/pas11/Pas11.py" \
  "python3 bots/py3_starter/MyBot.py3"
```

The engine sets the bot work dir to the bot file dir.
A bot finds its sibling `ants.py` with no extra path setup.

## Source

- `tools/` came from `vendor/tools.tar.bz2`. It was published on 22 Dec 2011.
- `bots/py3_starter/` came from `vendor/python3_starter_package.zip`. It was published on 29 Nov 2011.
- `bots/pas11/ants.py` is a copy of the starter `ants.py`.
