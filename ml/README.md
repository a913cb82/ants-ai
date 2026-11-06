# AlphaAnt: self-play loop

> **Pure AZ (live):** one-policy mirror self-play — latest vs latest,
> no league, no promotion gate. See `ml/runs/LEAGUE.md` (doctrine)
> and `ml/runs/LOOP.md` (pause/resume). The generation-league
> history below is frozen record (retired 2026-11-01) — `ml/runs/`
> keeps the receipts.

Train an Ants bot the AlphaZero way: mirror self-play, PPO updates,
continuous training. No external opponents, no human judgment.

## Why not vanilla AlphaZero

| AlphaZero assumption | Ants reality | Adaptation |
|---|---|---|
| small discrete actions | `5^N` joint moves | factorized per-ant policy, shared weights, symbolic collision resolution |
| full observability | fog of war, simultaneous moves | local 13-channel window (10 current + 3 T-1 memory), masked to team sight |
| fast simulator + MCTS | 1000 ms turn, subprocess engine | no search; CNN proposes, masks dispose |
| win/loss reward | score + survival + hills | dense shaping + terminal outcome, both discounted (`ml/rewards.py`) |

## Architecture (clean split)

| Layer | Owns | Must not know |
|---|---|---|
| `bots/alphaant/model.py` | network shape, masking, act/sample, save/load | game, training |
| `bots/alphaant/features.py` | actions/offsets, window encoding | policy, training |
| `ml/grid.py` | toroidal math (stdlib only) | everything else |
| `ml/game_if.py` | engine games, staging, replay/record formats | torch |
| `ml/rewards.py` | (game, records) → discounted returns (hills-only diet + 0.01 food) | torch, engine |
| `ml/algorithm.py` | PPO step on masked log-probs | ants, replays |
| `ml/archive.py` | game/update logs, live weights + Adam, pending bank | torch, engine |
| `ml/train.py` | training loop (PPO micro-batch) | league, files |
| `ml/selfplay.py` | mirror loop wiring (latest vs latest) | (thin) |

Policy shape swaps touch exactly one file (`model.py`); algorithm
swaps touch one file; the game interface never imports torch.

## Mirror loop (live — each tick = one game, fully automated)

1. **Play.** `main` plays `main` (any seat count, per the map).
   Every seat records
   `{turn, loc, dest, action, intent, blocked, window, legal}`, prices with
   `rewards.compute_returns` (hills-only diet: raze +10 / lost −10,
   food 0.01 trickle, everything else 0).
2. **Bank.** Scoring games bank PPO rows; scoreless games (all-zero
   returns) log to history but bank nothing and don't advance the
   cadence.
3. **Train.** PPO micro-batch every 16 scoring-game completions
   (`MICRO_BATCH=16`), oldest whole games first up to 65536 rows.
   Background thread on a weights snapshot (staleness ≤ 1 update).

```sh
.venv/bin/python ml/selfplay.py --archive ml/archive \
  --turns 250 --temperature 1.0 --entropy-beta 0.01 \
  --seed <n> --ticks <n>   # negative = forever
```

`ml/archive/` (gitignored) holds `games.jsonl`, `updates.jsonl`,
`state.json`, and `live/` (live `weights.json` + `opt.json` + pending
bank). `bots/alphaant/weights.json` holds a rated snapshot of live —
the only weights in git.

## Retired league (frozen record — generation loop, pre-2026-11-01)

1. ~~Sample opponents from the eval matrix (PFSP-lite).~~
2. ~~Train challenger (champion copy) on both slots.~~
3. ~~Evaluate: Wilson lower bound > 0.5 AND Nash mass ≥ champion's.~~
4. ~~Publish only on promotion: champion pointer + rated weights.~~

## Reward system (live: hills-only diet)

- **Source of truth**: the replay (food gatherer + turn, full order
  strings, hill raze turns) plus the bot's decision log.
