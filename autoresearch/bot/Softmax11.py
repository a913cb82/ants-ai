#!/usr/bin/env python
"""Softmax11 entry: ghost-memory deterministic pursuit combat.

Economy (clustered denial food), threatened-hill guard with
off-hill screening, muster, reinforce, explore, and walk-off are
the champion Crowd logic byte-identical apart from the class name.
Only sensing and the combat core are replaced.

Six new mechanisms, none in any repo Python bot:
- Ghost memory: last-seen foe squares persist GHOST_TTL turns and
  keep triggering hill guard while unseen, then expire. Guard on
  memory, harvest on sight (food denial still uses visible foes
  only, so no harvest is wasted on empty clusters).
- Deterministic pursuit: each visible foe holds contact when already
  inside attack range, else greedy-approaches its nearest own ant.
  One deterministic reply replaces N sampled replies; casualties
  follow the league engine's default `focus` rule (an ant dies iff
  some foe in range faces no more foes than it does), so surrounds
  kill free and duels go mutual. No RNG anywhere in combat, so
  identical turns give identical orders.
- Wall-aware carve: an own/foe pair joins a fight only with a
  short water-free path between them, so wall-separated pairs
  never carve phantom fights that dodge ghosts through stone.
- Directed retreat: ants in rejected (losing) fights first escape
  attack range, then huddle toward friends, then maximize the gap,
  or hold when nowhere is safer, instead of mustering back in.
  Accepted stays hold only the firing line (a foe in contact),
  otherwise the ant keeps flowing. Aggression is a deterministic
  local majority (own >= enemy takes equal trades), extended one
  down while the visible army leads so backup can arrive; passive
  play still needs a strictly positive overvalued trade.
"""

import math
from collections import deque
from collections.abc import Callable
from functools import lru_cache
from itertools import product

from ants import Ants

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]
PassFn = Callable[[Loc], bool]
DestFn = Callable[[Loc, str], Loc]

CLUSTER_R = 8
DENIAL_ENEMIES = 3
DENIAL_CLAIMS = 2
_CELL = CLUSTER_R + 1

# Own-ant overvaluation: each own death costs this much against
# one enemy kill. > 1 preserves forces; equal trades score
# negative so passive play refuses them.
OWN_ANT_WEIGHT = 1.5
# Ghost memory: last-seen foe squares stay sensed this many turns
# after vanishing, then expire. Guard on memory, harvest on sight.
GHOST_TTL = 3
# Submap carve radius: own/enemy ants linked within this many
# steps belong to one fight.
COMBAT_LINK = 6
# Wall-aware carve: an own/foe pair needs a water-free path this
# long or shorter to share a fight (open-field pairs always pass,
# wall-separated phantoms never carve).
WAR_LINK = 8
_DIRS = ("n", "e", "s", "w")
_AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1)}


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


def resolve_aggressive(own: int, enemy: int, ahead: bool = False) -> bool:
    """Deterministic aggression: local majority takes equal trades.

    While the visible army leads, one-down fights contest too (the
    dodge issues instead of a retreat), so backup can arrive; even
    or behind, those fights retreat rather than feed.
    """
    if enemy <= 0:
        return True
    if own <= 0:
        return False
    return own >= enemy or (ahead and own + 1 >= enemy)


@lru_cache(maxsize=131072)
def toroidal_sq(a: Loc, b: Loc, rows: int, cols: int) -> int:
    """Squared toroidal distance, same wrap as Ants.distance.

    Cached: combat re-scores the same square pairs thousands of
    times per turn, so memoizing keeps giant fights affordable.
    """
    dr = abs(a[0] - b[0])
    dr = min(dr, rows - dr) if rows else dr
    dc = abs(a[1] - b[1])
    dc = min(dc, cols - dc) if cols else dc
    return dr * dr + dc * dc


