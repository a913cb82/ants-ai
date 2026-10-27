"""Imitation probe (capacity check): distill champion decisions offline."""

import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "ml"))

import features  # noqa: E402

_C = len(features.CHANNELS)
ENEMY = features.CHANNELS.index("enemy_ant")


def _row(label, enemy=False):
    import bc

    w = torch.zeros(_C, 5, 5)
    if enemy:
        w[ENEMY, 2, 1] = 1.0
    return bc.Row(window=w, label=label, turn=1, owner=0, loc=(0, 0),
                  foods=(), dims=(10, 10))


def test_champ_side_owner_mapping():
    import probe_imitate

    assert probe_imitate.champ_owner({"a": "g9", "b": "g8"}, "g9") == 0
    assert probe_imitate.champ_owner({"a": "g9", "b": "g8"}, "g8") == 1


def test_combat_rows_selects_enemy_visible():
    import probe_imitate

    rows = [_row(0), _row(1, enemy=True), _row(2), _row(3, enemy=True)]
    combat = probe_imitate.combat_rows(rows)
    assert len(combat) == 2
    assert all(r.label in (1, 3) for r in combat)


def test_distill_reports_top1_agreement():
    import probe_imitate

    torch.manual_seed(0)
    rows = []
    for i in range(200):
        w = torch.zeros(_C, 5, 5)
        w[1, 2, 2] = 1.0 if i % 2 == 0 else 0.0  # trivially separable
        import bc
        rows.append(bc.Row(window=w, label=i % 2, turn=1, owner=0,
                           loc=(0, 0), foods=(), dims=(10, 10)))
    policy, stats = probe_imitate.distill(rows, arch="base", epochs=5,
                                          seed=0)
    assert 0.0 <= stats["val_acc"] <= 1.0
    assert 0.0 <= stats["train_acc"] <= 1.0
    assert stats["val_acc"] > 0.5  # separable toy must beat chance
