# PLAN: AlphaStar-exact continuous league (replaces generations + throne)

Status: APPROVED incrementally (user decisions per phase) and LIVE since
2026-10-31 (2000-tick first live run). Phases section is the record.
Supersedes: `LOOP.md`, rounds machinery, promotion/exam/jury/graft/strike doctrine
(frozen as record, not deleted). Archive, matrix, checkpoints, Elo: carry over.

## Why

Closed-population relative ratings sawtooth forever (proven: 1690 gens, med gap
dev 1.1 to seed choice, erosion ≈ jump). AlphaStar's rising curves come from
fixed references + a growing pool, not from better math. We imitate the
mechanism exactly, translated to one machine. The only absolute progress
signal in a mirror-only project is performance vs frozen internal anchors.

## Target architecture

Four persistent learners, equal shares, deterministic round-robin
main → ME → LE-A → LE-B (25% each; equal-per-learner is the absence of a
tuning choice — their compute split is unpublished).

| Learner | Init | Opponent rule (PFSP, no Nash anywhere) | Objective | Reset |
|---|---|---|---|---|
| Main | g1732 weights + banked Adam (main.json head = freshest trained state) | 50% squared-weighted historical (seeks counters); else variance-weighted; newcomer boost ×5 while <10 games | none (trains forever) | NEVER |
| ME | g000 weights (+pad to current arch, tested path) + fresh Adam | locked onto main while win-rate > 0.1, else variance-weighted easier historicals | sustained >60% over last 40 vs main → freeze copy in pool (relabel snapshot, no extra copy step)  | to g000 on admission only (no stall rule since 2026-11-02) |
| LE-A/B | same g000 init (independent runs) | linear_capped over all historicals (seeks any hole)  | sustained >60% over last 40 vs pool → freeze + reset | to g000 on admission only (no stall rule since 2026-11-02) |

Invariants (go in LEAGUE.md verbatim):
- One game trains exactly one learner; opponents are always frozen snapshots.
- Anchor games carry no gradient (measurement only — the mirror-only
  translation of their external test matches).
- Same net, same PPO, all roles; only diet (opponents) and job (objective) differ.

Training cadence: micro-batch PPO every 8 own-games per learner; snapshot
every 80 own-games (≈ 1 old gen, keeps history comparable). No cap, no cull:
every snapshot is a permanent member (their answer to bloat is weighting,
not removal; our growth rate is unchanged from today). Newcomer boost:
members with <10 total games get ×5 sampling weight until evaluated
(self-limiting; ancient well-evaluated weaklings get ~zero by weighting
alone). Storage is the only bound — see falsifiers.

Anchor ladder (the progress curve): g000 + 5 spread main-chain snapshots
(loaded with padding), 2 games each per main snapshot, no training.
Ship rule: publish main weights on anchor new-high (water mark, no training
privilege — a readout, not a throne).

PFSP weighting functions (implement per mini-AlphaStar pseudocode, TDD-pinned
on synthetic matrices; acceptance = role-appropriate distributions):
- Let p = opponent win fraction vs learner (Laplace-free, unseen = 0.5):
  linear p, squared p², variance p(1−p) (peaks at even = learning-rich),
  linear_capped min(p, 0.5) (no single-nemesis obsession).
- Exploiters invert the direction (weight by own win fraction: seek victims).
- Newcomer boost: members with <10 total games get ×5 sampling weight
  until evaluated (self-limiting; replaces the rare/omitted rule).

## Initialization (day one — verified on disk)

- Pool = all 1733 manifest entries BY DECLARATION. Manifest untouched;
  going-forward snapshots append with league roles. No relabeling, no migration.
- Anchors (frozen, weights verified): g000, g401, g588, g978, g1343, g1532
  (spread main-chain: ~gens 0/400/590/980/1340/1530). Loaded with padding.
