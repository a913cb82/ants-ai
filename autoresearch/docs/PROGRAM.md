# Autoresearch program

Two roles run the loop. A coder writes one bot change per iteration, inside a fixed time budget. A coordinator runs the exam and keeps the notes. Coders never play games. Coders never see scores. The coordinator never writes bot code. The loop still learns: commit, measure, keep the winner, repeat.

## Setup

Do this once for each run.

1. Read `autoresearch/README.md`, `autoresearch/docs/METHODS.md`,
   `autoresearch/docs/IDEAS.md`, `autoresearch/docs/STRATEGY.md`,
   `autoresearch/docs/CEILING.md`, `autoresearch/docs/PROGRESS.jsonl`,
   and the end of `autoresearch/docs/WORKLOG.md`.
2. Coders work on branch `autoresearch/main`. The coordinator keeps
   it merged with `main`. Never commit to `main`. Never push `main`.
3. The bot is in `autoresearch/bot/`. The file `main.bot` starts
   the bot. `main.bot` is a one-line command. The engine runs it
   with the bot directory as the working directory.

## Scope

The coder edits `autoresearch/bot/` only. This includes scratch
tests beside the bot. The coordinator edits `autoresearch/docs/`
only.

Nobody edits:

- `tools/` (the engine)
- `league/` (the league)
- `autoresearch/iteration.py` (the harness)
- `tests/`, `pyproject.toml`, or other bots

You can copy the code of another bot into `autoresearch/bot/`.
Do not edit another bot in its own directory.

Rules:

- Use `.venv/bin/python` for every command. Each command runs
  in a new shell. An activated venv does not stay active.
- Coder: make a fresh bot entry each iteration. Change the bot
  code and commit it. The harness counts games by bot id. An old
  entry cannot play again.
- Use only the Python standard library and the packages in
  the venv. Do not run pip.
- One turn must finish in 1000 ms. A slow bot loses on time.
  The load time is 3000 ms.
- The coordinator plays every game through
  `autoresearch/iteration.py`. It delegates each exam to one
  exam-runner subagent. The subagent runs in the coordinator
  tree. It reports the score line. It changes nothing else.
  A game outside the harness is forbidden. Coders run no engine
  games. Coders never learn scores. Exam-runners never code.
- `league/games.jsonl` is the game log. The harness appends
  to it. Do not edit it. Commit it with your notes.
- Read the code of the other bots. Do not edit their code.
- Know the 2011 top-bots. Sources are in `vendor/ants-topbots/`.
  Seven run in `bots/`. Steal mechanisms, not constants.
- The coder gets one idea and a fixed time budget. The budget
  is 30 minutes unless the brief says otherwise. The coder
  manages its own clock. Run `date +%s` first. Compute
  the deadline. Re-check before each major step. Stop coding
  early enough to run tests plus hooks plus commit before
  the deadline. Uncommitted work at budget end is dropped.
  A smaller green commit beats a bigger uncommitted one. It
  works detached in the shared worktree (/tmp/loop-coder). It
  never works in the coordinator tree. Never create a branch
  for unmeasured code. A visible branch leaks into the pool
  (`git log --all`). It drafts unrated code as rulers. It trips
  the duplicate guard on identical content later. Each entry
  gets fresh filenames. Copy the staged champion files to
  a new name. Add the one idea. Remove the predecessor's files.
  Never edit the previous entry's files in place. Stacking two
  unmeasured ideas in one filename destroys attribution. Tests
  are vital to making bots good. The coder writes failing test
  cases first for the whole idea, not just the risky part. Then
  it writes the bot code. It spends the budget on the idea and
  its scenarios. It commits `exp: <idea>`. It reports. It stops.
  It never runs `iteration.py`. It never plays games. It never
  reads scores. It never edits notes. It never pushes. It never
  merges.
