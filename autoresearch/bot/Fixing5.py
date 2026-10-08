#!/usr/bin/env python
"""crowd-gated anthonyvh greedy sequential fixing combat.

Fresh entry: Crowd's economy, muster, guard, and explore
byte-identical; the combat core is the faithful anthonyvh port
(Memetix-style influence plus greedy sequential fixing,
stationary enemies pinned first, suicide only to unblock a hill
rush), gated the Crowd way: a combat ant without a pack (3+
friends within 10 steps) never pins a solo attack -- it rallies
toward its nearest friend instead -- and while fewer than 10
enemies show, KILL takes press without waiting for a hill push
(full champion safety in crowds), outranking SAFE retreats while
the visible army leads (the extra ant wins the fight). A packless
ant whose only acceptable move unblocks this turn's hill rush
still pins the suicide: the rush outranks the pack. Self-contained: stdlib plus
ants.py only.

Complexity per turn: one influence pass O(E*R^2) over the visible
enemies (R = threat reach, 3 at attackradius2 5), one pack census
O(A^2) over our ants, then one greedy fix over the packed combat
ants -- most-constrained-first pops from a lazy bucketed queue in
O(1) amortized, and each pin re-scores only the neighbors within
R+1 steps (4 table lookups each) via incremental support stamps
instead of recomputing the field. Total
O(E*R^2 + A^2 + A*(4 + neighbors*4)) for A combat ants: no 5^A
exact search (rejected past 10-ant zones, per anthonyvh) and no
full recompute per pin. Measured under 10 ms per fight; anthonyvh
cut 200 ms to 5-10 ms the same way.
"""

from collections import deque
from collections.abc import Callable

from ants import Ants

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]
PassFn = Callable[[Loc], bool]
DestFn = Callable[[Loc, str], Loc]
UnoccFn = Callable[[Loc], bool]

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
# anthonyvh greedy sequential fixing -- combat core (no combat.py).
#
# Influence first: each square rates how many enemies could attack it
# after one move (toroidal manhattan diamond of threat_reach around
# each enemy -- the Memetix single pass). Stationary enemies stamp
# first as the fixed points of the field. Then greedy sequential
# fixing: our combat ants pin most-constrained-first (fewest
# acceptable moves; hotter squares and list order break ties), each
# ant taking its best move given the already-pinned ants, with only
# neighbors re-scored after each pin through incremental support
# stamps (no full recompute) ordered by a lazy bucketed queue (no
# 5^A search). Suicide -- issuing a DIE order -- is allowed if and
# only if its square unblocks this turn's hill rush.

# Combat trigger horizon: claim-free ants with an enemy inside it
# resolve here; the same population the champion pre-pass screened.
SEEK_RANGE = 8

# Pack gate: a combat ant advances only with PACK_NEED+ friends
# within PACK_RADIUS steps, else it rallies toward its nearest
# friend instead of donating solo into the fight.
PACK_NEED = 3
PACK_RADIUS = 10

# Fearless gate: fewer than CROWD_LIMIT visible enemies press
# KILL takes without a hill push; crowds keep full safety. While
# the visible army leads, pressed KILL takes outrank SAFE retreats.
CROWD_LIMIT = 10

# Odds gate, kept for the champion safety filter on food, guard, and
# explore steps: equal trades (friends + 1 == enemies) need this many
# near friends (within 10 steps). Champion tuned 14; Crowd tests 10.
EQUAL_TRADE_NEAR = 10

# Influence verdicts for one planned step. DIE refuses exactly as a
# losing fight; KILL trades 1-for-1 to break deadlocks while pushing
# a hill or pressing a fearless small fight; SAFE keeps champion
# pressure.
SAFE = "SAFE"
KILL = "KILL"
DIE = "DIE"

_DIRS = ("n", "e", "s", "w")


def has_pack(ant: Loc, ants_list: list[Loc], distance: DistFn) -> bool:
    """Whether an ant holds a pack: PACK_NEED+ friends in radius.

    The ant itself never counts toward its own pack. Pure: no board
    state, no side effects.
    """
    found = 0
    for friend in ants_list:
        if friend == ant:
            continue
        if distance(ant, friend) <= PACK_RADIUS:
            found += 1
            if found >= PACK_NEED:
                return True
    return False


