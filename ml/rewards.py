"""Rewards for AlphaAnt: game replay + bot decisions -> returns.

The engine replay already records everything the reward needs: food
pickups carry their gatherer and turn, every ant carries its full order
string, hills carry their raze turn. This module turns those facts into
per-decision credit.

Every event is discounted: a decision at turn t credited for an event
at turn T >= t receives amount * GAMMA**(T-t). Same-turn credit is the
special case GAMMA**0 = 1. Dense events walk back along the credited
ant's own path (records joined to replay trajectories by consecutive
pre/post-move tiles); team events walk back to every earlier decision.
Magnitudes are starting points, not tuned values.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

from grid import dist2, step

FOOD = 0.1
KILL = 0.1
DEATH = -0.2  # asymmetric: dying costs double killing pays, so 1-for-1
# trades net -0.1. Mutual annihilation is no longer free; combat must
# preserve material to profit. Exploiters keep their own scales.
HILL_APPROACH = 0.25  # same-turn pay per tile closed toward the enemy
# hill. Shortens the discount horizon: a +10 raze 100 turns out is
# worth ~+0.5 after GAMMA walk-back — real value, but 100 turns late
# and smeared, so hills need paying now, not at arrival.
# Unsplit (armies closing together are good) and unconditioned
# (suicide-watch instead of superiority gates).
# Ledger note (round 46): HA mass ran ~58/game vs outcome +-5 — the
# main's ledger was march-dominated, marching paid even when it
# killed you (Goodhart). The base price falls here; the RIVAL keeps
# 0.5 via override (winner's price untouched — Chesterton). Second
# anomaly, deliberately UNtouched: the exploiter DEATH override is
# +3.0 absolute, i.e. the rival is PAID to die (+6 per mutual kill).
# Comment above says "penalize" and round-19's 1-for-1 logic wants
# -6; "KILL/DEATH 3.0" reads as tripled stakes. But the subsidy
# produces winning aggression, not suicide — fixing the sign risks
# the only working line for an attribution nobody needs. Revisit
# only if the rival's board play ever looks suicidal (it doesn't).
HILL_RAZE = 10.0
HILL_LOST = -10.0
WIN = 5.0
LOSS = -5.0
DRAW = 0.0
GAMMA = 0.97

# Payment follows purpose: dense credit is gated on winning. On a win
# everything pays; on draw/loss the march subsidy (hill_approach)
# pays nothing and kills pay nothing (useless aggression unpaid).
# Dying always hurts and the terminal outcome always lands: defeats
# must sting, wins must sing.
GATED = {"hill_approach", "kill"}


def scales() -> dict:
    """The one event scale table: base game rewards."""
    return {
        "FOOD": FOOD,
        "KILL": KILL,
        "DEATH": DEATH,
        "HILL_RAZE": HILL_RAZE,
        "HILL_LOST": HILL_LOST,
        "WIN": WIN,
        "LOSS": LOSS,
        "HILL_APPROACH": HILL_APPROACH,
    }


def trajectories(replaydata):
    """Replay every ant: {(owner, idx): [(turn, loc), ...]}.

    orders[i] is the move executed on turn spawn+1+i ("-" = stay);
    the trajectory starts at the spawn turn on the initial tile.
    """
    rows = replaydata["map"]["rows"]
    cols = replaydata["map"]["cols"]
    out = {}
    for idx, (r, c, spawn, _end, owner, orders) in enumerate(replaydata["ants"]):
        loc = (r, c)
        traj = [(spawn, loc)]
        for i, order in enumerate(orders):
            loc = step(loc, order, rows, cols)
            traj.append((spawn + 1 + i, loc))
        out[(owner, idx)] = traj
    return out


def _was_killed(entry):
    """A killed ant's orders run through its death turn; a survivor's
    end marker is one past its last order."""
    _r, _c, spawn, end, _owner, orders = entry
    return end - spawn == len(orders)


def outcome(game, me, table=None):
    """Terminal signal from engine scores, linear over placements.

    Dense-rank seats by score (ties share a rank), then interpolate
    table WIN..LOSS across the distinct levels: sole-first always +5,
    sole-last always -5, middles graduated (1,2,3,4 ->
    +5,+1.67,-1.67,-5; 1,2,2,3 -> +5,0,0,-5; shared top shares full
    win credit). All-tied is DRAW 0. 2p (and sole-first/sole-last at
    any size) is byte-identical to winner-takes-all."""
    top = table["WIN"] if table is not None else WIN
    bottom = table["LOSS"] if table is not None else LOSS
    scores = list(game["score"])
    mine = scores[me]
    levels = len(set(scores))
    if levels == 1:
        return DRAW
    better = sum(1 for s in set(scores) if s > mine)
    return top - (top - bottom) * better / (levels - 1)


def record_identities(replaydata, records):
    """Join each decision record to its replay ant: [(owner, idx) | None].

        A record (turn t, loc -> dest) belongs to the ant whose trajectory
    holds (t-1, loc) followed by (t, dest). Unmatched records (missing or
    ambiguous replay paths) get None and receive same-turn credit only.
    """
    trajs = trajectories(replaydata)
    prev_of = {}
    for key, traj in trajs.items():
        for i in range(1, len(traj)):
            prev_of[(traj[i][0], traj[i - 1][1], traj[i][1])] = key
    out = []
    for rec in records:
        cands = prev_of.get((rec["turn"], tuple(rec["loc"]), tuple(rec["dest"])))
        out.append(cands)
    # disambiguate tile swaps: the (prev, curr) pair is unique per ant per
    # turn under legal movement, so at most one ant matches.
    return out


def dests_at(turns, dests, turn, pred=None):
    """Record indices at `turn` whose dest satisfies pred (default: any)."""
    return [
        i
        for i, (t, d) in enumerate(zip(turns, dests))
        if t == turn and (pred is None or pred(d))
    ]


def _awards(game, me, records, scales):
    """Credit events: (awards, end_value, length, turns, keys).

    awards: [(turn, {idx: same-turn share}, scope, kind)]. Food/kill/death
    shares in one award sum to the event amount (splits conserve value);
    hill shares are per-ant distance pay, unconserved."""
    replaydata = game["replaydata"]
    length = game.get("length", game.get("game_length"))
    rows = replaydata["map"]["rows"]
    cols = replaydata["map"]["cols"]
    attack2 = replaydata.get("attackradius2", 5)

    dests = [tuple(rec["dest"]) for rec in records]
    turns = [rec["turn"] for rec in records]
    keys = record_identities(replaydata, records)
    awards = []

    def same_turn_dest(turn, loc):
        return dests_at(turns, dests, turn, lambda d: d == loc)

    # food gathered by me: credit my ants that ended the turn ADJACENT to
    # the tile. Gathering runs on nearby_ants, which excludes distance 0:
    # the ant standing ON the food does not gather it. 0 < d2 <= spawnradius2.
    spawn2 = replaydata.get("spawnradius2", 1)
    for entry in replaydata.get("food", []):
        if len(entry) < 5 or entry[4] != me:
            continue
        r, c, _start, end, _owner = entry
        near = dests_at(
            turns,
            dests,
            end,
            lambda d: 0 < dist2(d, (r, c), rows, cols) <= spawn2,
        )
        if near:
            awards.append(
                (end, {i: scales["FOOD"] / len(near) for i in near}, "ant", "food")
            )

    # own deaths: penalize the ant that died on its death tile
    for entry in replaydata.get("ants", []):
        r, c, spawn, end, owner, orders = entry
        if owner != me or not _was_killed(entry):
            continue
        loc = (r, c)
        for order in orders:
            loc = step(loc, order, rows, cols)
        hit = same_turn_dest(end, loc)
        if hit:
            awards.append(
                (end, {i: scales["DEATH"] / len(hit) for i in hit}, "ant", "death")
            )

    # kills: split credit among my ants within attack radius of the death.
    # Combat runs on nearby_ants, which excludes distance 0: a co-located
    # ant is a collision, not a killer. 0 < d2 <= attackradius2.
    for entry in replaydata.get("ants", []):
        r, c, spawn, end, owner, orders = entry
        if owner == me or not _was_killed(entry):
            continue
        loc = (r, c)
        for order in orders:
            loc = step(loc, order, rows, cols)
        near = dests_at(
            turns,
            dests,
            end,
            lambda d: 0 < dist2(d, loc, rows, cols) <= attack2,
        )
        if near:
            awards.append(
                (end, {i: scales["KILL"] / len(near) for i in near}, "ant", "kill")
            )

    # hills: razed iff end_turn <= game length. Each ant earns its own
    # distance-scaled share: amount * exp(-d2*ln10/100) on toroidal
    # squared distance — calibrated so 10 tiles out pays exactly a
    # tenth (full on the tile, ~0.56 at 5, ~0.006 at 15, ~0.0001 at
    # 20). No normalization: credit depends on distance only, never on
    # headcount. Scope is per-ant: each share walks back along
    # its own path. Unlike food/kill/death splits, hill shares do NOT
    # conserve a total — each ant is paid for where IT stood.
    for entry in replaydata.get("hills", []):
        r, c, owner, end = entry
        if end > length:
            continue
        amount = scales["HILL_RAZE"] if owner != me else scales["HILL_LOST"]
        mine = dests_at(turns, dests, end)
        if mine:
            awards.append(
                (
                    end,
                    {
                        i: amount * math.exp(-dist2(dests[i], (r, c), rows, cols) * math.log(10) / 100.0)
                        for i in mine
                    },
                    "ant",
                    "hill",
                )
            )

    # hill approach: same-turn pay for closing distance to the nearest
    # enemy hill (toroidal tiles). Marching toward hills must pay NOW:
    # the discounted raze cannot compete with immediate death costs.
    # Opening distance or standing still pays nothing; reaching the
    # hill tile itself is the raze's credit, not approach's (skipped:
    # d_after == 0 would double-pay the arrival).
    foes = [(r, c) for r, c, owner, _end in replaydata.get("hills", []) if owner != me]
    # First enemy hill only: a shared convention concentrating force.
    # Min-nearest splits attackers (each ant closes its own nearest =
    # solo races); one common target masses them for breakthroughs.
    if foes:
        hill = foes[0]
        for i, rec in enumerate(records):
            loc, dest = tuple(rec["loc"]), tuple(rec["dest"])
            before = math.sqrt(dist2(loc, hill, rows, cols))
            after = math.sqrt(dist2(dest, hill, rows, cols))
            closed = before - after
            if closed > 0 and after > 0:
                awards.append(
                    (
                        rec["turn"],
                        {i: scales["HILL_APPROACH"] * closed},
                        "ant",
                        "hill_approach",
                    )
                )

    return awards, outcome(game, me, scales), length, turns, keys


def trace_report(game, seat, records):
    """Join audit: (miss_rate, problems).

    miss_rate counts records no replay ant explains. problems lists the
    ones that should be impossible: dest on water or live food (the
    legal mask forbids both — a mask breach) or no stayed step at all
    (ghost). Passable-stay misses are order-lost infra noise: counted,
    never raised. Missing map data raises: the engine always logs it."""
    if not records:
        return (0.0, [])  # nothing to audit: vacuous, not silent
    rd = game["replaydata"]
    trajs = trajectories(rd)
    keys = record_identities(rd, records)
    if all(k is not None for k in keys):
        return (0.0, [])  # nothing to classify: grid needed only for misses
    grid = (rd.get("map") or {}).get("data")
    if not grid:
        raise ValueError("trace_report needs replaydata.map.data")
    stayed = {
        (t, a, b)
        for (o, _i), tr in trajs.items()
        if o == seat
        for k in range(1, len(tr))
        for (t, a, b) in [(tr[k][0], tr[k - 1][1], tr[k][1])]
        if a == b
    }
    foods = [f for f in rd.get("food", []) if len(f) >= 4]
    missed = 0
    problems = []
    for rec, key in zip(records, keys):
        if key is not None:
            continue
        missed += 1
        t, loc, dest = rec["turn"], tuple(rec["loc"]), tuple(rec["dest"])
        if (t, loc, loc) not in stayed:
            problems.append(f"t{t} {loc}->{dest}: no ant stayed there (ghost)")
            continue
        r, c = dest
        on_water = (
            0 <= r < len(grid)
            and 0 <= c < len(grid[r])
            and grid[r][c] == "%"
        )
        on_food = any(
            f[0] == r and f[1] == c and f[2] <= t <= f[3] for f in foods
        )
        if on_water or on_food:
            problems.append(
                f"t{t} {loc}->{dest}: order into "
                f"{'water' if on_water else 'food'} (mask breach)"
            )
    total = len(records)
    return (missed / total if total else 0.0, problems)


def compute_returns(game, me, records, table=None):
    """Discounted return for each decision record.

    records: [{turn, loc, dest, action, ...}] logged by the bot for its
    own ants. Returns a parallel list of floats. table selects the
    event table (base game rewards by default). The game record itself
    is untouched — returns only."""
    table = table if table is not None else scales()
    awards, end_value, length, turns, keys = _awards(game, me, records, table)
    by_kind: dict[str, list[float]] = {}

    # settle: same-turn credit plus GAMMA-discounted walk-back. "ant"
    # awards travel back along the credited ant's own path; "team"
    # awards reach every earlier decision.
    for event_turn, shares, scope, kind in awards:
        arr = by_kind.setdefault(kind, [0.0] * len(records))
        for i, share in shares.items():
            arr[i] += share
            if kind == "hill_approach":
                continue  # same-turn only: walk-back would smear the
            # contingency (marching past the hill still pays).
            for j, t in enumerate(turns):
                if j == i or t >= event_turn:
                    continue
                if scope == "team" or (keys[i] is not None and keys[j] == keys[i]):
                    arr[j] += share * (GAMMA ** (event_turn - t))

    # outcome gate: marching/killing that doesn't win pays nothing.
    # The subsidy for suicidal marching lives here; zeroing it on
    # draws and losses is what kills the Goodhart. Placement-positive
    # seats (sole-first, upper middles) unlock kill/march pay;
    # zero and negative seats don't.
    gated = GATED if end_value <= 0 else set()
    rets = [0.0] * len(records)
    for kind, arr in by_kind.items():
        if kind in gated:
            continue
        for i, v in enumerate(arr):
            rets[i] += v

    # terminal outcome broadcast to every decision, UNDISCOUNTED. A win
    # belongs to the opening move as much as the final one: discounting
    # by time says early moves mattered less, which is false — time
    # distance is not causal distance. DRAW stays 0: under the
    # batch-mean baseline a uniform draw batch is already
    # advantage-neutral, matching promotion's half-win treatment.
    if end_value:
        for i, _t in enumerate(turns):
            rets[i] += end_value

    return rets
