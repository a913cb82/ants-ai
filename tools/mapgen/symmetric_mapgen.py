#!/usr/bin/env python

import math
import random
import sys


# Direction deltas shared by the hot loops. Order matches
# SymmetricMap.directions.values() (N, S, E, W); _WALK_DELTAS matches
# SymmetricMap.cdirections order (N, E, S, W). Tuple lookup avoids a
# per-call list() copy and dict lookup with identical neighbor order.
_NEIGHBOR_DELTAS = ((-1, 0), (1, 0), (0, 1), (0, -1))
_WALK_DELTAS = ((-1, 0), (0, 1), (1, 0), (0, -1))


# functions
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a


def lcm(a, b):
    if a == 0 and b == 0:
        return 0
    else:
        return abs(a * b) // gcd(a, b)


# map class
class SymmetricMap:
    cdirections = ["N", "E", "S", "W"]
    directions = {"N": (-1, 0), "S": (1, 0), "E": (0, 1), "W": (0, -1)}

    # game parameters
    min_players = 2
    max_players = 10
    per_player_dim = (10, 50)
    dim_bounds = (50, 150)
    min_start_distance = 30

    min_land_proportion = 0.60
    max_land_proportion = 0.98

    no_extra_walks = 30

    # map parameters
    no_players = 0
    rows = cols = 0
    row_t: float = 0
    col_t: float = 0
    # CLI overrides (None keeps the classic random behavior)
    fixed_players: int | None = None
    fixed_rows: int | None = None
    fixed_cols: int | None = None
    water_squares = 0
    land_squares = 0
    map_data: list = []
    times_visited: list = []
    a_loc: list = []
    c_locs: list = a_loc

    # makes a map by performing a bunch of random walks carving out water
    def random_walk_map(self):
        self.pick_dimensions()
        self.map_data = [["%"] * self.cols for _r in range(self.rows)]
        self.add_ants()
        self.start_walks()
        self.add_walk_land()

    # outputs the map
    def print_map(self):
        # Single write; bytes are identical to the old per-row prints
        # ("rows %s\n", "m %s\n", ... with sep=" ", end="\n").
        lines = ["rows " + str(self.rows), "cols " + str(self.cols),
                 "players " + str(self.no_players)]
        lines.extend("m " + "".join(row) for row in self.map_data)
        sys.stdout.write("\n".join(lines) + "\n")

    # picks the dimensions of the map
    def pick_dimensions(self):
        if (
            self.fixed_players is not None
            and self.fixed_rows is not None
            and self.fixed_cols is not None
        ):
            self.no_players = self.fixed_players
            self.rows = self.fixed_rows
            self.cols = self.fixed_cols
            if self.rows % self.no_players != 0 or self.cols % self.no_players != 0:
                raise ValueError("rows and cols must be divisible by players")
            # row_p = col_p = 1 is always coprime; translation by a full
            # per-player share keeps the lcm player count at no_players.
            self.row_t = (self.rows // self.no_players) * 1
            self.col_t = (self.cols // self.no_players) * 1
            if not self.is_valid_start():
                raise RuntimeError(
                    "fixed dims give no valid start; lower --min_start_distance"
                )
            return
        while True:
            while True:
                no_players = random.randint(self.min_players, self.max_players)
                self.no_players = no_players

                min_dim = max(self.per_player_dim[0] * no_players, self.dim_bounds[0])
                max_dim = min(self.per_player_dim[1] * no_players, self.dim_bounds[1])
                self.rows = random.randint(min_dim, max_dim)
                # make maps generally wider than they are tall
                min_cols = max(min_dim, int(self.rows * 0.80))
                max_cols = min(max_dim, int(self.rows * 2))
                self.cols = random.randint(min_cols, max_cols)

                if self.rows % no_players == 0 and self.cols % no_players == 0:
                    break

            row_p = random.randint(1, no_players - 1)
            while gcd(row_p, no_players) != 1:
                row_p = random.randint(1, no_players - 1)
            self.row_t = (self.rows // no_players) * row_p

            col_p = random.randint(1, no_players - 1)
            while gcd(col_p, no_players) != 1:
                col_p = random.randint(1, no_players - 1)
            self.col_t = (self.cols // no_players) * col_p

            if self.is_valid_start():
                break

    # returns the distance between two squares
    def distance(self, loc1, loc2):
        d1 = abs(loc1[0] - loc2[0])
        d2 = abs(loc1[1] - loc2[1])
        dr = min(d1, self.rows - d1)
        dc = min(d2, self.cols - d2)
        return math.sqrt(dr * dr + dc * dc)

    # randomly picks a location inside the map
    def pick_square(self):
        return [random.randint(0, self.rows - 1), random.randint(0, self.cols - 1)]

    # starts two random walks from the players starting ants
    def start_walks(self):
        self.c_locs = [self.a_loc, self.a_loc]
        for _w in range(self.no_extra_walks):
            self.c_locs.append(self.pick_square())

    # walks the random walk locations
    def walk_locations(self):
        # Same RNG sequence (one randint(0, 3) per loc, in order) and same
        # wrap arithmetic as get_loc; deltas are indexed directly instead
        # of going through cdirections + the directions dict.
        deltas = _WALK_DELTAS
        rows = self.rows
        cols = self.cols
        randint = random.randint
        locs = self.c_locs
        for c in range(len(locs)):
            dr, dc = deltas[randint(0, 3)]
            loc = locs[c]
            locs[c] = [(loc[0] + dr) % rows, (loc[1] + dc) % cols]

    # returns the new location after moving in a particular direction
    def get_loc(self, loc, direction):
        dr, dc = self.directions[direction]
        return [(loc[0] + dr) % self.rows, (loc[1] + dc) % self.cols]

    # return the neighbors of the given location
    def get_neighbors(self, loc):
        # Same order as before (N, S, E, W) without the list() copy.
        r0 = loc[0]
        c0 = loc[1]
        rows = self.rows
        cols = self.cols
        return [((r0 + dr) % rows, (c0 + dc) % cols)
                for dr, dc in _NEIGHBOR_DELTAS]

    # returns the new location after translating it by (rtranslate, ctranslate)
    def get_translate_loc(self, loc):
        return [(loc[0] + self.row_t) % self.rows, (loc[1] + self.col_t) % self.cols]

    # fills in all symmetrically equivalent squares with the given type
    def fill_squares(self, loc, type):
        # Same writes in the same order; translate arithmetic inlined.
        data = self.map_data
        row_t = self.row_t
        col_t = self.col_t
        rows = self.rows
        cols = self.cols
        r = loc[0]
        c = loc[1]
        value = type
        for _n in range(self.no_players):
            data[r][c] = value
            if type == "0":
                value = chr(ord(value) + 1)
            r = (r + row_t) % rows
            c = (c + col_t) % cols

    # checks whether the players start far enough apart
    def is_valid_start(self):
        loc = n_loc = [0, 0]
        for _n in range(self.no_players - 1):
            n_loc = self.get_translate_loc(n_loc)
            if self.distance(loc, n_loc) < self.min_start_distance:
                return False
        return True

    # checks whether the players can reach every non-wall square
    def is_valid(self):
        # Flood-fill count; the reachable set (and hence the count) does
        # not depend on traversal order, so a flat bytearray + explicit
        # stack gives the same boolean with fewer calls/allocations.
        rows = self.rows
        cols = self.cols
        data = self.map_data
        start = self.a_loc
        visited = bytearray(rows * cols)
        sr = start[0]
        sc = start[1]
        first = sr * cols + sc
        visited[first] = 1
        squaresVisited = 1
        stack = [first]
        while stack:
            idx = stack.pop()
            r, c = divmod(idx, cols)
            # north
            nr = r - 1
            if nr < 0:
                nr += rows
            nidx = nr * cols + c
            if not visited[nidx] and data[nr][c] != "%":
                visited[nidx] = 1
                squaresVisited += 1
                stack.append(nidx)
            # south
            nr = r + 1
            if nr >= rows:
                nr -= rows
            nidx = nr * cols + c
            if not visited[nidx] and data[nr][c] != "%":
                visited[nidx] = 1
                squaresVisited += 1
                stack.append(nidx)
            # east
            nc = c + 1
            if nc >= cols:
                nc -= cols
            nidx = r * cols + nc
            if not visited[nidx] and data[r][nc] != "%":
                visited[nidx] = 1
                squaresVisited += 1
                stack.append(nidx)
            # west
            nc = c - 1
            if nc < 0:
                nc += cols
            nidx = r * cols + nc
            if not visited[nidx] and data[r][nc] != "%":
                visited[nidx] = 1
                squaresVisited += 1
                stack.append(nidx)

        return squaresVisited == self.land_squares

    # adds ants to the map
    def add_ants(self):
        self.land_squares = self.no_players
        self.a_loc = self.pick_square()
        self.fill_squares(self.a_loc, "0")

    # adds land to a map of water
    def add_walk_land(self):
        # random.gauss(2,10)
        # Local bindings only; RNG calls, fill order, and puddle logic
        # are unchanged.
        data = self.map_data
        no_players = self.no_players
        no_land_squares = random.randint(
            int(self.min_land_proportion * self.rows * self.cols),
            int(self.max_land_proportion * self.rows * self.cols),
        )

        while self.land_squares < no_land_squares or not self.is_valid():
            self.walk_locations()

            for c_loc in self.c_locs:
                if data[c_loc[0]][c_loc[1]] == "%":
                    self.land_squares += no_players
                    self.fill_squares(c_loc, ".")

                    # fill in isolated water
                    wchecks = [
                        s
                        for s in self.get_neighbors(c_loc)
                        if data[s[0]][s[1]] == "%"
                    ]
                    for check_sq in wchecks:
                        is_puddle = True
                        for cn in self.get_neighbors(check_sq):
                            if data[cn[0]][cn[1]] == "%":
                                is_puddle = False
                                break
                        if is_puddle:
                            self.land_squares += no_players
                            self.fill_squares(check_sq, ".")

        print(
            "Land per:",
            self.land_squares / float(self.rows * self.cols),
            file=sys.stderr,
        )


def main(argv=None):
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("--players", dest="players", type="int", default=None)
    parser.add_option("--rows", dest="rows", type="int", default=None)
    parser.add_option("--cols", dest="cols", type="int", default=None)
    parser.add_option(
        "--min_start_distance",
        dest="min_start_distance",
        type="int",
        default=None,
    )
    parser.add_option("--seed", dest="seed", type="int", default=None)
    opts, _ = parser.parse_args(argv)

    random.seed(opts.seed)
    example_map = SymmetricMap()
    if opts.players is not None:
        example_map.fixed_players = opts.players
    if opts.rows is not None:
        example_map.fixed_rows = opts.rows
    if opts.cols is not None:
        example_map.fixed_cols = opts.cols
    if opts.min_start_distance is not None:
        example_map.min_start_distance = opts.min_start_distance
    example_map.random_walk_map()
    example_map.print_map()
    return 0


if __name__ == "__main__":
    sys.exit(main())
