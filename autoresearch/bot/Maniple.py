#!/usr/bin/env python
"""Maniple: no attack without a majority.

A maniple never fights alone, and a legion never marches into a
stronger foe. The majority is weighed against the strongest
rival in sight, not the sum of every flag on the board. Parity
is standing: food is contested, empty hills are raided, and
reserves march the nearest hill they can actually take. Only a
strictly stronger rival forces the turtle -- contested food is
ceded, marches hold, and reserves step home (testudo) when home
is close, or forage locally when it is past the horizon. Every
attack needs a majority -- local (a joined pair, a backed-up
step, ten near friends for an even trade, a lone duel only while
strictly ahead) or global (an assault needs 2:1 over the hill's
campers). Guards hold corner posts instead of piling onto the
hill, so home stays spawnable. Gathering stands off: the engine
ignores moves onto food, so adjacent ants hold by proximity and
paths never route through food squares; an unsafe holder
yields the meal rather than dying on it. Pathing searches 800
squares deep, so far missions resolve instead of silently
degrading to explore, and simultaneous explorers fan out on a
per-ant rotation instead of queueing north. No step is ever
fearless; the safety filter always has the last word.
"""

from collections import deque

from ants import Ants

SEEK_RANGE = 8
DIRS = ("n", "e", "s", "w")
PACK_NEED = 3
PACK_RADIUS = 10
EVEN_TRADE_NEAR = 10
CLUSTER_R = 8
DENIAL_FOES = 3
DENIAL_CLAIMS = 2
GUARD_RANGE = 10
CLOSING_RANGE = 16
# Pathing horizon. A 250-step budget silently drops ~12-step
# missions (open-field BFS fans out to ~2d^2 squares), so far
# hills degrade to explore without a trace. 800 reaches
# ~20 steps; the search still exits the moment the goal is
# generated, so the common short mission costs the same.
PATH_BUDGET = 800
# Assault needs 2:1 over the hill's campers. Defenders spawn on
# the hill, so an even march trades one-for-one forever while
# the field drains; twice their number converts the raze.
CAMP_RANGE = 12
ASSAULT_MARGIN = 2
# Testudo horizon. A march home longer than this outlasts the
# fight it would join, so the ant forages locally instead of
# trekking across the map to arrive after the war.
TESTUDO_REACH = 20


def has_majority(mine: int, foes: int) -> bool:
    """Global majority gate: attack only while strictly ahead.

    Even armies hold; empty armies never march. Pure integer
    compare, no side effects.
    """
    return mine > 0 and mine > foes


def strongest_rival(enemy_ants: list[tuple[tuple[int, int], int]]) -> int:
    """Biggest single visible rival army, by owner.

    Nine small FFA rivals are not one big army: the majority
    gate weighs the strongest of them, so a maniple still
    marches and claims while it leads every rival in sight.
    Pure: groups owner ids, no side effects.
    """
    counts: dict[int, int] = {}
    for _, owner in enemy_ants:
        counts[owner] = counts.get(owner, 0) + 1
    return max(counts.values(), default=0)


