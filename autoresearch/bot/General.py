#!/usr/bin/env python
import time
from collections import deque
from math import isqrt

from ants import Ants


# define a class with a do_turn method
# the Ants.run method will parse and update bot input
# it will also run the do_turn method for us
class General:
    def __init__(self):
        # define class level variables, will be remembered between turns
        self.visits: dict[tuple[int, int], int] = {}
        self.remembered_hills: set[tuple[int, int]] = set()
        self.prev_enemies: list[tuple[int, int]] = []

    # do_setup is run once at the start of the game
    # after the bot has received the game settings
    # the ants class is created and setup by the Ants.run method
    def do_setup(self, ants: Ants):
        # initialize data structures after learning the game settings
        self.visits = {}
        self.remembered_hills = set()
        self.prev_enemies = []

    # do turn is run once per turn
    # the ants class has the game state and is updated by the Ants.run method
    # it also has several helper methods to use
    def do_turn(self, ants: Ants):
        # General: battle-local 1-ply max-min combat on a united-hill base.
        # Battling as General. Economy, hills, exploration, and defense
        # structure match Flood (iteration 142): global food claims, guard
        # then screen threatened hills, united march on the hill nearest
        # the army, second-hill reinforce, least-visited explore, walk-off.
        # Combat only: the static local-majority is_safe check is replaced
        # by a battle-local 1-ply max-min over precomputed influence
        # (Memetix-style: enemies that can attack each tile after one
        # move), scored with xathis weights (enemyDead*300 - myDead*180
        # - dist) against best-reply enemy moves, hard no-1v1 default,
        # 200 ms hard time box with the old heuristic as instant fallback.
        foods = ants.food()
        ants_list = ants.my_ants()
        my_set = set(ants_list)
        for hloc, _ in ants.enemy_hills():
            self.remembered_hills.add(hloc)
        for hloc in list(self.remembered_hills):
            if hloc in my_set:
                self.remembered_hills.discard(hloc)
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
        attack_r2 = ants.attackradius2 or 5
        rows, cols = ants.rows, ants.cols

        def sq_dist(a: tuple[int, int], b: tuple[int, int]) -> int:
            dr = abs(a[0] - b[0])
            dr = min(dr, rows - dr) if rows else dr
            dc = abs(a[1] - b[1])
            dc = min(dc, cols - dc) if cols else dc
            return dr * dr + dc * dc

        def is_safe_legacy(nloc: tuple[int, int], self_loc: tuple[int, int]) -> bool:
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

        # General combat: battle-local 1-ply max-min, precomputed once
        # per turn (never resolved live per ant). For each threatened ant
        # group, every candidate move is scored against best-reply enemy
        # moves with xathis weights (enemyDead*300 - myDead*180 - dist)
        # under the engine's focus rule, with a hard no-1v1 default. The
        # whole precompute runs under a 200 ms time box; on timeout (or
        # oversized battles) every lookup misses and is_safe falls back
        # to the legacy static check instantly.
        verdicts: dict[tuple[tuple[int, int], tuple[int, int]], bool] = {}
        combat_ok = ants.time_remaining() >= 250
        if combat_ok:
            deadline = time.monotonic() + 0.2
            span = isqrt(attack_r2) + 2
            threat_d = span + 1
            threatened_ants = [
                a
                for a in ants_list
                if any(ants.distance(a, e) <= threat_d for e in enemy_locs)
            ]
            # Connected components over threatened ants (link distance 5).
            groups: list[list[tuple[int, int]]] = []
            seen: set[tuple[int, int]] = set()
            for a in threatened_ants:
                if a in seen:
                    continue
                comp = [a]
                seen.add(a)
                queue_g: deque[tuple[int, int]] = deque([a])
                while queue_g:
                    cur = queue_g.popleft()
                    for b in threatened_ants:
                        if b not in seen and ants.distance(cur, b) <= 5:
                            seen.add(b)
                            comp.append(b)
                            queue_g.append(b)
                groups.append(comp)
            resolutions = 0
            for comp in groups:
                if time.monotonic() > deadline:
                    combat_ok = False
                    break
                local_foes = [
                    e
                    for e in enemy_locs
                    if any(ants.distance(a, e) <= threat_d + 1 for a in comp)
                ]
                if len(comp) > 8 or len(local_foes) > 8:
                    continue
                replies: dict[tuple[int, int], list[tuple[int, int]]] = {}
                for e in local_foes:
                    opts = [e]
                    for d in ("n", "e", "s", "w"):
                        nxt = ants.destination(e, d)
                        if ants.passable(nxt):
                            opts.append(nxt)
                    replies[e] = opts
                options: dict[tuple[int, int], list[tuple[int, int]]] = {}
                for a in comp:
                    cand = [a]
                    for d in ("n", "e", "s", "w"):
                        nxt = ants.destination(a, d)
                        if ants.passable(nxt):
                            cand.append(nxt)
                    options[a] = cand

                def resolve(
                    post_my: list[tuple[int, int]],
                    post_foe: list[tuple[int, int]],
                    mover: int,
                ) -> tuple[int, int, bool]:
                    # Exact 1-turn focus resolution on hypothesized post-
                    # move positions. Returns (my_dead, foe_dead,
                    # mover_dies).
                    my_dead = 0
                    foe_dead = 0
                    mover_dies = False
                    for i, a in enumerate(post_my):
                        foes = [
                            j
                            for j, r in enumerate(post_foe)
                            if sq_dist(a, r) <= attack_r2
                        ]
                        if not foes:
                            continue
                        weak = len(foes)
                        if (
                            min(
                                sum(
                                    1
                                    for k, b in enumerate(post_my)
                                    if sq_dist(post_foe[j], b) <= attack_r2
                                )
                                for j in foes
                            )
                            <= weak
                        ):
                            my_dead += 1
                            if i == mover:
                                mover_dies = True
                    for _j, r in enumerate(post_foe):
                        attackers = [
                            i
                            for i, b in enumerate(post_my)
                            if sq_dist(r, b) <= attack_r2
                        ]
                        if not attackers:
                            continue
                        weak = len(attackers)
                        if (
                            min(
                                sum(
                                    1
                                    for k, s in enumerate(post_foe)
                                    if sq_dist(post_my[i], s) <= attack_r2
                                )
                                for i in attackers
                            )
                            <= weak
                        ):
                            foe_dead += 1
                    return my_dead, foe_dead, mover_dies

                base_my = list(ants_list)
                idx = {a: n for n, a in enumerate(ants_list)}
                for a in comp:
                    if time.monotonic() > deadline or resolutions > 20000:
                        combat_ok = False
                        break
                    ai = idx[a]
                    dist0 = min((ants.distance(a, e) for e in local_foes), default=0)
                    for d in options[a]:
                        # Cooperative joint model: group buddies take the
                        # step that best supports this move (closest to it);
                        # outsiders stay static. This keeps 2v1 advances
                        # accepted while best-reply foes punish real deaths.
                        post_my = list(base_my)
                        for b in comp:
                            if b != a:
                                post_my[idx[b]] = min(
                                    options[b], key=lambda o: sq_dist(o, d)
                                )
                        post_my[ai] = d
                        # Advance-model enemy reply, then per-enemy best
                        # reply: each foe picks the reply minimizing our
                        # eval, holding the rest at their advance spots.
                        advance = [
                            min(replies[e], key=lambda r: sq_dist(r, d))
                            for e in local_foes
                        ]
                        my_d, foe_d, mover_d = resolve(post_my, advance, ai)
                        resolutions += 1
                        score = 300 * foe_d - 180 * my_d - dist0
                        best_my, best_foe, best_mover = my_d, foe_d, mover_d
                        for n, e in enumerate(local_foes):
                            if time.monotonic() > deadline:
                                combat_ok = False
                                break
                            for r in replies[e]:
                                alt = list(advance)
                                alt[n] = r
                                md, fd, mv = resolve(post_my, alt, ai)
                                resolutions += 1
                                val = 300 * fd - 180 * md - dist0
                                if val < score:
                                    score = val
                                    best_my, best_foe, best_mover = md, fd, mv
                        # Hard no-1v1 default: a move that dies for at
                        # most one foe is refused; the 14+ aggressive
                        # gate may still accept equal trades.
                        friends = sum(
                            1
                            for f in ants_list
                            if f != a and sq_dist(d, f) <= attack_r2
                        )
                        foes_now = sum(
                            1 for e in enemy_locs if sq_dist(d, e) <= attack_r2
                        )
                        nearby = sum(
                            1 for f in ants_list if f != a and ants.distance(d, f) <= 10
                        )
                        mover_dies = best_mover
                        reach = any(
                            sq_dist(r, d) <= attack_r2
                            for e in local_foes
                            for r in replies[e]
                        )
                        if (
                            foes_now == 0
                            and not reach
                            or not mover_dies
                            or best_foe > best_my
                            or (
                                nearby >= 14
                                and friends + 1 >= foes_now
                                and best_foe >= best_my
                            )
                        ):
                            verdicts[(a, d)] = True
                        else:
                            verdicts[(a, d)] = False
                if not combat_ok:
                    break

        def is_safe(nloc: tuple[int, int], self_loc: tuple[int, int]) -> bool:
            if combat_ok:
                v = verdicts.get((self_loc, nloc))
                if v is not None:
                    return v
            return is_safe_legacy(nloc, self_loc)

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

        def try_step(
            ant_loc: tuple[int, int], direction: str, safe: bool = True
        ) -> bool:
            new_loc = ants.destination(ant_loc, direction)
            if (
                new_loc not in destinations
                and ants.passable(new_loc)
                and ants.unoccupied(new_loc)
                and (not safe or is_safe(new_loc, ant_loc))
            ):
                ants.issue_order((ant_loc, direction))
                destinations.add(new_loc)
                return True
            return False

        destinations: set[tuple[int, int]] = set()
        held: list[tuple[int, int]] = []
        anchored: set[tuple[int, int]] = set()
        for ai, ant_loc in enumerate(ants_list):
            self.visits[ant_loc] = self.visits.get(ant_loc, 0) + 1
            best = target.get(ai)
            moved = False
            if best is not None:
                step = first_step(ant_loc, best)
                if step is not None and try_step(ant_loc, step):
                    moved = True
                if not moved:
                    # Assigned food is blocked; keep the claim so no other
                    # ant chases the same region this turn.
                    pass
            if not moved and threatened:
                # No food or blocked: first guard holds the hill,
                # extras screen the razer off it.
                nearest = min(threatened, key=lambda h: ants.distance(ant_loc, h))
                if nearest in anchored:
                    screen = min(
                        enemy_locs,
                        key=lambda e: ants.distance(nearest, e),
                        default=nearest,
                    )
                    step = first_step(ant_loc, screen)
                else:
                    anchored.add(nearest)
                    step = first_step(ant_loc, nearest)
                if step is not None and try_step(ant_loc, step):
                    moved = True
            if not moved and hills:
                # Flood: the group marches on one target, the hill
                # nearest the army as a whole. Hunt always; fearless
                # when ahead on hills.
                muster = min(
                    hills,
                    key=lambda h: sum(ants.distance(a, h) for a in ants_list),
                )
                step = first_step(ant_loc, muster)
                if step is not None and try_step(
                    ant_loc, step, safe=len(my_hills) <= len(hills)
                ):
                    moved = True
            if not moved and hills:
                # No hill move: reinforce the second-nearest hill.
                ordered = sorted(hills, key=lambda h: ants.distance(ant_loc, h))
                near = ordered[1] if len(ordered) > 1 else ordered[0]
                hstep = first_step(ant_loc, near)
                if hstep is not None and try_step(ant_loc, hstep):
                    moved = True
            if not moved:
                # Still stuck: explore least-visited squares first.
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
        Ants.run(General())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
