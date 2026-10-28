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

FOOD = 1.0
KILL = 1.0
DEATH = -2.0  # asymmetric: dying costs double killing pays, so 1-for-1
# trades net -1. Mutual annihilation is no longer free; combat must
# preserve material to profit. Exploiters keep their own scales.
HILL_APPROACH = 0.25  # same-turn pay per tile closed toward the enemy
# hill. Shortens the discount horizon: a +10 raze 100 turns out is
# worth ~+0.5 after GAMMA walk-back and cannot compete with an
# immediate -2 death, so hills need paying now, not at arrival.
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

ROLE_OVERRIDES = {
    # Exploiters train to kill, not to win efficiently: triple combat
    # credit, halve gathering, shared hills and outcome. Main line
    # untouched. Anything unknown gets base rewards.
    # HA override pins the RIVAL's march price at the old 0.5 while
    # the base (main) falls to 0.25 (round-46 ledger rebalance).
    "exploiter": {"FOOD": 0.5, "KILL": 3.0, "DEATH": 3.0,
                  "HILL_APPROACH": 0.5},
    # Spoiler (line-B rival): naive, hungry, persistent. No food or
    # march credit (nothing to unlearn about turtling), teeth kept,
    # dying hurts at the base rate. Hills and outcome as base.
    "spoiler": {"FOOD": 0, "KILL": 3.0, "DEATH": -2.0,
                "HILL_APPROACH": 0},
    # Challenger (round-92 revert): falsified experiment removed —
    # returns to base scales (KILL 1.0, HA 0.25, gated as before).
}


# Payment follows purpose: dense credit is gated on winning. On a win
# everything pays; on draw/loss the march subsidy (hill_approach)
# pays nothing and the main's kills pay nothing (useless aggression
# unpaid). The rival's kills always pay (pressure is its job -
# winning aggression, not suicide). Dying always hurts and the
# terminal outcome always lands: defeats must sting, wins must sing.
GATED_BY_ROLE = {
    "challenger": {"hill_approach", "kill"},
    "exploiter": {"hill_approach"},
    # Spoiler: gate the march (moot, zero scale) but NOT kills —
    # pressure is the job, same as the exploiter.
    "spoiler": {"hill_approach"},
}


def scales_for(role: str) -> dict:
    """Full event scale table for a training role."""
    base = {
        "FOOD": FOOD, "KILL": KILL, "DEATH": DEATH,
        "HILL_RAZE": HILL_RAZE, "HILL_LOST": HILL_LOST,
        "WIN": WIN, "LOSS": LOSS, "HILL_APPROACH": HILL_APPROACH,
    }
    base.update(ROLE_OVERRIDES.get(role, {}))
    return base

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


def _awards(game, me, records, scales):
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

    # food gathered by me: credit my ants that ended the turn ADJACENT to
    # the tile. Gathering runs on nearby_ants, which excludes distance 0:
    # the ant standing ON the food does not gather it. 0 < d2 <= spawnradius2.
    spawn2 = replaydata.get("spawnradius2", 1)
    for entry in replaydata.get("food", []):
        if len(entry) < 5 or entry[4] != me:
            continue
        r, c, _start, end, _owner = entry
        near = dests_at(
            turns, dests, end,
            lambda d: 0 < dist2(d, (r, c), rows, cols) <= spawn2,
        )
        if near:
            awards.append((end, {i: scales["FOOD"] / len(near) for i in near}, "ant", "food"))

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
            awards.append((end, {i: scales["DEATH"] / len(hit) for i in hit}, "ant", "death"))

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
            awards.append((end, {i: scales["KILL"] / len(near) for i in near}, "ant", "kill"))

    # hills: razed iff end_turn <= game length. A hill falls to the single
    # enemy ant standing ON it (do_raze_hills), so the raze credits the
    # ant on the tile; a lost hill is a team failure, split across the
    # team's ants that turn.
    for entry in replaydata.get("hills", []):
        r, c, owner, end = entry
        if end > length:
            continue
        amount = scales["HILL_RAZE"] if owner != me else scales["HILL_LOST"]
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

    # hill approach: same-turn pay for closing distance to the nearest
    # enemy hill (toroidal tiles). Marching toward hills must pay NOW:
    # the discounted raze cannot compete with immediate death costs.
    # Opening distance or standing still pays nothing; reaching the
    # hill tile itself is the raze's credit, not approach's (skipped:
    # d_after == 0 would double-pay the arrival).
    import math

    foes = [(r, c) for r, c, owner, _end in replaydata.get("hills", [])
            if owner != me]
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
                awards.append((rec["turn"],
                               {i: scales["HILL_APPROACH"] * closed},
                               "ant", "hill_approach"))

    return awards, outcome(game, me), length, turns, keys


def compute_returns(game, me, records, scales=None, role="challenger",
                    draw_as_loss=False):
    """Discounted return for each decision record.

    records: [{turn, loc, dest, action, ...}] logged by the bot for its
    own ants. Returns a parallel list of floats. scales selects the
    training role's event table (base game rewards by default); role
    selects the outcome gate (payment follows purpose). draw_as_loss
    prices DRAWN games as losses (anti-turtle incentive): the terminal
    becomes LOSS and the loser's gate applies. The game record itself
    is untouched — returns only."""
    scales = scales or scales_for("challenger")
    awards, end_value, length, turns, keys = _awards(game, me, records, scales)
    # Penalty games: a draw stops being the safe fixed point.
    eff = LOSS if (draw_as_loss and end_value == DRAW) else end_value
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
    # draws and losses is what kills the Goodhart.
    gated = GATED_BY_ROLE.get(role, {"hill_approach", "kill"}) \
        if eff <= 0 else set()
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
    if eff:
        terminal = scales["WIN"] if eff > 0 else scales["LOSS"]
        for i, _t in enumerate(turns):
            rets[i] += terminal

    return rets


def decompose(game, me, records, role="challenger"):
    """Undiscounted return mass by category, for tuning magnitudes.

    Dense shares conserve the event amount (one food totals FOOD),
    but the terminal outcome is broadcast to every record by
    compute_returns — so it is reported separately as a PER-RECORD
    value ("terminal"), never multiplied by the row count. Comparing
    "terminal" against the dense totals shows the true scale ratio.
    The outcome gate applies here too (role selects it): mass the
    learner never receives must not appear in the ledger."""
    awards, end_value, _length, _turns, _keys = _awards(
        game, me, records, scales_for("challenger"))
    mass: dict[str, float] = {
        "food": 0.0, "kill": 0.0, "death": 0.0, "hill": 0.0,
        "hill_approach": 0.0,
    }
    for _turn, shares, _scope, kind in awards:
        mass[kind] += sum(shares.values())
    if end_value <= 0:
        for kind in GATED_BY_ROLE.get(role, {"hill_approach", "kill"}):
            mass[kind] = 0.0
    mass["terminal"] = end_value
    mass["result"] = (
        "win" if end_value > 0 else ("loss" if end_value < 0 else "draw")
    )
    return mass
