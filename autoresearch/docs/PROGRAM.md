# Autoresearch program

Two roles run the loop. A coder writes one bot change per
iteration, inside a fixed time budget. A coordinator runs the exam
and keeps the notes. Coders never play games or see scores; the
coordinator never writes bot code. The loop still learns: commit,
measure, keep the winner, repeat.

## Setup

Do this once for each run.

1. Read `autoresearch/README.md`, `autoresearch/docs/METHODS.md`,
   `autoresearch/docs/IDEAS.md`, `autoresearch/docs/STRATEGY.md`,
   `autoresearch/docs/CEILING.md`, `autoresearch/docs/PROGRESS.jsonl`,
   and the end of `autoresearch/docs/WORKLOG.md`.
2. Coders work on branch `autoresearch/main`, which the coordinator
   keeps merged with `main`. Never commit to `main`. Never push `main`.
3. The bot is in `autoresearch/bot/`. The file `main.bot` starts the bot.
   `main.bot` is a one-line command. The engine runs it with the bot
   directory as the working directory.

## Scope

The coder edits `autoresearch/bot/` (the bot) only, including scratch
tests beside the bot. The coordinator edits `autoresearch/docs/`
(the notes) only.

Nobody edits:

- `tools/` (the engine)
- `league/` (the league)
- `autoresearch/iteration.py` (the harness)
- `tests/`, `pyproject.toml`, or other bots

You can copy the code of another bot into `autoresearch/bot/`.
Do not edit another bot in its own directory.

Rules:

- Use `.venv/bin/python` for every command. Each command runs in a new
  shell, so an activated venv does not stay active.
- Coder: make a fresh bot entry each iteration. Change the bot code
  and commit it. The harness counts games by bot id. An old entry
  cannot play again.
- Use only the Python standard library and the packages in the venv.
  Do not run pip.
- One turn must finish in 1000 ms. A slow bot loses on time.
  The load time is 3000 ms.
- The coordinator plays every game through `autoresearch/iteration.py`.
  A game outside the harness is forbidden. Coders run no engine games;
  they test with unit tests and replay reads.
- `league/games.jsonl` is the game log. The harness appends to it.
  Do not edit it. Commit it with your notes.
- Read the code of the other bots. Do not edit their code.
- The coder gets one idea and a fixed time budget (30 minutes unless
  the brief says otherwise). It works detached in the shared worktree
  (/tmp/loop-coder), never in the coordinator tree. No branch is ever
  created for unmeasured code: a visible branch would leak into the
  pool (`git log --all`), drafting unrated code as rulers and tripping
  the duplicate guard on identical content later. Each entry gets
  fresh filenames: copy the staged champion files to a new name, add
  the one idea, and remove the predecessor's files. Never edit the
  previous entry's files in place — stacking two unmeasured ideas in
  one filename destroys attribution. It writes test cases first for
  the risky part, then the bot code, runs whatever tests it wants
  inside the budget, commits `exp: <idea>`, reports, and stops. It never runs `iteration.py`, never plays games, never
  reads scores, never edits notes, never pushes, never merges.
  Uncommitted work at budget end is dropped.
- Scratch tests live in /tmp or beside the bot, committed with the
  exp commit. They never go under `tests/`.
- The coordinator merges, briefs, plays, compares, tags, logs, and
  pushes. It never edits bot code. At spawn it stages the
  measured-champion files as the coder's base, so every entry is
  champion plus exactly one idea.

## Goal

The goal is to maximize the iteration score. The score is
`mu`, the skill estimate after the fixed budget of games.
The harness writes it to `autoresearch/docs/PROGRESS.jsonl` when the
budget ends. Every fresh bot gets 9 games, 7 duels plus 10p and 6p, against
fairly chosen opponents, so the comparison is fair. A bot's live
rating keeps moving after the iteration. The recorded score does not
move. The champion is the best recorded score for the current budget.

## One iteration

Each iteration makes a fresh bot entry. The coder writes it; the
coordinator measures it.

1. Coordinator: merge `main` into `autoresearch/main`:
   `git checkout autoresearch/main && git merge main`
   Resolve any conflict before briefing the coder.
