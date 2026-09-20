# Autoresearch program

You are a researcher. You improve one ants bot. You work alone.
Do not ask the human anything. Commit, play, measure, and repeat.

## Setup

Do this once for each run.

1. Activate the venv: `source .venv/bin/activate`
2. Check the tree: `git status`. The tree must be clean before you play.
3. Read `autoresearch/README.md`, `autoresearch/docs/METHODS.md`,
   `autoresearch/docs/IDEAS.md`, `autoresearch/docs/STRATEGY.md`,
   `autoresearch/docs/CEILING.md`, and the end of
   `autoresearch/docs/WORKLOG.md`.
4. Work on branch `autoresearch/main`. If the branch does not exist,
   run `git checkout -b autoresearch/main`.
   The seed commit has the tag `champion/main`.
5. The bot is in `autoresearch/bot/`. The file `main.bot` starts the bot.
   The seed is a copy of the py3 starter.

## Scope

You can edit:

- `autoresearch/bot/` (the bot)
- `autoresearch/docs/` (the notes)

You cannot edit:

- `tools/` (the engine)
- `league/` (the league)
- `autoresearch/iteration.py` (the harness)
- `tests/`, `pyproject.toml`, or other bots

Rules:

- Use the Python standard library and the packages in the venv.
  Do not run pip.
- One turn must finish in 1000 ms. A slow bot loses on time.
  The load time is 3000 ms.
- Play every game through `autoresearch/iteration.py`.
  A game outside the harness is forbidden.
- Read the code of the other bots. Do not edit their code.

## One iteration

1. Pick one idea from `autoresearch/docs/IDEAS.md` or from research.
2. Start from the champion:
   `git checkout champion/main -- autoresearch/bot`
3. Edit `autoresearch/bot/`.
4. Commit the change:
   `git add autoresearch/bot && git commit -m "exp: <idea>"`
5. Play the budget:
   `python autoresearch/iteration.py --bot autoresearch/bot/main.bot`
6. Read the score. The score is `lb = mu - 3 * sigma`.
7. If `lb` is more than the `lb` of the champion, move the tag:
   `git tag -f champion/main`.
   If not, keep the commit and start the next idea from the champion.
8. Add one entry to `autoresearch/docs/WORKLOG.md`. Commit the entry.
9. Go to step 1. Do not stop.

## Budget

The harness sets the budget for each commit:

- 16 duels. Each duel uses a different 2p map.
- 7 FFA games. One game for each size from 4 to 10.

Every game goes to `league/games.jsonl`. A commit cannot play more.
A second run of one commit plays no game.
Use `--dry-run` to see the rest of the budget and the score.

## Selection

The harness selects the maps, the slots, the seeds, and the opponents.
You do not select them.

- A duel: the opponent has the best information score.
- An FFA game: the candidate is always in the field. The other slots
  have the best information score.

The map, the slot, and the seeds are random. This keeps the test honest.
Do not try to control the selection.

## Bold work

A local optimum is the main risk. Obey these rules.

- If two iterations in a row do not beat the champion, the next
  iteration is bold.
- Start a bold iteration with research, not with code:
  1. Search the web for ants strategies and for other AI Challenge bots.
  2. Read the bot code in this repo.
  3. Write the sources and the notes in `autoresearch/docs/RESEARCH.md`.
  4. Pick a different design or a different idea group.
     Do not change one number.
- Give a bold line at least 3 iterations before you judge it.
  A new design starts weak.
- After about 10 iterations, or when you are stuck, start again from a
  different bot (for example `bots/pas11`). Give that line at least
  3 iterations.
- The champion is the best bot from any line. Never discard the best
  bot of a line.

## Errors

- A crash is data. Read the replay and the log.
  If the error is small, repair it and play again.
- If the harness says "duplicates a rated bot", change the code.
- If the harness says "tree is dirty", commit first.
- After 3 failed repairs for one idea, drop the idea and write the reason.

## Analysis

- `python league/board.py` shows the field. The `lb` column is the score.
- `python autoresearch/iteration.py --dry-run` shows the budget and the
  score.
- The replays are in `autoresearch/runs/<sha>/`.
  Read them to find errors.
- Read `autoresearch/docs/CEILING.md` before you work on a large gain.