- Tests live beside the bot in `autoresearch/bot/`. They are
  first-class loop code. Entry test files (`test_<Entry>.py`) go
  away with their entry. Shared helper modules (for example
  `combat.py`) and their tests (for example `test_combat.py`)
  persist between iterations and grow. Each coder extends them.
  Each coder keeps the whole suite green. Tests never go under
  `tests/`. Tests never reference worktree-root staging files.
- Tests are not only correctness checks. Every coder brief names
  2-3 benchmark scenarios. They are small hand-built situations.
  They cover any part of play. Each one discriminates base from
  tuned. Each one runs in seconds. Scenario files persist as
  a regression suite. Use them to understand the idea. Try
  variants. Watch what changes. Report what you learn. Scenarios
  guide experiment, not maximisation. A scenario score is
  evidence, not the goal.
- The coordinator merges, briefs, plays, compares, tags, logs,
  and pushes. It never edits bot code. At spawn it stages
  the measured-champion files as the coder base. Every entry is
  champion plus exactly one idea.

## Goal

The goal is to maximize the iteration score. The score is `mu`.
It is the skill estimate after the fixed budget of games. The
harness writes it to `autoresearch/docs/PROGRESS.jsonl` when
the budget ends. Every fresh bot gets 9 games. They are 7 duels
plus 10p and 6p. Opponents are fairly chosen, so the comparison
is fair.
A live rating keeps moving after the iteration. The recorded
score does not move. The champion is the best recorded score for
the current budget.

## One iteration

Each iteration makes a fresh bot entry. The coder writes it. The
coordinator measures it.

1. Coordinator: merge `main` into `autoresearch/main`:
   `git checkout autoresearch/main && git merge main`
   Resolve any conflict before briefing the coder.
2. Coordinator: pick one idea from `autoresearch/docs/IDEAS.md`
   or from research. Choose the start. The champion is safe.
   An older bot or a new design also works. Brief a coder with
   the idea and its time budget.
3. Coder: write failing test cases first for the risky part. Then
   write the bot code. Run the tests inside the budget. Commit:
   `git add autoresearch/bot && git commit -m "exp: <idea>"`
   Then report and stop. No games, no notes, no push.
4. Coordinator: play the budget:
   `.venv/bin/python autoresearch/iteration.py --bot <live bot file>`
5. Read the score. The harness prints the score. It adds one JSON
   line to `autoresearch/docs/PROGRESS.jsonl`. The champion is
   the best line for the current budget.
6. Compare the new score with the champion score:
   - Baseline (no row for this budget) or new best: point the tag
     at this commit: `git tag -f champion/main`.
   - Lower or equal: point the tag at the best row's commit:
     `git tag -f champion/main <sha in the best row's bot id>`.
   A missing tag is fine. The rule above rebuilds it. The tag is
   local. Never push tags. Keep the commit in all cases. Start
   the next idea from the champion.
7. Coordinator: add one entry to `autoresearch/docs/WORKLOG.md`.
   Mark the idea's row in `autoresearch/docs/IDEAS.md`. On a crown
   change, update the Current bot section of
   `autoresearch/docs/STRATEGY.md`. Commit the notes and the new
   games:
   `git add autoresearch/docs league/games.jsonl && git commit -m "log: <idea>"`
8. Push the branch:
   `git push origin autoresearch/main`
   The coordinator owns this branch only. Never push `main` or
   tags. A failed push is not a lost iteration. Keep the commits
   and push again at the next log commit.
9. Go to step 1. Do not stop.

## Pipeline

The coordinator may overlap exam(N) with coding(N+1). Worktrees
separate them, never discipline alone:

- The coordinator tree stays on `autoresearch/main` for the whole
  run. Never switch it to another branch while an exam runs. Never
  switch it while game, rating, or score files are uncommitted.
  A checkout orphans the open log of the harness and loses games.
  The coordinator's own `main`-side edits go through a scratch
  worktree.
