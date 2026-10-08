#!/usr/bin/env python
"""Rally: pack-gated centroid seekers press small fights.

The spine is Odds (denial economy, join packs, ahead-only 1v1
duels, off-hill screens, equal trades at 10 near). Nine new
rules make this entry a rally, not a copy:

(a) pack gate: only ants with 3+ friends within 10 seek; a
    packless ant steps toward its nearest friend instead;
(b) rally mark: a packed seeker marches on the foe nearest the
    army centroid among foes in SEEK_RANGE of itself;
(c) crowd press: packed rally advances skip safety while
    fewer than CROWD_LIMIT foes show, ahead or behind; crowds
    keep full safety. Donations happen in crowds, not duels;
(d) grave check: a remembered hill seen empty is forgotten, so
    no raid marches on a razed hill;
(e) stand-off harvest: paths never route through food squares;
    meals gather by adjacency (approach), so no order steps
    onto a food square the engine would ignore;
(f) raid margin: a remembered hill marches only at 2:1 over
    its campers (foes within 12), empty hills always raid, and
    the reinforce checks its own hill when the muster is camped;
(g) rotated explore: simultaneous explorers fan out by a
    per-ant compass rotation instead of marching in a column;
(h) stand-off sitters: an ant adjacent to its claim holds the
    meal instead of exploring off it, still walking off home
    hills so they stay spawnable;
(i) deeper paths: BFS budgets run 500 expansions while the
    clock is healthy (150 under 300 ms left), so cross-map raids
    actually route instead of silently exploring, and huge
    late-game maps degrade instead of timing out.
"""

from collections import deque
from collections.abc import Callable

import combat
from ants import Ants

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]

CLUSTER_R = 8
DENIAL_ENEMIES = 3
DENIAL_CLAIMS = 2
_CELL = CLUSTER_R + 1


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


