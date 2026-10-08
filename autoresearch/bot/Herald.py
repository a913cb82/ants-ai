#!/usr/bin/env python
"""Herald: turn-scaled muster quorum with standard rally.

Understudy base (denial food, flood muster, challenger rotation,
threatened guard, safety filter, BFS steps, least-visited explore,
walk-off) with one new mechanism: the muster march needs a quorum
that grows as the war runs on -- 2 + turn // 150, capped at 6.
Early, pairs still race hills for tempo; late, only a massed pack
marches, so the army stops donating ones and twos into defenders.
Quorum-short ants do not scatter: they rally to the army standard
(the medoid ant) and stay massed until enough have answered the
call. A suppressed turn records no challenge, so the next march
picks open instead of falsely rotating. Triumph relaxes the late
quorum to the early pair-race while ahead on hills, so a winning
army closes out instead of massing. Commitment holds a march already
under way with one fewer ant, so the army does not yo-yo as food
comes and goes."""

from collections import deque
from collections.abc import Callable

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
                nearby = buckets.get((br + dbr, bc + dbc))
                if not nearby:
                    continue
                for j in nearby:
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


def pick_challenger(
    hill: Loc,
    ants_list: list[Loc],
    distance: DistFn,
    exclude: Loc | None = None,
) -> Loc | None:
    # Nearest ant to the hill, skipping the excluded last
    # challenger. Ties break by list order (stable).
    best: Loc | None = None
    best_d = 0
    for ant in ants_list:
        if exclude is not None and ant == exclude:
            continue
        d = distance(ant, hill)
        if best is None or d < best_d:
            best = ant
            best_d = d
    return best


def challenge_exclusion(
    hill: Loc,
    last_target: Loc | None,
    held: set[Loc],
    last_challenger: dict[Loc, Loc],
    ants_list: list[Loc],
    distance: DistFn,
) -> Loc | None:
    # Failed challenge: this hill was last turn's target and is
    # still enemy-held. Rotate: sit the last challenger out. Any
    # other hill, a freed hill, or a gone challenger picks open.
    if last_target is None or hill != last_target or hill not in held:
        return None
    recorded = last_challenger.get(hill)
    if recorded is None:
        return None
    # Same ant moved at most one square since last turn.
    same = min(ants_list, key=lambda a: distance(a, recorded), default=None)
    if same is None or distance(same, recorded) > 1:
        return None
    return same


HERALD_QUORUM_BASE = 2
HERALD_QUORUM_STEP = 150
HERALD_QUORUM_CAP = 6