- Coders are sequential, so they share one worktree path
  (/tmp/loop-coder). Recreate it fresh from `autoresearch/main`
  for each iteration, always detached (`git worktree add --detach`:
  no branch, so unmeasured code stays invisible to the pool). Fresh
  means no stale scratch files leak across iterations. The coder
  never enters the coordinator tree.
- The coder never runs `iteration.py`. One exam call takes about
  25 minutes (7 duels plus two FFAs). The coordinator runs it after
  the exp commit lands. A run from a dirty tree trips the harness
  guard and aborts the exam. Early scores break the blind. Coders
  test with unit tests and replay reads.
- A detached exp commit holds bot changes only. The coordinator
  verifies with `git diff --stat`. It cherry-picks the commit onto
  `autoresearch/main` (linear history, exams run in commit order).
  Then it removes the shared worktree. The next spawn recreates it.
  Cherry-picks only ever carry unrated content: rated content is
  permanently unplayable as a fresh entry by design.

## Budget

The harness sets the budget and the selection. No flag changes them.

- One 10p census, then one 6p refine, then 7 duels. The order is
  fixed: the census reads priors, the refine reads the census,
  the duels read everything. Each duel uses a different 2p map.

Every game goes to `league/games.jsonl`. A commit cannot play
more. A completed commit plays no game on a second run. A run
stopped part-way plays the games that remain.

## Selection

The harness selects the maps, the slots, the seeds, and
the opponents. You do not select them.

- A duel: the opponent has the best draw odds + 0.02 sigma over
  the 40 nearest rulers. Deterministic: no epsilon, no breadth.
- The 10p game is a census: the candidate plus quantile-decile
  rulers over full-pool mass, nearest snap.
- The 6p game is a refine: the candidate plus bot-centered
  below/peer/above rulers by mass quota from the low-sigma tertile
  of the last 400 pool members by last log appearance.

The map, the slot, and the seeds are random. This keeps the test
honest. Do not try to control the selection.

## Bold work

A local optimum is the main risk. Obey these rules.

- If two iterations in a row do not beat the champion, make
  the next iteration bold.
- Start a bold iteration with research, not with code:
  1. Search the web for ants strategies and for other AI Challenge
     bots.
  2. Read the bot code in this repo.
  3. Write the sources and the notes in
     `autoresearch/docs/RESEARCH.md`.
  4. Pick a different design or a different idea group. Do not
     change one number.
- A bold approach can be a new design or the code of another bot.
  Copy that code into `autoresearch/bot/` (for example
  `bots/pas11`).
- Give a bold line at least 3 iterations before you judge it.
  A new design starts weak.
- The champion is the best bot from any line. Never discard
  the best bot of a line.

## Errors

- A crash is data. Read the replay and the log. If the error is
  small, change the code and play again.
- Each commit runs the hooks: ruff and mypy. Run pytest by hand.
  If a hook changes a file, add the file again and commit again.
  If a hook fails, change the code and commit again.
- If the harness says "duplicates a rated bot", the code matches
  a bot that already has games. Change the code.
- If the harness says "tree is dirty", commit first.
- If the harness says "main is not merged", run `git merge main`
  and commit the merge.
- If the harness says "tools/ diverges from branch main", the engine
  changed. Restore it with `git checkout main -- tools/`. Do not
  edit the engine.
- If the push fails (network, or the remote moved), do not reset or
  rebase. Keep the commits and push again at the next log commit.
- After 3 failed code changes for one idea, drop the idea and write
  the reason.

## Analysis

- `.venv/bin/python league/board.py` shows the field. The `lb`
  column is the live rating. A bot keeps playing after its
  iteration, so the live rating can differ from the recorded score.
- `autoresearch/docs/PROGRESS.jsonl` holds the recorded score for
  each completed iteration. It is the source of truth for keep or
  discard. It is append-only. The champion is the best row for
  the current budget. Rows from an older budget stay in the file.
  The harness ignores them.
- The replays are in `autoresearch/runs/<sha>/`. Read them to find
  errors.
- Read `autoresearch/docs/CEILING.md` before you work on a large
  gain.
