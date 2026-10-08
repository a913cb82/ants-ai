#!/usr/bin/env python
"""Greedy13: wedge-seek assaults with toll-taxed harvest.

The spine is the proven majority doctrine: denial economy on
contested food clusters, corner-post guards with halfway screens
for threatened home hills, pack-gated seekers, joined-pair even
trades, lone duels only while strictly ahead of the strongest
rival, equal trades backed by ten near friends, hill assaults
only at twice the campers, testudo home when outnumbered,
stand-off harvest (ants gather by adjacency; the engine ignores
moves onto food, so paths never route through it), frontier
rotated explore, walk-off so hills stay spawnable, and hill
memory with visible-absence forgetting (a remembered hill seen
empty is dropped, so no raid marches on a grave). Food,
guard, muster, testudo, and explore steps are
safety-filtered; packed seekers press small fights fearlessly
while fewer than CROWD_LIMIT enemies are visible, with full
safety in crowds.

Four new rules make this entry a wedge, not a copy:

(a) wedge seek: a seeker inside SEEK_RANGE does not chase the
    foe nearest itself. It marches on the foe nearest the army
    centroid, so scattered seekers converge into a wedge on one
    point instead of scattering into losing 1v1s;

(b) toll harvest: a food claim standing inside a locally lost
    contact -- strictly more visible foes than friends within
    TOLL_R of the meal -- is ceded outright, so no ant treks
    into a losing fight for a meal the safety filter would
    refuse at the last step anyway;

(c) frontier explore: the least-visited fallback prefers the
    darkest ground (most unseen within radius 3), so spares push
    into the dark instead of re-trampling mapped ground;

(d) grave check: a remembered enemy hill seen empty is
    forgotten at once, so no raid marches cross-map onto a
    grave (re-remembered the moment it is sighted again).
"""

from collections import deque
from collections.abc import Callable

from ants import Ants

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]

SEEK_RANGE = 8
PACK_NEED = 3
PACK_RADIUS = 10
EVEN_TRADE_NEAR = 10
CLUSTER_R = 8
DENIAL_FOES = 3
DENIAL_CLAIMS = 2
GUARD_RANGE = 10
CLOSING_RANGE = 16
PATH_BUDGET = 800
CAMP_RANGE = 12
ASSAULT_MARGIN = 2
TESTUDO_REACH = 20
TOLL_R = 4
CROWD_LIMIT = 10
DIRS = ("n", "e", "s", "w")


def has_majority(mine: int, foes: int) -> bool:
    """Attack only while strictly ahead; parity holds. Pure."""
    return mine > 0 and mine > foes


def strongest_rival(enemy_ants: list[tuple[Loc, int]]) -> int:
    """Biggest single visible rival army, by owner. Pure."""
    counts: dict[int, int] = {}
    for _, owner in enemy_ants:
        counts[owner] = counts.get(owner, 0) + 1
    return max(counts.values(), default=0)


def crowd_fearless(visible_foes: int, limit: int = CROWD_LIMIT) -> bool:
    """Press small fights: fearless below the crowd limit. Pure."""
    return visible_foes < limit


def takeable(mine: int, camped: int, margin: int = ASSAULT_MARGIN) -> bool:
    """A hill raids when the army outnumbers its campers margin:1.

    Empty hills always raid; a camped hill needs twice the camp.
    Pure integer compare, no side effects.
    """
    return mine >= margin * camped


def unseen_near(
    loc: Loc,
    visits: dict[Loc, int],
    rows: int,
    cols: int,
    radius: int = 3,
) -> int:
    """Unvisited squares within toroid-manhattan radius of loc.

    Measures how dark the ground past a candidate step is; the
    wedge pushes into the dark instead of re-trampling mapped
    ground. Pure: reads visits, no side effects.
    """
    dark = 0
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            if abs(dr) + abs(dc) > radius:
                continue
            if visits.get(((loc[0] + dr) % rows, (loc[1] + dc) % cols), 0) == 0:
                dark += 1
    return dark


