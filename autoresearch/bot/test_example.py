"""Correctness tests for the example bot.

The pattern every entry follows: a small fake world, then pins that
every order is legal. FakeAnts implements just the surface the bot
touches.
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Example as EB  # noqa: E402

ROWS = 20
COLS = 20
AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}


class FakeAnts:
    """Tiny toroidal world with one ant, food, and foes."""

    def __init__(self, own, foods, foes, water=()):
        self._own = list(own)
        self._foods = list(foods)
        self._foes = list(foes)
        self._water = set(water)
        self.orders = []

    def my_ants(self):
        return list(self._own)

    def food(self):
        return list(self._foods)

    def enemy_ants(self):
        return [(f, 1) for f in self._foes]

    def distance(self, a_row, a_col, b_row, b_col):
        dr = min(abs(a_row - b_row), ROWS - abs(a_row - b_row))
        dc = min(abs(a_col - b_col), COLS - abs(a_col - b_col))
        return dr + dc

    def direction(self, a_row, a_col, b_row, b_col):
        d = []
        if a_row != b_row:
            d.append("s" if (b_row - a_row) % ROWS < ROWS // 2 else "n")
        if a_col != b_col:
            d.append("e" if (b_col - a_col) % COLS < COLS // 2 else "w")
        return d or ["n"]

    def destination(self, row, col, direction):
        dr, dc = AIM[direction]
        return ((row + dr) % ROWS, (col + dc) % COLS)

    def unoccupied(self, row, col):
        return (row, col) not in self._water

    def issue_order(self, order):
        self.orders.append(order)


def run(own, foods, foes, seed=0, water=()):
    random.seed(seed)
    ants = FakeAnts(own, foods, foes, water)
    EB.Example().do_turn(ants)
    return ants


def test_hunts_nearest_food():
    ants = run([(10, 10)], [(10, 13), (10, 5)], [])
    assert ants.orders, "ant with food in sight must move"
    row, col, direction = ants.orders[0]
    assert (row, col) == (10, 10)
    assert direction in ("e", "w")


def test_one_order_per_ant():
    ants = run([(5, 5), (5, 6)], [(0, 0)], [(19, 19)])
    locs = [(o[0], o[1]) for o in ants.orders]
    assert len(locs) == len(set(locs)), "no ant moves twice"


def test_orders_land_off_water():
    water = [(10, 11)]
    ants = run([(10, 10)], [(10, 12)], [], water=water)
    for row, col, direction in ants.orders:
        dest = ants.destination(row, col, direction)
        assert dest not in water


def test_no_targets_no_orders():
    ants = run([(7, 7)], [], [])
    assert ants.orders == []


def test_chases_foe_when_closer_than_food():
    ants = run([(10, 10)], [(0, 0)], [(10, 12)])
    assert ants.orders, "ant with a close foe must move"
    row, col, direction = ants.orders[0]
    assert (row, col) == (10, 10)
