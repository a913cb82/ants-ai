# AlphaStarZero: self-play loop

Train an Ants bot the AlphaZero way: mirror self-play, policy-gradient
updates, scripted promotion. No external opponents, no human judgment.

## Why not vanilla AlphaZero

| AlphaZero assumption | Ants reality | Adaptation |
|---|---|---|
| small discrete actions | `5^N` joint moves | factorized per-ant policy, shared weights, symbolic collision resolution |
| full observability | fog of war, simultaneous moves | local 6-channel window, masked to the ant's sight circle |
| fast simulator + MCTS | 1000 ms turn, subprocess engine | no search; CNN proposes, masks dispose |
| win/loss reward | score + survival + hills | dense shaping + terminal outcome, both discounted (`ml/rewards.py`) |

## Architecture (clean split)

| Layer | Owns | Must not know |
|---|---|---|
| `bots/alphastarzero/model.py` | network shape, masking, act/sample, save/load | game, training |
| `bots/alphastarzero/features.py` | actions/offsets, window encoding | policy, training |
| `ml/grid.py` | toroidal math (stdlib only) | everything else |
| `ml/game_if.py` | engine games, staging, replay/record formats | torch |
| `ml/rewards.py` | (game, records) → discounted returns | torch, engine |
| `ml/algorithm.py` | REINFORCE step on masked log-probs | ants, replays |
| `ml/archive.py` | population, payoff matrices, PFSP, Nash, Wilson | torch, engine |
| `ml/train.py` / `ml/evaluate.py` | training loop / eval duels | promotion, files |
| `ml/selfplay.py` | wiring + scripted promotion | (thin) |

Policy shape swaps touch exactly one file (`model.py`); algorithm
swaps touch one file; the game interface never imports torch.

## Generation loop (each generation = fully automated)

1. **Sample opponents** from the eval matrix, PFSP-lite: mostly the
   opponents that beat the champion, plus a mirror fraction. Never
   anything outside the population.
2. **Train.** Challenger (champion copy) plays both slots, records
   `{turn, loc, dest, action, window, legal}`, prices with
   `rewards.compute_returns`, REINFORCE step (standardized
   advantages, persistent Adam, grad clip, entropy bonus).
3. **Evaluate.** Greedy duels, alternating slots. Promotion needs
   both: Wilson lower bound on the win rate clears 0.5 AND Nash mass
   ≥ champion's. Draws count half. Train games never vote.
4. **Publish** (only on promotion): champion pointer, rated
   `weights.json`, git commit.

```sh
.venv/bin/python ml/selfplay.py --train-games 4 --eval-games 20 \
  --turns 50 --archive ml/archive --no-commit   # dry run
```

`ml/archive/` (gitignored) holds every checkpoint, both matrices, and
the last report. `bots/alphastarzero/weights.json` holds only the
current champion — the rated phenotype, and the only weights in git.

## Reward system (landed)

- **Source of truth**: the replay (food gatherer + turn, full order
  strings, hill raze turns) plus the bot's decision log.
- **Credit**: food → adjacent ants (`0 < d2 <= spawnradius2`; the ant
  ON food gathers nothing per `nearby_ants`); kills → ants within
  attack radius (`0 < d2`); deaths → the dead ant; raze → the ant on
  the hill; lost hill → team-shared. Every event splits across its
  credited ants; one food is worth `FOOD` total.
- **Discount** (`GAMMA=0.97`, `WIN/LOSS=±5`): everything, uniformly —
  dense awards walk back along the credited ant's replay path, team
  awards and outcome reach every earlier decision.
- **Diagnose**: `rewards.decompose(game, me, records)` shows
  undiscounted mass per category — read it before tuning magnitudes.

## Population (AlphaStar-shaped, our scale)

- Frozen checkpoints + manifest; train matrix (diagnostic) vs eval
  matrix (canonical). Laplace prior: unplayed reads as 0.5.
- PFSP-lite sampling and Nash mixture read eval only.
- Every Nth generation can be an exploiter (fresh init, trains only
  against the champion) instead of a champion copy.

## Status

CNN policy + full loop landed; first automated generation ran clean
(trained, evaluated, correctly held the champion on a sub-bar eval).
Open: learning-signal validation over several generations, exploiter
phases, value head / PPO when REINFORCE plateaus.
