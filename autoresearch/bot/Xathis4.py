#!/usr/bin/env python
from collections import deque
from collections.abc import Callable

from ants import Ants

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]
SqDistFn = Callable[[Loc, Loc], int]
DestFn = Callable[[Loc, str], Loc]
PassFn = Callable[[Loc], bool]

CLUSTER_R = 8
DENIAL_ENEMIES = 3
DENIAL_CLAIMS = 2
_CELL = CLUSTER_R + 1

# Xathis combat: two modes per fight. AGGRO_NEED+ friends within
# AGGRO_RADIUS steps of the fight plus fewer than AGGRO_MAX_ENEMIES
# enemies visible means AGGRESSIVE (1-ply search with enemy
# best-reply and the 300/120 eval); otherwise PASSIVE (strict
# superiority only -- equal-or-worse trades refuse).
AGGRO_NEED = 10
AGGRO_RADIUS = 10
AGGRO_MAX_ENEMIES = 10

# Approach: an ant with an enemy inside APPROACH_RANGE steps
# advances on it via first_step pathing instead of walking only to
# food, hills, or empty ground.
APPROACH_RANGE = 8

# Aggressive eval weights: enemyDead * KILL_SCORE - myDead *
# DEATH_COST - dist. 1-for-1 scores +180 (take), 2-for-2 scores
# +360 (take), overruns refuse; the clash never emits a kill
# costing more ants than it kills.
KILL_SCORE = 300
DEATH_COST = 120

# Escape: among safe moves prefer the most open space, counting
# passable squares within ESCAPE_RADIUS steps.
ESCAPE_RADIUS = 3


