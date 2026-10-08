#!/usr/bin/env python
"""Softmax12: path-aware harvest by BFS food miles on crowd combat.

Economy is Denial-style contested clusters (exactly DENIAL_CLAIMS
ants on miles-nearest foods of a hot cluster) with one new rule no
repo Python bot uses: every harvest claim is ordered by BFS food
miles -- the true shortest walk around water -- instead of toroidal
manhattan. Wall-blocked foods sink (long mile, or manhattan plus
WALL_PENALTY when sealed beyond the horizon) so ants stop queuing
for food across stone. On open ground miles equal manhattan, so the
champion greedy is preserved exactly where it already wins.

Combat is the crowd chain (legs 1-7, no sampling anywhere):
pack-gated seek approach, committed-join pair attacks, ahead-only
1v1 duels, off-hill screening, 10-gate equal trades, fearless press
while fewer than CROWD_LIMIT foes show. Guard, muster, reinforce,
explore, and walk-off are champion.

Second mechanism, ported from fourmidable (2011 #9,
FoodAndHills.java): a food race gate. An ant skips a harvest claim
when the nearest visible foe walks to that food more than
FOOD_HEAD_START (3, fourmidable's number) steps ahead of it, so
ants stop donating long walks to camped food. Enemy walks come
from the same per-food BFS (foes join the goal set). Contested
denial clusters stay exempt as deliberate fights.

Distinct from the base and its line:
- Softmax (staged): joint max-min over sampled enemy replies with
  a logistic aggression coin -- Softmax12 has no sampling, no RNG,
  no joint enumeration, no carve.
- Softmax10: per-foe threat tax on harvest plus pack-press rules --
  Softmax12 taxes nothing per foe; walls, not lurkers, move claims.
- Softmax11: ghost memory, deterministic pursuit, wall-aware carve,
  directed retreat -- Softmax12 remembers no ghosts, pursues only
  with a pack, carves nothing, retreats nowhere special.
- Crowd (champion): manhattan harvest -- Softmax12's miles reorder
  every claim behind walls. New mix, new rule.
"""

from collections import deque
from collections.abc import Callable

from ants import Ants

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]
PassFn = Callable[[Loc], bool]
DestFn = Callable[[Loc, str], Loc]

CLUSTER_R = 8
DENIAL_ENEMIES = 3
DENIAL_CLAIMS = 2
_CELL = CLUSTER_R + 1

# BFS food miles: true walk length around water from each food.
# Horizon caps the walk; beyond it the food counts as sealed and
# falls back to manhattan plus WALL_PENALTY. Budget caps work per
# food so crowded maze turns stay far under the clock.
MILE_HORIZON = 32
MILE_BUDGET = 800
WALL_PENALTY = 50

# Food race gate, ported from fourmidable (2011 #9, MyBot
# FOOD_HEAD_START = 3): an ant skips a food when the nearest
# visible foe walks there more than this many steps ahead of it.
# Contested denial clusters are deliberate fights and stay exempt.
FOOD_HEAD_START = 3

# Crowd combat legs (same numbers as the champion chain).
SEEK_RANGE = 8
EQUAL_TRADE_NEAR = 10
PACK_NEED = 3
PACK_RADIUS = 10
CROWD_LIMIT = 10

_DIRS = ("n", "e", "s", "w")
_AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}


def _scan_board(
    foods: list[Loc], enemy_locs: list[Loc], rows: int, cols: int
) -> tuple[list[int], dict[int, int]]:
    # One bucketed pass: cluster roots for foods within CLUSTER_R and,
    # per cluster, how many distinct enemies sit within CLUSTER_R of a
    # member food. Linear buckets plus explicit seam bands, same wrap
    # formula as Ants.distance.
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


def bfs_miles(
    source: Loc,
    rows: int,
    cols: int,
    passable: PassFn,
    destination: DestFn,
    horizon: int = MILE_HORIZON,
    budget: int = MILE_BUDGET,
    goals: set[Loc] | None = None,
) -> dict[Loc, int]:
    """True walk lengths from a food around water, up to a horizon.

    Breadth-first over passable squares on the torus; the source is
    0 even when unpassable (food sits on open ground). Stops at the
    horizon, at the expansion budget, and as soon as every goal is
    reached (recorded miles are already exact then), so maze boards
    stay cheap. Pure: no board state beyond the two callbacks.
    """
    miles: dict[Loc, int] = {source: 0}
    if horizon <= 0:
        return miles
    pending = set(goals) - {source} if goals else set()
    if goals is not None and not pending:
        return miles
    queue: deque[Loc] = deque([source])
    expanded = 0
    while queue and expanded < budget:
        cur = queue.popleft()
        expanded += 1
        step = miles[cur] + 1
        if step > horizon:
            continue
        for d in _DIRS:
            nxt = destination(cur, d)
            if nxt in miles or not passable(nxt):
                continue
            miles[nxt] = step
            queue.append(nxt)
            if nxt in pending:
                pending.discard(nxt)
                if not pending:
                    queue.clear()
                    break
    return miles


