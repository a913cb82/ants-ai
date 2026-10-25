# AlphaStarZero bot (runtime)

Engine-playable student. One shared linear policy, per ant, greedy.

## Files

| File | Role |
|---|---|
| `main.bot` | manifest: `python MyBot.py` (league rebinds `python` to `.venv/bin/python`) |
| `MyBot.py` | engine loop: reserve-then-order, 10 ms time guard |
| `features.py` | per-ant cues: `passable, food, threat, crowd` |
| `model.py` | `LinearPolicy` (torch) + greedy `choose()` |
| `weights.json` | current student parameters (rewritten by the trainer) |
| `ants.py` | protocol wrapper, copied from `bots/py3_starter` |

## Why linear first

AlphaZero assumes a small discrete action space and full observability.
Ants has neither: the joint move is `5^N` and the map is partially
observed. So v0 factorizes: one shared per-ant policy conditioned on
local cues, with collisions resolved symbolically (reservation set).
The loop this enables — self-play games, policy-gradient step,
promote-if-better — is the AlphaZero skeleton; the network grows
(local CNN windows, value head, MCTS over abstract orders) only after
the loop turns end to end.

## Turn budget

`choose()` is one 4-wide dot product per action plus a water mask:
microseconds per ant. torch import happens once at process start,
inside the 3000 ms loadtime. No MCTS in the turn path yet.
