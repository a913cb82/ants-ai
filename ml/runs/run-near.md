# Run: train at the frontier (round 39) — PLAN

Round-38 forensics: ALL 120 train opponents were 20+ gens stale.
Two compounding stalenesses: (1) flat-rate PFSP over 300 members
degenerates to uniform-over-history in a draw regime (ancients
teach beating ancients); (2) the main trains against the CHAMP's
rivals — correct when challenger == champ-copy (reset era), stale
under lineage (lineage-era bug).

- Hypothesis: training against recent rivals + champ (window 15)
  makes every train game informative — gradients point at
  champ-beating, not weakling-beating. Evals (vs champ, draws)
  should start moving: wins instead of draws.
- Config: sample_opponents gains window=15 + include=(champ,);
  blind fallback mirrors the student (never raids history).
  train_generation takes student (main for challengers, champ for
  exploiters). Same 8 boards, 150 turns, same formula otherwise.
- Acceptance: train opponents recent (verify in games.jsonl);
  eval draws convert to wins; promotions resume.
- Success criteria: >= 1 promotion OR eval raw W up decisively
  vs rounds 34-38 (~15-23%).
- Failure criteria: 0 promos + evals still draw at the same rate
  -> the mismatch wasn't the blocker; the disease is in the
  update itself (pg cancels structurally) -> persistent
  exploiter lineages (counter-styles need time) or capacity.
- Results (g608-g622): ONE PROMOTION — g611 over g513 (0.625,
  nash 1.00). Drought over at 94 gens. Verification: train
  opponents 40/40 ancient -> 112/120 recent + 8 mirror + 0
  ancient. Eval draws 87% -> ~40%; raw wins 27/26/17 per block
  (was ~5). v healthy, kl anchored on challengers.
- Verdict: MISMATCH FIXED, decisively. The update works when fed
  informative opponents; the disease was stale rivalry, not the
  learner. Consolidate (round 40 same). Hygiene note (not a
  chase): runner saw g608 eval double-logged lines + a recount
  mismatch (W7/D7 vs W8/D5, same wr) — promotion math comes from
  evaluate()'s in-process numbers, not jsonl parsing; revisit in
  a hygiene pass, not mid-regime.
- Results (g623-g637): 0 PROMOTIONS. Knocks at 52.5% (g626/
  g627, Wilson-blocked). Evals flat ~.40 effective. Champ g611.
  Key forensic: champ sampled 0/60 train games — include=() only
  whitelists, and Laplace 0.55 loses to beat-you 1.05 every draw.
- Verdict: DRY-BUT-ALIVE by the tripwire rule (knocks = alive),
  so no plateau — but the 0/60 is a REAL bug in the frontier
  design, fixed structurally: slot 0 of every train batch is now
  the champ, guaranteed (_train_opponents). This completes round
  39's fix (whitelist ≠ slot), not a new variable. Round 41
  tests the completed design; same tripwire (knockless dry =
  plateau -> persistent exploiters).
