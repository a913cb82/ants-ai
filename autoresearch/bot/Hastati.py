#!/usr/bin/env python
"""Hastati: straggler-cutting skirmishers with a predictive screen.

The pack does not chase whatever is nearest. Once per turn it
picks the STRAGGLER -- the visible enemy with the fewest enemy
neighbours in attack range of itself (ties go to the foe nearest
any ant) -- and every packed seeker converges on that one foe,
so the pack cuts loners instead of feeding the enemy's main
stack. A seeker whose straggler is out of its own range falls
back to its nearest foe, and a seeker whose straggler is walled
behind water hunts its nearest reachable foe instead of idling;
seekers with nothing in range do not seek at all. The pin is sticky: last turn's victim holds while
it is still visible and nothing strictly lonelier appears, so
the pack finishes kills instead of flapping between equal loners.

Advances are never fearless: champion safety holds on every
step (strict superiority, equal trades only with 10 near
friends), except committed pairs (2+ ants stepping into contact
with the SAME foe this turn) may join with equal trades, and a
friendless 1v1 engages only while the visible army leads.

Extra guards screen the razer's PREDICTED next square (one-step
heading extrapolation from last turn's positions, static
midpoint for new spawns) instead of the static midpoint, so the
screen leads the target and the hill stays spawnable.

Food is champion greedy, except clusters contested by 3+
visible enemies draw exactly 2 claimants on distinct foods and
their other foods stay unclaimed. Packless seekers pack up one
safe step toward their nearest friend instead of advancing.
Idle ants push the unseen edge by BFS before diffusing over
least-visited ground, so corridors get walked early.
"""

from collections import deque
from collections.abc import Callable

from ants import Ants

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]
SqDistFn = Callable[[Loc, Loc], int]
PassFn = Callable[[Loc], bool]

SEEK_RANGE = 8
CLUSTER_R = 8
DENIAL_ENEMIES = 3
DENIAL_CLAIMS = 2
EQUAL_TRADE_NEAR = 10
PACK_NEED = 3
PACK_RADIUS = 10
_CELL = CLUSTER_R + 1


def pick_straggler(
    enemy_locs: list[Loc],
    ants_list: list[Loc],
    distance: DistFn,
    sq_dist: SqDistFn,
    attack_r2: int,
    seek_range: int = SEEK_RANGE,
    sticky: Loc | None = None,
) -> Loc | None:
    """The most isolated enemy in range of any ant, else None.

    Candidates are foes within seek_range steps of at least one
    ant. Each candidate scores its support: other enemies within
    attack range of the foe itself (own ants never count). The
    least-supported foe wins; ties go to the foe nearest any ant,
    list order breaking exact ties so the pick is deterministic.
    The sticky pin holds across turns: last turn's victim is kept
    while it is still visible, still in range, and no strictly
    lonelier foe exists -- so the pack finishes its kill instead
    of flapping between equal loners. Pure: no side effects.
    """
    best: Loc | None = None
    best_key: tuple[int, int] | None = None
    keys: dict[Loc, tuple[int, int]] = {}
    for foe in enemy_locs:
        nearest = None
        for ant in ants_list:
            d = distance(ant, foe)
            if nearest is None or d < nearest:
                nearest = d
        if nearest is None or nearest > seek_range:
            continue
        support = 0
        for other in enemy_locs:
            if other != foe and sq_dist(foe, other) <= attack_r2:
                support += 1
        key = (support, nearest)
        keys[foe] = key
        if best_key is None or key < best_key:
            best_key = key
            best = foe
    if (
        sticky is not None
        and sticky in keys
        and best_key is not None
        and keys[sticky][0] <= best_key[0]
    ):
        return sticky
    return best


def nearest_seek_enemy(
    ant_loc: Loc, enemy_locs: list[Loc], distance: DistFn
) -> Loc | None:
    """Nearest visible enemy within SEEK_RANGE steps, else None.

    Ties keep the first enemy in list order so the branch is
    deterministic. Pure: no board state, no side effects.
    """
    best: Loc | None = None
    best_d = SEEK_RANGE + 1
    for foe in enemy_locs:
        d = distance(ant_loc, foe)
        if d <= SEEK_RANGE and d < best_d:
            best_d = d
            best = foe
    return best


