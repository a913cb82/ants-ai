#!/usr/bin/env python
from collections import deque

from ants import Ants

# Duelist trade policy: refuse 1-for-1s by default (the
# strict-superiority gate), but allow the equal trade when it buys
# something concrete: (a) the hill rush is blocked, with most attack
# ants stuck (anthonyvh's 70% rule), so a trade that unblocks the march
# is worth it; or (b) the trade happens inside a hill-attack zone with
# backup arriving within BACKUP_STEPS.
HILL_ATTACK_RADIUS = 20
BACKUP_STEPS = 6
BLOCKED_RUSH_FRACTION = 0.7


def toroidal_sq_dist(
    a: tuple[int, int], b: tuple[int, int], rows: int, cols: int
) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, rows - dr) if rows else dr
    dc = abs(a[1] - b[1])
    dc = min(dc, cols - dc) if cols else dc
    return dr * dr + dc * dc


def count_engagement(
    nloc: tuple[int, int],
    self_loc: tuple[int, int],
    my_ants: list[tuple[int, int]],
    enemy_locs: list[tuple[int, int]],
    attack_r2: int,
    rows: int,
    cols: int,
) -> tuple[int, int]:
    """Local (friends, enemies) able to hit a move to nloc."""
    enemies = 0
    for e in enemy_locs:
        if toroidal_sq_dist(nloc, e, rows, cols) <= attack_r2:
            enemies += 1
            if enemies >= len(my_ants):
                break
    friends = 0
    for f in my_ants:
        if f == self_loc:
            continue
        if toroidal_sq_dist(nloc, f, rows, cols) <= attack_r2:
            friends += 1
    return friends, enemies


def nearest_toroidal(
    nloc: tuple[int, int],
    locs: list[tuple[int, int]],
    rows: int,
    cols: int,
    skip: tuple[int, int] | None = None,
) -> int | None:
    """Closest toroidal distance from nloc, or None when empty."""
    best: int | None = None
    for loc in locs:
        if loc == skip:
            continue
        d_col = min(abs(nloc[1] - loc[1]), cols - abs(nloc[1] - loc[1]))
        d_row = min(abs(nloc[0] - loc[0]), rows - abs(nloc[0] - loc[0]))
        dist = d_row + d_col
        if best is None or dist < best:
            best = dist
    return best


def blocked_rush(
    stuck: int, total: int, fraction: float = BLOCKED_RUSH_FRACTION
) -> bool:
    """anthonyvh's 70% rule: most of the hill rush is stuck."""
    return total > 0 and stuck / total >= fraction


def equal_trade_allowed(
    hill_dist: int | None, backup_dist: int | None, rush_blocked: bool
) -> bool:
    """A 1-for-1 is allowed only when it buys something concrete."""
    if rush_blocked:
        return True
    return (
        hill_dist is not None
        and hill_dist <= HILL_ATTACK_RADIUS
        and backup_dist is not None
        and backup_dist <= BACKUP_STEPS
    )


def trade_safe(
    friends: int,
    enemies: int,
    hill_dist: int | None,
    backup_dist: int | None,
    rush_blocked: bool,
) -> bool:
    """Full gate: strict superiority always, equal trades situational."""
    if enemies == 0:
        return True
    if friends + 1 > enemies:
        return True
    if friends + 1 < enemies:
        return False
    return equal_trade_allowed(hill_dist, backup_dist, rush_blocked)


# Defender proportional guard: 1 guard per 2 raiders, and the muster
# home front calls for help early (radius 20, no closing read).
EARLY_CALL_RADIUS = 20
GUARDS_PER_RAIDERS = 2


def guards_needed(n_raiders: int, per: int = GUARDS_PER_RAIDERS) -> int:
    """Guards for a raid: 1 per 2 raiders, rounded up."""
    return (n_raiders + per - 1) // per


def max_gatherer_draft(n_gatherers: int) -> int:
    """The economy never lends more than a third of its gatherers."""
    return n_gatherers // 3


