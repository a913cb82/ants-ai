"""Sampling tests for the mixed-generator script (TDD: fails until implemented)."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "maps" / "curriculum"))

import gen_mixed


def test_pick_dims_hits_budget_and_aspect():
    for n in (2, 3, 4):
        for seed in range(20):
            rng = random.Random(seed)
            rows, cols = gen_mixed.pick_dims(n, rng, snap=1)
            tiles = rows * cols
            assert abs(tiles - 250 * n) <= 0.25 * 250 * n, (n, rows, cols)
            assert 0.5 <= cols / rows <= 2.0, (n, rows, cols)
            assert rows % 1 == 0 and cols % 1 == 0


def test_pick_dims_snap_divisible():
    for n in (2, 3, 4):
        rng = random.Random(7)
        for _ in range(20):
            rows, cols = gen_mixed.pick_dims(n, rng, snap=n)
            assert rows % n == 0 and cols % n == 0, (n, rows, cols)


def test_validate_accepts_good_map():
    text = Path("/tmp/mixed-demo/mixed_symmetric_p2_20x28_s102.map").read_text()
    ok, reason = gen_mixed.validate(text, 2)
    assert ok, reason
    # The old unrated fixture has hills 3.0 apart: gate correctly rejects.
    text = Path("/tmp/mapgen-3p-24x32/random_a.map").read_text()
    ok, reason = gen_mixed.validate(text, 3)
    assert not ok and "apart" in reason, reason


def test_validate_rejects_bad_maps():
    text = Path("/tmp/mapgen-3p-24x32/random_a.map").read_text()
    ok, _ = gen_mixed.validate(text, 2)  # wrong player count
    assert not ok
    lines = text.splitlines()
    lines[0] = "rows 200"  # blow the tile budget
    ok, _ = gen_mixed.validate("\n".join(lines), 3)
    assert not ok


def test_metadata_header_present_and_valid():
    import subprocess
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1]
         / "tools" / "maps" / "curriculum" / "gen_mixed.py"),
         "--seed", "42", "--players", "2", "--generator", "symmetric"],
        capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert out.startswith("# generator: symmetric_mapgen.py\n")
    assert "# args:" in out and "# gen_mixed seed: 42" in out
    ok, reason = gen_mixed.validate(out, 2)
    assert ok, reason


def test_validate_rejects_degenerate_hill_twins():
    import math
    text = Path("/tmp/mapgen-3p-24x32/random_a.map").read_text()
    ok, reason = gen_mixed.validate(text, 3)
    assert not ok and "apart" in reason, reason
    # ...but every current mixed-demo map passes the default gate.
    for f in Path("/tmp/mixed-demo").glob("*.map"):
        n = int([l for l in f.read_text().splitlines()
                 if l.startswith("players")][0].split()[1])
        ok, reason = gen_mixed.validate(f.read_text(), n)
        assert ok, (f.name, reason)
    # Threshold is honored: the 5.0 walk map fails a 6.0 gate.
    text = Path("/tmp/mixed-demo/mixed_walk_p4_30x36_s103.map").read_text()
    ok, _ = gen_mixed.validate(text, 4, min_hill_dist=6.0)
    assert not ok


def test_end_to_end_each_generator():
    for gen, n in (("symmetric", 2), ("cavemap", 3), ("walk", 2),
                   ("symmetric", 4), ("cavemap", 2), ("walk", 3)):
        text, _, _ = gen_mixed.generate_one(gen, n, random.Random(11))
        ok, reason = gen_mixed.validate(text, n)
        assert ok, (gen, n, reason)