class Maniple:
    def __init__(self):
        self.visits: dict[tuple[int, int], int] = {}
        self.hills: set[tuple[int, int]] = set()
        self.prev_foes: list[tuple[int, int]] = []

    def do_setup(self, ants: Ants):
        self.visits = {}
        self.hills = set()
        self.prev_foes = []

    def do_turn(self, ants: Ants):
        mine = ants.my_ants()
        seen = ants.enemy_ants()
        foes = [loc for loc, _ in seen]
        foods = ants.food()
        my_set = set(mine)
        for hloc, _ in ants.enemy_hills():
            self.hills.add(hloc)
        for hloc in list(self.hills):
            if hloc in my_set:
                self.hills.discard(hloc)
        hills = sorted(self.hills)
        home = ants.my_hills()
        attack_r2 = ants.attackradius2 or 5
        rows, cols = ants.rows, ants.cols

        def sq(a: tuple[int, int], b: tuple[int, int]) -> int:
            dr = abs(a[0] - b[0])
            dr = min(dr, rows - dr) if rows else dr
            dc = abs(a[1] - b[1])
            dc = min(dc, cols - dc) if cols else dc
            return dr * dr + dc * dc

        def safe_step(nloc: tuple[int, int], self_loc: tuple[int, int]) -> bool:
            enemies = 0
            for e in foes:
                if sq(nloc, e) <= attack_r2:
                    enemies += 1
                    if enemies >= len(mine):
                        break
            if enemies == 0:
                return True
            friends = 0
            near = 0
            for f in mine:
                if f == self_loc:
                    continue
                if sq(nloc, f) <= attack_r2:
                    friends += 1
                if ants.distance(nloc, f) <= 10:
                    near += 1
            if friends + 1 > enemies:
                return True
            return near >= EVEN_TRADE_NEAR and friends + 1 >= enemies

        # The engine ignores moves onto food ("move blocked"),
        # like water: gathering works by proximity, so paths
        # never route through food squares.
        food_set = set(foods)

        def first_step(
            start: tuple[int, int],
            goal: tuple[int, int],
            budget: int = PATH_BUDGET,
        ) -> str | None:
            if start == goal:
                return None
            if not ants.passable(goal) or goal in food_set:
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
                    if nxt in parent or not ants.passable(nxt) or nxt in food_set:
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

        def approach_food(start: tuple[int, int], meal: tuple[int, int]) -> str | None:
            # Shortest land path to adjacency with the meal: the
            # first step of the shortest route to any square one
            # step from the food. None when already adjacent (the
            # caller holds) or unreachable within the budget.
            if ants.distance(start, meal) <= 1:
                return None
            parent: dict[tuple[int, int], tuple[tuple[int, int], str]] = {}
            parent[start] = (start, "")
            queue: deque[tuple[int, int]] = deque([start])
            expanded = 0
            while queue and expanded < PATH_BUDGET:
                cur = queue.popleft()
                expanded += 1
                for d in ("n", "e", "s", "w"):
                    nxt = ants.destination(cur, d)
                    if nxt in parent or not ants.passable(nxt) or nxt in food_set:
                        continue
                    parent[nxt] = (cur, d)
                    if ants.distance(nxt, meal) <= 1:
                        node = nxt
                        while parent[node][0] != start:
                            node = parent[node][0]
                        return parent[node][1]
                    queue.append(nxt)
            return None

        def packed(ant: tuple[int, int]) -> bool:
            found = 0
            for f in mine:
                if f != ant and ants.distance(ant, f) <= PACK_RADIUS:
                    found += 1
                    if found >= PACK_NEED:
                        return True
            return False

        def nearest_foe(ant: tuple[int, int]) -> tuple[int, int] | None:
            best: tuple[int, int] | None = None
            best_d = SEEK_RANGE + 1
            for e in foes:
                d = ants.distance(ant, e)
                if d <= SEEK_RANGE and d < best_d:
                    best_d = d
                    best = e
            return best

        def contact_at(dest: tuple[int, int]) -> tuple[int, int] | None:
            best: tuple[int, int] | None = None
            best_d = attack_r2 + 1
            for e in foes:
                d = sq(dest, e)
                if d <= attack_r2 and d < best_d:
                    best_d = d
                    best = e
            return best

        def halfway(hill: tuple[int, int]) -> tuple[int, int] | None:
            if not foes or rows <= 0 or cols <= 0:
                return None
            foe = min(foes, key=lambda e: ants.distance(hill, e))
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
            if ants.passable(mid) and mid not in food_set:
                return mid
            seen = {mid}
            queue: deque[tuple[int, int]] = deque([mid])
            while queue:
                cur = queue.popleft()
                for step in ((-1, 0), (0, 1), (1, 0), (0, -1)):
                    nxt = ((cur[0] + step[0]) % rows, (cur[1] + step[1]) % cols)
                    if nxt in seen:
                        continue
                    seen.add(nxt)
                    if ants.passable(nxt) and nxt not in food_set:
                        return nxt
                    queue.append(nxt)
            return None

        # No engagement without a majority -- not even for food.
        # Ahead, contested clusters (3+ foes within 8 of a member
        # food) draw exactly two ants on nearest pairs; the
        # cluster's other foods go unclaimed. Strictly behind
        # the strongest rival, the whole contested cluster is
        # ceded: no claim fires and the greedy pass skips it
        # too. Everything else is global nearest, one ant per
        # food.
        # Standing means parity or better with the strongest
        # rival in sight. Only a strictly stronger rival cedes
        # contested food and cancels marches; at parity the
        # economy contests and empty hills raid. The ahead-only
        # duel keeps the strict gate: mutual death at parity is
        # a wash, never an edge.
        rival = strongest_rival(seen)
        advance = has_majority(len(mine), rival)
        standing = len(mine) > 0 and len(mine) >= rival
        denial_claims = 0 if len(mine) < rival else DENIAL_CLAIMS
        claims: dict[int, tuple[int, int]] = {}
        if foods and mine:
            n = len(foods)
            parent = list(range(n))

            def find(a: int) -> int:
                while parent[a] != a:
                    parent[a] = parent[parent[a]]
                    a = parent[a]
                return a

            for i in range(n):
                for j in range(i + 1, n):
                    if ants.distance(foods[i], foods[j]) <= CLUSTER_R:
                        ri, rj = find(i), find(j)
                        if ri != rj:
                            parent[max(ri, rj)] = min(ri, rj)
            roots = [find(i) for i in range(n)]
            heat: dict[int, int] = {}
            for e in foes:
                seen_roots: set[int] = set()
                for i, f in enumerate(foods):
                    if ants.distance(e, f) <= CLUSTER_R:
                        seen_roots.add(roots[i])
                for r in seen_roots:
                    heat[r] = heat.get(r, 0) + 1
            hot = {r for r, c in heat.items() if c >= DENIAL_FOES}
            taken_food: set[int] = set()
            denied: set[int] = set()
            members: dict[int, list[int]] = {}
            for i, r in enumerate(roots):
                if r in hot:
                    members.setdefault(r, []).append(i)
                    denied.add(i)
            for group in members.values():
                cand = sorted(
                    (ants.distance(a, foods[fi]), ai, fi)
                    for ai, a in enumerate(mine)
                    for fi in group
                )
                picks = 0
                for _, ai, fi in cand:
                    if picks >= denial_claims:
                        break
                    if ai not in claims and fi not in taken_food:
                        claims[ai] = foods[fi]
                        taken_food.add(fi)
                        picks += 1
            pairs = sorted(
                (ants.distance(a, f), ai, fi)
                for ai, a in enumerate(mine)
                for fi, f in enumerate(foods)
            )
            for _, ai, fi in pairs:
                if fi in denied:
                    continue
                if ai not in claims and fi not in taken_food:
                    claims[ai] = foods[fi]
                    taken_food.add(fi)

        # Heading memory: match each visible foe to a last-turn
        # square at distance 0 or 1, so closing foes read as
        # threats one step earlier.
        leftovers = self.prev_foes[:]
        shut: dict[tuple[int, int], tuple[int, int]] = {}
        for cur in foes:
            match = None
            match_d = 2
            for p in leftovers:
                d = ants.distance(cur, p)
                if d < match_d:
                    match_d = d
                    match = p
            if match is not None:
                leftovers.remove(match)
                shut[cur] = match
        self.prev_foes = foes

        def closing(cur: tuple[int, int], hill: tuple[int, int]) -> bool:
            prev = shut.get(cur)
            return prev is not None and ants.distance(prev, hill) > ants.distance(
                cur, hill
            )

        threatened = [
            h
            for h in home
            if any(
                ants.distance(h, e) <= GUARD_RANGE
                or (ants.distance(h, e) <= CLOSING_RANGE and closing(e, h))
                for e in foes
            )
        ]

        # Join pre-pass: claim-free seekers whose step would touch
        # a foe commit on it; foes drawing 2+ commits release all
        # committers for an even trade without the near gate.
        commits: dict[int, tuple[int, int]] = {}
        if foes:
            for cai, cant in enumerate(mine):
                if claims.get(cai) is not None:
                    continue
                chase = nearest_foe(cant)
                if chase is None:
                    continue
                cstep = first_step(cant, chase)
                if cstep is None:
                    continue
                touched = contact_at(ants.destination(cant, cstep))
                if touched is not None:
                    commits[cai] = touched
        counts: dict[tuple[int, int], int] = {}
        for foe_loc in commits.values():
            counts[foe_loc] = counts.get(foe_loc, 0) + 1
        joined = {ai for ai, foe_loc in commits.items() if counts[foe_loc] >= 2}

        destinations: set[tuple[int, int]] = set()
        held: list[tuple[int, int]] = []
        anchored: set[tuple[int, int]] = set()

        def issue(ant_loc: tuple[int, int], direction: str, check: bool) -> bool:
            nloc = ants.destination(ant_loc, direction)
            if (
                nloc in destinations
                or not ants.passable(nloc)
                or not ants.unoccupied(nloc)
            ):
                return False
            if check and not safe_step(nloc, ant_loc):
                return False
            ants.issue_order((ant_loc, direction))
            destinations.add(nloc)
            return True

        def issue_join(ant_loc: tuple[int, int], direction: str) -> bool:
            nloc = ants.destination(ant_loc, direction)
            if (
                nloc in destinations
                or not ants.passable(nloc)
                or not ants.unoccupied(nloc)
            ):
                return False
            bad = sum(1 for e in foes if sq(nloc, e) <= attack_r2)
            if bad > 0:
                backup = sum(
                    1 for f in mine if f != ant_loc and sq(nloc, f) <= attack_r2
                )
                if backup + 1 < bad:
                    return False
            ants.issue_order((ant_loc, direction))
            destinations.add(nloc)
            return True

        for ai, ant_loc in enumerate(mine):
            self.visits[ant_loc] = self.visits.get(ant_loc, 0) + 1
            moved = False
            meal = claims.get(ai)
            if meal is not None:
                if ants.distance(ant_loc, meal) <= 1:
                    # Stand-off: adjacent ants gather by proximity,
                    # so a safe holder stays instead of stepping
                    # onto the food (the engine would ignore the
                    # move) and jittering away on the fallback. An
                    # unsafe holder abandons the meal and falls
                    # through to seek safety elsewhere.
                    if safe_step(ant_loc, ant_loc):
                        moved = True
                else:
                    step = approach_food(ant_loc, meal)
                    if step is not None and issue(ant_loc, step, True):
                        moved = True
            if not moved and threatened:
                close = min(threatened, key=lambda h: ants.distance(ant_loc, h))
                if ant_loc != close and ants.distance(ant_loc, close) == 1:
                    # Post-holder: already on a corner post, so stand.
                    # No order issues, the hill stays spawnable, and
                    # the ring holds across turns instead of churning.
                    moved = True
                else:
                    if close in anchored:
                        post = halfway(close)
                        if post is None:
                            post = min(foes, key=lambda e: ants.distance(close, e))
                        step = first_step(ant_loc, post)
                    else:
                        anchored.add(close)
                        step = first_step(ant_loc, close)
                    if step is not None and issue(ant_loc, step, True):
                        moved = True
            if not moved and foes:
                mark = nearest_foe(ant_loc)
                if mark is not None and not packed(ant_loc):
                    pal = min(
                        (f for f in mine if f != ant_loc),
                        key=lambda f: ants.distance(ant_loc, f),
                        default=None,
                    )
                    if pal is not None:
                        pstep = first_step(ant_loc, pal)
                        if pstep is not None and issue(ant_loc, pstep, True):
                            moved = True
                    mark = None
                if mark is not None:
                    step = first_step(ant_loc, mark)
                    if step is not None:
                        if ai in joined:
                            if issue_join(ant_loc, step):
                                moved = True
                        else:
                            nloc = ants.destination(ant_loc, step)
                            foes_on = sum(1 for e in foes if sq(nloc, e) <= attack_r2)
                            pals_on = sum(
                                1
                                for f in mine
                                if f != ant_loc and sq(nloc, f) <= attack_r2
                            )
                            if (
                                pals_on == 0
                                and foes_on == 1
                                and advance
                                and issue_join(ant_loc, step)
                            ) or issue(ant_loc, step, True):
                                moved = True
            if not moved and hills:
                # First passing hill, nearest first: a defended
                # muster does not cancel the march, it yields to
                # the next hill the army can actually take.
                marched = False
                if standing:
                    ordered = sorted(
                        hills,
                        key=lambda h: sum(ants.distance(a, h) for a in mine),
                    )
                    for target in ordered:
                        camped = sum(
                            1 for e in foes if ants.distance(e, target) <= CAMP_RANGE
                        )
                        if len(mine) < ASSAULT_MARGIN * camped:
                            continue
                        step = first_step(ant_loc, target)
                        # Always filtered: no posture marches into
                        # contact it would refuse standing still.
                        if step is not None and issue(ant_loc, step, True):
                            moved = True
                            marched = True
                        break
                if not marched and home:
                    # Testudo: outnumbered, so step home instead of
                    # marching on a stronger foe's hill -- unless
                    # home is past the horizon, when the ant
                    # forages locally on the explore fallback.
                    keep = min(home, key=lambda h: ants.distance(ant_loc, h))
                    if ants.distance(ant_loc, keep) > TESTUDO_REACH:
                        keep = None
                    if keep is not None:
                        step = first_step(ant_loc, keep)
                        if step is not None and issue(ant_loc, step, True):
                            moved = True
            if not moved:
                # Spread the fallback: ties break in a per-ant
                # rotation instead of always north, so simultaneous
                # explorers fan out instead of queueing one way.
                rot = (ant_loc[0] + ant_loc[1]) % 4
                order = DIRS[rot:] + DIRS[:rot]
                for direction in sorted(
                    order,
                    key=lambda d: self.visits.get(ants.destination(ant_loc, d), 0),
                ):
                    if issue(ant_loc, direction, True):
                        moved = True
                        break
            if not moved:
                held.append(ant_loc)
            if ants.time_remaining() < 10:
                break
        hill_set = set(home)
        for ant_loc in held:
            if ant_loc in hill_set and ants.time_remaining() >= 10:
                for direction in ("s", "e", "w", "n"):
                    if issue(ant_loc, direction, True):
                        break


if __name__ == "__main__":
    try:
        import psyco

        psyco.full()
    except ImportError:
        pass

    try:
        Ants.run(Maniple())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
