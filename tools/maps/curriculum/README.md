# Map curriculum

Graduated boards for the self-play league. Each rung adds one kind
of difficulty. Graduate on mastery, not on a schedule.

## Toroidal water rule

The board wraps on BOTH axes: every hill-to-hill route exists
twice (each direction around the torus), and columns wrap too —
a single vertical bar only blocks eastward, the westward route
slips around untouched. So: mid-board water must wet both
toroidal routes (central feature plus its wrap-edge twin), or a
barrier must span the full axis WITH its edge twin, sharing one
dry latitude. This rule is asserted by symmetry checks, not by
eyeballing — but dry-short-route review stays mandatory for every
new board.

## The ladder

| Rung | Maps | Tiles | New skill | Status |
|------|------|-------|-----------|--------|
| 1 | rung1_open (tiny + water, hills in sight) | 192 | contact: meet, fight, win | done, mastered, stays in pool |
| 2 | rung 1 + rung2a/b/c/d + f/g/h + 2 small real boards (gen2p_00, gen2p_05) | 192–1600 | bigger ground: scouting, water routing, room to maneuver | in play (round 11; f/g/h join round 12) |
| 3 | full pool: all 148 real 2p maps | up to 24k | corridors, mazes, full variety, no forgetting | queued (needs 2-in-10 on rung 2) |

## Graduation rule

Advance when two promotions land inside any ten-generation window
(mastery), or after forty generations on a rung regardless
(anti-stall cap: diagnose, don't advance blind). A rung that loses
peace or stops promoting is a signal to diagnose the rewards, not
to graduate. Early rungs stay in the pool forever (round 10:
rung-1 held-only forgot combat, peace 0.68 — skills rot without
practice). At full-pool scale, reserve train slots for curriculum
drills (each board trains every ~37 gens otherwise).

## Pool promotion and demotion

Boards move, not just rungs.

- Board promotion (staged -> pool): playable_2p, hills placed, one
clean smoke (runs end to end, no crash) -> joins the next round
as a passenger. Stays if its train-game decisive rate exceeds 10%
over that round.
- Board demotion (pool -> cut): decisive rate under 10% over a
full round -> cut, no second chances for real boards (gen2p_00
3.3% and gen2p_05 5.1% in round 11: cut). Curriculum boards get
one fix attempt first (the toroidal flaw class is repairable),
then the same bar.
- Rung promotion: two promotions in any ten-gen window (above).
- Rung demotion (retreat): a full round under 10% decisive
rung-wide means signal collapse -> retreat one rung and diagnose
before re-advancing (round-10 random_walk at 0%: rebuilt, same
spirit).
- Rung 1 never demotes: it is the contact drill. If even rung 1
goes peaceful, the disease is in the rewards, not the maps —
diagnose rewards, don't touch the pool.

## Notes

- Rung 1 -> rung 2 is MAP SIZE, not hill distance: bigger ground
  forces scouting, routing, and maneuver whether or not hills start
  in sight. Hill-beyond-sight was an early heuristic, not a rule.

- Every curriculum board is 180-degree rotationally symmetric,
  asserted by the generators. Real pool boards are asymmetric by
  design — asymmetry is the skill rung 3 teaches.
- Generated mid-size rung 3 (rung3a-d) DELETED: wrong direction —
  rung 3 is real boards; the one proven map (rung3a open,
  decisive 3-0) survives as rung2e. Generator script removed with
  it; gen_rung2.py remains for rung 2.
- Smallest real boards (~1600 tiles: gen2p_00, tutorial1) draw
  BC-vs-random at 150 turns — passengers under test in round 11,
  judged by the per-map table (decisive or material-margin, else cut).
