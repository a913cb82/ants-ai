#!/usr/bin/env python
"""Regroup-on-refusal plus unseen-edge scout (Influence15 bot).

Base is Influence8 (final-field veto) with exactly two changes (a
new mix no repo bot holds: verdicts plus regroup plus scout):

(1) In the seek branch, the Influence8 verdict still decides every
advance -- SAFE marches, KILL breaks deadlocks and hill pushes,
DIE refuses -- but a refused hunter with no pack regroups instead
of diffusing, when no hill is remembered: one step toward its
nearest friend under the normal safety filter (Crowd's leg-6 rule,
copied into this file), then muster, reinforce, and explore as base.
Hill races keep every body marching, so the gate only redirects
open-field refusals. Packing only redirects refusals, so free
advances (even lone winning fights) march exactly as base while
refused KILLs and DIEs gather mass for the follow-up instead of
wandering off through explore.

(2) Idle ants scout the unseen edge instead of wandering: the
first explore step heads down the shortest passable path to the
nearest never-seen square (Duelist's edge BFS, copied into this
file, Influence-flavored with the DIE-skip and the safety filter
and no live-field stamp, exactly like the least-visited fallback
it precedes). Seen-memory banks every visible square each turn,
so mazes get walked early, distant food shows sooner, and idle
ants push fog instead of re-wandering home ground.

The staged Influence10 backup-pricing is NOT carried: it scored
32.4 against Influence8's 45.9, so every KILL here is unpriced and
the veto covers takes exactly as base. Everything else is
byte-identical to Influence8.

Base (Influence8) notes follow.

Final-field veto (Influence8 bot).

Base is Influence4 (live own-influence stamps on every issued order)
with exactly one change: combat orders are PLANNED against the live
field but ISSUED only after re-verification against the final
post-move field -- every ant stamped where it will actually stand.
A planned combat step taken as SAFE mid-turn is vetoed (the ant
holds) unless it still reads SAFE finally, or KILL on a hill-push
turn; a step taken as a deadlock/hill-push KILL is vetoed only when
it degrades to DIE finally. Non-combat moves (food, guard,
walk-off, explore) are planned and issued exactly as base and are
never vetoed. The veto repeats to a fixed point (a vetoed holder
stays home, which can only weaken the final field), so the late
leaver that vacates a fight holds the hunter that committed behind
it, while a converged pair that still reads SAFE marches untouched.

Base (Influence4) notes follow.

Base is Influence3 (Memetix-style influence with the softer 2/3
refinement) with exactly one change: the own influence field
follows our issued moves -- every issued order re-stamps the
mover's attack diamond off its old tile and onto its new tile, so
later ants in the same turn read converging (or abandoned) support
instead of the stale snapshot. The foe field stays static and the
thirds refinement plus every verdict are unchanged: a second hunter
joins a 2v1 its snapshot called KILL once the leader's advance
lifts it to SAFE, while a hunter left behind refuses a step its
snapshot called SAFE once the departure drops it to KILL or DIE.

Base (Influence3) docstring follows.

Base is Influence2 (full Memetix + hill-push KILL) with exactly one
change: extra attackers beyond the first count at 2/3 weight instead
of 1/2, applied to BOTH sides symmetrically. refine(k) = 1 + (k-1)*2/3
compared exactly in thirds: scaled(k) = 0 when k == 0, else 2*k + 1.
Base DIE and base SAFE verdicts are unchanged (both orders are
monotone, so strict majorities survive); base-KILL ties with unequal
raw counts now split on the raw majority -- ours ahead refines to
SAFE (winnable fights march freely, no deadlock needed), theirs
ahead refines to DIE (still refused). Everything else is byte-identical
to Influence2: seek gating, hill-push KILL, muster/reinforce verdicts,
economy, guard, explore, walk-off.

Base is the faithful Influence entry (two raw influence fields, the
one-ant-per-tile refinement, SAFE/KILL/DIE verdicts, deadlock-KILL in
the seek). The one tuning idea: KILL (expect a 1-for-1) is allowed on
ANY turn pushing a remembered enemy hill (hill_push: remembered hills
non-empty), not just deadlocks. The seek already spent hill-push KILLs
but the hill advance (muster, reinforce) still answered to the champion
majority filter, which refuses winnable even fights; here the refined
verdict decides the hill advance instead -- SAFE and KILL march, DIE
still refuses and falls through to explore. Seek, deadlock-KILL, DIE-
refused-everywhere, economy, guard, explore, and walk-off are unchanged.

Base docstring follows.

Implements the RESEARCH.md row "Memetix influence combat"
(single-pass influence maps decide SAFE/KILL/DIE in 3-5 ms; KILL
only to break deadlocks): two raw influence fields -- ours and
theirs -- precomputed in ONE pass per turn (each ant stamps its
post-move attack diamond once), an in-thread refinement for
one-ant-per-tile overcounting, and a SAFE/KILL/DIE verdict for
every planned contact step. DIE is always refused; KILL (expect a
1-for-1) issues only to break a deadlock; SAFE advances.

Deadlock rule (exact): KILL issues iff (a) the army pushes a
remembered enemy hill this turn (hill_push: remembered hills
non-empty after this turn's sighting update -- visible hills are
added, razed/owned ones discarded), OR (b) the ant already stands
in contact (an enemy within attack range of its current tile) and
no SAFE move exists (every passable, unoccupied, unclaimed
neighbor classifies KILL or DIE under the same refined fields).

Refinement rule (exact, Influence3 tuning): refined(k) = 0 when
k == 0, else 1 + (k - 1)*2/3, compared in thirds as
2*k + 1 -- the first attacker on a tile counts fully, each extra
attacker counts two thirds. Multiple ants of one side covering the same tile must share approach lanes under
one-ant-per-tile, so the extras are discounted. Applied to BOTH
sides at classify time from the single-pass raw fields, so the
precompute stays one pass and the refinement rides in-thread.

Replaces the champion's pack gate, committed-join, grinder 1v1,
crowd-fearless, and 10-near equal-trade rules in the seek branch.
Economy (food claims), guard (threatened hills + screening),
muster, reinforce, explore ordering, and walk-off keep champion
Crowd behavior; explore additionally skips DIE squares. The crude
DIE-gate-only version of this idea (raw enemy counts, refuse
everything unfavorable, no KILL) scored 31.4 and was discarded
for refusing too much -- the refinement (which softens raw-DIE
into KILL) plus the deadlock-KILL above are the fidelity the
crude version lacked.

Self-contained: stdlib plus ants.py only, never combat.py.
"""

