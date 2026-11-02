# AZ.md — AlphaAnt pure-mirror doctrine (steady state)

Replaces LEAGUE.md's league machinery (roles, PFSP, admissions, snapshots,
anchors — frozen as record in ml/runs/). One learner, latest-vs-latest
mirror, no yardstick. The only absolute the board shows is behavior and
training vitals against the game's fixed substrate (food, kills,
army share, length): mirror draws stay decisive-free, curves slope the
right way, PPO stays healthy.

## The loop

1. **Mirror.** `main` plays `main` (any seat count, per the map).
   Every seat trains the same policy; every seat's records and
   seat-perspective returns accumulate into one batch. One row per
   game; the tick IS the game number
   (`games/main/tick{tick}`, `player_seed = seed + tick`,
   `engine_seed = 1000 + tick`).
2. **Cadence.** Micro-batch PPO every 16 completions (`MICRO_BATCH=16`).
   Serial by default; `--concurrency N` plays N games in flight while
   the update still fires every 16 completions. The update trains in a
   background thread on a weights snapshot taken at the boundary, so
   dispatch never stalls; games played mid-update train from weights at
   most one update old. Backpressure: at most one update runs — when
   the learner is slower than 16 games, the loop waits instead of
   piling up stale games. `updates.jsonl` carries `update_seconds`
   per update; the training table shows it, so the duty cycle reads
   off the board.
3. **Crash-ok.** `_claim_tick` hands out each tick under a lock, never
   reuses numbers. Every state is valid: game rows kept, `live/` points
   at the last finished update, the bank holds one shard per unapplied
   tick (a rewrite-free append, never a whole-list re-save). There is
   no recovery and no repair — just rerun.
4. **Fresh starts.** Every net is drawn fresh (`CNNPolicy.reset_parameters`,
   CleanRL init); nothing resumes from g000 or any snapshot.
5. **The one diet.** `rewards.scales()`: FOOD 0.1, KILL 0.1,
   HILL_APPROACH 0.25, DEATH −0.2, raze +10 / lost −10, WIN +5 /
   LOSS −5, terminal linear over placements (sole-first +5, sole-last
   −5, middles graduated; 2p unchanged). Hill-approach pays
   only on positive-placement finishes; kills pay on every finish;
   death always
   hurts. Each game's priced rows enter the batch whole up to
   `ROW_CAP` (4096, uniform seed:tick subsample), so a 20k-row table
   cannot dominate RAM or the batch. Terminal outcome broadcasts to every move, undiscounted.

6. **Loud, never silent.** Anything unexpected errors: a mask breach
   or ghost record fails the tick and halts the trainer for a human;
   passable-stay loss off the timeout turn fails it too (the engine
   applies every order it receives; playerturns pins the cutoff turn).
   Timeout-turn stranded orders resolve to stays instead of counting
   as misses (unsent ≡ stay; intent stays honest). Cutoff evidence is
   turn-level: any seat timing out on turn t explains any stranded
   miss on t — per-seat status proved racy at game end (tick635), and trace-miss over
   5% raises a board alert. Silent fallbacks hid
   a dead water channel all game; never again.
7. **PPO baseline (frozen).** Advantages from one frozen pre-update
   baseline, standardized over the whole micro-batch; clipped
   surrogate + shared-trunk value head. Stats logged per update:
   loss, pg, value, entropy, KL, clipfrac, explained variance.

## What to watch (the board)

- **Decisive rate + mean length:** mirror must not collapse into
  all-draws or all-timeout stalemates.
- **Behavior (per seat):** food, kills, army-alive share. High food
  + zero kills + long games = turtle; falling food + short games =
  degenerate rush.
- **Training vitals:** loss/pg/value should fall; entropy decay
  slowly; KL small and flat; clipfrac < ~0.3; explained variance
  rising toward 1. KL spiking or entropy collapsing = stop and look.
- **One spark = one history:** every sparkline is the trailing ≤40
  values of the number it sits next to, oldest first.

## Falsifiers

- Mirror draws a majority over any 40-game window → shaping lets the
  policy turtle; change the diet, not the loop.
- Two consecutive 8-game updates with explained variance ≤ 0 → the
  critic learned nothing; change capacity/features, not cadence.
- Entropy hits ~0 while decisive rate < 50% → premature convergence;
  raise temperature or entropy beta.
