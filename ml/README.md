# AlphaStarZero: self-play loop

Train an Ants bot the AlphaZero way: the bot plays itself, the trainer
learns from the games, the challenger replaces the champion only when
it wins. Three phases per generation, borrowed from the autoresearch
loop (fixed budget, recorded score, keep-the-winner).

## Why not vanilla AlphaZero

| AlphaZero assumption | Ants reality | Adaptation |
|---|---|---|
| small discrete actions | `5^N` joint moves | factorized per-ant policy, shared weights |
| full observability | fog of war, simultaneous moves | local cues + memory-less greedy; history/LSTM later |
| fast simulator + MCTS | 1000 ms turn, subprocess engine | MCTS over *abstract* orders (raid hill, gather food), not moves; neural net proposes, symbolic resolver disposes |
| win/loss reward | score + survival + hills | terminal outcome + dense shaping, both in `ml/rewards.py` (landed); learned value head later |

## Generation loop (each generation = one commit)

1. **Self-play.** Champion + challenger play K games through
   `league/play.py` (logged to `league/games.jsonl`, so ratings stay
   honest). Positions, sampled actions, and returns go to a replay
   buffer; keep several past generations to avoid cycles (league pool
   gives opponents for free).
2. **Train.** Policy-gradient step on `LinearPolicy` (REINFORCE with a
   running baseline now; value head + PPO when the encoder grows).
   Rewrites `bots/alphastarzero/weights.json` — nothing else.
3. **Promote.** Challenger vs champion duel set. Win-rate above
   threshold → challenger becomes champion (commit). Else keep
   champion, try new hyperparams. Same keep-the-winner rule as
   `autoresearch/docs/PROGRAM.md`.

## Scaling path

- v0 (this branch): linear over 4 cues, REINFORCE, food-seeking +
  collision-free baseline. Proves data → train → promote turns.
- v1: local window encoder (e.g. 9x9 x channels: water, food, own,
  enemy, hill, pheromone) + small CNN, value head.
  (encoder landed: `features.local_window`, radius 4 default; CNN head next)
- v2: MCTS over abstract group orders with the value head guiding
  search; per-ant policy executes the chosen assignment.

## Reward system (`ml/rewards.py`, landed)

Pure function of the engine replay plus the bot's decision log:

- **Source of truth**: the replay records food pickups (gatherer +
  turn), every ant's full order string, and hill raze turns.
- **Decisions**: the bot appends `{turn, loc, dest, action, cues}`
  per ant per turn, only when `AZ0_RECORD_DIR` is set (self-play
  only; outside the bot tree so league hashing stays clean).
- **Credit** (`compute_returns`): food/kills go to the ants within
  gather/attack radius (`spawnradius2`/`attackradius2` from the
  replay); deaths hit the dead ant; hills split across the team's
  ants that turn; outcome (`WIN=25 / LOSS=-25 / DRAW=0`) discounts
  back to every decision at `GAMMA=0.99`. Dense events are
  same-turn; the outcome carries the long horizon.
- **Trajectories**: rebuilt from initial tile + order string, so no
  simulator is needed for credit assignment.

Try it: run a wired self-play game with `AZ0_RECORD_DIR` set, then
price its decisions with `rewards.compute_returns(game, 0, records)`.

## Environment

Training needs torch in the repo venv (CPU is fine; inference is one
linear layer):

```sh
uv pip install --python .venv/bin/python numpy torch \
  --index-url https://download.pytorch.org/whl/cpu
```

Runtime inference uses the same venv interpreter: league `bind()`
rewrites a leading `python` token to it, so `import torch` works in
rated play. (Raw `tools/playgame.py` calls need an absolute
interpreter path for the same reason.)
