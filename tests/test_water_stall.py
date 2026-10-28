"""Anti-stall shaping: same-turn micro-tax on unproductive stays near water.

TDD seed (fails before the tax exists): a stay is taxed iff a water
tile sits within Chebyshev 1..2 of the post-move tile AND no enemy is
within attackradius2 (defense stays are exempt). Moves, open-ground
stays, and enemy-adjacent stays pay nothing. The tax is same-turn only
(linear accumulation, no walk-back), main-line only (rivals untaxed),
and gated behind an opt-in flag that defaults to legacy behavior.
"""

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))


def _map_data(waters, rows=10, cols=10):
    grid = [["."] * cols for _ in range(rows)]
    for r, c in waters:
        grid[r][c] = "%"  # engine render for WATER (tools/ants.py)
    return ["".join(row) for row in grid]


def _game(waters=(), enemies=(), score=(0, 0)):
    return {
        "score": list(score),
        "status": ["survived", "survived"],
        "length": 10,
        "replaydata": {
            "map": {"rows": 10, "cols": 10, "data": _map_data(waters)},
            "viewradius2": 77,
            "attackradius2": 5,
            "food": [],
            "ants": list(enemies),
            "hills": [],
        },
    }


def test_tax_fires_on_stay_near_water():
    import rewards

    game = _game(waters=[(5, 7)])  # Chebyshev-2 from (5, 5)
    records = [{"turn": 3, "loc": [5, 5], "dest": [5, 5], "action": "stay"}]
    rets = rewards.compute_returns(game, 0, records, enable_water_stall=True)
    assert rets == [rewards.STAY_NEAR_WATER]


def test_tax_fires_on_adjacent_water_chebyshev1():
    import rewards

    game = _game(waters=[(5, 6)])  # Chebyshev-1 from (5, 5)
    records = [{"turn": 3, "loc": [5, 5], "dest": [5, 5], "action": "stay"}]
    rets = rewards.compute_returns(game, 0, records, enable_water_stall=True)
    assert rets == [rewards.STAY_NEAR_WATER]


def test_no_tax_on_stay_with_enemy_near():
    import rewards

    # Enemy holds (5, 6): dist2 1 <= attackradius2 — a holding stay is
    # legitimate defense (the turtle minority), not dwelling.
    game = _game(waters=[(5, 7)], enemies=[[5, 6, 1, 4, 1, "--"]])
    records = [{"turn": 3, "loc": [5, 5], "dest": [5, 5], "action": "stay"}]
    rets = rewards.compute_returns(game, 0, records, enable_water_stall=True)
    assert rets == [0.0]


def test_no_tax_on_move_near_water():
    import rewards

    game = _game(waters=[(5, 7)])
    records = [{"turn": 3, "loc": [5, 4], "dest": [5, 5], "action": "e"}]
    rets = rewards.compute_returns(game, 0, records, enable_water_stall=True)
    assert rets == [0.0]


def test_no_tax_on_open_ground_stay():
    import rewards

    game = _game(waters=[(5, 7)])
    records = [{"turn": 3, "loc": [0, 0], "dest": [0, 0], "action": "stay"}]
    rets = rewards.compute_returns(game, 0, records, enable_water_stall=True)
    assert rets == [0.0]


def test_no_tax_at_chebyshev3():
    import rewards

    game = _game(waters=[(5, 8)])  # Chebyshev-3 from (5, 5): outside
    records = [{"turn": 3, "loc": [5, 5], "dest": [5, 5], "action": "stay"}]
    rets = rewards.compute_returns(game, 0, records, enable_water_stall=True)
    assert rets == [0.0]


def test_tax_accumulates_linearly_no_walkback():
    import rewards

    game = _game(waters=[(5, 7)])
    n = 5
    records = [
        {"turn": t, "loc": [5, 5], "dest": [5, 5], "action": "stay"}
        for t in range(1, n + 1)
    ]
    rets = rewards.compute_returns(game, 0, records, enable_water_stall=True)
    assert rets == [rewards.STAY_NEAR_WATER] * n
    assert sum(rets) == n * rewards.STAY_NEAR_WATER


def test_tax_applies_on_draw_ungated():
    import rewards

    # Draws zero the march/kill subsidies, but the stall tax is a cost,
    # not a subsidy: dwelling in a drawn game still pays.
    game = _game(waters=[(5, 7)], score=(0, 0))
    records = [{"turn": 3, "loc": [5, 5], "dest": [5, 5], "action": "stay"}]
    rets = rewards.compute_returns(
        game, 0, records, rewards.scales_for("challenger"), "challenger",
        enable_water_stall=True)
    assert rets == [rewards.STAY_NEAR_WATER]


def test_tax_main_line_only_rivals_untaxed():
    import rewards

    game = _game(waters=[(5, 7)])
    records = [{"turn": 3, "loc": [5, 5], "dest": [5, 5], "action": "stay"}]
    for role in ("exploiter", "spoiler"):
        rets = rewards.compute_returns(
            game, 0, records, rewards.scales_for(role), role,
            enable_water_stall=True)
        assert rets == [0.0], role


def test_gate_off_reproduces_legacy():
    import rewards

    # Mixed batch (food + kill + death + approach + win terminal): with
    # the flag off, a water-adjacent stay prices exactly as legacy.
    assert rewards.ENABLE_WATER_STALL_TAX is False
    game = _game(waters=[(5, 7)], score=[2, 0])
    game["replaydata"]["food"] = [[5, 6, 1, 3, 0]]
    game["replaydata"]["ants"] = [
        [5, 5, 1, 3, 0, "--"],  # own ant dies turn 3 on (5, 5)
        [5, 4, 1, 3, 1, "--"],  # enemy dies turn 3 on (5, 4)
    ]
    game["replaydata"]["hills"] = [[9, 9, 1, 999]]
    records = [
        # rec0 sits on food/death/kill tiles (stay near water, flag off).
        {"turn": 3, "loc": [5, 5], "dest": [5, 5], "action": "stay"},
        # rec1 marches toward the hill: HA only, no walk-back linkage.
        {"turn": 1, "loc": [0, 0], "dest": [9, 0], "action": "n"},
    ]
    s = rewards.scales_for("challenger")
    rets = rewards.compute_returns(game, 0, records, s, "challenger")
    closed = math.sqrt(2) - 1
    assert rets == [1.0 + 1.0 + rewards.DEATH + rewards.WIN,
                    0.25 * closed + rewards.WIN]


def test_missing_map_data_never_taxes():
    import rewards

    game = _game()
    del game["replaydata"]["map"]["data"]
    records = [{"turn": 3, "loc": [5, 5], "dest": [5, 5], "action": "stay"}]
    rets = rewards.compute_returns(game, 0, records, enable_water_stall=True)
    assert rets == [0.0]


def test_magnitude_small_vs_real_events():
    import rewards

    t = abs(rewards.STAY_NEAR_WATER)
    assert t <= 0.10 * rewards.FOOD  # one tax never outweighs a real event
    assert t <= 0.05 * abs(rewards.DEATH)  # dodging it is never worth dying
