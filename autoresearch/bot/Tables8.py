#!/usr/bin/env python
"""Pack-mustered table press with committed-join release (Tables8 entry).

Faithful port of the codetiger Python datapoint
(autoresearch/docs/RESEARCH.md, "codetiger Python time datapoint"):
full battle search is infeasible in Python under the turn limit, so
local battle outcomes are PRECOMPUTED once at setup into lookup
tables derived from the engine's focus-battle rules (an ant dies
iff its minimum enemy nearby-count is <= its own nearby-count).
Per-turn contact decisions
are pure table lookups -- the turn loop never resolves a battle
live per ant. Friendless 1v1 sacrifices (mutual-death trades) are
allowed within radius 14 of a held home hill, hiding the
replacement cost, or when committed-join releases them (their foe
drew 2+ advancing commitments); elsewhere they always refuse.

Tables base (precomputed battle tables, hill-gated trades, Denial
economy, guard/muster/reinforce/explore/walk-off) plus two
Crowd-proven but Tables-new gates, both table-native:
pack-mustered approaches (a packless ant never walks solo onto
the contact edge through empty ground and never mills on refused
contacts -- it packs up one table-safe step toward its nearest
friend instead -- while free kills and hill-covered sacrifices go
for every ant), and committed-join release (a foe drawing 2+
advancing commitments releases equal TRADE steps for its
committers without hill cover). Losing steps still always refuse.
Self-contained: stdlib plus ants.py only, never combat.py.
"""

from collections import deque
from collections.abc import Callable

from ants import Ants

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]

CLUSTER_R = 8
DENIAL_ENEMIES = 3
DENIAL_CLAIMS = 2
_CELL = CLUSTER_R + 1

# Codetiger combat core: precomputed battle-resolution tables.
SEEK_RANGE = 8
HILL_SACRIFICE_RADIUS = 14
TABLE_MAX = 32

# Tables8 press gates: pack-mustered approaches -- an ant with
# PACK_NEED+ friends within PACK_RADIUS steps presses like the
# base; a packless ant still takes free kills and hill-covered
# sacrifices but packs up toward its nearest friend instead of
# walking solo onto the contact edge through empty ground.
PACK_NEED = 3
PACK_RADIUS = 10

# Outcome classes for one planned contact step, keyed by
# (own ants in attack radius including the mover, enemy ants in
# attack radius). Derived once from the focus-battle rule under
# mutual contact (each side's nearby-count is the other side's
# ant count):
# we die iff OURS <= THEIRS, they die iff THEIRS <= OURS.
SAFE = "SAFE"
WIN = "WIN"
TRADE = "TRADE"
LOSE = "LOSE"


def build_battle_table(max_side: int = TABLE_MAX) -> dict[tuple[int, int], str]:
    """Precompute local battle outcomes for every count pair.

    Runs once at setup: (ours, theirs) with ours including the
    moving ant. No enemies means no battle (SAFE); otherwise more
    ants wins clean (WIN), equal counts die together (TRADE), and
    fewer dies alone (LOSE). Pure: integer compares, no board.
    """
    table: dict[tuple[int, int], str] = {}
    for ours in range(max_side + 1):
        for theirs in range(max_side + 1):
            if theirs == 0:
                table[(ours, theirs)] = SAFE
            elif ours > theirs:
                table[(ours, theirs)] = WIN
            elif ours == theirs:
                table[(ours, theirs)] = TRADE
            else:
                table[(ours, theirs)] = LOSE
    return table


def lookup_verdict(table: dict[tuple[int, int], str], ours: int, theirs: int) -> str:
    """Outcome class for one contact: a pure dict lookup.

    Counts clamp to the table span so crowded boards never raise
    KeyError; the clamped verdict still follows the rule (capped
    equal stays TRADE, capped superiority stays WIN). Pure: dict
    lookup plus clamps, far under 0.1ms.
    """
    ours = min(max(ours, 0), TABLE_MAX)
    theirs = min(max(theirs, 0), TABLE_MAX)
    return table[(ours, theirs)]


