#!/usr/bin/env python
"""Ghost memory, posture, pack joins, lead-pack, press, and soft-cede (Tables6).

Tables6 keeps the Tables core -- setup-precomputed battle tables with
pure-lookup contact verdicts -- and adds a memory-plus-posture mix
no repo bot has: decaying ghost memory (a vanished foe lingers
GHOST_TTL turns and still counts a foe near its last square),
army-posture trade gating (ahead goes AGGRESSIVE and takes mutual
trades anywhere, behind goes DEFENSIVE and refuses even hill-covered
trades, tied keeps the EXCHANGE hill gate; no visible enemies never
leaves EXCHANGE so ghosts get no free pass), pack-gated table joins
(claim-free ants whose seek steps contact the same live foe commit
on it, and 2+ committers engage every non-losing contact together;
losing contacts always refuse), lead-pack discipline (a packless
ahead seeker -- fewer than PACK_NEED friends within PACK_RADIUS --
packs up toward its nearest friend instead of dueling solo),
small-fight press (a packed seeker presses non-losing contacts while
fewer than SMALL_FIGHT_LIMIT enemies are visible, even without hill
cover; crowds keep full safety and DEFENSIVE never presses),
haunted-hill guard (ghosts near a home hill keep it threatened),
defensive packing (behind with nothing to do, ants consolidate
instead of wandering), and fresh-ghost investigation (idle ants take
one guarded step toward an age-1 lead), plus posture-scaled denial
(contested food draws 3 claimants when ahead, 1 when behind).
Friendless 1v1 sacrifices (mutual-death trades) are therefore allowed
under hill cover when tied, anywhere when ahead and packed, nowhere
when behind -- except a converging pair, which engages together,
a packed small-fight trade, which presses, and a crowd-backed trade
(10+ friends within 10 steps of the step), which goes at any
posture. Contested food draws posture-scaled denial claims (3/2/1),
except a lost race soft-cedes: no claimants, foods open to fair
greedy gathering.

Guard (hold plus off-hill screen), muster, reinforce, explore, and
walk-off match the Tables base; the combat core and the denial
economy carry the new mix. Self-contained: stdlib plus ants.py
only, never combat.py.
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


# Army posture: how the lookup table reads a mutual TRADE.
AGGRESSIVE = "AGGRESSIVE"
DEFENSIVE = "DEFENSIVE"
EXCHANGE = "EXCHANGE"

# Ghost memory: turns a vanished foe still counts near its square.
GHOST_TTL = 3


def posture(ours: int, theirs: int) -> str:
    """Table-reading mode from visible army parity.

    Ahead trades anywhere, behind only takes clean wins, tied keeps
    the hill gate. Zero visible enemies never reads aggressive so a
    lingering ghost cannot open a free pass. Pure: integer compares.
    """
    if theirs <= 0:
        return EXCHANGE
    if ours > theirs:
        return AGGRESSIVE
    if ours < theirs:
        return DEFENSIVE
    return EXCHANGE


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


# Posture-scaled denial pressure: contested clusters draw more
# claimants when ahead (starve the enemy) and fewer when behind
# (save bodies); tied keeps the Tables pair.
PRESS_CLAIMS = DENIAL_CLAIMS + 1
CEDE_CLAIMS = DENIAL_CLAIMS - 1

# Lead-pack discipline: an ahead ant holds a pack with PACK_NEED+
# friends within PACK_RADIUS steps; a packless ahead seeker packs
# up toward its nearest friend instead of bleeding solo 1v1s.
# Tied and behind ants keep the Tables rules (hill-gated refusal
# plus explore, defensive packing). A converging pair still hunts
# through the join below, pack or no pack.
PACK_NEED = 2
PACK_RADIUS = 10

# Small-fight press: while fewer than SMALL_FIGHT_LIMIT enemies are
# visible, a packed seeker presses non-losing contacts even without
# hill cover. Big crowds keep full table safety, and DEFENSIVE never
# presses; LOSE never presses at any count.
SMALL_FIGHT_LIMIT = 10

# Backed-trade near gate: a TRADE with BACKED_NEED+ friends within
# BACKED_RADIUS steps of the step advances at any posture -- the
# ring backs the parity while reinforcements stand near. LOSE still
# refuses everywhere.
BACKED_NEED = 10
BACKED_RADIUS = 10


def backed_by(
    dest: Loc,
    self_loc: Loc,
    ants_list: list[Loc],
    distance: DistFn,
    need: int = BACKED_NEED,
    radius: int = BACKED_RADIUS,
) -> bool:
    """Whether a step carries crowd backing: need+ friends in radius.

    Counts friends (never the mover) within radius steps of the
    destination square. Pure: no board state, no side effects.
    """
    found = 0
    for friend in ants_list:
        if friend == self_loc:
            continue
        if distance(dest, friend) <= radius:
            found += 1
            if found >= need:
                return True
    return False


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


def contact_foe(
    dest: Loc,
    enemy_locs: list[Loc],
    sq_dist: Callable[[Loc, Loc], int],
    attack_r2: int,
) -> Loc | None:
    """Nearest live enemy within attack range of a planned step.

    A seek step landing here would fight that foe next battle phase,
    so the move queues as a pack commitment on it. Ghosts never draw
    commitments: only visible foes count. Ties keep the first enemy
    in list order so the branch is deterministic. Pure.
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

    Each commitment maps one ant index to the live foe its planned
    step would contact. A foe drawing two or more commitments
    releases every committer, so the pair engages together; lone
    committers stay out and fall back to table safety. Pure.
    """
    counts: dict[Loc, int] = {}
    for foe in commitments.values():
        counts[foe] = counts.get(foe, 0) + 1
    return {ai for ai, foe in commitments.items() if counts[foe] >= 2}


def cluster_lost(
    group: list[int],
    foods: list[Loc],
    ants_list: list[Loc],
    enemy_locs: list[Loc],
    distance: DistFn,
) -> bool:
    """Whether the enemy wins the race to a contested cluster.

    Lost when a foe reaches some cluster food strictly sooner than
    any ant reaches any cluster food; ties and leads fight on.
    Pure: distance compares only.
    """
    ant_best = min(distance(ant, foods[fi]) for ant in ants_list for fi in group)
    foe_best = min(distance(foe, foods[fi]) for foe in enemy_locs for fi in group)
    return foe_best < ant_best


def assign_food_targets(
    ants_list: list[Loc],
    foods: list[Loc],
    enemy_locs: list[Loc],
    distance: DistFn,
    rows: int,
    cols: int,
    claims: int = DENIAL_CLAIMS,
) -> dict[int, Loc]:
    # Champion greedy everywhere, except contested clusters take
    # exactly `claims` ants on their nearest foods (distinct ants
    # and distinct foods, nearest pairs first); the cluster's other
    # foods stay unclaimed this turn instead of spreading one per food.
    # A one-food cluster can only draw one claimant. A lost cluster
    # (the enemy wins the race) is soft-ceded: no claimants, and its
    # foods stay open to fair greedy gathering.
    target: dict[int, Loc] = {}
    if not foods or not ants_list:
        return target
    claimed: set[int] = set()
    denied: set[int] = set()
    for group in denied_food_groups(foods, enemy_locs, distance, rows, cols):
        if cluster_lost(group, foods, ants_list, enemy_locs, distance):
            # Soft-cede: a lost cluster draws no denial claimants
            # and its foods stay open to fair greedy gathering below
            # instead of starving behind the block.
            continue
        denied.update(group)
        picks = 0
        ordered = sorted(
            (distance(ant, foods[fi]), ai, fi)
            for ai, ant in enumerate(ants_list)
            for fi in group
        )
        for _, ai, fi in ordered:
            if picks >= claims:
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
class Tables6:
    def __init__(self):
        # define class level variables, will be remembered between turns
        self.visits: dict[tuple[int, int], int] = {}
        self.remembered_hills: set[tuple[int, int]] = set()
        self.prev_enemies: list[tuple[int, int]] = []
        # Ghost memory: vanished-foe square -> unseen turn count.
        self.ghosts: dict[tuple[int, int], int] = {}
        # Precomputed battle-resolution tables (codetiger): built
        # once here so tests driving do_turn directly get lookups.
        self.battle_table = build_battle_table()
        # Cached per-turn board state for contact_verdict.
        self._ants_list: list[Loc] = []
        self._enemy_locs: list[Loc] = []
        self._home_hills: list[Loc] = []
        self._posture: str = EXCHANGE
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
        self.ghosts = {}
        self.battle_table = build_battle_table()
        self._ants_list = []
        self._enemy_locs = []
        self._home_hills = []
        self._posture = EXCHANGE
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
        setup-precomputed battle table. When no live foe sits in
        radius, one lingering ghost square still counts a foe, so
        last-known contacts read as trades until the memory fades.
        Never re-derives battle math live: dict-lookup scale, far
        under 0.1ms per call.
        """
        foes = 0
        for e in self._enemy_locs:
            if self._sq(dest, e) <= self._attack_r2:
                foes += 1
        if foes == 0:
            for g in self.ghosts:
                if self._sq(dest, g) <= self._attack_r2:
                    foes = 1
                    break
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
        # Tables6: Tables economy, muster, guard, explore, and
        # walk-off, with ghost-aware table lookups, posture-gated
        # trades, pack-gated table joins, and lead-pack discipline.
        #         # WIN and empty squares advance; a joined pair engages every
        # non-losing contact together; other mutual TRADE goes
        # anywhere when AGGRESSIVE and packed (a packless ahead
        # seeker packs up instead), only under home-hill cover
        # (within HILL_SACRIFICE_RADIUS) when EXCHANGE -- except a
        # packed seeker presses non-losing contacts while the visible
        # war stays small (fewer than SMALL_FIGHT_LIMIT enemies) --
        # and nowhere when DEFENSIVE; LOSE always falls through.
        # Food, guard, muster, reinforce, explore, and walk-off
        # match Tables.
        foods = ants.food()
        ants_list = ants.my_ants()
        my_set = set(ants_list)
        enemy_locs = [loc for loc, _ in ants.enemy_ants()]
        # Posture scales denial pressure: press contested food when
        # ahead, cede it when behind, pair it when tied.
        stance = posture(len(ants_list), len(enemy_locs))
        if stance == AGGRESSIVE:
            claims = PRESS_CLAIMS
        elif stance == DEFENSIVE:
            claims = CEDE_CLAIMS
        else:
            claims = DENIAL_CLAIMS
        target = assign_food_targets(
            ants_list,
            foods,
            enemy_locs,
            ants.distance,
            ants.rows,
            ants.cols,
            claims=claims,
        )
        for hloc, _ in ants.enemy_hills():
            self.remembered_hills.add(hloc)
        for hloc in list(self.remembered_hills):
            if hloc in my_set:
                self.remembered_hills.discard(hloc)
        hills = sorted(self.remembered_hills)
        my_hills = ants.my_hills()
        # Snapshot last turn's enemies before the heading match
        # below overwrites them; the ghost update needs the old set.
        last_enemies = self.prev_enemies
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

        attack_r2 = ants.attackradius2 or 5
        rows, cols = ants.rows, ants.cols
        # Ghost memory: age lingering squares, drop the expired,
        # forget resighted foes, and register the newly vanished.
        visible = set(enemy_locs)
        aged: dict[tuple[int, int], int] = {}
        for gloc, age in self.ghosts.items():
            if gloc not in visible and age + 1 <= GHOST_TTL:
                aged[gloc] = age + 1
        for ploc in last_enemies:
            if ploc not in visible and ploc not in aged:
                aged[ploc] = 1
        self.ghosts = aged
        threatened = [
            h
            for h in my_hills
            if any(
                ants.distance(h, e) <= 10
                or (ants.distance(h, e) <= 16 and closing(e, h))
                for e in enemy_locs
            )
            # Haunted: a fresh ghost near the hill keeps the guard.
            or any(ants.distance(h, g) <= 10 for g in self.ghosts)
        ]
        # Cache turn state so contact_verdict stays a bare lookup.
        self._ants_list = ants_list
        self._enemy_locs = enemy_locs
        self._home_hills = my_hills
        self._posture = posture(len(ants_list), len(enemy_locs))
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
            # Posture-gated safety: WIN and empty squares pass, LOSE
            # refuses; TRADE passes anywhere when AGGRESSIVE, only
            # under hill cover when EXCHANGE, nowhere when DEFENSIVE.
            verdict = self.contact_verdict(nloc, self_loc)
            if verdict in (SAFE, WIN):
                return True
            if verdict == LOSE:
                return False
            if self._posture == AGGRESSIVE:
                return True
            if self._posture == DEFENSIVE:
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

        # Join pre-pass: claim-free ants whose seek step lands in
        # contact with a live foe commit on it; foes drawing 2+
        # commitments release every committer to engage together.
        commitments: dict[int, Loc] = {}
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
                cloc = ants.destination(cant, cstep)
                cfoe = contact_foe(cloc, enemy_locs, self._sq, attack_r2)
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
                # Tables6: advance on the nearest foe within range;
                # the ghost-aware table clears the step. WIN and
                # empty squares go fearlessly; a joined pair engages
                # every non-losing contact together; otherwise TRADE
                # follows posture (anywhere / hill cover / nowhere),
                # except a packless ahead seeker packs up toward its
                # nearest friend instead of dueling solo, a packed
                # seeker presses non-losing contacts in small fights,
                # and a crowd-backed step (10+ friends within 10)
                # goes at any posture. LOSE always falls through to
                # muster/reinforce/explore.
                foe = _nearest_seek_enemy(ant_loc, enemy_locs, ants.distance)
                if foe is not None:
                    step = first_step(ant_loc, foe)
                    if step is not None:
                        nloc = ants.destination(ant_loc, step)
                        verdict = self.contact_verdict(nloc, ant_loc)
                        if verdict in (SAFE, WIN):
                            if try_move(ant_loc, step):
                                moved = True
                        elif ai in joined:
                            if verdict != LOSE and try_move(ant_loc, step):
                                moved = True
                        elif (
                            verdict == TRADE
                            and self._posture == AGGRESSIVE
                            and not has_pack(ant_loc, ants_list, ants.distance)
                        ):
                            pal = min(
                                (f for f in ants_list if f != ant_loc),
                                key=lambda f: ants.distance(ant_loc, f),
                                default=None,
                            )
                            if pal is not None:
                                pstep = first_step(ant_loc, pal)
                                if pstep is not None and try_step(ant_loc, pstep):
                                    moved = True
                        else:
                            cleared = verdict == TRADE and (
                                self._posture == AGGRESSIVE
                                or (self._posture == EXCHANGE and near_home(nloc))
                                or (
                                    self._posture == EXCHANGE
                                    and len(enemy_locs) < SMALL_FIGHT_LIMIT
                                    and has_pack(ant_loc, ants_list, ants.distance)
                                )
                                or backed_by(nloc, ant_loc, ants_list, ants.distance)
                            )
                            if cleared and try_move(ant_loc, step):
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
            if not moved and not any(
                ants.distance(ant_loc, e) <= SEEK_RANGE for e in enemy_locs
            ):
                # Memory lead: one step toward a fresh (age-1) ghost
                # under the normal filter when no live foe is close
                # enough to hunt; live refusals never reach here,
                # and stale leads fall through to explore.
                fresh = [g for g, age in self.ghosts.items() if age <= 1]
                if fresh:
                    lead = min(fresh, key=lambda g: ants.distance(ant_loc, g))
                    gstep = first_step(ant_loc, lead)
                    if gstep is not None and try_step(ant_loc, gstep):
                        moved = True
            if not moved and self._posture == DEFENSIVE and len(ants_list) > 1:
                # Behind: consolidate -- pack one step toward the
                # nearest friend under the normal filter instead of
                # wandering outward alone.
                pal = min(
                    (f for f in ants_list if f != ant_loc),
                    key=lambda f: ants.distance(ant_loc, f),
                    default=None,
                )
                if pal is not None:
                    pstep = first_step(ant_loc, pal)
                    if pstep is not None and try_step(ant_loc, pstep):
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
        Ants.run(Tables6())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
