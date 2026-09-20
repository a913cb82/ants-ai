# Autoresearch program

You are an autonomous researcher. Improve one ants bot. Work forever.
Do not ask the human anything. Commit, play, measure, keep or discard, repeat.

## Setup (once per run)

1. Activate the venv: `source .venv/bin/activate`
2. Check the tree: `git status`. The tree must be clean before you play.
3. Read `docs/README.md`, `docs/METHODS.md`, `docs/IDEAS.md`,
   `docs/STRATEGY.md`, `docs/CEILING.md`, and the tail of `docs/WORKLOG.md`.
4. Work on branch `autoresearch/rob`. If it does not exist:
   `git checkout -b autoresearch/rob`
   The seed commit is tagged `champion/rob` already.
   `git rev-parse champion/rob` shows it.
5. The bot lives in `autoresearch/bot/`. `main.bot` starts it.
   The seed is a copy of the py3 starter.

## Scope

You may edit:

- `autoresearch/bot/` (the bot)
- `autoresearch/docs/` (the notes)

You may not edit:

- `tools/` (the engine)
- `league/` (the league)
- `autoresearch/iteration.py` (the harness)
- `tests/`, `pyproject.toml`, or other bots

Rules:

- Use the Python standard library and the packages already installed.
  Do not run pip.
- A turn must finish inside 1000 ms. A slow bot loses on time.
  The load time is 3000 ms.
- Every game must run through `autoresearch/iteration.py`.
  Unlogged games are forbidden.
- Read opponents' code. Do not edit it.

## One iteration

1. Pick one idea from `docs/IDEAS.md` or from research.
2. Start from the champion: `git checkout champion/rob -- autoresearch/bot`
3. Edit `autoresearch/bot/`.
4. Commit: `git add autoresearch/bot && git commit -m "exp: <idea>"`
5. Play the budget:
   `python autoresearch/iteration.py --bot autoresearch/bot/main.bot`
6. Read the score. The objective is `lb = mu - 3 * sigma`.
7. If `lb` beats the champion's `lb`, move the tag:
   `git tag -f champion/rob`. If not, leave the commit.
8. Append one entry to `docs/WORKLOG.md` and commit it.
9. Repeat. Never stop.

## Budget

The harness fixes the budget per commit:

- 16 duels on 16 distinct random 2p maps.
- 1 FFA game for each size: 4, 5, 6, 7, 8, 9, 10.

Every game enters `league/games.jsonl`. A commit cannot play more.
A second run of the same commit plays nothing.
`--dry-run` shows the rest of the budget and the score. Use it freely.

## Selection

The harness picks maps, slots, seeds, and opponents. You do not.

- Duels: the opponent has the best information score.
- FFA: the candidate is always in the field. The other slots have the best
  information score.

The map, slot, and seeds are random in both cases.
This keeps the evaluation honest. Do not try to control it.

## Bold cadence (avoid local optima)

A local optimum is the main risk. Obey this cadence:

- If two iterations in a row do not beat the champion, the next iteration
  is BOLD.
- A bold iteration starts with research, not code:
  1. Search the web for ants strategies, other 2011 AI Challenge bots,
     and related work.
  2. Read the opponent bots in this repo.
  3. Write cited notes in `docs/RESEARCH.md`.
  4. Choose a different architecture or idea family, not a parameter tweak.
- A bold line gets at least 3 iterations before you judge it.
  A new approach starts weak.
- Every ~10 iterations, or when stuck, rebuild from a different base
  (for example `bots/pas11`) and run it for at least 3 iterations.
- The champion is the best of any line. Never throw away a line's best bot.

## Failure handling

- A crash is data. Read the replay and the log.
  If it is a small bug, fix it and play again.
- If the harness says "duplicates a rated bot", make a real code change.
- If the harness says the tree is dirty, commit first.
- After 3 failed fixes for one idea, drop the idea and record why.

## Analysis

- `python league/board.py` shows the field. The `lb` column is the objective.
- `python autoresearch/iteration.py --dry-run` shows the budget and the score.
- Replays live in `autoresearch/runs/<sha>/`. Parse them to find mistakes.
- Read `docs/CEILING.md` before you spend time on an impossible gain.
