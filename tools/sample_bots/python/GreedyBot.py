#!/usr/bin/env python
import logging
from random import shuffle
from typing import Any

from ants import AIM, ANTS, FOOD, HILL, LAND, UNSEEN, Ants
from logutils import getLogger

turn_number = 0
bot_version = "v0.1"


class LogFilter(logging.Filter):
    """
    This is a filter that injects stuff like TurnNumber into the log
    """

    def filter(self, record):
        global turn_number, bot_version
        record.turn_number = turn_number
        record.version = bot_version
        return True


class GreedyBot:
    def __init__(self):
        """Add our log filter so that botversion and turn number are output correctly"""
        log_filter = LogFilter()
        getLogger().addFilter(log_filter)
        self.visited = []  # keep track of visited row/cols
        self.standing_orders = []

    def hunt_hills(self, ants, a_row, a_col, destinations, hunted, orders):
        getLogger().debug("Start Finding Ant")
        closest_enemy_hill = ants.closest_enemy_hill(a_row, a_col)
        getLogger().debug("Done Finding Ant")
        if closest_enemy_hill is not None:
            return self.do_order(
                ants,
                HILL,
                (a_row, a_col),
                closest_enemy_hill,
                destinations,
                hunted,
                orders,
            )

    def hunt_ants(self, ants, a_row, a_col, destinations, hunted, orders):
        getLogger().debug("Start Finding Ant")
        closest_enemy_ant = ants.closest_enemy_ant(a_row, a_col, hunted)
        getLogger().debug("Done Finding Ant")
        if closest_enemy_ant is not None:
            return self.do_order(
                ants,
                ANTS,
                (a_row, a_col),
                closest_enemy_ant,
                destinations,
                hunted,
                orders,
            )

    def hunt_food(self, ants, a_row, a_col, destinations, hunted, orders):
        getLogger().debug("Start Finding Food")
        closest_food = ants.closest_food(a_row, a_col, hunted)
        getLogger().debug("Done Finding Food")
        if closest_food is not None:
            return self.do_order(
                ants, FOOD, (a_row, a_col), closest_food, destinations, hunted, orders
            )

    def hunt_unseen(self, ants, a_row, a_col, destinations, hunted, orders):
        getLogger().debug("Start Finding Unseen")
        closest_unseen = ants.closest_unseen(a_row, a_col, hunted)
        getLogger().debug("Done Finding Unseen")
        if closest_unseen is not None:
            return self.do_order(
                ants,
                UNSEEN,
                (a_row, a_col),
                closest_unseen,
                destinations,
                hunted,
                orders,
            )

    def random_move(self, ants, a_row, a_col, destinations, hunted, orders):
        # if we didn't move as there was no food try a random move
        directions = list(AIM.keys())
        getLogger().debug("random move:directions:%s", "".join(directions))
        shuffle(directions)
        getLogger().debug("random move:shuffled directions:%s", "".join(directions))
        for direction in directions:
            getLogger().debug("random move:direction:%s", direction)
            (n_row, n_col) = ants.destination(a_row, a_col, direction)
            if (n_row, n_col) not in destinations and ants.unoccupied(n_row, n_col):
                return self.do_order(
                    ants,
                    LAND,
                    (a_row, a_col),
                    (n_row, n_col),
                    destinations,
                    hunted,
                    orders,
                )

    def do_order(self, ants, order_type, loc, dest, destinations, hunted, orders):
        order_type_desc = ["ant", "hill", "unseen", None, "food", "random", None]
        a_row, a_col = loc
        getLogger().debug(f"chasing {order_type_desc}:start")
        directions = ants.direction(a_row, a_col, dest[0], dest[1])
        getLogger().debug(
            "chasing {}:directions:{}".format(
                order_type_desc[order_type], "".join(directions)
            )
        )
        shuffle(directions)
        for direction in directions:
            getLogger().debug(
                f"chasing {order_type_desc[order_type]}:direction:{direction}"
            )
            (n_row, n_col) = ants.destination(a_row, a_col, direction)
            if (n_row, n_col) not in destinations and ants.unoccupied(n_row, n_col):
                ants.issue_order((a_row, a_col, direction))
                getLogger().debug(
                    "issue_order:%s,%d,%d,%s",
                    f"chasing {order_type_desc[order_type]}",
                    a_row,
                    a_col,
                    direction,
                )
                destinations.append((n_row, n_col))
                hunted.append(dest)
                orders.append([loc, (n_row, n_col), dest, order_type])
                return True
        return False

    def do_turn(self, ants):
        global turn_number
        turn_number = turn_number + 1
        destinations: list[tuple[int, int]] = []
        getLogger().debug("Starting Turn")
        # continue standing orders
        orders: list[list[Any]] = []
        hunted: list[tuple[int, int]] = []
        for order in self.standing_orders:
            ant_loc, step_loc, dest_loc, order_type = order
            if (
                (order_type == HILL and dest_loc in ants.enemy_hills())
                or (order_type == FOOD and dest_loc in ants.food())
                or (order_type == ANTS and dest_loc in ants.enemy_ants())
                or (
                    order_type == UNSEEN
                    and ants.map[dest_loc[0]][dest_loc[1]] == UNSEEN
                )
            ):
                self.do_order(
                    ants, order_type, ant_loc, dest_loc, destinations, hunted, orders
                )

        origins = [order[0] for order in orders]
        for a_row, a_col in ants.my_ants():
            if (
                (a_row, a_col) not in origins
                and not self.hunt_hills(
                    ants, a_row, a_col, destinations, hunted, orders
                )
                and not self.hunt_food(ants, a_row, a_col, destinations, hunted, orders)
                and not self.hunt_ants(ants, a_row, a_col, destinations, hunted, orders)
                and not self.hunt_unseen(
                    ants, a_row, a_col, destinations, hunted, orders
                )
                and not self.random_move(
                    ants, a_row, a_col, destinations, hunted, orders
                )
            ):
                getLogger().debug("blocked:can't move:%d,%d", a_row, a_col)
                destinations.append((a_row, a_col))
        self.standing_orders = orders
        for order in self.standing_orders:
            # move ant location to step destination
            order[0] = order[1]


if __name__ == "__main__":
    try:
        import psyco

        psyco.full()
    except ImportError:
        pass
    try:
        Ants.run(GreedyBot())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
