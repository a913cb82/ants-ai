# Ideas

Doctrine: estimate first, refine later. Size trades update count
against looks per update. Early slots cut `sigma`. Late slots fix bias.

## Backlog

Status is `open`, `trying`, `done`, `dropped`, or `parked`.
A refinement is a new row. Leave old rows as they were.

| status | idea |
|---|---|
| done | Duel the closest `mu` (baseline). |
| dropped | Duel the highest `sigma` opponent. |
| dropped | Duel the strongest pool estimate. |
| open | All duels versus mixed FFA schedule. |
| trying | Champion split: 3 duels then FFA bulk (boundary 24). |
| done | Full-budget FFA-10 versus closest mus (bold: 3 updates per bot). |

## Bold lines

Two misses in a row (sigma duel, strongest duel) force a bold idea.
Bold line 1 (2026-10-03): comparison efficiency beats update count.
One 10-player game buys 9 pairwise looks for 10 slots; duels buy 1 look
per 2 slots. Test the size-axis endpoint first (all FFA-10), then mix.
Judge after iteration 5: confirmed. Duels-first mix (16.64) beats pure
FFA-10 (20.39) beats the mirror schedule (22.04). Order matters more
than the mix; bulk updates need an already-positioned `mu`.
| done | Duels first, then FFA with late budget. |
| dropped | Size from `budget_left`: big games early, duels late. |