def food_mile(
    ant: Loc,
    food: Loc,
    rows: int,
    cols: int,
    passable: PassFn,
    destination: DestFn,
    distance: DistFn,
    cache: dict[Loc, dict[Loc, int]],
    goals: set[Loc] | None = None,
) -> int:
    """Harvest cost of one ant-food pair: BFS walk, else penalized.

    Reached squares cost their exact walk length; sealed squares
    (beyond horizon or budget) cost manhattan plus WALL_PENALTY so
    they sink below every walkable claim without starving the army
    when everything is sealed. The per-food BFS is shared by cache.
    """
    field = cache.get(food)
    if field is None:
        field = bfs_miles(food, rows, cols, passable, destination, goals=goals)
        cache[food] = field
    walked = field.get(ant)
    if walked is not None:
        return walked
    return distance(ant, food) + WALL_PENALTY


def nearest_foe_mile(
    food: Loc,
    rows: int,
    cols: int,
    passable: PassFn,
    destination: DestFn,
    distance: DistFn,
    enemies: list[Loc],
    cache: dict[Loc, dict[Loc, int]],
    goals: set[Loc] | None = None,
) -> int | None:
    """Nearest visible foe's walk to a food, else None."""
    best: int | None = None
    for foe in enemies:
        mile = food_mile(
            foe, food, rows, cols, passable, destination, distance, cache, goals
        )
        if best is None or mile < best:
            best = mile
    return best


def bfs_worthwhile(
    foods: list[Loc],
    ants_list: list[Loc],
    distance: DistFn,
    horizon: int = MILE_HORIZON,
) -> set[int]:
    """Food indices worth a BFS: some ant within horizon manhattan.

    A walk is never shorter than manhattan (each step cuts it by at
    most one), so foods farther than the horizon from every ant can
    never be reached in-budget: they keep the manhattan-plus-penalty
    fallback exactly, with no BFS spent. Pure speed, no behavior.
    """
    near: set[int] = set()
    for fi, food in enumerate(foods):
        for ant in ants_list:
            if distance(ant, food) <= horizon:
                near.add(fi)
                break
    return near


def assign_food_targets(
    ants_list: list[Loc],
    foods: list[Loc],
    enemy_locs: list[Loc],
    distance: DistFn,
    rows: int,
    cols: int,
    passable: PassFn,
    destination: DestFn,
) -> dict[int, Loc]:
    """Denial claims plus greedy harvest, all ordered by BFS miles.

    Contested clusters take exactly DENIAL_CLAIMS ants on their
    miles-nearest foods (distinct ants and foods, miles first with
    manhattan and indices breaking ties); every other food draws
    one ant by global miles order. Open ground reproduces the
    champion greedy exactly; walls reroute claims to walkable food.
    """
    target: dict[int, Loc] = {}
    if not foods or not ants_list:
        return target
    cache: dict[Loc, dict[Loc, int]] = {}
    # Exact prefilter: foods beyond the horizon from every ant keep
    # the fallback value, so mark them sealed without a BFS.
    near = bfs_worthwhile(foods, ants_list, distance)
    for fi in range(len(foods)):
        if fi not in near:
            cache[foods[fi]] = {}
    claimed: set[int] = set()
    denied: set[int] = set()
    reach = set(ants_list) | set(enemy_locs)
    for group in denied_food_groups(foods, enemy_locs, distance, rows, cols):
        denied.update(group)
        picks = 0
        ordered = sorted(
            (
                food_mile(
                    ant,
                    foods[fi],
                    rows,
                    cols,
                    passable,
                    destination,
                    distance,
                    cache,
                    reach,
                ),
                distance(ant, foods[fi]),
                ai,
                fi,
            )
            for ai, ant in enumerate(ants_list)
            for fi in group
        )
        for _, _, ai, fi in ordered:
            if picks >= DENIAL_CLAIMS:
                break
            if ai not in target and fi not in claimed:
                target[ai] = foods[fi]
                claimed.add(fi)
                picks += 1
    # Race gate (fourmidable): per food, the nearest foe's walk. A
    # pair dies when the ant walks more than HEAD_START behind it;
    # denial clusters above already claimed as deliberate fights.
    foe_best: dict[int, int] = {}
    if enemy_locs:
        for fi, food_loc in enumerate(foods):
            if fi in denied:
                continue
            best = nearest_foe_mile(
                food_loc,
                rows,
                cols,
                passable,
                destination,
                distance,
                enemy_locs,
                cache,
                reach,
            )
            assert best is not None
            foe_best[fi] = best
    pairs: list[tuple[int, int, int, int]] = []
    for ai, ant_loc in enumerate(ants_list):
        for fi, food_loc in enumerate(foods):
            if fi in denied:
                continue
            mile = food_mile(
                ant_loc,
                food_loc,
                rows,
                cols,
                passable,
                destination,
                distance,
                cache,
                reach,
            )
            if fi in foe_best and mile > foe_best[fi] + FOOD_HEAD_START:
                continue
            pairs.append((mile, distance(ant_loc, food_loc), ai, fi))
    pairs.sort()
    for _, _, ai, fi in pairs:
        if ai not in target and fi not in claimed:
            target[ai] = foods[fi]
            claimed.add(fi)
    return target


