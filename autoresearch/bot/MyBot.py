#!/usr/bin/env python
from ants import Ants


# define a class with a do_turn method
# the Ants.run method will parse and update bot input
# it will also run the do_turn method for us
class MyBot:
    def __init__(self):
        # define class level variables, will be remembered between turns
        pass

    # do_setup is run once at the start of the game
    # after the bot has received the game settings
    # the ants class is created and setup by the Ants.run method
    def do_setup(self, ants: Ants):
        # initialize data structures after learning the game settings
        pass

    # do turn is run once per turn
    # the ants class has the game state and is updated by the Ants.run method
    # it also has several helper methods to use
    def do_turn(self, ants: Ants):
        # Combat: do not step into certain death.
        # Food and hill behavior matches iteration 4. A move is safe
        # only with a local majority (friends + self > enemies in
        # attack range). Unsafe directions are skipped.
        foods = ants.food()
        ants_list = ants.my_ants()
        pairs: list[tuple[int, int, int]] = []
        for ai, ant_loc in enumerate(ants_list):
            for fi, food_loc in enumerate(foods):
                pairs.append((ants.distance(ant_loc, food_loc), ai, fi))
        pairs.sort()
        target: dict[int, tuple[int, int]] = {}
        claimed_food: set[int] = set()
        for _, ai, fi in pairs:
            if ai not in target and fi not in claimed_food:
                target[ai] = foods[fi]
                claimed_food.add(fi)
        hills = [loc for loc, _ in ants.enemy_hills()]
        my_hills = ants.my_hills()
        enemy_locs = [loc for loc, _ in ants.enemy_ants()]
        threatened = [
            h for h in my_hills if any(ants.distance(h, e) <= 10 for e in enemy_locs)
        ]
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
            for f in ants_list:
                if f != self_loc and sq_dist(nloc, f) <= attack_r2:
                    friends += 1
            return friends + 1 > enemies

        destinations: set[tuple[int, int]] = set()
        for ai, ant_loc in enumerate(ants_list):
            best = target.get(ai)
            moved = False
            if best is not None:
                for direction in ants.direction(ant_loc, best):
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
                    # Assigned food is blocked; keep the claim so no other
                    # ant chases the same region this turn.
                    pass
            if not moved and (threatened or hills):
                # No food or blocked: guard home first, else hunt.
                targets = threatened if threatened else hills
                nearest = min(targets, key=lambda h: ants.distance(ant_loc, h))
                for direction in ants.direction(ant_loc, nearest):
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
                # No hill move: step in order n, e, s, w.
                for direction in ("n", "e", "s", "w"):
                    new_loc = ants.destination(ant_loc, direction)
                    if (
                        new_loc not in destinations
                        and ants.passable(new_loc)
                        and ants.unoccupied(new_loc)
                        and is_safe(new_loc, ant_loc)
                    ):
                        ants.issue_order((ant_loc, direction))
                        destinations.add(new_loc)
                        break
            # check if we still have time left to calculate more orders
            if ants.time_remaining() < 10:
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
        Ants.run(MyBot())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
