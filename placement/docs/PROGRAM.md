# Placement program

You are a researcher. You improve `select_next_game`. You work alone.
Do not ask the human anything. Commit, evaluate, measure, and repeat.

## Setup

1. Read `placement/AGENTS.md`, `placement/docs/PROGRAM.md`,
   `placement/strategy.py`, `placement/evaluate.py`, and
   `placement/docs/STRATEGY.md`, `IDEAS.md`, `PROGRESS.jsonl`,
   plus the tail of `placement/docs/WORKLOG.md`.
2. Work on branch `placement/main`. Merge `main` at each iteration
   start. Never commit to `main`. Never push `main`.
3. The strategy is `select_next_game(bot, ratings, budget_left)`
   in `placement/strategy.py`. It returns opponent ids.
   Size is `len(return) + 1`. Numbers are in `placement/AGENTS.md`.

## Scope

Edit `placement/strategy.py`, `placement/candidates/`, and docs notes.
Never edit `placement/evaluate.py`. Use `.venv/bin/python`.
The strategy sees only `mu`, `sigma`, `budget_left`. No `mu_true`.
It must be deterministic and fast (~10k calls per full run).

## Goal

Maximize corr(recorded mu, mu_true) over 1000 bots, averaged over
seeds 0 to 4. Higher wins. Champion is the highest mean correlation.
Correlation grades orders, not levels: the loop keeps champions by
comparison, so rank truth beats level truth. Doubt shuffles ranks
even when estimates sit near truth.

## One iteration

1. `git checkout placement/main && git merge main`.
2. Pick one idea from `placement/docs/IDEAS.md`.
3. Edit `placement/strategy.py` (or one `candidates/<name>.py` file,
   promoted by copy on a win).
4. Commit: `git add placement && git commit -m "exp: <idea>"`.
5. Quick check:
   `.venv/bin/python placement/evaluate.py --bots 200 --seed 0`.
6. Full score:
   `for s in 0 1 2 3 4; do .venv/bin/python placement/evaluate.py --bots 1000 --seed $s; done`.
   Score is the mean of the 5 means. Report all 5.
7. Append one line to `placement/docs/PROGRESS.jsonl`:
   `date`, `commit`, `corr`, `champion` (best prior commit or null).
   `corr` is the mean correlation over seeds 0 to 4. Never edit old lines.
8. Retag: `git tag -f champion/placement` on a new best, else on the
   best row's commit. Tags stay local. Keep every commit.
9. Log one `WORKLOG.md` entry. Commit notes with
   `git commit -m "log: <idea>"`.
10. `git push origin placement/main`. Repeat. Do not stop.

## Notes

Budget is 30 slots per bot, sizes 2 to 10, harness clips oversize and
`[]` ends early. Two misses in a row force a bold idea from research.
Record bold lines 3 iterations before judgement. See `IDEAS.md`.

## File map

Paths are relative to `placement/`.

| Path | Role |
|---|---|
| `docs/PROGRAM.md` | operating instructions (start here) |
| `AGENTS.md` | fixed numbers (binding spec) |
| `docs/PROGRESS.jsonl` | scores, one line per iteration |
| `docs/WORKLOG.md` | one entry per iteration |
| `docs/IDEAS.md` | doctrine and idea list |
| `docs/STRATEGY.md` | current champion only |
| `candidates/` | alternates, run with `--strategy` |
| `strategy.py` | the strategy under test |
| `evaluate.py` | the harness (scores MSE; do not edit) |
| `archive/mae-round/` | prior MAE round record (read-only) |
