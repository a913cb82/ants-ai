"""TDD for ml/bc.py: behavioral cloning rows from a tiny SYNTHETIC replay.

No engine involved: hand-built replay dicts exercise window rebuild,
order-char -> ACTIONS label mapping, and one supervised step.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "ml"))


def _synthetic_replaydata():
    """11x11 land map (wider than the 9x9 window, so no toroidal
    double-marking), water at (5,4), food present turns 1..2 at (5,6).

    Ant A (owner 0): (5,5) spawn 0, orders "nes" -> turns 1,2,3.
    Ant B (owner 1): (3,3) spawn 0, orders "---" -> stays, turns 1,2,3.
    Both survive: end = spawn + len(orders) + 1 = 4.
    """
    rows = ["..........."] * 11
    rows[5] = "....%......"  # water at (5,4)
    return {
        "map": {"rows": 11, "cols": 11, "data": rows},
        "ants": [
            [5, 5, 0, 4, 0, "nes"],
            [3, 3, 0, 4, 1, "---"],
        ],
        "food": [[5, 6, 1, 2]],
        "hills": [[5, 5, 0, 99], [3, 3, 1, 99]],
        "viewradius2": 77,
    }


def test_label_mapping_covers_engine_chars():
    import bc

    assert bc.label_of("n") == 0
    assert bc.label_of("e") == 1
    assert bc.label_of("s") == 2
    assert bc.label_of("w") == 3
    assert bc.label_of("-") == 4  # no order issued -> stay
    assert bc.label_of("x") is None  # unknown/attack/wait -> skip
    assert bc.label_of("") is None


def test_extract_rows_counts_and_labels():
    import bc

    rows = bc.extract_rows(_synthetic_replaydata())
    # 3 decision turns x 2 ants; spawn turn 0 has no decision.
    assert len(rows) == 6
    assert [r.label for r in rows if r.owner == 0] == [0, 1, 2]
    assert [r.label for r in rows if r.owner == 1] == [4, 4, 4]
    assert sorted({r.turn for r in rows}) == [1, 2, 3]


def test_extract_rows_skips_dead_and_ambiguous_turns():
    import bc

    rd = _synthetic_replaydata()
    # killed ant: end - spawn == len(orders); death during turn 2.
    rd["ants"].append([8, 8, 0, 2, 0, "ns"])
    # ambiguous char on turn 2 -> that turn skipped, turns 1+3 kept.
    rd["ants"].append([8, 0, 0, 4, 1, "nxs"])
    rows = bc.extract_rows(rd)
    dead = [r for r in rows if r.owner == 0 and r.loc in ((8, 8), (7, 8))]
    assert sorted(r.turn for r in dead) == [1, 2]
    amb = [r for r in rows if r.owner == 1 and r.loc in ((8, 0), (7, 0))]
    assert sorted(r.turn for r in amb) == [1, 3]


def test_window_rebuild_channels():
    import torch

    import bc
    import features

    rows = bc.extract_rows(_synthetic_replaydata())
    row = next(r for r in rows if r.owner == 0 and r.turn == 1)
    w = row.window
    assert isinstance(w, torch.Tensor) and w.shape == (6, 9, 9)
    ch = features.CHANNELS
    wi, fi = ch.index("water"), ch.index("food")
    oi, ei = ch.index("own_ant"), ch.index("enemy_ant")
    # ant A decides from (5,5): own mark at window center.
    assert w[oi, 4, 4] == 1.0
    # water at (5,4) is west of center -> water mark, suppresses rest.
    assert w[wi, 4, 3] == 1.0
    assert w[oi, 4, 3] == 0.0
    # food at (5,6) present turn 1 (1<=1<=2) -> east of center.
    assert w[fi, 4, 5] == 1.0
    # enemy ant B at (3,3): dr=-2, dc=-2 -> (2,2) in window.
    assert w[ei, 2, 2] == 1.0


def test_window_food_presence_convention():
    import bc
    import features

    rows = bc.extract_rows(_synthetic_replaydata())
    fi = features.CHANNELS.index("food")
    by_turn = {r.turn: r for r in rows if r.owner == 0}
    assert by_turn[1].window[fi].sum() == 1.0  # 1 <= 1 <= 2 present
    assert by_turn[2].window[fi].sum() == 1.0  # 1 <= 2 <= 2 present
    assert by_turn[3].window[fi].sum() == 0.0  # expired after turn 2


def test_supervised_step_decreases_loss():
    import torch

    import bc
    import model

    torch.manual_seed(0)
    policy = model.CNNPolicy()
    batch = [
        (torch.randn(6, 9, 9), i % 5) for i in range(16)
    ]
    before = bc.batch_loss(policy, batch)
    opt = torch.optim.Adam(policy.parameters(), lr=1e-3)
    for _ in range(5):
        opt.zero_grad()
        loss = bc.batch_loss(policy, batch)
        loss.backward()
        opt.step()
    assert bc.batch_loss(policy, batch) < before


def test_weights_roundtrip_in_policy_list_format():
    import algorithm
    import model

    policy = model.CNNPolicy()
    lists = algorithm.policy_weights(policy)
    assert all(isinstance(v, list) for v in lists.values())
    fresh = model.CNNPolicy(arch=model.infer_arch(lists))
    fresh.load_state_dict(model.lists_to_state_dict(lists))
    for a, b in zip(
        policy.state_dict().values(), fresh.state_dict().values()
    ):
        assert (a == b).all()
