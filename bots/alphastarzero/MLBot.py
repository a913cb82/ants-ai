#!/usr/bin/env python
"""AlphaStarZero: per-ant CNN policy bot (self-play student).

Inference runs the torch CNNPolicy from model.py over the 6-channel
local window, one ant at a time. Water and visible food are hard-masked
from the window (the engine ignores moves into both); the live
reservation set blocks already-claimed tiles so two ants never take the
same square. weights.json holds the champion parameters; the trainer
rewrites it only on promotion. `MLBot.py [weights]` points the bot at
another file for self-play games.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

from ants import Ants

import features
import model

WEIGHTS_PATH = Path(__file__).resolve().parent / "weights.json"

# When set, every decision is appended as one JSON row per ant per turn
# to $AZ0_RECORD_DIR/az0-<pid>.jsonl. Unset (rated play): zero overhead,
# zero behavior change. The log dir must live outside the bot tree so
# league pool hashing and the dirty-tree guard never see it.
RECORD_ENV = "AZ0_RECORD_DIR"

# When set to a float > 0, sample from the softmax instead of acting
# greedily. Self-play exploration only; rated play leaves it unset.
TEMPERATURE_ENV = "AZ0_TEMPERATURE"


class AlphaZeroBot:
    def __init__(self, weights_path: str | Path | None = None) -> None:
        self.policy = model.CNNPolicy()
        self.policy.load_state_dict(
            model.lists_to_state_dict(
                json.loads(Path(weights_path or WEIGHTS_PATH).read_text())
            )
        )
        self.policy.eval()
        temperature = os.environ.get(TEMPERATURE_ENV)
        self._temperature = float(temperature) if temperature else 0.0
        self._turn = 0
        record_dir = os.environ.get(RECORD_ENV)
        self._record_path = (
            Path(record_dir) / f"az0-{os.getpid()}.jsonl" if record_dir else None
        )

    def do_setup(self, ants: Ants) -> None:
        pass

    def do_turn(self, ants: Ants) -> None:
        self._turn += 1
        rows = []
        mine = ants.my_ants()
        # Every own tile starts reserved: ordering onto a staying nestmate
        # kills both ants (tools/ants.py do_orders). The acting ant's own
        # tile is exempted per action below.
        reserved = set(mine)
        for ant_loc in mine:
            rows.append(self._decide(ants, ant_loc, reserved))
            if rows[-1]["action"] != "stay":
                ants.issue_order((ant_loc, rows[-1]["action"]))
                reserved.add(tuple(rows[-1]["dest"]))
            if ants.time_remaining() < 10:
                break
        else:
            ant_loc = None  # all ants decided; loop did not break
        if ant_loc is not None:
            # Time ran out: log the undecided ants as stays so training
            # rows never starve late-order ants of credit.
            decided = len(rows)
            for rest in mine[decided:]:
                rows.append(self._row(ants, rest, "stay", frozenset()))
        if self._record_path is not None and rows:
            with open(self._record_path, "a") as f:
                for row in rows:
                    f.write(json.dumps(row) + "\n")

    def _decide(self, ants: Ants, ant_loc: tuple[int, int], reserved: set) -> dict:
        window = features.local_window(ants, ant_loc)
        blocked = frozenset(
            action
            for action in features.ACTIONS
            if (dest := features.dest_of(ants, ant_loc, action)) in reserved
            and dest != ant_loc
        )
        if self._temperature > 0:
            action = model.sample(self.policy, window, self._temperature, blocked)
        else:
            action = model.act_greedy(self.policy, window, blocked)
        return self._row(ants, ant_loc, action, blocked, window)

    def _row(self, ants, ant_loc, action, blocked, window=None) -> dict:
        window = features.local_window(ants, ant_loc) if window is None else window
        dest = features.dest_of(ants, ant_loc, action)
        return {
            "turn": self._turn,
            "loc": list(ant_loc),
            "dest": list(dest),
            "action": action,
            "window": window.tolist(),
            "legal": model.legal_mask(window, blocked).tolist(),
        }


if __name__ == "__main__":
    try:
        override = sys.argv[1] if len(sys.argv) > 1 else None
        Ants.run(AlphaZeroBot(weights_path=override))
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
