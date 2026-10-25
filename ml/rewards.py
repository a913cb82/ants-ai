"""Rewards for AlphaStarZero: game replay + bot decisions -> returns.

The engine replay already records everything the reward needs: food
pickups carry their gatherer and turn, every ant carries its full order
string, hills carry their raze turn. This module turns those facts into
per-decision credit:

- dense, same-turn: food gathered, own death, kills by proximity,
  hill razed/lost (team-shared);
- terminal: win/loss/draw, discounted back to every decision.

Dense events credit only the turn they happen on (myopic shaping);
the outcome carries the long-term signal. Magnitudes are starting
points, not tuned values.
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
    rets = [0.0] * len(records)

    def same_turn_dest(turn, loc):
        return [i for i, (t, d) in enumerate(zip(turns, dests)) if t == turn and d == loc]

    # food gathered by me: credit the ants that stepped onto the tile
    # food gathered by me: credit my ants that ended the turn within
    # spawnradius of the tile (gathering is by proximity, not occupancy)
    spawn2 = replaydata.get("spawnradius2", 1)
    for entry in replaydata.get("food", []):
        if len(entry) < 5 or entry[4] != me:
            continue
        r, c, _start, end, _owner = entry
        near = [
            i
            for i, (t, d) in enumerate(zip(turns, dests))
            if t == end and _dist2(d, (r, c), rows, cols) <= spawn2
        ]
        for i in near:
            rets[i] += FOOD / len(near)

    # own deaths: penalize the ant that died on its death tile
    for entry in replaydata.get("ants", []):
        r, c, spawn, end, owner, orders = entry
        if owner != me or not _was_killed(entry):
            continue
        loc = (r, c)
        for order in orders:
            loc = _step(loc, order, rows, cols)
        for i in same_turn_dest(end, loc):
            rets[i] += DEATH / max(1, len(same_turn_dest(end, loc)))

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
        for i in near:
            rets[i] += KILL / len(near)

    # hills: razed iff end_turn <= game length; team-shared that turn
    for entry in replaydata.get("hills", []):
        r, c, owner, end = entry
        if end > length:
            continue
        mine = [i for i, t in enumerate(turns) if t == end]
        if not mine:
            continue
        share = (HILL_RAZE if owner != me else HILL_LOST) / len(mine)
        for i in mine:
            rets[i] += share

    # terminal outcome discounted back to every decision
    end_value = outcome(game, me)
    if end_value:
        for i, t in enumerate(turns):
            rets[i] += end_value * (GAMMA ** (length - t))

    return rets
