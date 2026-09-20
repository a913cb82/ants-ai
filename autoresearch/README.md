# Autoresearch

`autoresearch/` runs a bot development loop. One agent improves one bot.
Each iteration makes a fresh bot entry: one commit, changed bot code,
and one fixed set of games. The agent keeps a change when the recorded
score improves.

## The loop

1. Merge `main` into `autoresearch/main`.
2. Read the notes. Pick one idea.
3. Choose the start. You can start from the champion, an older bot, or
   a new design.
4. Edit `bot/`.
5. Commit.
6. Play the budget: 5 duels and 3 FFA games.
7. The harness records the score in `docs/PROGRESS.jsonl`. Keep the
   commit if the new score beats the champion score for the current
   budget.
8. Log the result. Push your branch:
   `git push origin autoresearch/main`. Repeat.

The operating instructions are in `docs/PROGRAM.md`. Start there.

## Budget

One iteration has 8 games:

- 5 duels. Each duel uses a different 2p map.
- 3 FFA games. The harness picks one of two size sets: {4, 6, 10}
  or {5, 7, 8}.

The harness sets the numbers. No flag changes them.
Every game goes to `league/games.jsonl`. A commit cannot play more.
A completed commit plays no game on a second run. A run stopped
part-way plays the games that remain.

## Score

The score is the snapshot `mu - 3 * sigma` at the end of the budget.
The harness writes one JSON line for each completed iteration to
`docs/PROGRESS.jsonl`. Every fresh bot gets 8 games, 5 duels and
3 FFA, against fairly chosen opponents, so the comparison is fair.
A bot keeps playing after its iteration, but the recorded score does
not move. The champion is the best recorded score for the current
budget. The file is append-only. Rows from an older budget stay in
the file. The harness ignores them.

## Why the design holds

- Fixed budget per commit. Each iteration makes a fresh bot entry.
  The bot cannot gain more games, so the rating cannot be ground up.
- Recorded scores. The harness compares each bot after its fixed
  8-game budget, not against a live rating that keeps changing.
- Honest selection. The harness picks the maps, slots, seeds, and
  opponents. The agent cannot pick easy games.
- One mutable surface. The agent edits the bot and the notes only.
  The engine must match `main`. The league and the harness stay fixed.
- Remote sync. The loop pushes `autoresearch/main` after each log
  commit, so the remote carries every recorded score. `main` is
  maintained outside the loop.
- Bold cadence. Two failures in a row force a different approach.
  A bold line gets at least 3 iterations before judgement.

## Running the agent

Start your coding agent in this repo. Give the agent full permissions.
Then prompt:

```
Read autoresearch/docs/PROGRAM.md. Do the setup. Start the loop.
```

The agent works alone after that. It commits, plays, measures, and
repeats. `docs/PROGRAM.md` is the skill.

## File map

Paths are relative to `autoresearch/`.

| Path | Role |
|---|---|
| `docs/PROGRAM.md` | operating instructions (start here) |
| `docs/METHODS.md` | the fixed numbers and commands |
| `docs/PROGRESS.jsonl` | iteration scores, written by the harness |
| `docs/WORKLOG.md` | one entry per iteration |
| `docs/IDEAS.md` | doctrine and the idea list |
| `docs/RESEARCH.md` | notes from outside sources |
| `docs/STRATEGY.md` | how the bot plays now |
| `docs/CEILING.md` | limits that a game proved |
| `docs/archive/` | kept replays and notes |
| `bot/` | the bot that the agent improves |
| `iteration.py` | the harness |
| `runs/` | replays (not tracked, trimmed by size) |
| `tests/` | harness tests |