def focus_casualties(
    own_after: list[Loc],
    enemy_after: list[Loc],
    attack_r2: int,
    rows: int,
    cols: int,
) -> tuple[int, int]:
    """Engine-focus casualties: weakness is foe count in range.

    Mirrors the league engine's default `focus` attack: an ant dies
    iff some foe in range faces no more foes than it does, so
    surrounds kill free and duels go mutual. Pure, no side effects.
    """
    own_weak: list[int] = []
    own_touch: list[list[int]] = []
    for o in own_after:
        touching = [
            j
            for j, e in enumerate(enemy_after)
            if toroidal_sq(o, e, rows, cols) <= attack_r2
        ]
        own_touch.append(touching)
        own_weak.append(len(touching))
    foe_weak: list[int] = []
    foe_touch: list[list[int]] = []
    for e in enemy_after:
        touching = [
            i
            for i, o in enumerate(own_after)
            if toroidal_sq(e, o, rows, cols) <= attack_r2
        ]
        foe_touch.append(touching)
        foe_weak.append(len(touching))
    own_dead = sum(
        1
        for i in range(len(own_after))
        if own_touch[i] and min(foe_weak[j] for j in own_touch[i]) <= own_weak[i]
    )
    enemy_dead = sum(
        1
        for j in range(len(enemy_after))
        if foe_touch[j] and min(own_weak[i] for i in foe_touch[j]) <= foe_weak[j]
    )
    return own_dead, enemy_dead


def resolve_exchange(
    own_after: list[Loc],
    enemy_after: list[Loc],
    attack_r2: int,
    rows: int,
    cols: int,
) -> tuple[int, int]:
    """1-turn casualties under the engine's focus rule.

    Pure: no board state, no side effects.
    """
    return focus_casualties(own_after, enemy_after, attack_r2, rows, cols)


def exchange_score(
    own_dead: int, enemy_dead: int, own_weight: float = OWN_ANT_WEIGHT
) -> float:
    """Overvalued trade score: enemy kills minus weighted own dead."""
    return float(enemy_dead) - own_weight * float(own_dead)


def should_accept(
    own_dead: int, enemy_dead: int, aggressive: bool, own_weight: float = OWN_ANT_WEIGHT
) -> bool:
    """Trade gate: aggressive takes equal trades, passive refuses.

    Passive needs a strictly positive overvalued score; aggressive
    accepts any worst case down to the equal-trade score
    (1 - own_weight), still refusing strictly losing fights.
    Pure: integer counts plus compare, no side effects.
    """
    score = exchange_score(own_dead, enemy_dead, own_weight)
    if aggressive:
        return score >= (1.0 - own_weight) - 1e-9
    return score > 0.0


def legal_dests(loc: Loc, rows: int, cols: int, passable: PassFn) -> list[Loc]:
    """Stay plus passable orthogonal steps, deterministic order."""
    out = [loc]
    for d in _DIRS:
        dr, dc = _AIM[d]
        nxt = ((loc[0] + dr) % rows, (loc[1] + dc) % cols)
        if passable(nxt):
            out.append(nxt)
    return out


def remember_enemies(
    ghosts: dict[Loc, int], enemy_locs: list[Loc], turn: int
) -> dict[Loc, int]:
    """Ghost memory: stamp visible foes, drop sightings older than TTL.

    Pure: returns the new map, no side effects.
    """
    kept = {loc: seen for loc, seen in ghosts.items() if turn - seen <= GHOST_TTL}
    for loc in enemy_locs:
        kept[loc] = turn
    return kept


def sensed_enemies(enemy_locs: list[Loc], ghosts: dict[Loc, int]) -> list[Loc]:
    """Visible foes plus unseen ghosts, deterministic order.

    Pure: no board state, no side effects.
    """
    visible = set(enemy_locs)
    extra = sorted(loc for loc in ghosts if loc not in visible)
    return list(enemy_locs) + extra


def pursuit_step(
    foe: Loc,
    own_locs: list[Loc],
    attack_r2: int,
    rows: int,
    cols: int,
    passable: PassFn,
    destination: DestFn,
    distance: DistFn,
) -> Loc:
    """One deterministic foe reply: hold contact inside attack range,
    else greedy-approach the nearest own ant (stay breaks ties).

    Pure: no board state, no side effects.
    """
    if not own_locs:
        return foe
    for own in own_locs:
        if toroidal_sq(foe, own, rows, cols) <= attack_r2:
            return foe
    target = min(own_locs, key=lambda o: distance(foe, o))
    best = foe
    best_d = distance(foe, target)
    for d in _DIRS:
        cand = destination(foe, d)
        if not passable(cand):
            continue
        cand_d = distance(cand, target)
        if cand_d < best_d:
            best_d = cand_d
            best = cand
    return best


