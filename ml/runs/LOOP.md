# LOOP — pausing and resuming the AZ mirror run

The run is indefinite: one tick plays one game; every 16 scoring games
runs a PPO micro-batch. If you are resuming, read State then Resume
and go.

## State (live)

- Branch: `ml/alphastarzero`. Repo: `/home/acbraith/projects/ants-ai`.
  Venv: `.venv/bin/python` (Python 3.12, torch CPU). Run all
  commands from the repo root.
- Archive: `ml/archive/`. `live/weights.json` (the live policy) +
  `live/opt.json` (its Adam state) + `live/pending/` (unapplied bank,
  one shard per tick). `state.json` holds `{tick, next_tick, micro}`
  and the tick counter never reuses numbers.
- Rewards = one diet (`rewards.scales()`: hills ±10, food 0.01,
  everything else 0); dashboard = pure-AZ board
  (`h0/training/behavior/games/alerts/mtime`).
- Base command (single-threaded first, no `--concurrency`):
  `.venv/bin/python ml/selfplay.py --archive ml/archive
  --maps <map...> --turns 250 --temperature 1.0 --entropy-beta 0.01
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
