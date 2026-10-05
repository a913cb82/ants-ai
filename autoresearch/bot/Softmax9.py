#!/usr/bin/env python
"""Softmax9 entry: champion economy with hill-gated small-fight press.

Economy (clustered denial food), threatened-hill guard with
off-hill screening, muster, reinforce, explore, and walk-off are
the champion Crowd logic byte-identical apart from the class name
and the removed combat import. Only the combat core is replaced.

Nhaehnle tactical combat (top 20, RESEARCH.md row "nhaehnle
tactical 1-ply max-min"):
- Carve combat submaps (connected components linked within
  COMBAT_LINK steps), no lookahead beyond this turn.
- 1-ply max-min over SAMPLED enemy move combos (seeded RNG,
  N_ENEMY_SAMPLES per fight), not exhaustive best-reply and not
  a1k0n-style provisional sampling. Each own joint move scores
  its worst case over the samples; the argmax issues.
- Overvalue own ants by default: OWN_ANT_WEIGHT = 1.5, so an
  equal 1-for-1 scores 1 - 1.5 = -0.5.
- Aggressive mode fires through a contest-zone gate over the
  exact logistic p = 1/(1+exp(-(a*ln(own/enemy)+b))), a = 2.0,
  b = 0.0: decisive odds gate deterministically (p >= 0.5, so
  2v1 presses and 1v2 refuses), while near-parity odds
  (|p - 0.5| <= CONTEST_HALF = 0.2: 1v1, 3v2, 2v3) flip the
  seeded per-fight coin with probability p. Parity explores
  like the impl coin flip; decisions exploit like the tune.
- Nhaehnle tried a1k0n sampling and found it worse than this
  tactical code; the min-over-samples rule below is the pinned
  distinction (robust max-min, never first-sample or average).
"""

import math
import random
from collections import deque
from collections.abc import Callable
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
# Logistic aggression gate in ln(own/enemy): p covers 1v1 at 0.5,
# 2v1 at 0.8, 1v2 at 0.2 with a=2, b=0.
LOGISTIC_A = 2.0
LOGISTIC_B = 0.0
# Sampled enemy joint moves evaluated per fight (seeded).
N_ENEMY_SAMPLES = 8
# Contest-zone half-width on the logistic p: fights with
# |p - 0.5| <= CONTEST_HALF flip the seeded per-fight coin,
# decisive fights gate deterministically. 1v1 (0.5), 3v2
# (~0.69), 2v3 (~0.31) explore; 2v1 (0.8), 1v2 (0.2) exploit.
CONTEST_HALF = 0.2
# Small-fight ceiling: carved fights with own+enemy at or below
# this many ants press deterministically at p >= 0.5 ONLY when
# the fight contests a hill prize (see HILL_PRIZE_R). Covers
# exactly 1v1 and 2v2 at parity (3v1/1v3 are decisive anyway);
# open-field small parity and all bigger fights keep the coin.
SMALL_FIGHT_MAX = 4
# Hill-prize radius: a carved fight contests a prize when any of
# its ants sits within this many steps (ants.distance) of a hill,
# own or remembered enemy. Open-field parity donations never paid;
# pressing fires only where a hill justifies the equal trade.
HILL_PRIZE_R = 5
# Submap carve radius: own/enemy ants linked within this many
# steps belong to one fight.
COMBAT_LINK = 6
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


def aggressive_probability(
    own: int,
    enemy: int,
    a: float = LOGISTIC_A,
    b: float = LOGISTIC_B,
) -> float:
    """Exact logistic gate in ln(own/enemy): 1/(1+exp(-(a*ln+b)))."""
    if enemy <= 0:
        return 1.0
    if own <= 0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-(a * math.log(own / enemy) + b)))


def is_aggressive(
    own: int,
    enemy: int,
    a: float = LOGISTIC_A,
    b: float = LOGISTIC_B,
) -> bool:
    """Deterministic aggression gate: aggressive iff logistic p >= 0.5.

    Same formula as the coin flip, no randomness: favored fights
    press and underdog fights refuse equal trades, so a losing
    fight can no longer fire aggression by luck of the draw.
    """
    return aggressive_probability(own, enemy, a, b) >= 0.5


def is_contested(
    own: int,
    enemy: int,
    half: float = CONTEST_HALF,
    a: float = LOGISTIC_A,
    b: float = LOGISTIC_B,
) -> bool:
    """True when the logistic odds are too close to call.

    Contested fights (|p - 0.5| <= half) explore via the seeded
    coin; decisive fights exploit via the deterministic gate.
    Pure: counts plus compare, no side effects.
    """
    p = aggressive_probability(own, enemy, a, b)
    return abs(p - 0.5) <= half


def is_small_fight(own: int, enemy: int, max_ants: int = SMALL_FIGHT_MAX) -> bool:
    """True when the carved fight is an atomic duel unit.

    Fight-local headcount only: own+enemy <= max_ants (1v1,
    2v2 at parity; decisive small odds are decided anyway).
    Pure: integer counts plus compare, no side effects, and
    deliberately no owner identity (cf. Softmax4's owner split)."""
    return own + enemy <= max_ants


