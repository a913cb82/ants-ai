#!/usr/bin/env python
"""A1K0N Dirichlet sampling combat entry (faithful top-10 sampler).

Self-contained: stdlib plus ants.py only, no combat.py import.
Economy, muster, guard, and explore are the champion Crowd logic
byte-identical; only the combat core is replaced with the a1k0n
approach from the RESEARCH.md row "a1k0n combat by random
sampling" (Dec 2011 forum thread):

- per-ant Dirichlet(1,1,1,1,1) over 5 moves (n/e/s/w/hold),
  gamma-sampled from stdlib random per combat decision,
- random ant order each turn (seeded RNG, seed stored per game
  for reproducibility),
- best-reply by provisional resolution: each sampled move is
  scored under provisional enemy best replies, where every enemy
  picks its most damaging reply under focus-battle rules (an ant
  dies iff min enemy weakness <= own weakness), with the xathis
  eval score = enemyDead*300 - myDead*180 - dist; the best
  sampled move is kept until the per-fight time budget runs out,
- sampling replaces minimax precisely because minimax is too
  conservative: the static majority filter (strict superiority,
  equal trades only with 10 near friends) refuses 1-for-1s that
  price at 300-180-dist > retreating, so the sampler sometimes
  advances where max-min holds (xathis contrast: xathis 1-ply
  minimax with the same eval refuses equal trades unless 14+
  friends are near; Odds moved our gate to 10; the sampler goes
  further by pricing the trade instead of gating it).

Provisional resolution is battle-local (manhattan 6 around the
moving ant) so a crowded board stays inside the turn budget;
enemies reply sequentially in list order, ties keep the first
move (n, e, s, w, hold), so scoring is deterministic given the
sampled move.
"""

import random
import time
from collections import deque
from collections.abc import Callable

from ants import Ants

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]
SqDistFn = Callable[[Loc, Loc], int]
PassFn = Callable[[Loc], bool]
DestFn = Callable[[Loc, str], Loc]
UnoccFn = Callable[[Loc], bool]

CLUSTER_R = 8
DENIAL_ENEMIES = 3
DENIAL_CLAIMS = 2
_CELL = CLUSTER_R + 1

# A1K0N sampler: five moves in Dirichlet order, per-fight time
# budget per combat decision, battle-local resolution radius.
MOVES = ("n", "e", "s", "w", "hold")
ENEMY_MOVES = ("n", "e", "s", "w", "hold")
FIGHT_BUDGET = 0.005
LOCAL_R = 6

# Champion Odds gate, kept for the non-combat safety filter only:
# equal trades (friends + 1 == enemies) need this many near
# friends (within 10 steps) to be accepted outside the sampler.
EQUAL_TRADE_NEAR = 10


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


def dirichlet_sample(rng: random.Random, n: int = 5) -> list[float]:
    """One Dirichlet(1, ..., 1) draw over n moves via gamma sampling.

    Each of the n unit-exponential draws (gammavariate(1, 1)) is
    normalized by the total, so the weights are positive and sum
    to 1. Pure: randomness only from the passed RNG, so the same
    seed replays the same stream.
    """
    draws = [rng.gammavariate(1.0, 1.0) for _ in range(n)]
    total = sum(draws)
    return [d / total for d in draws]


def turn_order(
    ants_list: list[Loc],
    enemy_locs: list[Loc],
    distance: DistFn,
    rng: random.Random,
) -> list[int]:
    """Random ant order for one turn, drawn from the game RNG.

    A uniform shuffle of the ant indices, so combat decisions
    never favor engine order. Pure apart from the RNG: the same
    seed replays the same order.
    """
    _ = enemy_locs, distance
    order = list(range(len(ants_list)))
    rng.shuffle(order)
    return order


