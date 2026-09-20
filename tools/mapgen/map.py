#!/usr/bin/env python
import heapq
import os
import sys
from collections import defaultdict, deque
from copy import deepcopy
from itertools import product
from optparse import OptionParser
from random import choice, randint, seed
from sys import maxsize as maxint
from typing import Any, cast

MY_ANT = 0
ANTS = 0
DEAD = -1
LAND = -2
FOOD = -3
WATER = -4
UNSEEN = -5

PLAYER_ANT = "abcdefghij"
HILL_ANT = string = "ABCDEFGHIJ"
PLAYER_HILL = string = "0123456789"
MAP_OBJECT = "?%*.!"
MAP_RENDER = PLAYER_HILL + HILL_ANT + PLAYER_ANT + MAP_OBJECT
ALLOWABLE = list(range(30)) + [LAND, FOOD, WATER]
# MAP_RENDER = ["{0:02}".format(n) for n in range(100)] + [' ?', ' %', ' *', ' .', ' !']

AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}


class Map:
    def __init__(self, options=None):
        if options is None:
            options = {}
        super().__init__()
        self.name = options.get("name", "blank")
        self.map: list[list[int]] = [[]]
        self.reports = []

        self.report(f"map type: {self.name}")
        self.random_seed = options.get("seed")
        if self.random_seed is None:
            self.random_seed = randint(-maxint - 1, maxint)
        seed(self.random_seed)
        self.report(f"random seed: {self.random_seed}")

    def log(self, msg):
        msg = "# " + str(msg) + "\n"
        sys.stderr.write(msg)

    def report(self, msg):
        msg = "# " + str(msg) + "\n"
        self.reports.append(msg)

    def generate(self):
        raise Exception("Not Implemented")

    def get_random_option(self, option):
        if type(option) is tuple:
            if len(option) == 2:
                return randint(*option)
            elif len(option) == 1:
                return option[0]
            elif len(option) == 0:
                raise Exception("Invalid option: 0 length tuple")
            else:
                return choice(option)
        elif type(option) in (list, set):
            if len(option) > 0:
                return choice(option)
            else:
                raise Exception("Invalid option: 0 length list")
        elif type(option) in (int, float, str):
            return option
        else:
            raise Exception(f"Invalid option: type {type(option)} not supported")

    def toPNG(self, fd=sys.stdout):
        raise Exception("Not Implemented")

    def toText(self, fd=sys.stdout):
        players = set()
        for row in self.map:
            for c in row:
                if c >= ANTS:
                    players.add(c)
        for msg in self.reports:
            fd.write(msg)
        fd.write(
            f"players {len(players)}\nrows {len(self.map)}\ncols {len(self.map[0])}\n"
        )
        for _r, row in enumerate(self.map):
            fd.write("m {}\n".format("".join([MAP_RENDER[c] for c in row])))

    def toFile(self, filename=None):
        if filename is None:
            filename = self.name.replace(" ", "_") + "_p" + f"{self.players:02}" + "_"
            filename += "{:02}".format(
                max(
                    0 if not x.isdigit() else int(x)
                    for x in [
                        f[len(filename) : len(filename) + 2]
                        for f in os.listdir(".")
                        if f.startswith(filename)
                    ]
                    + ["0"]
                )
                + 1
            )
            filename += ".map"
        with open(filename, "w") as mapfile:
            self.toText(mapfile)

    def manhatten_distance(self, loc1, loc2, size):
        rows, cols = size
        row1, col1 = loc1
        row2, col2 = loc2
        row1 = row1 % rows
        row2 = row2 % rows
        col1 = col1 % cols
        col2 = col2 % cols
        d_col = min(abs(col1 - col2), cols - abs(col1 - col2))
        d_row = min(abs(row1 - row2), rows - abs(row1 - row2))
        return d_row + d_col

    def euclidean_distance2(self, loc1, loc2, size):
        rows, cols = size
        row1, col1 = loc1
        row2, col2 = loc2
        row1 = row1 % rows
        row2 = row2 % rows
        col1 = col1 % cols
        col2 = col2 % cols
        d_col = min(abs(col1 - col2), cols - abs(col1 - col2))
        d_row = min(abs(row1 - row2), rows - abs(row1 - row2))
        return d_row**2 + d_col**2

    def get_distances(self, start_loc, end_locs, size=None):
        "get a list of distances from 1 location to a bunch of others"
        end_locs = end_locs[:]
        if size is None:
            rows, cols = len(self.map), len(self.map[0])
        else:
            rows, cols = size
        visited: dict[Any, int | None] = {}
        open_nodes: deque[tuple[Any, int]] = deque()
        open_nodes.append((start_loc, 0))
        if start_loc in end_locs:
            yield open_nodes[-1]
            end_locs.remove(start_loc)
        while open_nodes and len(end_locs) > 0:
            (row, col), dist = open_nodes.popleft()
            for n_loc in [
                ((row + 1) % rows, col),
                ((row - 1) % rows, col),
                (row, (col + 1) % cols),
                (row, (col - 1) % cols),
            ]:
                if n_loc not in visited:
                    if self.map[n_loc[0]][n_loc[1]] != WATER:
                        new_dist = dist + 1
                        visited[n_loc] = new_dist
                        open_nodes.append((n_loc, new_dist))
                        if n_loc in end_locs:
                            # print('# get distances: {0}'.format(open_nodes[-1]))
                            yield open_nodes[-1]
                            end_locs.remove(n_loc)
                    else:
                        visited[n_loc] = None

    def get_path(self, loc1, loc2, size, block=1, ignore=None):
        "get path from 1 location to another as a list of locations"

        # make a node class to calc F, G and H automatically
        distance = self.manhatten_distance

        class Node:
            def __init__(self, loc, parent, G):
                self.loc = loc
                self.parent: Node | None = parent
                self.G = G
                self.H = distance(loc, loc2, size)
                self.F = self.G + self.H

            def __lt__(self, other: "Node") -> bool:
                return self.F < other.F

        # heap list to help get lowest F cost
        open_nodes: list[Node] = []
        # lists indexed by location
        closed_list: dict[Any, Node] = {}
        open_list: dict[Any, Node] = {}
        block_offsets = list(product(range(block), range(block)))

        def add_open(node, open_nodes=open_nodes, open_list=open_list):
            heapq.heappush(open_nodes, (node.F, node))
            open_list[node.loc] = node

        def get_open(open_nodes=open_nodes, open_list=open_list):
            _, node = heapq.heappop(open_nodes)
            del open_list[node.loc]
            return node

        def replace_open(new_node, open_nodes=open_nodes, open_list=open_list):
            old_node = open_list[new_node.loc]
            open_nodes.remove((old_node.F, old_node))
            heapq.heapify(open_nodes)
            add_open(new_node)

        def build_path(node):
            path = []
            while node:
                path.append(node.loc)
                node = node.parent
            path.reverse()
            return path

        # A* search
        # add starting square to open list
        if block > 1:
            # find open block position on starting location
            for o_loc in product(range(-block + 1, 1), range(-block + 1, 1)):
                s_loc = self.dest_offset(loc1, o_loc, size)
                for d_loc in block_offsets:
                    b_row, b_col = self.dest_offset(s_loc, d_loc, size)
                    if self.map[b_row][b_col] == WATER and (
                        ignore is None or (b_row, b_col) not in ignore
                    ):
                        break
                else:
                    # no water found, use this start location
                    add_open(Node(s_loc, None, 0))
                    break
        else:
            add_open(Node(loc1, None, 0))
        while len(open_nodes) > 0:
            # get lowest F cost node
            node = get_open()
            # switch to closed list
            closed_list[node.loc] = node
            # check if found distination
            if block > 1:
                for d_loc in block_offsets:
                    if loc2 == self.dest_offset(node.loc, d_loc, size):
                        return build_path
            else:
                if node.loc == loc2:
                    # build path
                    return build_path(node)
            # expand node
            for d in AIM:
                loc = self.destination(node.loc, d, size)
                # ignore if closed or not traversable
                # ignore list is a set of locations to assume as traversable
                # block is a block size that must fit, the loc is the upper left corner
                if loc in closed_list:
                    continue
                skip = False
                for d_loc in block_offsets:
                    b_row, b_col = self.dest_offset(loc, d_loc, size)
                    if self.map[b_row][b_col] == WATER and (
                        ignore is None or (b_row, b_col) not in ignore
                    ):
                        skip = True
                        break
                if skip:
                    continue

                if loc in open_list:
                    old_node = open_list[loc]
                    # check for shortest path
                    if node.G + 1 < old_node.G:
                        # replace node
                        replace_open(Node(loc, node, node.G + 1))
                else:
                    # add to open list
                    add_open(Node(loc, node, node.G + 1))
        return None

    def destination(self, loc, direction, size):
        rows, cols = size
        row, col = loc
        d_row, d_col = AIM[direction]
        return ((row + d_row) % rows, (col + d_col) % cols)

    def dest_offset(self, loc, d_loc, size):
        rows, cols = size
        d_row, d_col = d_loc
        row, col = loc
        return ((row + d_row) % rows, (col + d_col) % cols)

    def section(self, block_size=1):
        """split map into sections that can be travesered by a block

        block_size 1 is a 3x3 block (1 step each direction)"""
        rows = len(self.map)
        cols = len(self.map[0])
        visited = [[False] * cols for _ in range(rows)]

        def is_block_free(loc):
            row, col = loc
            for d_row in range(-block_size, block_size + 1):
                for d_col in range(-block_size, block_size + 1):
                    h_row = (row + d_row) % rows
                    h_col = (col + d_col) % cols
                    if self.map[h_row][h_col] == WATER:
                        return False
            return True

        def mark_block(loc, m, ilk):
            row, col = loc
            for d_row in range(-block_size, block_size + 1):
                for d_col in range(-block_size, block_size + 1):
                    h_row = (row + d_row) % rows
                    h_col = (col + d_col) % cols
                    m[h_row][h_col] = ilk

        def find_open_spot():
            for row, col in product(range(rows), range(cols)):
                if is_block_free((row, col)) and not visited[row][col]:
                    return (row, col)
            else:
                return None

        # list of contiguous areas
        areas = []

        # flood fill map for each separate area
        while find_open_spot():
            # maintain lists of visited and seen squares
            # visited will not overlap, but seen may
            area_visited = [[False] * cols for _ in range(rows)]
            area_seen = [[False] * cols for _ in range(rows)]

            squares: deque[tuple[Any, Any]] = deque()
            row, col = find_open_spot()

            # seen_area = open_block((row, col))
            squares.appendleft((row, col))

            while len(squares) > 0:
                row, col = squares.pop()
                visited[row][col] = True
                area_visited[row][col] = True
                area_seen[row][col] = True
                for d_row, d_col in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                    s_row = (row + d_row) % rows
                    s_col = (col + d_col) % cols
                    if not visited[s_row][s_col] and is_block_free((s_row, s_col)):
                        visited[s_row][s_col] = True
                        mark_block((s_row, s_col), area_seen, True)
                        squares.appendleft((s_row, s_col))

            # check percentage filled
            # areas.append(1.0 * seen_area / land_area)
            visited_list = []
            seen_list = []
            for row in range(rows):
                for col in range(cols):
                    if area_visited[row][col]:
                        visited_list.append((row, col))
                    elif area_seen[row][col]:
                        seen_list.append((row, col))
            areas.append([visited_list, seen_list])

        # sort by largest area first
        areas.sort(key=lambda area: len(area[0]), reverse=True)
        return areas

    def fill_small_areas(self):
        # keep largest contiguous area as land, fill the rest with water
        count = 0
        areas = self.section(0)
        for area in areas[1:]:
            for row, col in area[0]:
                self.map[row][col] = WATER
                count += 1
        # print("fill {0}".format(count))

    def make_wider(self):
        # make sure the map has more columns than rows
        rows = len(self.map)
        cols = len(self.map[0])
        if rows > cols:
            map = [[LAND] * rows for _ in range(cols)]
            for row in range(rows):
                for col in range(cols):
                    map[col][row] = self.map[row][col]
            self.map = map

    def tile(self, grid):
        rows = len(self.map)
        cols = len(self.map[0])
        row_sym, col_sym = grid

        # select random mirroring
        row_mirror = 0
        if row_sym % 2 == 0:
            # if row_sym % 4 == 0:
            #    row_mirror = choice((0,4))
            row_mirror = choice((row_mirror, 2))
            row_mirror = 2

        col_mirror = 0
        if col_sym % 2 == 0:
            # if col_sym % 4 == 0:
            #    col_mirror = choice((0,4))
            col_mirror = choice((col_mirror, 2))
            col_mirror = 2

        # perform tiling
        t_rows = rows * row_sym
        t_cols = cols * col_sym
        ant = 0
        map = [[LAND] * t_cols for _ in range(t_rows)]
        for t_row in range(t_rows):
            for t_col in range(t_cols):
                # detect grid location
                g_row = t_row // rows
                g_col = t_col // cols
                if row_mirror == 2 and g_row % 2 == 1:
                    row = rows - 1 - (t_row % rows)
                else:
                    row = t_row % rows
                if col_mirror == 2 and g_col % 2 == 1:
                    col = cols - 1 - (t_col % cols)
                else:
                    col = t_col % cols
                try:
                    map[t_row][t_col] = self.map[row][col]
                except Exception:
                    print("issue")
                if self.map[row][col] == ANTS:
                    map[t_row][t_col] = ant
                    ant += 1
        self.map = map

    def translate(self, offset):
        d_row, d_col = offset
        rows = len(self.map)
        cols = len(self.map[0])
        map = [[LAND] * cols for _ in range(rows)]
        for row in range(rows):
            for col in range(cols):
                o_row = (d_row + row) % rows
                o_col = (d_col + col) % cols
                map[o_row][o_col] = self.map[row][col]
        self.map = map

    def offset_aim(self, offset, aim):
        """Return proper offset given an orientation"""
        # eight possible orientations
        row, col = offset
        aims = {
            0: (row, col),
            1: (-row, col),
            2: (row, -col),
            3: (-row, -col),
            4: (col, row),
            5: (-col, row),
            6: (col, -row),
            7: (-col, -row),
        }
        return aims.get(aim)

    def map_similar(self, loc1, loc2, aim, player):
        """find if map is similar given loc1 aim of 0 and loc2 ant of player
        return a map of translated enemy locations
        """
        enemy_map: dict[int, int] = {}
        rows = len(self.map)
        cols = len(self.map[0])
        size = (rows, cols)
        for row in range(rows):
            for col in range(cols):
                row0, col0 = self.dest_offset(loc1, (row, col), size)
                row1, col1 = self.dest_offset(
                    loc2, self.offset_aim((row, col), aim), size
                )
                # compare locations
                ilk0 = self.map[row0][col0]
                ilk1 = self.map[row1][col1]
                if ilk0 == 0 and ilk1 != player:
                    # friendly ant not in same location
                    return None
                elif ilk0 > 0 and (ilk1 < 0 or ilk1 == player):
                    # enemy ant not in same location
                    return None
                elif ilk0 < 0 and ilk1 != ilk0:
                    # land or water not in same location
                    return None
                if ilk0 >= 0 and enemy_map is not None:
                    enemy_map[ilk0] = ilk1
        return enemy_map

    def get_map_symmetry(self):
        """Get orientation for each starting hill"""
        size = (len(self.map), len(self.map[0]))
        # build list of all hills
        player_hills = defaultdict(list)  # list of hills for each player
        for row, squares in enumerate(self.map):
            for col, square in enumerate(squares):
                if 0 <= square < 10:
                    player_hills[square].append((row, col))
        if len(player_hills) > 0:
            # list of
            #     list of tuples containing
            #         location, aim, and enemy map dict
            orientations = [
                [
                    (
                        player_hills[0][0],
                        0,
                        {i: i for i in range(self.players)},
                    )
                ]
            ]
            for player in range(1, self.players):
                if len(player_hills[player]) != len(player_hills[0]):
                    raise Exception(
                        "Invalid map",
                        f"This map is not symmetric.  Player 0 has {len(player_hills[0])} hills while player {player} has {len(player_hills[player])} hills.",
                    )
                new_orientations = []
                for player_hill in player_hills[player]:
                    for aim in range(8):
                        # check if map looks similar given the orientation
                        enemy_map = self.map_similar(
                            player_hills[0][0], player_hill, aim, player
                        )
                        if enemy_map is not None:
                            # produce combinations of orientation sets
                            for hill_aims in orientations:
                                new_hill_aims = deepcopy(hill_aims)
                                new_hill_aims.append((player_hill, aim, enemy_map))
                                new_orientations.append(new_hill_aims)
                orientations = new_orientations
                if len(orientations) == 0:
                    raise Exception(
                        "Invalid map",
                        f"This map is not symmetric. Player {player} does not have an orientation that matches player 0",
                    )
            # ensure types of hill aims in orientations are symmetric
            # place food set and double check symmetry
            valid_orientations = []
            for hill_aims in orientations:
                fix = []
                for loc, aim, _enemy_map in hill_aims:
                    row, col = self.dest_offset(loc, self.offset_aim((1, 2), aim), size)
                    fix.append(((row, col), self.map[row][col]))
                    self.map[row][col] = FOOD
                for loc, aim, enemy_map in hill_aims:
                    if (
                        self.map_similar(hill_aims[0][0], loc, aim, enemy_map[0])
                        is None
                    ):
                        break
                else:
                    valid_orientations.append(hill_aims)
                for (row, col), ilk in reversed(fix):
                    self.map[row][col] = ilk
            if len(valid_orientations) == 0:
                raise Exception("Invalid map", "There are no valid orientation sets")
            return valid_orientations
        else:
            raise Exception("Invalid map", "There are no player hills")

    def allowable(self, check_sym=True, check_dist=True):
        # Maps are limited to at most 200 squares for either dimension
        size = (len(self.map), len(self.map[0]))
        if size[0] > 200 or size[1] > 200:
            return "Map is too large"

        # Maps are limited to 10 players
        players = set()
        hills = {}
        for row, squares in enumerate(self.map):
            for col, square in enumerate(squares):
                if square not in ALLOWABLE:
                    return "Maps are limited to 10 players and must contain the following characters: A-Ja-j0-9.*%"
                elif square >= 0:
                    players.add(square % 10)
                    if square < 10:
                        hills[(row, col)] = square

        # Maps are limited in area by number of players
        if size[0] * size[1] > max(25000, 5000 * len(players)):
            return "Map area is too large for player count"
        if size[0] * size[1] < 900 * len(players):
            return "Map area is too small for player count"

        # Maps are limited in area by number of hills
        if size[0] * size[1] < 500 * len(hills):
            return "Map has too many hills for its size"

        # Maps must be symmetric
        if check_sym:
            try:
                self.get_map_symmetry()
            except Exception as e:
                return "Map is not symmetric: " + str(e)

        # Hills must be between 20 and 150 steps away from other hills
        # Hills must be more than 5 distance apart
        hill_min = False
        hill_max = False
        hill_range = False
        self.report(
            "hill distance " + " ".join([f"{loc[0]:>3},{loc[1]:>3}" for loc in hills])
        )
        for hill_loc in hills:
            hill_dists = dict(self.get_distances(hill_loc, hills.keys(), size))
            hill_msg = f"      {hill_loc[0]:>3},{hill_loc[1]:>3} "
            for hill_loc2 in hills:
                if (
                    hill_loc != hill_loc2
                    and self.euclidean_distance2(hill_loc, hill_loc2, size) <= 25
                ):
                    hill_range = True
                hill_msg += f"{hill_dists[hill_loc2]:>7} "
            self.report(hill_msg)
            if (
                min(
                    [
                        dist
                        for point, dist in hill_dists.items()
                        if self.map[point[0]][point[1]]
                        != self.map[hill_loc[0]][hill_loc[1]]
                    ]
                )
                < 20
            ):
                hill_min = True
            if max(hill_dists.values()) > 150:
                hill_max = True
        if hill_min and hill_max:
            return "Map has hills too close and too far"
        elif hill_min:
            return "Map has hills too close"
        elif hill_max:
            return "Map has hills too far"
        elif hill_range:
            return "Map has hills within attack range"

        # Maps must not contain islands
        # all squares must be accessible from all other squares
        # fill small areas can fix this
        areas = self.section(0)
        if len(areas) > 1:
            area_visited, _ = areas[0]
            for loc in area_visited:
                if self.map[loc[0]][loc[1]] == LAND:
                    self.map[loc[0]][loc[1]] = UNSEEN
            return "Map not 100% accessible"

        # find section with first hill
        areas = self.section(1)
        first_hill_loc = list(hills.keys())[0]
        area_visited = area_seen = None
        for area_visited, area_seen in areas:
            if first_hill_loc in area_seen or first_hill_loc in area_visited:
                break
        else:
            return "Could not find first hill area"

        for hill_loc in hills:
            if hill_loc not in area_seen and hill_loc not in area_visited:
                return "Starting hills not in same unblockable area"

        return None

    def fromFile(self, fd):
        """Parse the map_text into a more friendly data structure"""
        ant_list = None
        hill_list = []
        hill_count: defaultdict[int, int] = defaultdict(int)
        width = height = None
        water = []
        food = []
        ants = defaultdict(list)
        hills = defaultdict(list)
        row = 0
        num_players = None

        # for line in map_text.split('\n'):
        for line in fd:
            line = line.strip()

            # ignore blank lines and comments
            if not line or line[0] == "#":
                continue

            key, value = line.split(" ", 1)
            key = key.lower()
            if key == "cols":
                width = int(value)
            elif key == "rows":
                height = int(value)
            elif key == "players":
                num_players = int(value)
                if num_players < 2 or num_players > 10:
                    raise Exception("map", "player count must be between 2 and 10")
            elif key == "m":
                if ant_list is None:
                    if num_players is None:
                        raise Exception(
                            "map", "players count expected before map lines"
                        )
                    ant_list = [chr(97 + i) for i in range(num_players)]
                    hill_list = list(map(str, range(num_players)))
                    hill_ant = [chr(65 + i) for i in range(num_players)]
                if len(value) != width:
                    raise Exception(
                        "map",
                        f"Incorrect number of cols in row {row}. "
                        f"Got {len(value)}, expected {width}.",
                    )
                for col, c in enumerate(value):
                    if c in ant_list:
                        ants[ant_list.index(c)].append((row, col))
                    elif c in hill_list:
                        hills[hill_list.index(c)].append((row, col))
                        hill_count[hill_list.index(c)] += 1
                    elif c in hill_ant:
                        ants[hill_ant.index(c)].append((row, col))
                        hills[hill_ant.index(c)].append((row, col))
                        hill_count[hill_ant.index(c)] += 1
                    elif c == MAP_OBJECT[FOOD]:
                        food.append((row, col))
                    elif c == MAP_OBJECT[WATER]:
                        water.append((row, col))
                    elif c != MAP_OBJECT[LAND]:
                        raise Exception("map", f"Invalid character in map: {c}")
                row += 1

        if height != row:
            raise Exception(
                "map", f"Incorrect number of rows.  Expected {height}, got {row}"
            )

        # look for ants without hills to invalidate map for a game
        for hill, count in hill_count.items():
            if count == 0:
                raise Exception("map", f"Player {hill} has no starting hills")

        map_data: dict[str, Any] = {
            "size": (height, width),
            "num_players": num_players,
            "hills": hills,
            "ants": ants,
            "food": food,
            "water": water,
        }

        # initialize size
        self.height, self.width = map_data["size"]
        self.land_area = self.height * self.width - len(map_data["water"])

        # initialize map
        # this matrix does not track hills, just ants
        self.map = [[LAND] * self.width for _ in range(self.height)]

        # initialize water
        for row, col in map_data["water"]:
            self.map[row][col] = WATER

        # for new games
        # ants are ignored and 1 ant is created per hill
        # food is ignored
        # for scenarios, the map file is followed exactly

        # initialize hills
        for owner, locs in map_data["hills"].items():
            for loc in locs:
                self.map[loc[0]][loc[1]] = owner
        self.players = cast(int, num_players)


def main():
    parser = OptionParser()
    parser.add_option(
        "-f", "--filename", dest="filename", help="filename to check for allowable map"
    )
    parser.add_option("-n", "--name", dest="name", help="name of map file to create")
    parser.add_option(
        "-q",
        "--quiet",
        action="store_true",
        default=False,
        help="Do not output map data to console",
    )

    opts, _ = parser.parse_args(sys.argv)
    new_map = Map()
    if opts.filename:
        with open(opts.filename) as f:
            new_map.fromFile(f)
    else:
        new_map.fromFile(sys.stdin)
    errors = new_map.allowable()
    if errors:
        if opts.filename:
            print(opts.filename)
        print(errors)
        sys.exit(1)
    else:
        if opts.name:
            new_map.name = opts.name
            new_map.toFile()
        else:
            if not opts.quiet:
                new_map.toText()

    # options = {key: value for key, value in vars(opts).items() if value is not None}


if __name__ == "__main__":
    main()