from collections import deque
from collections.abc import Callable
from fractions import Fraction

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

# Equal trades (friends + 1 == enemies) need this many near friends
# (within 10 steps of the step) for the champion safety filter to
# accept them. Carried forward from the champion chain (Odds tuned
# the champion's 14 down to 10); food, guard, muster, reinforce,
# and explore keep it byte-identical.
EQUAL_TRADE_NEAR = 10

# Single-pass influence verdicts for one planned contact step. DIE
# refuses exactly as a losing fight; KILL trades 1-for-1 only to
# break deadlocks; SAFE keeps carried-forward play.
SAFE = "SAFE"
KILL = "KILL"
DIE = "DIE"

SqDistFn = Callable[[Loc, Loc], int]
PassFn = Callable[[Loc], bool]


def threat_reach(attack_r2: int) -> int:
    """Manhattan threat radius of one ant after it moves one step.

    Attack reach is the floor square root of attackradius2, plus the
    one square the ant may step before attacking. Pure: integer
    arithmetic, no side effects.
    """
    return int(attack_r2**0.5) + 1


def influence_fields(
    ours: list[Loc], theirs: list[Loc], rows: int, cols: int, reach: int
) -> tuple[list[list[int]], list[list[int]]]:
    """Per-square count of ants that could attack each tile after 1 move.

    One precompute pass per turn: every ant of both sides stamps its
    toroidal manhattan diamond once, ours into the first field and
    theirs into the second. Pure: no board state, no side effects.
    """
    own = [[0] * cols for _ in range(rows)]
    foe = [[0] * cols for _ in range(rows)]
    if reach < 0 or rows <= 0 or cols <= 0:
        return own, foe
    for field, locs in ((own, ours), (foe, theirs)):
        for er, ec in locs:
            for dr in range(-reach, reach + 1):
                width = reach - abs(dr)
                row = field[(er + dr) % rows]
                for dc in range(-width, width + 1):
                    row[(ec + dc) % cols] += 1
    return own, foe