def has_pack(
    ant_loc: Loc,
    ants_list: list[Loc],
    distance: DistFn,
    need: int = PACK_NEED,
    radius: int = PACK_RADIUS,
) -> bool:
    """Whether an ant holds need+ friends within radius steps."""
    found = 0
    for friend in ants_list:
        if friend == ant_loc:
            continue
        if distance(ant_loc, friend) <= radius:
            found += 1
            if found >= need:
                return True
    return False


def nearest_seek_enemy(
    ant_loc: Loc, enemy_locs: list[Loc], distance: DistFn
) -> Loc | None:
    """Nearest visible enemy within SEEK_RANGE steps, else None."""
    best: Loc | None = None
    best_d = SEEK_RANGE + 1
    for foe in enemy_locs:
        d = distance(ant_loc, foe)
        if d <= SEEK_RANGE and d < best_d:
            best_d = d
            best = foe
    return best


def contact_foe(
    dest: Loc,
    enemy_locs: list[Loc],
    sq_dist: Callable[[Loc, Loc], int],
    attack_r2: int,
) -> Loc | None:
    """Nearest enemy within attack range of a planned step, else None."""
    best: Loc | None = None
    best_d = attack_r2 + 1
    for foe in enemy_locs:
        d = sq_dist(dest, foe)
        if d <= attack_r2 and d < best_d:
            best_d = d
            best = foe
    return best


def joined_attackers(commitments: dict[int, Loc]) -> set[int]:
    """Ant indices released: foes with 2+ committers engage together."""
    counts: dict[Loc, int] = {}
    for foe in commitments.values():
        counts[foe] = counts.get(foe, 0) + 1
    return {ai for ai, foe in commitments.items() if counts[foe] >= 2}


def grinder_release(friends: int, enemies: int, my_army: int, enemy_army: int) -> bool:
    """Engage a friendless 1v1 contact only when the army leads."""
    return friends == 0 and enemies == 1 and my_army > enemy_army


def crowd_fearless(enemy_count: int, limit: int = CROWD_LIMIT) -> bool:
    """Press fearlessly while fewer than limit enemies show."""
    return enemy_count < limit


def _intercept_square(
    hill: Loc,
    enemy_locs: list[Loc],
    distance: DistFn,
    passable: PassFn,
    rows: int,
    cols: int,
) -> Loc | None:
    """Off-hill intercept: nearest passable square to the midpoint."""
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