def explore_dirs(ant: Loc, visits: dict[Loc, int], rows: int, cols: int) -> list[str]:
    """Fallback order for one ant: least-visited first, then dark.

    Least-visited stays primary so spread is never sacrificed
    for curiosity; among equally fresh squares the frontier
    (most unseen within radius 3) leads. Per-ant rotation
    breaks the remaining ties so simultaneous explorers fan
    out. Pure: no board state, no side effects.
    """
    aim = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}
    rot = (ant[0] + ant[1]) % 4
    order = DIRS[rot:] + DIRS[:rot]

    def dest(direction: str) -> Loc:
        step = aim[direction]
        return ((ant[0] + step[0]) % rows, (ant[1] + step[1]) % cols)

    return sorted(
        order,
        key=lambda d: (
            visits.get(dest(d), 0),
            -unseen_near(dest(d), visits, rows, cols),
        ),
    )


def wedge_mark(
    ant: Loc,
    mine: list[Loc],
    foes: list[Loc],
    distance: DistFn,
    seek_range: int = SEEK_RANGE,
) -> Loc | None:
    """The foe nearest the army centroid among foes in range.

    Only foes within seek_range of the ant qualify, so distant
    ants never trek across the map; among those, the wedge
    converges on the one closest to the mass of the army.
    Ties keep list order, so the branch is deterministic. Pure.
    """
    if not mine:
        return None
    heart: Loc = (
        sum(a[0] for a in mine) // len(mine),
        sum(a[1] for a in mine) // len(mine),
    )
    best: Loc | None = None
    best_d = 0
    for foe in foes:
        if distance(ant, foe) > seek_range:
            continue
        scored = distance(heart, foe)
        if best is None or scored < best_d:
            best = foe
            best_d = scored
    return best


def toll_lost(
    meal: Loc,
    claimant: Loc,
    mine: list[Loc],
    foes: list[Loc],
    distance: DistFn,
    toll_r: int = TOLL_R,
) -> bool:
    """True when the meal stands inside a locally lost contact.

    Counts visible foes against visible friends (claimant
    included) within toll_r of the meal; strictly more foes
    means the trek dies at the safety filter, so the claim is
    ceded before any ant wastes the trip. Quiet meals never
    lose. Pure: no board state, no side effects.
    """
    bad = sum(1 for e in foes if distance(meal, e) <= toll_r)
    if bad == 0:
        return False
    pals = sum(1 for f in mine if distance(meal, f) <= toll_r)
    if distance(meal, claimant) > toll_r:
        pals += 1
    return bad > pals


