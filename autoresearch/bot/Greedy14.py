#!/usr/bin/env python
"""Greedy14: pin-and-swarm assaults on a denial economy.

New mechanism -- top-down victim pinning. Each turn the bot pins
ONE enemy: the foe with the best free-hunter margin (free ants
minus visible enemies inside SUPPORT_R), needing 2+ hunters and a
strict local edge. The pin is sticky while still winnable, so
kills finish instead of thrashing. Claim-free hunters inside
HUNT_RANGE converge on the pin -- at most a party of three, so
the muster keeps its mass -- then hold the surround; committed
backup lets pinned hunters accept equal trades, and outnumbered
steps are never taken. This is not bottom-up
commitment joining (Swarm: ants chase their own nearest foe and
join when 2+ share one) and not Greedy13's centroid-wedge
(seekers bias toward the seeker centroid); the victim is chosen
globally first, then hunters are assigned to it.

Around the pin the entry runs the proven mix: Denial's
two-claim contested-cluster food economy, Duelist's proportional
guard (1 per 2 raiders, a third of gatherers draftable) with
off-hill intercept screening for extra guards, single-target
muster with reinforce, unseen-edge scouting, and an endgame that
sits held hills and contests only winnable ones. Unpinned ants
fight under strict superiority, taking equal trades only inside a
hill-attack zone with backup arriving or as friendless 1v1s while
the visible army leads; mission-free ants near foes rally to
their pack instead of drifting solo. Stdlib plus ants.py only.
"""

from collections import deque
from collections.abc import Callable

from ants import Ants

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]
SqDistFn = Callable[[Loc, Loc], int]
PassFn = Callable[[Loc], bool]

CLUSTER_R = 8
DENIAL_ENEMIES = 3
DENIAL_CLAIMS = 2
_CELL = CLUSTER_R + 1

# Pin-and-swarm: hunters counted inside SUPPORT_R of a foe, 2+
# needed to pin, strict local edge required; free hunters inside
# HUNT_RANGE converge on the pinned victim.
SUPPORT_R = 8
PIN_NEED = 2
HUNT_RANGE = 12

# Rally fallback: a mission-free ant with a foe inside SEEK_RANGE
# but no pack (PACK_NEED+ friends inside PACK_RADIUS) rallies one
# step toward its nearest friend instead of drifting solo.
SEEK_RANGE = 8
PACK_NEED = 3
PACK_RADIUS = 10

# Party cap: PIN_PARTY convergers per victim are enough for any
# kill; the rest of the army keeps its muster mass.
PIN_PARTY = 3

# Unpinned equal trades need something concrete: the step lands
# inside HILL_ATTACK_RADIUS of a known enemy hill with backup
# inside BACKUP_STEPS.
HILL_ATTACK_RADIUS = 20
BACKUP_STEPS = 6

# Proportional guard: 1 guard per 2 raiders, and the economy never
# lends more than a third of its gatherers.
EARLY_CALL_RADIUS = 20
GUARDS_PER_RAIDERS = 2

# Endgame: past ENDGAME_TURN idle ants sit held hills and contest
# the nearest uncontrolled hill only when the theater force
# (inside ENDGAME_THEATER_R2) strictly outnumbers.
ENDGAME_TURN = 600
ENDGAME_THEATER_R2 = 400


def _scan_board(
    foods: list[Loc], enemy_locs: list[Loc], rows: int, cols: int
) -> tuple[list[int], dict[int, int]]:
    # One bucketed pass: cluster roots for foods within CLUSTER_R and,
    # per cluster, how many distinct enemies sit within CLUSTER_R of a
    # member food. Linear buckets plus explicit seam bands cover the
    # torus. Same formula as Ants.distance.
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


def pin_margins(
    free_ants: list[Loc],
    enemy_locs: list[Loc],
    distance: DistFn,
    support_r: int = SUPPORT_R,
) -> dict[Loc, tuple[int, int]]:
    """Per-foe (hunters, margin) inside support_r. Hunters are free
    ants near the foe; margin subtracts visible enemies near it.
    Pure: no board state, no side effects."""
    margins: dict[Loc, tuple[int, int]] = {}
    for foe in enemy_locs:
        ours = sum(1 for a in free_ants if distance(a, foe) <= support_r)
        theirs = sum(1 for e in enemy_locs if distance(e, foe) <= support_r)
        margins[foe] = (ours, ours - theirs)
    return margins


