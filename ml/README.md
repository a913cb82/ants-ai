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

CNN policy + PPO loop landed (clipped surrogate, shared-trunk value
head, per-minibatch standardized advantages; Monte-Carlo targets,
no GAE — see `ml/algorithm.py`). First automated generations ran
clean (trained, evaluated, correctly held the champion on sub-bar
evals). Open: learning-signal validation over several generations,
exploiter phases, GAE if the value baseline proves insufficient.

## Experiment log

2026-10-25, 1-hour perf + hyperparameter budget (4 arms x 4 gens,
60 turns, train 4 / eval 10, seed 7, paired):
- Wave 1 was VOID: parallel games caused turn-1 engine timeouts
  (`game_length 0`, both sides `timeout`), which log zero rows and
  score 0-0. Empty batches trained on nothing; "draws" were timeouts.
- Fix: engine `--turntime` 1s->5s, `--loadtime` 3s->15s (free when
  healthy), one automatic retry on `game_length 0` (`game_if.play`
  returns a `retried` flag), default workers 12->8. Wave 2:
  zero double-timeouts, full batches (800-1100 rows/gen).
- KL landed at ~0.01/epoch for lr=1e-3 (healthy band) and ~0.01 for
  lr=3e-3: both safe, 1e-3 stays the default. lr=3e-3 showed the
  fastest critic learning (v_loss 1.0->0.74); no eval separation.
- Headline bottleneck: mirror evals on tutorial1 draw ~90%
  (0W/10D typical), so n=10 evals cannot separate knobs or promote.
  Next levers are draw-rate, not step size: longer turns, second map,
  or score-margin eval metric. gamma=0.99 raised train returns
  (+50%) with no eval change — consistent with draws, not learning.

## Performance (same day, inference + training throughput)

150-ant turn: ~40ms -> 7.5ms greedy / 11ms sampled.
- features.snapshot(): five board scans once per turn, not per ant;
  water cached in do_setup (static all game) -> zero engine calls.
- One batched forward per turn (1.2ms vs 6-8ms serial).
- legal_mask vectorized via advanced indexing (49us -> 10us/ant).
- Window buffer is numpy + cached sight-circle offsets.
- No row materialization when not recording.
8-game generation at workers=4: 21.7s -> 7.0s via single-thread
bot env (OMP/MKL/OPENBLAS=1 in game_if; torch.set_num_threads(1)
in the bot). Training compute untouched: 86ms/epoch is noise next
to data cost. Fixed cost left: torch cold start ~1.3s/bot/game
(engine spawns fresh interpreters; out of our hands).

## Pro calibration (2026-10-25; toolchains installed)

Only pas11 runs as-ported; the rest needed compilers (apt: default-jdk
+ build-essential + mono-complete) and all now build except flagcapper
(needs -Wno-implicit-function-declaration, applied to its .sh).
Long games, all rank-stabilized endings, none hitting turn budgets:
- xathis 3-0 fourmidable, tutorial1, 165 turns.
- greentea 3-0 lazarant, generated gen2p_05, 135 turns.
- flagcapper 3-0 starter, tutorial1, 24 turns (fast C bot).
- xathis 3-0 AZ0 (early champion), tutorial1, 30 turns.
- pas11 is broken as an opponent: crashes on first enemy contact
  (3-arg destination call its bundled ants.py lacks); also too slow
  (~1000ms/turn, timed out twice). Not a sparring partner.
Lesson: competent games resolve at 130-165 turns, so default turns
100 -> 150 (covers the resolution range; 300-turn endgame evals stay
periodic). xathis is the external measuring stick.
