"""Run a league match through tools/playgame.py and record it.

Bot commands use absolute paths: the engine runs each bot from its own
dir, where relative paths do not resolve. -HEAD suffixes pin to the
current HEAD sha so records are exact.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from pool import (
    ROOT,
    WORKBASE,
    DirtyTree,
    EngineDiverged,
    bot_cmd,
    bot_id,
    engine_on_main,
    is_clean,
    parse_id,
    short,
    worktree,
)

STATUS_ORDER = {"survived": 0, "eliminated": 1, "timeout": 2, "crashed": 3}


class EngineError(Exception):
    """The engine wrote no score, so there is no result to rate."""


def bind(cmd: str, python: str, rundir: str | Path) -> str:
    """Bind a manifest command to absolute paths. A leading python
    token becomes the league's own interpreter (never the caller's
    PATH); file tokens become absolute under rundir, so the engine's
    get_cmd_wd finds the bot dir. Anything else passes verbatim."""
    rundir = Path(rundir)
    parts = shlex.split(cmd)
    if parts[0] in ("python", "python3"):
        parts[0] = python
    return " ".join(str(rundir / p) if (rundir / p).is_file() else p for p in parts)


def parse_replay(path: str | Path) -> tuple[list, list, int, list]:
    d = json.loads(Path(path).read_text())
    if "score" not in d or "status" not in d:
        raise EngineError(f"{path} has no score: {d.get('error')}")
    return (
        list(d["score"]),
        list(d["status"]),
        d.get("game_length", 0),
        list(d.get("errors", [])),
    )


def require_playable(statuses: list, length: int) -> None:
    """A game where every bot crashed on launch is a setup fault, not
    a result to rate."""
    if length == 0 and all(s == "crashed" for s in statuses):
        raise EngineError("every bot crashed at turn 0 (bad command?)")


def rank_slots(scores: list, statuses: list) -> list[int]:
    """Slots best-first: higher score wins, status breaks ties."""
    return sorted(
        range(len(scores)), key=lambda s: (-scores[s], STATUS_ORDER[statuses[s]], s)
    )


def resolve(field: list[str], root: str | Path = ROOT) -> list[str]:
    out = []
    for bid in field:
        path, sha = parse_id(bid)
        if sha == "HEAD":
            sha = short(root, "HEAD")
        out.append(bot_id(path, sha))
    return out


def play_match(
    root: str | Path,
    python: str,
    field: list[str],
    map_rel: str,
    turns: int,
    turntime: int,
    loadtime: int,
    pseed: int,
    eseed: int,
    log_dir: str | Path,
    workbase: str | Path = WORKBASE,
) -> dict:
    root = Path(root)
    if not engine_on_main(root):
        raise EngineDiverged("tools/ diverges from branch main")
    if not is_clean(root):
        raise DirtyTree("bot tree is dirty; commit or stash before logged play")
    ids = resolve(field, root)
    cmds = []
    for bid in ids:
        path, sha = parse_id(bid)
        rundir = worktree(root, sha, workbase) / Path(path).parent
        cmds.append(bind(bot_cmd(root, bid, workbase), python, rundir))
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        python,
        str(root / "tools" / "playgame.py"),
        "--map_file",
        map_rel,
        "--nolaunch",
        "--turns",
        str(turns),
        "--turntime",
        str(turntime),
        "--loadtime",
        str(loadtime),
        "--player_seed",
        str(pseed),
        "--engine_seed",
        str(eseed),
        "--log_dir",
        str(log_dir),
        "--capture_errors",
    ] + cmds
    subprocess.run(cmd, cwd=root, check=True, capture_output=True)
    scores, statuses, length, errors = parse_replay(log_dir / "0.replay")
    try:
        require_playable(statuses, length)
    except EngineError as exc:
        raise EngineError(f"{exc}: {errors}") from None
    order = rank_slots(scores, statuses)
    return {
        "v": 1,
        "map": map_rel,
        "turns": turns,
        "turntime": turntime,
        "loadtime": loadtime,
        "engine": short(root, "main"),
        "pseed": pseed,
        "eseed": eseed,
        "field": ids,
        "result": [ids[s] for s in order],
        "length": length,
    }
