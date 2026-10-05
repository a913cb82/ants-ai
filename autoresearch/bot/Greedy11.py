#!/usr/bin/env python
from collections import deque
from collections.abc import Callable

from ants import Ants

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]

CLUSTER_R = 8
DENIAL_ENEMIES = 3
DENIAL_CLAIMS = 2
_CELL = CLUSTER_R + 1
# Range-gated food (lazarant food25 mechanism, the census winner's
# economy): food claims only reach FOOD_RADIUS steps out. Beyond
# that ants explore/cover instead of trekking cross-map through
# crowded 10p territory. Duel boards are small, so the gate rarely
# binds there; 10p boards are big, so it frees explorers exactly
# where greedy loses the expansion race.
FOOD_RADIUS = 25
# Race-gated (winnable) denial with soft-cede: a contested cluster
# draws denial claimants only when our nearest ant stands no farther
# from the cluster than the nearest visible enemy. Ties still deny,
# so duel middle-food races play on; a lost cluster draws NO denial
# stacking -- but its foods stay eligible for normal nearest-pair
# greedy claims below, so nearby ants still gather instead of
# starving while far ants are never yanked cross-map onto it.
DENIAL_RACE_MARGIN = 0


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
    # Champion greedy everywhere, except winnable contested clusters
    # take exactly DENIAL_CLAIMS ants on their nearest foods (distinct
    # ants and distinct foods, nearest pairs first); the cluster's
    # other foods stay unclaimed this turn instead of spreading one
    # per food. A one-food cluster can only draw one claimant. A lost
    # cluster (our nearest ant farther than the nearest enemy plus
    # DENIAL_RACE_MARGIN) draws no denial stacking and -- the
    # soft-cede -- its foods stay open to fair greedy claims below,
    # so crowds keep gathering while duels keep their takes.
    target: dict[int, Loc] = {}
    if not foods or not ants_list:
        return target
    claimed: set[int] = set()
    denied: set[int] = set()
    for group in denied_food_groups(foods, enemy_locs, distance, rows, cols):
        ours = min(distance(ant, foods[fi]) for ant in ants_list for fi in group)
        theirs = min(distance(e, foods[fi]) for e in enemy_locs for fi in group)
        if ours > theirs + DENIAL_RACE_MARGIN:
            continue
        denied.update(group)
        picks = 0
        ordered = sorted(
            (distance(ant, foods[fi]), ai, fi)
            for ai, ant in enumerate(ants_list)
            for fi in group
            if distance(ant, foods[fi]) <= FOOD_RADIUS
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
            if distance(ant_loc, food_loc) <= FOOD_RADIUS:
                pairs.append((distance(ant_loc, food_loc), ai, fi))
    pairs.sort()
    for _, ai, fi in pairs:
        if fi in denied:
            continue
        if ai not in target and fi not in claimed:
            target[ai] = foods[fi]
            claimed.add(fi)
    return target


SqDistFn = Callable[[Loc, Loc], int]
PassFn = Callable[[Loc], bool]
Weights = tuple[float, float, float, float]

# Delineate combat (RESEARCH.md "delineate heuristic combat", top
# 10, briefly top 3): zero search. Every candidate move scores
# greedily from horizon-limited BFS feature fields of the form
# 1/(1+d^2): food, enemy, hill, and unseen (visits paint) fields,
# plus a kill bonus gated on strict local superiority. No minimax,
# no sampling, no influence maps -- pure greedy field climbing.
FIELD_HORIZON = 8
COMBAT_RANGE = 8
W_FOOD = 1.0
W_ENEMY = 0.5
W_HILL = 3.0
W_UNSEEN = 0.1
KILL_BONUS = 2.0
WEIGHTS: Weights = (W_FOOD, W_ENEMY, W_HILL, W_UNSEEN)

# Off-hill screen and the 10-gate, vendored from the champion's
# combat helpers so this entry stays self-contained (stdlib +
# ants.py only, never combat.py). The first guard still holds the
# threatened hill; extras march halfway to its nearest enemy.
EQUAL_TRADE_NEAR = 10
# Objective-weighted bravery: an even-trade combat step (ours equals
# theirs, at least one foe in range) is worth taking only when the
# destination stands this close to visible food or a remembered
# enemy hill -- something worth dying for. 1vN is never brave, and
# pointless 1v1s far from objectives still hold.
BRAVE_OBJECTIVE_R = 2


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


def _bfs_dists(
    start: Loc, passable: PassFn, rows: int, cols: int, horizon: int
) -> dict[Loc, int]:
    # Toroidal BFS distances from start; water blocks, steps past
    # horizon are never expanded. Pure: no board state, no effects.
    seen = {start: 0}
    if horizon < 0 or rows <= 0 or cols <= 0:
        return seen
    queue: deque[Loc] = deque([start])
    while queue:
        cur = queue.popleft()
        if seen[cur] >= horizon:
            continue
        dist = seen[cur] + 1
        for step in ((-1, 0), (0, 1), (1, 0), (0, -1)):
            nxt = ((cur[0] + step[0]) % rows, (cur[1] + step[1]) % cols)
            if nxt in seen or not passable(nxt):
                continue
            seen[nxt] = dist
            queue.append(nxt)
    return seen


def bfs_field(
    start: Loc,
    targets: set[Loc],
    passable: PassFn,
    rows: int,
    cols: int,
    horizon: int = FIELD_HORIZON,
) -> float:
    # One BFS feature field: the sum of 1/(1+d^2) over targets
    # within horizon BFS steps of start. Pure: no side effects.
    if not targets:
        return 0.0
    total = 0.0
    dists = _bfs_dists(start, passable, rows, cols, horizon)
    for node, dist in dists.items():
        if node in targets:
            total += 1.0 / (1.0 + dist * dist)
    return total


def count_sides(
    dest: Loc,
    mover: Loc,
    own_ants: list[Loc],
    enemy_locs: list[Loc],
    sq_dist: SqDistFn,
    attack_r2: int,
) -> tuple[int, int]:
    # (ours, theirs) at dest: friends in attack range plus the
    # moving ant itself, versus enemies in attack range. Pure.
    theirs = sum(1 for e in enemy_locs if sq_dist(dest, e) <= attack_r2)
    friends = sum(1 for f in own_ants if f != mover and sq_dist(dest, f) <= attack_r2)
    return (friends + 1, theirs)


def brave_even_trade(
    dest: Loc,
    mover: Loc,
    own_ants: list[Loc],
    enemy_locs: list[Loc],
    foods: set[Loc] | list[Loc],
    hills: set[Loc] | list[Loc],
    distance: DistFn,
    sq_dist: SqDistFn,
    attack_r2: int,
    radius: int = BRAVE_OBJECTIVE_R,
) -> bool:
    # True only for an even trade (equal ants, at least one foe in
    # range) landing within radius of food or a known enemy hill.
    # Strict wins and crowd-backed equals go through is_safe; 1vN
    # (theirs exceeds ours) is never brave. Pure: no side effects.
    ours, theirs = count_sides(dest, mover, own_ants, enemy_locs, sq_dist, attack_r2)
    if theirs < 1 or ours != theirs:
        return False
    return any(distance(dest, f) <= radius for f in foods) or any(
        distance(dest, h) <= radius for h in hills
    )


def score_move(
    dest: Loc,
    mover: Loc,
    own_ants: list[Loc],
    enemy_locs: list[Loc],
    foods: set[Loc],
    hills: set[Loc],
    visits: dict[Loc, int] | None,
    passable: PassFn,
    sq_dist: SqDistFn,
    attack_r2: int,
    rows: int,
    cols: int,
    horizon: int = FIELD_HORIZON,
    weights: Weights | None = None,
) -> float:
    # Greedy delineate score for ending the move on dest: weighted
    # food/enemy/hill/unseen fields from a single BFS, plus
    # KILL_BONUS only with strict local superiority (ours exceeds
    # theirs with at least one foe in range). Equality earns no
    # bonus, so hold wins unless another field does. Pure.
    wf, we, wh, wu = WEIGHTS if weights is None else weights
    food = 0.0
    enemy = 0.0
    hill = 0.0
    unseen = 0.0
    dists = _bfs_dists(dest, passable, rows, cols, horizon)
    for node, dist in dists.items():
        bump = 1.0 / (1.0 + dist * dist)
        if node in foods:
            food += bump
        if node in enemy_locs:
            enemy += bump
        if node in hills:
            hill += bump
        if visits is not None and visits.get(node, 0) == 0:
            unseen += bump
    ours, theirs = count_sides(dest, mover, own_ants, enemy_locs, sq_dist, attack_r2)
    bonus = KILL_BONUS if theirs >= 1 and ours > theirs else 0.0
    return wf * food + we * enemy + wh * hill + wu * unseen + bonus


def pick_best(scores: dict[str, float]) -> str:
    # Direction with the highest score; ties keep the first-listed
    # candidate, so callers list hold first and ties hold. Pure.
    return max(scores, key=lambda d: scores[d])


# define a class with a do_turn method
# the Ants.run method will parse and update bot input
# it will also run the do_turn method for us
class Greedy11:
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
        # Greedy: champion wiring (Denial's economy, off-hill
        # screening guards, single-target muster, reinforce,
        # least-visited explore, walk-off) with the combat core
        # replaced by delineate greedy fields: zero search, each
        # candidate move scores 1/(1+d^2) food/enemy/hill/unseen
        # fields plus a kill bonus only under strict local
        # superiority. Food, guard, muster, reinforce, explore,
        # and walk-off are champion.
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
            # Odds: EQUAL_TRADE_NEAR (10) near friends accept equal
            # trades, down from champion's tuned 14.
            return near >= EQUAL_TRADE_NEAR and friends + 1 >= enemies

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
                # Delineate: no food or guard move and a foe within
                # COMBAT_RANGE. Zero search: score hold plus every
                # passable, unoccupied, unclaimed neighbor on the
                # 1/(1+d^2) food/enemy/hill/unseen fields, with the
                # kill bonus only under strict local superiority.
                # Step only to a strict winner that is also safe to
                # stand on (no foe in range, strict local edge, or
                # an equal trade backed by EQUAL_TRADE_NEAR friends
                # nearby), or to a brave even trade near food or a
                # known enemy hill; other suicides hold and fall
                # through to muster, reinforce, and explore. Ties
                # hold likewise.
                in_range = enemy_locs and (
                    min(ants.distance(ant_loc, e) for e in enemy_locs) <= COMBAT_RANGE
                )
                if not moved and in_range:
                    options: dict[str, Loc] = {"-": ant_loc}
                    for d in ("n", "e", "s", "w"):
                        cand = ants.destination(ant_loc, d)
                        if (
                            cand not in destinations
                            and ants.passable(cand)
                            and ants.unoccupied(cand)
                        ):
                            options[d] = cand
                    food_set = set(foods)
                    hill_set = set(hills)
                    scored = {
                        d: score_move(
                            loc,
                            ant_loc,
                            ants_list,
                            enemy_locs,
                            food_set,
                            hill_set,
                            self.visits,
                            ants.passable,
                            sq_dist,
                            attack_r2,
                            rows,
                            cols,
                        )
                        for d, loc in options.items()
                    }
                    choice = pick_best(scored)
                    if (
                        choice != "-"
                        and scored[choice] > scored["-"]
                        and (
                            is_safe(options[choice], ant_loc)
                            or brave_even_trade(
                                options[choice],
                                ant_loc,
                                ants_list,
                                enemy_locs,
                                foods,
                                hills,
                                ants.distance,
                                sq_dist,
                                attack_r2,
                            )
                        )
                    ):
                        ants.issue_order((ant_loc, choice))
                        destinations.add(options[choice])
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
        Ants.run(Greedy11())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
