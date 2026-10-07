# Autoresearch program

## Goal

Maximize the iteration score. The score is `mu`. It is the skill
estimate after the fixed budget of games. The harness writes it to
`autoresearch/docs/PROGRESS.jsonl` when the budget ends. Every fresh
bot gets 9 games. They are 7 duels plus 10p and 6p. Opponents are
fairly chosen, so the comparison is fair. A live rating keeps moving
after the iteration. The recorded score does not move. The champion
is the best recorded score for the current budget.

## Roles

Three roles run the loop. Each role has its own files. No role
touches another role's files.

- Coder: builds the best bot it can from a given start,
  inside 60 minutes. It edits `autoresearch/bot/` only.
  It never plays games.
- Coordinator: runs the exam and keeps the notes. It edits
  `autoresearch/docs/` only. It never writes bot code.
- Scorer: plays one exam through `autoresearch/iteration.py`.
  It runs in the coordinator tree. It reports the score line. It
  changes nothing else. It never codes.

Nobody edits `tools/`, `league/`, `autoresearch/iteration.py`,
`tests/`, `pyproject.toml`, or another bot in its own directory.
You can copy the code of another bot into `autoresearch/bot/`.

The loop still learns: commit, measure, keep the winner, repeat.

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

## Loop

Each iteration makes a fresh bot entry. The coder writes it. The
coordinator measures it.

1. Coordinator: merge `main` into `autoresearch/main`:
   `git checkout autoresearch/main && git merge main`
   Resolve any conflict before briefing the coder.
2. Coordinator: pick the start: the code in `autoresearch/bot/`
   on a given commit. Brief a coder with the start and the goal:
   build the best bot possible. On bold steps the brief also prompts
a new direction. Brief the 60-minute budget. At spawn, stage
   the start files as the coder base. Copy any replay
   files the brief cites: runs/ is ignored, so fresh worktrees
   lack them.
3. Coder: write failing test cases first for the risky part. Then
   write the bot code. Run the tests inside the budget. Commit:
   `git add autoresearch/bot && git commit -m "exp: <idea>"`
   Then report and stop. No games, no notes, no push.
4. Coordinator: merge the coder branch with `git merge --no-ff`.
   The merge keeps the leaf sha: exams and history reference one
   node. List it with `git log --graph`. Then delete the branch.
   A conflicted merge resolves in a scratch worktree first:
   the exam tree is never dirty while a scorer runs. Merge
   commits land only when no scorer runs: coder branches wait
   for the exam boundary.
   Then play the budget:
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
7. Coordinator: record Score, Learned, Next in the body of
   a `log: <idea>` commit. Mark the idea's row in `autoresearch/docs/IDEAS.md`. On a crown
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

The coordinator may overlap exam(N) with coding(N+1). Worktrees
separate them, never discipline alone. The coordinator tree stays
on `autoresearch/main` for the whole run. Never switch it while
an exam runs. Never switch it while game, rating, or score files
are uncommitted. A checkout orphans the open log and loses games.
The coordinator's own `main`-side edits go through a scratch
worktree.

## Coder

## Coder

Build the best bot possible from the staged start files.
60 minutes: run `date +%s` first, reserve the last 10 for
tests plus hooks plus commit.

Work on `tree/<line>-<n>` in its worktree. Never enter the
coordinator tree. Never push `tree/*`.

Fresh filenames per entry. Never edit another entry in place.

Tests first, whole suite green. Tests live in `autoresearch/bot/`.

Self-contained entry: stdlib plus `ants.py` only. One turn must
finish in 1000 ms. Use `.venv/bin/python`.

Commit `git add autoresearch/bot` only, message `exp: <idea>`.
Report and stop. No games, no `iteration.py`, no push.

## Tree

Coders run in parallel, one branch per coder. Exams stay serial:
one scorer at a time. Keep at most 6 entries ahead of the scorer
(coding plus unscored). Spawn no coder past that. Git stores the tree: each merge keeps
the leaf as second parent, so `git log --graph` shows every line.
A line is dead when its last 3 exams never beat its earlier best.
Upward trend means max(last 3) is above max(all earlier exams);
a line with fewer than 4 exams is immune. Dead lines get no exams
and no children. The champion line never dies.
Two selections drive the loop. Score: oldest unscored leaf of
the next live line, round-robin over lines. Spawn coders in
this order, enough to reach 6 entries ahead of the scorer
(coding plus unscored). 1. Extend: a live line has a scored leaf with no
child in flight. Take the newest scored leaf of the most
recently examined live line. 2. Split-branch: a second diagnosis exists for a failure
that already has a child. Branch the same parent. 3. Idle-branch:
coder capacity is idle and every scored leaf has a child in
flight. Take the oldest unscored leaf of the line with
the fewest children in flight. Never give one leaf two children
in flight.
Split one failure with two diagnoses into one child leaf each.
A leaf that wins big on a new mechanism starts its own line.
Prune the weaker fork at its next exam.

## Log

Git is the log. `WORKLOG.md` is frozen (history only).

- Coder commits `exp: <idea>` on its branch.
- Coordinator merges with:
  `git merge --no-ff tree/<line>-<n> -m "merge tree/<line>-<n>: <idea>"`
- Coordinator logs with `log: <idea>`. The body holds Score,
  Learned, Next, Rivals. Rivals are open alternative explanations
  of the same result. They arm split-branch.
- A hook rejects other subjects. Explore with:
  `.venv/bin/python autoresearch/log.py frontier|show|lines|best`.

## Harness

The harness sets the budget and the selection. No flag changes
them. The harness selects the maps, the slots, the seeds, and
the opponents. You do not select them.

- One 10p census, then one 6p refine, then 7 duels. The order is
  fixed: the census reads priors, the refine reads the census,
  the duels read everything. Each duel uses a different 2p map.
- A duel: the opponent has the best draw odds + 0.02 sigma over
  the 40 nearest rulers. Deterministic: no epsilon, no breadth.
- The 10p game is a census: the candidate plus quantile-decile
  rulers over full-pool mass, nearest snap.
- The 6p game is a refine: the candidate plus bot-centered
  below/peer/above rulers by mass quota from the low-sigma tertile
  of the last 400 pool members by last log appearance.
- The map, the slot, and the seeds are random. This keeps the test
  honest. Do not try to control the selection.

Every game goes to `league/games.jsonl`. A commit cannot play
more. A completed commit plays no game on a second run. A run
stopped part-way plays the games that remain.

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
