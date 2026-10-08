#!/usr/bin/env python
"""Ring: siege-ring hill assault over a pack-combat economy.

Only the challenger marches onto the muster hill square itself;
every other muster-bound ant takes a distinct passable orthogonal
neighbor (the ring) and holds it, so re-challenges start one step
away instead of a column away. The siege marches only with a quorum
(challenger + escort) and only inside MUSTER_RADIUS steps, except
a lone ant still races an open hill (no visible enemy within
RACE_RADIUS steps): racing empty hills is tempo, donating into
defenders is the loss. Farther hills wait for explore to close the
distance. Remembered hills get a grave check: a hill we see empty
(no hill reported while an ant stands in vision) is forgotten
instead of marched at. Food is a local harvest: only food within
FOOD_RADIUS steps is claimed, so distant treks never scatter the
pack -- except a deserted ant (nothing in range) still races its
nearest uncontested far food rather than diffusing. Picks skip squares held by other ants (never your own). A holder
stands only with backup (or
fearless while ahead on hills): a full ring backs every holder
and kills the defender, while a lone holder retreats instead of
donation-holding. Claim-free ants hunt only with a pack
(3+ friends within 10): packless ants pack up toward a friend,
packed hunters press fearlessly in small fights, focus the pack's
most popular prey instead of splitting duels, pairs join
committed attacks, friendless duels engage only while ahead,
extra guards screen razers at the halfway square, and equal
trades engage at 10 near friends. The anchor holds its home hill
on any fair-or-better contact (a 1v1 mutual kill saves the hill)
but never donates into a losing fight. Anchors are drafted by
nearness (nearest claim-free ant holds each threatened hill),
not loop order. Denial, challenger rotation,
reinforce, explore, and walk-off match Understudy.
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
# Local harvest: only claim food within this many steps. Distant
# food is left for explore/hunt/muster instead of cross-map treks.
FOOD_RADIUS = 20
# Muster quorum: the siege marches only with this many claim-free
# ants (challenger + escort). A lone ant reinforces safely instead
# of donating onto a defended hill.
MUSTER_QUORUM = 2
# Local muster: hills beyond this many steps get no marches at
# all. Explore, hunt, and the harvest close the distance first
# instead of cross-map donation treks.
MUSTER_RADIUS = 20
# Empty-hill race: below quorum, a lone ant still marches a hill
# with no visible enemy inside this radius. Racing empty hills is
# free tempo; donating into defenders is the loss.
RACE_RADIUS = 8


def ring_hill_open(
    hill: Loc,
    enemy_locs: list[Loc],
    distance: DistFn,
    radius: int = RACE_RADIUS,
) -> bool:
    # Whether a hill is raceable: no visible enemy within radius
    # steps of it. Pure: counts only, no side effects.
    return all(distance(hill, e) > radius for e in enemy_locs)


def ring_hill_gone(
    hill: Loc,
    ants_list: list[Loc],
    reported: set[Loc],
    viewradius2: int,
    sq_dist: SqDistFn,
) -> bool:
    # Whether a remembered hill is provably gone: unreported this
    # turn while an ant stands within vision of its square, so we
    # would see it if it stood. Out-of-view hills are kept --
    # absence there proves nothing. Pure: no side effects.
    if hill in reported:
        return False
    return any(sq_dist(ant, hill) <= viewradius2 for ant in ants_list)


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
    radius: int = FOOD_RADIUS,
) -> dict[int, Loc]:
    # Champion greedy everywhere, except contested clusters take
    # exactly DENIAL_CLAIMS ants on their nearest foods (distinct ants
    # and distinct foods, nearest pairs first); the cluster's other
    # foods stay unclaimed this turn instead of spreading one per food.
    # A one-food cluster can only draw one claimant.
    # Local harvest (Ring): only foods within radius steps are
    # claimed at all -- except the desert race below, where an ant
    # with nothing in range beelines uncontested far food. Distant
    # food is otherwise left for explorers, hunters, and the muster
    # to walk toward instead of cross-map treks that scatter the
    # pack and feed crowds piecemeal.
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
            if distance(ant, foods[fi]) <= radius
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
            d = distance(ant_loc, food_loc)
            if d <= radius:
                pairs.append((d, ai, fi))
    pairs.sort()
    for _, ai, fi in pairs:
        if fi in denied:
            continue
        if ai not in target and fi not in claimed:
            target[ai] = foods[fi]
            claimed.add(fi)
    for ai, ant_loc in enumerate(ants_list):
        # Desert race (Ring): an ant with no food inside the radius
        # beelines its nearest uncontested far food (no enemy within
        # RACE_RADIUS) instead of diffusing on explore. Contested
        # far food is ceded -- the ant stays free for hunt, muster,
        # and explore rather than donating down a long trek.
        if ai in target:
            continue
        if any(distance(ant_loc, food_loc) <= radius for food_loc in foods):
            continue
        order = sorted(range(len(foods)), key=lambda fi: distance(ant_loc, foods[fi]))
        for fi in order:
            if fi in claimed or fi in denied:
                continue
            if any(distance(foods[fi], foe) <= RACE_RADIUS for foe in enemy_locs):
                continue
            target[ai] = foods[fi]
            claimed.add(fi)
            break
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


def siege_slots(
    hill: Loc,
    passable: PassFn,
    rows: int,
    cols: int,
) -> list[Loc]:
    # The siege ring: passable orthogonal neighbors of an enemy
    # hill in fixed n, e, s, w order. Escorts hold these instead of
    # stacking behind the challenger. Water squares are skipped;
    # on a thin board a folded neighbor maps onto the hill itself
    # and is skipped too, so no slot ever equals the hill.
    slots: list[Loc] = []
    for dr, dc in ((-1, 0), (0, 1), (1, 0), (0, -1)):
        loc = ((hill[0] + dr) % rows, (hill[1] + dc) % cols)
        if loc != hill and passable(loc):
            slots.append(loc)
    return slots


def pick_siege_goal(
    ant_loc: Loc,
    hill: Loc,
    challenger: Loc | None,
    slots: list[Loc],
    claimed: set[Loc],
    occupied: set[Loc],
    distance: DistFn,
) -> Loc:
    # The challenger marches on the hill square itself; every other
    # ant takes its nearest still-unclaimed ring slot (ties keep
    # slot order, so the pick is deterministic). Squares held by
    # other ants are skipped -- stepping at an occupied square only
    # collides -- except the ant's own square, so a holder keeps
    # its station no matter the claim order. A full or missing
    # ring falls back to the hill: classic stacking. A slot sits
    # next to the hill, so even when the challenger eats instead
    # of marching, escorts detour by at most one step. Pure: reads
    # the claimed set, never mutates it.
    if ant_loc == challenger:
        return hill
    best: Loc | None = None
    best_d = 0
    for slot in slots:
        if slot in claimed:
            continue
        if slot in occupied and slot != ant_loc:
            continue
        d = distance(ant_loc, slot)
        if best is None or d < best_d:
            best = slot
            best_d = d
    return best if best is not None else hill


SEEK_RANGE = 8

# Equal trades (friends + 1 == enemies) need this many near
# friends (within 10 steps of the step) for the safety filter
# to accept them. Understudy tuned 14 on its scale; Ring tests
# 10 on ours, so crowded-board equal trades engage sooner.
EQUAL_TRADE_NEAR = 10

# Hunt only with a pack: an ant advances on a nearby enemy
# only with PACK_NEED+ friends within PACK_RADIUS steps, else
# it packs up toward its nearest friend. Fearless solo hunters
# donate into crowds.
PACK_NEED = 3
PACK_RADIUS = 10

# Fearless under ten enemies: packed hunters skip the safety
# filter on advancing moves in small fights and keep full
# safety in crowds. Donations happen in crowds, not duels.
CROWD_LIMIT = 10


def ring_nearest_foe(
    ant_loc: Loc, enemy_locs: list[Loc], distance: DistFn
) -> Loc | None:
    # Nearest visible enemy within SEEK_RANGE steps, else None.
    # Ties keep the first enemy in list order so the branch is
    # deterministic. Pure: no board state, no side effects.
    best: Loc | None = None
    best_d = SEEK_RANGE + 1
    for foe in enemy_locs:
        d = distance(ant_loc, foe)
        if d <= SEEK_RANGE and d < best_d:
            best_d = d
            best = foe
    return best


def ring_has_pack(
    ant_loc: Loc,
    ants_list: list[Loc],
    distance: DistFn,
    need: int = PACK_NEED,
    radius: int = PACK_RADIUS,
) -> bool:
    # Whether an ant holds a pack: need+ friends within radius
    # steps. The ant itself never counts. Pure, no side effects.
    found = 0
    for friend in ants_list:
        if friend == ant_loc:
            continue
        if distance(ant_loc, friend) <= radius:
            found += 1
            if found >= need:
                return True
    return False


def ring_contact_foe(
    dest: Loc, enemy_locs: list[Loc], sq_dist: SqDistFn, attack_r2: int
) -> Loc | None:
    # Nearest enemy within attack range of a planned step, else
    # None. A seek step landing here would fight that foe next
    # battle phase, so the move queues as a pack commitment on
    # it. Pure: no board state, no side effects.
    best: Loc | None = None
    best_d = attack_r2 + 1
    for foe in enemy_locs:
        d = sq_dist(dest, foe)
        if d <= attack_r2 and d < best_d:
            best_d = d
            best = foe
    return best


def ring_share_prey(
    prey: dict[int, Loc],
    ants_list: list[Loc],
    distance: DistFn,
    mate_radius: int = PACK_RADIUS,
    prey_range: int = SEEK_RANGE,
) -> dict[int, Loc]:
    # Focus fire: each hunter adopts its pack's most popular prey,
    # counting its own vote, so trios+ converge on one foe instead
    # of splitting 1v1s across adjacent foes. Ties hold the status
    # quo (pairs keep their own); only strict majorities flip, and
    # nearer preys win among those. Only pack-mates within
    # mate_radius vote, and only preys within prey_range of the
    # hunter are adoptable, so nobody treks. Single pass over the
    # original preys: no chaining, deterministic. Pure: no board
    # state, no side effects.
    shared = dict(prey)
    for ai, aloc in enumerate(ants_list):
        mine = prey.get(ai)
        if mine is None:
            continue
        votes: dict[Loc, int] = {}
        for aj, bloc in enumerate(ants_list):
            if aj == ai or aj not in prey:
                continue
            if distance(aloc, bloc) > mate_radius:
                continue
            cand = prey[aj]
            if distance(aloc, cand) > prey_range:
                continue
            votes[cand] = votes.get(cand, 0) + 1
        best = mine
        best_count = 1
        best_d = 0
        for cand, count in votes.items():
            d = distance(aloc, cand)
            if count > best_count or (count == best_count and d < best_d):
                best = cand
                best_count = count
                best_d = d
        shared[ai] = best
    return shared


def ring_joined(commitments: dict[int, Loc]) -> set[int]:
    # Ant indices released to attack: foes with 2+ committers.
    # Each commitment maps one ant index to the foe its planned
    # step would contact. A foe drawing two or more commitments
    # releases every committer, so the pair engages together;
    # lone committers stay out and fall back to safety. Pure.
    counts: dict[Loc, int] = {}
    for foe in commitments.values():
        counts[foe] = counts.get(foe, 0) + 1
    return {ai for ai, foe in commitments.items() if counts[foe] >= 2}


def ring_grinder_release(
    friends: int, enemies: int, my_army: int, enemy_army: int
) -> bool:
    # Engage a friendless duel only when the visible army
    # strictly outnumbers theirs; every other shape refuses.
    # Pure: integer compare, no side effects.
    return friends == 0 and enemies == 1 and my_army > enemy_army


def ring_fearless(enemy_count: int, limit: int = CROWD_LIMIT) -> bool:
    # Whether hunters advance fearlessly at this visible count.
    # True when fewer than limit enemies are visible, so the
    # seek branch skips the safety filter on the advancing move;
    # False in crowds, where full safety applies. Pure.
    return enemy_count < limit


def ring_defend_release(
    dest: Loc,
    ant_loc: Loc,
    ants_list: list[Loc],
    enemy_locs: list[Loc],
    sq_dist: SqDistFn,
    attack_r2: int,
) -> bool:
    # Defender's trade: the anchor holds its home hill on any
    # fair-or-better contact. A 1v1 (or backed) step onto the hill
    # kills the razer with the guard and saves the hill, which
    # mints ants; a strictly losing step still holds -- donating
    # into 1v3 saves nothing. Pure: counts only, no side effects.
    foes = 0
    for e in enemy_locs:
        if sq_dist(dest, e) <= attack_r2:
            foes += 1
    if foes == 0:
        return True
    backup = 0
    for f in ants_list:
        if f != ant_loc and sq_dist(dest, f) <= attack_r2:
            backup += 1
    return backup + 1 >= foes


def ring_intercept(
    hill: Loc,
    enemy_locs: list[Loc],
    distance: DistFn,
    passable: PassFn,
    rows: int,
    cols: int,
) -> Loc | None:
    # Off-hill intercept for one threatened home hill. Take the
    # nearest enemy to the hill, halve the toroidal approach,
    # and return the nearest passable square to that midpoint
    # (the midpoint itself when open). No enemies -- or no
    # passable square on the whole board -- returns None so the
    # caller holds the fallback. Pure: no board state.
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
class Ring:
    def __init__(self):
        # define class level variables, will be remembered between turns
        self.visits: dict[tuple[int, int], int] = {}
        self.remembered_hills: set[tuple[int, int]] = set()
        self.prev_enemies: list[tuple[int, int]] = []
        self.last_challenger: dict[tuple[int, int], tuple[int, int]] = {}
        self.last_target: tuple[int, int] | None = None

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

    # do turn is run once per turn
    # the ants class has the game state and is updated by the Ants.run method
    # it also has several helper methods to use
    def do_turn(self, ants: Ants):
        # Siege ring over a pack-combat economy: the muster march
        # surrounds the hill -- the challenger takes the hill square
        # itself while each escort holds a distinct passable neighbor
        # with backup (lone holders retreat), so re-challenges start
        # one step away instead of a column away. Claim-free ants
        # hunt only with a pack: packless ants pack up, packed
        # hunters press small fights fearlessly, pairs join committed
        # attacks, friendless duels engage only while ahead, extra
        # guards screen razers at the halfway square, and equal
        # trades engage at 10 near friends. The anchor holds its
        # home hill on any fair-or-better contact (a 1v1 mutual kill
        # saves the hill) but never donates into a losing fight.
        # Denial, challenger rotation, reinforce, explore, and
        # walk-off match Understudy; food is a local harvest, the
        # muster needs a quorum unless the hill is open, and graves
        # are forgotten (see helpers).
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
            radius=FOOD_RADIUS,
        )
        attack_r2 = ants.attackradius2 or 5
        rows, cols = ants.rows, ants.cols

        def sq_dist(a: tuple[int, int], b: tuple[int, int]) -> int:
            dr = abs(a[0] - b[0])
            dr = min(dr, rows - dr) if rows else dr
            dc = abs(a[1] - b[1])
            dc = min(dc, cols - dc) if cols else dc
            return dr * dr + dc * dc

        reported: set[tuple[int, int]] = set()
        for hloc, _ in ants.enemy_hills():
            self.remembered_hills.add(hloc)
            reported.add(hloc)
        seen2 = getattr(ants, "viewradius2", 0) or 93
        for hloc in list(self.remembered_hills):
            if hloc in my_set:
                self.remembered_hills.discard(hloc)
            elif ring_hill_gone(hloc, ants_list, reported, seen2, sq_dist):
                # Grave check: we see the square and no hill stands
                # there -- someone else razed it, so forget it
                # instead of marching the siege at rubble.
                self.remembered_hills.discard(hloc)
        hills = sorted(self.remembered_hills)
        my_hills = ants.my_hills()
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
        # Nearest-anchor drafting: each threatened hill is held by
        # its nearest claim-free ant, stable across turns instead
        # of loop-order. Blocked harvesters and overflow hills fall
        # back to first-come below; everyone else screens.
        anchor_for: dict[tuple[int, int], int] = {}
        drafted: set[int] = set()
        for h in sorted(threatened):
            best_ai = -1
            best_d = 0
            for cai, cant in enumerate(ants_list):
                if cai in drafted or target.get(cai) is not None:
                    continue
                d = ants.distance(cant, h)
                if best_ai < 0 or d < best_d:
                    best_ai = cai
                    best_d = d
            if best_ai >= 0:
                anchor_for[h] = best_ai
                drafted.add(best_ai)

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
            # Crowded-board equal trades engage sooner: 10 near
            # friends accept them, down from Understudy's 14.
            return near >= EQUAL_TRADE_NEAR and friends + 1 >= enemies

        step_cache: dict[tuple[tuple[int, int], tuple[int, int]], str | None] = {}

        def first_step(
            start: tuple[int, int], goal: tuple[int, int], budget: int = 250
        ) -> str | None:
            # Shortest passable path around water; return its first step.
            # Per-turn cache: passability never changes mid-turn, so a
            # repeated (start, goal) lookup replays the same step and
            # crowded armies share muster/hunt paths instead of
            # re-running the BFS per ant.
            if start == goal:
                return None
            key = (start, goal)
            if key in step_cache:
                return step_cache[key]
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
                step_cache[key] = None
                return None
            node = goal
            while parent[node][0] != start:
                node = parent[node][0]
            step_cache[key] = parent[node][1]
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
            # Committed-join: the pack already holds this foe, so
            # an equal trade goes through without the near gate.
            # Strictly losing fights still hold. Passable,
            # occupancy, and destination clashes check as usual.
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

        # Prey-sharing pre-pass: packed hunters focus the pack's
        # most popular prey instead of splitting 1v1s. The join set
        # below commits on the shared preys, so pairs pile onto one
        # foe together.
        prey0: dict[int, Loc] = {}
        if enemy_locs:
            for pai, pant in enumerate(ants_list):
                if target.get(pai) is not None:
                    continue
                pf = ring_nearest_foe(pant, enemy_locs, ants.distance)
                if pf is not None:
                    prey0[pai] = pf
        shared_prey = ring_share_prey(prey0, ants_list, ants.distance)
        # Join pre-pass: which claim-free ants would step into
        # contact this turn, and on whom. The join set holds the
        # ants whose foe draws 2+ commitments.
        commitments: dict[int, Loc] = {}
        if enemy_locs:
            for cai, cant in enumerate(ants_list):
                if target.get(cai) is not None:
                    continue
                chase = shared_prey.get(
                    cai, ring_nearest_foe(cant, enemy_locs, ants.distance)
                )
                if chase is None:
                    continue
                cstep = first_step(cant, chase)
                if cstep is None:
                    continue
                cloc = ants.destination(cant, cstep)
                cfoe = ring_contact_foe(cloc, enemy_locs, sq_dist, attack_r2)
                if cfoe is not None:
                    commitments[cai] = cfoe
        joined = ring_joined(commitments)

        destinations: set[tuple[int, int]] = set()
        held: list[tuple[int, int]] = []
        anchored: set[tuple[int, int]] = set()
        # Muster quorum: the siege marches only with challenger +
        # escort. A lone claim-free ant skips the muster and falls
        # through to a safe reinforce instead of donating.
        n_march = sum(
            1
            for mai, mant in enumerate(ants_list)
            if target.get(mai) is None and mant != understudy_out
        )
        # Empty-hill race: below quorum, an open muster hill (no
        # visible enemy within RACE_RADIUS) still draws marches.
        # Racing empty hills is tempo; the quorum only stops
        # donations into defenders.
        muster_open = muster_hill is not None and ring_hill_open(
            muster_hill, enemy_locs, ants.distance
        )
        # Siege ring around the muster hill, computed once per turn.
        # Escorts claim distinct slots as the loop reaches them.
        siege = (
            siege_slots(muster_hill, ants.passable, rows, cols)
            if muster_hill is not None
            else []
        )
        claimed_slots: set[tuple[int, int]] = set()
        occupied = set(ants_list)
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
                # No food or blocked: the drafted anchor holds the
                # hill while extras screen the razer off it at the
                # halfway square, so the hill stays spawnable.
                # Undrafted hills (overflow) fall back to first-come.
                nearest = min(threatened, key=lambda h: ants.distance(ant_loc, h))
                draft = anchor_for.get(nearest)
                anchor = (nearest not in anchored) if draft is None else draft == ai
                if not anchor:
                    inter = ring_intercept(
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
                elif step is not None and anchor:
                    # Defender's trade: the anchor holds its hill on
                    # a fair-or-better contact. The safe filter
                    # refuses 1v1s, but a mutual kill saves the hill
                    # and the hill mints ants; strictly losing steps
                    # still hold.
                    hold = ants.destination(ant_loc, step)
                    if (
                        hold not in destinations
                        and ants.passable(hold)
                        and ants.unoccupied(hold)
                        and ring_defend_release(
                            hold,
                            ant_loc,
                            ants_list,
                            enemy_locs,
                            sq_dist,
                            attack_r2,
                        )
                    ):
                        ants.issue_order((ant_loc, step))
                        destinations.add(hold)
                        moved = True
            if not moved and enemy_locs:
                # Hunt only with a pack, fearless in small fights.
                # A packless ant never advances -- it packs up one
                # step toward its nearest friend instead, under the
                # normal filter. Packed hunters chase the shared
                # prey (focus fire), falling back to their own
                # nearest foe.
                foe = shared_prey.get(
                    ai, ring_nearest_foe(ant_loc, enemy_locs, ants.distance)
                )
                if foe is not None and not ring_has_pack(
                    ant_loc, ants_list, ants.distance
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
                    foe = None
                if foe is not None:
                    # Packed: fearless ahead while fewer than
                    # CROWD_LIMIT enemies are visible -- the
                    # advancing step skips the safety filter. In
                    # crowds a joined ant (its foe drew 2+
                    # commitments) engages with equal trades
                    # allowed; an unjoined ant on a friendless 1v1
                    # contact engages only while the visible army
                    # leads, otherwise the safe step holds.
                    step = first_step(ant_loc, foe)
                    if step is not None:
                        if ring_fearless(len(enemy_locs)):
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
                            if ring_grinder_release(
                                pals, foes, len(ants_list), len(enemy_locs)
                            ):
                                if try_join(ant_loc, step):
                                    moved = True
                            elif try_step(ant_loc, step):
                                moved = True
            if (
                not moved
                and hills
                and muster_hill is not None
                and ant_loc != understudy_out
                and ants.distance(ant_loc, muster_hill) <= MUSTER_RADIUS
                and (n_march >= MUSTER_QUORUM or muster_open)
            ):
                # Siege: the challenger marches on the hill itself
                # while each escort takes its nearest free ring slot
                # instead of stacking in column. An escort already
                # standing on its slot holds station, so the next
                # re-challenge starts one step away. Hunt always;
                # fearless when ahead on hills, as before. Below
                # quorum a defended hill stands the muster down and
                # lone ants fall through to a safe reinforce; an
                # open hill still draws the race (muster_open).
                goal = pick_siege_goal(
                    ant_loc,
                    muster_hill,
                    challenger,
                    siege,
                    claimed_slots,
                    occupied,
                    ants.distance,
                )
                if goal != muster_hill:
                    claimed_slots.add(goal)
                # Garrison bravery: a holder stands only with backup
                # (or fearless while ahead on hills). A full ring backs
                # every holder 4v1 and kills the defender; a lone holder
                # just donates, so it falls through and retreats.
                holds_ring = (
                    ant_loc == goal
                    and goal != muster_hill
                    and (len(my_hills) > len(hills) or is_safe(goal, ant_loc))
                )
                if holds_ring:
                    moved = True
                # else: death trap; reinforce/explore below retreats.
                if not moved:
                    step = first_step(ant_loc, goal)
                    if step is not None and try_step(
                        ant_loc, step, safe=len(my_hills) <= len(hills)
                    ):
                        moved = True
            if not moved and hills:
                # No hill move: reinforce the second-nearest hill,
                # but only inside the muster radius -- farther hills
                # wait for explore to close the distance.
                ordered = sorted(hills, key=lambda h: ants.distance(ant_loc, h))
                near = ordered[1] if len(ordered) > 1 else ordered[0]
                if (
                    not (ant_loc == understudy_out and near == muster_hill)
                    and ants.distance(ant_loc, near) <= MUSTER_RADIUS
                ):
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
        if muster_hill is not None and challenger is not None:
            self.last_challenger[muster_hill] = challenger
        for old in list(self.last_challenger):
            if old != muster_hill and old not in self.remembered_hills:
                del self.last_challenger[old]
        self.last_target = muster_hill
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
        Ants.run(Ring())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