def move_own_stamp(
    own_field: list[list[int]],
    src: Loc,
    dst: Loc,
    rows: int,
    cols: int,
    reach: int,
) -> None:
    """Slide one own ant's attack diamond from src to dst, in place.

    Undoes the single-pass stamp centered on the mover's old tile
    and re-applies it centered on its new tile, so later verdicts
    in the same turn read the army as it now stands. Overlapping
    tiles net to zero change and total stamped tiles are conserved.
    Mutates own_field; the foe field is never touched. Pure
    bookkeeping: no board state, no side effects beyond the field.
    """
    if reach < 0 or rows <= 0 or cols <= 0 or src == dst:
        return
    for center, delta in ((src, -1), (dst, 1)):
        er, ec = center
        for dr in range(-reach, reach + 1):
            width = reach - abs(dr)
            row = own_field[(er + dr) % rows]
            for dc in range(-width, width + 1):
                row[(ec + dc) % cols] += delta


def project_final_field(
    mine: list[Loc],
    moves: list[tuple[Loc, Loc]],
    rows: int,
    cols: int,
    reach: int,
) -> list[list[int]]:
    """Own influence field stamped at final post-move positions.

    Every mover in moves (src, dst pairs) stamps its attack diamond
    centered on its destination; every other ant stamps from its
    start tile. The foe field is untouched -- foes are not planned.
    Pure: builds a fresh field, no board state, no side effects.
    """
    dest_of = dict(moves)
    return stamp_positions([dest_of.get(ant, ant) for ant in mine], rows, cols, reach)


def stamp_positions(
    locs: list[Loc], rows: int, cols: int, reach: int
) -> list[list[int]]:
    """Per-square count of ants that could attack each tile after 1 move.

    Stamps one side's toroidal manhattan diamonds into a fresh field.
    Pure: no board state, no side effects.
    """
    field = [[0] * cols for _ in range(rows)]
    if reach < 0 or rows <= 0 or cols <= 0:
        return field
    for er, ec in locs:
        for dr in range(-reach, reach + 1):
            width = reach - abs(dr)
            row = field[(er + dr) % rows]
            for dc in range(-width, width + 1):
                row[(ec + dc) % cols] += 1
    return field


def refine_scaled(count: int) -> int:
    """Attacker weight in thirds (exact one-ant-per-tile discount).

    The first attacker counts 3/3, each extra counts 2/3: 0 stays 0,
    then scaled(k) = 2*k + 1, so 1 -> 3, pairs -> 5, triples -> 7.
    Pure: integer arithmetic, no side effects.
    """
    if count <= 0:
        return 0
    return 2 * count + 1


def refine(count: int) -> Fraction:
    """Discounted attacker count for one tile (one-ant-per-tile rule).

    The first attacker counts fully, each extra counts two thirds:
    0 stays 0, 1 stays 1, pairs count 5/3, triples 7/3. Exact:
    thirds arithmetic via refine_scaled, no side effects.
    """
    return Fraction(refine_scaled(count), 3)


def classify_counts(ours_raw: int, theirs_raw: int) -> str:
    """Verdict from raw influence counts at one tile.

    Both sides reweight first (extra attackers count 2/3, compared
    exactly in thirds): DIE when their scaled count strictly exceeds
    ours, KILL when equal (expect a 1-for-1), SAFE when we lead.
    Pure: table lookup plus compare, no side effects.
    """
    ours = refine_scaled(ours_raw)
    theirs = refine_scaled(theirs_raw)
    if theirs > ours:
        return DIE
    if theirs == ours:
        return KILL
    return SAFE