def threat_reach(attack_r2: int) -> int:
    """Manhattan threat radius of one enemy after it moves one step.

    Attack reach is the floor square root of attackradius2, plus the
    one square the enemy may step before attacking.
    """
    return int(attack_r2**0.5) + 1


def _stamp(field: list[list[int]], foe: Loc, rows: int, cols: int, reach: int) -> None:
    """Stamp one enemy's toroidal threat diamond onto the field."""
    for dr in range(-reach, reach + 1):
        width = reach - abs(dr)
        row = field[(foe[0] + dr) % rows]
        for dc in range(-width, width + 1):
            row[(foe[1] + dc) % cols] += 1


def influence_field(
    enemy_locs: list[Loc], rows: int, cols: int, reach: int
) -> list[list[int]]:
    """Per-square count of enemies within reach manhattan steps.

    One pass: each enemy stamps its toroidal diamond once, so the
    whole crowded board costs far under a millisecond.
    """
    field = [[0] * cols for _ in range(rows)]
    if reach < 0 or rows <= 0 or cols <= 0:
        return field
    for foe in enemy_locs:
        _stamp(field, foe, rows, cols, reach)
    return field


def classify_step(field: list[list[int]], dest: Loc, friends: int) -> str:
    """Verdict for a planned step onto dest with friends backing it.

    Ours is friends + 1 (the moving ant): DIE when enemy influence
    strictly exceeds us, KILL when equal (expect a 1-for-1), SAFE
    when we lead.
    """
    theirs = field[dest[0]][dest[1]]
    ours = friends + 1
    if theirs > ours:
        return DIE
    if theirs == ours:
        return KILL
    return SAFE


def stationary_pins(
    prev_enemies: list[Loc], cur_enemies: list[Loc], distance: DistFn
) -> list[Loc]:
    """Visible enemies that did not move since last turn, in order.

    Matches each current enemy to an unmatched last-turn position
    within 1 step (the same rule do_turn's headings use); a match at
    distance 0 is the same ant holding still. These pin first during
    evaluation as the fixed points of the field.
    """
    unmatched = list(prev_enemies)
    pinned = []
    for cur in cur_enemies:
        match = None
        match_d = 2
        for prev in unmatched:
            d = distance(cur, prev)
            if d < match_d:
                match_d = d
                match = prev
        if match is not None:
            unmatched.remove(match)
            if match == cur:
                pinned.append(cur)
    return pinned


def unblocks_hill_rush(ant: Loc, dest: Loc, hills: list[Loc], distance: DistFn) -> bool:
    """Whether stepping onto dest opens this turn's hill rush.

    True iff dest sits strictly closer than the ant to a contested
    (remembered) enemy hill: the death square still moves the rush
    forward. Empty hills never unblock, so peacetime suicides refuse.
    """
    return any(distance(dest, hill) < distance(ant, hill) for hill in hills)


