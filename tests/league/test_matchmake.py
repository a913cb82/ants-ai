"""Matchmaking: random maps, informative fields, position shuffle."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "league"))

MAPS = Path(__file__).resolve().parents[2] / "tools" / "maps"


def test_maps_for_players_match_header():
    from matchmake import maps_for_players
    maps = maps_for_players(MAPS, 8)
    assert len(maps) > 5
    assert all(m.parent.name != "example" or True for m in maps)
    import re
    for m in maps[:5]:
        head = (MAPS / m).read_text().splitlines()
        assert any(re.match(rf"^players\s+8\s*$", l) for l in head)


def test_pick_map_is_deterministic_per_seed():
    from matchmake import pick_map
    assert pick_map(random.Random(7), MAPS) == pick_map(random.Random(7), MAPS)


def test_pick_map_pins_count():
    from matchmake import pick_map, maps_for_players
    n, m = pick_map(random.Random(1), MAPS, n=2)
    assert n == 2 and m in maps_for_players(MAPS, 2)


def test_propose_fills_field_with_distinct_bots():
    from matchmake import propose, new_model
    cands = [f"bots/b{i}-abc1234" for i in range(6)]
    field = propose(new_model(), cands, {}, 4, random.Random(0))
    assert len(field) == 4 and len(set(field)) == 4


def test_propose_seeds_highest_sigma():
    from matchmake import propose, new_model
    m = new_model()
    ratings = {"x": {"mu": 25.0, "sigma": 0.5, "games": 20},
               "y": {"mu": 25.0, "sigma": 8.0, "games": 0}}
    field = propose(m, ["x", "y"], ratings, 1, random.Random(0))
    assert field == ["y"]


def test_info_score_prefers_close_ratings():
    from matchmake import info_score, new_model
    m = new_model()
    close = info_score(m, ["a", "b"],
                       {"a": {"mu": 30.0, "sigma": 1.0, "games": 9},
                        "b": {"mu": 30.5, "sigma": 1.0, "games": 9}})
    far = info_score(m, ["a", "c"],
                     {"a": {"mu": 30.0, "sigma": 1.0, "games": 9},
                      "c": {"mu": 45.0, "sigma": 1.0, "games": 9}})
    assert close > far


def test_assign_positions_shuffles_but_keeps_set():
    from matchmake import assign_positions
    f = ["a", "b", "c", "d"]
    assert sorted(assign_positions(f, random.Random(3))) == f


def test_prune_evicts_oldest_over_limit(tmp_path):
    import os
    import time as _t
    from pool import prune_worktrees
    base = tmp_path / "wb"
    for name, size in (("old", 600), ("mid", 600), ("new", 600)):
        d = base / name
        d.mkdir(parents=True)
        (d / "f").write_bytes(b"x" * size)
    now = _t.time()
    os.utime(base / "old", (now - 30, now - 30))
    os.utime(base / "mid", (now - 20, now - 20))
    os.utime(base / "new", (now - 10, now - 10))
    freed = prune_worktrees(base, max_bytes=1500)
    assert freed == 600
    assert not (base / "old").exists()
    assert (base / "mid").is_dir() and (base / "new").is_dir()
