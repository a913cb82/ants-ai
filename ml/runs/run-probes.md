# Run: probes (60-turn, one mechanism each)

Campaign of short probes on /tmp archives (seeds 99/123), each
testing one link of the seed-7 failure chain.

- probe-60: 60-turn horizon alone. Verdict: flat (v 0.81-1.00,
  120/120 draws). Time alone doesn't break draws.
- probe-stack v1/v2/v3: potential-based food-approach shaping
  (symmetric, same-turn-only, scale 1.0). Verdict: signal fires
  (food mass appears), but v stays flat, 0 wins alone.
- probe-vf (vf_coef 4.0): stronger critic weight. Verdict: no
  sustained drop (0.92-1.03). Coefficient isn't the lever.
- probe-critic (/tmp/azlong, 15 gens): critic.json persists across
  gens. Verdict: PARTIAL — v floor 1.00 -> ~0.77, but returns flat
  0.09-0.21, 0W/300D. Continuity helps, doesn't convert.
- Combo-30 (/tmp/azcombo, shaping + batch-norm + continuity,
  vf 4.0): v oscillates 0.67-0.98 around ~0.85, returns flat
  0.09-0.21, eval 1W/599D, 0 promotions.
- Shipped from probes: APPROACH shaping, batch-level advantage
  normalization (event minibatches stay large, noise stays small),
  persistent critic, 60-turn fast probes.
- Verdict: no single mechanism unstick learning; critic moves,
  policy never converts. Actor audit (later): 0.006 displacement
  vs 0.03-0.06 critic — the freeze is real and unexplained by any
  of these.
- Next: imitate competence instead of bootstrapping from random
  (BC-from-pros), split the critic trunk.
