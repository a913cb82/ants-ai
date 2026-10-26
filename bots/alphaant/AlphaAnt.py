#!/usr/bin/env python
"""AlphaAnt: per-ant CNN policy bot (self-play student).

Inference runs the torch CNNPolicy from model.py over the 12-channel
local window, one ant at a time. Water and visible food are hard-masked
from the window (the engine ignores moves into both); the live
reservation set blocks already-claimed tiles so two ants never take the
same square. The 5 intent channels carry last turn's friendly action
distributions (T=1.0, temperature-free want) wherever a friendly ant
stands — communication with ant-local state intact. weights.json holds
the champion parameters; the trainer rewrites it only on promotion.
`AlphaAnt.py [weights]` points the bot at another file for self-play
games.
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


def _intent_for_turn(prev: dict) -> dict | None:
    """Ablation gate: AA_ZERO_INTENT blinds the policy to intent.

    The gateway measure for the comms axis — eval the champ with
    the gate shut; a score drop proves the policy reads the
    channels. Accumulation keeps running (the map stays warm);
    only the input is blinded."""
    if os.environ.get("AA_ZERO_INTENT"):
        return None
    return prev


def _accumulate_intent(new_map: dict, counts: dict, dest, dist) -> None:
    """File this turn's want under its destination (1-turn identity).

    The bot issues the orders, so dest is where the ant will be read
    next turn. Collisions (two ants, one dest) average — rare, and the
    mean is the honest shared signal."""
    key = tuple(dest)
    if key in new_map:
        n = counts[key] + 1
        new_map[key] = [v + (d - v) / n for v, d in zip(new_map[key], dist)]
        counts[key] = n
    else:
        new_map[key] = list(dist)
        counts[key] = 1


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
        self._prev_intent: dict = {}  # dest -> last turn's T=1.0 want
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
        seen = _intent_for_turn(self._prev_intent)
        windows = [
            features.local_window(ants, loc, view=view, intent=seen)
            for loc in mine
        ]
        with torch.no_grad():
            logits = self.policy(torch.stack(windows))
        recording = self._record_path is not None
        rows = []
        reserved = set(mine)
        undecided: tuple = ()
        new_intent: dict = {}
        counts: dict = {}
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
            with torch.no_grad():
                want = torch.softmax(masked, dim=0).tolist()
            _accumulate_intent(new_intent, counts, dest, want)
            if recording:
                rows.append({
                    "turn": self._turn,
                    "loc": list(ant_loc),
                    "dest": list(dest),
                    "action": action,
                    "window": windows[i].tolist(),
                    "legal": legal.tolist(),
                })
            if ants.time_remaining() < 10:
                undecided = tuple(mine[i + 1 :])
                break
        if undecided:
            # Time ran out: the ants stay, and their wants still file
            # for next turn's intent (recording or not — rated play
            # communicates too). Rows log only when recording.
            start = len(mine) - len(undecided)
            for j, rest in enumerate(undecided):
                rest_window = features.local_window(
                    ants, rest, view=view, intent=seen)
                with torch.no_grad():
                    rest_masked = model.mask_logits(
                        logits[start + j], rest_window, frozenset())
                _accumulate_intent(
                    new_intent, counts, rest,
                    torch.softmax(rest_masked, dim=0).tolist())
                if recording:
                    # Log the undecided ants as stays so training rows
                    # never starve late-order ants of credit.
                    rows.append({
                        "turn": self._turn,
                        "loc": list(rest),
                        "dest": list(rest),
                        "action": "stay",
                        "window": rest_window.tolist(),
                        "legal": model.legal_mask(
                            rest_window, frozenset()).tolist(),
                    })
        self._prev_intent = new_intent
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
