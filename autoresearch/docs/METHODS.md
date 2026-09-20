# Methods

These numbers are binding. The harness reads the defaults.
Change a number with a flag, not with an edit.

## Budget

One iteration has 23 games for each candidate commit:

| Part | Count | Maps | Time |
|---|---|---|---|
| Duels | 16 | 16 different 2p maps | about 5 s each |
| FFA | 7 | one map for each size 4, 5, 6, 7, 8, 9, 10 | 20 to 90 s each |
| Total | 23 | all different in one iteration | about 5 to 8 min |

- The candidate is a fresh bot entry: a new commit with changed bot code.
  A new commit is a new bot id.
- A commit cannot play more than this budget. A second run plays nothing.
- Every game goes to `league/games.jsonl` and updates `ratings.json`.

## Score

The score is `lb = mu - 3 * sigma`. The model is OpenSkill
BradleyTerryFull. A high score is good.
`board.py` shows `mu`, `sigma`, and `lb`.
The harness measures a commit one time.
The record keeps the score for a later comparison.

## Selection

- A duel: the candidate is in the game. The opponent has the best
  information score. The top 3 opponents are eligible.
  In 20 percent of duels the harness picks one of the top 3 at random.
- An FFA game: the candidate is in the field. The harness fills the
  other slots by the same information score.
- The information score is `predict_draw + 0.02 * sum(sigma)`.
- The maps are random and different in one iteration.
- The slots and both seeds are random. The record keeps the seeds.
- The harness does not pair games. The rating model corrects for the
  strength of the opponent. Map variety is more important than a repeat
  of the seeds or the slots.

## Engine settings

| Flag | Value |
|---|---|
| `--turns` | 1000 |
| `--turntime` | 1000 ms |
| `--loadtime` | 3000 ms |
| `--timeout` | 900 s for each game |

## Commands

```sh
# play the rest of the budget and show the score
.venv/bin/python autoresearch/iteration.py --bot autoresearch/bot/main.bot

# show the budget and the score. Play no game.
.venv/bin/python autoresearch/iteration.py --bot autoresearch/bot/main.bot --dry-run

# show the field
.venv/bin/python league/board.py
```

## Replays

Each game writes `autoresearch/runs/<sha>/<phase>_<n>/0.replay`.
The harness removes the oldest replays when the store is larger than
`--max-replay-gb` (0.5 GB). It keeps the replays of the current
candidate. The harness removes the oldest worktrees when the store is
larger than `--max-worktree-gb` (1.0 GB).