def intercept_square(
    hill: Loc,
    enemy_locs: list[Loc],
    distance: DistFn,
    passable: PassFn,
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
    caller holds the champion fallback.
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


def add_support(
    support: dict[Loc, int], dest: Loc, rows: int, cols: int, attack_r2: int
) -> None:
    """Stamp one pinned ant's backing onto its attack disc, in place.

    The incremental local update: only squares this pin touches are
    written, so later ants re-evaluate against pinned support without
    recomputing anything. Attack discs are square-distance, matching
    the battle resolution the old safety filter approximates.
    """
    rad = int(attack_r2**0.5)
    for dr in range(-rad, rad + 1):
        for dc in range(-rad, rad + 1):
            if dr * dr + dc * dc <= attack_r2:
                sq = ((dest[0] + dr) % rows, (dest[1] + dc) % cols)
                support[sq] = support.get(sq, 0) + 1


def acceptable_moves(
    ant: Loc,
    field: list[list[int]],
    support: dict[Loc, int],
    hills: list[Loc],
    distance: DistFn,
    destination: DestFn,
    passable: PassFn,
    unoccupied: UnoccFn,
    fearless: bool = False,
) -> list[str]:
    """Pinnable step directions for one ant, in n/e/s/w order.

    A step is acceptable when legal (passable, unoccupied) and SAFE,
    or KILL while pushing a remembered hill (the deadlock break) or
    while fearless presses a small fight, or DIE when its square
    unblocks this turn's hill rush (the only allowed suicide).
    Staying never pins: a held ant falls through to muster exactly
    as a refused seek does.
    """
    moves = []
    for direction in _DIRS:
        dest = destination(ant, direction)
        if not passable(dest) or not unoccupied(dest):
            continue
        rating = classify_step(field, dest, support.get(dest, 0))
        if rating == SAFE:
            moves.append(direction)
        elif rating == KILL:
            if hills or fearless:
                moves.append(direction)
        elif unblocks_hill_rush(ant, dest, hills, distance):
            moves.append(direction)
    return moves


def best_move(
    ant: Loc,
    field: list[list[int]],
    support: dict[Loc, int],
    hills: list[Loc],
    enemy_locs: list[Loc],
    distance: DistFn,
    destination: DestFn,
    passable: PassFn,
    unoccupied: UnoccFn,
    fearless: bool = False,
    press_kills: bool = False,
) -> str | None:
    """Best pinnable step for one ant given already-pinned support.

    Ranks acceptable moves SAFE first, then KILL, then allowed DIE;
    while the fearless army leads (press_kills), KILL takes press
    first -- even trades favor the extra ant. Ties press toward the
    nearest enemy, then n/e/s/w order, so the greedy pin advances
    fighting lines instead of milling. DIE always ranks last: press
    never prefers death. None when nothing is acceptable: the ant
    holds for muster fallthrough.
    """
    options = acceptable_moves(
        ant,
        field,
        support,
        hills,
        distance,
        destination,
        passable,
        unoccupied,
        fearless,
    )
    if not options:
        return None

    def rank(direction: str) -> tuple[int, int, int]:
        dest = destination(ant, direction)
        rating = classify_step(field, dest, support.get(dest, 0))
        press = 0
        if enemy_locs:
            press = min(distance(dest, foe) for foe in enemy_locs)
        if press_kills:
            tier = 0 if rating == KILL else (1 if rating == SAFE else 2)
        else:
            tier = 0 if rating == SAFE else (1 if rating == KILL else 2)
        return (tier, press, _DIRS.index(direction))

    return min(options, key=rank)


def resolve_fight(
    our_ants: list[Loc],
    enemy_locs: list[Loc],
    stationary: list[Loc],
    rows: int,
    cols: int,
    attack_r2: int,
    hills: list[Loc],
    distance: DistFn,
    destination: DestFn,
    passable: PassFn,
    unoccupied: UnoccFn,
    trace: list[str] | None = None,
    fearless: bool = False,
    press_kills: bool = False,
) -> dict[int, str]:
    """Greedy sequential fixing for one turn's combat ants.

    Stationary enemies stamp first as fixed points of the field,
    mobile enemies stamp after (same single-pass arithmetic -- the
    pin order is what "pinned first" means). Our ants then pin
    most-constrained-first: fewest acceptable moves, hotter squares
    first, list order on full ties. Each pin stamps support locally
    around its square and re-scores only neighbors within reach+1
    through the lazy bucketed queue (stale entries skipped), so no
    pin ever recomputes the field. Returns pinned directions keyed
    by ant index; unpinned ants hold for muster fallthrough.
    """
    plan: dict[int, str] = {}
    if not our_ants or not enemy_locs:
        return plan
    reach = threat_reach(attack_r2)
    stat = set(stationary)
    field = [[0] * cols for _ in range(rows)]
    for foe in [e for e in enemy_locs if e in stat]:
        _stamp(field, foe, rows, cols, reach)
        if trace is not None:
            trace.append(f"pin enemy {foe}")
    for foe in [e for e in enemy_locs if e not in stat]:
        _stamp(field, foe, rows, cols, reach)
    support: dict[Loc, int] = {}
    count = len(our_ants)
    buckets: list[deque[tuple[int, int]]] = [deque() for _ in range(5)]
    version = [0] * count
    unpinned = set(range(count))

    def push(i: int) -> None:
        moves = acceptable_moves(
            our_ants[i],
            field,
            support,
            hills,
            distance,
            destination,
            passable,
            unoccupied,
            fearless,
        )
        version[i] += 1
        buckets[len(moves)].append((i, version[i]))

    for i in range(count):
        push(i)
    while unpinned:
        cur = None
        for constraint in range(5):
            while buckets[constraint]:
                i, stamped = buckets[constraint].popleft()
                if i in unpinned and stamped == version[i]:
                    cur = i
                    break
            if cur is not None:
                break
        if cur is None:
            break
        unpinned.discard(cur)
        move = best_move(
            our_ants[cur],
            field,
            support,
            hills,
            enemy_locs,
            distance,
            destination,
            passable,
            unoccupied,
            fearless,
            press_kills,
        )
        if move is None:
            if trace is not None:
                trace.append(f"hold {cur}")
            continue
        dest = destination(our_ants[cur], move)
        plan[cur] = move
        add_support(support, dest, rows, cols, attack_r2)
        if trace is not None:
            trace.append(f"fix {cur} {move}")
        for j in list(unpinned):
            if distance(our_ants[j], dest) <= reach + 1:
                push(j)
    return plan


def plan_fixing(
    ants_list: list[Loc],
    target: dict[int, Loc],
    enemy_locs: list[Loc],
    stationary: list[Loc],
    rows: int,
    cols: int,
    attack_r2: int,
    hills: list[Loc],
    distance: DistFn,
    destination: DestFn,
    passable: PassFn,
    unoccupied: UnoccFn,
    trace: list[str] | None = None,
    fearless: bool = False,
) -> tuple[dict[int, str], set[int]]:
    """Pin this turn's combat moves, keyed by ant index, plus rally set.

    The population matches the champion screen: claim-free ants with
    an enemy in SEEK_RANGE. Only packed ants (3+ friends within 10)
    pin attacks -- packless ants rally toward their nearest friend
    instead of donating solo, except the rush outranks the pack: a
    packless ant whose only acceptable move unblocks this turn's
    hill rush still pins the suicide. Thin wrapper over
    resolve_fight that selects the population and maps the
    sub-index plan back.
    """
    if not enemy_locs:
        return {}, set()
    picked = [
        ai
        for ai, ant in enumerate(ants_list)
        if target.get(ai) is None
        and any(distance(ant, foe) <= SEEK_RANGE for foe in enemy_locs)
    ]
    if not picked:
        return {}, set()
    packed = [ai for ai in picked if has_pack(ants_list[ai], ants_list, distance)]
    packed_set = set(packed)
    packless = [ai for ai in picked if ai not in packed_set]
    # Press even trades while the fearless army leads: the extra ant
    # wins the fight. Behind or even, SAFE ranks first as before.
    press = fearless and len(ants_list) > len(enemy_locs)
    plan: dict[int, str] = {}
    if packed:
        sub = [ants_list[ai] for ai in packed]
        sub_plan = resolve_fight(
            sub,
            enemy_locs,
            stationary,
            rows,
            cols,
            attack_r2,
            hills,
            distance,
            destination,
            passable,
            unoccupied,
            trace,
            fearless,
            press,
        )
        for k, direction in sub_plan.items():
            plan[packed[k]] = direction
    rally: set[int] = set(packless)
    if packless and hills:
        # The rush outranks the pack only with no alternative: judge
        # the packless against the packed line's final support
        # (re-stamped here, so the verdict matches what resolve saw)
        # and pin the move only when it is a rush-unblocking DIE --
        # a DIE pin exists iff its square unblocks the rush, so the
        # verdict check below is exactly the unblock check. Ants
        # with a SAFE (or allowed KILL) alternative rally instead of
        # donating.
        support: dict[Loc, int] = {}
        for ai, direction in plan.items():
            add_support(
                support,
                destination(ants_list[ai], direction),
                rows,
                cols,
                attack_r2,
            )
        field = influence_field(enemy_locs, rows, cols, threat_reach(attack_r2))
        for ai in packless:
            move = best_move(
                ants_list[ai],
                field,
                support,
                hills,
                enemy_locs,
                distance,
                destination,
                passable,
                unoccupied,
                fearless,
                press,
            )
            if move is not None:
                dest = destination(ants_list[ai], move)
                if classify_step(field, dest, support.get(dest, 0)) == DIE:
                    plan[ai] = move
                    rally.discard(ai)
                    if trace is not None:
                        trace.append(f"fix {ai} {move}")
                    add_support(support, dest, rows, cols, attack_r2)
    return plan, rally


class Fixing5:
    def __init__(self):
        # define class level variables, will be remembered between turns
        self.visits: dict[tuple[int, int], int] = {}
        self.remembered_hills: set[tuple[int, int]] = set()
        self.prev_enemies: list[tuple[int, int]] = []

    # do_setup is run once at the start of the game
    # after the bot has received the game settings
    # the ants class is created and setup by the Ants.run method
    def do_setup(self, ants: Ants):
        # initialize data structures after learning the game settings
        self.visits = {}
        self.remembered_hills = set()
        self.prev_enemies = []

    # do turn is run once per turn
    # the ants class has the game state and is updated by the Ants.run method
    # it also has several helper methods to use
    def do_turn(self, ants: Ants):
        # Fixing5: champion Crowd economy, muster, guard, and explore
        # byte-identical (Denial food claims, threatened-hill guards
        # with off-hill screening, muster plus reinforce, visits
        # explore, walk-off); the combat core is anthonyvh greedy
        # sequential fixing instead of the pack/join/grinder/crowd
        # gates, but gated the Crowd way: packless ants rally to a
        # friend instead of pinning solo attacks, and small fights
        # press KILL takes fearlessly. Influence rates every square
        # by the enemies that could attack it after one move;
        # stationary enemies pin first; each packed combat ant pins
        # its best move most-constrained-first with local
        # re-evaluation after every pin; suicide issues only to
        # unblock a hill rush.
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
            # Odds: EQUAL_TRADE_NEAR (10) near friends accept equal
            # trades, down from champion's tuned 14.
            return near >= EQUAL_TRADE_NEAR and friends + 1 >= enemies

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

        # Fixing5 pre-pass (crowd-gated anthonyvh greedy sequential
        # fixing): pin stationary enemies first -- they are the fixed
        # points of the field -- then pin each packed combat ant's
        # best move in most-constrained-first order, re-evaluating
        # neighbors locally after every pin (incremental support
        # stamps, lazy bucketed queue; no full recompute, no 5^A
        # search). Packless ants skip the pins and rally to a friend
        # instead (the rush-unblocking suicide still pins); small
        # fights press KILL takes fearlessly. The population matches
        # the champion screen: claim-free ants with an enemy in
        # SEEK_RANGE. Guards keep precedence: a planned ant that
        # takes a guard move above simply leaves its pin unused, and
        # pins check destinations on issue.
        stationary = [cur for cur in enemy_locs if headings.get(cur) == cur]
        fearless = len(enemy_locs) < CROWD_LIMIT
        fight_plan, rally = plan_fixing(
            ants_list,
            target,
            enemy_locs,
            stationary,
            rows,
            cols,
            attack_r2,
            hills,
            ants.distance,
            ants.destination,
            ants.passable,
            ants.unoccupied,
            None,
            fearless,
        )

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
                    inter = intercept_square(
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
            if not moved and ai in fight_plan:
                # Fixing5: this ant's move was pinned above given the
                # already-pinned ants. Issue it while still legal
                # (passable, unoccupied, unclaimed by an earlier
                # mover); otherwise fall through to muster exactly as
                # a refused seek does. DIE pins only exist when their
                # square unblocks this turn's hill rush.
                step = fight_plan[ai]
                nloc = ants.destination(ant_loc, step)
                if (
                    nloc not in destinations
                    and ants.passable(nloc)
                    and ants.unoccupied(nloc)
                ):
                    ants.issue_order((ant_loc, step))
                    destinations.add(nloc)
                    moved = True
            if not moved and ai in rally:
                # Packless near enemies: rally toward the nearest
                # friend instead of donating solo into the fight.
                # A friendless ant skips the rally and falls through.
                mates = [f for f in ants_list if f != ant_loc]
                if mates:
                    buddy = min(mates, key=lambda f: ants.distance(ant_loc, f))
                    step = first_step(ant_loc, buddy)
                    if step is not None and try_step(ant_loc, step):
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
        Ants.run(Fixing5())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
