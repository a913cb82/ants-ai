# Fleet review synthesis (8 lenses, 2026-10-28)

Read-only review fleet. Minimal priors: each lens got its corner +
one question, no program history. I verified every load-bearing local
fact against the repo before believing it. Verdicts: CONFIRMED /
PLAUSIBLE / FABRICATED.

## Verification table

| Lens | Hottest claim | Verdict |
|---|---|---|
| ppo | advantages recomputed from current value net per minibatch × `epochs` loop → adv evaporates mid-update (`algorithm.py:220-280`, `train.py:157-158`) | CONFIRMED (code-fact) |
| ppo | per-batch z-scored value targets + persistent critic = scale churn | PLAUSIBLE (math certain, attribution not) |
| ledger | exploiter DEATH +3.0 pays mutual kills +6 (`rewards.py:61`) | CONFIRMED arithmetic, REJECTED as "fix": file :41-47 documents it as deliberate, reviewed, kept (winning aggression, not suicide) |
| capacity | conv RF 9x9 < 15x15 window; "whole window" docstring false (`model.py:39`) | CONFIRMED |
| capacity | net not the bottleneck (twin-lineage split = value-starvation) | PLAUSIBLE (65% self-rated; imitation probe decides) |
| features | in-circle sight filled from player-union sets, no per-ant raycast (`features.py:~127`) — ghost contacts through lakes | CONFIRMED (docstring's own tier logic) |
| features | own_sight ~constant; corners conflate unknown with land | CONFIRMED by inspection |
| actions | blocked intent erased (only post-mask action logged); `reserved=set(mine)` forbids swaps; timeout logs fake stays (`AlphaAnt.py:89-140`) | CONFIRMED (all three, comments confess the third) |
| redteam | Nash 0.985 on non-champ g1234; champ-only exam + Laplace wash | CONFIRMED (recomputed exactly) |
| redteam | cites held exams g1240/g1246; crown burst at gens 1174-1191 | FABRICATED (ids don't exist; real burst 1202-1228) — math kept, citations burned |
| alphastar | ME/LE split, reset-on-crown, league exam | PLAUSIBLE (paper-faithful; maps to our failure mode) |
| alphastar | "already-designed draw-aware PFSP weight" in README | CONFIRMED real (`ml/README.md:343`) — my suspicion was wrong |
| explore | asymmetric mini-tasks; caveated RND | NOVEL (nothing in program history) |

## Convergence (≥2 lenses, unprompted — strongest signal)

1. **Terminal broadcast dominates** (ppo#3 + ledger#3/#5): undiscounted ±5
   to every ant-record drowns dense mass; lazy-ant problem.
2. **Champ-only exam is the wrong test** (alphastar#3 + redteam#2): promote
   vs a league jury, not one incumbent.

## Filtered through existing evidence (fleet couldn't know; synthesis can)

- Draw-penalty default-ON (ledger R4, explore#1): FAILED twice, valid
  control. Closed.
- Spoiler league (explore#2): flatlined, folded. Closed.
- Blind widen (capacity itself says no): parked with bar.
- Turn-phase/global channels (features#3/#4): REJECTED — violates the
  ant-local founding constraint (reviewer wasn't told; the constraint
  stands until a result forces it).
- Held-out train/exam split (redteam#5): tension with coverage doctrine;
  noted, not adopted.

## Ranked next-stage work (see plan-next.md for staging)

0. Adv-freeze + per-epoch pg logging (S) · imitation probe (S, offline) ·
   ghost-chase replay audit (S analysis).
1. League/jury exam (M) · terminal cap/discount (M).
2. Intent+blocked logging (S), swaps (M) · force-ratio channels (S-M) ·
   ME slot (M) + reset-on-crown (S) · outcome-neutral challenger
   combat (S) · RF dilation, ablation-gated (S) · asymmetric mini-tasks (M).
