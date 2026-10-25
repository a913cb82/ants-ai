# Map curriculum

Graduated boards for the self-play league. Each rung adds one kind
of difficulty. Graduate on mastery, not on a schedule.

## The ladder

| Rung | Maps | Tiles | New skill | Status |
|------|------|-------|-----------|--------|
| 1 | rung1_open (tiny + water, hills in sight) | 192 | contact: meet, fight, win | done, mastered |
| 2 | rung2a/b/c/d (open, pond, gap, lakes; hills beyond sight) | 384–560 | scouting + water routing | in play |
| 3 | 14 random_walk boards + rung 1 + rung 2 pool (19 total) | 192–5200 | scale + variety, no forgetting | queued |
| 4 | full pool (148 maps, mazes included) | up to 24k | corridors, chokepoints, full generalization | queued |

## Graduation rule

Advance when two promotions land inside any ten-generation window
(mastery: a challenger repeatedly proves stronger on this rung), or
after forty generations on a rung regardless (anti-stall cap: if the
rung stops teaching, diagnose instead of advancing blind). A rung
that loses peace (back to all-draws) or stops promoting is a signal
to diagnose the rewards, not to graduate. Graduation is manual per
round for now; automate once the ladder stops changing.

## Rung 3 map list (9 boards, all train)

Rung 1 + rung2a-d (early skills keep training every ~2 gens via
rotation) + 4 generated mid-boards: rung3a open 24x40 (960),
rung3b twin 5x5 lakes, rung3c chokepoint gap 28x44, rung3d twin
6x6 lakes 32x52 (1664). Under 13 maps: no held-out split, evals
run the train pool (promotion judges mastery; graduation to rung
4 tests transfer). Random_walk boards parked for rung 4 — 3k+
tiles never meet in 150 turns (round 10: zero decisive).

## Notes

- Every curriculum board is 180-degree rotationally symmetric
  (players swapped), asserted by gen_rung2.py for rung 2.
- Rung 1 history: plain open board first, then symmetric hills plus
  four single water tiles (v2). Rung 2 pond grew 2x2 to 8x2 tall
  lake, lakes 3x3 to 4x4, on review.
