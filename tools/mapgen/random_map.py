#!/usr/bin/env python
import sys
from optparse import OptionParser
from random import randint

from map import LAND, WATER, Map


class RandomMap(Map):
    def __init__(self, options=None):
        if options is None:
            options = {}
        super().__init__(options)
        self.name = "random"
        self.rows = options.get("rows", (40, 120))
        self.cols = options.get("cols", (40, 120))
        self.players = options.get("players", (2, 26))
        self.land = options.get("land", (80, 95))

    def generate(self):
        rows = self.get_random_option(self.rows)
        cols = self.get_random_option(self.cols)
        players = self.get_random_option(self.players)
        land = self.get_random_option(self.land)

        # initialize map
        self.map = [[LAND] * cols for _ in range(rows)]

        # place water
        water = rows * cols * (100 - land) // 100
        row = 0
        col = 0
        for _ in range(water):
            while self.map[row][col] == WATER:
                row = randint(0, rows - 1)
                col = randint(0, cols - 1)
            self.map[row][col] = WATER

        # place player starts
        for player in range(players):
            while self.map[row][col] != LAND:
                row = randint(0, rows - 1)
                col = randint(0, cols - 1)
            self.map[row][col] = player


def main(argv=None):
    parser = OptionParser()
    parser.add_option("--rows", dest="rows", type="int", help="exact row count")
    parser.add_option("--cols", dest="cols", type="int", help="exact col count")
    parser.add_option(
        "--players", dest="players", type="int", help="exact player count"
    )
    parser.add_option("--seed", dest="seed", type="int", help="random seed")
    opts, _ = parser.parse_args(argv)

    options = {}
    if opts.rows is not None:
        options["rows"] = opts.rows
    if opts.cols is not None:
        options["cols"] = opts.cols
    if opts.players is not None:
        options["players"] = opts.players
    if opts.seed is not None:
        options["seed"] = opts.seed

    new_map = RandomMap(options)
    new_map.generate()
    new_map.toText()


if __name__ == "__main__":
    main(sys.argv[1:])