- **Credit**: food → adjacent ants (`0 < d2 <= spawnradius2`) at 0.01
  trickle; raze → distance-scaled per ant
  (`amount * exp(-d2*ln10/100)`); lost hill → flat −10 per ant;
  kills / deaths / approach / terminal are 0. Scoreless (all-zero
  returns) games bank nothing.
- **Discount** (`GAMMA=0.97`): dense awards walk back along the
  credited ant's replay path. Terminal outcome is 0 under the diet.
- **Diagnose**: `rewards.decompose(game, me, records)` shows
  undiscounted mass per category — read it before tuning magnitudes.

## Population (retired — frozen record)

- ~~Frozen checkpoints + manifest; train/eval matrices; PFSP-lite;
  Nash mixture; exploiters.~~ League machinery deleted 2026-11-01
  (`ml/pfsp.py`, `ml/measure.py` gone). One live policy only.

## Status (live: pure mirror)

13-channel CNN policy (10 current + 3 T-1 memory) + PPO loop landed
(clipped surrogate, separate value trunk, frozen pre-update baseline
standardized over the micro-batch; Monte-Carlo targets, no GAE — see
`ml/algorithm.py`). Mirror ticks run clean (latest vs latest, update
every 16 scoring games). Open: decisive-rate slope, critic explained
variance, D4/entropy health — see `ml/runs/LEAGUE.md` falsifiers.

## Experiment log

2026-10-25, 1-hour perf + hyperparameter budget (4 arms x 4 gens,
60 turns, train 4 / eval 10, seed 7, paired):
- Wave 1 was VOID: parallel games caused turn-1 engine timeouts
  (`game_length 0`, both sides `timeout`), which log zero rows and
  score 0-0. Empty batches trained on nothing; "draws" were timeouts.
- Fix: engine `--turntime` 1s->5s, `--loadtime` 3s->15s (free when
  healthy), one automatic retry on `game_length 0` (`game_if.play`
  returns a `retried` flag), default workers 12->8. Wave 2:
  zero double-timeouts, full batches (800-1100 rows/gen).
- KL landed at ~0.01/epoch for lr=1e-3 (healthy band) and ~0.01 for
  lr=3e-3: both safe, 1e-3 stays the default. lr=3e-3 showed the
  fastest critic learning (v_loss 1.0->0.74); no eval separation.
- Headline bottleneck: mirror evals on tutorial1 draw ~90%
  (0W/10D typical), so n=10 evals cannot separate knobs or promote.
  Next levers are draw-rate, not step size: longer turns, second map,
  or score-margin eval metric. gamma=0.99 raised train returns
  (+50%) with no eval change — consistent with draws, not learning.

## Performance (same day, inference + training throughput)

150-ant turn: ~40ms -> 7.5ms greedy / 11ms sampled.
- features.snapshot(): five board scans once per turn, not per ant;
  water cached in do_setup (static all game) -> zero engine calls.
- One batched forward per turn (1.2ms vs 6-8ms serial).
- legal_mask vectorized via advanced indexing (49us -> 10us/ant).
- Window buffer is numpy + cached sight-circle offsets.
- No row materialization when not recording.
8-game generation at workers=4: 21.7s -> 7.0s via single-thread
bot env (OMP/MKL/OPENBLAS=1 in game_if; torch.set_num_threads(1)
in the bot). Training compute untouched: 86ms/epoch is noise next
to data cost. Fixed cost left: torch cold start ~1.3s/bot/game
(engine spawns fresh interpreters; out of our hands).

## Pro calibration (2026-10-25; toolchains installed)

Only pas11 runs as-ported; the rest needed compilers (apt: default-jdk
+ build-essential + mono-complete) and all now build except flagcapper
(needs -Wno-implicit-function-declaration, applied to its .sh).
Long games, all rank-stabilized endings, none hitting turn budgets:
- xathis 3-0 fourmidable, tutorial1, 165 turns.
- greentea 3-0 lazarant, generated gen2p_05, 135 turns.
- flagcapper 3-0 starter, tutorial1, 24 turns (fast C bot).
- xathis 3-0 AlphaAnt (early champion), tutorial1, 30 turns.
- pas11 is broken as an opponent: crashes on first enemy contact
  (3-arg destination call its bundled ants.py lacks); also too slow
  (~1000ms/turn, timed out twice). Not a sparring partner.
