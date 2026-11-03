"""T-1 history channels: geometry, surgery, drift, live verification.

The input grows 10 -> 13 channels: the current frame plus prev_own_ant,
prev_enemy_ant (the T-1 entity grids re-centered on this turn's ant) and
prev_self (a marker where THIS ant was last turn). Two things must hold:

1. Surgery: port_weights copies every old weight verbatim and grows only
   the two first-conv layers with small-nonzero slices, so the ported net
   starts within a whisper of the original policy (argmax agreement on
   realistic states, tiny KL and value drift).
2. Content: on a real engine, with real moves and a real kill, the history
   channels show exactly the previous turn re-centered — including a dead
   enemy the current frame no longer sees.
"""

import json
import os
import sys
from pathlib import Path

import test_live_rewards as LR
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "ml"))

import features
import model

# Custom 13x13: A1 (4,5) and A2 (6,5) sandwich E1 (5,5) at d2=1 — no
# single move escapes attackradius2 5, so T1 combat is unavoidable and
# E1 dies on schedule. W (10,10) watches from safety (d2=50, visible
# but out of range); E2 (0,0) keeps both players alive through T2.
MAP_HISTORY = """\
rows 13
cols 13
players 2
m b............
m .............
m .............
m .............
m .....a.......
m .....b.......
m .....a.......
m .............
m .............
m .............
m ..........a..
m .............
m .............
"""


def _small_grid(marks, n=5):
    """(n,n) float grid with 1.0 at each (i, j) mark."""
    import numpy as _np

    g = _np.zeros((n, n), dtype=_np.float32)
    for i, j in marks:
        g[i, j] = 1.0
    return g


def test_shift_frame_moves_content_with_the_ant():
    # Ant moves north: prev (-5 stays): content shifts one row south,
    # the exposed north edge zeroes, self marker sits one south.
    prev = _small_grid([(2, 2)])
    rolled, selfm = features.shift_frame(prev, (6, 6), (5, 6), 13, 13)
    assert rolled[3, 2] == 1.0
    assert rolled[0].sum() == 0.0
    assert rolled.sum() == 1.0
    assert selfm[3, 2] == 1.0
    assert selfm.sum() == 1.0


def test_shift_frame_stay_marks_center():
    prev = _small_grid([(2, 2), (0, 0)])
    rolled, selfm = features.shift_frame(prev, (6, 6), (6, 6), 13, 13)
    assert (rolled == prev).all()
    assert selfm[2, 2] == 1.0
    assert selfm.sum() == 1.0


def test_shift_frame_wrap_move_zeroes_only_the_wrapped_edge():
    # East off the last column wraps to 0: map cell (7,10) [prev index
    # (2,0)] falls out of the new frame entirely, while (7,1) [prev
    # index (2,4)] shifts one west to (2,3). The stale content that
    # rolls into the east edge must read 0.
    prev = _small_grid([(2, 0), (2, 4)])
    rolled, selfm = features.shift_frame(prev, (7, 12), (7, 0), 13, 13)
    assert rolled[2, 3] == 1.0  # (2,4) shifted one west
    assert rolled[2, 4] == 0.0  # wrapped edge fogged
    assert rolled.sum() == 1.0  # (2,0) left the frame
    assert selfm[2, 1] == 1.0  # was one west of the new center
    assert selfm.sum() == 1.0


def test_with_history_none_gives_zero_memory():
    import torch as _t

    grid = _t.zeros(10, 15, 15)
    full = features.with_history(grid, None)
    assert full.shape == (13, 15, 15)
    assert full[10:].sum() == 0.0
    assert torch.equal(full[:10], grid)


def test_with_history_picks_previous_entity_grids():
    import torch as _t

    cur = _t.zeros(10, 15, 15)
    prev = _t.zeros(10, 15, 15)
    prev[1, 7, 7] = 1.0  # me-then at center
    prev[3, 0, 0] = 1.0  # enemy-then far away
    full = features.with_history(
        cur, (prev.numpy(), (6, 6), (6, 6), 13, 13)
    )
    assert full.shape == (13, 15, 15)
    assert full[10, 7, 7] == 1.0  # prev_own_ant
    assert full[10].sum() == 1.0
    assert full[11, 0, 0] == 1.0  # prev_enemy_ant
    assert full[12, 7, 7] == 1.0  # prev_self at center on a stay
    assert torch.equal(full[:10], cur)