def seek_target(
    ant_loc: Loc,
    straggler: Loc | None,
    enemy_locs: list[Loc],
    distance: DistFn,
) -> Loc | None:
    """This ant's hunt target: the straggler when in its own range.

    The pack converges when co-located; a lone ant whose
    straggler is far away still hunts its own nearest foe instead
    of marching across the map or standing idle. Pure.
    """
    if straggler is not None and distance(ant_loc, straggler) <= SEEK_RANGE:
        return straggler
    return nearest_seek_enemy(ant_loc, enemy_locs, distance)


def predict_square(cur: Loc, prev: Loc | None, rows: int, cols: int) -> Loc:
    """Where a foe is headed: one toroidal step along its heading.

    The heading is the minimal toroidal delta from prev to cur,
    clamped to a unit step; a stationary or unknown foe predicts
    its own square. Pure: no board state, no side effects.
    """
    if prev is None or prev == cur or rows <= 0 or cols <= 0:
        return cur
    dr = cur[0] - prev[0]
    if dr > rows // 2:
        dr -= rows
    elif dr < -(rows // 2):
        dr += rows
    dc = cur[1] - prev[1]
    if dc > cols // 2:
        dc -= cols
    elif dc < -(cols // 2):
        dc += cols
    step_r = 0 if dr == 0 else (1 if dr > 0 else -1)
    step_c = 0 if dc == 0 else (1 if dc > 0 else -1)
    return ((cur[0] + step_r) % rows, (cur[1] + step_c) % cols)


def intercept_square(
    hill: Loc,
    aim: Loc,
    passable: PassFn,
    rows: int,
    cols: int,
) -> Loc | None:
    """Off-hill intercept: nearest passable square to the midpoint.

    Screens the aim square (usually the razer's predicted next
    position) instead of piling onto the hill: halve the toroidal
    approach and return the nearest passable square to that
    midpoint (the midpoint itself when open). No passable square
    on the whole board returns None. Pure.
    """
    if rows <= 0 or cols <= 0:
        return None
    dr = aim[0] - hill[0]
    if dr > rows // 2:
        dr -= rows
    elif dr < -(rows // 2):
        dr += rows
    dc = aim[1] - hill[1]
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


def edge_step(
    start: Loc,
    seen: set[Loc],
    passable: PassFn,
    destination: Callable[[Loc, str], Loc],
    budget: int = 300,
) -> str | None:
    """First step of the shortest passable path to the nearest unseen square.

    Pushes the unseen edge instead of diffusing over visited ground,
    so maze corridors get walked early and distant food shows sooner.
    None when everything in budget is explored. Pure.
    """
    parent: dict[Loc, tuple[Loc, str]] = {start: (start, "")}
    queue: deque[Loc] = deque([start])
    expanded = 0
    while queue and expanded < budget:
        cur = queue.popleft()
        expanded += 1
        for d in ("n", "e", "s", "w"):
            nxt = destination(cur, d)
            if nxt in parent or not passable(nxt):
                continue
            parent[nxt] = (cur, d)
            if nxt not in seen:
                node = nxt
                while parent[node][0] != start:
                    node = parent[node][0]
                return parent[node][1]
            queue.append(nxt)
    return None


def has_pack(
    ant_loc: Loc,
    ants_list: list[Loc],
    distance: DistFn,
    need: int = PACK_NEED,
    radius: int = PACK_RADIUS,
) -> bool:
    """Whether an ant holds a pack: need+ friends within radius steps.

    The ant itself never counts toward its own pack. Pure.
    """
    found = 0
    for friend in ants_list:
        if friend == ant_loc:
            continue
        if distance(ant_loc, friend) <= radius:
            found += 1
            if found >= need:
                return True
    return False


def contact_foe(
    dest: Loc, enemy_locs: list[Loc], sq_dist: SqDistFn, attack_r2: int
) -> Loc | None:
    """Nearest enemy within attack range of a planned step, else None.

    Ties keep the first enemy in list order. Pure.
    """
    best: Loc | None = None
    best_d = attack_r2 + 1
    for foe in enemy_locs:
        d = sq_dist(dest, foe)
        if d <= attack_r2 and d < best_d:
            best_d = d
            best = foe
    return best


def joined_attackers(commitments: dict[int, Loc]) -> set[int]:
    """Ant indices released to attack: foes with 2+ committers.

    Each commitment maps one ant index to the foe its planned step
    would contact. A foe drawing two or more commitments releases
    every committer; lone committers fall back to safety. Pure.
    """
    counts: dict[Loc, int] = {}
    for foe in commitments.values():
        counts[foe] = counts.get(foe, 0) + 1
    return {ai for ai, foe in commitments.items() if counts[foe] >= 2}


def grinder_release(friends: int, enemies: int, my_army: int, enemy_army: int) -> bool:
    """Engage a friendless 1v1 contact only when the army leads."""
    return friends == 0 and enemies == 1 and my_army > enemy_army


def _scan_board(
    foods: list[Loc], enemy_locs: list[Loc], rows: int, cols: int
) -> tuple[list[int], dict[int, int]]:
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


<<<<<<<< HEAD:autoresearch/bot/Crowd.py
# define a class with a do_turn method
# the Ants.run method will parse and update bot input
# it will also run the do_turn method for us
class Crowd:
========
class Hastati:
>>>>>>>> tree/legion-3:autoresearch/bot/Hastati.py
    def __init__(self):
        self.visits: dict[tuple[int, int], int] = {}
        self.seen: set[tuple[int, int]] = set()
        self.remembered_hills: set[tuple[int, int]] = set()
        self.prev_enemies: list[tuple[int, int]] = []
        self.pin: tuple[int, int] | None = None

    def do_setup(self, ants: Ants):
        self.visits = {}
        self.seen = set()
        self.remembered_hills = set()
        self.prev_enemies = []
        self.pin = None

    def do_turn(self, ants: Ants):
<<<<<<<< HEAD:autoresearch/bot/Crowd.py
        # Crowd: Gang's wiring (Denial's economy, pack-gated seek
        # approach, committed-join packs, ahead-only 1v1 duels,
        # off-hill screening, 10-gate equal trades), except a packed
        # hunter advances fearlessly -- skipping the safety filter --
        # while fewer than combat.CROWD_LIMIT enemies are visible.
        # With CROWD_LIMIT+ enemies visible the full champion safety
        # applies. Food, guard, muster, reinforce, explore, and
        # walk-off are champion.
========
>>>>>>>> tree/legion-3:autoresearch/bot/Hastati.py
        foods = ants.food()
        ants_list = ants.my_ants()
        my_set = set(ants_list)
        for r in range(ants.rows):
            for c in range(ants.cols):
                loc = (r, c)
                if ants.visible(loc):
                    self.seen.add(loc)
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

        # Straggler pick: one isolated foe for the whole pack, so
        # seekers converge instead of each feeding the nearest stack.
        # The pin is sticky while nothing strictly lonelier shows.
        straggler = (
            pick_straggler(
                enemy_locs,
                ants_list,
                ants.distance,
                sq_dist,
                attack_r2,
                sticky=self.pin,
            )
            if enemy_locs
            else None
        )
        self.pin = straggler

        def chase_for(
            cant: tuple[int, int],
        ) -> tuple[tuple[int, int] | None, str | None]:
            # This ant's hunt and its first step. When the
            # straggler is unreachable behind water, the ant hunts
            # its nearest reachable foe instead of standing idle.
            foe = seek_target(cant, straggler, enemy_locs, ants.distance)
            if foe is None:
                return None, None
            step = first_step(cant, foe)
            if step is None and foe == straggler:
                foe = nearest_seek_enemy(cant, enemy_locs, ants.distance)
                if foe is not None and foe != straggler:
                    step = first_step(cant, foe)
                else:
                    foe = None
            if step is None:
                return None, None
            return foe, step

        commitments: dict[int, tuple[int, int]] = {}
        chase_cache: dict[int, tuple[tuple[int, int] | None, str | None]] = {}
        if enemy_locs:
            for cai, cant in enumerate(ants_list):
                if target.get(cai) is not None:
                    continue
                foe_c, step_c = chase_for(cant)
                chase_cache[cai] = (foe_c, step_c)
                if step_c is None:
                    continue
                if not has_pack(cant, ants_list, ants.distance):
                    continue
                cloc = ants.destination(cant, step_c)
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
                    # Predictive screen: lead the razer to its
                    # predicted next square, meet it off the hill.
                    razer = min(
                        enemy_locs,
                        key=lambda e: ants.distance(nearest, e),
                        default=nearest,
                    )
                    aim = predict_square(razer, headings.get(razer), rows, cols)
                    inter = intercept_square(nearest, aim, ants.passable, rows, cols)
                    if inter is None:
                        inter = razer
                    step = first_step(ant_loc, inter)
                else:
                    anchored.add(nearest)
                    step = first_step(ant_loc, nearest)
                if step is not None and try_step(ant_loc, step):
                    moved = True
            if not moved and enemy_locs:
<<<<<<<< HEAD:autoresearch/bot/Crowd.py
                # Crowd: no food or guard move; hunt only with a pack,
                # fearless in small fights. A packless ant never
                # advances -- it packs up one step toward its nearest
                # friend instead (below), under the normal filter.
                foe = combat.nearest_seek_enemy(ant_loc, enemy_locs, ants.distance)
                if foe is not None and not combat.has_pack(
                    ant_loc, ants_list, ants.distance
                ):
========
                cached = chase_cache.get(ai)
                if cached is None:
                    foe, step = chase_for(ant_loc)
                else:
                    foe, step = cached
                if foe is not None and not has_pack(ant_loc, ants_list, ants.distance):
>>>>>>>> tree/legion-3:autoresearch/bot/Hastati.py
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
<<<<<<<< HEAD:autoresearch/bot/Crowd.py
                if foe is not None:
                    # Packed: fearless ahead while fewer than
                    # CROWD_LIMIT enemies are visible -- the advancing
                    # step skips the safety filter. In crowds the legs
                    # 1-3 rules hold: a joined ant (its foe drew 2+
                    # commitments) engages with equal trades allowed;
                    # an unjoined ant on a friendless 1v1 contact
                    # engages only while the visible army leads,
                    # otherwise the leg-1 safe seek holds.
                    step = first_step(ant_loc, foe)
                    if step is not None:
                        if combat.crowd_fearless(len(enemy_locs), combat.CROWD_LIMIT):
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
                            if combat.grinder_release(
                                pals, foes, len(ants_list), len(enemy_locs)
                            ):
                                if try_join(ant_loc, step):
                                    moved = True
                            elif try_step(ant_loc, step):
                                moved = True
========
                if foe is not None and step is not None:
                    # Always safe: joined pairs may take equal
                    # trades, friendless 1v1s only while ahead,
                    # everything else needs superiority or 10 near.
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
                        if grinder_release(pals, foes, len(ants_list), len(enemy_locs)):
                            if try_join(ant_loc, step):
                                moved = True
                        elif try_step(ant_loc, step):
                            moved = True
>>>>>>>> tree/legion-3:autoresearch/bot/Hastati.py
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
<<<<<<<< HEAD:autoresearch/bot/Crowd.py
                # Still stuck: explore least-visited squares first.
========
                # Scout: push the unseen edge first, so maze corridors
                # get walked early and distant food shows sooner.
                estep = edge_step(ant_loc, self.seen, ants.passable, ants.destination)
                if estep is not None and try_step(ant_loc, estep):
                    moved = True
            if not moved:
>>>>>>>> tree/legion-3:autoresearch/bot/Hastati.py
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
<<<<<<<< HEAD:autoresearch/bot/Crowd.py
        # if run is passed a class with a do_turn method, it will do the work
        # this is not needed, in which case you will need to write your own
        # parsing function and your own game state class
        Ants.run(Crowd())
========
        Ants.run(Hastati())
>>>>>>>> tree/legion-3:autoresearch/bot/Hastati.py
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
