# Methods

Binding numbers for the autoresearch loop. The harness reads these
defaults. Change them with flags, not with edits.

## Budget (per candidate commit)

| Games | Count | Maps | Cost |
|---|---|---|---|
| Duels | 16 | 16 distinct random 2p maps | ~5 s each |
| FFA | 1 per size | one random map for each size 4..10 | 20-90 s each |
| Total | 23 | all distinct within an iteration | ~5-8 min |

- The candidate is a commit. A fresh commit is a fresh bot id.
- A commit cannot play more than this budget. A second run plays nothing.
- Every game appends to `league/games.jsonl` and updates `ratings.json`.

## Objective

`lb = mu - 3 * sigma`, from the shared OpenSkill BradleyTerryFull model.
Higher is better. `board.py` prints `mu`, `sigma`, and `lb`.
A seed commit is measured once. Its score is kept for comparison.

## Selection

- Duels: candidate forced; opponent has the best information score
  `predict_draw + 0.02 * sum(sigma)`. The top 3 are eligible.
  A random pick among the top 3 takes 20% of games.
- FFA: candidate forced; the other slots are filled the same way.
- Maps: random and distinct inside one iteration.
- Slots and both seeds: random and logged.
- No pairing. Opponent strength is handled by the rating model.
  Map variety matters more than seed or slot repeats.

## Engine settings

| Flag | Value |
|---|---|
| `--turns` | 1000 |
| `--turntime` | 1000 ms |
| `--loadtime` | 3000 ms |
| `--timeout` | 900 s per game |

## Commands

```sh
# play the rest of the budget and print the score
python autoresearch/iteration.py --bot autoresearch/bot/main.bot

# show the budget and score, play nothing
python autoresearch/iteration.py --bot autoresearch/bot/main.bot --dry-run

# the field
python league/board.py
```

## Replays

Each game writes `autoresearch/runs/<sha>/<phase>_<n>/0.replay`.
The store is pruned oldest-first past `--max-replay-gb` (0.5 GB).
The current candidate's directory is protected. Worktrees are pruned
the same way past `--max-worktree-gb` (1.0 GB).