def _seeded_state(channels, arch="base", seed=7):
    torch.manual_seed(seed)
    return dict(model.CNNPolicy(channels=channels, arch=arch).state_dict())


def test_port_preserves_every_old_weight():
    old = _seeded_state(10)
    new = model.port_weights(old)
    assert set(new) == set(old)
    for key, val in old.items():
        if key in ("conv1.weight", "vconv1.weight"):
            assert torch.equal(new[key][:, :10], val)
            assert new[key].shape[1] == 13
        else:
            assert torch.equal(new[key], val), key


def test_port_new_slices_are_small_and_nonzero():
    old = _seeded_state(10)
    new = model.port_weights(old, hist_scale=0.01)
    for key in ("conv1.weight", "vconv1.weight"):
        extra = new[key][:, 10:]
        assert extra.shape[1] == 3
        assert bool((extra != 0.0).all()), key
        # Same init family as the trunk (orthogonal, gain sqrt2),
        # shrunk 100x: per-element scale ~1e-3, drift stays a whisper.
        assert extra.abs().max() < 0.05, (key, extra.abs().max())


def test_ported_net_loads_strict_and_keeps_arch():
    for arch in ("base", "deep"):
        old = _seeded_state(10, arch=arch)
        net = model.CNNPolicy(arch=arch)  # default width is the full input
        net.load_state_dict(model.port_weights(old), strict=True)
        assert model.infer_arch(dict(net.state_dict())) == arch


def _drift_battery(n=128, seed=99):
    """Realistic current frames: sparse entity one-hots like real games,
    plus random memory (even nonsense memory must not swing policy)."""
    torch.manual_seed(seed)
    cur = torch.zeros(n, 10, 15, 15)
    for b in range(n):
        for ch in (1, 3, 5):
            for _ in range(torch.randint(1, 5, (1,)).item()):
                cur[b, ch, torch.randint(0, 15, (1,)), torch.randint(0, 15, (1,))] = 1.0
        cur[b, 6] = 1.0  # visible builders fill the sight flag
        cur[b, 0, torch.randint(0, 15, (1,)), torch.randint(0, 15, (1,))] = 1.0
    hist = (torch.rand(n, 2, 15, 15) < 0.05).float()
    selfm = torch.zeros(n, 1, 15, 15)
    selfm[torch.arange(n), 0, torch.randint(0, 15, (n,)), torch.randint(0, 15, (n,))] = 1.0
    return cur, torch.cat([hist, selfm], dim=1)


def _assert_whisper(old_net, new_net, cur, hist):
    old_net.eval()
    new_net.eval()
    with torch.no_grad():
        full = torch.cat([cur, hist], dim=1)
        old_l = old_net(cur)
        new_l = new_net(full)
        old_v = old_net.values(cur)
        new_v = new_net.values(full)
    assert (old_l.argmax(1) == new_l.argmax(1)).all(), "argmax must agree"
    assert (new_l - old_l).abs().max() < 0.25, "logit drift must stay small"
    kl = (torch.softmax(old_l, 1) * (torch.log_softmax(old_l, 1) - torch.log_softmax(new_l, 1))).sum(1)
    assert kl.mean() < 1e-3, f"KL drift {kl.mean()}"
    assert (new_v - old_v).abs().max() < 0.25, "value drift must stay small"


def test_port_drift_is_a_whisper_on_synthetic_states():
    old_sd = _seeded_state(10, seed=11)
    old_net = model.CNNPolicy(channels=10)
    old_net.load_state_dict(old_sd, strict=True)
    new_net = model.CNNPolicy()
    new_net.load_state_dict(model.port_weights(old_sd), strict=True)
    cur, hist = _drift_battery()
    _assert_whisper(old_net, new_net, cur, hist)


