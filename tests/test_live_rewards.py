"""Live-engine reward audit: real map, real orders, real replay.

Drives the REAL engine (tools.ants.Ants) in-process on tiny hand maps,
issues MANUAL orders turn by turn, and checks three things:

1. The engine executed exactly what was ordered (positions, kills, razes).
2. The bot's real perception path (engine vision strings -> bot Ants ->
   recorded windows) sees water/food/friendly+enemy ants+hills.
3. compute_returns pays exactly the spec amounts with GAMMA walk-back decay.

Maps are 13x13: big enough that no two far-apart tiles fall inside combat
or hill range through the toroidal wrap, so every distance below reads as
written (raw == toroidal). Map legend: '.' land, '%' water, food is placed
via add_food (the engine's "none" food mode ignores map food), '0'/'1'
hills, 'a'/'b' ants, 'A'/'B' ant+hill.

Action labels follow features.ACTIONS: n/e/s/w/stay.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# NOTE: never `import ants` here: test_mapgen_java binds that name to the
# ENGINE ants at collection time, and module-level binding to the bot
# interface would poison its import. Both ants modules load by file path
# under unique names instead (same pattern as the bot-behavior splits).
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "tools"))

import features
import rewards

_bot_spec = importlib.util.spec_from_file_location(
    "bot_side_ants", str(ROOT / "bots" / "alphaant" / "ants.py")
)
bot_side_ants = importlib.util.module_from_spec(_bot_spec)
_bot_spec.loader.exec_module(bot_side_ants)
BotAnts = bot_side_ants.Ants

_spec = importlib.util.spec_from_file_location(
    "engine_ants", str(ROOT / "tools" / "ants.py")
)
engine_ants = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(engine_ants)

APPROX = {"rel": 1e-9}


def _options(map_text, turns):
    return {
        "map": map_text,
        "turns": turns,
        "loadtime": 3000,
        "turntime": 5000,
        "viewradius2": 77,
        "attackradius2": 5,
        "spawnradius2": 1,
        "food": "none",  # no random spawns: every credit is hand-placed
        "attack": "focus",
        # Scenario mode: the map is followed exactly (placed ants, no
        # 1-ant-per-hill auto-spawn). Without it the engine ignores 'a'.
        "scenario": True,
        "engine_seed": 1,
        "player_seed": 1,
    }


def _new_game(map_text, turns):
    game = engine_ants.Ants(_options(map_text, turns))
    game.start_game()
    return game


def _step(game, moves0, moves1):
    """Run one full turn. moves are [(row, col, direction)].

    "stay" drops the order line (the engine holds ants without orders).
    """
    game.start_turn()
    for seat, moves in ((0, moves0), (1, moves1)):
        wanted = [(r, c, d) for r, c, d in moves if d != "stay"]
        lines = [f"o {r} {c} {d}" for r, c, d in wanted]
        valid, ignored, invalid = game.do_moves(seat, lines)
        assert ignored == [], f"seat {seat} orders ignored: {ignored}"
        assert invalid == [], f"seat {seat} orders invalid: {invalid}"
        assert sorted(valid) == sorted(lines)
    game.finish_turn()
    return game


def _positions(game):
    return {ant.loc: ant.owner for ant in game.current_ants.values()}


def _killed(game):
    return {(ant.loc, ant.owner) for ant in game.killed_ants}


def _game_dict(game):
    game.finish_game()
    return {
        "score": list(game.get_scores()),
        "status": ["survived"] * game.num_players,
        "game_length": game.turn,
        "replaydata": game.get_replay(),
    }


def _records(rows):
    return [{"turn": t, "loc": list(loc), "dest": list(dest), "action": d}
            for t, loc, dest, d in rows]


def _join_ok(replaydata, records):
    keys = rewards.record_identities(replaydata, records)
    assert all(k is not None for k in keys), "every manual row must join"
    return keys


# --------------------------------------------------------------------------
# Main game: 2v1 clean kill (T2), march, hill raze (T6), P0 wins.
# A1 (7,4), A2 (7,6) vs E1 (8,9); E2 sits on the far hill (9,9).
# --------------------------------------------------------------------------
MAP_MAIN = """\
rows 13
cols 13
players 2
m .............
m .............
m .............
m .............
m ....0...1....
m .............
m ......%......
m ....a.a......
m .........b...
m .........B...
m .............
m .............
m .............
"""

MAIN_ROWS = [
    # turn, loc, dest, action
    (1, (7, 4), (7, 5), "e"),  # A1: closes on H1 (4,8): 5.0 -> sqrt(18)
    (1, (7, 6), (7, 6), "stay"),  # A2: holds
    (2, (7, 5), (7, 6), "e"),  # A1: closes sqrt(18) -> sqrt(13)
    (2, (7, 6), (7, 7), "e"),  # A2: closes sqrt(13) -> sqrt(10); kill E1
    (3, (7, 6), (7, 7), "e"),  # A1: closes sqrt(13) -> sqrt(10)
    (3, (7, 7), (6, 7), "n"),  # A2: closes sqrt(10) -> sqrt(5)
    (4, (7, 7), (6, 7), "n"),  # A1: closes sqrt(10) -> sqrt(5)
    (4, (6, 7), (5, 7), "n"),  # A2: closes sqrt(5) -> sqrt(2)
    (5, (6, 7), (5, 7), "n"),  # A1: closes sqrt(5) -> sqrt(2)
    (5, (5, 7), (4, 7), "n"),  # A2: closes sqrt(2) -> 1
    (6, (5, 7), (4, 7), "n"),  # A1: closes sqrt(2) -> 1
    (6, (4, 7), (4, 8), "e"),  # A2: steps onto H1 -> raze (approach skips)
]

MAIN_ORDERS = [
    ([(7, 4, "e"), (7, 6, "stay")], [(8, 9, "stay"), (9, 9, "stay")]),
    ([(7, 5, "e"), (7, 6, "e")], [(8, 9, "w"), (9, 9, "stay")]),
    ([(7, 6, "e"), (7, 7, "n")], [(8, 8, "stay"), (9, 9, "stay")]),
    ([(7, 7, "n"), (6, 7, "n")], [(8, 8, "stay"), (9, 9, "stay")]),
    ([(6, 7, "n"), (5, 7, "n")], [(8, 8, "stay"), (9, 9, "stay")]),
    ([(5, 7, "n"), (4, 7, "e")], [(8, 8, "stay"), (9, 9, "stay")]),
]


def _play_main():
    game = _new_game(MAP_MAIN, 6)
    got_positions, got_kills = [], []
    for m0, m1 in MAIN_ORDERS:
        _step(game, m0, m1)
        got_positions.append(_positions(game))
        got_kills.append(_killed(game))
    return game, got_positions, got_kills


def test_live_orders_execute_exactly():
    game, positions, kills = _play_main()
    assert positions[0] == {
        (7, 5): 0, (7, 6): 0, (8, 9): 1, (9, 9): 1,
    }
    # T2: E1 walked into the 2v1 and died on arrival; both attackers live.
    assert positions[1] == {
        (7, 6): 0, (7, 7): 0, (9, 9): 1,
    }
    assert kills[1] == {((8, 8), 1)}
    assert kills[0] == set() and kills[2] == set()
    # E1 is dead from T2 on: later positions show only the living.
    assert positions[4] == {
        (5, 7): 0, (4, 7): 0, (9, 9): 1,
    }
    assert positions[5] == {
        (4, 7): 0, (4, 8): 0, (9, 9): 1,
    }
    hills = {(h[0], h[1]): (h[2], h[3]) for h in game.get_replay()["hills"]}
    assert hills[(4, 8)] == (1, 6), "H1 razed on turn 6"
    assert hills[(4, 4)][1] > 6, "own hill stands"
    assert hills[(9, 9)][1] > 6, "far hill stands"


def test_live_kill_splits_and_decays():
    game, _, _ = _play_main()
    gdict = _game_dict(game)
    assert gdict["score"] == [3, 0], "raze points decide: P0 wins"
    records = _records(MAIN_ROWS)
    _join_ok(gdict["replaydata"], records)
    # The split mechanism still works when paid: the full classic table
    # recovers the old 0.05/0.05 kill shares exactly.
    classic = {
        "FOOD": 0.1, "KILL": 0.1, "DEATH": -0.2, "HILL_RAZE": 10.0,
        "HILL_LOST": -10.0, "WIN": 5.0, "LOSS": -5.0, "HILL_APPROACH": 0.25,
    }
    classic_rets = rewards.compute_returns(gdict, 0, records, classic)
    classic_by_turn = {
        (r["turn"], tuple(r["loc"])): v
        for r, v in zip(records, classic_rets)
    }
    assert classic_by_turn[(2, (7, 5))] == pytest.approx(
        0.05 + 8.651410853765604 + 0.1592723529138239 + 5, **APPROX
    )
    assert classic_by_turn[(2, (7, 6))] == pytest.approx(
        0.05 + 8.8529281 + 0.1108184038239024 + 5, **APPROX
    )
    # Live diet: kills pay nothing. Only the hill walk-back remains
    # (win +5 is gone too).
    rets = rewards.compute_returns(gdict, 0, records)
    by_turn = {(r["turn"], tuple(r["loc"])): v for r, v in zip(records, rets)}
    # Kill: E1 died T2 at (8,8) — now unpaid. A1T2/A2T2 keep only their
    # hill shares; the T1 rows keep the GAMMA walk-back of those shares.
    # Hill walk-back (k = 6 - t): A1's own share 9.7723, A2's 10.
    assert by_turn[(2, (7, 5))] == pytest.approx(
        0.0 + 8.651410853765604 + 0.0 + 0, **APPROX
    )
    assert by_turn[(2, (7, 6))] == pytest.approx(
        0.0 + 8.8529281 + 0.0 + 0, **APPROX
    )
    assert by_turn[(1, (7, 4))] == pytest.approx(
        0.0 + 8.391868528152637 + 0.0 + 0, **APPROX
    )
    assert by_turn[(1, (7, 6))] == pytest.approx(
        0.0 + 8.587340257 + 0.0 + 0, **APPROX
    )


def test_live_hill_raze_pays_distance_scaled():
    game, _, _ = _play_main()
    gdict = _game_dict(game)
    records = _records(MAIN_ROWS)
    _join_ok(gdict["replaydata"], records)
    rets = rewards.compute_returns(gdict, 0, records)
    by_turn = {(r["turn"], tuple(r["loc"])): v for r, v in zip(records, rets)}
    # A2 stands on H1: full 10. A1 one tile off: 10*exp(-ln10/100).
    # Terminal is gone; A2's arrival pays no approach (on-hill skip).
    assert by_turn[(6, (4, 7))] == pytest.approx(10.0 + 0.0 + 0, **APPROX)
    assert by_turn[(6, (5, 7))] == pytest.approx(
        9.772372209558107 + 0.0 + 0, **APPROX
    )
    # Walk-back: each ant's own earlier rows earn share * GAMMA^(6-t).
    assert by_turn[(5, (5, 7))] == pytest.approx(
        9.7 + 0.0 + 0, **APPROX
    )
    assert by_turn[(5, (6, 7))] == pytest.approx(
        9.479201043271363 + 0.0 + 0, **APPROX
    )
    assert by_turn[(3, (7, 6))] == pytest.approx(
        8.918980261614026 + 0.0 + 0, **APPROX
    )


def test_live_approach_detected_but_unpaid():
    game, _, _ = _play_main()
    gdict = _game_dict(game)
    records = _records(MAIN_ROWS)
    awards, _, _, _, _ = rewards._awards(gdict, 0, records, rewards.scales())
    kinds = {kind for _, _, _, kind in awards}
    assert "hill_approach" in kinds
    rets = rewards.compute_returns(gdict, 0, records)
    by_turn = {(r["turn"], tuple(r["loc"])): v for r, v in zip(records, rets)}
    # A1's T4 march: hill walk-back k=2 survives; approach and win pay 0.
    assert by_turn[(4, (7, 7))] == pytest.approx(
        9.194825011973222 + 0.0 + 0, **APPROX
    )


# --------------------------------------------------------------------------
# Loss game: clean 2v1 kill (T1, unpaid), own hill razed (T2), P0
# loses. Only the flat hill loss pays.
# --------------------------------------------------------------------------
MAP_LOSS = """\
rows 13
cols 13
players 2
m .............
m .............
m .............
m .............
m ......aa.B...
m .............
m .............
m ....b........
m ....0...bb...
m .............
m .............
m .............
m .............
"""


def _play_loss():
    game = _new_game(MAP_LOSS, 2)
    _step(game, [(4, 6, "e"), (4, 7, "e")], [])
    _step(game, [], [(7, 4, "s")])
    return game


def test_live_loss_game_pays_only_hill_loss():
    game = _play_loss()
    hills = {(h[0], h[1]): (h[2], h[3]) for h in game.get_replay()["hills"]}
    assert hills[(8, 4)] == (0, 2), "H0 razed on turn 2"
    assert hills[(4, 9)][1] > 2, "P1 hill stands"
    gdict = _game_dict(game)
    assert gdict["score"] == [0, 3], "raze points decide: P0 loses"
    records = _records(
        [
            (1, (4, 6), (4, 7), "e"),
            (1, (4, 7), (4, 8), "e"),
            (2, (4, 7), (4, 7), "stay"),
            (2, (4, 8), (4, 8), "stay"),
        ]
    )
    _join_ok(gdict["replaydata"], records)
    awards, _, _, _, _ = rewards._awards(gdict, 0, records, rewards.scales())
    kinds = {kind for _, _, _, kind in awards}
    assert "hill_approach" in kinds, "marching happened"
    assert "kill" in kinds, "E1 died T1"
    rets = rewards.compute_returns(gdict, 0, records)
    by_turn = {(r["turn"], tuple(r["loc"])): v for r, v in zip(records, rets)}
    # Both T1 rows marched a full tile; approach and kills pay 0 now.
    # The hill loss is FLAT: every raze-turn row eats the full -10
    # (fleeing must not shrink it), walked back at GAMMA along each
    # ant's own path. Terminal is gone.
    assert by_turn[(1, (4, 6))] == pytest.approx(
        0.0 + 0.0 - 10 * 0.97 + 0, **APPROX
    )
    assert by_turn[(1, (4, 7))] == pytest.approx(
        0.0 + 0.0 - 10 * 0.97 + 0, **APPROX
    )
    assert by_turn[(2, (4, 7))] == pytest.approx(
        -10.0 + 0, **APPROX
    )
    assert by_turn[(2, (4, 8))] == pytest.approx(
        -10.0 + 0, **APPROX
    )


# --------------------------------------------------------------------------
# Food game: gather on T2, draw. Pins the 0.01 FOOD trickle and that
# the draw terminal pays nothing.
# --------------------------------------------------------------------------
MAP_FOOD = """\
rows 13
cols 13
players 2
m .............
m .............
m .............
m .............
m ....0...1....
m .............
m .............
m .....a.......
m .............
m .........b...
m .............
m .............
m .............
"""


def _play_food():
    game = _new_game(MAP_FOOD, 2)
    game.add_food((7, 7))
    _step(game, [], [])
    _step(game, [(7, 5, "e")], [])
    return game


def test_live_food_pays_tiny_and_decays():
    game = _play_food()
    food = [f for f in game.get_replay()["food"]]
    assert food == [[7, 7, 0, 2, 0]], "gathered end of turn 2 by P0"
    gdict = _game_dict(game)
    assert gdict["score"] == [1, 1], "no razes: draw"
    records = _records(
        [
            (1, (7, 5), (7, 5), "stay"),
            (2, (7, 5), (7, 6), "e"),
        ]
    )
    _join_ok(gdict["replaydata"], records)
    rets = rewards.compute_returns(gdict, 0, records)
    # Gathered: full 0.01 on the gathering row, 0.01*GAMMA walked back.
    # The draw terminal still pays nothing.
    assert rets[1] == pytest.approx(0.01 + 0.0, **APPROX)
    assert rets[0] == pytest.approx(0.01 * 0.97 + 0.0, **APPROX)


# --------------------------------------------------------------------------
# Defend vs flee: same threat, two answers. Successful interception
# (D) vs running away while the hill burns (F).
# --------------------------------------------------------------------------
MAP_DF = """\
rows 13
cols 13
players 2
m .............
m .............
m .............
m .............
m .............
m .............
m ....aa0.b....
m .............
m ........B....
m .............
m .............
m .............
m .............
"""


def _play_defend():
    game = _new_game(MAP_DF, 2)
    _step(game, [(6, 4, "e"), (6, 5, "e")], [(6, 8, "w")])
    assert _killed(game) == {((6, 7), 1)}, "E1 dies on the interception"
    _step(game, [], [])
    return game


def _play_flee():
    game = _new_game(MAP_DF, 2)
    _step(game, [(6, 4, "n"), (6, 5, "w")], [(6, 8, "w")])
    assert _killed(game) == set(), "E1 walks through unopposed"
    _step(game, [(5, 4, "n"), (6, 4, "w")], [(6, 7, "w")])
    return game


def test_live_defend_pays_nothing_without_raze():
    game = _play_defend()
    hills = {(h[0], h[1]): (h[2], h[3]) for h in game.get_replay()["hills"]}
    assert hills[(6, 6)][1] > 2, "H0 still stands: no hill award at all"
    gdict = _game_dict(game)
    assert gdict["score"] == [1, 1], "no razes: draw"
    records = _records(
        [
            (1, (6, 4), (6, 5), "e"),
            (1, (6, 5), (6, 6), "e"),
            (2, (6, 5), (6, 5), "stay"),
            (2, (6, 6), (6, 6), "stay"),
        ]
    )
    _join_ok(gdict["replaydata"], records)
    awards, _, _, _, _ = rewards._awards(gdict, 0, records, rewards.scales())
    kinds = {kind for _, _, _, kind in awards}
    assert "hill" not in kinds
    rets = rewards.compute_returns(gdict, 0, records)
    rets = rewards.compute_returns(gdict, 0, records)
    # No raze, no terminal: the interception kill pays 0, approach 0.
    assert rets[0] == pytest.approx(0.0 + 0.0 + 0.0, **APPROX)
    assert rets[1] == pytest.approx(0.0 + 0.0 + 0.0, **APPROX)
    assert rets[2] == pytest.approx(0.0, **APPROX)
    assert rets[3] == pytest.approx(0.0, **APPROX)


def test_live_flee_lets_hill_burn_and_loss_follows():
    game = _play_flee()
    hills = {(h[0], h[1]): (h[2], h[3]) for h in game.get_replay()["hills"]}
    assert hills[(6, 6)] == (0, 2), "H0 razed on turn 2"
    gdict = _game_dict(game)
    assert gdict["score"] == [0, 3], "raze points flip it: P0 loses"
    records = _records(
        [
            (1, (6, 4), (5, 4), "n"),
            (1, (6, 5), (6, 4), "w"),
            (2, (5, 4), (4, 4), "n"),
            (2, (6, 4), (6, 3), "w"),
        ]
    )
    _join_ok(gdict["replaydata"], records)
    rets = rewards.compute_returns(gdict, 0, records)
    # Fleeing marches AWAY from the enemy hill: approach 0 everywhere.
    # The raze still reaches back at the FULL flat -10 (distance no
    # longer shrinks it), walked back at GAMMA to the fleeing rows.
    # Terminal is gone: fleeing now pays -10 on the raze rows.
    assert rets[0] == pytest.approx(-10 * 0.97 + 0, **APPROX)
    assert rets[1] == pytest.approx(-10 * 0.97 + 0, **APPROX)
    assert rets[2] == pytest.approx(-10.0 + 0, **APPROX)
    assert rets[3] == pytest.approx(-10.0 + 0, **APPROX)


# --------------------------------------------------------------------------
# Perception: the real bot on real engine vision strings.
# --------------------------------------------------------------------------
MAP_SEE = """\
rows 25
cols 25
players 2
m .........................
m .........................
m .........................
m .........................
m .........................
m .........................
m .........................
m .........................
m ........0.......1........
m .........................
m .........................
m .............%...........
m ............a............
m .........................
m .........................
m .........................
m .........................
m .........................
m .........................
m ............a......b.....
m .........................
m .........................
m .........................
m .........................
m .........................
"""
# A1 (12,12), ally (19,12), enemy E1 (19,19). E1 sits in A1's window
# corner (offset (+7,+7), raw d2=98): outside A1's own circle but
# inside the ally's (d2=49) — visible ONLY through team sight.
# Food at (5,5) (window corner (-7,-7)) is seen by nobody: stays fogged.


def test_live_perception_sees_all_channels(tmp_path, monkeypatch):
    import AlphaAnt  # runtime import: same ENGINE-ants binding as the suite

    monkeypatch.setenv("AA_RECORD_DIR", str(tmp_path))
    game = _new_game(MAP_SEE, 1)
    game.add_food((12, 14))  # visible: offset (0,+2) from A1
    game.add_food((5, 5))  # fogged: seen by nobody
    # Protocol order: the turn-1 state is read BEFORE start_turn, so it
    # still carries the initially revealed water (start_turn resets it).
    state = game.get_player_state(0)
    _step(game, [], [])
    start = game.get_player_start(0)

    ants = BotAnts()
    ants.setup(start)

    bot = AlphaAnt.AlphaAntBot()
    bot.do_setup(ants)
    ants.update(state)
    assert ants.ant_list == {(12, 12): 0, (19, 12): 0, (19, 19): 1}, (
        "engine vision round-trips"
    )
    assert ants.food_list == [(12, 14)], "fogged food never sent"
    assert ants.hill_list == {(8, 8): 0, (8, 16): 1}
    bot.do_turn(ants)

    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    rows = [json.loads(line) for line in files[0].read_text().splitlines()]
    mine = [r for r in rows if r["loc"] == [12, 12]]
    assert len(mine) == 1
    grid = features.decode_window(mine[0]["window"])
    assert grid.shape == (features.INPUT_CHANNELS, 15, 15)
    assert grid[10:].sum() == 0.0, "first sight has no past"
    r = features.DEFAULT_RADIUS
    # Own cell, ally (offset (+7,0)), hills, water, visible food.
    assert grid[features.WATER_CHANNEL, r - 1, r + 1] == 1.0, "water"
    assert grid[1, r, r] == 1.0, "own ant"
    assert grid[1, r + 7, r] == 1.0, "ally in window"
    assert grid[1].sum() == 2.0, "no ant leakage"
    assert grid[2, r - 4, r - 4] == 1.0, "own hill (8,8)"
    assert grid[4, r - 4, r + 4] == 1.0, "enemy hill (8,16)"
    assert grid[5, r, r + 2] == 1.0, "food (12,14)"
    assert grid[5].sum() == 1.0, "fogged food never fills"
    assert grid[features.OWN_SIGHT_CHANNEL, r, r] == 1.0, "own cell in sight"
    # Team sight, positive: E1 at (19,19) is in A1's window corner
    # (offset (+7,+7), raw d2=98) but outside A1's own circle — only
    # the ally at (19,12) sees it (d2=49). Fills iff the mask is team.
    assert grid[3, r + 7, r + 7] == 1.0, "ally-covered enemy fills"
    assert grid[features.OWN_SIGHT_CHANNEL, r + 7, r + 7] == 1.0
    assert grid[3].sum() == 1.0, "no enemy leakage"
    # Fog preserved: corner (-7,-7) is cell (5,5), seen by nobody.
    assert grid[5, 0, 0] == 0.0, "unseen food stays fogged"
    assert grid[features.OWN_SIGHT_CHANNEL, 0, 0] == 0.0
