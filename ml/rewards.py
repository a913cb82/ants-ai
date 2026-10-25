"""Rewards for AlphaStarZero: game replay + bot decisions -> returns.

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

FOOD = 1.0
KILL = 1.0
DEATH = -1.0
HILL_RAZE = 10.0
HILL_LOST = -10.0
WIN = 25.0
LOSS = -25.0
DRAW = 0.0
GAMMA = 0.99

AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1), "-": (0, 0)}


def _step(loc, order, rows, cols):
    dr, dc = AIM.get(order, (0, 0))
    return ((loc[0] + dr) % rows, (loc[1] + dc) % cols)


def _dist2(a, b, rows, cols):
    dr = min(abs(a[0] - b[0]), rows - abs(a[0] - b[0]))
    dc = min(abs(a[1] - b[1]), cols - abs(a[1] - b[1]))
    return dr * dr + dc * dc


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
            loc = _step(loc, order, rows, cols)
            traj.append((spawn + 1 + i, loc))
        out[(owner, idx)] = traj
    return out


def _was_killed(entry):
    """A killed ant's orders run through its death turn; a survivor's
    end marker is one past its last order."""
    _r, _c, spawn, end, _owner, orders = entry
    return end - spawn == len(orders)


def outcome(game, me):
    """Terminal signal from the engine score: win, loss, or draw."""
    mine = game["score"][me]
    best_other = max(s for i, s in enumerate(game["score"]) if i != me)
    if mine > best_other:
        return WIN
    if mine < best_other:
        return LOSS
    return DRAW


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
        cands = prev_of.get((rec["turn"], tuple(rec["loc"]), tuple(rec["dest"])), None)
        out.append(cands)
    # disambiguate tile swaps: the (prev, curr) pair is unique per ant per
    # turn under legal movement, so at most one ant matches.
    return out


def compute_returns(game, me, records):
    """Discounted return for each decision record.

    records: [{turn, loc, dest, action, ...}] logged by the bot for its
    own ants. Returns a parallel list of floats.
    """
    replaydata = game["replaydata"]
    length = game.get("length", game.get("game_length"))
    rows = replaydata["map"]["rows"]
    cols = replaydata["map"]["cols"]
    attack2 = replaydata.get("attackradius2", 5)

    dests = [tuple(rec["dest"]) for rec in records]
    turns = [rec["turn"] for rec in records]
    keys = record_identities(replaydata, records)
    rets = [0.0] * len(records)
    awards = []  # (turn, {idx: share}, scope) with scope in ("ant", "team")

    def same_turn_dest(turn, loc):
        return [i for i, (t, d) in enumerate(zip(turns, dests)) if t == turn and d == loc]

    # food gathered by me: credit my ants that ended the turn ADJACENT to
    # the tile. Gathering runs on nearby_ants, which excludes distance 0:
    # the ant standing ON the food does not gather it. 0 < d2 <= spawnradius2.
    spawn2 = replaydata.get("spawnradius2", 1)
    for entry in replaydata.get("food", []):
        if len(entry) < 5 or entry[4] != me:
            continue
        r, c, _start, end, _owner = entry
        near = [
            i
            for i, (t, d) in enumerate(zip(turns, dests))
            if t == end and 0 < _dist2(d, (r, c), rows, cols) <= spawn2
        ]
        if near:
            awards.append((end, {i: FOOD / len(near) for i in near}, "ant"))

    # own deaths: penalize the ant that died on its death tile
    for entry in replaydata.get("ants", []):
        r, c, spawn, end, owner, orders = entry
        if owner != me or not _was_killed(entry):
            continue
        loc = (r, c)
        for order in orders:
            loc = _step(loc, order, rows, cols)
        hit = same_turn_dest(end, loc)
        if hit:
            awards.append((end, {i: DEATH / len(hit) for i in hit}, "ant"))

    # kills: split credit among my ants within attack radius of the death
    for entry in replaydata.get("ants", []):
        r, c, spawn, end, owner, orders = entry
        if owner == me or not _was_killed(entry):
            continue
        loc = (r, c)
        for order in orders:
            loc = _step(loc, order, rows, cols)
        near = [
            i
            for i, (t, d) in enumerate(zip(turns, dests))
            if t == end and _dist2(d, loc, rows, cols) <= attack2
        ]
        if near:
            awards.append((end, {i: KILL / len(near) for i in near}, "ant"))

    # hills: razed iff end_turn <= game length. A hill falls to the single
    # enemy ant standing ON it (do_raze_hills), so the raze credits the
    # ant on the tile; a lost hill is a team failure, split across the
    # team's ants that turn.
    for entry in replaydata.get("hills", []):
        r, c, owner, end = entry
        if end > length:
            continue
        amount = HILL_RAZE if owner != me else HILL_LOST
        razers = [
            i
            for i, (t, d) in enumerate(zip(turns, dests))
            if t == end and d == (r, c)
        ]
        if razers:
            awards.append((end, {i: amount / len(razers) for i in razers}, "ant"))
        else:
            mine = [i for i, t in enumerate(turns) if t == end]
            if mine:
                awards.append((end, {i: amount / len(mine) for i in mine}, "team"))

    # settle: same-turn credit plus GAMMA-discounted walk-back. "ant"
    # awards travel back along the credited ant's own path; "team"
    # awards reach every earlier decision.
    for event_turn, shares, scope in awards:
        for i, share in shares.items():
            rets[i] += share
            for j, t in enumerate(turns):
                if j == i or t >= event_turn:
                    continue
                if scope == "team" or (keys[i] is not None and keys[j] == keys[i]):
                    rets[j] += share * (GAMMA ** (event_turn - t))

    # terminal outcome discounted back to every decision
    end_value = outcome(game, me)
    if end_value:
        for i, t in enumerate(turns):
            rets[i] += end_value * (GAMMA ** (length - t))

    return rets
