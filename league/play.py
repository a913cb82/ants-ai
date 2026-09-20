"""Run a league match through tools/playgame.py and record it.

Bot commands use absolute paths: the engine runs each bot from its own
dir, where relative paths do not resolve. -HEAD suffixes pin to the
current HEAD sha so records are exact.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pool import ROOT, DirtyTree, bot_cmd, bot_id, is_clean, parse_id, short

STATUS_ORDER = {"survived": 0, "eliminated": 1, "timeout": 2, "crashed": 3}


def parse_replay(path: str | Path) -> tuple[list, list]:
    d = json.loads(Path(path).read_text())
    return list(d["score"]), list(d["status"])


def rank_slots(scores: list, statuses: list) -> list[int]:
    """Slots best-first: higher score wins, status breaks ties."""
    return sorted(range(len(scores)),
                  key=lambda s: (-scores[s],
                                 STATUS_ORDER.get(statuses[s], 5), s))


def resolve(field: list[str], root: str | Path = ROOT) -> list[str]:
    out = []
    for bid in field:
        path, sha = parse_id(bid)
        if sha == "HEAD":
            sha = short(root, "HEAD")
        out.append(bot_id(path, sha))
    return out


def play_match(root: str | Path, python: str, field: list[str],
               map_rel: str, turns: int, turntime: int, loadtime: int,
               pseed: int, eseed: int, log_dir: str | Path,
               timeout: int = 300) -> dict:
    root = Path(root)
    if not is_clean(root):
        raise DirtyTree("bots/ is dirty; commit or stash before logged play")
    ids = resolve(field, root)
    cmds = []
    for bid in ids:
        py, entry = bot_cmd(root, bid, python)
        cmds.append(f"{py} {entry}")
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    cmd = ([python, str(root / "tools" / "playgame.py"),
            "--map_file", map_rel, "--nolaunch",
            "--turns", str(turns), "--turntime", str(turntime),
            "--loadtime", str(loadtime),
            "--player_seed", str(pseed), "--engine_seed", str(eseed),
            "--log_dir", str(log_dir), "--capture_errors"]
           + cmds)
    subprocess.run(cmd, cwd=root, check=True, capture_output=True,
                   timeout=timeout)
    scores, statuses = parse_replay(log_dir / "0.replay")
    order = rank_slots(scores, statuses)
    return {"v": 1, "map": map_rel, "turns": turns, "turntime": turntime,
            "loadtime": loadtime, "engine": short(root, "main"),
            "pseed": pseed, "eseed": eseed, "field": ids,
            "result": [ids[s] for s in order]}