Lesson: competent games resolve at 130-220 turns (the 24-game
sample below: median 229). Default turns 100 -> 150 -> 250 as the
evidence grew; the 300+ tail stays periodic-eval territory.
xathis is the external measuring stick.

## Pro length sample (24 games, 500-turn cap, all 7 working pros,
   all 5 map families, zero timeouts)

46-500 turns, median 229, mean 256. 21/24 decided before the cap
(rank-stabilized or extermination); 3 hit 500, all draws. Coverage:
turns=150 ends 79% of pro games early; 250 covers 58%, 300 covers
71%. Default turns 150 -> 250: the majority of real games now fit
inside a training game, and the 300+ tail stays periodic-eval
territory.

## Why 30 gens learned nothing (deep-dive 2026-10-25)

Causal chain, evidence-backed:

1. Champion stays random init (0/30 promotions), so every gen trains
   from scratch and evals against random. Nothing accumulates.
2. Batches hold ~20k rows with ~1.6% food-event rows; the rest are
   near-identical walked-back mush (gamma=0.97 over 250 turns credits
   the whole trajectory almost uniformly: 0.97^250 ≈ 0.0005).
3. Per-MINIBATCH advantage standardization amplifies the noise rows
   to O(1) advantages in minibatches that contain zero real events.
   900 noise-gradient steps/gen random-walk the policy far from init
   (challenger-vs-champion KL 1.18) and sharpen it onto noise.
4. The critic chases standardized noise: v_loss flat at ~0.78 all
   30 gens, and probed trainee value heads diverge (+24 vs target
   mean 0). Advantages are standardized noise.
5. Noise-sharpened challenger vs random champion: draws. No promotion.
   Next gen resets. 30 gens = 30 independent random walks.
6. Credit code itself is CORRECT (synthetic traces: same-turn food,
   path walk-back, kill radius, drop conditions all verified) and
   behavior is frozen (scores identical across gens, 0 razes/96 games,
   ~0.5 deaths/game: random-walk foraging, never fighting).

Probes/fixes: 60-turn horizon alone FAILED (6 gens, v_loss 0.81-0.99,
120/120 draws) — horizon sharpens credit but can't create signal when
returns are unpredictable from windows. Landed instead:
(a) potential-based food-approach shaping (symmetric, bounded ~0.2
per approach, offline training-only; every step now carries signal
the critic can learn from windows), (b) batch-level advantage norm
(no second standardization; noise minibatches stay small next to
event minibatches). Stacked probe v1 (turns-60 + both, seed 99):
STILL FLAT (v 0.96-1.00, 120/120 draws). Diagnosis: the walk-back
smeared shaping's immediate contingency with future-movement noise.
Fix: approach awards are same-turn ONLY (food still walks back).
Stacked probe v2 next.

## Critic continuity (2026-10-25): the structural fix

v3 (APPROACH=1.0): still flat (v ~1.0, 120/120 draws). v4 (vf_coef
4.0): v 0.96->0.89, still no wins. Realization: within-gen v falls
(1.03->0.89 over 3 epochs) but the critic RESETS every generation
(challenger starts from champion = random init, zero head) and is
discarded — 30 gens = 30 critic cold-starts. Landed: the value head
persists via archive/critic.json (training apparatus, not the agent;
actor still restarts from champion, evals use policy only). 15-gen
continuity probe (seed 99, turns 60, defaults) next.

## Run 2 (2026-10-25, in flight): the unstick attempt

Same lineage (ml/archive, BC g000, 15 more gens -> 45). Four fixes
vs the flat 30: full-trunk critic banking (was head-only no-op),
ENGAGE=0.5 enemy-approach shaping, exams at 150 turns (60t exams
truncated before wars resolved), exploration up (temp 2.0 +
entropy 0.05; the actor sat frozen at BC weights, 0.006 moves).
Watch: v start-epoch falling across gens (continuity finally
working?), first non-zero margin, first win/promotion.

