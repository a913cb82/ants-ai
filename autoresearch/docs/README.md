# Autoresearch

`autoresearch/` runs a bot development loop. One agent improves one bot.
Each iteration is one commit and one fixed set of games.
The agent keeps a change when the rating improves.

## The loop

1. Read the notes. Pick one idea.
2. Start from the champion commit. Edit `autoresearch/bot/`.
3. Commit.
4. Play the budget: 16 duels + 1 FFA per size 4..10.
5. Keep the commit if `mu - 3 * sigma` beats the champion.
6. Log the result. Repeat forever.

The operating instructions are in `docs/PROGRAM.md`. Start there.

## Why the design holds

- **Fixed budget per commit.** A fresh commit is a fresh bot id.
  A commit cannot play more games, so a rating cannot be ground up.
- **Every game enters the record.** All games go to `league/games.jsonl`.
  Ratings rebuild from that log.
- **Honest selection.** The harness picks maps, slots, seeds, and opponents
  by information score. The agent cannot pick easy games.
- **One mutable surface.** The agent edits the bot and the notes only.
  The engine, the league, and the harness stay fixed.
- **Bold cadence.** Two failures in a row force a researched, different
  approach. A bold line gets at least 3 iterations before judgement.
  This fights local optima.

## File map

| Path | Role |
|---|---|
| `docs/PROGRAM.md` | operating instructions (start here) |
| `docs/METHODS.md` | binding numbers, selection, commands |
| `docs/WORKLOG.md` | one entry per iteration, append-only |
| `docs/IDEAS.md` | doctrine and the idea backlog |
| `docs/RESEARCH.md` | cited external research |
| `docs/STRATEGY.md` | how the bot plays; what good play looks like |
| `docs/CEILING.md` | measured limits; what cannot help |
| `docs/archive/` | report cards and kept replays |
| `bot/` | the bot the agent improves |
| `iteration.py` | the harness: budget, selection, logging, score |
| `runs/` | per-game replays (untracked, pruned by size) |
| `tests/` | harness tests |
