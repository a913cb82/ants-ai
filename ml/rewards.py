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

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

from grid import dist2, step

KILL = 1.0
DEATH = -1.0
HILL_RAZE = 10.0
HILL_LOST = -10.0
WIN = 5.0
LOSS = -5.0
DRAW = 0.0
GAMMA = 0.97

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


def dests_at(turns, dests, turn, pred=None):
    """Record indices at `turn` whose dest satisfies pred (default: any)."""
    return [
        i
        for i, (t, d) in enumerate(zip(turns, dests))
        if t == turn and (pred is None or pred(d))
    ]


def _awards(game, me, records):
    """Credit events: (awards, end_value, length, turns, keys).

    awards: [(turn, {idx: same-turn share}, scope, kind)]. Shares in one
    award always sum to the event amount (splits conserve value)."""
    replaydata = game["replaydata"]
    length = game.get("length", game.get("game_length"))
    rows = replaydata["map"]["rows"]
    cols = replaydata["map"]["cols"]
    attack2 = replaydata.get("attackradius2", 5)

    dests = [tuple(rec["dest"]) for rec in records]
    locs = [tuple(rec["loc"]) for rec in records]
    turns = [rec["turn"] for rec in records]
    keys = record_identities(replaydata, records)
    awards = []

    def same_turn_dest(turn, loc):
        return dests_at(turns, dests, turn, lambda d: d == loc)

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
            awards.append((end, {i: DEATH / len(hit) for i in hit}, "ant", "death"))

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
            turns, dests, end,
            lambda d: 0 < dist2(d, loc, rows, cols) <= attack2,
        )
        if near:
            awards.append((end, {i: KILL / len(near) for i in near}, "ant", "kill"))

    # hills: razed iff end_turn <= game length. A hill falls to the single
    # enemy ant standing ON it (do_raze_hills), so the raze credits the
    # ant on the tile; a lost hill is a team failure, split across the
    # team's ants that turn.
    for entry in replaydata.get("hills", []):
        r, c, owner, end = entry
        if end > length:
            continue
        amount = HILL_RAZE if owner != me else HILL_LOST
        razers = dests_at(turns, dests, end, lambda d: d == (r, c))
        if razers:
            awards.append(
                (end, {i: amount / len(razers) for i in razers}, "ant", "hill")
            )
        else:
            mine = dests_at(turns, dests, end)
            if mine:
                awards.append(
                    (end, {i: amount / len(mine) for i in mine}, "team", "hill")
                )

    return awards, outcome(game, me), length, turns, keys


def compute_returns(game, me, records):
    """Discounted return for each decision record.

    records: [{turn, loc, dest, action, ...}] logged by the bot for its
    own ants. Returns a parallel list of floats.
    """
    awards, end_value, length, turns, keys = _awards(game, me, records)
    rets = [0.0] * len(records)

    # settle: same-turn credit plus GAMMA-discounted walk-back. "ant"
    # awards travel back along the credited ant's own path; "team"
    # awards reach every earlier decision.
    for event_turn, shares, scope, kind in awards:
        for i, share in shares.items():
            rets[i] += share
            for j, t in enumerate(turns):
                if j == i or t >= event_turn:
                    continue
                if scope == "team" or (keys[i] is not None and keys[j] == keys[i]):
                    rets[j] += share * (GAMMA ** (event_turn - t))

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


def decompose(game, me, records):
    """Undiscounted return mass by category, for tuning magnitudes.

    Dense shares conserve the event amount (one kill totals KILL),
    but the terminal outcome is broadcast to every record by
    compute_returns — so it is reported separately as a PER-RECORD
    value ("terminal"), never multiplied by the row count. Comparing
    "terminal" against the dense totals shows the true scale ratio.
    """
    awards, end_value, _length, _turns, _keys = _awards(game, me, records)
    mass: dict[str, float] = {
        "food": 0.0, "kill": 0.0, "death": 0.0, "hill": 0.0,
    }
    for _turn, shares, _scope, kind in awards:
        mass[kind] += sum(shares.values())
    mass["terminal"] = end_value
    mass["result"] = (
        "win" if end_value > 0 else ("loss" if end_value < 0 else "draw")
    )
    return mass
