# Autoresearch

`autoresearch/` runs a bot development loop. One agent improves one bot.
Each iteration makes a fresh bot entry: one commit, changed bot code,
and one fixed set of games. The agent keeps a change when the recorded
score improves.

## The loop

1. Read the notes. Pick one idea.
2. Choose the start. You can start from the champion, an older bot, or
   a new design.
3. Edit `bot/`.
4. Commit.
5. Play the budget: 16 duels and 7 FFA games.
6. The harness records the score in `docs/PROGRESS.jsonl`. Keep the
   commit if the new score beats the champion score.
7. Log the result. Repeat.

The operating instructions are in `docs/PROGRAM.md`. Start there.

## Budget

One iteration has 23 games:

- 16 duels. Each duel uses a different 2p map.
- 7 FFA games. One game for each size from 4 to 10.

The harness sets the numbers. No flag changes them.
Every game goes to `league/games.jsonl`. A commit cannot play more.
A second run of the same commit plays no game.

## Score

The score is the snapshot `mu - 3 * sigma` at the end of the budget.
The harness writes one JSON line for each completed iteration to
`docs/PROGRESS.jsonl`. Every fresh bot gets the same games, so the
comparison is fair. A bot keeps playing after its iteration, but the
recorded score does not move. The champion is the best recorded score.

## Why the design holds

- Fixed budget per commit. Each iteration makes a fresh bot entry.
  The bot cannot gain more games, so the rating cannot be ground up.
- Recorded scores. The harness compares each bot after the same 23
  games, not against a live rating that keeps changing.
- Honest selection. The harness picks the maps, slots, seeds, and
  opponents. The agent cannot pick easy games.
- One mutable surface. The agent edits the bot and the notes only.
  The engine must match `main`. The league and the harness stay fixed.
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
