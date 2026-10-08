#!/usr/bin/env python
"""Tercio: assault in company.

A tercio never raids alone. Every ant votes its nearest remembered
enemy hill; only hills drawing 2+ votes are assailable this turn, and
only their voters march. A solo voter harvests or scouts instead of
donating on a lone raid. Everything else is a stripped champion core:

- harvest: full greedy nearest-pair claims, never ceded -- contested
  food is still food, and a camped field denied to both sides beats a
  field gifted to the foe; ants already on the meal sit it out instead
  of exploring away, but never squat a home hill;
- guard: threatened home hills hold one anchor, extras screen the
  razer off the hill at the midpoint so home stays spawnable;
  last-seen razer squares haunt the guard for 3 turns, so a hill
  stays posted while its threat blinks out of sight;
- combat: champion safety (strict local majority, equal trades need
  10 near friends), joined pairs engage together, friendless 1v1 duels
  only while the visible army leads -- except a packed hunter advances
  fearlessly while fewer than 10 enemies are visible, and a company
  marches fearlessly while ahead on hills; never pack-up wandering;
- pathing: 800-square BFS horizon with a per-turn memo and a global
  expansion cap, falling back to greedy direction steps; orders
  reserve destinations while squares ants vacate stay enterable, so
  files march through each other and only home hills stay reserved;
- assault: companies march remembered hills, hold the siege when the
  approach is blocked, and lone arrivals inside the committed zone
  still step onto empty squares; razed hills are forgotten the moment
  they show visible and empty;
- explore: least-visited squares with a per-ant compass rotation so
  simultaneous scouts fan out instead of marching in a column;
- walk off home hills when held.
"""

from collections import deque

from ants import Ants

Loc = tuple[int, int]

DIRS = ("n", "e", "s", "w")
SEEK_RANGE = 8
GHOST_TTL = 3
PACK_NEED = 3
PACK_RADIUS = 10
CROWD_LIMIT = 10
EQUAL_TRADE_NEAR = 10
GUARD_RANGE = 10
CLOSING_RANGE = 16
PATH_BUDGET = 800
TURN_EXPANSIONS = 40000


def assign_food_targets(ants_list, foods, enemy_locs, distance, rows, cols):
    """Greedy nearest-pair claims over ALL foods; nothing is ever ceded.

    enemy_locs is accepted for signature parity with the denial bots
    but ignored: contested food still draws a harvester. Returns
    {ant_index: food_loc}.
    """
    target: dict[int, Loc] = {}
    if not foods or not ants_list:
        return target
    pairs = []
    for ai, ant_loc in enumerate(ants_list):
        for fi, food_loc in enumerate(foods):
            pairs.append((distance(ant_loc, food_loc), ai, fi))
    pairs.sort()
    claimed = set()
    for _, ai, fi in pairs:
        if ai not in target and fi not in claimed:
            target[ai] = foods[fi]
            claimed.add(fi)
    return target


def has_pack(ant_loc, ants_list, distance):
    """Whether an ant holds PACK_NEED+ friends within PACK_RADIUS steps."""
    found = 0
    for friend in ants_list:
        if friend == ant_loc:
            continue
        if distance(ant_loc, friend) <= PACK_RADIUS:
            found += 1
            if found >= PACK_NEED:
                return True
    return False


def company_hills(ants_list, hills, distance):
    """Hills drawing 2+ nearest-hill votes, mapped to their voters.

    Each ant votes its nearest remembered hill; hills with fewer than
    two voters are unassailable this turn (solo raids donate). Pure:
    no board state, no side effects.
    """
    votes: dict[Loc, list[Loc]] = {}
    for ant in ants_list:
        if not hills:
            break
        best = min(hills, key=lambda h: distance(ant, h))
        votes.setdefault(best, []).append(ant)
    return {h: v for h, v in votes.items() if len(v) >= 2}


