# LOOP — pausing and resuming the AZ mirror run

The run is indefinite: one tick plays one game; every 8th game runs a
PPO update. Training stopped for rebuilding (archive wiped 2026-11-01,
only `live/weights.json` + `live/opt.json` kept). If you are resuming,
read State then Resume and go.

## State (as of the pure-AZ switch)

- Branch: `ml/alphastarzero`. Repo: `/home/abrai/projects/ants-ai`.
  Venv: `.venv/bin/python` (Python 3.12, torch CPU). Run all
  commands from the repo root.
- Archive: `ml/archive/`, wiped. `live/weights.json` (the latest
  main policy) + `live/opt.json` (its Adam state) only.
  `state.json` starts at `{tick: 0, next_tick: 0, micro: 0}`.
- League code deleted: `ml/pfsp.py`, `ml/measure.py` gone; rewards =
  one diet (`scales()`); dashboard = pure-AZ board
  (`h0/training/behavior/games/game_total/alerts/mtime`).
- Base command (single-threaded first, no `--concurrency`):
  `.venv/bin/python ml/selfplay.py --archive ml/archive
  --maps <map...> --turns 150 --temperature 2.0 --entropy-beta 0.05
  --seed <n> --ticks <n>`

## Resume

1. Pre-flight: `git status` clean, no `selfplay.py` running,
   maps exist, `live/` + `state.json` present (continuity, not
   the old numbers).
2. Run the base command. Ctrl-C finishes the current tick, then
   stops; rerunning resumes (tick counter never reuses numbers).
3. Watch the board (`ml/dashboard.py --port 8090
   --archive ml/archive`): decisive rate, behavior means,
   training vitals. Doctrine + falsifiers: LEAGUE.md.

## Pause (how this file got written)

1. Ctrl-C the runner (finishes the tick); note `state.json` tick.
2. Update this file's State, commit.