def pin_victim(
    free_ants: list[Loc],
    enemy_locs: list[Loc],
    distance: DistFn,
    support_r: int = SUPPORT_R,
    sticky: Loc | None = None,
) -> Loc | None:
    """The pinned victim: foe with the best free-hunter margin.

    Margin is free ants minus visible enemies inside support_r of
    the foe. Needs PIN_NEED+ hunters and a strict edge (margin at
    least 1); the best margin pins, ties keep the first foe in
    sorted order so the branch is deterministic. A sticky pin that
    is still visible and winnable holds even against a better
    margin, so hunters finish kills instead of thrashing; a lost
    or gone sticky releases to the best margin. None when no foe
    is winnable. Pure: no board state, no side effects.
    """
    margins = pin_margins(free_ants, enemy_locs, distance, support_r)
    if sticky is not None and sticky in margins:
        ours, margin = margins[sticky]
        if ours >= PIN_NEED and margin >= 1:
            return sticky
    best: Loc | None = None
    best_margin = 0
    for foe in sorted(margins):
        ours, margin = margins[foe]
        if ours >= PIN_NEED and margin > best_margin:
            best_margin = margin
            best = foe
    return best


def pin_trade_safe(friends: int, enemies: int, pinned: bool) -> bool:
    """Step gate for hunters converging on the pinned victim.

    Free and winning steps go; equal trades go because the pin
    commits backup; outnumbered steps never go. Pure.
    """
    if enemies == 0:
        return True
    if friends + 1 > enemies:
        return True
    if friends + 1 < enemies:
        return False
    return pinned


def grinder_release(friends: int, enemies: int, my_army: int, enemy_army: int) -> bool:
    """Engage a friendless 1v1 contact only when the army leads.

    A planned step with no friend in attack range facing exactly one
    foe is mutual death, so it is refused by default; when the
    visible army strictly outnumbers theirs we replace faster, so
    the trade accelerates the win. Every other shape refuses exactly
    as the strict gate does. Pure."""
    return friends == 0 and enemies == 1 and my_army > enemy_army


def has_pack(
    ant_loc: Loc,
    ants_list: list[Loc],
    distance: DistFn,
    need: int = PACK_NEED,
    radius: int = PACK_RADIUS,
) -> bool:
    """Whether an ant holds a pack: need+ friends within radius."""
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
    """Nearest visible enemy within SEEK_RANGE, else None."""
    best: Loc | None = None
    best_d = SEEK_RANGE + 1
    for foe in enemy_locs:
        d = distance(ant_loc, foe)
        if d <= SEEK_RANGE and (best is None or d < best_d):
            best_d = d
            best = foe
    return best


def party_full(
    hunter_locs: list[Loc],
    victim: Loc,
    sq_dist: SqDistFn,
    attack_r2: int,
    cap: int = PIN_PARTY,
) -> bool:
    """Whether cap+ hunters already hold the surround: converged
    ants in attack range of the victim. Extra convergers would only
    dissolve the muster, so they stand down. Pure."""
    return sum(1 for a in hunter_locs if sq_dist(a, victim) <= attack_r2) >= cap


def surround_holds(friends: int, enemies: int) -> bool:
    """Whether a hunter holds its surround square: the pin commits
    backup, so equal fights hold; outnumbered ones release. Pure."""
    if enemies == 0:
        return True
    return friends + 1 >= enemies


def equal_trade_allowed(hill_dist: int | None, backup_dist: int | None) -> bool:
    """An equal trade is allowed only when it buys something concrete."""
    return (
        hill_dist is not None
        and hill_dist <= HILL_ATTACK_RADIUS
        and backup_dist is not None
        and backup_dist <= BACKUP_STEPS
    )


def trade_safe(
    friends: int,
    enemies: int,
    hill_dist: int | None = None,
    backup_dist: int | None = None,
) -> bool:
    """Full gate for unpinned ants: strict superiority always, equal
    trades only inside a hill-attack zone with backup arriving."""
    if enemies == 0:
        return True
    if friends + 1 > enemies:
        return True
    if friends + 1 < enemies:
        return False
    return equal_trade_allowed(hill_dist, backup_dist)