def pursuit_enemy_joint(
    enemy_locs: list[Loc],
    own_locs: list[Loc],
    attack_r2: int,
    rows: int,
    cols: int,
    passable: PassFn,
    destination: DestFn,
    distance: DistFn,
) -> list[list[Loc]]:
    """Single deterministic enemy reply, one joint, no RNG.

    Pure: no board state, no side effects.
    """
    joint = [
        pursuit_step(
            e, own_locs, attack_r2, rows, cols, passable, destination, distance
        )
        for e in enemy_locs
    ]
    return [joint]


def retreat_dest(
    ant: Loc,
    own_locs: list[Loc],
    enemy_locs: list[Loc],
    attack_r2: int,
    rows: int,
    cols: int,
    passable: PassFn,
    distance: DistFn,
) -> Loc:
    """Directed retreat: escape attack range, then huddle, then gap.

    Candidates are stay plus passable steps in fixed order; the best
    first prefers leaving attack range entirely, then nearness to
    friends, then the squared gap to the nearest foe. Pure.
    """
    if not enemy_locs:
        return ant
    friends = [f for f in own_locs if f != ant]
    cands = [ant]
    for d in _DIRS:
        cand = ((ant[0] + _AIM[d][0]) % rows, (ant[1] + _AIM[d][1]) % cols)
        if passable(cand):
            cands.append(cand)
    best = ant
    best_key = (False, -(10**9), -1)
    for cand in cands:
        gap = min(toroidal_sq(cand, e, rows, cols) for e in enemy_locs)
        huddle = -min((distance(cand, f) for f in friends), default=0)
        key = (gap > attack_r2, huddle, gap)
        if key > best_key:
            best_key = key
            best = cand
    return best


def worst_score_for_own(
    own_joint: list[Loc],
    enemy_samples: list[list[Loc]],
    attack_r2: int,
    rows: int,
    cols: int,
    own_weight: float = OWN_ANT_WEIGHT,
) -> float:
    """Min over the samples (robust max-min), never mean or first."""
    if not enemy_samples:
        return 0.0
    worst = math.inf
    for sample in enemy_samples:
        own_dead, enemy_dead = focus_casualties(
            own_joint, sample, attack_r2, rows, cols
        )
        score = float(enemy_dead) - own_weight * float(own_dead)
        if score < worst:
            worst = score
    return worst


def choose_own_joint(
    own_locs: list[Loc],
    enemy_locs: list[Loc],
    attack_r2: int,
    rows: int,
    cols: int,
    passable: PassFn,
    destination: DestFn,
    enemy_samples: list[list[Loc]],
    own_weight: float = OWN_ANT_WEIGHT,
    deadline: Callable[[], bool] | None = None,
) -> tuple[list[Loc], float]:
    """Argmax own joint over the min-over-samples score, 1-ply only.

    Exhaustive joint enumeration at 4 or fewer own ants (distinct
    destinations only); sequential greedy fixing above that, so
    crowded fights stay far under budget. A deadline, when given,
    stops either search early and returns the best joint so far,
    so giant late-game fights degrade instead of timing out. Ties
    keep the first joint, so play is deterministic. No lookahead.
    """
    _ = destination
    _ = enemy_locs
    options = [legal_dests(o, rows, cols, passable) for o in own_locs]
    if not options:
        return [], 0.0
    if len(options) <= 4:
        best: list[Loc] | None = None
        best_score = -math.inf
        checked = 0
        for joint in product(*options):
            candidate = list(joint)
            if len(set(candidate)) < len(candidate):
                continue
            checked += 1
            if deadline is not None and checked % 512 == 0 and not deadline():
                break
            score = worst_score_for_own(
                candidate, enemy_samples, attack_r2, rows, cols, own_weight
            )
            if score > best_score:
                best_score = score
                best = candidate
        if best is None:
            best = list(own_locs)
            best_score = worst_score_for_own(
                best, enemy_samples, attack_r2, rows, cols, own_weight
            )
        return best, best_score
    current = list(own_locs)
    current_score = worst_score_for_own(
        current, enemy_samples, attack_r2, rows, cols, own_weight
    )
    for i, opts in enumerate(options):
        if deadline is not None and not deadline():
            break
        placed = current[:]
        local_best = current[i]
        local_score = current_score
        for cand in opts:
            trial = current[:]
            trial[i] = cand
            if len(set(trial)) < len(trial):
                continue
            score = worst_score_for_own(
                trial, enemy_samples, attack_r2, rows, cols, own_weight
            )
            if score > local_score:
                local_score = score
                local_best = cand
        placed[i] = local_best
        current = placed
        current_score = worst_score_for_own(
            current, enemy_samples, attack_r2, rows, cols, own_weight
        )
    return current, current_score


