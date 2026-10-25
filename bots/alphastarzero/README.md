# AlphaStarZero bot (runtime)

Engine-playable student. One shared CNN policy, per ant, greedy in
rated play and temperature-sampled in self-play.

## Files

| File | Role |
|---|---|
| `MLBot.bot` | manifest: `python MLBot.py` (league rebinds `python` to `.venv/bin/python`) |
| `MLBot.py` | engine loop: `MLBot.py [weights]` override, `AZ0_TEMPERATURE` sampling, `AZ0_RECORD_DIR` logging |
| `features.py` | actions/offsets, `local_window` (6-channel relative 1-hot, LoS-masked) |
| `model.py` | `CNNPolicy` (6ch window → 5 logits, ~6k params), water/food masking, act/sample, save/load |
| `weights.json` | champion parameters (rated phenotype; rewritten only on promotion) |
| `ants.py` | protocol wrapper, copied from `bots/py3_starter` |

## Decision path (per ant, per turn)

1. Encode the 6-channel window (water, own ant/hill, enemy ant/hill,
   food), masked to the ant's sight circle.
2. Mask water and visible-food destinations (the engine ignores moves
   into both) plus tiles reserved by earlier ants this turn.
3. Greedy argmax (rated) or softmax sample (self-play). Reservations
   make collisions impossible by construction; the engine resolves
   anything left.

## Record rows (self-play only)

`{turn, loc, dest, action, window, legal}` — everything the trainer
needs and nothing else. `legal` is the exact mask acted with, so the
learner scores decisions under the behavior distribution. No cues,
no history, no reuse across turns.

## Turn budget

Two small convolutions over 9×9 plus a linear head: microseconds per
ant on CPU. No search in the turn path. torch imports once at process
start, inside the 3000 ms loadtime.