def hill_threatened_old(dist: int, is_closing: bool) -> bool:
    """Flood's rule: close, or closing from mid range."""
    return dist <= 10 or (dist <= 16 and is_closing)


def hill_threatened(dist: int, is_closing: bool, early: bool) -> bool:
    """Old rule, plus the early call on the muster home front."""
    if hill_threatened_old(dist, is_closing):
        return True
    return early and dist <= EARLY_CALL_RADIUS


def assign_guards(
    free_ids: list[int],
    gatherer_ids: list[int],
    quotas: list[int],
    draft_cap: int,
) -> dict[int, int]:
    """Map ant index to threatened-hill slot; free ants march first,
    then gatherers up to the draft cap."""
    assignment: dict[int, int] = {}
    free = list(free_ids)
    gatherers = list(gatherer_ids)
    drafted = 0
    for hi, quota in enumerate(quotas):
        need = quota
        while need > 0 and free:
            assignment[free.pop(0)] = hi
            need -= 1
        while need > 0 and gatherers and drafted < draft_cap:
            assignment[gatherers.pop(0)] = hi
            need -= 1
            drafted += 1
    return assignment


# Endgamer closing rule: past turn 600 (of 1000) idle explorers sit
# on held hills and contest the nearest uncontrolled hill only with
# strict local superiority, instead of diffusing. Economy, muster,
# combat gates, and defense are untouched.
ENDGAME_TURN = 600
ENDGAME_THEATER_R2 = 400


def endgame_active(turn: int) -> bool:
    """The closing rule flips on at turn 600 and stays on."""
    return turn >= ENDGAME_TURN


def endgame_challenge_allowed(friends: int, enemies: int) -> bool:
    """Strict local superiority: the committing force must outnumber."""
    return friends + 1 > enemies


def count_near(
    loc: tuple[int, int],
    others: list[tuple[int, int]],
    r2: int,
    rows: int,
    cols: int,
) -> int:
    """Ants of `others` inside squared-toroidal range r2 of loc."""
    return sum(1 for o in others if toroidal_sq_dist(loc, o, rows, cols) <= r2)


def theater_allows(
    goal: tuple[int, int],
    my_ants: list[tuple[int, int]],
    enemy_locs: list[tuple[int, int]],
    rows: int,
    cols: int,
) -> bool:
    """Our theater force at an uncontrolled hill strictly outnumbers."""
    friends = count_near(goal, my_ants, ENDGAME_THEATER_R2, rows, cols)
    enemies = count_near(goal, enemy_locs, ENDGAME_THEATER_R2, rows, cols)
    return endgame_challenge_allowed(friends, enemies)


