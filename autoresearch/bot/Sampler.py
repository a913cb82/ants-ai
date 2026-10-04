#!/usr/bin/env python
import random
import time
from collections import deque
from collections.abc import Callable

from ants import Ants

Loc = tuple[int, int]
DistFn = Callable[[Loc, Loc], int]

SAMPLER_MS = 150
SAMPLER_ROUNDS = 200
K_ENEMY_DEAD = 300
K_MY_DEAD = 180

CombatMove = str | None  # 'n', 'e', 's', 'w', or None for hold


def torus_sq(a: Loc, b: Loc, rows: int, cols: int) -> int:
    # Squared toroidal distance; matches the engine's attackradius2 test.
    dr = abs(a[0] - b[0])
    dr = min(dr, rows - dr) if rows else dr
    dc = abs(a[1] - b[1])
    dc = min(dc, cols - dc) if cols else dc
    return dr * dr + dc * dc


def torus_man(a: Loc, b: Loc, rows: int, cols: int) -> int:
    dr = abs(a[0] - b[0])
    dr = min(dr, rows - dr) if rows else dr
    dc = abs(a[1] - b[1])
    dc = min(dc, cols - dc) if cols else dc
    return dr + dc


def focus_deaths(
    my_pos: list[Loc], en_pos: list[Loc], r2: int, rows: int, cols: int
) -> tuple[set[int], set[int]]:
    # One step of the engine's focus combat: weakness is the nearby
    # enemy count; an ant dies when its weakest opponent's weakness
    # is at most its own. Immune with no nearby enemies.
    my_foes: list[list[int]] = [[] for _ in my_pos]
    en_foes: list[list[int]] = [[] for _ in en_pos]
    for i, a in enumerate(my_pos):
        for j, b in enumerate(en_pos):
            if torus_sq(a, b, rows, cols) <= r2:
                my_foes[i].append(j)
                en_foes[j].append(i)
    my_weak = [len(f) for f in my_foes]
    en_weak = [len(f) for f in en_foes]
    my_dead = {
        i
        for i, foes in enumerate(my_foes)
        if foes and min(en_weak[j] for j in foes) <= my_weak[i]
    }
    en_dead = {
        j
        for j, foes in enumerate(en_foes)
        if foes and min(my_weak[i] for i in foes) <= en_weak[j]
    }
    return my_dead, en_dead


def battle_score(
    my_pos: list[Loc],
    en_pos: list[Loc],
    my_dead: set[int],
    en_dead: set[int],
    rows: int,
    cols: int,
) -> int:
    # xathis: killing weighs 300, losing 180, survivors closing on
    # the enemy break ties. A supported hold that kills for free
    # (+300) outscores a naked equal trade (+120).
    live_en = [p for j, p in enumerate(en_pos) if j not in en_dead]
    dist = 0
    for i, a in enumerate(my_pos):
        if i in my_dead or not live_en:
            continue
        dist += min(torus_man(a, b, rows, cols) for b in live_en)
    return K_ENEMY_DEAD * len(en_dead) - K_MY_DEAD * len(my_dead) - dist