class Rally:
    def __init__(self):
        self.visits: dict[tuple[int, int], int] = {}
        self.hills: set[tuple[int, int]] = set()
        self.prev_enemies: list[tuple[int, int]] = []

    def do_setup(self, ants: Ants):
        self.visits = {}
        self.hills = set()
        self.prev_enemies = []

    def do_turn(self, ants: Ants):
        foods = ants.food()
        ants_list = ants.my_ants()
        my_set = set(ants_list)
        seen = ants.enemy_ants()
        enemy_locs = [loc for loc, _ in seen]
        food_set = set(foods)
        target = assign_food_targets(
            ants_list, foods, enemy_locs, ants.distance, ants.rows, ants.cols
        )
        for hloc, _ in ants.enemy_hills():
            self.hills.add(hloc)
        live = {hloc for hloc, _ in ants.enemy_hills()}
        for hloc in list(self.hills):
            if hloc in my_set or hloc not in live and ants.visible(hloc):
                self.hills.discard(hloc)
        hills = sorted(self.hills)
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
        press = combat.crowd_fearless(len(enemy_locs))

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
            return near >= combat.EQUAL_TRADE_NEAR and friends + 1 >= enemies

        def path_budget() -> int:
            # Graceful degradation: full 500-expansion searches while
            # time is healthy, cheap 150-expansion ones when the turn
            # burns down, so a huge late-game map slows the bot
            # instead of timing it out. Tests run at 500.
            return 150 if ants.time_remaining() < 300 else 500

        def first_step(
            start: tuple[int, int], goal: tuple[int, int], budget: int | None = None
        ) -> str | None:
            if start == goal:
                return None
            if not ants.passable(goal) or goal in food_set:
                return None
            if budget is None:
                budget = path_budget()
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
            start: tuple[int, int], meal: tuple[int, int], budget: int | None = None
        ) -> str | None:
            if ants.distance(start, meal) <= 1:
                return None
            if budget is None:
                budget = path_budget()
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

        def try_step(
            ant_loc: tuple[int, int], direction: str, safe: bool = True
        ) -> bool:
            new_loc = ants.destination(ant_loc, direction)
            if (
                new_loc not in destinations
                and ants.passable(new_loc)
                and new_loc not in food_set
                and ants.unoccupied(new_loc)
                and (not safe or is_safe(new_loc, ant_loc))
            ):
                ants.issue_order((ant_loc, direction))
                destinations.add(new_loc)
                return True
            return False

        def try_press(ant_loc: tuple[int, int], direction: str) -> bool:
            new_loc = ants.destination(ant_loc, direction)
            if (
                new_loc in destinations
                or not ants.passable(new_loc)
                or new_loc in food_set
                or not ants.unoccupied(new_loc)
            ):
                return False
            ants.issue_order((ant_loc, direction))
            destinations.add(new_loc)
            return True

        def try_join(ant_loc: tuple[int, int], direction: str) -> bool:
            new_loc = ants.destination(ant_loc, direction)
            if (
                new_loc in destinations
                or not ants.passable(new_loc)
                or new_loc in food_set
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
                if not combat.has_pack(cant, ants_list, ants.distance):
                    continue
                chase = combat.rally_mark(cant, ants_list, enemy_locs, ants.distance)
                if chase is None:
                    continue
                cstep = first_step(cant, chase)
                if cstep is None:
                    continue
                cloc = ants.destination(cant, cstep)
                cfoe = combat.contact_foe(cloc, enemy_locs, sq_dist, attack_r2)
                if cfoe is not None:
                    commitments[cai] = cfoe
        joined = combat.joined_attackers(commitments)
        muster = None
        if hills:
            muster = min(
                hills,
                key=lambda h: sum(ants.distance(a, h) for a in ants_list),
            )
        raid = muster is None or combat.hill_takeable(
            len(ants_list), combat.camped_at(muster, enemy_locs, ants.distance)
        )

        destinations: set[tuple[int, int]] = set()
        held: list[tuple[int, int]] = []
        anchored: set[tuple[int, int]] = set()
        for ai, ant_loc in enumerate(ants_list):
            self.visits[ant_loc] = self.visits.get(ant_loc, 0) + 1
            best = target.get(ai)
            moved = False
            if best is not None:
                step = approach_food(ant_loc, best)
                if step is not None and try_step(ant_loc, step):
                    moved = True
            if not moved and threatened:
                nearest = min(threatened, key=lambda h: ants.distance(ant_loc, h))
                if nearest in anchored:
                    inter = combat.intercept_square(
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
                if combat.has_pack(ant_loc, ants_list, ants.distance):
                    foe = combat.rally_mark(
                        ant_loc, ants_list, enemy_locs, ants.distance
                    )
                    if foe is not None:
                        step = first_step(ant_loc, foe)
                        if step is not None:
                            if ai in joined:
                                if try_join(ant_loc, step):
                                    moved = True
                            elif press:
                                if try_press(ant_loc, step):
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
                else:
                    buddy = min(
                        (f for f in ants_list if f != ant_loc),
                        key=lambda f: ants.distance(ant_loc, f),
                        default=None,
                    )
                    if buddy is not None:
                        step = first_step(ant_loc, buddy)
                        if step is not None and try_step(ant_loc, step):
                            moved = True
            if not moved and hills and raid:
                assert muster is not None
                step = first_step(ant_loc, muster)
                if step is not None and try_step(
                    ant_loc, step, safe=len(my_hills) <= len(hills)
                ):
                    moved = True
            if not moved and hills:
                ordered = sorted(hills, key=lambda h: ants.distance(ant_loc, h))
                near = ordered[1] if len(ordered) > 1 else ordered[0]
                if combat.hill_takeable(
                    len(ants_list), combat.camped_at(near, enemy_locs, ants.distance)
                ):
                    hstep = first_step(ant_loc, near)
                    if hstep is not None and try_step(ant_loc, hstep):
                        moved = True
            if not moved and (
                best is not None
                and ants.distance(ant_loc, best) <= 1
                and ant_loc not in my_hills
            ):
                # Stand-off sitter: already gathering by adjacency,
                # so hold the meal instead of exploring off it.
                # Guard, seek, and muster already had their chance,
                # and home-hill ants still walk off below.
                moved = True
            if not moved:
                dirs = sorted(
                    combat.explore_order(ant_loc),
                    key=lambda d: self.visits.get(ants.destination(ant_loc, d), 0),
                )
                for direction in dirs:
                    new_loc = ants.destination(ant_loc, direction)
                    if (
                        new_loc not in destinations
                        and ants.passable(new_loc)
                        and new_loc not in food_set
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
        Ants.run(Rally())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
