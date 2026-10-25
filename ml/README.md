# AlphaAnt: self-play loop

Train an Ants bot the AlphaZero way: mirror self-play, policy-gradient
updates, scripted promotion. No external opponents, no human judgment.

## Why not vanilla AlphaZero

| AlphaZero assumption | Ants reality | Adaptation |
|---|---|---|
| small discrete actions | `5^N` joint moves | factorized per-ant policy, shared weights, symbolic collision resolution |
| full observability | fog of war, simultaneous moves | local 6-channel window, masked to the ant's sight circle |
| fast simulator + MCTS | 1000 ms turn, subprocess engine | no search; CNN proposes, masks dispose |
| win/loss reward | score + survival + hills | dense shaping + terminal outcome, both discounted (`ml/rewards.py`) |

## Architecture (clean split)

| Layer | Owns | Must not know |
|---|---|---|
| `bots/alphaant/model.py` | network shape, masking, act/sample, save/load | game, training |
| `bots/alphaant/features.py` | actions/offsets, window encoding | policy, training |
| `ml/grid.py` | toroidal math (stdlib only) | everything else |
| `ml/game_if.py` | engine games, staging, replay/record formats | torch |
| `ml/rewards.py` | (game, records) → discounted returns | torch, engine |
| `ml/algorithm.py` | REINFORCE step on masked log-probs | ants, replays |
| `ml/archive.py` | population, payoff matrices, PFSP, Nash, Wilson | torch, engine |
| `ml/train.py` / `ml/evaluate.py` | training loop / eval duels | promotion, files |
| `ml/selfplay.py` | wiring + scripted promotion | (thin) |

Policy shape swaps touch exactly one file (`model.py`); algorithm
swaps touch one file; the game interface never imports torch.

## Generation loop (each generation = fully automated)

1. **Sample opponents** from the eval matrix, PFSP-lite: mostly the
   opponents that beat the champion, plus a mirror fraction. Never
   anything outside the population.
2. **Train.** Challenger (champion copy) plays both slots, records
   `{turn, loc, dest, action, window, legal}`, prices with
   `rewards.compute_returns`, REINFORCE step (standardized
   advantages, persistent Adam, grad clip, entropy bonus).
3. **Evaluate.** Greedy duels, alternating slots. Promotion needs
   both: Wilson lower bound on the win rate clears 0.5 AND Nash mass
   ≥ champion's. Draws count half. Train games never vote.
4. **Publish** (only on promotion): champion pointer, rated
   `weights.json`, git commit.

```sh
.venv/bin/python ml/selfplay.py --train-games 4 --eval-games 20 \
  --turns 50 --archive ml/archive --no-commit   # dry run
```

`ml/archive/` (gitignored) holds every checkpoint, both matrices, and
the last report. `bots/alphaant/weights.json` holds only the
current champion — the rated phenotype, and the only weights in git.

## Reward system (landed)

- **Source of truth**: the replay (food gatherer + turn, full order
  strings, hill raze turns) plus the bot's decision log.
- **Credit**: food → adjacent ants (`0 < d2 <= spawnradius2`; the ant
  ON food gathers nothing per `nearby_ants`); kills → ants within
  attack radius (`0 < d2`); deaths → the dead ant; raze → the ant on
  the hill; lost hill → team-shared. Every event splits across its
  credited ants; one food is worth `FOOD` total.
- **Discount** (`GAMMA=0.97`, `WIN/LOSS=±5`): everything, uniformly —
  dense awards walk back along the credited ant's replay path, team
  awards and outcome reach every earlier decision.
- **Diagnose**: `rewards.decompose(game, me, records)` shows
  undiscounted mass per category — read it before tuning magnitudes.

## Population (AlphaStar-shaped, our scale)

- Frozen checkpoints + manifest; train matrix (diagnostic) vs eval
  matrix (canonical). Laplace prior: unplayed reads as 0.5.
- PFSP-lite sampling and Nash mixture read eval only.
- Every Nth generation can be an exploiter (fresh init, trains only
  against the champion) instead of a champion copy.

## Status

CNN policy + PPO loop landed (clipped surrogate, shared-trunk value
head, per-minibatch standardized advantages; Monte-Carlo targets,
no GAE — see `ml/algorithm.py`). First automated generations ran
clean (trained, evaluated, correctly held the champion on sub-bar
evals). Open: learning-signal validation over several generations,
exploiter phases, GAE if the value baseline proves insufficient.

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

Probes/fixes, simplest first: 60-turn horizon (gamma contrast ~330x)
-> whole-batch advantage norm (preserve event magnitude) -> denser
shaping only if those fail.

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

## Next: per-duel margins (designed, not built)

evaluate.py keeps only mean_margin; per-duel margins are discarded.
Logging the list (10 ints per gen) would show whether a +0.3 mean is
one +3 game or three +1s — the difference between a fluke and a
repeatable edge. Cheap; do it when margins start moving.

## Next: eval map rotation offset (bug, not built)

With 12 held maps and 10 eval duels starting at pool[0], maps 10-11
are never evaluated. Fix: offset the rotation by generation index
(start = gen_index % len(pool)) so all held maps cycle into evals.
