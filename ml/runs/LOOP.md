# LOOP — pausing and resuming the indefinite runs

The training loop is indefinite: one idea per round, 15 gens per
round, verdict → next round, forever. This file is the bookmark.
If you are resuming, read State then Resume and go.

## State (as of pause, round 112 partial)

- Branch: `ml/alphastarzero`. Repo: `/home/abrai/projects/ants-ai`.
  Venv: `.venv/bin/python` (Python 3.12, torch CPU). Run all
  commands from the repo root.
- Archive: `ml/archive/`, 1689 history entries, champ **g1719**
  (main-line crown, complete: total .625 / slice .625 / jury .75).
- Round 112 stopped at 8/15 (user pause): gens g1682–g1689 stand
  as committed history, **no verdict**. Never complete a partial —
  resume with a fresh 15-gen round from head.
- Config fingerprint (identical since round 102, tax off since 102):
  seed 456, turns 150, train-games 30, workers 12,
  train-draw-penalty-every 0, NO --water-stall-tax (legacy rewards),
  champ-share 0.25, exam-jury-size 4, temp 2.0, entropy-beta 0.05,
  kl-anchor-beta 0.0. Live code: swaps + honest logging +
  force-ratio (9ch) + LOS F1 + dormant ch9. Base reward scales.
- Pool (frozen 9-board, HOLD per round-110 review):
  rung2a/b/c/d/f/g/h/i/j (open, pond, gap, lakes, mapgen1-3,
  cave1-2). No rung1, no q/r/s, no passengers.
- Dashboard: `.venv/bin/python ml/dashboard.py --port 8090
  --archive ml/archive` (read-only, stdlib only).
- Standing meters: `ml/probe_dwell.py LABEL replay...`
  (shoreline dwell vs 4.8–5.0% baseline band).
- Last regime: 8 crowns in 10 rounds (staircase), then g1660 held
  45, then double turnover to g1719. Open question for the next
  round: does g1719 harden or does the staircase take a 9th?

## Resume (fresh round from head)

1. Pre-flight (all must pass, else STOP and report):
   - `.venv/bin/python -c` history count and champ id from
     `ml/archive/history.jsonl` + `ml/archive/champion.json`
     (expect continuity from State above, not the old numbers).
   - `ls` all 9 pool maps. `git status` clean, no `selfplay.py`
     running. ` free -g` sane (rounds OOM above ~13GB anon).
2. Write `ml/archive/run_plan.json`:
   `{"target_gens": <head+15>, "label": "round<N>: <question>"}`.
3. Spawn ONE runner subagent per round with this brief skeleton
   (copy standing clauses verbatim; only the QUESTION/falsifier
   and the champ change per round):
   - Archive CONTINUES from head; VERIFY count+champ first.
   - The exact command below, 15 times sequentially, no pipes
     around selfplay, exit-code check after each gen; first
     non-zero exit → STOP, report verbatim + dmesg tail.
   - Never write under `ml/runs/`. Never touch code/tests/maps.
   - Standing: exploiters CAN promote; held = Wilson-held. Every
     knock/promo reported as total eff + champ-slice + juror-split
     (slice derived from games.jsonl challenger-vs-champ rows).
   - Report: per-5-gen blocks (promos + role/parent/line; main
     evals W/D/eff + margins + three numbers; line-A trajectory;
     per-map train conversion all 9; mean_return + per-epoch
     pg_abs; v_loss[0] vs [-1]; knocks ≥.50; decisiveness;
     wall-clock total + avg s/gen) + one EXPLICIT VERDICT line
     chosen from the round's falsifier menu.
4. On result: append verdict to `campaign.md` (Results + next),
   update `QUEUE.md` trying, commit notes. Next round.

## The exact command (copy character-for-character)

`.venv/bin/python ml/selfplay.py --archive ml/archive --seed 456
--turns 150 --train-games 30 --workers 12
--train-draw-penalty-every 0 --champ-share 0.25 --exam-jury-size 4
--maps tools/maps/curriculum/rung2a_open.map
tools/maps/curriculum/rung2b_pond.map
tools/maps/curriculum/rung2c_gap.map
tools/maps/curriculum/rung2d_lakes.map
tools/maps/curriculum/rung2f_mapgen1.map
tools/maps/curriculum/rung2g_mapgen2.map
tools/maps/curriculum/rung2h_mapgen3.map
tools/maps/curriculum/rung2i_cave1.map
tools/maps/curriculum/rung2j_cave2.map
--temperature 2.0 --entropy-beta 0.05 --kl-anchor-beta 0.0`

(No `--water-stall-tax`: the shaping tax was acquitted in round
101 and stays off. Re-enabling it is a round variable, not a
default — it needs its own falsifier.)

## Pause (how this file got written)

1. Cancel the runner; note archive head + champ + completed gens.
2. Append the partial to `campaign.md` (no verdict, ever).
3. Set `run_plan.json` to `{"target_gens": <head>,
   "label": "paused: <what> (<done>/15, no verdict)"}`.
4. Update `QUEUE.md` trying + this file's State, commit.

## Doctrine pointers (unchanged by pause)

- Fixed exam, discard bar, exam integrity, strike accounting
  (continuity-only; ladder spent): README.md.
- One variable per round; falsifier per round; parallelism in
  construction, never in activation: QUEUE.md open rules.
- Map pool frozen 9-board; rung rules: tools/maps/curriculum/README.md.