class Greedy13:
    def __init__(self):
        self.visits: dict[tuple[int, int], int] = {}
        self.hills: set[tuple[int, int]] = set()
        self.prev_foes: list[tuple[int, int]] = []

    def do_setup(self, ants: Ants):
        self.visits = {}
        self.hills = set()
        self.prev_foes = []

    def do_turn(self, ants: Ants):
        mine = ants.my_ants()
        seen = ants.enemy_ants()
        foes = [loc for loc, _ in seen]
        foods = ants.food()
        my_set = set(mine)
        seen_hills = ants.enemy_hills()
        for hloc, _ in seen_hills:
            self.hills.add(hloc)
        live = {hloc for hloc, _ in seen_hills}
        for hloc in list(self.hills):
            if hloc in my_set or hloc not in live and ants.visible(hloc):
                self.hills.discard(hloc)
        hills = sorted(self.hills)
        home = ants.my_hills()
        attack_r2 = ants.attackradius2 or 5
        rows, cols = ants.rows, ants.cols
        path_budget = 200 if ants.time_remaining() < 400 else PATH_BUDGET

        def sq(a: tuple[int, int], b: tuple[int, int]) -> int:
            dr = abs(a[0] - b[0])
            dr = min(dr, rows - dr) if rows else dr
            dc = abs(a[1] - b[1])
            dc = min(dc, cols - dc) if cols else dc
            return dr * dr + dc * dc

        def safe_step(nloc: tuple[int, int], self_loc: tuple[int, int]) -> bool:
            enemies = 0
            for e in foes:
                if sq(nloc, e) <= attack_r2:
                    enemies += 1
                    if enemies >= len(mine):
                        break
            if enemies == 0:
                return True
            friends = 0
            near = 0
            for f in mine:
                if f == self_loc:
                    continue
                if sq(nloc, f) <= attack_r2:
                    friends += 1
                if ants.distance(nloc, f) <= EVEN_TRADE_NEAR:
                    near += 1
            if friends + 1 > enemies:
                return True
            return near >= EVEN_TRADE_NEAR and friends + 1 >= enemies

        food_set = set(foods)

        def first_step(
            start: tuple[int, int],
            goal: tuple[int, int],
            budget: int = PATH_BUDGET,
        ) -> str | None:
            if start == goal:
                return None
            if not ants.passable(goal) or goal in food_set:
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
                    if nxt in parent or not ants.passable(nxt) or nxt in food_set:
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

        def approach_food(
            start: tuple[int, int], meal: tuple[int, int], budget: int = PATH_BUDGET
        ) -> str | None:
            if ants.distance(start, meal) <= 1:
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
                    if nxt in parent or not ants.passable(nxt) or nxt in food_set:
                        continue
                    parent[nxt] = (cur, d)
                    if ants.distance(nxt, meal) <= 1:
                        node = nxt
                        while parent[node][0] != start:
                            node = parent[node][0]
                        return parent[node][1]
                    queue.append(nxt)
            return None

        def packed(ant: tuple[int, int]) -> bool:
            found = 0
            for f in mine:
                if f != ant and ants.distance(ant, f) <= PACK_RADIUS:
                    found += 1
                    if found >= PACK_NEED:
                        return True
            return False

        def contact_at(dest: tuple[int, int]) -> tuple[int, int] | None:
            best: tuple[int, int] | None = None
            best_d = attack_r2 + 1
            for e in foes:
                d = sq(dest, e)
                if d <= attack_r2 and (best is None or d < best_d):
                    best_d = d
                    best = e
            return best

        def halfway(hill: tuple[int, int]) -> tuple[int, int] | None:
            if not foes or rows <= 0 or cols <= 0:
                return None
            foe = min(foes, key=lambda e: ants.distance(hill, e))
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
            if ants.passable(mid) and mid not in food_set:
                return mid
            seen_mid = {mid}
            queue: deque[tuple[int, int]] = deque([mid])
            while queue:
                cur = queue.popleft()
                for step in ((-1, 0), (0, 1), (1, 0), (0, -1)):
                    nxt = ((cur[0] + step[0]) % rows, (cur[1] + step[1]) % cols)
                    if nxt in seen_mid:
                        continue
                    seen_mid.add(nxt)
                    if ants.passable(nxt) and nxt not in food_set:
                        return nxt
                    queue.append(nxt)
            return None

        rival = strongest_rival(seen)
        advance = has_majority(len(mine), rival)
        standing = len(mine) > 0 and len(mine) >= rival
        denial_claims = 0 if len(mine) < rival else DENIAL_CLAIMS
        claims: dict[int, tuple[int, int]] = {}
        if foods and mine:
            n = len(foods)
            parent_u = list(range(n))

            def find(a: int) -> int:
                while parent_u[a] != a:
                    parent_u[a] = parent_u[parent_u[a]]
                    a = parent_u[a]
                return a

            for i in range(n):
                for j in range(i + 1, n):
                    if ants.distance(foods[i], foods[j]) <= CLUSTER_R:
                        ri, rj = find(i), find(j)
                        if ri != rj:
                            parent_u[max(ri, rj)] = min(ri, rj)
            roots = [find(i) for i in range(n)]
            heat: dict[int, int] = {}
            for e in foes:
                seen_roots: set[int] = set()
                for i, f in enumerate(foods):
                    if ants.distance(e, f) <= CLUSTER_R:
                        seen_roots.add(roots[i])
                for r in seen_roots:
                    heat[r] = heat.get(r, 0) + 1
            hot = {r for r, c in heat.items() if c >= DENIAL_FOES}
            taken_food: set[int] = set()
            denied: set[int] = set()
            members: dict[int, list[int]] = {}
            for i, r in enumerate(roots):
                if r in hot:
                    members.setdefault(r, []).append(i)
                    denied.add(i)
            for group in members.values():
                cand = sorted(
                    (ants.distance(a, foods[fi]), ai, fi)
                    for ai, a in enumerate(mine)
                    for fi in group
                )
                picks = 0
                for _, ai, fi in cand:
                    if picks >= denial_claims:
                        break
                    if ai not in claims and fi not in taken_food:
                        claims[ai] = foods[fi]
                        taken_food.add(fi)
                        picks += 1
            pairs = sorted(
                (ants.distance(a, f), ai, fi)
                for ai, a in enumerate(mine)
                for fi, f in enumerate(foods)
            )
            for _, ai, fi in pairs:
                if fi in denied:
                    continue
                if ai not in claims and fi not in taken_food:
                    claims[ai] = foods[fi]
                    taken_food.add(fi)
            for ai in list(claims):
                dish = claims[ai]
                if toll_lost(dish, mine[ai], mine, foes, ants.distance):
                    del claims[ai]

        leftovers = self.prev_foes[:]
        shut: dict[tuple[int, int], tuple[int, int]] = {}
        for cur in foes:
            match = None
            match_d = 2
            for p in leftovers:
                d = ants.distance(cur, p)
                if d < match_d:
                    match_d = d
                    match = p
            if match is not None:
                leftovers.remove(match)
                shut[cur] = match
        self.prev_foes = foes

        def closing(cur: tuple[int, int], hill: tuple[int, int]) -> bool:
            prev = shut.get(cur)
            return prev is not None and ants.distance(prev, hill) > ants.distance(
                cur, hill
            )

        threatened = [
            h
            for h in home
            if any(
                ants.distance(h, e) <= GUARD_RANGE
                or (ants.distance(h, e) <= CLOSING_RANGE and closing(e, h))
                for e in foes
            )
        ]

        march_order: list[tuple[int, int]] = []
        camped_of: dict[tuple[int, int], int] = {}
        if hills and standing:
            march_order = sorted(
                hills,
                key=lambda h: sum(ants.distance(a, h) for a in mine),
            )
            for target in march_order:
                camped_of[target] = sum(
                    1 for e in foes if ants.distance(e, target) <= CAMP_RANGE
                )
        commits: dict[int, tuple[int, int]] = {}
        if foes:
            for cai, cant in enumerate(mine):
                if claims.get(cai) is not None:
                    continue
                chase = wedge_mark(cant, mine, foes, ants.distance)
                if chase is None:
                    continue
                cstep = first_step(cant, chase, path_budget)
                if cstep is None:
                    continue
                touched = contact_at(ants.destination(cant, cstep))
                if touched is not None:
                    commits[cai] = touched
        counts: dict[tuple[int, int], int] = {}
        for foe_loc in commits.values():
            counts[foe_loc] = counts.get(foe_loc, 0) + 1
        joined = {ai for ai, foe_loc in commits.items() if counts[foe_loc] >= 2}

        destinations: set[tuple[int, int]] = set()
        held: list[tuple[int, int]] = []
        anchored: set[tuple[int, int]] = set()

        def issue(ant_loc: tuple[int, int], direction: str, check: bool) -> bool:
            nloc = ants.destination(ant_loc, direction)
            if (
                nloc in destinations
                or not ants.passable(nloc)
                or not ants.unoccupied(nloc)
            ):
                return False
            if check and not safe_step(nloc, ant_loc):
                return False
            ants.issue_order((ant_loc, direction))
            destinations.add(nloc)
            return True

        def issue_join(ant_loc: tuple[int, int], direction: str) -> bool:
            nloc = ants.destination(ant_loc, direction)
            if (
                nloc in destinations
                or not ants.passable(nloc)
                or not ants.unoccupied(nloc)
            ):
                return False
            bad = sum(1 for e in foes if sq(nloc, e) <= attack_r2)
            if bad > 0:
                backup = sum(
                    1 for f in mine if f != ant_loc and sq(nloc, f) <= attack_r2
                )
                if backup + 1 < bad:
                    return False
            ants.issue_order((ant_loc, direction))
            destinations.add(nloc)
            return True

        for ai, ant_loc in enumerate(mine):
            self.visits[ant_loc] = self.visits.get(ant_loc, 0) + 1
            moved = False
            meal: Loc | None = claims.get(ai)
            if meal is not None:
                if ants.distance(ant_loc, meal) <= 1:
                    if safe_step(ant_loc, ant_loc):
                        moved = True
                else:
                    step = approach_food(ant_loc, meal, path_budget)
                    if step is not None and issue(ant_loc, step, True):
                        moved = True
            if not moved and threatened:
                close = min(threatened, key=lambda h: ants.distance(ant_loc, h))
                if ant_loc != close and ants.distance(ant_loc, close) == 1:
                    moved = True
                else:
                    if close in anchored:
                        post = halfway(close)
                        if post is None:
                            post = min(foes, key=lambda e: ants.distance(close, e))
                        step = first_step(ant_loc, post, path_budget)
                    else:
                        anchored.add(close)
                        step = first_step(ant_loc, close, path_budget)
                    if step is not None and issue(ant_loc, step, True):
                        moved = True
            if not moved and foes:
                mark = wedge_mark(ant_loc, mine, foes, ants.distance)
                if mark is not None and not packed(ant_loc):
                    pal = min(
                        (f for f in mine if f != ant_loc),
                        key=lambda f: ants.distance(ant_loc, f),
                        default=None,
                    )
                    if pal is not None:
                        pstep = first_step(ant_loc, pal, path_budget)
                        if pstep is not None and issue(ant_loc, pstep, True):
                            moved = True
                    mark = None
                if mark is not None:
                    step = first_step(ant_loc, mark, path_budget)
                    if step is not None:
                        if crowd_fearless(len(foes)):
                            if issue(ant_loc, step, False):
                                moved = True
                        elif ai in joined:
                            if issue_join(ant_loc, step):
                                moved = True
                        else:
                            nloc = ants.destination(ant_loc, step)
                            foes_on = sum(1 for e in foes if sq(nloc, e) <= attack_r2)
                            pals_on = sum(
                                1
                                for f in mine
                                if f != ant_loc and sq(nloc, f) <= attack_r2
                            )
                            if (
                                pals_on == 0
                                and foes_on == 1
                                and advance
                                and issue_join(ant_loc, step)
                            ) or issue(ant_loc, step, True):
                                moved = True
            if not moved and hills:
                marched = False
                if march_order:
                    for target in march_order:
                        if not takeable(len(mine), camped_of[target]):
                            continue
                        step = first_step(ant_loc, target, path_budget)
                        if step is not None and issue(ant_loc, step, True):
                            moved = True
                            marched = True
                        break
                if not marched and home:
                    keep: Loc | None = min(
                        home, key=lambda h: ants.distance(ant_loc, h)
                    )
                    if ants.distance(ant_loc, keep) > TESTUDO_REACH:
                        keep = None
                    if keep is not None:
                        step = first_step(ant_loc, keep, path_budget)
                        if step is not None and issue(ant_loc, step, True):
                            moved = True
            if not moved:
                for direction in explore_dirs(ant_loc, self.visits, rows, cols):
                    if issue(ant_loc, direction, True):
                        moved = True
                        break
            if not moved:
                held.append(ant_loc)
            if ants.time_remaining() < 10:
                break
        hill_set = set(home)
        for ant_loc in held:
            if ant_loc in hill_set and ants.time_remaining() >= 10:
                for direction in ("s", "e", "w", "n"):
                    if issue(ant_loc, direction, True):
                        break


if __name__ == "__main__":
    try:
        import psyco

        psyco.full()
    except ImportError:
        pass

    try:
        Ants.run(Greedy13())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