## The run that should learn (2026-10-25, done flat)

30 gens, seed 456, turns 60, defaults + --init-weights
/tmp/bcpros/bc_weights.json (BC val 0.462; live gate 23-4).
Fresh ml/archive (seed-7 history kept in ml/archive_seed7), commit
ON. Stack: BC init + split critic + continuity + shaping +
batch-norm. Watch: v_loss sustained <0.7, train-return ascent,
first promotion. Dashboard: :8090 (Run card reads run_plan.json).

## Unblocking the next run (2026-10-25): two-pronged

The combo moved the critic (1.0 -> ~0.85, dips to 0.67) but the
policy never converted: shared-trunk thrash was proven by the
critic-fit test (head-only stuck, whole-net fit), and random-init
means E[return|window] = 0 everywhere (nothing predictable to fit).
Two independent fixes, landing in parallel:
(a) separate value trunk (vconv* keys; actor gradients can no longer
fight critic gradients; old checkpoints load with a random-init
value trunk and keep working);
(b) BC-from-pros supervised init (xathis games -> (window, pro move)
rows -> cross-entropy -> --init-weights seeds the gen-0 champion,
so self-play starts from food-competent play instead of random).
Either alone might unstick it; together they compound: a non-random
policy gives the critic something predictable from step one.

## 30-gen combo verdict (2026-10-25): critic moves, policy doesn't

/tmp/azcombo (seed 123, turns 60, vf_coef 4.0, shaping + batch-norm
+ continuity): v oscillates 0.67-0.98 around ~0.85 (floor keeps
touching 0.67-0.77 but never holds); train returns flat 0.09-0.21;
eval 1W/599D (lone win gen 10, margin 0.15, same gen v hit 0.67);
0 promotions. Wins DO co-occur with v dips — the coupling is real —
but the critic never locks below ~0.8 and the policy never converts
sustained wins.

Net of the hour: the failure chain is nailed (reset critic +
noise-amplifying normalization + flat walk-back credit + random-init
champion), three fixes shipped and verified (shaping fires, batch
norm preserves event magnitude, critic persists), and the critic
moved 1.00 -> ~0.85 with flickers to 0.67. But gradient-only
bootstrap from random is still unproven: the policy has not learned
anything measurable in 100+ generations across 6 probes.
Ranked next: (1) separate value network (unshared trunk — the
critic-fit test proved the shared trunk is the blockage); (2)
BC-from-pros supervised init (breaks chicken-and-egg with certainty,
AlphaStar recipe); (3) longer combo runs (cheap, tests compounding).
Decisive-PFSP stays queued (matters once someone CAN win).

## Critic continuity (2026-10-25): partial win

15-gen probe (seed 99, turns 60, shaping + batch-norm + continuity):
v floor 1.00 -> ~0.77 (gen 13: 0.762), oscillating with
exploiter-gen bumps; train returns flat 0.09-0.21; eval 0W/300D,
0 promotions. The baseline now accumulates and the critic
converges slowly — but 15 gens didn't convert to policy wins.
Closing experiment: 30-gen combo (continuity + vf_coef 4.0 +
shaping + batch-norm, seed 123) running in /tmp/azcombo.

## Critic-fittability test (2026-10-25, /tmp/criticfit.py)

Supervised value-only fit on 1547 random-policy rows: whole-net
v 1.27 -> 0.60 (fits, unstably); head-only stuck ~1.0. So the
architecture CAN represent E[return|window] but the LINEAR head on
a thrashed trunk cannot — and in PPO the shared trunk is thrashed
by noise-dominated policy gradients (50x stronger than the value
gradient). The critic never gets stable features, advantages stay
noise, loop stalls. Testable fix: vf_coef 0.5 -> 4.0 (flag only).
Probe v4 next.

## Shaping design (superseded: implemented + probed, see above)

