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

## Rung 3 map list (18 train + 2 held)

Rung 1 + rung 2a-d stay in the pool (early skills keep training;
nothing graduates out). Plus 14 random_walk boards: _32, _54, _72,
_60, _27, _31, _03, _13, _37, _15, _45, _08, _20 (all under
tools/maps/random_walk/). Held out: rung 1 (retention exam on the
simplest board) and one random_walk board (every 13th). Train games
rotate across the pool by generation so every board sees play.

## Notes

- Every curriculum board is 180-degree rotationally symmetric
  (players swapped), asserted by gen_rung2.py for rung 2.
- Rung 1 history: plain open board first, then symmetric hills plus
  four single water tiles (v2). Rung 2 pond grew 2x2 to 8x2 tall
  lake, lakes 3x3 to 4x4, on review.
