# Methods

These numbers are binding. The harness sets them. No flag changes the
budget, the maps, the seeds, or the selection.

## Budget

One iteration has 8 games for each candidate commit:

| Part | Count | Maps | Time |
|---|---|---|---|
| Duels | 5 | 5 different 2p maps | about 5 s each |
| FFA | 3 | one map for each size in one set | 20 to 90 s each |
| Total | 8 | all different in one iteration | about 1 to 4 min |

- The FFA sizes are one of two fixed sets: `{4, 6, 10}` or `{5, 7, 8}`.
  The harness picks the set from the bot id, so a partly played budget
  resumes with the same set.
- The candidate is a fresh bot entry: a new commit with changed bot code.
  A commit that changes the bot directory is a new bot id. A docs-only
  commit keeps the old id.
- A commit cannot play more than this budget. A completed commit plays
  no game on a second run. A run stopped part-way plays the games that
  remain.
- Every game goes to `league/games.jsonl` and updates `ratings.json`.

## Score

The score is the snapshot `lb = mu - 3 * sigma` at the end of the
budget. The model is OpenSkill BradleyTerryFull. A high score is good.
The harness appends the score to `autoresearch/docs/PROGRESS.jsonl` and
never changes that line. The file is append-only. The champion is the
best recorded score for the current budget.

The harness prints the candidate's live `mu`, `sigma`, and `lb` after
each game, then the recorded score at the end.

A bot keeps playing after its iteration, so its live rating moves.
Compare recorded scores, not live ratings.

## Progress file

`autoresearch/docs/PROGRESS.jsonl` holds one JSON object per completed
iteration. The object has these keys:

| Key | Value |
|---|---|
| `date` | the day of the run |
| `bot` | the bot id (`path-sha`) |
| `mu` | the rating mean |
| `sigma` | the rating deviation |
| `lb` | `mu - 3 * sigma` |
| `games` | the number of games in the budget |
| `champion` | the best bot id before this line, or `null` |
| `budget` | the budget tag (`duels=5,ffa=3,turns=1000`) |

Rows with an older `budget` stay in the file. The harness ignores
them for the champion.

## Result order

`result` lists the field best first. `result[0]` is rank 1, the winner
of a duel. A high score wins. Status breaks ties (`ok` before `crashed`
and `timeout`). In an FFA game the index in `result` is the rank.

## Selection

- A duel: the candidate is in the game. The opponent has the best
  information score. The top 3 opponents are eligible.
  In 20 percent of duels the harness picks one of the top 3 at random.
- An FFA game: the candidate is in the field. The harness fills the
  other slots by the same information score.
- The FFA sizes come from one fixed set per candidate: `{4, 6, 10}` or
  `{5, 7, 8}` (see Budget).
- The information score is `predict_draw + 0.02 * sum(sigma)`.
- The maps are random and different in one iteration.
- The slots and both seeds are random. The record keeps the seeds.
- The harness does not pair games. The rating model accounts for the
  strength of the opponent. Map variety is more important than a repeat
  of the seeds or the slots.

## Engine settings

| Flag | Value |
|---|---|
| `--turns` | 1000 |
| `--turntime` | 1000 ms |
| `--loadtime` | 3000 ms |

The engine under `tools/` must match branch `main`. The iteration
fails when it does not.

## Branch

Branch `main` must be an ancestor of `HEAD`. The iteration fails when
it is not. Merge `main` into `autoresearch/main` at the start of each
iteration.

The loop pushes its own branch after the log commit:
`git push origin autoresearch/main`. The loop never pushes `main`
(which it only merges in) and never pushes tags. A failed push keeps
the commits in place. The loop retries the push at the next log
commit.

## Commands

```sh
# play the budget and show the score
.venv/bin/python autoresearch/iteration.py --bot autoresearch/bot/main.bot

# show the field (live ratings)
.venv/bin/python league/board.py

# push the iteration (after the log commit)
git push origin autoresearch/main
```

## Replays

Each game writes `autoresearch/runs/<sha>/<phase>_<n>/0.replay`.
The harness removes the oldest replays when the store is larger than
`--max-replay-gb` (5 GB). It keeps the replays of the current
candidate. The harness removes the oldest worktrees when the store is
larger than `--max-worktree-gb` (1.0 GB).