def muster_quorum(turn: int) -> int:
    # How many mission-free ants the muster march needs this turn.
    # Grows as the war runs on: pairs race early for tempo, a massed
    # pack marches late so lone ants stop donating into defenders.
    return min(HERALD_QUORUM_BASE + turn // HERALD_QUORUM_STEP, HERALD_QUORUM_CAP)


def march_allowed(
    mission_free: int, turn: int, ahead: bool = False, committed: bool = False
) -> bool:
    # Whether the muster march goes out: enough mission-free ants
    # answered the herald's call this turn. Triumph relaxes the
    # late quorum to the early pair-race when ahead on hills, so a
    # winning army closes out instead of massing. Commitment holds a
    # march already under way with one fewer ant, so the army does
    # not yo-yo between marching and rallying as food comes and goes.
    need = HERALD_QUORUM_BASE if ahead else muster_quorum(turn)
    if committed:
        need = max(1, need - 1)
    return mission_free >= need


def rally_point(ants_list: list[Loc], distance: DistFn) -> Loc | None:
    # The army standard: the medoid ant, minimizing the summed
    # distance to the whole army. Quorum-short ants gather here
    # instead of scattering. Ties keep list order (stable).
    if not ants_list:
        return None
    best = ants_list[0]
    best_sum: int | None = None
    for candidate in ants_list:
        total = 0
        for other in ants_list:
            total += distance(candidate, other)
        if best_sum is None or total < best_sum:
            best_sum = total
            best = candidate
    return best


# define a class with a do_turn method
# the Ants.run method will parse and update bot input
# it will also run the do_turn method for us
class Herald:
    def __init__(self):
        # define class level variables, will be remembered between turns
        self.visits: dict[tuple[int, int], int] = {}
        self.remembered_hills: set[tuple[int, int]] = set()
        self.prev_enemies: list[tuple[int, int]] = []
        self.last_challenger: dict[tuple[int, int], tuple[int, int]] = {}
        self.last_target: tuple[int, int] | None = None
        self.turn: int = 0

    # do_setup is run once at the start of the game
    # after the bot has received the game settings
    # the ants class is created and setup by the Ants.run method
    def do_setup(self, ants: Ants):
        # initialize data structures after learning the game settings
        self.visits = {}
        self.remembered_hills = set()
        self.prev_enemies = []
        self.last_challenger = {}
        self.last_target = None
        self.turn = 0

    # do turn is run once per turn
    # the ants class has the game state and is updated by the Ants.run method
    # it also has several helper methods to use
    def do_turn(self, ants: Ants):
        # Herald: Understudy wiring, except the muster march needs a
        # quorum that grows with the war (2 + turn // 150, cap 6).
        # Quorum-short ants rally to the army standard (medoid) and
        # stay massed instead of donating; food, guard, rotation,
        # safety, explore, and walk-off are base. A suppressed turn
        # records no challenge, so the next march picks open.
        self.turn += 1
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
        # Herald: the march goes out only when enough mission-free
        # (foodless) ants answered the call; the rest rally to the
        # standard and stay massed until the pack is big enough.
        # Triumph: ahead on hills, the pair-race stays open all war.
        # Commitment: a march already under way holds with one fewer.
        ahead = len(my_hills) > len(hills)
        committed = self.last_target is not None and self.last_target in hills
        marching = march_allowed(
            len(ants_list) - len(target), self.turn, ahead, committed
        )
        standard: tuple[int, int] | None = (
            rally_point(ants_list, ants.distance) if not marching else None
        )
        # Understudy: the muster target formula is unchanged, but a
        # failed challenge rotates -- last turn's challenger sits out
        # this hill's next challenge and a different ant goes instead.
        muster_hill: tuple[int, int] | None = (
            min(
                hills,
                key=lambda h: sum(ants.distance(a, h) for a in ants_list),
            )
            if hills
            else None
        )
        understudy_out: tuple[int, int] | None = None
        challenger: tuple[int, int] | None = None
        if muster_hill is not None:
            understudy_out = challenge_exclusion(
                muster_hill,
                self.last_target,
                self.remembered_hills,
                self.last_challenger,
                ants_list,
                ants.distance,
            )
            challenger = pick_challenger(
                muster_hill, ants_list, ants.distance, understudy_out
            )
            if challenger is None:
                # No understudy exists: the lone ant retries the hill.
                understudy_out = None
                challenger = pick_challenger(
                    muster_hill, ants_list, ants.distance, None
                )
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
            # Aggressive: 14+ friends near the fight accept equal trades.
            return near >= 14 and friends + 1 >= enemies

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
            if (
                not moved
                and marching
                and hills
                and muster_hill is not None
                and ant_loc != understudy_out
            ):
                # Flood: the group marches on one target, the hill
                # nearest the army as a whole. Hunt always; fearless
                # when ahead on hills.
                step = first_step(ant_loc, muster_hill)
                if step is not None and try_step(
                    ant_loc, step, safe=len(my_hills) <= len(hills)
                ):
                    moved = True
            if (
                not moved
                and not marching
                and standard is not None
                and muster_hill is not None
                and ant_loc != standard
            ):
                # Quorum short with a march to wait for: gather on the
                # standard instead of marching or scattering, so the
                # pack stays massed. With no known hills the scouts
                # keep scouting (explore below) instead. The standard
                # itself holds for explore below.
                rstep = first_step(ant_loc, standard)
                if rstep is not None and try_step(ant_loc, rstep):
                    moved = True
            if not moved and hills and marching:
                # No hill move: reinforce the second-nearest hill.
                ordered = sorted(hills, key=lambda h: ants.distance(ant_loc, h))
                near = ordered[1] if len(ordered) > 1 else ordered[0]
                if not (ant_loc == understudy_out and near == muster_hill):
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
        if muster_hill is not None and challenger is not None and marching:
            self.last_challenger[muster_hill] = challenger
        for old in list(self.last_challenger):
            if old != muster_hill and old not in self.remembered_hills:
                del self.last_challenger[old]
        # A suppressed turn is waiting, not a failed challenge: record
        # no target so the next march picks open, never a false rotate.
        self.last_target = muster_hill if marching else None
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
        Ants.run(Herald())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
