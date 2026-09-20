#!/usr/bin/env python
from collections import deque

from ants import Ants


# define a class with a do_turn method
# the Ants.run method will parse and update bot input
# it will also run the do_turn method for us
class Steward:
    def __init__(self):
        # define class level variables, will be remembered between turns
        self.visits: dict[tuple[int, int], int] = {}
        self.remembered_hills: set[tuple[int, int]] = set()
        self.prev_enemies: list[tuple[int, int]] = []
        self.missions: dict[tuple[int, int], tuple[str, tuple[int, int]]] = {}

    # do_setup is run once at the start of the game
    # after the bot has received the game settings
    # the ants class is created and setup by the Ants.run method
    def do_setup(self, ants: Ants):
        # initialize data structures after learning the game settings
        self.visits = {}
        self.remembered_hills = set()
        self.prev_enemies = []
        self.missions = {}

    # do turn is run once per turn
    # the ants class has the game state and is updated by the Ants.run method
    # it also has several helper methods to use
    def do_turn(self, ants: Ants):
        # Standing orders: ants keep targets across turns.
        # Battling as Steward. Headings, memory, aggression, walk-off,
        # and exploration match iteration 15. Each ant holds its food
        # or hill mission until the target is gone; only missionless
        # ants bid, so equidistant targets stop swapping every turn.
        foods = ants.food()
        ants_list = ants.my_ants()
        my_set = set(ants_list)
        for hloc, _ in ants.enemy_hills():
            self.remembered_hills.add(hloc)
        for hloc in list(self.remembered_hills):
            if hloc in my_set:
                self.remembered_hills.discard(hloc)
        hills = sorted(self.remembered_hills)
        my_hills = ants.my_hills()
        enemy_locs = [loc for loc, _ in ants.enemy_ants()]
        # Match each visible enemy to a last-turn position to read
        # its heading. Ants move one square per turn, so matches at
        # distance 0 or 1 are the same ant; the rest are new spawns.
        unmatched = self.prev_enemies[:]
        headings: dict[tuple[int, int], tuple[int, int]] = {}
        for cur in enemy_locs:
            match = None
            match_d = 2
            for p in unmatched:
                d = ants.distance(cur, p)
                if d < match_d:
                    match_d = d
                    match = p
            if match is not None:
                unmatched.remove(match)
                headings[cur] = match
        self.prev_enemies = enemy_locs

        def closing(cur: tuple[int, int], hill: tuple[int, int]) -> bool:
            prev = headings.get(cur)
            return prev is not None and ants.distance(prev, hill) > ants.distance(
                cur, hill
            )

        threatened = [
            h
            for h in my_hills
            if any(
                ants.distance(h, e) <= 10
                or (ants.distance(h, e) <= 16 and closing(e, h))
                for e in enemy_locs
            )
        ]
        # Standing orders: re-attach ants to last turn's missions by
        # proximity, then draft only missionless ants. Food missions
        # need the food still present and unclaimed; hill missions need
        # the hill still known.
        food_set = set(foods)
        valid_hills = set(threatened) | set(hills)
        mission: dict[int, tuple[str, tuple[int, int]]] = {}
        kept: dict[tuple[int, int], tuple[str, tuple[int, int]]] = {}
        taken_food: set[tuple[int, int]] = set()
        holders = list(self.missions.keys())
        free: list[int] = []
        for ai, ant_loc in enumerate(ants_list):
            keep = None
            keep_d = 3
            for h in holders:
                d = ants.distance(ant_loc, h)
                if d < keep_d:
                    keep_d = d
                    keep = h
            kind_loc = self.missions.get(keep) if keep is not None else None
            if keep is not None:
                holders.remove(keep)
            if kind_loc is None:
                free.append(ai)
                continue
            kind, loc = kind_loc
            if kind == "food" and loc in food_set and loc not in taken_food:
                mission[ai] = ("food", loc)
                taken_food.add(loc)
                kept[ant_loc] = ("food", loc)
            elif kind == "hill" and loc in valid_hills:
                mission[ai] = ("hill", loc)
                kept[ant_loc] = ("hill", loc)
            else:
                free.append(ai)
        pairs: list[tuple[int, int, int]] = []
        for ai in free:
            ant_loc = ants_list[ai]
            for fi, food_loc in enumerate(foods):
                if food_loc in taken_food:
                    continue
                pairs.append((ants.distance(ant_loc, food_loc), ai, fi))
        pairs.sort()
        for _, ai, fi in pairs:
            if ai not in mission and foods[fi] not in taken_food:
                mission[ai] = ("food", foods[fi])
                taken_food.add(foods[fi])
                kept[ants_list[ai]] = ("food", foods[fi])
        for ai in free:
            if ai not in mission and (threatened or hills):
                targets = threatened if threatened else hills
                ant_loc = ants_list[ai]
                nearest = min(targets, key=lambda h: ants.distance(ant_loc, h))
                mission[ai] = ("hill", nearest)
                kept[ant_loc] = ("hill", nearest)
        self.missions = kept
        attack_r2 = ants.attackradius2 or 5
        rows, cols = ants.rows, ants.cols

        def sq_dist(a: tuple[int, int], b: tuple[int, int]) -> int:
            dr = abs(a[0] - b[0])
            dr = min(dr, rows - dr) if rows else dr
            dc = abs(a[1] - b[1])
            dc = min(dc, cols - dc) if cols else dc
            return dr * dr + dc * dc

        def is_safe(nloc: tuple[int, int], self_loc: tuple[int, int]) -> bool:
            enemies = 0
            for e in enemy_locs:
                if sq_dist(nloc, e) <= attack_r2:
                    enemies += 1
                    if enemies >= len(ants_list):
                        break
            if enemies == 0:
                return True
            friends = 0
            near = 0
            for f in ants_list:
                if f == self_loc:
                    continue
                if sq_dist(nloc, f) <= attack_r2:
                    friends += 1
                if ants.distance(nloc, f) <= 10:
                    near += 1
            if friends + 1 > enemies:
                return True
            # Aggressive: 14+ friends near the fight accept equal trades.
            return near >= 14 and friends + 1 >= enemies

        def first_step(
            start: tuple[int, int], goal: tuple[int, int], budget: int = 250
        ) -> str | None:
            # Shortest passable path around water; return its first step.
            if start == goal:
                return None
            parent: dict[tuple[int, int], tuple[tuple[int, int], str]] = {}
            parent[start] = (start, "")
            queue: deque[tuple[int, int]] = deque([start])
            expanded = 0
            while queue and expanded < budget:
                cur = queue.popleft()
                expanded += 1
                for d in ("n", "e", "s", "w"):
                    nxt = ants.destination(cur, d)
                    if nxt in parent or not ants.passable(nxt):
                        continue
                    parent[nxt] = (cur, d)
                    if nxt == goal:
                        queue.clear()
                        break
                    queue.append(nxt)
            if goal not in parent:
                return None
            node = goal
            while parent[node][0] != start:
                node = parent[node][0]
            return parent[node][1]

        def try_step(ant_loc: tuple[int, int], direction: str) -> bool:
            new_loc = ants.destination(ant_loc, direction)
            if (
                new_loc not in destinations
                and ants.passable(new_loc)
                and ants.unoccupied(new_loc)
                and is_safe(new_loc, ant_loc)
            ):
                ants.issue_order((ant_loc, direction))
                destinations.add(new_loc)
                return True
            return False

        destinations: set[tuple[int, int]] = set()
        held: list[tuple[int, int]] = []
        for ai, ant_loc in enumerate(ants_list):
            self.visits[ant_loc] = self.visits.get(ant_loc, 0) + 1
            kind_loc = mission.get(ai)
            moved = False
            if kind_loc is not None and kind_loc[0] == "food":
                step = first_step(ant_loc, kind_loc[1])
                if step is not None and try_step(ant_loc, step):
                    moved = True
                # else keep the mission; the claim persists.
            if not moved:
                hill_goal = None
                if kind_loc is not None and kind_loc[0] == "hill":
                    hill_goal = kind_loc[1]
                elif threatened or hills:
                    targets = threatened if threatened else hills
                    hill_goal = min(targets, key=lambda h: ants.distance(ant_loc, h))
                if hill_goal is not None:
                    step = first_step(ant_loc, hill_goal)
                    if step is not None and try_step(ant_loc, step):
                        moved = True
                        self.missions[ant_loc] = ("hill", hill_goal)
            if not moved:
                # No hill move: explore least-visited squares first.
                dirs = sorted(
                    ("n", "e", "s", "w"),
                    key=lambda d: self.visits.get(ants.destination(ant_loc, d), 0),
                )
                for direction in dirs:
                    new_loc = ants.destination(ant_loc, direction)
                    if (
                        new_loc not in destinations
                        and ants.passable(new_loc)
                        and ants.unoccupied(new_loc)
                        and is_safe(new_loc, ant_loc)
                    ):
                        ants.issue_order((ant_loc, direction))
                        destinations.add(new_loc)
                        moved = True
                        break
            if not moved:
                held.append(ant_loc)
            # check if we still have time left to calculate more orders
            if ants.time_remaining() < 10:
                break
        # Walk off hill: a held ant on a home hill must step off.
        hill_set = set(my_hills)
        for ant_loc in held:
            if ant_loc in hill_set and ants.time_remaining() >= 10:
                for direction in ("s", "e", "w", "n"):
                    if try_step(ant_loc, direction):
                        break


if __name__ == "__main__":
    # psyco will speed up python a little, but is not needed
    try:
        import psyco

        psyco.full()
    except ImportError:
        pass

    try:
        # if run is passed a class with a do_turn method, it will do the work
        # this is not needed, in which case you will need to write your own
        # parsing function and your own game state class
        Ants.run(Steward())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