def resolve_focus(
    my_pos: list[Loc],
    foe_pos: list[Loc],
    attack_r2: int,
    sq_dist: SqDistFn,
) -> tuple[set[int], set[int]]:
    """Focus-battle casualties for hypothetical positions.

    Weakness is the count of enemies within attack range; an ant
    with no enemy nearby cannot die, otherwise it dies iff its
    most focused nearby enemy is at least as focused (min enemy
    weakness <= own weakness) -- exactly the engine's
    do_attack_focus rule. Returns dead index sets for both sides.
    Pure: no board state, no side effects.
    """
    my_near: list[list[int]] = []
    for m in my_pos:
        near = [j for j, q in enumerate(foe_pos) if sq_dist(m, q) <= attack_r2]
        my_near.append(near)
    foe_near: list[list[int]] = []
    for q in foe_pos:
        near = [i for i, m in enumerate(my_pos) if sq_dist(m, q) <= attack_r2]
        foe_near.append(near)
    my_weak = [len(near) for near in my_near]
    foe_weak = [len(near) for near in foe_near]
    my_dead = {
        i
        for i, near in enumerate(my_near)
        if near and min(foe_weak[j] for j in near) <= my_weak[i]
    }
    foe_dead = {
        j
        for j, near in enumerate(foe_near)
        if near and min(my_weak[i] for i in near) <= foe_weak[j]
    }
    return my_dead, foe_dead


def combat_score(
    my_dead: int,
    foe_dead: int,
    my_pos: list[Loc],
    foe_pos: list[Loc],
    distance: DistFn,
) -> int:
    """Xathis combat eval: enemyDead*300 - myDead*180 - dist.

    Dist is the sum over our ants of the distance to the nearest
    visible enemy (0 with no enemies), pulling ants toward the
    enemy even when no trade is on. Pure: integer arithmetic.
    """
    dist = sum(min(distance(m, q) for q in foe_pos) for m in my_pos) if foe_pos else 0
    return foe_dead * 300 - my_dead * 180 - dist


def is_safe_step(
    nloc: Loc,
    self_loc: Loc,
    ants_list: list[Loc],
    enemy_locs: list[Loc],
    attack_r2: int,
    sq_dist: SqDistFn,
    distance: DistFn,
    near_gate: int = EQUAL_TRADE_NEAR,
) -> bool:
    """Champion static majority filter for one planned step.

    Strict superiority accepts; otherwise equal trades need
    near_gate friends within 10 steps. The combat sampler prices
    trades instead of gating them, so it may accept steps this
    refuses. Pure: no board state, no side effects.
    """
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
        if distance(nloc, f) <= 10:
            near += 1
    if friends + 1 > enemies:
        return True
    return near >= near_gate and friends + 1 >= enemies


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


def best_reply_score(
    my_local: list[Loc],
    foe_local: list[Loc],
    attack_r2: int,
    sq_dist: SqDistFn,
    distance: DistFn,
    destination: DestFn,
    passable: PassFn,
) -> int:
    """Our combat eval after provisional enemy best replies.

    Each enemy in list order picks the passable reply (n/e/s/w or
    hold) minimizing our eval, ties keeping the first move; the
    returned score resolves the resulting positions under focus
    rules. Deterministic given the positions. Pure apart from the
    passed board functions.
    """
    foes = list(foe_local)
    for j in range(len(foes)):
        best_q = foes[j]
        best_s: int | None = None
        for d in ENEMY_MOVES:
            q = foes[j] if d == "hold" else destination(foes[j], d)
            if d != "hold" and not passable(q):
                continue
            trial = foes[:j] + [q] + foes[j + 1 :]
            my_dead, foe_dead = resolve_focus(my_local, trial, attack_r2, sq_dist)
            s = combat_score(len(my_dead), len(foe_dead), my_local, trial, distance)
            if best_s is None or s < best_s:
                best_s = s
                best_q = q
        foes[j] = best_q
    my_dead, foe_dead = resolve_focus(my_local, foes, attack_r2, sq_dist)
    return combat_score(len(my_dead), len(foe_dead), my_local, foes, distance)