def fight_near_prize(
    own_group: list[Loc],
    foe_group: list[Loc],
    hills: list[Loc],
    distance: DistFn,
    radius: int = HILL_PRIZE_R,
) -> bool:
    """True when any combatant sits within radius of a hill.

    Prize sensor for the gated press: fights contesting a hill
    (attack or defense) may press parity deterministically, while
    open-field meetings keep the exploring coin. Pure: distances
    plus compares, no side effects."""
    if not hills:
        return False
    for ant in own_group:
        for h in hills:
            if distance(ant, h) <= radius:
                return True
    for ant in foe_group:
        for h in hills:
            if distance(ant, h) <= radius:
                return True
    return False


def decide_aggression(
    own: int,
    enemy: int,
    rng: random.Random,
    half: float = CONTEST_HALF,
    a: float = LOGISTIC_A,
    b: float = LOGISTIC_B,
    near_prize: bool = False,
) -> bool:
    """Contest-zone gate: coin at parity, threshold at decision.

    Inside the zone the per-fight seeded coin flips with
    probability p (impl exploration, reproducible per turn and
    fight); outside, the deterministic p >= 0.5 gate rules
    (tune duel intent). Small fights (own+enemy <= SMALL_FIGHT_MAX)
    with favored-or-even odds (p >= 0.5: 1v1, 2v2) press
    deterministically with no rng draw ONLY when near_prize holds
    (the fight contests a hill); open-field small parity keeps the
    coin, so lone meetings never donate tempo by lock-step press.
    Consumes one rng draw iff the coin flips, so call after enemy
    sampling to keep sample streams identical.
    """
    p = aggressive_probability(own, enemy, a, b)
    if is_small_fight(own, enemy) and p >= 0.5 and near_prize:
        return True
    if abs(p - 0.5) <= half:
        return rng.random() < p
    return p >= 0.5


def roll_aggressive(
    own: int,
    enemy: int,
    rng: random.Random,
    a: float = LOGISTIC_A,
    b: float = LOGISTIC_B,
) -> bool:
    """Probabilistic aggression: one logistic coin flip per fight.

    Retained as the documented reference for the replaced policy;
    the entry itself gates deterministically via is_aggressive.
    """
    return rng.random() < aggressive_probability(own, enemy, a, b)


def toroidal_sq(a: Loc, b: Loc, rows: int, cols: int) -> int:
    """Squared toroidal distance, same wrap as Ants.distance."""
    dr = abs(a[0] - b[0])
    dr = min(dr, rows - dr) if rows else dr
    dc = abs(a[1] - b[1])
    dc = min(dc, cols - dc) if cols else dc
    return dr * dr + dc * dc


def resolve_exchange(
    own_after: list[Loc],
    enemy_after: list[Loc],
    attack_r2: int,
    rows: int,
    cols: int,
) -> tuple[int, int]:
    """Symmetric 1-turn resolution: an ant dies iff any foe is near.

    Each own ant dies iff some enemy lands within attackradius2 of
    it, and vice versa, so a lone pair kills both (focus 1v1).
    Pure: no board state, no side effects.
    """
    own_dead = 0
    for o in own_after:
        for e in enemy_after:
            if toroidal_sq(o, e, rows, cols) <= attack_r2:
                own_dead += 1
                break
    enemy_dead = 0
    for e in enemy_after:
        for o in own_after:
            if toroidal_sq(o, e, rows, cols) <= attack_r2:
                enemy_dead += 1
                break
    return own_dead, enemy_dead


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


def all_enemy_joints(
    enemy_locs: list[Loc], rows: int, cols: int, passable: PassFn, destination: DestFn
) -> list[list[Loc]]:
    """Exhaustive enemy joint moves (best-reply reference for tests)."""
    _ = destination
    options = [legal_dests(e, rows, cols, passable) for e in enemy_locs]
    if not options:
        return []
    return [list(joint) for joint in product(*options)]


