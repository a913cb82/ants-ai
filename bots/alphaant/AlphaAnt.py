#!/usr/bin/env python
"""AlphaAnt: per-ant CNN policy bot (self-play student).

Inference runs the torch CNNPolicy from model.py over the 9-channel
local window, one ant at a time. Water and visible food are hard-masked
from the window (the engine ignores moves into both); the live
reservation set blocks already-claimed tiles so two ants never take the
same square. weights.json holds the champion parameters; the trainer
rewrites it only on promotion. `AlphaAnt.py [weights]` points the bot at
another file for self-play games.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

import torch
from ants import Ants

# One net this small gains nothing from intra-op thread pools, and the
# driver runs up to 8 workers x 2 bots concurrently: cap threads so
# parallel games stop oversubscribing the machine (game_if also sets
# OMP/MKL env for the subprocess). Training keeps default threads.
torch.set_num_threads(1)

import features
import model

# Stall-memory gain: ch9 = clip(streak / STALL_K, 0, 1), K=8 turns to
# saturate. One scalar, broadcast constant across the window.
STALL_K = features.STALL_K

WEIGHTS_PATH = Path(__file__).resolve().parent / "weights.json"


# When set, every decision is appended as one JSON row per ant per turn
# to $AA_RECORD_DIR/aa-<pid>.jsonl. Unset (rated play): zero overhead,
# zero behavior change. The log dir must live outside the bot tree so
# league pool hashing and the dirty-tree guard never see it.
def find_cycles(intents: dict[tuple, tuple]) -> list[set]:
    """Rotation cycles among intended moves (origin -> dest).

    A cycle is a group of origins whose destinations permute the group
    with no fixed points: every member's square is vacated
    simultaneously, so all members may execute. Chains ending on a
    free square and stays (dest == origin) are never cycles. Walks
    follow mine order, so output is deterministic.
    """
    cycles = []
    seen = set()
    for start in intents:
        if start in seen:
            continue
        path: list = []
        pos: dict = {}
        cur = start
        while (
            cur in intents
            and intents[cur] != cur
            and cur not in pos
            and cur not in seen
        ):
            pos[cur] = len(path)
            path.append(cur)
            cur = intents[cur]
        if cur in pos:
            group = set(path[pos[cur] :])
            if len(group) > 1:
                cycles.append(group)
        seen.update(path)
    return cycles


RECORD_ENV = "AA_RECORD_DIR"

# When set to a float > 0, sample from the softmax instead of acting
# greedily. Self-play exploration only; rated play leaves it unset.
TEMPERATURE_ENV = "AA_TEMPERATURE"


class AlphaAntBot:
    def __init__(self, weights_path: str | Path | None = None) -> None:
        raw = json.loads(Path(weights_path or WEIGHTS_PATH).read_text())
        self.policy = model.CNNPolicy(arch=model.infer_arch(raw))
        self.policy.load_state_dict(
            model.pad_in_channels(model.lists_to_state_dict(raw), self.policy),
            strict=False,  # pre-value-head champions lack the value keys
        )
        self.policy.eval()
        temperature = os.environ.get(TEMPERATURE_ENV)
        self._temperature = float(temperature) if temperature else 0.0
        self._turn = 0
        self._water = None  # impassable set, cached in do_setup
        # Stall memory: cell -> same-cell streak. The engine exposes no
        # ant ids, so position continuity is the identity proxy: an ant
        # observed on the same cell as last turn keeps (and grows) its
        # streak; a cell never seen starts at 0 (covers moves and
        # dead-id replacements alike). Updated at end of turn, keyed by
        # where each ant ends up, so intent-blocked moves carry their
        # hysteresis to the fallback cell while free moves reset to 0.
        self._stall: dict = {}
        record_dir = os.environ.get(RECORD_ENV)
        self._record_path = (
            Path(record_dir) / f"aa-{os.getpid()}.jsonl" if record_dir else None
        )

    def do_setup(self, ants: Ants) -> None:
        # Water never changes mid-game: cache the impassable set once so
        # per-turn encoding is pure set lookups, zero engine calls.
        self._water = {
            (r, c)
            for r in range(ants.rows)
            for c in range(ants.cols)
            if not ants.passable((r, c))
        }

    def _choose(self, logits_i, window_i, blocked):
        """Masked action pick for one ant; returns (action, legal)."""
        legal = model.legal_mask(window_i, blocked)
        masked = model.mask_logits(logits_i, window_i, blocked, legal=legal)
        if self._temperature > 0:
            probs = torch.softmax(masked / self._temperature, dim=0)
            action = features.ACTIONS[int(torch.multinomial(probs, 1))]
        else:
            action = features.ACTIONS[int(torch.argmax(masked))]
        return action, legal

    def _resolve(self, ants, mine, moves, logits, windows) -> None:
        """Swap/cycle resolution pass: runs BEFORE any issue_order.

        Cycle members (A->B, B->A swaps and longer rotations) all
        execute: each destination is vacated simultaneously. Any other
        mover into a square that stays occupied (a stayer's square, or
        an undecided ant's square past the timeout break) is revoked
        and re-decides with that square blocked; everyone else's
        claims stand (first-claimant-wins). Re-decisions update the
        move in place, so rows keep the executed action/dest while
        intent (pre-mask want) is untouched. Terminates: every
        revocation permanently blocks one more square for that ant.
        """
        n = len(mine)
        extra = [set() for _ in range(n)]
        for _ in range(5 * n + 10):
            intents = {
                tuple(mine[i]): tuple(moves[i]["dest"])
                for i in range(n)
                if moves[i] is not None
            }
            cyclic: set = set()
            for group in find_cycles(intents):
                cyclic.update(group)
            staying = {
                tuple(mine[j])
                for j in range(n)
                if moves[j] is None or tuple(moves[j]["dest"]) == tuple(mine[j])
            }
            revoked = False
            for i in range(n):
                if moves[i] is None:
                    continue
                origin = tuple(mine[i])
                dest = tuple(moves[i]["dest"])
                if dest == origin or origin in cyclic:
                    continue
                if dest in staying:
                    # Square never vacated: stayer (or timeout-holder)
                    # owns it. Revoke the mover, keep the holder.
                    extra[i].add(dest)
                    forbid = set(extra[i])
                    for j in range(n):
                        if j == i or moves[j] is None:
                            continue
                        forbid.add(tuple(moves[j]["dest"]))
                    forbid.update(staying)
                    blocked = frozenset(
                        action
                        for action in features.ACTIONS
                        if (d := features.dest_of(ants, mine[i], action)) in forbid
                        and tuple(d) != origin
                    )
                    action, legal = self._choose(logits[i], windows[i], blocked)
                    moves[i]["action"] = action
                    moves[i]["dest"] = tuple(features.dest_of(ants, mine[i], action))
                    moves[i]["blocked"] = blocked
                    moves[i]["legal"] = legal
                    revoked = True
            if not revoked:
                return

    def _update_stall(self, mine, moves) -> None:
        """Roll the stall memory forward one turn, keyed by end cells.

        Same-cell (dest == origin, held or blocked-stay): streak + 1 up
        to STALL_K saturation. Moved with intent reservation-blocked:
        hysteresis carries (streak + 1) to the fallback cell. Free move:
        reset to 0. Undecided (timeout, move None): keep the current
        streak without increment. New cells default to 0 via dict miss.
        """
        nxt: dict = {}
        for i, ant_loc in enumerate(mine):
            origin = tuple(ant_loc)
            if moves[i] is None:
                nxt.setdefault(origin, self._stall.get(origin, 0))
                continue
            dest = tuple(moves[i]["dest"])
            cur = self._stall.get(origin, 0)
            if dest == origin or moves[i]["intent"] in moves[i]["blocked"]:
                val = min(cur + 1, STALL_K)
            else:
                val = 0
            nxt[dest] = max(val, nxt.get(dest, 0))
        self._stall = nxt

    def do_turn(self, ants: Ants) -> None:
        self._turn += 1
        mine = ants.my_ants()
        if not mine:
            return
        # One board read, one forward for the whole turn. Reservation
        # stays sequential (ant i's blocked set needs ants 0..i-1's
        # destinations), but masking applies to precomputed logit rows.
        view = features.snapshot(ants, water=self._water)
        windows = [
            features.local_window(
                ants,
                loc,
                view=view,
                stall=min(self._stall.get(tuple(loc), 0) / STALL_K, 1.0),
            )
            for loc in mine
        ]
        with torch.no_grad():
            logits = self.policy(torch.stack(windows))
        recording = self._record_path is not None
        rows = []
        moves = []
        # Destinations, not origins: an ant's current square stays
        # claimable until it actually moves (stays claim their own
        # square, so holders still own them). Orders are deferred to
        # the resolution pass below.
        reserved: set = set()
        for i, ant_loc in enumerate(mine):
            blocked = frozenset(
                action
                for action in features.ACTIONS
                if (dest := features.dest_of(ants, ant_loc, action)) in reserved
                and dest != ant_loc
            )
            # Honest logging: the want (pre-mask argmax of the raw
            # logits) plus the reservation set that constrained it.
            # The taken action stays the fallback the bot actually
            # played; the learner decides what to reinforce from
            # intent + blocked instead of blaming terrain.
            intent = features.ACTIONS[int(torch.argmax(logits[i]))]
            action, legal = self._choose(logits[i], windows[i], blocked)
            if action != "stay":
                dest = features.dest_of(ants, ant_loc, action)
            else:
                dest = ant_loc
            reserved.add(tuple(dest))
            moves.append(
                {
                    "action": action,
                    "dest": tuple(dest),
                    "intent": intent,
                    "blocked": blocked,
                    "legal": legal,
                }
            )
            if recording:
                rows.append(
                    {
                        "turn": self._turn,
                        "loc": list(ant_loc),
                        "dest": list(dest),
                        "action": action,
                        "intent": intent,
                        "blocked": sorted(blocked),
                        "window": features.encode_window(windows[i]),
                        "legal": legal.tolist(),
                    }
                )
            if ants.time_remaining() < 10:
                # Time ran out: undecided ants leave no rows. Logging
                # them as stays forged supervision they never chose
                # and starved late-order ants of real credit.
                break
        moves.extend([None] * (len(mine) - len(moves)))
        self._resolve(ants, mine, moves, logits, windows)
        self._update_stall(mine, moves)
        for i, ant_loc in enumerate(mine):
            if moves[i] is None:
                continue
            if recording:
                rows[i]["action"] = moves[i]["action"]
                rows[i]["dest"] = list(moves[i]["dest"])
                rows[i]["blocked"] = sorted(moves[i]["blocked"])
                rows[i]["legal"] = moves[i]["legal"].tolist()
            if moves[i]["action"] != "stay":
                ants.issue_order((ant_loc, moves[i]["action"]))
        if recording and rows:
            with open(self._record_path, "a") as f:
                for row in rows:
                    f.write(json.dumps(row) + "\n")


if __name__ == "__main__":
    try:
        override = sys.argv[1] if len(sys.argv) > 1 else None
        Ants.run(AlphaAntBot(weights_path=override))
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