# define a class with a do_turn method
# the Ants.run method will parse and update bot input
# it will also run the do_turn method for us
class Duelist:
    def __init__(self):
        # define class level variables, will be remembered between turns
        self.visits: dict[tuple[int, int], int] = {}
        self.seen: set[tuple[int, int]] = set()
        self.remembered_hills: set[tuple[int, int]] = set()
        self.prev_enemies: list[tuple[int, int]] = []
        self.turn = 0

    # do_setup is run once at the start of the game
    # after the bot has received the game settings
    # the ants class is created and setup by the Ants.run method
    def do_setup(self, ants: Ants):
        # initialize data structures after learning the game settings
        self.visits = {}
        self.seen = set()
        self.remembered_hills = set()
        self.prev_enemies = []
        self.turn = 0

    # do turn is run once per turn
    # the ants class has the game state and is updated by the Ants.run method
    # it also has several helper methods to use
    def do_turn(self, ants: Ants):
        # Duelist: Flood's united hunt, but idle ants push the unseen
        # edge by BFS instead of diffusing over least-visited
        # neighbours. Battling as Duelist: 1-for-1 trades are refused
        # by default (strict-superiority gate) and allowed only when
        # they buy something concrete -- a blocked hill rush or a
        # hill-zone trade with backup arriving.
        # aggression, walk-off, food, and exploration match iteration
        # 76. Hunt always; ahead on hills, hunters skip the safety
        # filter. Closeouts need teeth, not patience.
        self.turn += 1
        endgame = endgame_active(self.turn)
        foods = ants.food()
        ants_list = ants.my_ants()
        my_set = set(ants_list)
        for r in range(ants.rows):
            for c in range(ants.cols):
                loc = (r, c)
                if ants.visible(loc):
                    self.seen.add(loc)
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

        # Flood: the group marches on one target, the hill nearest the
        # army as a whole. Hoisted so the rush check shares it.
        muster_target: tuple[int, int] | None = None
        if hills and ants_list:
            muster_target = min(
                hills,
                key=lambda h: sum(ants.distance(a, h) for a in ants_list),
            )
        # Defender: the muster home front calls for help early. The
        # home hill nearest the muster target treats any enemy inside
        # 20 steps as a raid instead of waiting for the closing read.
        early_hill: tuple[int, int] | None = None
        if muster_target is not None and my_hills:
            early_hill = min(my_hills, key=lambda h: ants.distance(h, muster_target))
        threatened = [
            h
            for h in my_hills
            if any(
                hill_threatened(ants.distance(h, e), closing(e, h), h == early_hill)
                for e in enemy_locs
            )
        ]
        # Defender: proportional guard. Each threatened hill draws 1
        # guard per 2 raiders inside its threat radius (20 on the early
        # hill, 16 elsewhere). Free ants march first; gatherers are
        # drafted only up to a third of their number.
        guard_for: dict[int, tuple[int, int]] = {}
        if threatened:
            ordered_hills = sorted(threatened)
            quotas: list[int] = []
            for h in ordered_hills:
                radius = EARLY_CALL_RADIUS if h == early_hill else 16
                raiders = sum(1 for e in enemy_locs if ants.distance(h, e) <= radius)
                quotas.append(max(1, guards_needed(raiders)))
            free_ids = [ai for ai in range(len(ants_list)) if ai not in target]
            gatherer_ids = [ai for ai in range(len(ants_list)) if ai in target]
            slot = assign_guards(
                free_ids, gatherer_ids, quotas, max_gatherer_draft(len(target))
            )
            guard_for = {ai: ordered_hills[hi] for ai, hi in slot.items()}
        attack_r2 = ants.attackradius2 or 5
        rows, cols = ants.rows, ants.cols
        # Duelist: is the hill rush blocked? Attack ants (no food
        # claim) count as stuck when no passable neighbour steps
        # closer to the muster hill. Static and O(ants): no BFS on the
        # decision path.
        rush_blocked = False
        if muster_target is not None:
            attack_pool = [a for ai, a in enumerate(ants_list) if ai not in target]
            if attack_pool:
                stuck = 0
                for a in attack_pool:
                    here = ants.distance(a, muster_target)
                    closer = False
                    for d in ("n", "e", "s", "w"):
                        nxt = ants.destination(a, d)
                        if (
                            ants.passable(nxt)
                            and ants.distance(nxt, muster_target) < here
                        ):
                            closer = True
                            break
                    if not closer:
                        stuck += 1
                rush_blocked = blocked_rush(stuck, len(attack_pool))

        def is_safe(nloc: tuple[int, int], self_loc: tuple[int, int]) -> bool:
            friends, enemies = count_engagement(
                nloc, self_loc, ants_list, enemy_locs, attack_r2, rows, cols
            )
            hill_dist: int | None = None
            backup_dist: int | None = None
            if friends + 1 == enemies:
                # Only price an equal trade when one is on the table.
                hill_dist = nearest_toroidal(nloc, hills, rows, cols)
                backup_dist = nearest_toroidal(
                    nloc, ants_list, rows, cols, skip=self_loc
                )
            return trade_safe(friends, enemies, hill_dist, backup_dist, rush_blocked)

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

        def edge_step(start: tuple[int, int], budget: int = 500) -> str | None:
            # First step of the shortest passable path to the nearest
            # square never seen. None when explored or over budget.
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
                    if nxt not in self.seen:
                        node = nxt
                        while parent[node][0] != start:
                            node = parent[node][0]
                        return parent[node][1]
                    queue.append(nxt)
            return None

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
        challenge_cache: dict[tuple[int, int], bool] = {}
        held: list[tuple[int, int]] = []
        anchored: set[tuple[int, int]] = set()
        for ai, ant_loc in enumerate(ants_list):
            self.visits[ant_loc] = self.visits.get(ant_loc, 0) + 1
            best = target.get(ai)
            moved = False
            if ai in guard_for:
                # Proportional guard: only the drafted quota marches;
                # the first guard holds the hill, extras screen the
                # razer off it. A guard with no path holds its ground
                # instead of falling back to the muster.
                hill = guard_for[ai]
                if hill in anchored:
                    screen = min(
                        enemy_locs,
                        key=lambda e: ants.distance(hill, e),
                        default=hill,
                    )
                    step = first_step(ant_loc, screen)
                else:
                    anchored.add(hill)
                    step = first_step(ant_loc, hill)
                if step is not None and try_step(ant_loc, step):
                    moved = True
                if not moved:
                    held.append(ant_loc)
                if ants.time_remaining() < 10:
                    break
                continue
            if best is not None:
                step = first_step(ant_loc, best)
                if step is not None and try_step(ant_loc, step):
                    moved = True
                if not moved:
                    # Assigned food is blocked; keep the claim so no other
                    # ant chases the same region this turn.
                    pass
            if not moved and hills and muster_target is not None:
                # Flood: the group marches on one target, the hill
                # nearest the army as a whole. Hunt always; fearless
                # when ahead on hills.
                step = first_step(ant_loc, muster_target)
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
            if not moved and endgame:
                # Endgamer: sit on the nearest held hill. An ant
                # already sitting (or with no held hill) contests the
                # nearest uncontrolled hill, but only with strict
                # superiority at the theater and at the step.
                sit: tuple[int, int] | None = None
                sit_best = 0
                for h in my_hills:
                    d = ants.distance(ant_loc, h)
                    if sit is None or d < sit_best:
                        sit = h
                        sit_best = d
                if sit is not None and ant_loc != sit:
                    sit_step = first_step(ant_loc, sit)
                    if sit_step is not None and try_step(ant_loc, sit_step):
                        moved = True
                else:
                    goal: tuple[int, int] | None = None
                    goal_best = 0
                    for h in hills:
                        d = ants.distance(ant_loc, h)
                        if goal is None or d < goal_best:
                            goal = h
                            goal_best = d
                    if goal is not None:
                        if goal not in challenge_cache:
                            challenge_cache[goal] = theater_allows(
                                goal, ants_list, enemy_locs, rows, cols
                            )
                        if challenge_cache[goal]:
                            here = ants.distance(ant_loc, goal)
                            steps: list[str] = []
                            bstep = first_step(ant_loc, goal)
                            if bstep is not None:
                                steps.append(bstep)
                            for direction in ("n", "e", "s", "w"):
                                if (
                                    direction not in steps
                                    and ants.distance(
                                        ants.destination(ant_loc, direction), goal
                                    )
                                    < here
                                ):
                                    steps.append(direction)
                            for step in steps:
                                dest = ants.destination(ant_loc, step)
                                if (
                                    dest in destinations
                                    or not ants.passable(dest)
                                    or not ants.unoccupied(dest)
                                ):
                                    continue
                                cf, ce = count_engagement(
                                    dest,
                                    ant_loc,
                                    ants_list,
                                    enemy_locs,
                                    attack_r2,
                                    rows,
                                    cols,
                                )
                                if endgame_challenge_allowed(cf, ce):
                                    ants.issue_order((ant_loc, step))
                                    destinations.add(dest)
                                    moved = True
                                    break
            if not moved and not endgame:
                # Scout: push the unseen edge first, so maze corridors
                # get walked early and distant food shows sooner.
                estep = edge_step(ant_loc)
                if estep is not None and try_step(ant_loc, estep):
                    moved = True
            if not moved and not endgame:
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
        Ants.run(Duelist())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
