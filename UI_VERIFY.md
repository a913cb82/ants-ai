# UI_PASS verify evidence (impl/ui, 2026-10-31)

Worktree `/tmp/impl-ui`, branch `impl/ui`, base `ml/alphastarzero` + spec commit.
Venv `/home/abrai/projects/ants-ai/.venv/bin/python`.
Live archive served read-only; mtimes + `git status` confirm zero writes.

## Tests

- `pytest tests/ -q -m "not slow"` (worktree): **395 passed, 2 failed** —
  both pre-exist on base (verified identical on base before the change):
  `league/test_pool.py::test_pool_matches_golden` (golden drift),
  `test_advantage_freeze.py` (cwd-dependent m.map). 11 new tests in
  `tests/test_ui_pass.py` (mtime/?since=/pagination/first-paint/crowns/
  maps-last/HTTP protocol/replay title) all pass.
- `node --check` on extracted SCRIPT: OK.
- Stub-DOM runtime harness (`/tmp/dom_harness2.js`): every render path
  (header/board/pop/gens/games/maps/seedMember/empty-states) runs against
  the synthetic snapshot — BOARD RUNTIME OK.
- Ruff: base `ml/dashboard.py` = 12 findings (5 F401, 2 E402, 2 E741,
  SIM105, 2 SIM113); branch = 10 (F401 5→3, `html` now used). Zero new
  violations. `tests/test_ui_pass.py` clean.

## Synthetic archive (`/tmp/synth_ui.py` → `/tmp/synth_arch`)

2 gens (c1 promoted, c2 held), 5 grouped games (2p eval incl. a re-run
split, 3p + 4p train), null-map legacy rows + named maps, target 2.

- `/` 200 (59KB) — raw HTML contains champion id, first game replay paths,
  crown value `complete`, `unlabelled (pre-map logging)`,
  `gen 2 · target 2 reached`, `gen c2 · train4 →` replay labels.
- `/api/snapshot` 200 — `mtime` present; `?since=<mtime>` → 49-byte
  `{"unchanged": true, ...}`; `?since=1` → full snapshot.
- `/api/games?member=c1` → total 3 (any-seat); invalid member →
  `{"total": 0, "rows": []}`; `limit=2&offset=1` slices correctly.
- `/replay?f=games/c1/eval1/logs/0.replay` 200 with
  `<title>replay games/c1/eval1/logs/0.replay · AZDash</title>`;
  missing/traversal → 404.

## Real archive (read-only serve, port 8902)

- `/`, `/api/snapshot` (1.89MB), `/api/games`: all 200, no 500s.
- Meaning unchanged vs base: counts 1690 gens / 80438 games / 1733 members;
  board series all length 1690; Elo panel `[g000,g1658,g1660,g1718]`;
  crowns 64 complete / 0 soft / 1626 held — all match the curves-verify
  numbers and the base snapshot taken before the change.
- First paint (raw HTML): `target 1689 reached`, unlabelled-maps row,
  dot strips, `150 turns` / `γ 0.97` / `draws count ½` renames,
  hide-zero-Nash control, provenance footer.

## Perf (real 1690-gen archive, same machine)

- Base (pre-change, direct `snapshot()`): cold **11.81s**, warm **0.74s**.
- Branch: `/` cold **13.16s** (full snapshot + 338KB first-paint render),
  `/` warm **0.75s**, `/api/snapshot` warm **0.53s**,
  `?since=`-fresh poll **49 bytes**.
- Cold stays snapshot-bound (grouping + history parse + causal refits,
  untouched); the ~1.3s delta is first-paint HTML for 100+50+~100 rows.
  The spec's "~0.2s server-side" is not reachable without a light snapshot
  path — documented gap, not a behavior change (warm <1s as required).

## No spec item deferred

All P0 (1–8), P1 (1–8), P2 (1–6), the section order, and the light-mode +
table-design lens are implemented. P0-2's "drop margins OR render them" is
satisfied by rendering (per-gen W/D/L dot strips, P2-4); margins stay in
the payload (an existing test pins `generations[].margins`).