def test_port_drift_is_a_whisper_on_the_live_champion():
    """The deploy gate: the real lineage, real scripted-game frames."""
    live = json.loads((ROOT / "ml" / "archive" / "live" / "weights.json").read_text())
    old_sd = model.lists_to_state_dict(live)
    old_net = model.CNNPolicy(channels=10, arch=model.infer_arch(old_sd))
    old_net.load_state_dict(old_sd, strict=True)
    new_net = model.CNNPolicy(arch=model.infer_arch(old_sd))
    new_net.load_state_dict(model.port_weights(old_sd), strict=True)
    cur, hist = _drift_battery(n=256, seed=1234)
    _assert_whisper(old_net, new_net, cur, hist)


def _run_history_game(tmp_path, monkeypatch):
    """Two turns, real engine, real bot: P0 plays its own greedy picks,
    P1 parks. Returns (bot rows by turn, BotAnts views by turn)."""
    import AlphaAnt  # runtime import: same ENGINE-ants binding as the suite

    monkeypatch.setenv("AA_RECORD_DIR", str(tmp_path))
    game = LR._new_game(MAP_HISTORY, 2)
    ants = LR.BotAnts()
    ants.setup(game.get_player_start(0))
    bot = AlphaAnt.AlphaAntBot()
    bot.do_setup(ants)
    views = []
    for turn in range(1, 3):
        state = game.get_player_state(0)
        ants.update(state)
        views.append(dict(ants.ant_list))
        bot.do_turn(ants)
        game.start_turn()
        rec_path = tmp_path / f"aa-{os.getpid()}.jsonl"
        latest = rec_path.read_text().splitlines()[-len(ants.my_ants()):]
        p0 = [
            (r["loc"][0], r["loc"][1], r["action"])
            for r in (json.loads(line) for line in latest)
        ]
        lines0 = [f"o {r} {c} {d}" for r, c, d in p0 if d != "stay"]
        valid, ignored, invalid = game.do_moves(0, lines0)
        assert ignored == [] and invalid == [], (ignored, invalid)
        game.do_moves(1, [])  # P1 parks: E1 holds the sandwich, E2 holds.
        game.finish_turn()
    rows = [json.loads(line) for line in rec_path.read_text().splitlines()]
    return rows, views


def test_live_history_tracks_real_moves_and_a_real_kill(tmp_path, monkeypatch):
    rows, views = _run_history_game(tmp_path, monkeypatch)
    by_turn = {}
    for r in rows:
        by_turn.setdefault(r["turn"], []).append(r)
    assert set(by_turn) == {1, 2}
    # Turn 1: first sight, memory empty on every row.
    for r in by_turn[1]:
        grid = features.decode_window(r["window"])
        assert grid.shape == (13, 15, 15)
        assert grid[10:].sum() == 0.0, "first sight has no past"
    # E1 died on schedule in the T1 sandwich.
    assert (5, 5) not in views[1], f"E1 must die T1, saw {views[1]}"
    # Turn 2: every survivor links to a T1 decision and carries the
    # exact shifted T1 frame — including E1, gone from current vision.
    t1 = {tuple(r["loc"]): r for r in by_turn[1]}
    assert len(by_turn[2]) >= 1, "witness must survive"
    for r in by_turn[2]:
        grid = features.decode_window(r["window"])
        assert grid.shape == (13, 15, 15)
        prev = next(
            (t for t in by_turn[1] if t["dest"] == r["loc"]), None
        )
        assert prev is not None, f"no T1 decision leads to {r['loc']}"
        base = features.decode_window(prev["window"])[:10].numpy()
        rolled, selfm = features.shift_frame(
            base, tuple(prev["loc"]), tuple(r["loc"]), 13, 13
        )
        import numpy as _np

        assert _np.array_equal(grid[10].numpy(), rolled[1]), "prev_own_ant"
        assert _np.array_equal(grid[11].numpy(), rolled[3]), "prev_enemy_ant"
        assert _np.array_equal(grid[12].numpy(), selfm), "prev_self"
        # Kill memory, pinned on E1-then (5,5): present in prev_enemy at
        # its shifted cell, absent from the current enemy channel — the
        # dead are gone from vision but not from memory.
        di = features._tdelta(5, r["loc"][0], 13)
        dj = features._tdelta(5, r["loc"][1], 13)
        assert abs(di) <= 7 and abs(dj) <= 7, "E1-then in frame"
        assert grid[11, 7 + di, 7 + dj] == 1.0, "memory keeps the kill"
        assert grid[3, 7 + di, 7 + dj] == 0.0, "vision drops the dead"