def _scan_board(
    foods: list[Loc], enemy_locs: list[Loc], rows: int, cols: int
) -> tuple[list[int], dict[int, int]]:
    # One bucketed pass: cluster roots for foods within CLUSTER_R and,
    # per cluster, how many distinct enemies sit within CLUSTER_R of a
    # member food. Buckets are linear (no wrap): adjacent buckets catch
    # every linear-close pair, and explicit seam bands catch the pairs
    # the torus folds together (rows 0..R with rows-R..rows-1, same for
    # cols). Toroid manhattan inline, same formula as Ants.distance.
    n = len(foods)
    cell = _CELL
    fr = [f[0] for f in foods]
    fc = [f[1] for f in foods]
    buckets: dict[tuple[int, int], list[int]] = {}
    for i in range(n):
        buckets.setdefault((fr[i] // cell, fc[i] // cell), []).append(i)
    parent = list(range(n))

    def union(a: int, b: int) -> None:
        ra, rb = a, b
        while parent[ra] != ra:
            parent[ra] = parent[parent[ra]]
            ra = parent[ra]
        while parent[rb] != rb:
            parent[rb] = parent[parent[rb]]
            rb = parent[rb]
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    R = CLUSTER_R
    for key, members in buckets.items():
        br, bc = key
        for dbr, dbc in ((0, 0), (0, 1), (1, -1), (1, 0), (1, 1)):
            others = buckets.get((br + dbr, bc + dbc))
            if not others:
                continue
            inner = dbr == 0 and dbc == 0
            for ii, i in enumerate(members):
                ri = fr[i]
                ci = fc[i]
                group_b = members[ii + 1 :] if inner else others
                for j in group_b:
                    # Linear-gap reject: seam pairs never share
                    # linear buckets, so this never misfires.
                    dr = ri - fr[j]
                    if dr < 0:
                        dr = -dr
                    if dr > R:
                        continue
                    dc = ci - fc[j]
                    if dc < 0:
                        dc = -dc
                    if dc > R:
                        continue
                    if dr + dc <= R:
                        union(i, j)
    row_top = [i for i in range(n) if fr[i] <= CLUSTER_R]
    row_bot = [i for i in range(n) if fr[i] >= rows - CLUSTER_R]
    for i in row_top:
        for j in row_bot:
            if i == j:
                continue
            dr = fr[i] - fr[j]
            if dr < 0:
                dr = -dr
            if dr > rows - dr:
                dr = rows - dr
            if dr > R:
                continue
            dc = fc[i] - fc[j]
            if dc < 0:
                dc = -dc
            if dc > cols - dc:
                dc = cols - dc
            if dr + dc <= R:
                union(i, j)
    col_left = [i for i in range(n) if fc[i] <= CLUSTER_R]
    col_right = [i for i in range(n) if fc[i] >= cols - CLUSTER_R]
    for i in col_left:
        for j in col_right:
            if i == j:
                continue
            dr = fr[i] - fr[j]
            if dr < 0:
                dr = -dr
            if dr > rows - dr:
                dr = rows - dr
            if dr > R:
                continue
            dc = fc[i] - fc[j]
            if dc < 0:
                dc = -dc
            if dc > cols - dc:
                dc = cols - dc
            if dr + dc <= R:
                union(i, j)
    roots = [0] * n
    for i in range(n):
        a = i
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        roots[i] = a
    counts: dict[int, int] = {}
    for e in enemy_locs:
        er = e[0]
        ec = e[1]
        br, bc = er // cell, ec // cell
        hit: set[int] = set()
        for dbr in (-1, 0, 1):
            for dbc in (-1, 0, 1):
                cell_members = buckets.get((br + dbr, bc + dbc))
                if not cell_members:
                    continue
                for j in cell_members:
                    dr = er - fr[j]
                    if dr < 0:
                        dr = -dr
                    if dr > rows - dr:
                        dr = rows - dr
                    if dr > R:
                        continue
                    dc = ec - fc[j]
                    if dc < 0:
                        dc = -dc
                    if dc > cols - dc:
                        dc = cols - dc
                    if dr + dc <= R:
                        hit.add(roots[j])
        if er <= R or er >= rows - R:
            for j in row_top + row_bot:
                dr = er - fr[j]
                if dr < 0:
                    dr = -dr
                if dr > rows - dr:
                    dr = rows - dr
                if dr > R:
                    continue
                dc = ec - fc[j]
                if dc < 0:
                    dc = -dc
                if dc > cols - dc:
                    dc = cols - dc
                if dr + dc <= R:
                    hit.add(roots[j])
        if ec <= R or ec >= cols - R:
            for j in col_left + col_right:
                dr = er - fr[j]
                if dr < 0:
                    dr = -dr
                if dr > rows - dr:
                    dr = rows - dr
                if dr > R:
                    continue
                dc = ec - fc[j]
                if dc < 0:
                    dc = -dc
                if dc > cols - dc:
                    dc = cols - dc
                if dr + dc <= R:
                    hit.add(roots[j])
        for root in hit:
            counts[root] = counts.get(root, 0) + 1
    return roots, counts


def denied_food_groups(
    foods: list[Loc],
    enemy_locs: list[Loc],
    distance: DistFn,
    rows: int,
    cols: int,
) -> list[list[int]]:
    # Clusters contested by DENIAL_ENEMIES+ visible enemies within
    # CLUSTER_R of a cluster food. Each group holds food indices.
    if not foods or len(enemy_locs) < DENIAL_ENEMIES:
        return []
    roots, counts = _scan_board(foods, enemy_locs, rows, cols)
    contested = {r for r, c in counts.items() if c >= DENIAL_ENEMIES}
    groups: dict[int, list[int]] = {}
    for i, root in enumerate(roots):
        if root in contested:
            groups.setdefault(root, []).append(i)
    return list(groups.values())


def assign_food_targets(
    ants_list: list[Loc],
    foods: list[Loc],
    enemy_locs: list[Loc],
    distance: DistFn,
    rows: int,
    cols: int,
) -> dict[int, Loc]:
    # Champion greedy everywhere, except contested clusters take
    # exactly DENIAL_CLAIMS ants on their nearest foods (distinct ants
    # and distinct foods, nearest pairs first); the cluster's other
    # foods stay unclaimed this turn instead of spreading one per food.
    # A one-food cluster can only draw one claimant.
    target: dict[int, Loc] = {}
    if not foods or not ants_list:
        return target
    claimed: set[int] = set()
    denied: set[int] = set()
    for group in denied_food_groups(foods, enemy_locs, distance, rows, cols):
        denied.update(group)
        picks = 0
        ordered = sorted(
            (distance(ant, foods[fi]), ai, fi)
            for ai, ant in enumerate(ants_list)
            for fi in group
        )
        for _, ai, fi in ordered:
            if picks >= DENIAL_CLAIMS:
                break
            if ai not in target and fi not in claimed:
                target[ai] = foods[fi]
                claimed.add(fi)
                picks += 1
    pairs: list[tuple[int, int, int]] = []
    for ai, ant_loc in enumerate(ants_list):
        for fi, food_loc in enumerate(foods):
            pairs.append((distance(ant_loc, food_loc), ai, fi))
    pairs.sort()
    for _, ai, fi in pairs:
        if fi in denied:
            continue
        if ai not in target and fi not in claimed:
            target[ai] = foods[fi]
            claimed.add(fi)
    return target


def threat_reach(attack_r2: int) -> int:
    """Manhattan threat radius of one enemy after it moves one step."""
    return int(attack_r2**0.5) + 1


def count_near(
    ant_loc: Loc,
    ants_list: list[Loc],
    distance: DistFn,
    radius: int = AGGRO_RADIUS,
) -> int:
    """Friends (never self) within radius steps of the fight."""
    found = 0
    for friend in ants_list:
        if friend == ant_loc:
            continue
        if distance(ant_loc, friend) <= radius:
            found += 1
    return found


def is_aggressive(
    ant_loc: Loc,
    ants_list: list[Loc],
    distance: DistFn,
    need: int = AGGRO_NEED,
    radius: int = AGGRO_RADIUS,
    n_enemies: int = 0,
) -> bool:
    """Aggression gate: need+ friends near and few enemies visible."""
    return (
        count_near(ant_loc, ants_list, distance, radius) >= need
        and n_enemies < AGGRO_MAX_ENEMIES
    )


def nearest_approach_enemy(
    ant_loc: Loc,
    enemy_locs: list[Loc],
    distance: DistFn,
    limit: int = APPROACH_RANGE,
) -> Loc | None:
    """Nearest visible enemy within limit steps, else None.

    Ties keep the first enemy in list order so the branch is
    deterministic. Pure: no board state, no side effects.
    """
    best: Loc | None = None
    best_d = limit + 1
    for foe in enemy_locs:
        d = distance(ant_loc, foe)
        if d <= limit and d < best_d:
            best_d = d
            best = foe
    return best


def best_enemy_reply(
    dest: Loc,
    enemy: Loc,
    destination: DestFn,
    passable: PassFn,
    distance: DistFn,
) -> Loc:
    """The enemy's most damaging reply to our step onto dest.

    Each threatening enemy answers our move with its own move, so
    the 1-ply resolves against replies, not static positions: the
    reply is the passable square (hold included) nearest our dest,
    pressing the attack. Ties keep n/e/s/w/hold order so the search
    is deterministic. Pure: no board state, no side effects.
    """
    best = enemy
    best_d = distance(enemy, dest)
    for step in ("n", "e", "s", "w"):
        cand = destination(enemy, step)
        if not passable(cand):
            continue
        d = distance(cand, dest)
        if d < best_d:
            best_d = d
            best = cand
    return best


def clash_deaths(supporters: int, attackers: int) -> tuple[int, int]:
    """Local clash outcome as (enemyDead, myDead).

    Ours is the moving ant plus supporters in attack range of its
    dest; theirs is the enemy replies in range. Superiority wipes
    the smaller side at no cost, equal forces trade mutually, and
    an outnumbered attack dies for nothing. Pure: no side effects.
    """
    ours = supporters + 1
    theirs = attackers
    if theirs <= 0:
        return (0, 0)
    if ours > theirs:
        return (theirs, 0)
    if ours == theirs:
        return (theirs, ours)
    return (0, ours)


def combat_eval(enemy_dead: int, my_dead: int, dist: int) -> int:
    """Xathis aggressive eval: enemyDead*300 - myDead*120 - dist."""
    return enemy_dead * KILL_SCORE - my_dead * DEATH_COST - dist


def search_best_move(
    ant_loc: Loc,
    ants_list: list[Loc],
    enemy_locs: list[Loc],
    destination: DestFn,
    passable: PassFn,
    distance: DistFn,
    sq_dist: SqDistFn,
    rows: int,
    cols: int,
    attack_r2: int,
    claimed: set[Loc],
) -> tuple[str | None, Loc, int]:
    """Aggressive 1-ply: our 5 moves against enemy best-reply.

    Each legal move (4 dirs when passable, unoccupied, unclaimed;
    hold always) resolves its clash -- supporters are friends in
    attack range of the dest, attackers are best-replied enemies in
    range -- and scores combat_eval. Returns (direction, dest,
    eval); direction None means hold at ant_loc. Ties prefer the
    nearer square, then n/e/s/w/hold order. Pure: no orders.
    """
    options: list[tuple[str | None, Loc]] = [(None, ant_loc)]
    for step in ("n", "e", "s", "w"):
        cand = destination(ant_loc, step)
        if cand in claimed or not passable(cand):
            continue
        options.append((step, cand))
    occupied = set(ants_list) | set(enemy_locs)
    best_dir: str | None = None
    best_dest = ant_loc
    best_score: int | None = None
    best_dist = 0
    for move, dest in options:
        if move is not None and dest in occupied:
            continue
        supporters = 0
        for friend in ants_list:
            if friend != ant_loc and sq_dist(dest, friend) <= attack_r2:
                supporters += 1
        replies: list[Loc] = []
        for foe in enemy_locs:
            if distance(ant_loc, foe) <= APPROACH_RANGE + threat_reach(attack_r2):
                replies.append(
                    best_enemy_reply(dest, foe, destination, passable, distance)
                )
            else:
                replies.append(foe)
        attackers = 0
        for reply in replies:
            if sq_dist(dest, reply) <= attack_r2:
                attackers += 1
        near = min(distance(dest, reply) for reply in replies) if replies else 0
        killed, lost = clash_deaths(supporters, attackers)
        score = combat_eval(killed, lost, near)
        if (
            best_score is None
            or score > best_score
            or (score == best_score and near < best_dist)
        ):
            best_score = score
            best_dir = move
            best_dest = dest
            best_dist = near
    assert best_score is not None
    return (best_dir, best_dest, best_score)


def openness(
    dest: Loc,
    passable: PassFn,
    rows: int,
    cols: int,
    radius: int = ESCAPE_RADIUS,
) -> int:
    """Escape value: passable squares within radius steps of dest."""
    found = 0
    for dr in range(-radius, radius + 1):
        width = radius - abs(dr)
        for dc in range(-width, width + 1):
            if passable(((dest[0] + dr) % rows, (dest[1] + dc) % cols)):
                found += 1
    return found


def intercept_square(
    hill: Loc,
    enemy_locs: list[Loc],
    distance: DistFn,
    passable: PassFn,
    rows: int,
    cols: int,
) -> Loc | None:
    """Off-hill intercept for one threatened home hill.

    Screens the razer instead of piling onto the hill: take the
    nearest enemy to the hill, halve the toroidal approach, and
    return the nearest passable square to that midpoint (the
    midpoint itself when open). Ties keep the first enemy in list
    order so the branch is deterministic. No enemies -- or no
    passable square on the whole board -- returns None so the
    caller holds the champion fallback. Pure: no board state, no
    side effects.
    """
    if not enemy_locs or rows <= 0 or cols <= 0:
        return None
    foe = min(enemy_locs, key=lambda e: distance(hill, e))
    dr = foe[0] - hill[0]
    if dr > rows // 2:
        dr -= rows
    elif dr < -(rows // 2):
        dr += rows
    dc = foe[1] - hill[1]
    if dc > cols // 2:
        dc -= cols
    elif dc < -(cols // 2):
        dc += cols
    mid = ((hill[0] + int(dr / 2)) % rows, (hill[1] + int(dc / 2)) % cols)
    if passable(mid):
        return mid
    seen = {mid}
    queue: deque[Loc] = deque([mid])
    while queue:
        cur = queue.popleft()
        for step in ((-1, 0), (0, 1), (1, 0), (0, -1)):
            nxt = ((cur[0] + step[0]) % rows, (cur[1] + step[1]) % cols)
            if nxt in seen:
                continue
            seen.add(nxt)
            if passable(nxt):
                return nxt
            queue.append(nxt)
    return None


# define a class with a do_turn method
# the Ants.run method will parse and update bot input
# it will also run the do_turn method for us
class Xathis4:
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
        # Xathis4: champion Crowd economy, muster, guard, reinforce,
        # explore, and walk-off, with the combat core replaced by the
        # faithful xathis two-mode fight gated on small fights. An ant
        # with an enemy in range approaches it: with 10+ friends
        # within 10 steps and fewer than 10 enemies visible the
        # fight is AGGRESSIVE -- a 1-ply search over its 5 moves
        # against each threatening enemy's best reply, scoring
        # enemyDead*300 - myDead*120 - dist (1-for-1 and 2-for-2
        # engage, overruns never do) -- else PASSIVE, refusing all
        # equal-or-worse trades and escaping to the most open safe
        # square. Food, guard, muster, reinforce, explore, and
        # walk-off are champion.
        foods = ants.food()
        ants_list = ants.my_ants()
        my_set = set(ants_list)
        enemy_locs = [loc for loc, _ in ants.enemy_ants()]
        target = assign_food_targets(
            ants_list, foods, enemy_locs, ants.distance, ants.rows, ants.cols
        )
        for hloc, _ in ants.enemy_hills():
            self.remembered_hills.add(hloc)
        for hloc in list(self.remembered_hills):
            if hloc in my_set:
                self.remembered_hills.discard(hloc)
        hills = sorted(self.remembered_hills)
        my_hills = ants.my_hills()
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

        def is_safe(nloc: tuple[int, int], self_loc: tuple[int, int]) -> bool:
            # Passive xathis: strict superiority only -- equal or
            # worse trades refuse, however many friends stand near.
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
                if f == self_loc:
                    continue
                if sq_dist(nloc, f) <= attack_r2:
                    friends += 1
            return friends + 1 > enemies

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
                    inter = intercept_square(
                        nearest,
                        enemy_locs,
                        ants.distance,
                        ants.passable,
                        ants.rows,
                        ants.cols,
                    )
                    if inter is None:
                        inter = min(
                            enemy_locs,
                            key=lambda e: ants.distance(nearest, e),
                            default=nearest,
                        )
                    step = first_step(ant_loc, inter)
                else:
                    anchored.add(nearest)
                    step = first_step(ant_loc, nearest)
                if step is not None and try_step(ant_loc, step):
                    moved = True
            if not moved and enemy_locs:
                # Xathis fight: an ant with an enemy in range
                # approaches it instead of seeking only food, hills,
                # or empty ground.
                foe = nearest_approach_enemy(ant_loc, enemy_locs, ants.distance)
                if foe is not None and is_aggressive(
                    ant_loc, ants_list, ants.distance, n_enemies=len(enemy_locs)
                ):
                    # AGGRESSIVE: 1-ply over our 5 moves against
                    # enemy best-reply; the max-eval move issues
                    # even into 1-for-1 trades. A hold verdict ends
                    # the ant's turn so static-safe fallbacks cannot
                    # override the search.
                    direction, dest, _ = search_best_move(
                        ant_loc,
                        ants_list,
                        enemy_locs,
                        ants.destination,
                        ants.passable,
                        ants.distance,
                        sq_dist,
                        rows,
                        cols,
                        attack_r2,
                        destinations,
                    )
                    if direction is not None:
                        new_loc = ants.destination(ant_loc, direction)
                        if (
                            new_loc not in destinations
                            and ants.passable(new_loc)
                            and ants.unoccupied(new_loc)
                        ):
                            ants.issue_order((ant_loc, direction))
                            destinations.add(new_loc)
                            moved = True
                        else:
                            held.append(ant_loc)
                            moved = True
                    else:
                        held.append(ant_loc)
                        moved = True
                    foe = None
                if foe is not None:
                    # PASSIVE: advance only on strict superiority;
                    # otherwise escape to the most open safe square.
                    step = first_step(ant_loc, foe)
                    if step is not None and try_step(ant_loc, step):
                        moved = True
                    else:
                        flee_dir: str | None = None
                        flee_open = -1
                        flee_seen = -1
                        for cand in ("n", "e", "s", "w"):
                            cand_loc = ants.destination(ant_loc, cand)
                            if (
                                cand_loc in destinations
                                or not ants.passable(cand_loc)
                                or not ants.unoccupied(cand_loc)
                                or not is_safe(cand_loc, ant_loc)
                            ):
                                continue
                            cand_open = openness(cand_loc, ants.passable, rows, cols)
                            cand_seen = self.visits.get(cand_loc, 0)
                            if cand_open > flee_open or (
                                cand_open == flee_open and cand_seen < flee_seen
                            ):
                                flee_dir = cand
                                flee_open = cand_open
                                flee_seen = cand_seen
                        if flee_dir is not None and try_step(ant_loc, flee_dir):
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
        Ants.run(Xathis4())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
