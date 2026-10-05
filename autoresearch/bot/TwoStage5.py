#!/usr/bin/env python
"""Michigan two-stage combat with safe-backup pricing on Crowd base.

ONE IDEA over TwoStage4: support counts only from SAFE friends
(allies outside threat reach of every threat). A threatened
"supporter" is itself about to die or flee, so its backup is
phantom: counting it priced losing advances as backed trades
and donated (the 38.4-to-18.9 collapse). Gated backup reprices
those advances as the losses they are, and the joint search
holds instead; safe-backed ties still advance, and all-safe
positions behave exactly as TwoStage4.

TwoStage4's idea (kept): losing ties run toward support, and
stage-2 squares score the net disadvantage (modeled foes minus
supporting friends in range of the square, floored at zero)
instead of raw foe counts. Backed advances read as wins and
proceed; lone advances still read as losses and hold (the
emergent no-1v1 gate survives: net equals raw with no backup).
Stage 1 labels, stay-or-advance,
search caps, and all economy/guard wiring are TwoStage's.

Michigan two-stage combat on the champion Crowd base.

Economy (denial food claims), guard (hold plus off-hill screen),
muster, reinforce, explore, and walk-off are the champion's,
byte-identical. The combat core -- seek, join, grinder, crowd,
legion, influence -- is replaced by a faithful port of the
RESEARCH.md row "Michigan battle resolution" (claimed top 25):

STAGE 1 (static analysis): classify each nearby enemy as a
safe-target or a threat from current positions only. No enemy
moves are assumed: ours counts our ants in attack range of the
foe today, theirs counts its nearby allies including itself, and
strict superiority (>, never >=) marks a safe-target.

STAGE 2 (threatened analysis): ants outside threat reach of
every threat keep their desired square -- static analysis
already cleared it. Threatened ants model each enemy as
stay-or-advance (two options each, no deeper model: the foe
either holds or takes one toroidal step toward our square) and
pick against the worse of the two, so a lurker one step out
vetoes a step the static counts would accept.

Fewest-ants preference: among equal-scoring moves the one
committing fewer ants wins. No explicit 1v1 rule exists: a
friendless duel scores the engage and the hold equally under the
stay-or-advance worst case, and the hold commits 0 ants against
the engage's 1, so the ant holds. The no-1v1 gate emerges from
the tie-break.

Recursive search: threatened ants search their desired squares
jointly, scoring +1 moved (a safe step only) / -1 per new enemy
drawn in. A branch exits early when even its ceiling trails the
leader by more than EARLY_EXIT_GAP -- deeper search cannot change
the pick. The original recursed unbounded and crashed past 20
ants a side; the recursion caps at MAX_COMBAT_ANTS ants and a
SEARCH_BUDGET node budget, and every ant past either falls back
to a greedy single, so crowded boards stay stable and fast.

Self-contained: stdlib plus ants.py only, no combat import. The
Odds 10-gate and the Screen intercept ride along inline so guard
and explore read exactly as the champion's.
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


SEEK_RANGE = 8

# Odds gate carried from the champion: equal trades (friends + 1
# == enemies) need this many near friends (within 10 steps of the
# step) for the safety filter to accept them. Inlined (no combat
# import) so the entry stays self-contained.
EQUAL_TRADE_NEAR = 10

# Michigan two-stage combat tuning. EARLY_EXIT_GAP is the
# branch-and-bound slack: a search branch whose ceiling trails the
# leader by more than this exits early. MAX_COMBAT_ANTS caps the
# joint recursion (the original crashed past 20 ants a side) and
# SEARCH_BUDGET caps total search nodes; ants past either limit
# fall back to greedy singles.
SAFE_TARGET = "safe-target"
THREAT = "threat"
EARLY_EXIT_GAP = 2
MAX_COMBAT_ANTS = 20
SEARCH_BUDGET = 1500


def _nearest_seek_enemy(
    ant_loc: Loc, enemy_locs: list[Loc], distance: DistFn
) -> Loc | None:
    """Nearest visible enemy within SEEK_RANGE steps, else None.

    Ties keep the first enemy in list order so the branch is
    deterministic. Carried from the champion (inlined, no combat
    import). Pure: no board state, no side effects.
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
    passable: PassFn,
    rows: int,
    cols: int,
) -> Loc | None:
    """Off-hill intercept for one threatened home hill.

    Screens the razer instead of piling onto the hill: take the
    nearest enemy to the hill, halve the toroidal approach, and
    return the nearest passable square to that midpoint (the
    midpoint itself when open). Carried from the champion
    (inlined, no combat import). Pure: no side effects.
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


def threat_reach(attack_r2: int) -> int:
    """Manhattan threat radius of one enemy after it moves one step.

    Attack reach is the floor square root of attackradius2, plus the
    one square the enemy may step before attacking. Pure: integer
    arithmetic, no side effects.
    """
    return int(attack_r2**0.5) + 1


def classify_static(
    ants_list: list[Loc],
    enemy_locs: list[Loc],
    sq_dist: SqDistFn,
    attack_r2: int,
) -> dict[Loc, str]:
    """STAGE 1: label each enemy safe-target or threat, statically.

    Ours counts our ants in attack range of the foe's CURRENT
    square; theirs counts its allies in range of that square,
    including itself. Strict superiority (ours > theirs, never
    >=) marks a safe-target; everything else is a threat. No
    enemy moves are assumed anywhere -- adjacency changes
    nothing, only today's counts do. Pure: no side effects.
    """
    labels: dict[Loc, str] = {}
    for foe in enemy_locs:
        ours = 0
        for ant in ants_list:
            if sq_dist(ant, foe) <= attack_r2:
                ours += 1
        theirs = 0
        for other in enemy_locs:
            if sq_dist(other, foe) <= attack_r2:
                theirs += 1
        labels[foe] = SAFE_TARGET if ours > theirs else THREAT
    return labels


def is_threatened(
    ant_loc: Loc, threat_locs: list[Loc], distance: DistFn, reach: int
) -> bool:
    """Whether a threat could hit the ant after one enemy step.

    True when any threat sits within reach + 1 manhattan steps:
    the enemy's step plus its attack reach. Pure: no side
    effects.
    """
    return any(distance(ant_loc, foe) <= reach + 1 for foe in threat_locs)


def step_toward(src: Loc, dest: Loc, rows: int, cols: int) -> Loc:
    """One toroidal step from src toward dest, wider axis first.

    Rows and cols are positive board sizes. The coarsest advance
    model: no pathing, no second step, ties go to the row. Pure:
    no side effects.
    """
    if src == dest:
        return src
    dr = dest[0] - src[0]
    dc = dest[1] - src[1]
    if dr > rows // 2:
        dr -= rows
    elif dr < -(rows // 2):
        dr += rows
    if dc > cols // 2:
        dc -= cols
    elif dc < -(cols // 2):
        dc += cols
    if dr == 0 and dc == 0:
        return src
    if abs(dr) >= abs(dc):
        return ((src[0] + (1 if dr > 0 else -1)) % rows, src[1])
    return (src[0], (src[1] + (1 if dc > 0 else -1)) % cols)


def static_foes(
    dest: Loc, enemy_locs: list[Loc], sq_dist: SqDistFn, attack_r2: int
) -> int:
    """Enemies in attack range of dest at their current squares.

    The stage-1 view: nobody moves. Pure: no side effects.
    """
    found = 0
    for foe in enemy_locs:
        if sq_dist(dest, foe) <= attack_r2:
            found += 1
    return found


def modeled_foes(
    dest: Loc,
    enemy_locs: list[Loc],
    sq_dist: SqDistFn,
    attack_r2: int,
    rows: int,
    cols: int,
) -> int:
    """STAGE 2: enemies that could hit dest under stay-or-advance.

    Each enemy gets two options -- stay, or one step toward dest
    -- and the worse of the two counts is taken. No deeper model:
    no second step, no coordination, no retreat. Pure: no side
    effects.
    """
    stay = static_foes(dest, enemy_locs, sq_dist, attack_r2)
    advanced = 0
    for foe in enemy_locs:
        if sq_dist(dest, step_toward(foe, dest, rows, cols)) <= attack_r2:
            advanced += 1
    return stay if stay >= advanced else advanced


def move_value(dest: Loc, ant_loc: Loc, foes: int) -> int:
    """Score of one square: +1 moved (safe steps only) - foes.

    A step onto a foe-free square scores +1; holding a foe-free
    square scores 0; any square with foes scores minus their
    count. Pure: integer arithmetic, no side effects.
    """
    bonus = 1 if dest != ant_loc and foes == 0 else 0
    return bonus - foes


def support_count(
    dest: Loc,
    ant_loc: Loc,
    friend_locs: list[Loc],
    sq_dist: SqDistFn,
    attack_r2: int,
    safe: Callable[[Loc], bool] | None = None,
) -> int:
    """Friends backing dest: SAFE allies in attack range, mover excluded.

    The mover never counts toward its own support; holding ants
    count the friends around the square they keep. The safe gate
    (TwoStage5 idea) drops threatened friends: backup that is
    itself inside threat reach is phantom and does not count.
    None keeps the old all-count behavior. Pure: no side
    effects.
    """
    total = 0
    for friend in friend_locs:
        if friend == ant_loc:
            continue
        if sq_dist(dest, friend) > attack_r2:
            continue
        if safe is not None and not safe(friend):
            continue
        total += 1
    return total


def net_value(dest: Loc, ant_loc: Loc, foes: int, friends: int) -> int:
    """Score of one square: +1 moved (safe nets only) - net foes.

    Net is modeled foes minus supporting friends, floored at
    zero: backup cancels contact the way the battle phase does
    (one attacker kills one defender, the extra ant wins). A
    backed step onto a net-free square scores +1; holding a
    net-free square scores 0; any square facing net foes scores
    minus their count. Pure: integer arithmetic, no side
    effects.
    """
    net = foes - friends
    if net < 0:
        net = 0
    bonus = 1 if dest != ant_loc and net == 0 else 0
    return bonus - net


def choice_key(value: int, support: int, committed: int) -> tuple[int, int, int]:
    """Order key for one candidate square: top net score wins.

    The supported-trade tie-break (TwoStage4 idea): a LOSING
    tie (value below zero -- the even trade TwoStage2 refuses
    on fewest ants) runs toward the square with more supporting
    friends, so a backed trade advances while a lone one still
    holds on fewest ants. Safe scores (0 and +1) never credit
    support: winning advances and safe holds order exactly as
    TwoStage2. Pure: integer arithmetic, no side effects.
    """
    return (value, support if value < 0 else 0, -committed)


def commit_count(
    dest: Loc,
    ant_loc: Loc,
    friend_locs: list[Loc],
    sq_dist: SqDistFn,
    attack_r2: int,
) -> int:
    """Ants committed by taking dest: mover plus backup in range.

    The mover commits when it steps (holding commits nobody);
    friends in attack range of dest, excluding the mover, add up.
    Pure: no side effects.
    """
    total = 0 if dest == ant_loc else 1
    for friend in friend_locs:
        if friend != ant_loc and sq_dist(dest, friend) <= attack_r2:
            total += 1
    return total


def pick_best(
    ant_loc: Loc,
    options: list[Loc],
    foes_of: dict[Loc, int],
    friend_locs: list[Loc],
    sq_dist: SqDistFn,
    attack_r2: int,
    safe: Callable[[Loc], bool] | None = None,
) -> Loc:
    """Best square: top score, then supported trade, then list order.

    Equal combat scores first run toward the square with more
    supporting friends when the tie loses (the supported-trade
    rule), and only then prefer the move drawing fewer ants in,
    so lone duels still hold instead of trading. Support counts
    through the safe gate: threatened friends do not back the
    trade. Pure: no side effects.
    """
    best = options[0]
    best_key = choice_key(
        move_value(best, ant_loc, foes_of.get(best, 0)),
        support_count(best, ant_loc, friend_locs, sq_dist, attack_r2, safe),
        commit_count(best, ant_loc, friend_locs, sq_dist, attack_r2),
    )
    for square in options[1:]:
        key = choice_key(
            move_value(square, ant_loc, foes_of.get(square, 0)),
            support_count(square, ant_loc, friend_locs, sq_dist, attack_r2, safe),
            commit_count(square, ant_loc, friend_locs, sq_dist, attack_r2),
        )
        if key > best_key:
            best_key = key
            best = square
    return best


def search_moves(
    order: list[int],
    candidates: dict[int, list[Loc]],
    values: dict[tuple[int, Loc], int],
    committed: dict[tuple[int, Loc], int],
    backing: dict[tuple[int, Loc], int] | None = None,
    gap: int = EARLY_EXIT_GAP,
    cap: int = MAX_COMBAT_ANTS,
    budget: int = SEARCH_BUDGET,
) -> tuple[dict[int, Loc], dict[str, int]]:
    """Recursive per-ant search over desired squares, capped.

    Depth-first over the ants in order: each ant tries its
    desired squares, the running total prices +1 moved / -1 new
    enemy drawn in, and ties run toward support when losing and
    toward fewer committed ants otherwise (same rule as
    pick_best). The optional backing table holds supporting
    friends per ant and square; None behaves as all zeros, which
    is exactly the TwoStage2 order. A branch exits early when even its
    ceiling trails the leader by more than gap -- deeper search
    cannot change the pick -- and the instrumented stats count
    every such exit. Only the first cap ants search jointly and
    only budget nodes run; the rest fall back to greedy singles,
    so 25v25 boards return fast where the original crashed past
    20 a side. Pure: no board state, no side effects.
    """
    stats = {"nodes": 0, "early_exits": 0, "capped": 0}
    support_of = backing if backing is not None else {}
    plan: dict[int, Loc] = {}
    if not order:
        return plan, stats
    front = order[:cap]
    rest = order[cap:]
    if rest:
        stats["capped"] = 1
    ceiling_each = 1
    for sai in front:
        for square in candidates.get(sai, []):
            got = values.get((sai, square), 0)
            if got > ceiling_each:
                ceiling_each = got

    def greedy(ai: int) -> Loc | None:
        best_sq: Loc | None = None
        best_key: tuple[int, int, int] | None = None
        for square in candidates.get(ai, []):
            key = choice_key(
                values.get((ai, square), 0),
                support_of.get((ai, square), 0),
                committed.get((ai, square), 0),
            )
            if best_key is None or key > best_key:
                best_key = key
                best_sq = square
        return best_sq

    best_total = 0
    best_lo = 0
    best_tie = 0
    found = False
    choice: dict[int, Loc] = {}
    stopped = False

    def evaluate() -> None:
        nonlocal best_total, best_lo, best_tie, found
        total = 0
        lototal = 0
        tie = 0
        for eai, esq in choice.items():
            worth = values.get((eai, esq), 0)
            total += worth
            if worth < 0:
                lototal += support_of.get((eai, esq), 0)
            tie -= committed.get((eai, esq), 0)
        if not found or (total, lototal, tie) > (best_total, best_lo, best_tie):
            found = True
            best_total = total
            best_lo = lototal
            best_tie = tie
            plan.clear()
            plan.update(choice)

    def dfs(i: int, partial: int, losup: int, tie: int) -> None:
        nonlocal stopped
        if stopped:
            return
        stats["nodes"] += 1
        if stats["nodes"] > budget:
            # Node budget blown: greedy-fill this branch, score
            # it, and stop branching everywhere. Between this and
            # the cap above, no board can run away.
            stats["capped"] = 1
            for j in range(i, len(front)):
                fill = greedy(front[j])
                if fill is not None:
                    choice[front[j]] = fill
            evaluate()
            for j in range(i, len(front)):
                choice.pop(front[j], None)
            stopped = True
            return
        if i == len(front):
            evaluate()
            return
        left = len(front) - i
        if found and best_total - (partial + left * ceiling_each) > gap:
            # Early exit: the ceiling of this branch trails the
            # leader by more than gap, so no leaf down here can
            # change the pick. Count it and prune.
            stats["early_exits"] += 1
            return
        ai = front[i]
        cands = candidates.get(ai, [])
        if not cands:
            dfs(i + 1, partial, losup, tie)
            return
        for square in cands:
            choice[ai] = square
            worth = values.get((ai, square), 0)
            extra = support_of.get((ai, square), 0) if worth < 0 else 0
            dfs(
                i + 1,
                partial + worth,
                losup + extra,
                tie - committed.get((ai, square), 0),
            )
            if stopped:
                return
        choice.pop(ai, None)

    dfs(0, 0, 0, 0)
    for rai in rest:
        fill = greedy(rai)
        if fill is not None:
            plan[rai] = fill
    for fai in front:
        if fai not in plan:
            fill = greedy(fai)
            if fill is not None:
                plan[fai] = fill
    return plan, stats


# define a class with a do_turn method
# the Ants.run method will parse and update bot input
# it will also run the do_turn method for us
class TwoStage5:
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
        # TwoStage: Crowd's wiring (Denial's economy, hold plus
        # off-hill screening, muster, reinforce, explore, walk-off)
        # with the combat core replaced by the Michigan two-stage
        # search above: static safe-target/threat labels, then a
        # joint stay-or-advance plan for threatened ants with the
        # fewest-ants tie-break. Food, guard, muster, reinforce,
        # explore, and walk-off are champion.
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

        # MICHIGAN Stage 1 (static analysis): classify each nearby
        # enemy as a safe-target or a threat from current positions
        # only -- no enemy moves assumed. Desired squares give each
        # claim-free ant the first step toward its nearest enemy
        # within SEEK_RANGE, the champion's approach shape; ants
        # holding food claims never reach the fight.
        labels = classify_static(ants_list, enemy_locs, sq_dist, attack_r2)
        reach = threat_reach(attack_r2)
        threats = [e for e in enemy_locs if labels.get(e) == THREAT]
        desired: dict[int, tuple[Loc, str]] = {}
        for cai, cant in enumerate(ants_list):
            if target.get(cai) is not None:
                continue
            chase = _nearest_seek_enemy(cant, enemy_locs, ants.distance)
            if chase is None:
                continue
            cstep = first_step(cant, chase)
            if cstep is None:
                continue
            desired[cai] = (ants.destination(cant, cstep), cstep)
        # MICHIGAN Stage 2 (threatened analysis): ants outside
        # threat reach of every threat keep their desired square.
        # Threatened ants search jointly under the stay-or-advance
        # model; squares price +1 moved / -1 new enemy drawn in
        # with the supported-trade tie-break (losing ties run
        # toward SAFE support, else fewest ants), the recursion caps
        # past MAX_COMBAT_ANTS ants, and held ants (no step) fall
        # through to muster, reinforce, and explore below.
        # The safe set prices backup once: friends outside threat
        # reach of every threat. Threatened "supporters" are
        # phantom -- their squares back nobody, in nets or ties.
        michigan_step: dict[int, str] = {}
        stage2: list[int] = []
        for dai in desired:
            if is_threatened(ants_list[dai], threats, ants.distance, reach):
                stage2.append(dai)
            else:
                michigan_step[dai] = desired[dai][1]
        if stage2:
            cands: dict[int, list[Loc]] = {}
            vals: dict[tuple[int, Loc], int] = {}
            coms: dict[tuple[int, Loc], int] = {}
            backs: dict[tuple[int, Loc], int] = {}
            safe_set = {
                f
                for f in ants_list
                if not is_threatened(f, threats, ants.distance, reach)
            }

            def is_safe_backup(floc: Loc) -> bool:
                return floc in safe_set

            for sai in stage2:
                cur = ants_list[sai]
                dest = desired[sai][0]
                pair = [dest] if dest == cur else [dest, cur]
                cands[sai] = pair
                for square in pair:
                    foes_here = modeled_foes(
                        square, enemy_locs, sq_dist, attack_r2, rows, cols
                    )
                    friends_here = support_count(
                        square,
                        cur,
                        ants_list,
                        sq_dist,
                        attack_r2,
                        is_safe_backup,
                    )
                    vals[(sai, square)] = net_value(
                        square, cur, foes_here, friends_here
                    )
                    coms[(sai, square)] = commit_count(
                        square, cur, ants_list, sq_dist, attack_r2
                    )
                    backs[(sai, square)] = friends_here
            chosen, _mstats = search_moves(stage2, cands, vals, coms, backs)
            for eai, esq in chosen.items():
                if esq != ants_list[eai] and eai in desired:
                    michigan_step[eai] = desired[eai][1]

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
                # MICHIGAN execution: the joint plan already priced
                # the stay-or-advance model, so the step issues
                # without the champion safety filter (passability,
                # occupancy, and destination clashes still check).
                # Held or out-of-range ants carry no plan and fall
                # through to muster, reinforce, and explore below.
                mstep = michigan_step.get(ai)
                if mstep is not None and try_step(ant_loc, mstep, safe=False):
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
        Ants.run(TwoStage5())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
