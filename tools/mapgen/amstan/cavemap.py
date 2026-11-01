#!/usr/bin/env python

import random

from symmetricmap import SymmetricMap
from terrain import LAND, WATER, Point, diag_directions, directions

# Frozen smoothing-kernel offsets as plain (dx, dy) ints, taken from the
# same diag_directions dict in the same order. smooth() only uses the
# *count* of water neighbors, so iterating this tuple counts identically
# while avoiding per-cell dict/list/Point churn.
_NEIGHBOR_OFFSETS = tuple((d.x, d.y) for d in diag_directions.values())

# Frozen walk steps. random.choice over this tuple draws the identical RNG
# stream as choice(list(directions.values())) (same length, one _randbelow
# per call), without rebuilding the list on every step.
_WALK_STEPS = tuple(directions.values())


class Cavemap(SymmetricMap):
    def __init__(self, **kwargs):
        kwargs["defaultterrain"] = WATER
        SymmetricMap.__init__(self, **kwargs)

    def add_water_randomly(self, percent=0.49):
        for point in self.size.upto():
            self[point] = LAND
            if random.random() < percent:
                self[point] = WATER

    def random_walk(self, start, cover=0.5):
        total_squares = self.size.x * self.size.y
        squares_water = 0
        symmetric_locations = len(self.symmetry_vector(Point(0, 0)))

        location = start

        while squares_water < total_squares * cover:
            if self[location] == WATER:
                self[location] = LAND
                squares_water += symmetric_locations

            location += random.choice(_WALK_STEPS)

    def smooth(self, times=1):
        """Apply a cellular automaton to smoothen the walls"""
        water = WATER
        land = LAND
        width = self.size.x
        height = self.size.y
        offsets = _NEIGHBOR_OFFSETS
        # Twin-cell table: twins[y][x] lists every (tx, ty) cell written
        # by self[Point(x, y)] = value. Derived from the same
        # symmetry_vector (single source of truth), so the written cells
        # are identical while per-cell Point/symmetry/normalize dispatch
        # is paid once instead of on every smoothing iteration.
        vector = self.symmetry_vector
        twins = [
            [tuple((p.x, p.y) for p in vector(Point(x, y))) for x in range(width)]
            for y in range(height)
        ]
        terrain = self.terrain
        for _time in range(times):
            # Snapshot of the pre-iteration terrain: reads below see it,
            # writes go to self.terrain, same as the old self.copy()
            # read pattern. Cells are visited in the same order with the
            # same values as the old self[point] writes, so the final
            # terrain is identical.
            old = [row[:] for row in terrain]
            for y in range(height):
                twinrow = twins[y]
                for x in range(width):
                    neighbour_water = 0
                    for dx, dy in offsets:
                        if old[(y + dy) % height][(x + dx) % width] == water:
                            neighbour_water += 1

                    if neighbour_water < 4:
                        value = land
                    elif neighbour_water > 4:
                        value = water
                    else:
                        continue
                    for tx, ty in twinrow[x]:
                        terrain[ty][tx] = value

    def generate(self, **kwargs):
        self.random_walk(list(self.hills())[0])

        try:
            self.smooth(kwargs["smooth"])
        except KeyError:
            self.smooth(4)


if __name__ == "__main__":
    # random.seed(6)

    size = Point(60, 60)
    playerone = size.random_upto() * (0.5 / 3) + size * (0.5 / 3)

    map = Cavemap(size=size, num_players=4, symmetry="translational")

    map.add_hill(playerone)
    map.generate()

    print(map)
