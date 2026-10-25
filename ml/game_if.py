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

BOT_DIR = Path(__file__).resolve().parents[1] / "bots" / "alphaant"
MAIN_BOT = "AlphaAnt.py"


def _safe_name(name: str) -> str:
    """Checkpoint ids are filename-safe; sanitize anything else."""
    safe = "".join(c for c in str(name) if c.isalnum() or c in ("-", "_"))
    return safe or "side"


@dataclass
class GameConfig:
    """One engine game. Seeds make temperature-0 games reproducible."""

    map: str
    turns: int
    temperature: float = 0.0
    player_seed: int = 0
    engine_seed: int = 0
    timeout: int = 600
    turntime_ms: int = 5000
    loadtime_ms: int = 15000


def _bot_files() -> list[str]:
    """Every bot module, derived from the bot dir: new files ride along."""
    return sorted(p.name for p in BOT_DIR.glob("*.py"))


def _bot_env(cfg: GameConfig) -> dict:
    """Environment for bot subprocesses.

    Single-threaded torch: each game spawns two fresh interpreters and
    a 6k-param net gains nothing from thread pools, while 8 workers x 2
    bots x 8 OpenMP threads oversubscribes the machine 8x and triples
    game time under parallel load (measured 21.7s -> 7.0s on 8 games).
    Training (driver process) keeps default threads."""
    env = dict(os.environ)
    env["AA_RECORD_DIR"] = "records"
    env["AA_TEMPERATURE"] = str(cfg.temperature)
    env["OMP_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    return env


def stage_side(base: Path, weights: dict, tag: str, name: str = "side") -> Path:
    """A runnable bot dir: copies of code plus this side's weights.

    The main bot file is staged as <name>.py so replays carry the
    checkpoint id (g004.py) instead of the same bot name every game.
    Copies, not symlinks: the engine resolves realpath for the working
    directory, and symlinks would land both sides back in the real bot
    dir (wrong weights, wrong record dir)."""
    side = base / tag
    side.mkdir(parents=True, exist_ok=True)
    (side / "records").mkdir(exist_ok=True)
    safe = _safe_name(name)
    for fname in _bot_files():
        dest = f"{safe}.py" if fname == MAIN_BOT else fname
        shutil.copy(BOT_DIR / fname, side / dest)
    (side / "weights.json").write_text(json.dumps(weights))
    return side


def play(
    root: Path,
    python: str,
    weights_a: dict,
    weights_b: dict,
    cfg: GameConfig,
    outdir: Path,
    name_a: str = "A",
    name_b: str = "B",
) -> dict:
    """Mirror-capable game. Returns {"game", "records_a", "records_b"}.

    Records land in each side's own dir: AA_RECORD_DIR is relative,
    so it resolves under the side's working directory. Attribution by
    side is exact, and nothing touches the real bot tree. Staged sides
    are removed before return; the replay logs stay.
    """
    outdir = Path(outdir)
    log_dir = outdir / "logs"
    side_a = stage_side(outdir, weights_a, "side_a", name_a)
    side_b = stage_side(outdir, weights_b, "side_b", name_b)
    env = _bot_env(cfg)
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
        "--turntime",
        str(cfg.turntime_ms),
        "--loadtime",
        str(cfg.loadtime_ms),
        "--log_dir",
        str(log_dir),
        f"{python} {side_a / (_safe_name(name_a) + '.py')}",
        f"{python} {side_b / (_safe_name(name_b) + '.py')}",
    ]
    try:
        _run_once(cmd, root, env, cfg.timeout)
    finally:
        records_a, records_b = _read_records(side_a), _read_records(side_b)
        cleanup(outdir)
    game = json.loads((log_dir / "0.replay").read_text())
    retried = False
    if game.get("game_length", 1) == 0:
        # Turn-1 timeout under load: both sides log nothing and the game
        # carries zero signal. One retry with a fresh engine seed; a
        # double-timeout is reported, not hidden.
        for tag in ("side_a", "side_b"):
            shutil.rmtree(outdir / tag, ignore_errors=True)
        shutil.rmtree(log_dir, ignore_errors=True)
        side_a = stage_side(outdir, weights_a, "side_a", name_a)
        side_b = stage_side(outdir, weights_b, "side_b", name_b)
        at = cmd.index("--engine_seed") + 1
        cmd_retry = cmd[:at] + [str(cfg.engine_seed + 7919)] + cmd[at + 1 :]
        try:
            _run_once(cmd_retry, root, env, cfg.timeout)
        finally:
            records_a, records_b = _read_records(side_a), _read_records(side_b)
            cleanup(outdir)
        game = json.loads((log_dir / "0.replay").read_text())
        retried = True
    return {"game": game, "records_a": records_a, "records_b": records_b,
            "retried": retried}


def _run_once(cmd: list, root: Path, env: dict, timeout: int) -> None:
    """One engine invocation; raises TimeoutError/RuntimeError."""
    try:
        proc = subprocess.run(
            cmd, cwd=root, capture_output=True, env=env, timeout=timeout
        )
        proc.check_returncode()
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"engine game timed out after {timeout}s") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"engine failed: {exc.stderr.decode()[-2000:]}"
        ) from exc


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
