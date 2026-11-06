"""Map pool and staging: playability, seats, deterministic generation.

Split from the test_alphastarzero monolith; no behavior change.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "bots" / "alphaant" / "train"))

import pytest




def _parse_grid(lines: list[str]) -> tuple[int, int, list[str]]:
    rows = cols = 0
    grid: list[str] = []
    for line in lines:
        if line.startswith("rows "):
            rows = int(line.split()[1])
        elif line.startswith("cols "):
            cols = int(line.split()[1])
        elif line.startswith("m "):
            grid.append(line[2:])
    return rows, cols, grid



def test_default_pool_covers_any_player_count():
    import game_if
    import mapgen
    import selfplay

    pool = selfplay.default_map_pool()
    counts = {}
    for m in pool:
        assert mapgen.is_playable(m), m
        n = game_if.map_player_count(m)
        counts[n] = counts.get(n, 0) + 1
    assert 2 in counts and 4 in counts  # small and large tables play
    assert max(counts) >= 8  # the big multi_hill/cell_maze tables join
    import glob as _glob

    assert sorted(pool) == sorted(
        f
        for d in ("cell_maze", "maze", "multi_hill_maze", "random_walk")
        for f in _glob.glob(f"tools/maps/{d}/*.map")
    )  # every map in the four upstream dirs, none odder




def test_is_playable_accepts_n_player_maps(tmp_path):
    import mapgen

    def tiny(players, hills):
        n = max(8, players)
        grid = ["m " + "." * 8 for _ in range(n)]
        for i, h in enumerate(hills):
            grid[i] = "m " + h + "." * 7
        p = tmp_path / f"p{players}.map"
        p.write_text(f"rows {n}\ncols 8\nplayers {players}\n" + "\n".join(grid) + "\n")
        return str(p)

    assert mapgen.is_playable(tiny(2, "01"))
    assert mapgen.is_playable(tiny(3, "012"))
    assert mapgen.is_playable(tiny(4, "0123"))
    assert mapgen.is_playable(tiny(5, "01234"))  # any table size plays
    assert mapgen.is_playable(tiny(10, "0123456789"))  # up to 10 seats
    assert not mapgen.is_playable(tiny(1, "0"))  # solo is not a game
    assert not mapgen.is_playable(tiny(3, "01"))  # seat 2 has no hill




def test_default_maps_exist_and_turns_cover_endgames():
    import os

    import mapgen
    import selfplay

    cfg = selfplay.default_config()
    assert sorted(cfg["maps"]) == selfplay.default_map_pool()
    assert len(cfg["maps"]) >= 200  # the mixed 2/3/4p upstream pool
    for m in cfg["maps"]:
        assert os.path.exists(m), m
        assert mapgen.is_playable(m), m
    assert cfg["turns"] >= 250  # pro median is 229; 150 covered 21%




def test_mapgen_deterministic_and_valid():
    import mapgen

    assert mapgen.generate(3) == mapgen.generate(3)
    for seed in range(6):
        lines = mapgen.generate(seed)
        rows, cols, grid = _parse_grid(lines)
        assert len(grid) == rows and all(len(r) == cols for r in grid)
        flat = "".join(grid)
        # tools symmetric output: walk-carved land, digit hills.
        assert set(flat) <= set(".%0123456789")
        assert flat.count("0") == 1 and flat.count("1") == 1




def test_mapgen_tools_backed_and_valid(tmp_path):
    """generate() delegates to tools/mapgen (in-process): deterministic,
    playable 2p, hills exactly 0+1. Connectivity is enforced by the
    generator's own validity loop (is_valid until connected)."""
    import mapgen

    assert mapgen.generate(3) == mapgen.generate(3)
    for seed in range(6):
        p = tmp_path / f"g{seed}.map"
        p.write_text("\n".join(mapgen.generate(seed)) + "\n")
        assert mapgen.is_playable_2p(str(p)), f"seed {seed} not playable 2p"
        flat = "".join(
            line[2:] for line in p.read_text().splitlines() if line.startswith("m ")
        )
        assert flat.count("0") == 1 and flat.count("1") == 1




def test_custom_maps_used_directly_without_split():
    import selfplay

    maps = [f"m{i}.map" for i in range(30)]
    cfg = selfplay.parse_args(["--maps"] + maps)
    # No separate exam under the continuous league: the scheduler plays
    # one pool, nothing held out.
    assert cfg["maps"] == maps