class Softmax12:
    def __init__(self):
        self.visits: dict[tuple[int, int], int] = {}
        self.remembered_hills: set[tuple[int, int]] = set()
        self.prev_enemies: list[tuple[int, int]] = []

    def do_setup(self, ants: Ants):
        self.visits = {}
        self.remembered_hills = set()
        self.prev_enemies = []

    def do_turn(self, ants: Ants):
        # Softmax12: path-aware harvest (BFS miles) with the crowd
        # combat chain. Claims reroute around walls; packed hunters
        # press small fights fearlessly, join pairs, duel ahead-only
        # 1v1s, screen razers off threatened hills, and take equal
        # trades at 10 near friends. Muster, reinforce, explore, and
        # walk-off are champion.
        foods = ants.food()
        ants_list = ants.my_ants()
        my_set = set(ants_list)
        enemy_locs = [loc for loc, _ in ants.enemy_ants()]
        target = assign_food_targets(
            ants_list,
            foods,
            enemy_locs,
            ants.distance,
            ants.rows,
            ants.cols,
            ants.passable,
            ants.destination,
        )
        for hloc, _ in ants.enemy_hills():
            self.remembered_hills.add(hloc)
        for hloc in list(self.remembered_hills):
            if hloc in my_set:
                self.remembered_hills.discard(hloc)
        hills = sorted(self.remembered_hills)
        my_hills = ants.my_hills()
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
            return near >= EQUAL_TRADE_NEAR and friends + 1 >= enemies

        def first_step(
            start: tuple[int, int], goal: tuple[int, int], budget: int = 250
        ) -> str | None:
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

        def try_join(ant_loc: tuple[int, int], direction: str) -> bool:
            new_loc = ants.destination(ant_loc, direction)
            if (
                new_loc in destinations
                or not ants.passable(new_loc)
                or not ants.unoccupied(new_loc)
            ):
                return False
            foes = 0
            for e in enemy_locs:
                if sq_dist(new_loc, e) <= attack_r2:
                    foes += 1
                    if foes >= len(ants_list):
                        break
            if foes > 0:
                backup = 0
                for f in ants_list:
                    if f != ant_loc and sq_dist(new_loc, f) <= attack_r2:
                        backup += 1
                if backup + 1 < foes:
                    return False
            ants.issue_order((ant_loc, direction))
            destinations.add(new_loc)
            return True

        commitments: dict[int, tuple[int, int]] = {}
        if enemy_locs:
            for cai, cant in enumerate(ants_list):
                if target.get(cai) is not None:
                    continue
                chase = nearest_seek_enemy(cant, enemy_locs, ants.distance)
                if chase is None:
                    continue
                cstep = first_step(cant, chase)
                if cstep is None:
                    continue
                cloc = ants.destination(cant, cstep)
                cfoe = contact_foe(cloc, enemy_locs, sq_dist, attack_r2)
                if cfoe is not None:
                    commitments[cai] = cfoe
        joined = joined_attackers(commitments)

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
            if not moved and threatened:
                nearest = min(threatened, key=lambda h: ants.distance(ant_loc, h))
                if nearest in anchored:
                    inter = _intercept_square(
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
                foe = nearest_seek_enemy(ant_loc, enemy_locs, ants.distance)
                if foe is not None and not has_pack(ant_loc, ants_list, ants.distance):
                    pal = min(
                        (f for f in ants_list if f != ant_loc),
                        key=lambda f: ants.distance(ant_loc, f),
                        default=None,
                    )
                    if pal is not None:
                        pstep = first_step(ant_loc, pal)
                        if pstep is not None and try_step(ant_loc, pstep):
                            moved = True
                    foe = None
                if foe is not None:
                    step = first_step(ant_loc, foe)
                    if step is not None:
                        if crowd_fearless(len(enemy_locs), CROWD_LIMIT):
                            if try_step(ant_loc, step, safe=False):
                                moved = True
                        elif ai in joined:
                            if try_join(ant_loc, step):
                                moved = True
                        else:
                            nloc = ants.destination(ant_loc, step)
                            foes = 0
                            for e in enemy_locs:
                                if sq_dist(nloc, e) <= attack_r2:
                                    foes += 1
                                    if foes > 1:
                                        break
                            pals = 0
                            for f in ants_list:
                                if f != ant_loc and sq_dist(nloc, f) <= attack_r2:
                                    pals += 1
                                    break
                            if grinder_release(
                                pals, foes, len(ants_list), len(enemy_locs)
                            ):
                                if try_join(ant_loc, step):
                                    moved = True
                            elif try_step(ant_loc, step):
                                moved = True
            if not moved and hills:
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
                ordered = sorted(hills, key=lambda h: ants.distance(ant_loc, h))
                near = ordered[1] if len(ordered) > 1 else ordered[0]
                hstep = first_step(ant_loc, near)
                if hstep is not None and try_step(ant_loc, hstep):
                    moved = True
            if not moved:
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
            if ants.time_remaining() < 10:
                break
        hill_set = set(my_hills)
        for ant_loc in held:
            if ant_loc in hill_set and ants.time_remaining() >= 10:
                for direction in ("s", "e", "w", "n"):
                    if try_step(ant_loc, direction):
                        break


if __name__ == "__main__":
    try:
        import psyco

        psyco.full()
    except ImportError:
        pass

    try:
        Ants.run(Softmax12())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
