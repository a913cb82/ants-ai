"""Swap mechanics: reserve destinations, not origins.

(a) Head-to-head 2-ant swap executes BOTH moves (old code blocked the
second ant: the vacated origin sat in the initial reserved set, so
adjacent swaps were inexpressible).
(b) Rotation cycles among intended moves all execute (each destination
is vacated simultaneously). Grids are bipartite so only even cycles
are constructible in-game: the integration test uses a 2x2 4-cycle,
and the pure cycle finder is pinned with an abstract 3-cycle.
(c) Non-cycle conflicts keep first-claimant-wins: orders are
byte-identical to the HEAD (pre-swap) bot when no cycle exists.
"""

import importlib.util
import json
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))

import features

ACTION_INDEX = {a: i for i, a in enumerate(features.ACTIONS)}


class StubAnts:
    rows, cols = 10, 10
    viewradius2 = 77

    def __init__(self, mine, clock=(1000,)):
        self._mine = list(mine)
        self._clock = list(clock)
        self.orders = []

    def my_ants(self):
        return list(self._mine)

    def enemy_ants(self):
        return []

    def food(self):
        return []

    def my_hills(self):
        return []

    def enemy_hills(self):
        return []

    def destination(self, loc, d):
        r, c = loc
        return {
            "n": ((r - 1) % self.rows, c),
            "s": ((r + 1) % self.rows, c),
            "e": (r, (c + 1) % self.cols),
            "w": (r, (c - 1) % self.cols),
        }[d]

    def passable(self, loc):
        return True

    def issue_order(self, order):
        self.orders.append(order)

    def time_remaining(self):
        return self._clock.pop(0) if len(self._clock) > 1 else self._clock[0]


def _bot(tmp_path, monkeypatch, logits):
    import AlphaAnt

    monkeypatch.setenv("AA_RECORD_DIR", str(tmp_path))
    bot = AlphaAnt.AlphaAntBot()
    bot.policy = lambda x: logits  # fixed desires, independent of input
    return bot


def _want(action):
    vec = [0.0] * 5
    vec[ACTION_INDEX[action]] = 10.0
    return vec


