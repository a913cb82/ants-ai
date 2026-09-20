# Autoresearch program

You are a researcher. You improve one ants bot. You work alone.
Do not ask the human anything. Commit, play, measure, and repeat.

## Setup

Do this once for each run.

1. Read `autoresearch/README.md`, `autoresearch/docs/METHODS.md`,
   `autoresearch/docs/IDEAS.md`, `autoresearch/docs/STRATEGY.md`,
   `autoresearch/docs/CEILING.md`, `autoresearch/docs/PROGRESS.jsonl`,
   and the end of `autoresearch/docs/WORKLOG.md`.
2. Work on branch `autoresearch/main`:
   `git checkout autoresearch/main`. The loop merges `main` at step 1.
   `main` is read-only for you: never commit to it, never push it.
3. The bot is in `autoresearch/bot/`. The file `main.bot` starts the bot.
   `main.bot` is a one-line command; the engine runs it with the bot
   directory as the working directory.

## Scope

You can edit:

- `autoresearch/bot/` (the bot)
- `autoresearch/docs/` (the notes)

You cannot edit:

- `tools/` (the engine)
- `league/` (the league)
- `autoresearch/iteration.py` (the harness)
- `tests/`, `pyproject.toml`, or other bots

You can copy the code of another bot into `autoresearch/bot/`.
Do not edit another bot in its own directory.

Rules:

- Use `.venv/bin/python` for every command. Each command runs in a new
  shell, so an activated venv does not stay active.
- Make a fresh bot entry each iteration. Change the bot code and commit it.
  The harness counts games by bot id. An old entry cannot play again.
- Use only the Python standard library and the packages in the venv.
  Do not run pip.
- One turn must finish in 1000 ms. A slow bot loses on time.
  The load time is 3000 ms.
- Play every game through `autoresearch/iteration.py`.
  A game outside the harness is forbidden.
- `league/games.jsonl` is the game log. The harness appends to it.
  Do not edit it. Commit it with your notes.
- Read the code of the other bots. Do not edit their code.

## Goal

The goal is to maximize the iteration score. The score is
`lb = mu - 3 * sigma`, measured after the fixed budget of games.
The harness writes it to `autoresearch/docs/PROGRESS.jsonl` when the
budget ends. Every fresh bot gets 8 games, 5 duels and 3 FFA, against
fairly chosen opponents, so the comparison is fair. A bot's live
rating keeps moving after the iteration. The recorded score does not
move. The champion is the best recorded score for the current budget.

## One iteration

Each iteration must run a fresh bot entry. Change the bot code first.

1. Merge `main` into `autoresearch/main`:
   `git checkout autoresearch/main && git merge main`
   Resolve any conflict before you continue.
2. Pick one idea from `autoresearch/docs/IDEAS.md` or from research.
3. Choose the start. The champion is a safe start. An older bot or a
   new design is also allowed.
4. Edit `autoresearch/bot/`.
5. Commit the change:
   `git add autoresearch/bot && git commit -m "exp: <idea>"`
6. Play the budget:
   `.venv/bin/python autoresearch/iteration.py --bot autoresearch/bot/main.bot`
7. Read the score. The harness prints the score and adds one JSON line
   to `autoresearch/docs/PROGRESS.jsonl`. The champion is the best
   line for the current budget.
8. Compare the new score with the champion score:
   - Baseline (no row for this budget) or new best: point the tag at
     this commit: `git tag -f champion/main`.
   - Lower or equal: point the tag at the best row's commit:
     `git tag -f champion/main <sha in the best row's bot id>`.
   A missing tag is fine; the rule above rebuilds it. The tag is
   local: never push tags. Keep the commit in all cases. Start the
   next idea from the champion.
9. Add one entry to `autoresearch/docs/WORKLOG.md`. Commit the notes
   and the new games:
   `git add autoresearch/docs league/games.jsonl && git commit -m "log: <idea>"`
10. Push your branch:
    `git push origin autoresearch/main`
    You own this branch only; never push `main` or tags. A failed
    push is not a lost iteration. Keep the commits and push again at
    the next log commit.
11. Go to step 1. Do not stop.

## Budget

The harness sets the budget and the selection. No flag changes them.

- 5 duels. Each duel uses a different 2p map.
- 3 FFA games. The harness picks one of two size sets: {4, 6, 10} or
  {5, 7, 8}.

Every game goes to `league/games.jsonl`. A commit cannot play more.
A completed commit plays no game on a second run; a run stopped
part-way plays the games that remain.

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

- If two iterations in a row do not beat the champion, make the next
  iteration bold.
- Start a bold iteration with research, not with code:
  1. Search the web for ants strategies and for other AI Challenge bots.
  2. Read the bot code in this repo.
  3. Write the sources and the notes in `autoresearch/docs/RESEARCH.md`.
  4. Pick a different design or a different idea group.
     Do not change one number.
- A bold approach can be a new design or the code of another bot.
  Copy that code into `autoresearch/bot/` (for example `bots/pas11`).
- Give a bold line at least 3 iterations before you judge it.
  A new design starts weak.
- The champion is the best bot from any line. Never discard the best
  bot of a line.

## Errors

- A crash is data. Read the replay and the log.
  If the error is small, change the code and play again.
- Each commit runs the hooks: ruff, mypy, and pytest. If a hook
  changes a file, add the file again and commit again. If a hook
  fails, change the code and commit again.
- If the harness says "duplicates a rated bot", the code matches a bot
  that already has games. Change the code.
- If the harness says "tree is dirty", commit first.
- If the harness says "main is not merged", run `git merge main` and
  commit the merge.
- If the harness says "tools/ diverges from branch main", the engine
  changed. Restore it with `git checkout main -- tools/`.
  Do not edit the engine.
- If the push fails (network, or the remote moved), do not reset or
  rebase. Keep the commits and push again at the next log commit.
- After 3 failed code changes for one idea, drop the idea and write
  the reason.

## Analysis

- `.venv/bin/python league/board.py` shows the field. The `lb` column is
  the live rating. A bot keeps playing after its iteration, so the live
  rating can differ from the recorded score.
- `autoresearch/docs/PROGRESS.jsonl` holds the recorded score for each
  completed iteration. It is the source of truth for keep or discard.
  It is append-only; the champion is the best row for the current
  budget. Rows from an older budget stay in the file and are ignored.
- The replays are in `autoresearch/runs/<sha>/`.
  Read them to find errors.
- Read `autoresearch/docs/CEILING.md` before you work on a large gain.
