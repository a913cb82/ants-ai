# Autoresearch

`autoresearch/` runs a bot development loop. One agent improves one bot.
Each iteration is one commit and one fixed set of games.
The agent keeps a change when the rating improves.

## The loop

1. Read the notes. Pick one idea.
2. Start from the champion commit. Edit `bot/`.
3. Commit.
4. Play the budget: 16 duels and 7 FFA games.
5. Keep the commit if `mu - 3 * sigma` beats the champion.
6. Log the result. Repeat.

The operating instructions are in `docs/PROGRAM.md`. Start there.

## Budget

One iteration has 23 games:

- 16 duels. Each duel uses a different 2p map.
- 7 FFA games. One game for each size from 4 to 10.

Every game goes to `league/games.jsonl`. A commit cannot play more.
A second run of the same commit plays nothing.

## Why the design holds

- Fixed budget per commit. A new commit is a new bot id. The bot cannot
  gain more games, so the rating cannot be ground up.
- Honest selection. The harness picks the maps, slots, seeds, and
  opponents. The agent cannot pick easy games.
- One mutable surface. The agent edits the bot and the notes only.
  The engine, the league, and the harness stay fixed.
- Bold cadence. Two failures in a row force a researched, different
  approach. A bold line gets at least 3 iterations before judgement.

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
| `docs/METHODS.md` | the binding numbers and commands |
| `docs/WORKLOG.md` | one entry per iteration |
| `docs/IDEAS.md` | doctrine and the idea list |
| `docs/RESEARCH.md` | notes from outside sources |
| `docs/STRATEGY.md` | how the bot plays now |
| `docs/CEILING.md` | limits that a game proved |
| `docs/archive/` | report cards and kept replays |
| `bot/` | the bot that the agent improves |
| `iteration.py` | the harness |
| `runs/` | replays (not tracked, trimmed by size) |
| `tests/` | harness tests |
