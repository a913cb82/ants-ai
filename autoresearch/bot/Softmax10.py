#!/usr/bin/env python
"""Softmax10: taxed harvest, pack combat, hill-ward drift.

Economy: Denial-style contested clusters draw exactly two claims;
every other food is harvested by taxed greedy -- each visible foe
within THREAT_R of a food adds THREAT_TAX to its distance, so lone
lurkers below the hard denial gate still reroute harvest instead
of feeding ambushes. No repo bot taxes food softly like this.

Combat chain: idle ants hunt visible foes within SEEK_RANGE only
with PACK_NEED friends inside PACK_RADIUS (packless ants rally to
their nearest friend); joint contacts on one foe engage together;
friendless 1v1 contacts engage only while the visible army leads;
equal trades need EQUAL_TRADE_NEAR friends nearby; hunters press
fearlessly while fewer than CROWD_LIMIT foes are visible.

Explore: least-visited first, tiebroken toward the nearest
remembered enemy hill, so idle ants drift at future razes. Guard,
muster, reinforce, and walk-off are standard.
"""

from collections import deque
from collections.abc import Callable

from ants import Ants

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]

CLUSTER_R = 8
DENIAL_ENEMIES = 3
DENIAL_CLAIMS = 2

# Threat tax: soft per-foe harvest penalty. Fires at a single
# lurker, where the hard denial gate (3+ foes) stays silent.
THREAT_R = 8
THREAT_TAX = 3

SEEK_RANGE = 8
PACK_NEED = 3
PACK_RADIUS = 10
EQUAL_TRADE_NEAR = 10
CROWD_LIMIT = 10

_COMPASS = ("n", "e", "s", "w")
_STEP = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}


def threat_count(food: Loc, foes: list[Loc], distance: DistFn) -> int:
    """Visible foes within THREAT_R of a food square."""
    n = 0
    for foe in foes:
        if distance(food, foe) <= THREAT_R:
            n += 1
    return n


def taxed_distance(ant: Loc, food: Loc, foes: list[Loc], distance: DistFn) -> int:
    """Harvest cost: walk distance plus THREAT_TAX per lurking foe."""
    return distance(ant, food) + THREAT_TAX * threat_count(food, foes, distance)


def _clusters(foods: list[Loc], distance: DistFn) -> list[int]:
    """Union-find roots: foods within CLUSTER_R share a root."""
    n = len(foods)
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i in range(n):
        for j in range(i + 1, n):
            if distance(foods[i], foods[j]) <= CLUSTER_R:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)
    return [find(i) for i in range(n)]


def denied_food_groups(
    foods: list[Loc],
    enemy_locs: list[Loc],
    distance: DistFn,
    rows: int,
    cols: int,
) -> list[list[int]]:
    """Food-index clusters with DENIAL_ENEMIES+ foes nearby."""
    _ = (rows, cols)
    if not foods or len(enemy_locs) < DENIAL_ENEMIES:
        return []
    roots = _clusters(foods, distance)
    tally: dict[int, int] = {}
    for foe in enemy_locs:
        seen: set[int] = set()
        for i, food in enumerate(foods):
            if distance(foe, food) <= CLUSTER_R:
                seen.add(roots[i])
        for root in seen:
            tally[root] = tally.get(root, 0) + 1
    hot = {r for r, c in tally.items() if c >= DENIAL_ENEMIES}
    groups: dict[int, list[int]] = {}
    for i, root in enumerate(roots):
        if root in hot:
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
    """Two claims per contested cluster, taxed greedy elsewhere."""
    target: dict[int, Loc] = {}
    if not foods or not ants_list:
        return target
    claimed: set[int] = set()
    off_limits: set[int] = set()
    for group in denied_food_groups(foods, enemy_locs, distance, rows, cols):
        off_limits.update(group)
        takes = 0
        ranked = sorted(
            (distance(ant, foods[fi]), ai, fi)
            for ai, ant in enumerate(ants_list)
            for fi in group
        )
        for _, ai, fi in ranked:
            if takes >= DENIAL_CLAIMS:
                break
            if ai not in target and fi not in claimed:
                target[ai] = foods[fi]
                claimed.add(fi)
                takes += 1
    tax = [threat_count(food, enemy_locs, distance) for food in foods]
    pairs: list[tuple[int, int, int]] = []
    for ai, ant in enumerate(ants_list):
        if ai in target:
            continue
        for fi, food in enumerate(foods):
            if fi in off_limits or fi in claimed:
                continue
            pairs.append((distance(ant, food) + THREAT_TAX * tax[fi], ai, fi))
    pairs.sort()
    for _, ai, fi in pairs:
        if ai not in target and fi not in claimed:
            target[ai] = foods[fi]
            claimed.add(fi)
    return target