def sample_enemy_joints(
    enemy_locs: list[Loc],
    rows: int,
    cols: int,
    passable: PassFn,
    destination: DestFn,
    rng: random.Random,
    k: int = N_ENEMY_SAMPLES,
) -> list[list[Loc]]:
    """K seeded enemy joint moves, uniform per ant over legal steps."""
    _ = destination
    options = [legal_dests(e, rows, cols, passable) for e in enemy_locs]
    joints: list[list[Loc]] = []
    for _ in range(k):
        joints.append([rng.choice(opts) for opts in options])
    return joints


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
        own_dead = 0
        for o in own_joint:
            ors = o[0]
            ocs = o[1]
            for e in sample:
                dr = ors - e[0]
                if dr < 0:
                    dr = -dr
                if rows:
                    dr = min(dr, rows - dr)
                dc = ocs - e[1]
                if dc < 0:
                    dc = -dc
                if cols:
                    dc = min(dc, cols - dc)
                if dr * dr + dc * dc <= attack_r2:
                    own_dead += 1
                    break
        enemy_dead = 0
        for e in sample:
            ers = e[0]
            ecs = e[1]
            for o in own_joint:
                dr = ers - o[0]
                if dr < 0:
                    dr = -dr
                if rows:
                    dr = min(dr, rows - dr)
                dc = ecs - o[1]
                if dc < 0:
                    dc = -dc
                if cols:
                    dc = min(dc, cols - dc)
                if dr * dr + dc * dc <= attack_r2:
                    enemy_dead += 1
                    break
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
) -> tuple[list[Loc], float]:
    """Argmax own joint over the min-over-samples score, 1-ply only.

    Exhaustive joint enumeration at 4 or fewer own ants (distinct
    destinations only); sequential greedy fixing above that, so
    crowded fights stay far under budget. Ties keep the first
    joint, so play is deterministic. No lookahead.
    """
    _ = destination
    _ = enemy_locs
    options = [legal_dests(o, rows, cols, passable) for o in own_locs]
    if not options:
        return [], 0.0
    if len(options) <= 4:
        best: list[Loc] | None = None
        best_score = -math.inf
        for joint in product(*options):
            candidate = list(joint)
            if len(set(candidate)) < len(candidate):
                continue
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


def carve_fights(
    own_locs: list[Loc],
    enemy_locs: list[Loc],
    distance: DistFn,
    link: int = COMBAT_LINK,
) -> list[tuple[list[Loc], list[Loc]]]:
    """Connected components over own+enemy ants linked within link.

    Two ants join one fight when their distance is link or less,
    transitively, so isolated duels solve alone and crowds solve
    together. Pure: no board state, no side effects.
    """
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

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if distance(loc_of(nodes[i]), loc_of(nodes[j])) <= link:
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
class Softmax9:
    def __init__(self):
        # define class level variables, will be remembered between turns
        self.visits: dict[tuple[int, int], int] = {}
        self.remembered_hills: set[tuple[int, int]] = set()
        self.prev_enemies: list[tuple[int, int]] = []
        self._turn = 0

    # do_setup is run once at the start of the game
    # after the bot has received the game settings
    # the ants class is created and setup by the Ants.run method
    def do_setup(self, ants: Ants):
        # initialize data structures after learning the game settings
        self.visits = {}
        self.remembered_hills = set()
        self.prev_enemies = []
        self._turn = 0

    # do turn is run once per turn
    # the ants class has the game state and is updated by the Ants.run method
    # it also has several helper methods to use
    def do_turn(self, ants: Ants):
        # Softmax: champion economy/muster/guard/explore with an
        # nhaehnle tactical combat core. Fights are carved into
        # submaps once per turn; each fight runs 1-ply max-min over
        # K seeded enemy samples with overvalued own ants, and a
        # logistic aggression gate decides whether equal
        # trades may issue. Food, guard, muster, reinforce,
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
        self._turn += 1
        # Tactical plan: one max-min per carved fight over seeded
        # enemy samples. Rejected (losing/equal-passive) fights map
        # to no plan so those ants fall through to muster/explore.
        fight_plan: dict[tuple[int, int], tuple[int, int]] = {}
        if enemy_locs:
            enemy_set = set(enemy_locs)

            def plan_passable(loc: tuple[int, int]) -> bool:
                return ants.passable(loc) and loc not in enemy_set

            fights = carve_fights(ants_list, enemy_locs, ants.distance)
            prize_hills = hills + my_hills
            for fi, (own_group, foe_group) in enumerate(fights):
                rng = random.Random(self._turn * 100003 + fi * 7919 + len(ants_list))
                samples = sample_enemy_joints(
                    foe_group, rows, cols, ants.passable, ants.destination, rng
                )
                joint, _ = choose_own_joint(
                    own_group,
                    foe_group,
                    attack_r2,
                    rows,
                    cols,
                    plan_passable,
                    ants.destination,
                    samples,
                )
                near_prize = fight_near_prize(
                    own_group, foe_group, prize_hills, ants.distance
                )
                aggressive = decide_aggression(
                    len(own_group), len(foe_group), rng, near_prize=near_prize
                )
                worst_dead = (0, 0)
                worst_score = math.inf
                for sample in samples:
                    cand_dead = resolve_exchange(joint, sample, attack_r2, rows, cols)
                    cand_score = exchange_score(*cand_dead)
                    if cand_score < worst_score:
                        worst_score = cand_score
                        worst_dead = cand_dead
                if not samples:
                    continue
                if should_accept(worst_dead[0], worst_dead[1], aggressive):
                    for start, goal in zip(own_group, joint, strict=True):
                        fight_plan[start] = goal

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
                # Softmax: no food or guard move; the fight plan
                # holds the max-min joint move for this ant. Holds
                # and rejected fights fall through to muster.
                dest = fight_plan.get(ant_loc)
                if dest is not None and dest != ant_loc:
                    for d in ("n", "e", "s", "w"):
                        if ants.destination(ant_loc, d) == dest:
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
        Ants.run(Softmax9())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