Potential-based food approach, training-only (policy stays ant-local):
Phi(s) = -dist(ant, nearest visible food)/scale, reward F = GAMMA*Phi(s')
- Phi(s), computed offline in rewards.py from replay food positions +
record trajectories (Ng et al., policy-invariant). Fires every step the
ant moves relative to food; the critic can learn it from windows
(food is IN the window), breaking the chicken-and-egg: approach ->
more pickups -> sparse food signal grows. ~20 lines + tests.

## Launching a run (dashboard progress)

Write `ml/archive/run_plan.json` before starting, e.g.
`{"target_gens": 30, "label": "seed 7 baseline"}`: the dashboard
Run card then shows gen N of target, average pace over the last 5
gens, and ETA. Generation history lines carry started/finished
timestamps and per-gen duration. Replays name the bots after their
checkpoints (`g004.py` vs `g000.py`), staged per side. The bot is
AlphaAnt (`bots/alphaant`, `AlphaAnt.py` + `AlphaAnt.bot`).

## 30-gen training run, seed 7, defaults (2026-10-25)

Status: DAMNING. Returns flat 0.15-0.18 all 30 gens, eval 5W/595D
(99.2% draws), zero promotions, champion stuck at g000. Only wins:
gens 1/3/4 (early) + one at g024; gens 5-23 and 25-30 unbroken
draws with margins exactly 0.0. 15 + 30 gens across two seeds now
show time alone does not break the plateau: the loop is mechanically
perfect and learns nothing measurable after gen ~4. Next lever per
roadmap: decisive-weighted PFSP. Archive: ml/archive (seed 7).

## 15-gen run on the full new machinery (seed 22, exploiters +
   held evals + margins)

Returns flat 0.16-0.18 all 15 gens, 0 promotions, eval 2W/148D.
Both wins came from exploiters (gens 9, 12: 1W/9D, margin +0.3);
mirrors drew everything else with margins exactly 0.0. Per-duel
margins (kept in duel order) showed each +0.3 is ONE +3 duel, and
on DIFFERENT held maps — the champion has small per-map holes and
fresh inits find them. Exploiters are currently the SOLE source of
eval signal. Landed on this evidence: duel-ordered per-duel margins,
eval map rotation by generation (10 duels had left 2 of 12 held maps
unevaluated forever), exploiter badge on the dashboard.

## A/B: base vs deep + 10-gen signal run (paired seed 21, 250 turns)

No separation at 3 gens; extended to 10v10. Base: 0.136->0.178
(noisy +0.04), eval 3W/97D. Deep: 0.174->0.147 (drift -0.03),
eval 2W/98D. Weak evidence for base on trend and level, but both
inside noise with all-draw evals: the arch question stays open
until margins/exploiters provide a working judge. The loop is
mechanically perfect (full batches, falling in-gen loss, sane KL)
and strategically stagnant. Per research (AlphaStar league, Hide-and-
Seek, chess variants): the fixes are exploiters, decisive-weighted
PFSP, and shorter curricula. Draw-as-loss was considered and
REJECTED: under per-minibatch standardization a constant draw
penalty washes out; only return variance trains. Landed: exploiter
generations (every 3rd gen fresh-inits vs champion, same rule;
live-fire validated) + score-margin logging (draws hide progress;
margins show it first).

## Next: decisive-weighted PFSP (designed, not built)

Plain win-rate PFSP is constant under 95% draws. The fix needs real
draw counts, but record_result folds draws into 0.5/0.5, so the matrix
stores only [wA, wB]. Design: extend matrix entries to [w, l, d],
migrate old archives (d = 0 preserves current behavior), weight
opponents by (1 - draw_rate) x f(win_rate) with fallback to
lowest-draw-rate when all win-rates tie. Touches record_result,
payoff_matrix, nash_mixture, win_rates + a migration; sizeable,
so it waits until exploiters show whether fresh blood suffices.

## Next: eval map rotation offset (bug, not built)

With 12 held maps and 10 eval duels starting at pool[0], maps 10-11
are never evaluated. Fix: offset the rotation by generation index
(start = gen_index % len(pool)) so all held maps cycle into evals.