def nearest_toroidal(
    nloc: Loc,
    locs: list[Loc] | set[Loc],
    rows: int,
    cols: int,
    skip: Loc | None = None,
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


def guards_needed(n_raiders: int, per: int = GUARDS_PER_RAIDERS) -> int:
    """Guards for a raid: 1 per 2 raiders, rounded up."""
    return (n_raiders + per - 1) // per


def max_gatherer_draft(n_gatherers: int) -> int:
    """The economy never lends more than a third of its gatherers."""
    return n_gatherers // 3


def hill_threatened_old(dist: int, is_closing: bool) -> bool:
    """Close raiders, or closing ones from mid range."""
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


def endgame_active(turn: int) -> bool:
    """The closing rule flips on at ENDGAME_TURN and stays on."""
    return turn >= ENDGAME_TURN


def endgame_challenge_allowed(friends: int, enemies: int) -> bool:
    """Strict local superiority: the committing force must outnumber."""
    return friends + 1 > enemies


def count_near(
    loc: Loc,
    others: list[Loc],
    r2: int,
    rows: int,
    cols: int,
) -> int:
    """Ants of `others` inside squared-toroidal range r2 of loc."""
    total = 0
    for o in others:
        dr = abs(loc[0] - o[0])
        dr = min(dr, rows - dr) if rows else dr
        dc = abs(loc[1] - o[1])
        dc = min(dc, cols - dc) if cols else dc
        if dr * dr + dc * dc <= r2:
            total += 1
    return total


def theater_allows(
    goal: Loc,
    my_ants: list[Loc],
    enemy_locs: list[Loc],
    rows: int,
    cols: int,
) -> bool:
    """Our theater force at an uncontrolled hill strictly outnumbers."""
    friends = count_near(goal, my_ants, ENDGAME_THEATER_R2, rows, cols)
    enemies = count_near(goal, enemy_locs, ENDGAME_THEATER_R2, rows, cols)
    return endgame_challenge_allowed(friends, enemies)


def intercept_square(
    hill: Loc,
    enemy_locs: list[Loc],
    distance: DistFn,
    passable: PassFn,
    rows: int,
    cols: int,
) -> Loc | None:
    """Off-hill intercept: nearest passable square to the midpoint
    between a threatened home hill and its nearest enemy, so extra
    guards meet the razer off the hill. None when no square works."""
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
class Greedy14:
    def __init__(self):
        # define class level variables, will be remembered between turns
        self.visits: dict[Loc, int] = {}
        self.seen: set[Loc] = set()
        self.remembered_hills: set[Loc] = set()
        self.prev_enemies: list[Loc] = []
        self.turn = 0
        self.pin: Loc | None = None

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
        self.pin = None

    # do turn is run once per turn
    # the ants class has the game state and is updated by the Ants.run method
    # it also has several helper methods to use
    def do_turn(self, ants: Ants):
        # Pin-and-swarm on a denial economy. Food runs Denial's
        # two-claim contested clusters; threatened hills draw a
        # proportional guard (first holds, extras screen the razer
        # off the hill); claim-free hunters inside HUNT_RANGE
        # converge on the one pinned victim with committed-backup
        # equal trades; the army musters on one hill and reinforces
        # a second; idle ants push the unseen edge, then spread over
        # least-visited ground; past turn 600 sitters hold home and
        # only winnable hills are contested. Unpinned ants fight
        # under strict superiority with hill-zone equal trades.
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
        headings: dict[Loc, Loc] = {}
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

        def closing(cur: Loc, hill: Loc) -> bool:
            prev = headings.get(cur)
            return prev is not None and ants.distance(prev, hill) > ants.distance(
                cur, hill
            )

        # The group marches on one target, the hill nearest the army
        # as a whole. Hoisted so the early-call guard shares it.
        muster_target: Loc | None = None
        if hills and ants_list:
            muster_target = min(
                hills,
                key=lambda h: sum(ants.distance(a, h) for a in ants_list),
            )
        # The muster home front calls for help early: the home hill
        # nearest the muster target treats any enemy inside 20 steps
        # as a raid.
        early_hill: Loc | None = None
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
        # Proportional guard: each threatened hill draws 1 guard per
        # 2 raiders. Free ants march first; gatherers are drafted
        # only up to a third of their number.
        guard_for: dict[int, Loc] = {}
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
        # Pin the victim before moving: only claim-free, guard-free
        # ants hunt, so the pin counts exactly the ants that can go.
        free_ants = [
            a
            for ai, a in enumerate(ants_list)
            if ai not in target and ai not in guard_for
        ]
        victim = pin_victim(free_ants, enemy_locs, ants.distance, sticky=self.pin)
        self.pin = victim
        attack_r2 = ants.attackradius2 or 5
        rows, cols = ants.rows, ants.cols

        def sq_dist(a: Loc, b: Loc) -> int:
            dr = abs(a[0] - b[0])
            dr = min(dr, rows - dr) if rows else dr
            dc = abs(a[1] - b[1])
            dc = min(dc, cols - dc) if cols else dc
            return dr * dr + dc * dc

        def count_sides(nloc: Loc, self_loc: Loc) -> tuple[int, int]:
            enemies = 0
            for e in enemy_locs:
                if sq_dist(nloc, e) <= attack_r2:
                    enemies += 1
                    if enemies >= len(ants_list):
                        break
            friends = 0
            for f in ants_list:
                if f == self_loc:
                    continue
                if sq_dist(nloc, f) <= attack_r2:
                    friends += 1
            return friends, enemies

        def is_safe(nloc: Loc, self_loc: Loc) -> bool:
            friends, enemies = count_sides(nloc, self_loc)
            hill_dist: int | None = None
            backup_dist: int | None = None
            if friends + 1 == enemies:
                # Only price an equal trade when one is on the table.
                hill_dist = nearest_toroidal(nloc, hills, rows, cols)
                backup_dist = nearest_toroidal(
                    nloc, ants_list, rows, cols, skip=self_loc
                )
            if trade_safe(friends, enemies, hill_dist, backup_dist):
                return True
            return grinder_release(friends, enemies, len(ants_list), len(enemy_locs))

        def first_step(start: Loc, goal: Loc, budget: int = 250) -> str | None:
            # Shortest passable path around water; return its first step.
            if start == goal:
                return None
            parent: dict[Loc, tuple[Loc, str]] = {}
            parent[start] = (start, "")
            queue: deque[Loc] = deque([start])
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

        def edge_step(start: Loc, budget: int = 500) -> str | None:
            # First step of the shortest passable path to the nearest
            # square never seen. None when explored or over budget.
            parent: dict[Loc, tuple[Loc, str]] = {}
            parent[start] = (start, "")
            queue: deque[Loc] = deque([start])
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

        def try_step(ant_loc: Loc, direction: str, safe: bool = True) -> bool:
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

        def try_hunt(ant_loc: Loc) -> bool:
            # Converge on the pinned victim, then hold the surround.
            # Hunters already in attack range stay and fight (the pin
            # commits backup, so equal trades hold); the step in goes
            # only on strict superiority or a committed-backup equal
            # trade; outnumbered shapes fall through to the muster.
            if victim is None:
                return False
            if sq_dist(ant_loc, victim) <= attack_r2:
                friends, enemies = count_sides(ant_loc, ant_loc)
                return surround_holds(friends, enemies)
            if ants.distance(ant_loc, victim) > HUNT_RANGE:
                return False
            if party_full(free_ants, victim, sq_dist, attack_r2):
                # The surround already holds a full party: keep the
                # muster mass instead of piling on.
                return False
            step = first_step(ant_loc, victim)
            if step is None:
                return False
            dest = ants.destination(ant_loc, step)
            if (
                dest in destinations
                or not ants.passable(dest)
                or not ants.unoccupied(dest)
            ):
                return False
            friends, enemies = count_sides(dest, ant_loc)
            if not pin_trade_safe(friends, enemies, pinned=True):
                return False
            ants.issue_order((ant_loc, step))
            destinations.add(dest)
            return True

        destinations: set[Loc] = set()
        challenge_cache: dict[Loc, bool] = {}
        held: list[Loc] = []
        anchored: set[Loc] = set()
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
                    inter = intercept_square(
                        hill,
                        enemy_locs,
                        ants.distance,
                        ants.passable,
                        ants.rows,
                        ants.cols,
                    )
                    if inter is None:
                        inter = min(
                            enemy_locs,
                            key=lambda e: ants.distance(hill, e),
                            default=hill,
                        )
                    step = first_step(ant_loc, inter)
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
            if not moved and ai not in target and try_hunt(ant_loc):
                # Pin-and-swarm: claim-free hunters converge on the
                # pinned victim; the pin guarantees the edge, the
                # step gate guarantees no donations.
                moved = True
            if not moved and hills and muster_target is not None:
                # The group marches on one target, the hill nearest
                # the army as a whole. Hunt always; fearless when
                # ahead on hills.
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
                # Sit on the nearest held hill. An ant already sitting
                # (or with no held hill) contests the nearest
                # uncontrolled hill, but only with strict superiority
                # at the theater and at the step.
                sit: Loc | None = None
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
                    goal: Loc | None = None
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
                                cf, ce = count_sides(dest, ant_loc)
                                if endgame_challenge_allowed(cf, ce):
                                    ants.issue_order((ant_loc, step))
                                    destinations.add(dest)
                                    moved = True
                                    break
            if (
                not moved
                and not endgame
                and nearest_seek_enemy(ant_loc, enemy_locs, ants.distance) is not None
                and not has_pack(ant_loc, ants_list, ants.distance)
            ):
                # Rally: a foe is near but the ant holds no pack, so
                # it packs up one step toward its nearest friend
                # instead of drifting solo into the fight.
                pal = min(
                    (f for f in ants_list if f != ant_loc),
                    key=lambda f: ants.distance(ant_loc, f),
                    default=None,
                )
                if pal is not None:
                    pstep = first_step(ant_loc, pal)
                    if pstep is not None and try_step(ant_loc, pstep):
                        moved = True
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
        Ants.run(Greedy14())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
