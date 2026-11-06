# AlphaAnt: self-play loop

> **Pure AZ (live):** one-policy mirror self-play — latest vs latest,
> no league, no promotion gate. See `ml/runs/LEAGUE.md` (doctrine)
> and `ml/runs/LOOP.md` (pause/resume). The generation-league
> history below is frozen record (retired 2026-11-01) — `ml/runs/`
> keeps the receipts.

Train an Ants bot the AlphaZero way: mirror self-play, PPO updates,
continuous training. No external opponents, no human judgment.

## Why not vanilla AlphaZero

| AlphaZero assumption | Ants reality | Adaptation |
|---|---|---|
| small discrete actions | `5^N` joint moves | factorized per-ant policy, shared weights, symbolic collision resolution |
| full observability | fog of war, simultaneous moves | local 13-channel window (10 current + 3 T-1 memory), masked to team sight |
| fast simulator + MCTS | 1000 ms turn, subprocess engine | no search; CNN proposes, masks dispose |
| win/loss reward | score + survival + hills | dense shaping + terminal outcome, both discounted (`ml/rewards.py`) |

## Architecture (clean split)

| Layer | Owns | Must not know |
|---|---|---|
| `bots/alphaant/model.py` | network shape, masking, act/sample, save/load | game, training |
| `bots/alphaant/features.py` | actions/offsets, window encoding | policy, training |
| `ml/grid.py` | toroidal math (stdlib only) | everything else |
| `ml/game_if.py` | engine games, staging, replay/record formats | torch |
| `ml/rewards.py` | (game, records) → discounted returns (hills-only diet + 0.01 food) | torch, engine |
| `ml/algorithm.py` | PPO step on masked log-probs | ants, replays |
| `ml/archive.py` | game/update logs, live weights + Adam, pending bank | torch, engine |
| `ml/train.py` | training loop (PPO micro-batch) | league, files |
| `ml/selfplay.py` | mirror loop wiring (latest vs latest) | (thin) |

Policy shape swaps touch exactly one file (`model.py`); algorithm
swaps touch one file; the game interface never imports torch.

## Mirror loop (live — each tick = one game, fully automated)

1. **Play.** `main` plays `main` (any seat count, per the map).
   Every seat records
   `{turn, loc, dest, action, intent, blocked, window, legal}`, prices with
   `rewards.compute_returns` (hills-only diet: raze +10 / lost −10,
   food 0.01 trickle, everything else 0).
2. **Bank.** Scoring games bank PPO rows; scoreless games (all-zero
   returns) log to history but bank nothing and don't advance the
   cadence.
3. **Train.** PPO micro-batch every 16 scoring-game completions
   (`MICRO_BATCH=16`), oldest whole games first up to 65536 rows.
   Background thread on a weights snapshot (staleness ≤ 1 update).

```sh
.venv/bin/python ml/selfplay.py --archive ml/archive \
  --turns 250 --temperature 1.0 --entropy-beta 0.01 \
  --seed <n> --ticks <n>   # negative = forever
```

`ml/archive/` (gitignored) holds `games.jsonl`, `updates.jsonl`,
`state.json`, and `live/` (live `weights.json` + `opt.json` + pending
bank). `bots/alphaant/weights.json` holds a rated snapshot of live —
the only weights in git.

## Retired league (frozen record — generation loop, pre-2026-11-01)

1. ~~Sample opponents from the eval matrix (PFSP-lite).~~
2. ~~Train challenger (champion copy) on both slots.~~
3. ~~Evaluate: Wilson lower bound > 0.5 AND Nash mass ≥ champion's.~~
4. ~~Publish only on promotion: champion pointer + rated weights.~~

## Reward system (live: hills-only diet)

- **Source of truth**: the replay (food gatherer + turn, full order
  strings, hill raze turns) plus the bot's decision log.
- **Credit**: food → adjacent ants (`0 < d2 <= spawnradius2`) at 0.01
  trickle; raze → distance-scaled per ant
  (`amount * exp(-d2*ln10/100)`); lost hill → flat −10 per ant;
  kills / deaths / approach / terminal are 0. Scoreless (all-zero
  returns) games bank nothing.
- **Discount** (`GAMMA=0.97`): dense awards walk back along the
  credited ant's replay path. Terminal outcome is 0 under the diet.
- **Diagnose**: `rewards.decompose(game, me, records)` shows
  undiscounted mass per category — read it before tuning magnitudes.

## Population (retired — frozen record)

- ~~Frozen checkpoints + manifest; train/eval matrices; PFSP-lite;
  Nash mixture; exploiters.~~ League machinery deleted 2026-11-01
  (`ml/pfsp.py`, `ml/measure.py` gone). One live policy only.

## Status (live: pure mirror)

13-channel CNN policy (10 current + 3 T-1 memory) + PPO loop landed
(clipped surrogate, separate value trunk, frozen pre-update baseline
standardized over the micro-batch; Monte-Carlo targets, no GAE — see
`ml/algorithm.py`). Mirror ticks run clean (latest vs latest, update
every 16 scoring games). Open: decisive-rate slope, critic explained
variance, D4/entropy health — see `ml/runs/LEAGUE.md` falsifiers.

## History (frozen record — pre-2026-11-01 league era)

The 2026-10-25 experiment log (perf + hyperparameter waves, 30-gen
flat runs, critic probes, BC init, exploiter verdicts, pro
calibration, map-pool notes) was removed from HEAD — git history
keeps it (`git log -- ml/README.md`). Live questions are the
`ml/runs/LEAGUE.md` falsifiers, not the old generation gate.