class Tercio:
    def __init__(self):
        self.visits: dict[Loc, int] = {}
        self.remembered_hills: set[Loc] = set()
        self.prev_enemies: list[Loc] = []
        self.ghosts: dict[Loc, int] = {}
        self.turn = 0

    def do_setup(self, ants: Ants):
        self.visits = {}
        self.remembered_hills = set()
        self.prev_enemies = []
        self.ghosts = {}
        self.turn = 0

    def do_turn(self, ants: Ants):
        foods = ants.food()
        ants_list = ants.my_ants()
        my_set = set(ants_list)
        enemy_locs = [loc for loc, _ in ants.enemy_ants()]
        target = assign_food_targets(
            ants_list, foods, enemy_locs, ants.distance, ants.rows, ants.cols
        )
        seen_hills = set()
        for hloc, _ in ants.enemy_hills():
            self.remembered_hills.add(hloc)
            seen_hills.add(hloc)
        for hloc in list(self.remembered_hills):
            if hloc in my_set:
                self.remembered_hills.discard(hloc)
            elif hloc not in seen_hills:
                try:
                    if ants.visible(hloc):
                        # Visible but empty: razed or never there; forget it.
                        self.remembered_hills.discard(hloc)
                except AttributeError:
                    pass
        hills = sorted(self.remembered_hills)
        companies = company_hills(ants_list, hills, ants.distance)
        my_hills = ants.my_hills()
        # Heading match is O(E^2): cap the remembered side so a
        # mega-melee cannot eat the turn; unmatched extras read as
        # new spawns (no closing), range-10 guard still holds.
        unmatched = self.prev_enemies[:80]
        headings: dict[Loc, Loc] = {}
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
        self.turn += 1

        def closing(cur: Loc, hill: Loc) -> bool:
            prev = headings.get(cur)
            return prev is not None and ants.distance(prev, hill) > ants.distance(
                cur, hill
            )

        for g in list(self.ghosts):
            self.ghosts[g] -= 1
            if self.ghosts[g] <= 0:
                del self.ghosts[g]
        for e in enemy_locs:
            self.ghosts[e] = GHOST_TTL
        sensed = enemy_locs + [g for g in self.ghosts if g not in enemy_locs]
        threatened = [
            h
            for h in my_hills
            if any(
                ants.distance(h, e) <= GUARD_RANGE
                or (ants.distance(h, e) <= CLOSING_RANGE and closing(e, h))
                for e in sensed
            )
        ]
        attack_r2 = ants.attackradius2 or 5
        rows, cols = ants.rows, ants.cols

        def sq_dist(a: Loc, b: Loc) -> int:
            dr = abs(a[0] - b[0])
            dr = min(dr, rows - dr) if rows else dr
            dc = abs(a[1] - b[1])
            dc = min(dc, cols - dc) if cols else dc
            return dr * dr + dc * dc

        def foes_at(nloc: Loc, cap: int) -> int:
            n = 0
            for e in enemy_locs:
                if sq_dist(nloc, e) <= attack_r2:
                    n += 1
                    if n >= cap:
                        break
            return n

        def pals_at(nloc: Loc, self_loc: Loc, cap: int) -> int:
            n = 0
            for f in ants_list:
                if f == self_loc:
                    continue
                if sq_dist(nloc, f) <= attack_r2:
                    n += 1
                    if n >= cap:
                        break
            return n

        def is_safe(nloc: Loc, self_loc: Loc) -> bool:
            if enemy_locs:
                far = True
                for e in enemy_locs:
                    if ants.distance(nloc, e) <= GUARD_RANGE + 1:
                        far = False
                        break
                if far:
                    return True
            friends = pals_at(nloc, self_loc, 3)
            enemies = foes_at(nloc, friends + 2)
            if enemies <= friends:
                return True
            if enemies > friends + 1:
                return False
            near = 0
            for f in ants_list:
                if f == self_loc:
                    continue
                if ants.distance(nloc, f) <= GUARD_RANGE:
                    near += 1
                    if near >= EQUAL_TRADE_NEAR:
                        return True
            return False

        memo: dict[tuple[Loc, Loc], str | None] = {}
        expansions = [0]

        def first_step(start: Loc, goal: Loc) -> str | None:
            if start == goal:
                return None
            key = (start, goal)
            if key in memo:
                return memo[key]
            if not ants.passable(goal):
                memo[key] = None
                return None
            if expansions[0] >= TURN_EXPANSIONS:
                memo[key] = None
                return None
            parent: dict[Loc, tuple[Loc, str]] = {start: (start, "")}
            queue: deque[Loc] = deque([start])
            budget = PATH_BUDGET
            found = False
            while queue and budget > 0 and expansions[0] < TURN_EXPANSIONS:
                cur = queue.popleft()
                budget -= 1
                expansions[0] += 1
                for d in DIRS:
                    nxt = ants.destination(cur, d)
                    if nxt in parent or not ants.passable(nxt):
                        continue
                    parent[nxt] = (cur, d)
                    if nxt == goal:
                        found = True
                        queue.clear()
                        break
                    queue.append(nxt)
            if not found:
                memo[key] = None
                return None
            node = goal
            while parent[node][0] != start:
                node = parent[node][0]
            memo[key] = parent[node][1]
            return memo[key]

        def step_candidates(start: Loc, goal: Loc) -> list[str]:
            out: list[str] = []
            bs = first_step(start, goal)
            if bs is not None:
                out.append(bs)
            for d in ants.direction(start, goal):
                if d not in out:
                    out.append(d)
            return out

        destinations: set[Loc] = set()
        vacated: set[Loc] = set()

        def free_square(loc: Loc) -> bool:
            # Squares ants leave this turn are enterable: simultaneous
            # moves never collide there. Home hills stay reserved even
            # when walked off, so traffic never plugs a spawn square.
            return ants.unoccupied(loc) or loc in vacated

        def try_step(ant_loc: Loc, direction: str, safe: bool = True) -> bool:
            new_loc = ants.destination(ant_loc, direction)
            if new_loc in destinations or not ants.passable(new_loc):
                return False
            if not free_square(new_loc):
                return False
            if safe and not is_safe(new_loc, ant_loc):
                return False
            ants.issue_order((ant_loc, direction))
            destinations.add(new_loc)
            if ant_loc not in hill_set:
                vacated.add(ant_loc)
            return True

        def try_join(ant_loc: Loc, direction: str) -> bool:
            new_loc = ants.destination(ant_loc, direction)
            if new_loc in destinations or not ants.passable(new_loc):
                return False
            if not free_square(new_loc):
                return False
            foes = foes_at(new_loc, len(ants_list))
            if foes >= len(ants_list):
                # Saturated the cap: recount exactly, so 3 foes never
                # read as 2 and release a donating pair.
                foes = foes_at(new_loc, len(enemy_locs) + 1)
            if foes:
                backup = pals_at(new_loc, ant_loc, foes)
                if backup + 1 < foes:
                    return False
            ants.issue_order((ant_loc, direction))
            destinations.add(new_loc)
            if ant_loc not in hill_set:
                vacated.add(ant_loc)
            return True

        def contact_foe(dest: Loc) -> Loc | None:
            best = None
            best_d = attack_r2 + 1
            for foe in enemy_locs:
                d = sq_dist(dest, foe)
                if d <= attack_r2 and d < best_d:
                    best_d = d
                    best = foe
            return best

        def nearest_foe(ant_loc: Loc) -> Loc | None:
            best = None
            best_d = SEEK_RANGE + 1
            for foe in enemy_locs:
                d = ants.distance(ant_loc, foe)
                if d <= SEEK_RANGE and d < best_d:
                    best_d = d
                    best = foe
            return best

        def intercept(hill: Loc) -> Loc | None:
            if not enemy_locs or rows <= 0 or cols <= 0:
                return None
            foe = min(enemy_locs, key=lambda e: ants.distance(hill, e))
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
            if ants.passable(mid):
                return mid
            seen = {mid}
            queue: deque[Loc] = deque([mid])
            budget = 500
            while queue and budget > 0:
                budget -= 1
                cur = queue.popleft()
                for s in ((-1, 0), (0, 1), (1, 0), (0, -1)):
                    nxt = ((cur[0] + s[0]) % rows, (cur[1] + s[1]) % cols)
                    if nxt in seen:
                        continue
                    seen.add(nxt)
                    if ants.passable(nxt):
                        return nxt
                    queue.append(nxt)
            return None

        # Join pre-pass: claim-free ants whose planned step would fight
        # share their foe; foes drawing 2+ commitments release the pair.
        commitments: dict[int, Loc] = {}
        if enemy_locs:
            for cai, cant in enumerate(ants_list):
                if target.get(cai) is not None:
                    continue
                chase = nearest_foe(cant)
                if chase is None:
                    continue
                cstep = first_step(cant, chase)
                if cstep is None:
                    continue
                cfoe = contact_foe(ants.destination(cant, cstep))
                if cfoe is not None:
                    commitments[cai] = cfoe
        counts: dict[Loc, int] = {}
        for cfoe2 in commitments.values():
            counts[cfoe2] = counts.get(cfoe2, 0) + 1
        joined = {ai for ai, cfoe2 in commitments.items() if counts[cfoe2] >= 2}

        held: list[Loc] = []
        anchored: set[Loc] = set()
        hill_set = set(my_hills)
        for ai, ant_loc in enumerate(ants_list):
            self.visits[ant_loc] = self.visits.get(ant_loc, 0) + 1
            moved = False
            best = target.get(ai)
            if best is not None:
                for d in step_candidates(ant_loc, best):
                    if try_step(ant_loc, d):
                        moved = True
                        break
                if (
                    not moved
                    and ants.distance(ant_loc, best) <= 2
                    # Stand-off sitter: already on the meal; holding
                    # gathers by proximity, exploring would gift it.
                    # Never squat a home hill: it must stay spawnable.
                    # And never sit on a meal with no path to it.
                    and ant_loc not in hill_set
                    and first_step(ant_loc, best) is not None
                    and is_safe(ant_loc, ant_loc)
                ):
                    moved = True
            if not moved and threatened:
                nearest = min(threatened, key=lambda h: ants.distance(ant_loc, h))
                if nearest in anchored:
                    goal: Loc | None = intercept(nearest)
                    if goal is None and enemy_locs:
                        goal = min(enemy_locs, key=lambda e: ants.distance(nearest, e))
                    cands = step_candidates(ant_loc, goal) if goal is not None else []
                else:
                    anchored.add(nearest)
                    cands = step_candidates(ant_loc, nearest)
                for d in cands:
                    if try_step(ant_loc, d):
                        moved = True
                        break
            if not moved and enemy_locs:
                foe: Loc | None = nearest_foe(ant_loc)
                if foe is not None:
                    if len(enemy_locs) < CROWD_LIMIT and has_pack(
                        ant_loc, ants_list, ants.distance
                    ):
                        # Fearless: a packed hunter presses a small fight,
                        # skipping the safety filter on the advancing step.
                        for d in step_candidates(ant_loc, foe):
                            if try_step(ant_loc, d, safe=False):
                                moved = True
                                break
                    elif ai in joined:
                        order = sorted(
                            DIRS,
                            key=lambda d: ants.distance(
                                ants.destination(ant_loc, d), foe
                            ),
                        )
                        for d in order:
                            if contact_foe(ants.destination(ant_loc, d)) is None:
                                continue
                            if try_join(ant_loc, d):
                                moved = True
                                break
                    else:
                        for d in step_candidates(ant_loc, foe):
                            nloc = ants.destination(ant_loc, d)
                            foes = foes_at(nloc, 2)
                            pals = pals_at(nloc, ant_loc, 1)
                            if (
                                pals == 0
                                and foes == 1
                                and len(ants_list) > len(enemy_locs)
                            ):
                                if try_join(ant_loc, d):
                                    moved = True
                                    break
                            elif try_step(ant_loc, d):
                                moved = True
                                break
                        if not moved and contact_foe(ant_loc) is not None:
                            moved = True  # hold contact; the battle is automatic
            company_goal = None
            voter = any(ant_loc in voters for voters in companies.values())
            if not moved and companies:
                mine = [h for h, voters in companies.items() if ant_loc in voters]
                if mine:
                    company_goal = min(mine, key=lambda h: ants.distance(ant_loc, h))
                    # Fearless while ahead on hills; full safety otherwise.
                    bold = len(my_hills) > len(hills)
                    for d in step_candidates(ant_loc, company_goal):
                        if try_step(ant_loc, d, safe=not bold):
                            moved = True
                            break
                    if not moved and ants.distance(ant_loc, company_goal) <= 4:
                        # Blocked at the gates: hold the siege instead of
                        # wandering off to explore.
                        moved = True
            if not moved and best is None and hills and not voter:
                # Lone arrival: a claim-free non-voter already inside
                # the committed zone still steps in when the square is
                # free (an empty hill razes for nothing); blocked
                # arrivals hold their one-ant siege instead of
                # wandering off. Outside the zone solos farm.
                near_hill = min(hills, key=lambda h: ants.distance(ant_loc, h))
                if ants.distance(ant_loc, near_hill) <= 4:
                    for d in step_candidates(ant_loc, near_hill):
                        if try_step(ant_loc, d):
                            moved = True
                            break
                if (
                    not moved
                    and ants.distance(ant_loc, near_hill) <= 2
                    and is_safe(ant_loc, ant_loc)
                ):
                    moved = True
            if not moved and contact_foe(ant_loc) is not None:
                moved = True  # hold contact; the battle is automatic
            if not moved:
                rot = (ai + self.turn) % len(DIRS)
                order = [DIRS[(rot + k) % len(DIRS)] for k in range(len(DIRS))]
                cands = sorted(
                    order,
                    key=lambda d: self.visits.get(ants.destination(ant_loc, d), 0),
                )
                for d in cands:
                    if try_step(ant_loc, d):
                        moved = True
                        break
            if not moved:
                held.append(ant_loc)
            if ants.time_remaining() < 10:
                break
        for ant_loc in held:
            if ant_loc in hill_set and ants.time_remaining() >= 10:
                for direction in ("s", "e", "w", "n"):
                    if try_step(ant_loc, direction):
                        break


if __name__ == "__main__":
    try:
        import psyco

        psyco.full()
    except ImportError:
        pass
    try:
        Ants.run(Tercio())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