- Live learners: main ← g1732 weights + g1732.opt.json Adam (main.json head =
  freshest trained state; g1732's parent g1730 keeps the training line).
  ME/LE-A/LE-B ← g000 weights (+pad to current arch) + fresh Adam.
- New state file `league.json` (main working id, incarnation counters, anchor
  list, scheduler position). main.json/champion.json frozen as record.
- Records: matrix as-is, PLUS one port-only step. Live main gets a fresh id
  whose initial matrix row = union of the main-chain pair-records (traced
  g1732→g000, 751 links; ancestors' rows untouched). Exploiters start with
  empty records (a fresh reset has no games; g000's ancient games belong to
  g000 the pool member, not to them). Going forward: own-games-only
  accumulation; population expands on admission. The union is port fuel —
  it dilutes as fresh games dominate and is never repeated.

## History mapping (nothing lost)

- 1733 checkpoints + parents + matrix (80k games) → the pool, as-is.
  Main chain traced: 751 links g1719→g000 (574 challengers + 176 grafted
  exploiters + g000). g1719/g000 weights + g1732 Adam verified on disk.
- PFSP starts warm: every pool member has a record book (no cold start).
- Elo pass continues unchanged (trajectories get cleaner: no takeover breaks).
- Champion/promotion/exam/jury/grafts/strikes/rounds/Nash-solve: retired.
  Matrix record-keeping stays (PFSP reads it); Nash solve deleted from training.

## File changes

- `ml/pfsp.py` NEW: 4 weighting fns + 3 role policies, pure, TDD red-first.
- `ml/selfplay.py`: scheduler loop replaces run_generation; snapshot cadence;
  admission checks; anchor measurement calls.
- `ml/train.py`: PFSP selection; micro-batch updates; role configs.
- `ml/evaluate.py`: DELETED → small `ml/measure.py` (anchor games only).
- `ml/archive.py`: roles main/me/le/snapshot/anchor; admission log.
  No cap, no cull — removal is forbidden (weighting handles bloat).
- `ml/dashboard.py`: retire throne/promotion/jury UI; add anchor-trend +
  admissions cards; Elo untouched.
- `ml/rewards.py`, `algorithm.py`, bot, engine, maps: UNTOUCHED (byte-identical;
  enforced by diff check every phase).
- Docs: freeze LOOP.md/QUEUE.md/campaign; new `LEAGUE.md` (10 rules:
  roles+shares, PFSP defaults, snapshot K, no-removal, ME bar, LE bar,
  reset-to-g000, anchor list+cadence, ship rule, kill criteria).

## Falsifiers (1 live week)

- Anchor curve non-decreasing; main >60% vs fresh exploiters; admissions
  nonzero; archive growth ≤ historical rate; sampling concentrates
  (top-20 members ≥80% of matches by week 2 — weighting works, no junk churn).
- Full suite green (2 pre-existing failures excepted); training-core diff empty.
- Kill: anchor flat 2 weeks + admission drought → revisit (time-boxed where
  they'd run forever).

## League state and dashboard contracts (defines phases 2–4 interfaces)

league.json (single object, atomically rewritten each scheduler tick):
main working id + micro-batch progress; per-exploiter {id, games,
last-40 window vs target}; anchors list; admissions list
({id, role, at_game, record}); scheduler_pos; snapshot_counter.
New snapshots append manifest rows (role: main-snapshot/me/le/admitted).
Anchor results append anchor.jsonl rows
{snapshot_id, main_id, anchor_id, wins, losses, draws}.
No other new files; matrix/games/history formats unchanged.

Dashboard rework (phase 4 implements; contracts fixed here):
- RETIRE: throne/promotion/jury UI — duel cand/champ framing, knock marks +
  rates, reign strip, champ-slice strikes, exam slices, Nash column, hero
  champion banner, Elo subtitle (rewrite for snapshots).
- KEEP (re-bucketed by K-game interval instead of gen): decisiveness,
  margin bands, train conversion, PG signal + entropy (main-only),
  value slope, maps section, recent games, replays, member table.
- ADD: anchor-trend card (main vs ladder per snapshot — THE progress curve),
  admissions log card, pool-health card (member growth, top-20 sampling
  share, newcomer queue), scheduler-state strip (current learner,
  micro-batch progress, live exploiter records).
- BACKEND: bucket games by interval (order // K) — gen_pair_buckets
  generalizes to interval keys; panel (= anchors from league.json) replaces
  panel_ids; knock/conversion/decisiveness take intervals; member table
  shows role + sampling share instead of Nash; snapshot memo extends
  the _elo_cached pattern. Elo pass itself unchanged (trajectories lose
  their takeover breaks).

## Phases (dependency order; 1–2 parallelizable; nothing live before phase 3)

0. LOCK this plan (approve or amend the labeled choices: shares, K=80, N=8,
   bars 60%/40, anchor set, newcomer boost ×5/10 games;
   stall 400 REMOVED 2026-11-02 (no AlphaStar counterpart).
1. `ml/pfsp.py` + tests. Zero training impact. DONE (59ca5b4).
2. Archive roles/admission log + tests. DONE (3479404).
3. Scheduler + `measure.py`, delete `evaluate.py`; smoke on tiny pool. DONE (b7c162c).
   3b. Per-incarnation member ids (slot-identity bugfix). DONE (fdadbdf).
   Port fixes (union idempotent + main row + live-id exclusion). DONE (5db421b).
4. Dashboard cards swapped (per dashboard contracts above). DONE (d50283b).
5. `LEAGUE.md` (written, ml/runs/LEAGUE.md) + migration runbook; first live week. LIVE.

Fresh start 2026-11-01 (user order: throw away ALL history): pre-wipe
tarball /tmp/league-prewipe-backup.tar.gz (670MB). Kept ONLY the 4 live
weight+Adam sets (learners/), g000.json (reset baseline + floor anchor),
and the 80-map pool. Fresh matrix (empty), manifest (main/me/le-a/le-b +
main0 = frozen current main), empty games/history, no anchor.jsonl,
league.json main_id=main0 anchors=[g000] tick 0 resets []. g000 kept as
infrastructure (exploiters must reset to SOMETHING; random init would
un-train them for weeks) -- one file, delete on veto. Anchor ladder
rebuilds from main0 (g000 floor + past mains). NO port union, NO lineage
seeding content, NO grandfathering anywhere. Training stays stopped.

Migration log 2026-10-31: backup /tmp/league-port-backup/ (matrix,
manifest, history, champion, main). Pool: 80 fresh 2p gen_mixed maps
(seed 456001) at ml/archive/maps-live/ (9-board gone from tree; rung
generators absent from this checkout). Union: chain g1732->g000 (759
links), 1623 pairs / 44701 games, intra-lineage dual-perspective
included. League flags: turns 150, temp 2.0, ent 0.05, workers 12,
seed 456, anchors g000/g401/g588/g978/g1343/g1532. First 8 ticks
green; 2000-tick live run started (nohup, /tmp/league-live.log);
dashboard :8090 restarted live. Resume note: a crashed first run left
league.json behind, so ensure_league skipped the port on retry; the
union was applied manually after (idempotent, merged with new games).
main.json left pointing at g1732 (last frozen main = port source).
