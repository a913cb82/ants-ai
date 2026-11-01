"""Memory profile: in-memory batch must not hold python-float windows.

Regression for the selfplay OOM (~14GB anon-RSS in one process at
85k rows/gen x 1575-float python lists): records arrive from disk as
nested python lists and pool.map materialized every game (~60KB/row
vs 6.3KB as a float32 tensor). The contract: windows are compacted
to tensors at production (train._play_one) and the compacted batch
is bit-identical to the list path (training math unchanged).
"""

import copy
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "ml"))

import algorithm  # noqa: E402
import features  # noqa: E402

_C = len(features.CHANNELS)
_S = 2 * features.DEFAULT_RADIUS + 1


def _disk_rows(n=16, seed=0):
    """Rows shaped like game_if._read_records output: nested lists."""
    rng = torch.Generator().manual_seed(seed)
    rows = []
    for i in range(n):
        w = (torch.rand(_C, _S, _S, generator=rng) > 0.5).float()
        rows.append(
            {"turn": i, "action": "n", "window": w.tolist(), "legal": [True] * 5}
        )
    return rows


def _has_py_window(rows):
    def _py(o):
        if isinstance(o, float):
            return True
        if isinstance(o, list):
            return any(_py(x) for x in o)
        return False

    return any(_py(r["window"]) for r in rows)


def test_compact_records_removes_python_float_windows():
    rows = _disk_rows()
    assert _has_py_window(rows)  # disk shape really is python floats
    compacted = algorithm.compact_records(rows)
    assert not _has_py_window(compacted)
    for rec in compacted:
        assert isinstance(rec["window"], torch.Tensor)
        assert rec["window"].dtype == torch.float32
        assert rec["window"].shape == (_C, _S, _S)


def test_compact_batch_byte_identical_to_list_path():
    """Same seed -> same collect output on lists vs compacted tensors."""
    policy = algorithm.new_policy({})
    rets = [float(i % 3 - 1) for i in range(16)]
    torch.manual_seed(7)
    a = algorithm.collect(policy, copy.deepcopy(_disk_rows()), rets)
    torch.manual_seed(7)
    b = algorithm.collect(policy, algorithm.compact_records(_disk_rows()), rets)
    assert len(a) == len(b) == 16
    for (wa, aa, ra, ma, oa), (wb, ab, rb, mb, ob) in zip(a, b):
        assert torch.equal(wa, wb)
        assert (aa, ra, ma, oa) == (ab, rb, mb, ob)


def test_frozen_advantages_chunked_matches_full():
    """Chunked values-forward is bit-identical (order + contents)."""
    import algorithm as A

    policy = algorithm.new_policy({})
    batch = algorithm.collect(
        policy,
        algorithm.compact_records(_disk_rows(24)),
        [float(i % 3 - 1) for i in range(24)],
    )
    full, bm, bs = A.frozen_advantages(policy, batch)
    old = A._VALUE_CHUNK
    try:
        A._VALUE_CHUNK = 5
        chunked, cm, cs = A.frozen_advantages(policy, batch)
    finally:
        A._VALUE_CHUNK = old
    assert torch.equal(full, chunked)
    assert torch.equal(bm, cm) and torch.equal(bs, cs)


def test_same_seed_same_update():
    """Same seed -> same PPO step on the compacted path (determinism)."""

    def _run():
        torch.manual_seed(11)
        policy = algorithm.new_policy({})
        opt = algorithm.make_optimizer(policy, lr=1e-3)
        batch = algorithm.collect(
            policy,
            algorithm.compact_records(_disk_rows()),
            [float(i % 3 - 1) for i in range(16)],
        )
        adv, bmean, bstd = algorithm.frozen_advantages(policy, batch)
        algorithm.train_epoch(
            policy, opt, batch, advantages=adv, bmean=bmean, bstd=bstd
        )
        return algorithm.policy_weights(policy)

    w1, w2 = _run(), _run()
    assert w1.keys() == w2.keys()
    for k in w1:
        assert torch.equal(torch.tensor(w1[k]), torch.tensor(w2[k])), k
