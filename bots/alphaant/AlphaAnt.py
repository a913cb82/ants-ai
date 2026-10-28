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

WEIGHTS_PATH = Path(__file__).resolve().parent / "weights.json"

# When set, every decision is appended as one JSON row per ant per turn
# to $AA_RECORD_DIR/aa-<pid>.jsonl. Unset (rated play): zero overhead,
# zero behavior change. The log dir must live outside the bot tree so
# league pool hashing and the dirty-tree guard never see it.
RECORD_ENV = "AA_RECORD_DIR"

# When set to a float > 0, sample from the softmax instead of acting
# greedily. Self-play exploration only; rated play leaves it unset.
TEMPERATURE_ENV = "AA_TEMPERATURE"


class AlphaAntBot:
    def __init__(self, weights_path: str | Path | None = None) -> None:
        raw = json.loads(Path(weights_path or WEIGHTS_PATH).read_text())
        self.policy = model.CNNPolicy(arch=model.infer_arch(raw))
        self.policy.load_state_dict(
            model.pad_in_channels(model.lists_to_state_dict(raw),
                                  self.policy),
            strict=False,  # pre-value-head champions lack the value keys
        )
        self.policy.eval()
        temperature = os.environ.get(TEMPERATURE_ENV)
        self._temperature = float(temperature) if temperature else 0.0
        self._turn = 0
        self._water = None  # impassable set, cached in do_setup
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

    def do_turn(self, ants: Ants) -> None:
        self._turn += 1
        mine = ants.my_ants()
        if not mine:
            return
        # One board read, one forward for the whole turn. Reservation
        # stays sequential (ant i's blocked set needs ants 0..i-1's
        # destinations), but masking applies to precomputed logit rows.
        view = features.snapshot(ants, water=self._water)
        windows = [features.local_window(ants, loc, view=view) for loc in mine]
        with torch.no_grad():
            logits = self.policy(torch.stack(windows))
        recording = self._record_path is not None
        rows = []
        reserved = set(mine)
        for i, ant_loc in enumerate(mine):
            blocked = frozenset(
                action
                for action in features.ACTIONS
                if (dest := features.dest_of(ants, ant_loc, action)) in reserved
                and dest != ant_loc
            )
            legal = model.legal_mask(windows[i], blocked)
            masked = model.mask_logits(
                logits[i], windows[i], blocked, legal=legal
            )
            # Honest logging: the want (pre-mask argmax of the raw
            # logits) plus the reservation set that constrained it.
            # The taken action stays the fallback the bot actually
            # played; the learner decides what to reinforce from
            # intent + blocked instead of blaming terrain.
            intent = features.ACTIONS[int(torch.argmax(logits[i]))]
            if self._temperature > 0:
                probs = torch.softmax(masked / self._temperature, dim=0)
                action = features.ACTIONS[int(torch.multinomial(probs, 1))]
            else:
                action = features.ACTIONS[int(torch.argmax(masked))]
            if action != "stay":
                dest = features.dest_of(ants, ant_loc, action)
                ants.issue_order((ant_loc, action))
                reserved.add(tuple(dest))
            else:
                dest = ant_loc
            if recording:
                rows.append({
                    "turn": self._turn,
                    "loc": list(ant_loc),
                    "dest": list(dest),
                    "action": action,
                    "intent": intent,
                    "blocked": sorted(blocked),
                    "window": windows[i].tolist(),
                    "legal": legal.tolist(),
                })
            if ants.time_remaining() < 10:
                # Time ran out: undecided ants leave no rows. Logging
                # them as stays forged supervision they never chose
                # and starved late-order ants of real credit.
                break
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