def test_stage_side_names_main_file(tmp_path):
    import game_if

    side = game_if.stage_side(tmp_path / "out", {}, "side_a", "g004")
    assert (side / "g004.py").exists()
    assert not (side / game_if.MAIN_BOT).exists()
    assert (side / "ants.py").exists()  # support modules ride along
    assert (side / "weights.json").exists()




def test_play_stages_checkpoint_names(tmp_path, monkeypatch):
    import game_if

    seen = {}

    def fake_run(cmd, root, env, timeout):
        seen["bots"] = [c for c in cmd if c.endswith(".py") and "playgame" not in c]
        logdir = tmp_path / "g0" / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        (logdir / "0.replay").write_text(
            '{"game_length": 10, "score": [1, 1], "replaydata": {}}'
        )

    monkeypatch.setattr(game_if, "_run_once", fake_run)
    w = {"a": [1.0]}
    out = game_if.play(
        tmp_path,
        "python",
        [w, w],
        game_if.GameConfig(map="m.map", turns=10),
        tmp_path / "g0",
        names=["g004", "g000"],
    )
    assert out["game"]["game_length"] == 10
    assert seen["bots"][0].endswith("side_0/g004.py")
    assert seen["bots"][1].endswith("side_1/g000.py")




def test_map_player_count_reads_header(tmp_path):
    import game_if

    p = tmp_path / "m.map"
    p.write_text("rows 16\ncols 24\nplayers 3\nm " + "." * 24 + "\n")
    assert game_if.map_player_count(p) == 3




@pytest.mark.slow
def test_3p_game_end_to_end_fixed_seats(tmp_path):
    """A real 3-player engine game through the N-seat path: 3 bots, 3 scores,
    per-seat records, student seat 0 priced without crashing."""
    import game_if
    import model
    import rewards

    sys.path.insert(0, str(ROOT / "tools" / "mapgen"))
    import gen_mixed

    train, _eval = gen_mixed.fresh_pool(1, 0, tmp_path / "maps", seed=99, jobs=1)
    maps3 = [m for m in train if game_if.map_player_count(m) == 3]
    assert maps3, "seed 99 must draw a 3p map"
    w = model.state_dict_to_lists(model.CNNPolicy())
    out = game_if.play(
        ROOT,
        sys.executable,
        [w, w, w],
        game_if.GameConfig(
            map=maps3[0], turns=2, temperature=0.0, player_seed=1, engine_seed=1
        ),
        tmp_path / "g3",
        names=["s", "c", "x"],
    )
    assert len(out["game"]["score"]) == 3
    assert len(out["records"]) == 3
    rows = out["records"][0]
    rets = rewards.compute_returns(out["game"], 0, rows)
    assert len(rets) == len(rows)




def test_log_game_logs_n_seats_and_scores(tmp_path):
    import archive

    base = tmp_path / "archive"
    archive.log_game(
        base, ["main", "main", "main"], [3, 1, 0],
        "games/g/logs/0.replay", game="gid-3", tick=5,
        food=[2, 1, 0], kills=[1, 0, 0], army=[5, 4, 6], length=120)
    (row,) = archive.list_games(base)
    assert row["seats"] == ["main", "main", "main"]
    assert row["scores"] == [3, 1, 0] and row["tick"] == 5
    assert row["food"] == [2, 1, 0] and row["army"] == [5, 4, 6]




def test_log_game_carries_game_id(tmp_path):
    import archive

    base = tmp_path / "archive"
    archive.log_game(
        base,
        ["main", "main"], [3, 1],
        "games/g001/t0/logs/0.replay",
        game="games/g001/t0#abc",
    )
    rows = archive.list_games(base)
    assert len(rows) == 1 and rows[0]["game"] == "games/g001/t0#abc"




def test_log_game_game_optional_for_old_callers(tmp_path):
    import archive

    base = tmp_path / "archive"
    archive.log_game(base, ["main", "main"], [3, 1], "games/g001/t0/logs/0.replay")
    rows = archive.list_games(base)
    assert len(rows) == 1 and not rows[0].get("game")




def test_rank_of_matches_engine_ties_share_rank():
    import dashboard

    assert dashboard.rank_of([5, 3, 3, 1]) == [0, 1, 1, 3]
    assert dashboard.rank_of([10, 10, 5]) == [0, 0, 2]
    assert dashboard.rank_of([2, 2]) == [0, 0]
