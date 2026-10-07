#!/usr/bin/env python
"""Example bot: the shape every entry follows.

One bot file, one manifest, correctness tests beside it.
Copied from tools/sample_bots/python/HunterBot.py, class renamed.
"""

from random import shuffle

from ants import Ants


class Example:
    def do_setup(self, ants):
        pass

    def do_turn(self, ants):
        destinations = []
        for a_row, a_col in ants.my_ants():
            targets = ants.food() + [
                (row, col) for (row, col), owner in ants.enemy_ants()
            ]
            closest_target = None
            closest_distance = 999999
            for t_row, t_col in targets:
                dist = ants.distance((a_row, a_col), (t_row, t_col))
                if dist < closest_distance:
                    closest_distance = dist
                    closest_target = (t_row, t_col)
            if closest_target is None:
                destinations.append((a_row, a_col))
                continue
            directions = ants.direction((a_row, a_col), closest_target)
            shuffle(directions)
            for direction in directions:
                dest = ants.destination((a_row, a_col), direction)
                if ants.unoccupied(dest) and dest not in destinations:
                    destinations.append(dest)
                    ants.issue_order(((a_row, a_col), direction))
                    break
            else:
                destinations.append((a_row, a_col))


if __name__ == "__main__":
    try:
        Ants.run(Example())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
