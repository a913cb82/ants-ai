"""Engine interface: play a game, get back data.

Knows the playgame CLI, side-dir staging, and the replay/record file
formats. Knows nothing about torch or learning: results come back as
plain dicts and lists. Deterministic when seeds are given.
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parents[1] / "bots" / "alphastarzero"
BOT_FILES = ("MLBot.py", "ants.py", "features.py", "model.py")


def stage_side(base: Path, weights: dict, tag: str) -> Path:
    """A runnable bot dir: copies of code plus this side's weights.

    Copies, not symlinks: the engine resolves realpath for the working
    directory, and symlinks would land both sides back in the real bot
    dir (wrong weights, wrong record dir)."""
    import shutil

    side = base / tag
    side.mkdir(parents=True, exist_ok=True)
    (side / "records").mkdir(exist_ok=True)
    for name in BOT_FILES:
        shutil.copy(BOT_DIR / name, side / name)
    (side / "weights.json").write_text(json.dumps(weights))
    return side


def play(
    root: Path,
    python: str,
    weights_a: dict,
    weights_b: dict,
    map_rel: str,
    turns: int,
    outdir: Path,
    temperature: float = 0.0,
    player_seed: int = 0,
    engine_seed: int = 0,
) -> dict:
    """Mirror-capable game. Returns {"game", "records_a", "records_b"}.

    Records land in each side's own dir: AZ0_RECORD_DIR is relative,
    so it resolves under the side's working directory. Attribution by
    side is exact, and nothing touches the real bot tree.
    """
    outdir = Path(outdir)
    log_dir = outdir / "logs"
    side_a = stage_side(outdir, weights_a, "side_a")
    side_b = stage_side(outdir, weights_b, "side_b")
    env = dict(os.environ)
    env["AZ0_RECORD_DIR"] = "records"
    env["AZ0_TEMPERATURE"] = str(temperature)
    cmd = [
        python,
        str(root / "tools" / "playgame.py"),
        "--map_file",
        map_rel,
        "--nolaunch",
        "--turns",
        str(turns),
        "--player_seed",
        str(player_seed),
        "--engine_seed",
        str(engine_seed),
        "--log_dir",
        str(log_dir),
        f"{python} {side_a / 'MLBot.py'}",
        f"{python} {side_b / 'MLBot.py'}",
    ]
    subprocess.run(cmd, cwd=root, check=True, capture_output=True, env=env)
    game = json.loads((log_dir / "0.replay").read_text())
    return {
        "game": game,
        "records_a": _read_records(side_a),
        "records_b": _read_records(side_b),
    }


def _read_records(side: Path) -> list:
    rows = []
    for path in sorted(glob.glob(str(side / "records" / "*.jsonl"))):
        rows.extend(json.loads(line) for line in open(path) if line.strip())
    return rows


def cleanup(outdir: Path) -> None:
    """Drop staged side dirs after pricing; keep the replay logs."""
    import shutil

    for tag in ("side_a", "side_b"):
        shutil.rmtree(Path(outdir) / tag, ignore_errors=True)