def _nearest_seek_enemy(
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


def has_pack(
    ant_loc: Loc,
    ants_list: list[Loc],
    distance: DistFn,
    need: int = PACK_NEED,
    radius: int = PACK_RADIUS,
) -> bool:
    """Whether an ant holds a pack: need+ friends within radius steps.

    The ant itself never counts toward its own pack. Pure: no board
    state, no side effects.
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


def _intercept_square(
    hill: Loc,
    enemy_locs: list[Loc],
    distance: DistFn,
    passable: Callable[[Loc], bool],
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


# define a class with a do_turn method
# the Ants.run method will parse and update bot input
# it will also run the do_turn method for us
class Tables8:
    def __init__(self):
        # define class level variables, will be remembered between turns
        self.visits: dict[tuple[int, int], int] = {}
        self.remembered_hills: set[tuple[int, int]] = set()
        self.prev_enemies: list[tuple[int, int]] = []
        # Precomputed battle-resolution tables (codetiger): built
        # once here so tests driving do_turn directly get lookups.
        self.battle_table = build_battle_table()
        # Cached per-turn board state for contact_verdict.
        self._ants_list: list[Loc] = []
        self._enemy_locs: list[Loc] = []
        self._home_hills: list[Loc] = []
        self._attack_r2: int = 5
        self._rows: int = 0
        self._cols: int = 0

    # do_setup is run once at the start of the game
    # after the bot has received the game settings
    # the ants class is created and setup by the Ants.run method
    def do_setup(self, ants: Ants):
        # initialize data structures after learning the game settings
        self.visits = {}
        self.remembered_hills = set()
        self.prev_enemies = []
        self.battle_table = build_battle_table()
        self._ants_list = []
        self._enemy_locs = []
        self._home_hills = []
        self._attack_r2 = 5
        self._rows = 0
        self._cols = 0

    def _sq(self, a: Loc, b: Loc) -> int:
        # Squared toroidal distance for attack-range checks.
        rows, cols = self._rows, self._cols
        if rows <= 0 or cols <= 0:
            return 10**9
        dr = abs(a[0] - b[0])
        dr = min(dr, rows - dr)
        dc = abs(a[1] - b[1])
        dc = min(dc, cols - dc)
        return dr * dr + dc * dc

    def contact_verdict(self, dest: Loc, self_loc: Loc) -> str:
        """Outcome class for stepping onto dest: a pure table lookup.

        Counts own (excluding the mover) and enemy ants within
        attack radius of dest, then looks the pair up in the
        setup-precomputed battle table. Never re-derives battle
        math live: dict-lookup scale, far under 0.1ms per call.
        """
        foes = 0
        for e in self._enemy_locs:
            if self._sq(dest, e) <= self._attack_r2:
                foes += 1
        if foes == 0:
            return SAFE
        pals = 0
        for f in self._ants_list:
            if f == self_loc:
                continue
            if self._sq(dest, f) <= self._attack_r2:
                pals += 1
        return lookup_verdict(self.battle_table, pals + 1, foes)

    # do turn is run once per turn
    # the ants class has the game state and is updated by the Ants.run method
    # it also has several helper methods to use
    def do_turn(self, ants: Ants):
        # Tables8: the Tables base (champion economy, muster,
        # guard, explore, walk-off; precomputed battle tables with
        # hill-gated trades) plus pack-mustered approaches and
        # committed-join release. Free kills and hill-covered
        # TRADE sacrifices (within HILL_SACRIFICE_RADIUS) go for
        # every ant; joined TRADEs go without hill cover; packed
        # ants press empty squares; packless ants pack up toward
        # a friend instead of walking solo onto the contact edge
        # or milling on refused contacts. LOSE and unjoined
        # open-field trades fall through to the next branch.
        # Food, guard, muster, reinforce, explore, and walk-off
        # are champion.
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
        # Cache turn state so contact_verdict stays a bare lookup.
        self._ants_list = ants_list
        self._enemy_locs = enemy_locs
        self._home_hills = my_hills
        self._attack_r2 = attack_r2
        self._rows = rows
        self._cols = cols

        def near_home(nloc: tuple[int, int]) -> bool:
            # Hill cover: the sacrifice hides inside the spawn flow
            # only within HILL_SACRIFICE_RADIUS of a held home hill.
            return any(
                ants.distance(nloc, h) <= HILL_SACRIFICE_RADIUS for h in my_hills
            )

        def square_safe(nloc: tuple[int, int], self_loc: tuple[int, int]) -> bool:
            # Table-backed safety: WIN and empty squares pass, LOSE
            # refuses, and TRADE passes only under hill cover.
            verdict = self.contact_verdict(nloc, self_loc)
            if verdict in (SAFE, WIN):
                return True
            if verdict == LOSE:
                return False
            return near_home(nloc)

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
                and (not safe or square_safe(new_loc, ant_loc))
            ):
                ants.issue_order((ant_loc, direction))
                destinations.add(new_loc)
                return True
            return False

        def try_move(ant_loc: tuple[int, int], direction: str) -> bool:
            # The table already cleared this step: only passable,
            # occupancy, and destination clashes check here.
            new_loc = ants.destination(ant_loc, direction)
            if (
                new_loc not in destinations
                and ants.passable(new_loc)
                and ants.unoccupied(new_loc)
            ):
                ants.issue_order((ant_loc, direction))
                destinations.add(new_loc)
                return True
            return False

        # Join pre-pass: which claim-free ants would step into
        # contact this turn, and on whom. A foe drawing 2+
        # commitments releases equal TRADE steps for its committers
        # without hill cover; losing steps still always refuse.
        def contact_foe(nloc: tuple[int, int]) -> tuple[int, int] | None:
            best: tuple[int, int] | None = None
            best_d: int | None = None
            for e in enemy_locs:
                if self._sq(nloc, e) <= attack_r2:
                    d = ants.distance(nloc, e)
                    if best_d is None or d < best_d:
                        best_d = d
                        best = e
            return best

        commitments: dict[int, tuple[int, int]] = {}
        if enemy_locs:
            for cai, cant in enumerate(ants_list):
                if target.get(cai) is not None:
                    continue
                chase = _nearest_seek_enemy(cant, enemy_locs, ants.distance)
                if chase is None:
                    continue
                cstep = first_step(cant, chase)
                if cstep is None:
                    continue
                cfoe = contact_foe(ants.destination(cant, cstep))
                if cfoe is not None:
                    commitments[cai] = cfoe
        tally: dict[tuple[int, int], int] = {}
        for cfoe in commitments.values():
            tally[cfoe] = tally.get(cfoe, 0) + 1
        joined = {cai for cai, cfoe in commitments.items() if tally[cfoe] >= 2}

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
                # Tables8: packed ants press exactly like the base
                # (WIN and empty squares go; TRADE sacrifices go
                # under home-hill cover or when joined); packless
                # ants still take free kills and hill-covered
                # sacrifices, but never walk solo onto the contact
                # edge -- approaches through empty ground and
                # refused contacts pack up one table-safe step
                # toward the nearest friend instead. LOSE and
                # unjoined open-field trades fall through to
                # muster/reinforce/explore.
                foe = _nearest_seek_enemy(ant_loc, enemy_locs, ants.distance)
                if foe is not None:
                    step = first_step(ant_loc, foe)
                    if step is not None:
                        nloc = ants.destination(ant_loc, step)
                        verdict = self.contact_verdict(nloc, ant_loc)
                        packed = has_pack(ant_loc, ants_list, ants.distance)
                        if (
                            verdict == WIN
                            or (verdict == TRADE and (near_home(nloc) or ai in joined))
                            or (verdict == SAFE and packed)
                        ):
                            if try_move(ant_loc, step):
                                moved = True
                        elif not packed:
                            pal = min(
                                (f for f in ants_list if f != ant_loc),
                                key=lambda f: ants.distance(ant_loc, f),
                                default=None,
                            )
                            if pal is not None:
                                pstep = first_step(ant_loc, pal)
                                if pstep is not None and try_step(ant_loc, pstep):
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
                        and square_safe(new_loc, ant_loc)
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
        Ants.run(Tables8())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
