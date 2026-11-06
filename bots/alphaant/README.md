# AlphaAnt bot (runtime)

Engine-playable student. One shared CNN policy, per ant, greedy in
rated play and temperature-sampled in self-play.

## Files

| File | Role |
|---|---|
| `AlphaAnt.bot` | manifest: `python AlphaAnt.py` (league rebinds `python` to `.venv/bin/python`) |
| `AlphaAnt.py` | engine loop: `AlphaAnt.py [weights]` override, `AA_TEMPERATURE` sampling, `AA_RECORD_DIR` logging |
| `features.py` | actions/offsets, `local_window` (10-channel current + 3-channel T-1 memory, LoS-masked) |
| `model.py` | `CNNPolicy` (13ch window → 5 logits + 1 value, base ~6k params), water/food masking, act/sample, save/load |
| `weights.json` | rated snapshot of the live policy (copied from `ml/archive/live/weights.json`, not trained here) |
| `ants.py` | protocol wrapper, copied from `bots/py3_starter` |

## Decision path (per ant, per turn)

1. Encode the 10-channel current window (water, own ant/hill, enemy
   ant/hill, food, own-sight team flag, force-ratio, enemy-dist,
   stall), masked to the team's sight circles, plus 3 T-1 memory
   channels (prev own ant, prev enemy ant, prev self marker).
2. Mask water and visible-food destinations (the engine ignores moves
   into both) plus tiles reserved by earlier ants this turn.
3. Greedy argmax (rated) or softmax sample (self-play). Swap/cycle
   resolution + reservation make collisions impossible by
   construction; the engine resolves anything left.

## Record rows (self-play only)

`{turn, loc, dest, action, intent, blocked, window, legal}` — everything the trainer
needs and nothing else. `legal` is the exact mask acted with, so the
learner scores decisions under the behavior distribution. `window` is
the full 13-channel frame (10 current + 3 history).

## Turn budget

Two small convolutions over 9×9 plus a linear head: microseconds per
ant on CPU. No search in the turn path. torch imports once at process
start, inside the 3000 ms loadtime.
