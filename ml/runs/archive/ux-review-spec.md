# Dashboard UI/UX spec — final beauty pass (2026-10-31)

Source: `uxreview` subagent report (read-only review of `ml/dashboard.py` at
1690 gens / 1733 members / 80,438 games; no screenshot tooling on machine —
review from code + served HTML + live JSON). Evidence: `/tmp/uxshots/`
(page.html, snap.json, member/empty samples). Open questions answered by
lead inline as A1–A6.

Standing constraints (challenge only with justification): stdlib-only, no
deps; single-file `ml/dashboard.py` (STYLES / SCRIPT / render_page
sections); system font stack; desktop-first (keep the 900px breakpoint
working, don't regress keyboard/AT); no new ports; live-poll tick stays
(5s active / 15s idle); no training-code changes.

New direction (lead): light-mode colour scheme; lay out for 16:10
(2560×1600 and 1920×1200); rethink every table's layout/sizing/columns;
display each table's data as compactly and visually as possible.

## P0 — looks broken or cheap, fix first

- P0-1 First paint is an empty shell (FOUC-by-fetch): server-render first
  paint into the HTML — champion/gen/game counts, status line, first 50
  game rows + first pages of generations/population inline via
  `snapshot(base)` (~0.2s server-side). JS polling keeps updating.
  Fallback if rejected: skeleton shimmer rows so layout doesn't jump.
- P0-2 Full ~1.8MB snapshot re-polled every 5s: add `?since=`/ETag-style
  short-circuit — server returns `{"unchanged":true}` when
  games.jsonl/history.jsonl/matrix.json mtimes match (caches already stat
  them; expose max mtime in snapshot). Also: drop unused `margins[]` from
  per-generation payload OR render them (see P2-4); round
  train_return/train_loss server-side.
- P0-3 Population (1733 rows) + Generations (1690 rows) fully re-rendered
  on every change; member `<select>` has 1733 options: paginate both tables
  client-side from the held `S` object (100/page, same pager pattern as
  games, zero new endpoints); preserve scrollTop/selection/focus (patch
  only changed page slices, mirror the `lastGames` guard); replace member
  `<select>` with text `<input list="member-list">` + `<datalist>`
  (native autocomplete, keyboard-friendly) + keep hash sync; extend the
  hover/focus guard to skip re-render of any table being interacted with.
- P0-4 `?member=` deep links silently ignored (filter is hash-only):
  on load, seed filter from `?member=X` when valid, then `replaceState`
  to canonical `#member=X`; invalid values show the "no games" empty
  state + a "clear filter" link (currently the only escape is reselecting
  "all members" — add the link regardless).
- P0-5 Run header reads "gen 1690 / 1689": when finished >= target render
  `gen 1690 · target 1689 reached` and suppress ETA. (A5: display-only
  fix; the loop is allowed to overshoot.)
- P0-6 Timestamps are time-of-day only: render `MMM d, HH:MM` for anything
  older than today (HH:MM for today), full ISO in `title`.
- P0-7 Maps table's largest bucket is literally "unknown": label
  `unlabelled (pre-map logging)` + one-line footnote; pin that row last.
  (A3: nulls are legacy pre-map-logging rows, not a logging bug.)
- P0-8 Games table header scrolls away: add `table-tall` to that scroller
  (one word); verify no double-scrollbar regression.

## P1 — usability gaps

- P1-1 Jargon wall (`chal`, `γ0.97`, `150t`, `draw=½`, `nash`,
  exploiter/spoiler): one `<details>` toggle per section (zero JS) with
  2–3 plain sentences; rename in-table (`chal W-D-L` → `challenger W-D-L`,
  `150t` → `150 turns`, `γ0.97` → `γ 0.97`, `draw=½` → `draws count ½`).
  (A1: audience is the lead mid-run; keep density, explain cheaply.)
- P1-2 Nash column is 1673 dead bars: default-sort population by Nash
  desc, "hide zero-Nash" checkbox default-on, % with one decimal, clamp
  nonzero bars to ≥1px.
- P1-3 Generations table has no filter; games filter doesn't propagate:
  member input also filters generations (challenger OR champion),
  client-side, pager reset, `showing N of 1690` count line.
- P1-4 Charts decorative at 1690 points: min/max-envelope downsampling per
  pixel column; x labels first / champion-change gens / last; y-axis
  titles in gutter; delta chip vs median-of-last-10 with tooltip; cap aria
  description to `N points, min x, max y, last z`. (Canvas plot helpers
  now include frame/lineInto/plotLines/plotBand/plotBars/plotDual/plotStrip
  from the curves board — extend, don't duplicate.)
- P1-5 Number/unit consistency: counts integers, rates 1dp, losses 3dp,
  returns 2dp; durations always tagged (`220 s`, `3m 40s` past 60s);
  margins suffixed `pts` + `title`; define "return" once in curves
  `<details>`.
- P1-6 Replay affordance cryptic: label `gen g1732 · eval 15 →`, keep
  title; keep `target="_blank"`; verify replay page sets `<title>` so
  tabs are distinguishable. (A4: side-by-side comparison is the workflow.)
- P1-7 Poll feedback is a whisper: status pill next to live toggle —
  `● live · refreshed 3s ago` / `○ paused` / `▲ stale 40s` (stale when age
  > 2× interval), text + color, never color alone.
- P1-8 Keyboard/semantics: real `<caption>` + scoped `<th>` (games table
  abuses `<caption class="legend">` — split caption and legend);
  pager `aria-label`s; keep canvas `role="img"` with shortened label;
  progressbar role + aria-valuenow/min/max.

## P2 — polish

- P2-1 Flat hierarchy: merge champion + run + status into one hero banner
  (`★ champion g1719 · gen 1690/1689 · progress bar`); other stats to a
  compact strip; section titles 14px with 40px top margin.
- P2-2 Legend cruft: ≤1 line per legend; rest into P1-1 `<details>`;
  dedupe the doubled empty-state strings.
- P2-3 Bars need scales: `title="promotion threshold 0.50"` on the marker
  + tiny `▲ 0.50` header note; round nonzero widths up to ≥1px.
- P2-4 Ship or drop margin data: render a per-generation 20-cell W/D/L
  dot strip answering "close or blowout?" — or stop shipping per P0-2.
- P2-5 Provenance footer: `archive … · N games · polls 5s/15s · AZDash`.
- P2-6 Status color discipline: held stays amber everywhere incl. bar;
  draws neutral-blue; document the badge palette in one CSS comment.
  (A6: keep held/promoted badge semantics; clarify inside details.)

## Section order + above-the-fold (16:10)

Fold ≈ 700px content at 1440×900, `.wrap` max 1200 (recheck at
2560×1600 and 1920×1200 — hero + strip + first chart visible without
scrolling):
1. Header + hero banner (~150px). 2. Stat strip, compact (~90px).
3. Training curves side-by-side (keep 220px height; fold cuts mid-chart).
4. Generations (newest first, paginated, member-aware). 5. Recent games
(filter + pager) as its drill-down. 6. Population (Nash-sorted,
zero-Nash hidden). 7. Maps + provenance footer.

## Light-mode + table design lens (lead direction, applies to all above)

- Light-mode colour scheme: paper background, ink text, one accent (keep
  close to the current blue), semantic badge colors that survive on white
  (win green / loss red / draw neutral-blue / held amber / train gray /
  eval distinct); zebra or hairline rows; muted secondary text ≥ 4.5:1.
- Every table gets a layout pass: column widths that fit content (ids,
  numbers right-aligned tabular, no wrapping on scores), sticky headers
  everywhere, density that shows ≥15 rows per card without scrolling where
  possible, truncation with `title` for long ids/paths.
- Compact visual data per table: promotion-threshold marker + Wilson bar
  in generations; W-D-L dot strips (P2-4); Nash share bars that paint at
  sub-1% (P1-2); per-map train/eval mini-bars; hero progress bar with
  target marker.