2. Coordinator: pick one idea from `autoresearch/docs/IDEAS.md` or
   from research, choose the start (the champion is safe; an older
   bot or a new design is allowed), and brief a coder with the idea
   and its time budget.
3. Coder: write failing test cases first for the risky part, then
   the bot code. Run the tests inside the budget. Commit:
   `git add autoresearch/bot && git commit -m "exp: <idea>"`
   Then report and stop. No games, no notes, no push.
4. Coordinator: play the budget:
   `.venv/bin/python autoresearch/iteration.py --bot <live bot file>`
5. Read the score. The harness prints the score and adds one JSON line
   to `autoresearch/docs/PROGRESS.jsonl`. The champion is the best
   line for the current budget.
6. Compare the new score with the champion score:
   - Baseline (no row for this budget) or new best: point the tag at
     this commit: `git tag -f champion/main`.
   - Lower or equal: point the tag at the best row's commit:
     `git tag -f champion/main <sha in the best row's bot id>`.
   A missing tag is fine. The rule above rebuilds it. The tag is
   local. Never push tags. Keep the commit in all cases. Start the
   next idea from the champion.
9. Coordinator: add one entry to `autoresearch/docs/WORKLOG.md`. Mark
   the idea's row in `autoresearch/docs/IDEAS.md`. On a crown change,
   update the Current bot section of `autoresearch/docs/STRATEGY.md`.
   Commit the notes and the new games:
   `git add autoresearch/docs league/games.jsonl && git commit -m "log: <idea>"`
10. Push the branch:
    `git push origin autoresearch/main`
    The coordinator owns this branch only. Never push `main` or tags. A failed
    push is not a lost iteration. Keep the commits and push again at
    the next log commit.
11. Go to step 1. Do not stop.

## Pipeline

The coordinator may overlap exam(N) with coding(N+1). Separation is
by worktree, never by discipline alone:

- The coordinator tree stays on `autoresearch/main` for the whole
  run. It is never switched to another branch while an exam runs or
  while game, rating, or score files are uncommitted: a checkout
  would orphan the harness's open log and lose games. The
  coordinator's own `main`-side edits go through a scratch worktree.
- Coders are sequential, so they share one worktree path
  (/tmp/loop-coder), recreated fresh from `autoresearch/main` for
  each iteration, always detached (`git worktree add --detach`:
  no branch, so unmeasured code stays invisible to the pool).
  Fresh means no stale scratch files leak across iterations. The
  coder never enters the coordinator tree.
- The coder never runs `iteration.py`. One exam call takes about
  25 minutes (7 duels plus two FFAs); the coordinator runs it after
  the exp commit lands. Running it from a dirty tree trips the
  harness guard and aborts the exam, and seeing scores early breaks
  the blind. Coders test with unit tests and replay reads.
- A detached exp commit holds bot changes only. The coordinator
  verifies with `git diff --stat` and cherry-picks it onto
  `autoresearch/main` (linear history, exams run in commit order),
  then removes the shared worktree. The next spawn recreates it.
  Cherry-picks only ever carry unrated content: rated content is
  permanently unplayable as a fresh entry by design.

## Budget

The harness sets the budget and the selection. No flag changes them.

- 7 duels. Each duel uses a different 2p map.
- One 10p census and one 6p refine, fixed sizes.

Every game goes to `league/games.jsonl`. A commit cannot play more.
A completed commit plays no game on a second run. A run stopped
part-way plays the games that remain.

## Selection

The harness selects the maps, the slots, the seeds, and the opponents.
You do not select them.

- A duel: the opponent has the best draw odds + 0.02 sigma over the
  40 nearest rulers. Deterministic: no epsilon, no breadth.
- The 10p game is a census: the candidate plus quantile-decile rulers
  over full-pool mass, nearest snap.
- The 6p game is a refine: the candidate plus bot-centered
  below/peer/above rulers by mass quota from the low-sigma tertile
  of the last 400 pool members by last log appearance.

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
  It is append-only. The champion is the best row for the current
  budget. Rows from an older budget stay in the file. The harness
  ignores them.
- The replays are in `autoresearch/runs/<sha>/`.
  Read them to find errors.
- Read `autoresearch/docs/CEILING.md` before you work on a large gain.