def reachable_within(
    start: Loc,
    steps: int,
    passable: PassFn,
    destination: DestFn,
) -> set[Loc]:
    """Squares reachable from start within steps passable moves.

    Pure BFS, no board state, no side effects.
    """
    seen = {start}
    depth = {start: 0}
    queue: deque[Loc] = deque([start])
    while queue:
        cur = queue.popleft()
        if depth[cur] >= steps:
            continue
        for d in _DIRS:
            nxt = destination(cur, d)
            if nxt not in seen and passable(nxt):
                seen.add(nxt)
                depth[nxt] = depth[cur] + 1
                queue.append(nxt)
    return seen


def carve_fights(
    own_locs: list[Loc],
    enemy_locs: list[Loc],
    distance: DistFn,
    link: int = COMBAT_LINK,
    passable: PassFn | None = None,
    destination: DestFn | None = None,
    rows: int = 0,
    cols: int = 0,
    path_link: int = 0,
) -> list[tuple[list[Loc], list[Loc]]]:
    """Connected components over own+enemy ants linked within link.

    Two ants join one fight when their distance is link or less,
    transitively, so isolated duels solve alone and crowds solve
    together. When a passable map is given, an own/foe pair also
    needs a short water-free path (path_link steps) between them,
    so wall-separated pairs never carve phantom fights that dodge
    ghosts through stone. Own/own and foe/foe links stay
    distance-only. Pure: no board state, no side effects.
    """
    if path_link <= 0:
        path_link = WAR_LINK
    nodes: list[tuple[str, int]] = [("o", i) for i in range(len(own_locs))]
    nodes += [("e", i) for i in range(len(enemy_locs))]
    parent = list(range(len(nodes)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    def loc_of(node: tuple[str, int]) -> Loc:
        kind, i = node
        return own_locs[i] if kind == "o" else enemy_locs[i]

    _ = (rows, cols)
    reach_cache: dict[int, set[Loc]] = {}

    def foes_can_meet(own_idx: int, foe_loc: Loc) -> bool:
        if passable is None or destination is None:
            return True
        reach = reach_cache.get(own_idx)
        if reach is None:
            reach = reachable_within(
                own_locs[own_idx], path_link, passable, destination
            )
            reach_cache[own_idx] = reach
        return foe_loc in reach

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if distance(loc_of(nodes[i]), loc_of(nodes[j])) > link:
                continue
            ki, ii = nodes[i]
            kj, jj = nodes[j]
            if ki != kj and passable is not None and destination is not None:
                own_idx, foe_loc = (
                    (ii, enemy_locs[jj]) if ki == "o" else (jj, enemy_locs[ii])
                )
                if not foes_can_meet(own_idx, foe_loc):
                    continue
            union(i, j)
    groups: dict[int, tuple[list[Loc], list[Loc]]] = {}
    for idx, node in enumerate(nodes):
        root = find(idx)
        entry = groups.setdefault(root, ([], []))
        kind, i = node
        if kind == "o":
            entry[0].append(own_locs[i])
        else:
            entry[1].append(enemy_locs[i])
    fights = [(o, e) for o, e in groups.values() if o and e]
    fights.sort(key=lambda fight: (sorted(fight[0]), sorted(fight[1])))
    return fights


# define a class with a do_turn method
# the Ants.run method will parse and update bot input
# it will also run the do_turn method for us
class Softmax11:
    def __init__(self):
        # define class level variables, will be remembered between turns
        self.visits: dict[tuple[int, int], int] = {}
        self.remembered_hills: set[tuple[int, int]] = set()
        self.prev_enemies: list[tuple[int, int]] = []
        self.ghosts: dict[tuple[int, int], int] = {}
        self._turn = 0

    # do_setup is run once at the start of the game
    # after the bot has received the game settings
    # the ants class is created and setup by the Ants.run method
    def do_setup(self, ants: Ants):
        # initialize data structures after learning the game settings
        self.visits = {}
        self.remembered_hills = set()
        self.prev_enemies = []
        self.ghosts = {}
        self._turn = 0

    # do turn is run once per turn
    # the ants class has the game state and is updated by the Ants.run method
    # it also has several helper methods to use
    def do_turn(self, ants: Ants):
        # Softmax11: champion economy/muster/guard/explore with a
        # ghost-memory deterministic pursuit core. Ghosts keep dead
        # foe squares threatening home hills while fresh; wall-aware
        # carving splits phantom fights; each real fight answers one
        # deterministic pursuit reply with the focus-rule argmax
        # joint, taking it at local majority (one down while ahead)
        # and retreating rejected ants to safety. Accepted stays hold
        # the firing line, the rest keep flowing. Food, guard,
        # muster, reinforce, explore, and walk-off are champion.
        self._turn += 1
        foods = ants.food()
        ants_list = ants.my_ants()
        my_set = set(ants_list)
        enemy_locs = [loc for loc, _ in ants.enemy_ants()]
        self.ghosts = remember_enemies(self.ghosts, enemy_locs, self._turn)
        sensed = sensed_enemies(enemy_locs, self.ghosts)
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
                for e in sensed
            )
        ]
        attack_r2 = ants.attackradius2 or 5
        rows, cols = ants.rows, ants.cols
        # Pursuit plan: one deterministic reply per carved fight.
        # Accepted fights map to the argmax joint; rejected fights
        # map to a directed retreat (or a hold when nowhere safer).
        fight_plan: dict[tuple[int, int], tuple[int, int]] = {}
        retreat_plan: dict[tuple[int, int], tuple[int, int]] = {}
        if enemy_locs:
            enemy_set = set(enemy_locs)

            def plan_passable(loc: tuple[int, int]) -> bool:
                return ants.passable(loc) and loc not in enemy_set

            fights = carve_fights(
                ants_list,
                enemy_locs,
                ants.distance,
                COMBAT_LINK,
                ants.passable,
                ants.destination,
                rows,
                cols,
            )
            ahead = len(ants_list) > len(enemy_locs)
            for own_group, foe_group in fights:
                if ants.time_remaining() < 50:
                    break
                reply = pursuit_enemy_joint(
                    foe_group,
                    ants_list,
                    attack_r2,
                    rows,
                    cols,
                    ants.passable,
                    ants.destination,
                    ants.distance,
                )[0]
                joint, _ = choose_own_joint(
                    own_group,
                    foe_group,
                    attack_r2,
                    rows,
                    cols,
                    plan_passable,
                    ants.destination,
                    [reply],
                    OWN_ANT_WEIGHT,
                    lambda: ants.time_remaining() >= 50,
                )
                dead = resolve_exchange(joint, reply, attack_r2, rows, cols)
                aggressive = resolve_aggressive(len(own_group), len(foe_group), ahead)
                if should_accept(dead[0], dead[1], aggressive):
                    for start, goal in zip(own_group, joint, strict=True):
                        fight_plan[start] = goal
                else:
                    for start in own_group:
                        retreat_plan[start] = retreat_dest(
                            start,
                            ants_list,
                            enemy_locs,
                            attack_r2,
                            rows,
                            cols,
                            ants.passable,
                            ants.distance,
                        )

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
            return near >= 10 and friends + 1 >= enemies

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
                # Softmax11: no food or guard move; the fight plan
                # holds the argmax joint for this ant: takes moves,
                # holds winning surrounds, else retreats (or holds
                # when nowhere is safer).
                dest = fight_plan.get(ant_loc)
                if dest is not None:
                    if dest == ant_loc:
                        if any(sq_dist(ant_loc, e) <= attack_r2 for e in enemy_locs):
                            moved = True
                            destinations.add(ant_loc)
                    else:
                        for d in ("n", "e", "s", "w"):
                            if ants.destination(ant_loc, d) == dest:
                                if try_step(ant_loc, d, safe=False):
                                    moved = True
                                break
                else:
                    away = retreat_plan.get(ant_loc)
                    if away is not None:
                        if away == ant_loc:
                            moved = True
                            destinations.add(ant_loc)
                        else:
                            for d in ("n", "e", "s", "w"):
                                if ants.destination(ant_loc, d) == away:
                                    if try_step(ant_loc, d, safe=False):
                                        moved = True
                                    break
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


def _intercept_square(
    hill: Loc,
    enemy_locs: list[Loc],
    distance: DistFn,
    passable: PassFn,
    rows: int,
    cols: int,
) -> Loc | None:
    """Off-hill intercept: nearest passable square to the midpoint."""
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
        Ants.run(Softmax11())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