def explore_order(
    loc: Loc,
    visits: dict[Loc, int],
    hills: set[Loc],
    distance: DistFn,
    rows: int = 0,
    cols: int = 0,
) -> list[str]:
    """Compass by (visits, hill distance): fresh squares first,
    ties drifting at the nearest remembered enemy hill."""
    scored = []
    for idx, d in enumerate(_COMPASS):
        dr, dc = _STEP[d]
        nxt = (loc[0] + dr, loc[1] + dc)
        if rows and cols:
            nxt = (nxt[0] % rows, nxt[1] % cols)
        hill_d = 0
        if hills:
            hill_d = min(distance(nxt, h) for h in hills)
        scored.append((visits.get(nxt, 0), hill_d, idx, d))
    scored.sort()
    return [d for _, _, _, d in scored]


def has_pack(
    ant_loc: Loc,
    ants_list: list[Loc],
    distance: DistFn,
    need: int = PACK_NEED,
    radius: int = PACK_RADIUS,
) -> bool:
    """PACK_NEED+ friends within PACK_RADIUS steps (self excluded)."""
    found = 0
    for friend in ants_list:
        if friend != ant_loc and distance(ant_loc, friend) <= radius:
            found += 1
            if found >= need:
                return True
    return False


def nearest_seek_enemy(
    ant_loc: Loc, enemy_locs: list[Loc], distance: DistFn
) -> Loc | None:
    """Nearest foe within SEEK_RANGE, else None (list-order ties)."""
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
    """Nearest foe in attack range of a planned step, else None."""
    best: Loc | None = None
    best_d = attack_r2 + 1
    for foe in enemy_locs:
        d = sq_dist(dest, foe)
        if d <= attack_r2 and d < best_d:
            best_d = d
            best = foe
    return best


def joined_attackers(commitments: dict[int, Loc]) -> set[int]:
    """Ants whose contacted foe drew 2+ commitments engage together."""
    counts: dict[Loc, int] = {}
    for foe in commitments.values():
        counts[foe] = counts.get(foe, 0) + 1
    return {ai for ai, foe in commitments.items() if counts[foe] >= 2}


def grinder_release(friends: int, enemies: int, my_army: int, enemy_army: int) -> bool:
    """Friendless 1v1 contact engages only while the army leads."""
    return friends == 0 and enemies == 1 and my_army > enemy_army


def crowd_fearless(enemy_count: int, limit: int = CROWD_LIMIT) -> bool:
    """Press small fights fearlessly; keep safety in crowds."""
    return enemy_count < limit


def press_donation(
    dest: Loc,
    ant_loc: Loc,
    ants_list: list[Loc],
    enemy_locs: list[Loc],
    sq_dist: Callable[[Loc, Loc], int],
    attack_r2: int,
) -> bool:
    """Whether a fearless step donates: 2+ contacted foes outnumber
    the ant plus its backup in attack range. Single contacts and
    backed trades press ahead; only unbacked crowd donations hold."""
    foes = sum(1 for e in enemy_locs if sq_dist(dest, e) <= attack_r2)
    if foes < 2:
        return False
    backup = sum(1 for f in ants_list if f != ant_loc and sq_dist(dest, f) <= attack_r2)
    return backup + 1 < foes


def _midpoint_screen(
    hill: Loc,
    enemy_locs: list[Loc],
    distance: DistFn,
    passable: Callable[[Loc], bool],
    rows: int,
    cols: int,
) -> Loc | None:
    """Nearest passable square to the hill-foe midpoint."""
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


class Softmax10:
    def __init__(self):
        self.visits: dict[tuple[int, int], int] = {}
        self.remembered_hills: set[tuple[int, int]] = set()
        self.prev_enemies: list[tuple[int, int]] = []

    def do_setup(self, ants: Ants):
        self.visits = {}
        self.remembered_hills = set()
        self.prev_enemies = []

    def do_turn(self, ants: Ants):
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
                for d in _COMPASS:
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
                    inter = _midpoint_screen(
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
                        pressed = False
                        if crowd_fearless(len(enemy_locs)):
                            nloc = ants.destination(ant_loc, step)
                            if not press_donation(
                                nloc,
                                ant_loc,
                                ants_list,
                                enemy_locs,
                                sq_dist,
                                attack_r2,
                            ) and try_step(ant_loc, step, safe=False):
                                moved = True
                                pressed = True
                        if not pressed:
                            if ai in joined:
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
                for direction in explore_order(
                    ant_loc,
                    self.visits,
                    self.remembered_hills,
                    ants.distance,
                    ants.rows,
                    ants.cols,
                ):
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
        Ants.run(Softmax10())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
