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
- Results: pending.
- Verdict: pending.