def _head_bot(path):
    """Load the HEAD (pre-swap) AlphaAnt.py under a distinct module name."""
    src = subprocess.run(
        ["git", "-C", str(ROOT), "show", "HEAD:bots/alphaant/AlphaAnt.py"],
        capture_output=True, text=True, check=True,
    ).stdout
    path.write_text(src)
    import shutil

    shutil.copy(ROOT / "bots" / "alphaant" / "weights.json",
                path.parent / "weights.json")
    spec = importlib.util.spec_from_file_location("AlphaAntHEAD", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_head_to_head_swap_executes_both_moves(tmp_path, monkeypatch):
    """A->B, B->A: both orders must issue (old code blocked the mover
    into the vacated origin)."""
    import AlphaAnt

    ants = StubAnts([(4, 4), (4, 5)])
    logits = torch.tensor([_want("e"), _want("w")])
    bot = _bot(tmp_path, monkeypatch, logits)
    bot.do_setup(ants)
    bot.do_turn(ants)
    assert sorted(map(tuple, ants.orders)) == [
        ((4, 4), "e"),
        ((4, 5), "w"),
    ]


def test_rotation_cycle_executes(tmp_path, monkeypatch):
    """2x2 rotation: each destination is vacated simultaneously, so all
    four moves execute (old code blocked three of them)."""
    import AlphaAnt

    ants = StubAnts([(4, 4), (4, 5), (5, 5), (5, 4)])
    logits = torch.tensor([_want("e"), _want("s"), _want("w"), _want("n")])
    bot = _bot(tmp_path, monkeypatch, logits)
    bot.do_setup(ants)
    bot.do_turn(ants)
    assert sorted(map(tuple, ants.orders)) == [
        ((4, 4), "e"),
        ((4, 5), "s"),
        ((5, 4), "n"),
        ((5, 5), "w"),
    ]


def test_cycle_finder_detects_two_three_and_four_cycles():
    """Pure resolution helper: 2/3/4-cycles found, chains and stays
    ignored. (Odd cycles can't occur on a bipartite grid, but the
    finder is length-general.)"""
    import AlphaAnt

    two = {(0, 0): (0, 1), (0, 1): (0, 0)}
    assert AlphaAnt.find_cycles(two) == [{(0, 0), (0, 1)}]
    three = {(0, 0): (0, 1), (0, 1): (0, 2), (0, 2): (0, 0)}
    assert AlphaAnt.find_cycles(three) == [{(0, 0), (0, 1), (0, 2)}]
    four = {(4, 4): (4, 5), (4, 5): (5, 5), (5, 5): (5, 4), (5, 4): (4, 4)}
    assert AlphaAnt.find_cycles(four) == [
        {(4, 4), (4, 5), (5, 5), (5, 4)}]
    # Chain into a free square is not a cycle; stays are not cycles.
    chain = {(4, 4): (4, 5), (4, 5): (4, 6)}
    assert AlphaAnt.find_cycles(chain) == []
    stays = {(4, 4): (4, 4), (4, 5): (4, 5)}
    assert AlphaAnt.find_cycles(stays) == []


def test_non_cycle_conflict_byte_identical_to_head(tmp_path, monkeypatch):
    """Same-target conflict, no cycle: orders must match the HEAD bot
    exactly (first-claimant-wins preserved)."""
    import AlphaAnt

    ants = StubAnts([(4, 4), (4, 6)])
    # ant1 takes (4,5); ant2 wants w=(4,5, taken), falls back to n.
    logits = torch.tensor([_want("e"), [5.0, 0.0, 0.0, 10.0, 0.0]])
    bot = _bot(tmp_path, monkeypatch, logits)
    bot.do_setup(ants)
    bot.do_turn(ants)
    new_orders = list(ants.orders)

    head_mod = _head_bot(tmp_path / "AlphaAntHEAD.py")
    head_ants = StubAnts([(4, 4), (4, 6)])
    monkeypatch.setenv("AA_RECORD_DIR", str(tmp_path / "head"))
    (tmp_path / "head").mkdir()
    head_bot = head_mod.AlphaAntBot()
    head_bot.policy = lambda x: logits
    head_bot.do_setup(head_ants)
    head_bot.do_turn(head_ants)
    assert new_orders == head_ants.orders
    assert [o for o in new_orders] == [((4, 4), "e"), ((4, 6), "n")]


def test_mover_into_vacated_non_cycle_square_executes(tmp_path, monkeypatch):
    """Chain A->B-origin with B leaving elsewhere: the mover is no
    longer blocked by the vacated origin (mechanism 1)."""
    import AlphaAnt

    ants = StubAnts([(4, 4), (4, 5)])
    # ant1 vacates east; ant0 follows into (4,5).
    logits = torch.tensor([_want("e"), _want("e")])
    bot = _bot(tmp_path, monkeypatch, logits)
    bot.do_setup(ants)
    bot.do_turn(ants)
    assert sorted(map(tuple, ants.orders)) == [
        ((4, 4), "e"),
        ((4, 5), "e"),
    ]


def test_mover_into_staying_ant_square_still_blocked(tmp_path, monkeypatch):
    """A stayer's square is never claimable: the mover falls back and
    no two ants share a destination (engine kills collisions)."""
    import AlphaAnt

    ants = StubAnts([(4, 4), (4, 5)])
    # ant1 stays; ant0 wants e=(4,5, occupied at end) -> falls back.
    logits = torch.tensor([_want("e"), _want("stay")])
    bot = _bot(tmp_path, monkeypatch, logits)
    bot.do_setup(ants)
    bot.do_turn(ants)
    dests = [ants.destination(loc, d) for loc, d in ants.orders]
    assert len(set(dests)) == len(dests)  # unique destinations
    assert ((4, 5), "stay") not in ants.orders  # stays never issue
    assert ((4, 4), "e") not in ants.orders  # mover did not take it
