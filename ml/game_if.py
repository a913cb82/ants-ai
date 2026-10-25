"""Engine interface: play a game, get back data.

Knows the playgame CLI, side-dir staging, and the replay/record file
formats. Knows nothing about torch or learning: results come back as
plain dicts and lists. Deterministic when seeds are given.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parents[1] / "bots" / "alphastarzero"


@dataclass
class GameConfig:
    """One engine game. Seeds make temperature-0 games reproducible."""

    map: str
    turns: int
    temperature: float = 0.0
    player_seed: int = 0
    engine_seed: int = 0
    timeout: int = 600


def _bot_files() -> list[str]:
    """Every bot module, derived from the bot dir: new files ride along."""
    return sorted(p.name for p in BOT_DIR.glob("*.py"))


def stage_side(base: Path, weights: dict, tag: str) -> Path:
    """A runnable bot dir: copies of code plus this side's weights.

    Copies, not symlinks: the engine resolves realpath for the working
    directory, and symlinks would land both sides back in the real bot
    dir (wrong weights, wrong record dir)."""
    side = base / tag
    side.mkdir(parents=True, exist_ok=True)
    (side / "records").mkdir(exist_ok=True)
    for name in _bot_files():
        shutil.copy(BOT_DIR / name, side / name)
    (side / "weights.json").write_text(json.dumps(weights))
    return side


def play(
    root: Path,
    python: str,
    weights_a: dict,
    weights_b: dict,
    cfg: GameConfig,
    outdir: Path,
) -> dict:
    """Mirror-capable game. Returns {"game", "records_a", "records_b"}.

    Records land in each side's own dir: AZ0_RECORD_DIR is relative,
    so it resolves under the side's working directory. Attribution by
    side is exact, and nothing touches the real bot tree. Staged sides
    are removed before return; the replay logs stay.
    """
    outdir = Path(outdir)
    log_dir = outdir / "logs"
    side_a = stage_side(outdir, weights_a, "side_a")
    side_b = stage_side(outdir, weights_b, "side_b")
    env = dict(os.environ)
    env["AZ0_RECORD_DIR"] = "records"
    env["AZ0_TEMPERATURE"] = str(cfg.temperature)
    cmd = [
        python,
        str(root / "tools" / "playgame.py"),
        "--map_file",
        cfg.map,
        "--nolaunch",
        "--turns",
        str(cfg.turns),
        "--player_seed",
        str(cfg.player_seed),
        "--engine_seed",
        str(cfg.engine_seed),
        "--log_dir",
        str(log_dir),
        f"{python} {side_a / 'MLBot.py'}",
        f"{python} {side_b / 'MLBot.py'}",
    ]
    try:
        proc = subprocess.run(
            cmd, cwd=root, capture_output=True, env=env, timeout=cfg.timeout
        )
        proc.check_returncode()
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"engine game timed out after {cfg.timeout}s") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"engine failed: {exc.stderr.decode()[-2000:]}"
        ) from exc
    finally:
        records_a, records_b = _read_records(side_a), _read_records(side_b)
        cleanup(outdir)
    game = json.loads((log_dir / "0.replay").read_text())
    return {"game": game, "records_a": records_a, "records_b": records_b}


def _read_records(side: Path) -> list:
    """Bot decision rows; skips corrupt lines (a bad row must not kill
    a paid-for game)."""
    rows = []
    for path in sorted(side.glob("records/*.jsonl")):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    return rows


def cleanup(outdir: Path) -> None:
    """Drop staged side dirs after pricing; keep the replay logs."""
    for tag in ("side_a", "side_b"):
        shutil.rmtree(Path(outdir) / tag, ignore_errors=True)