def rate_step(own_field: list[list[int]], foe_field: list[list[int]], dest: Loc) -> str:
    """Verdict for a planned step onto dest from both raw fields.

    Ours includes the moving ant (it stamps its own destination from
    one step away), so an empty tile always reads SAFE. Pure: two
    table lookups plus compare, no side effects.
    """
    return classify_counts(own_field[dest[0]][dest[1]], foe_field[dest[0]][dest[1]])


# Regroup-on-refusal (Influence15 tuning, Crowd leg 6 copied): a hunter
# refused by the verdict packs up when it holds no pack -- fewer than
# PACK_NEED+ friends within PACK_RADIUS steps -- one step toward its
# nearest friend instead of diffusing away through explore. Refused
# KILLs and DIEs gather mass for the follow-up; free advances march
# untouched, so small wins are never ceded for cohesion. Triggers on
# the seek verdict only: Horde's leg-8 regroup covers the hill march
# instead, and this entry keeps the Influence8 muster exactly.
PACK_NEED = 3
PACK_RADIUS = 10


def has_pack(
    ant_loc: Loc,
    ants_list: list[Loc],
    distance: DistFn,
    need: int = PACK_NEED,
    radius: int = PACK_RADIUS,
) -> bool:
    """Whether an ant holds a pack: need+ friends within radius steps.

    The ant itself never counts toward its own pack. Measured from
    start tiles. Pure: no board state, no side effects.
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


def nearest_enemy(ant_loc: Loc, enemy_locs: list[Loc], distance: DistFn) -> Loc | None:
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


# define a class with a do_turn method
# the Ants.run method will parse and update bot input
# it will also run the do_turn method for us
class Influence15:
    def __init__(self):
        # define class level variables, will be remembered between turns
        self.visits: dict[tuple[int, int], int] = {}
        self.seen: set[tuple[int, int]] = set()
        self.remembered_hills: set[tuple[int, int]] = set()
        self.prev_enemies: list[tuple[int, int]] = []

    # do_setup is run once at the start of the game
    # after the bot has received the game settings
    # the ants class is created and setup by the Ants.run method
    def do_setup(self, ants: Ants):
        # initialize data structures after learning the game settings
        self.visits = {}
        self.seen = set()
        self.remembered_hills = set()
        self.prev_enemies = []

    # do turn is run once per turn
    # the ants class has the game state and is updated by the Ants.run method
    # it also has several helper methods to use
    def do_turn(self, ants: Ants):
        # Influence: Crowd's economy, guard, muster, reinforce,
        # explore ordering, and walk-off (same targets, same order),
        # except the seek branch answers to the refined influence
        # verdict instead of the pack/join/grinder/crowd gates:
        # SAFE advances, KILL breaks deadlocks only, DIE refuses.
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
        for r in range(ants.rows):
            for c in range(ants.cols):
                loc = (r, c)
                if ants.visible(loc):
                    self.seen.add(loc)
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
        # Influence: single precompute pass over both armies stamps
        # every square each side could attack after one move;
        # hill_push marks a contested-hill turn, the deadlock KILL
        # may break.
        reach = threat_reach(attack_r2)
        own_field, foe_field = influence_fields(
            ants_list, enemy_locs, rows, cols, reach
        )
        hill_push = bool(hills)

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

        def edge_step(start: tuple[int, int], budget: int = 150) -> str | None:
            # First step of the shortest passable path to the nearest
            # square never seen. None when explored or over budget.
            # Budget 150 (down from Duelist's 500): fog within about
            # seven rings is still found every turn while hundreds of
            # idle ants stay inside the turn limit; farther fog waits
            # for the next turn's memory update. A fully banked map
            # skips the search entirely (the BFS could only return
            # None) so explored late games cost nothing here.
            if len(self.seen) >= rows * cols:
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
                    if nxt not in self.seen:
                        node = nxt
                        while parent[node][0] != start:
                            node = parent[node][0]
                        return parent[node][1]
                    queue.append(nxt)
            return None

        # Influence8: orders are PLANNED here and ISSUED after the
        # final-field veto below. plan_order records (src, step, dst,
        # combat, mid-turn verdict) and keeps the live own field and
        # the destination claims identical to base, so every mid-turn
        # read matches Influence4 exactly; only the issue is deferred.
        planned: list[tuple[tuple[int, int], str, tuple[int, int], bool, str]] = []

        def plan_order(
            ant_loc: tuple[int, int],
            direction: str,
            new_loc: tuple[int, int],
            combat: bool,
            mid: str,
            stamp: bool,
        ) -> None:
            planned.append((ant_loc, direction, new_loc, combat, mid))
            destinations.add(new_loc)
            if stamp:
                move_own_stamp(own_field, ant_loc, new_loc, rows, cols, reach)

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
                plan_order(ant_loc, direction, new_loc, False, "", True)
                return True
            return False

        def try_free(ant_loc: tuple[int, int], direction: str, mid: str) -> bool:
            # Unchecked plan: the influence verdict already decided.
            # Passable, occupancy, and destination clashes check as
            # usual. The mid-turn verdict rides along so the veto can
            # tell a degraded SAFE from a kept deadlock KILL.
            new_loc = ants.destination(ant_loc, direction)
            if (
                new_loc not in destinations
                and ants.passable(new_loc)
                and ants.unoccupied(new_loc)
            ):
                plan_order(ant_loc, direction, new_loc, True, mid, True)
                return True
            return False

        def _in_contact(ant_loc: tuple[int, int]) -> bool:
            # Already standing in a fight: an enemy within attack
            # range of the current tile.
            return any(sq_dist(ant_loc, e) <= attack_r2 for e in enemy_locs)

        def _has_safe_move(ant_loc: tuple[int, int]) -> bool:
            # A SAFE escape exists among the passable, unoccupied,
            # unclaimed neighbors under the same refined fields.
            for direction in ("n", "e", "s", "w"):
                cand = ants.destination(ant_loc, direction)
                if (
                    cand not in destinations
                    and ants.passable(cand)
                    and ants.unoccupied(cand)
                    and rate_step(own_field, foe_field, cand) == SAFE
                ):
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
            if not moved and enemy_locs:
                # Influence15: no food or guard move; the Influence8
                # verdict decides the advance (SAFE issues unchecked,
                # KILL trades 1-for-1 only to break a deadlock or push
                # a remembered hill, DIE always refuses). A refused
                # hunter with no pack regroups instead of diffusing:
                # one step toward its nearest friend under the normal
                # filter (Crowd's leg-6 rule, copied into this file),
                # then muster, reinforce, and explore as base -- and
                # only when no hill is remembered, so hill races keep
                # every body marching exactly as base. Free advances
                # march exactly as base -- packing only redirects
                # refusals, so small wins are never ceded.
                foe = nearest_enemy(ant_loc, enemy_locs, ants.distance)
                if foe is not None:
                    step = first_step(ant_loc, foe)
                    if step is not None:
                        dest = ants.destination(ant_loc, step)
                        verdict = rate_step(own_field, foe_field, dest)
                        take = verdict == SAFE or (
                            verdict == KILL
                            and (
                                hill_push
                                or (
                                    _in_contact(ant_loc) and not _has_safe_move(ant_loc)
                                )
                            )
                        )
                        if take and try_free(ant_loc, step, verdict):
                            moved = True
                        elif (
                            not take
                            and not hills
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
            if not moved and hills:
                # Flood: the group marches on one target, the hill
                # nearest the army as a whole. Hunt always; fearless
                # when ahead on hills. Influence3: this turn pushes a
                # remembered enemy hill (hills non-empty IS hill_push),
                # so the refined verdict decides the advance, not the
                # majority filter: SAFE and KILL (expect a 1-for-1)
                # march, DIE still refuses and falls through.
                muster = min(
                    hills,
                    key=lambda h: sum(ants.distance(a, h) for a in ants_list),
                )
                step = first_step(ant_loc, muster)
                if step is not None:
                    muster_verdict = rate_step(
                        own_field, foe_field, ants.destination(ant_loc, step)
                    )
                    if muster_verdict != DIE and try_free(
                        ant_loc, step, muster_verdict
                    ):
                        moved = True
            if not moved and hills:
                # No hill move: reinforce the second-nearest hill.
                # Influence3: same hill-push verdict as the muster --
                # KILL reinforces, DIE still refuses.
                ordered = sorted(hills, key=lambda h: ants.distance(ant_loc, h))
                near = ordered[1] if len(ordered) > 1 else ordered[0]
                hstep = first_step(ant_loc, near)
                if hstep is not None:
                    near_verdict = rate_step(
                        own_field, foe_field, ants.destination(ant_loc, hstep)
                    )
                    if near_verdict != DIE and try_free(ant_loc, hstep, near_verdict):
                        moved = True
            if not moved:
                # Scout: push the unseen edge first, so maze corridors
                # get walked early and distant food shows sooner. The
                # edge step carries the explore guards (DIE-skip,
                # safety filter, no live-field stamp); when the edge
                # is shut or refused, the least-visited fallback below
                # decides exactly as base.
                estep = edge_step(ant_loc)
                if estep is not None:
                    enew = ants.destination(ant_loc, estep)
                    if (
                        rate_step(own_field, foe_field, enew) != DIE
                        and enew not in destinations
                        and ants.passable(enew)
                        and ants.unoccupied(enew)
                        and is_safe(enew, ant_loc)
                    ):
                        plan_order(ant_loc, estep, enew, False, "", False)
                        moved = True
            if not moved:
                # Still stuck: explore least-visited squares first.
                dirs = sorted(
                    ("n", "e", "s", "w"),
                    key=lambda d: self.visits.get(ants.destination(ant_loc, d), 0),
                )
                for direction in dirs:
                    new_loc = ants.destination(ant_loc, direction)
                    # Influence: never wander onto a DIE square;
                    # KILL and SAFE explore exactly as champion.
                    if rate_step(own_field, foe_field, new_loc) == DIE:
                        continue
                    if (
                        new_loc not in destinations
                        and ants.passable(new_loc)
                        and ants.unoccupied(new_loc)
                        and is_safe(new_loc, ant_loc)
                    ):
                        plan_order(ant_loc, direction, new_loc, False, "", False)
                        moved = True
                        break
            if not moved:
                held.append(ant_loc)
            # check if we still have time left to calculate more orders
            if ants.time_remaining() < 10:
                break
        # Influence8 veto: re-rate every planned combat step against
        # the final post-move field (movers stamped at their planned
        # destinations, which may include explore movers the live
        # field left stale). A SAFE take must still read SAFE -- or
        # KILL on a hill-push turn, which would have marched anyway;
        # a deadlock/hill-push KILL take survives anything but DIE.
        # Vetoed ants hold at home. Repeat to a fixed point: a veto
        # only weakens the final field, so one pass per veto suffices
        # and quiet turns change nothing.
        vetoed: list[tuple[int, int]] = []
        remaining_rounds = len(planned) + 1
        while remaining_rounds > 0:
            remaining_rounds -= 1
            final_field = project_final_field(
                ants_list,
                [(src, dst) for src, _, dst, _, _ in planned],
                rows,
                cols,
                reach,
            )
            combat = [entry for entry in planned if entry[3]]
            degraded = set()
            for src, _step, dst, _is_combat, mid in combat:
                final = rate_step(final_field, foe_field, dst)
                if final == DIE or (
                    mid == SAFE and final != SAFE and not (final == KILL and hill_push)
                ):
                    degraded.add(src)
            if not degraded:
                break
            planned = [entry for entry in planned if entry[0] not in degraded]
            vetoed.extend(sorted(degraded))
        held.extend(ant for ant in vetoed if ant not in held)
        # Walk off hill: a held ant on a home hill must step off.
        hill_set = set(my_hills)
        for ant_loc in held:
            if ant_loc in hill_set and ants.time_remaining() >= 10:
                for direction in ("s", "e", "w", "n"):
                    if try_step(ant_loc, direction):
                        break
        # Deferred issue: surviving plans go out in plan order.
        for src, direction, _dst, _combat, _mid in planned:
            ants.issue_order((src, direction))


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
        Ants.run(Influence15())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
