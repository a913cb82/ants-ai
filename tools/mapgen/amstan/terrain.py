#!/usr/bin/env python

from util import Point

directions = {"N": Point(-1, 0), "S": Point(1, 0), "E": Point(0, 1), "W": Point(0, -1)}
diag_directions = {
    "NW": Point(-1, -1),
    "SW": Point(1, -1),
    "NE": Point(-1, 1),
}
diag_directions.update(directions)

WATER = "%"
LAND = "."


class Terrain:
    """Terrain class contains only map size and terrain data.
    It does not concern itself with players and symmetries"""

    def __init__(self, **kwargs):
        self.size = kwargs["size"]

        try:
            defaultterrain = kwargs["defaultterrain"]
        except KeyError:
            defaultterrain = LAND
        self.terrain = [
            [defaultterrain for x in range(self.size.x)] for y in range(self.size.y)
        ]

    def __getitem__(self, point):
        """Gets a point in the terrain"""
        point = point.normalize(self.size)
        return self.terrain[point.y][point.x]

    def __setitem__(self, point, value):
        """Sets a point in the terrain"""
        point = point.normalize(self.size)
        self.terrain[point.y][point.x] = value

    def copy(self):
        """Makes a copy of this map"""
        newterrain = Terrain(size=self.size)
        for point in self.size.upto():
            newterrain[point] = self[point]
        return newterrain

    def render(self):
        string = f"rows {self.size.y}\n"
        string += f"cols {self.size.x}\n"

        for y in range(self.size.y):
            string += "m "
            for x in range(self.size.x):
                string += self[Point(x, y)]
            string += "\n"

        return string[:-1]

    def __str__(self):
        return self.render()


if __name__ == "__main__":
    terrain = Terrain(size=Point(10, 10))
    terrain[Point(-1, -1)] = WATER
    print(terrain)