def legal_combat_moves(ants: Ants, loc: Loc) -> list[CombatMove]:
    # Passable, unoccupied steps plus hold. Hold first so exact ties
    # keep the ant still (anti-trade).
    moves: list[CombatMove] = [None]
    for d in ("n", "e", "s", "w"):
        nxt = ants.destination(loc, d)
        if ants.passable(nxt) and ants.unoccupied(nxt):
            moves.append(d)
    return moves


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
                members = buckets.get((br + dbr, bc + dbc))
                if not members:
                    continue
                for j in members:
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
class Sampler:
    def __init__(self):
        # define class level variables, will be remembered between turns
        self.visits: dict[tuple[int, int], int] = {}
        self.remembered_hills: set[tuple[int, int]] = set()
        self.prev_enemies: list[tuple[int, int]] = []
        self.sampler_rounds = SAMPLER_ROUNDS
        self.sampler_ms = SAMPLER_MS
        self._rng = random.Random()

    # do_setup is run once at the start of the game
    # after the bot has received the game settings
    # the ants class is created and setup by the Ants.run method
    def do_setup(self, ants: Ants):
        # initialize data structures after learning the game settings
        self.visits = {}
        self.remembered_hills = set()
        self.prev_enemies = []
        self.sampler_rounds = SAMPLER_ROUNDS
        self.sampler_ms = SAMPLER_MS

    def sample_battle_orders(
        self,
        ants: Ants,
        ants_list: list[Loc],
        enemy_locs: list[Loc],
        max_rounds: int | None = None,
        budget_s: float | None = None,
        rng: random.Random | None = None,
    ) -> tuple[dict[int, CombatMove], int]:
        # Dirichlet sampler over contact combat. Per engaged ant keep
        # counts over legal moves (init 1 each); each round picks a
        # random engaged ant (own maximize, enemy minimize the same
        # battle score), scores every legal move with one step of
        # provisional focus resolution, and increments the best move's
        # count. Stops at the time budget or the round cap. Highest
        # count wins; ties fall back to the legacy check (no entry).
        # Returns ({ant index: move}, rounds run).
        if max_rounds is None:
            max_rounds = self.sampler_rounds
        if budget_s is None:
            budget_s = self.sampler_ms / 1000.0
        if rng is None:
            rng = self._rng
        rows, cols = ants.rows, ants.cols
        r2 = ants.attackradius2 or 5
        engaged_own = [
            ai
            for ai, a in enumerate(ants_list)
            if any(torus_sq(a, e, rows, cols) <= r2 for e in enemy_locs)
        ]
        engaged_en = [
            ei
            for ei, e in enumerate(enemy_locs)
            if any(torus_sq(e, a, rows, cols) <= r2 for a in ants_list)
        ]
        if not engaged_own or max_rounds <= 0:
            return {}, 0
        own_moves = {ai: legal_combat_moves(ants, ants_list[ai]) for ai in engaged_own}
        en_moves = {ei: legal_combat_moves(ants, enemy_locs[ei]) for ei in engaged_en}
        own_counts = {ai: dict.fromkeys(ms, 1) for ai, ms in own_moves.items()}
        en_counts = {ei: dict.fromkeys(ms, 1) for ei, ms in en_moves.items()}
        pool = [("own", ai) for ai in engaged_own] + [("en", ei) for ei in engaged_en]
        start = time.perf_counter()
        rounds = 0
        while rounds < max_rounds:
            if time.perf_counter() - start >= budget_s:
                break
            side, idx = rng.choice(pool)
            if side == "own":
                best: CombatMove = own_moves[idx][0]
                best_score: int | None = None
                for m in own_moves[idx]:
                    cand = list(ants_list)
                    if m is not None:
                        cand[idx] = ants.destination(ants_list[idx], m)
                    my_dead, en_dead = focus_deaths(cand, enemy_locs, r2, rows, cols)
                    s = battle_score(cand, enemy_locs, my_dead, en_dead, rows, cols)
                    if best_score is None or s > best_score:
                        best_score = s
                        best = m
                own_counts[idx][best] += 1
            else:
                worst: CombatMove = en_moves[idx][0]
                worst_score: int | None = None
                for m in en_moves[idx]:
                    cand_en = list(enemy_locs)
                    if m is not None:
                        cand_en[idx] = ants.destination(enemy_locs[idx], m)
                    my_dead, en_dead = focus_deaths(ants_list, cand_en, r2, rows, cols)
                    s = battle_score(ants_list, cand_en, my_dead, en_dead, rows, cols)
                    if worst_score is None or s < worst_score:
                        worst_score = s
                        worst = m
                en_counts[idx][worst] += 1
            rounds += 1
        orders: dict[int, CombatMove] = {}
        for ai in engaged_own:
            counts = own_counts[ai]
            top = max(counts.values())
            winners = [m for m, v in counts.items() if v == top]
            if len(winners) == 1:
                orders[ai] = winners[0]
        return orders, rounds

    # do turn is run once per turn
    # the ants class has the game state and is updated by the Ants.run method
    # it also has several helper methods to use
    def do_turn(self, ants: Ants):
        # Sampler: Denial's denial, except ants in contact (a visible
        # enemy within attack range) follow a time-boxed Dirichlet
        # sampler over provisional combat instead of the static
        # local-majority check. Battling sampled. Homeward structure, wide fallback,
        # aggression, walk-off, food, and exploration match iteration
        # 76. Hunt always; ahead on hills, hunters skip the safety
        # filter. Closeouts need teeth, not patience.
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

        # Dirichlet contact combat: engaged ants follow sampled orders
        # (highest count wins; ties and quiet ants keep legacy below).
        # Zero rounds disables the sampler exactly.
        sampler_orders, _ = self.sample_battle_orders(ants, ants_list, enemy_locs)
        destinations: set[tuple[int, int]] = set()
        held: list[tuple[int, int]] = []
        anchored: set[tuple[int, int]] = set()
        for ai, ant_loc in enumerate(ants_list):
            self.visits[ant_loc] = self.visits.get(ant_loc, 0) + 1
            if ai in sampler_orders:
                # Sampled contact combat replaces the static check.
                smove = sampler_orders[ai]
                if smove is None:
                    held.append(ant_loc)
                    if ants.time_remaining() < 10:
                        break
                    continue
                sdest = ants.destination(ant_loc, smove)
                if (
                    sdest not in destinations
                    and ants.passable(sdest)
                    and ants.unoccupied(sdest)
                ):
                    ants.issue_order((ant_loc, smove))
                    destinations.add(sdest)
                    if ants.time_remaining() < 10:
                        break
                    continue
                # Spoiled: fall through to the legacy path.
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
        Ants.run(Sampler())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
