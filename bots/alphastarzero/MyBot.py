#!/usr/bin/env python
"""AlphaStarZero v0: per-ant linear policy bot (self-play student).

Inference runs the torch LinearPolicy from model.py greedily, one ant
at a time, with a live reservation set so two ants never take the same
tile. weights.json holds the current student parameters; the trainer in
ml/ rewrites that file after each self-play generation.
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


class AlphaZeroBot:
    def __init__(self) -> None:
        self.weights = json.loads(WEIGHTS_PATH.read_text())
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
        reserved: set[tuple[int, int]] = set()
        for ant_loc in ants.my_ants():
            feats = features.ant_features(ants, ant_loc, occupied=reserved)
            action = model.choose(feats, self.weights, occupied=reserved)
            dest = features.dest_of(ants, ant_loc, action)
            if action != "stay" and (dest in reserved or not ants.passable(dest)):
                action = self._fallback(feats, ants, ant_loc, reserved)
                dest = features.dest_of(ants, ant_loc, action)
            if self._record_path is not None:
                rows.append(
                    {
                        "turn": self._turn,
                        "loc": list(ant_loc),
                        "dest": list(dest),
                        "action": action,
                        "cues": feats,
                    }
                )
            if action == "stay":
                continue
            ants.issue_order((ant_loc, action))
            reserved.add(dest)
            if ants.time_remaining() < 10:
                break
        if self._record_path is not None and rows:
            with open(self._record_path, "a") as f:
                for row in rows:
                    f.write(json.dumps(row) + "\n")

    def _fallback(
        self,
        feats: dict[str, dict[str, float]],
        ants: Ants,
        loc: tuple[int, int],
        reserved: set[tuple[int, int]],
    ) -> str:
        scored = sorted(
            features.ACTIONS,
            key=lambda a: sum(
                self.weights[k] * feats[a][k] for k in model.FEATURE_KEYS
            ),
            reverse=True,
        )
        for action in scored:
            dest = features.dest_of(ants, loc, action)
            if feats[action]["passable"] > 0 and dest not in reserved:
                return action
        return "stay"


if __name__ == "__main__":
    try:
        Ants.run(AlphaZeroBot())
    except KeyboardInterrupt:
        print("ctrl-c, leaving ...")
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
