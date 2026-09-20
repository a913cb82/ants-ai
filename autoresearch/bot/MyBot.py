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
        # Closest food: each ant moves to its nearest visible food.
        # One ant claims one food so two ants do not target the same food.
        foods = ants.food()
        claimed: set[tuple[int, int]] = set()
        destinations: set[tuple[int, int]] = set()
        for ant_loc in ants.my_ants():
            best = None
            best_dist = 0
            for food_loc in foods:
                if food_loc in claimed:
                    continue
                dist = ants.distance(ant_loc, food_loc)
                if best is None or dist < best_dist:
                    best = food_loc
                    best_dist = dist
            moved = False
            if best is not None:
                for direction in ants.direction(ant_loc, best):
                    new_loc = ants.destination(ant_loc, direction)
                    if (
                        new_loc not in destinations
                        and ants.passable(new_loc)
                        and ants.unoccupied(new_loc)
                    ):
                        ants.issue_order((ant_loc, direction))
                        destinations.add(new_loc)
                        claimed.add(best)
                        moved = True
                        break
                if not moved:
                    # Nearest food is blocked; free it for another ant.
                    pass
            if not moved:
                # No food or blocked: step in order n, e, s, w.
                for direction in ("n", "e", "s", "w"):
                    new_loc = ants.destination(ant_loc, direction)
                    if (
                        new_loc not in destinations
                        and ants.passable(new_loc)
                        and ants.unoccupied(new_loc)
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