def sample_fight_move(
    ant_loc: Loc,
    my_pos: list[Loc],
    foe_pos: list[Loc],
    attack_r2: int,
    distance: DistFn,
    sq_dist: SqDistFn,
    destination: DestFn,
    passable: PassFn,
    unoccupied: UnoccFn,
    claimed: set[Loc],
    rows: int,
    cols: int,
    rng: random.Random,
    budget: float = FIGHT_BUDGET,
) -> str:
    """A1K0N sampled combat move for one ant within a time budget.

    Legal steps (passable, unoccupied, unclaimed) plus hold are
    the candidates; hold is the baseline. Until the budget runs
    out, each iteration draws a Dirichlet(1*5) distribution, draws
    one move from it, and scores it under provisional enemy best
    replies (focus rules, xathis eval); the best sampled move is
    kept. No local foe means no fight: hold, so the caller falls
    through to muster/explore. Always returns a legal move.
    """
    _ = rows, cols
    try:
        idx = my_pos.index(ant_loc)
    except ValueError:
        return "hold"
    options: list[str] = []
    for d in ("n", "e", "s", "w"):
        dest = destination(ant_loc, d)
        if dest in claimed or not passable(dest) or not unoccupied(dest):
            continue
        options.append(d)
    local_my = [i for i, p in enumerate(my_pos) if distance(p, ant_loc) <= LOCAL_R]
    local_foe = [j for j, q in enumerate(foe_pos) if distance(q, ant_loc) <= LOCAL_R]
    if not local_foe:
        return "hold"
    base_my = [my_pos[i] for i in local_my]
    base_foe = [foe_pos[j] for j in local_foe]
    mover_k = local_my.index(idx)

    def score_with(mover_pos: Loc) -> int:
        my_local = base_my[:mover_k] + [mover_pos] + base_my[mover_k + 1 :]
        return best_reply_score(
            my_local, base_foe, attack_r2, sq_dist, distance, destination, passable
        )

    best_move = "hold"
    best_s = score_with(ant_loc)
    deadline = time.perf_counter() + budget
    while True:
        weights = dirichlet_sample(rng)
        pick = 4
        roll = rng.random()
        cum = 0.0
        for k, w in enumerate(weights):
            cum += w
            if roll < cum:
                pick = k
                break
        cand = MOVES[pick]
        if cand != "hold" and cand in options:
            s = score_with(destination(ant_loc, cand))
            if s > best_s:
                best_s = s
                best_move = cand
        if time.perf_counter() >= deadline:
            break
    return best_move


# define a class with a do_turn method
# the Ants.run method will parse and update bot input
# it will also run the do_turn method for us
class Dirichlet:
    def __init__(self, seed: int = 0):
        # define class level variables, will be remembered between turns
        self.visits: dict[tuple[int, int], int] = {}
        self.remembered_hills: set[tuple[int, int]] = set()
        self.prev_enemies: list[tuple[int, int]] = []
        # Game seed for the combat RNG: stored per game so every
        # turn order and Dirichlet draw replays exactly.
        self.seed = seed
        self.rng = random.Random(seed)

    # do_setup is run once at the start of the game
    # after the bot has received the game settings
    # the ants class is created and setup by the Ants.run method
    def do_setup(self, ants: Ants):
        # initialize data structures after learning the game settings
        self.visits = {}
        self.remembered_hills = set()
        self.prev_enemies = []
        self.rng = random.Random(self.seed)

    # do turn is run once per turn
    # the ants class has the game state and is updated by the Ants.run method
    # it also has several helper methods to use
    def do_turn(self, ants: Ants):
        # Dirichlet: Crowd's wiring (Denial's economy, off-hill
        # screening, 10-gate equal trades outside combat, muster,
        # reinforce, explore, walk-off), except the combat core is
        # the a1k0n sampler -- random ant order, Dirichlet(1*5)
        # move distributions, provisional best-reply resolution
        # under focus rules until the per-fight budget runs out.
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

        destinations: set[tuple[int, int]] = set()
        held: list[tuple[int, int]] = []
        anchored: set[tuple[int, int]] = set()
        for ai in turn_order(ants_list, enemy_locs, ants.distance, self.rng):
            # Random order carries the original ant index, so food
            # claims still key on the right ant; only the move
            # sequence changes, sampled per the a1k0n approach.
            ant_loc = ants_list[ai]
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
                # A1K0N sampling combat: Dirichlet(1*5) move draws
                # scored under provisional enemy best replies until
                # the per-fight budget runs out. The eval prices
                # 1-for-1s at 300-180-dist, so the sampler sometimes
                # advances where the static filter above holds;
                # hold falls through to muster/explore below.
                move = sample_fight_move(
                    ant_loc,
                    ants_list,
                    enemy_locs,
                    attack_r2,
                    ants.distance,
                    sq_dist,
                    ants.destination,
                    ants.passable,
                    ants.unoccupied,
                    destinations,
                    rows,
                    cols,
                    self.rng,
                    FIGHT_BUDGET,
                )
                if move != "hold" and try_step(ant_loc, move, safe=False):
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
        Ants.run(Dirichlet())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
