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


def map_player_count(map_path) -> int:
    """Player count from the map header (single small read)."""
    with open(map_path) as f:
        for line in f:
            if line.startswith("players "):
                return int(line.split()[1])
    raise ValueError(f"no players header in {map_path}")


def play(
    root: Path,
    python: str,
    weights: list[dict],
    cfg: GameConfig,
    outdir: Path,
    names: list[str] | None = None,
) -> dict:
    """N-sided game. Returns {"game", "records" (per-seat list), ...}.

    Seats are fixed: weights[i] plays engine player i. Attribution by
    side is exact, and nothing touches the real bot tree. Staged sides
    are removed before return; the replay logs stay.
    """
    if names is None:
        names = [f"side_{i}" for i in range(len(weights))]
    assert len(names) == len(weights)
    outdir = Path(outdir)
    log_dir = outdir / "logs"
    sides = [
        stage_side(outdir, w, f"side_{i}", names[i]) for i, w in enumerate(weights)
    ]
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
    ]
    for i, side in enumerate(sides):
        cmd.append(f"{python} {side / (_safe_name(names[i]) + '.py')}")
    attempts = []
    try:
        attempts.append(_parse_breaks(_run_once(cmd, root, env, cfg.timeout)))
    finally:
        records = [_read_records(side) for side in sides]
        cleanup(outdir)
    game = json.loads((log_dir / "0.replay").read_text())
    retried = False
    if game.get("game_length", 1) == 0:
        # Turn-1 timeout under load: all sides log nothing and the game
        # carries zero signal. One retry with a fresh engine seed; a
        # double-timeout is reported, not hidden.
        for i in range(len(sides)):
            shutil.rmtree(outdir / f"side_{i}", ignore_errors=True)
        shutil.rmtree(log_dir, ignore_errors=True)
        sides = [
            stage_side(outdir, w, f"side_{i}", names[i]) for i, w in enumerate(weights)
        ]
        at = cmd.index("--engine_seed") + 1
        cmd_retry = cmd[:at] + [str(cfg.engine_seed + 7919)] + cmd[at + 1 :]
        try:
            attempts.append(
                _parse_breaks(_run_once(cmd_retry, root, env, cfg.timeout))
            )
        finally:
            records = [_read_records(side) for side in sides]
            cleanup(outdir)
        game = json.loads((log_dir / "0.replay").read_text())
        retried = True
    with open(log_dir / "breaks.jsonl", "a") as f:
        for i, br in enumerate(attempts):
            f.write(json.dumps({"attempt": i, "breaks": br}) + "\n")
    return {
        "game": game,
        "records": records,
        "retried": retried,
        "breaks": sum(len(br) for br in attempts),
    }


def _parse_breaks(stderr: bytes) -> list[dict]:
    """Bot early-stop lines: BREAK side=<seat> turn=<t> decided=<d>/<m>.

    Anything else on the stream (orders, tracebacks) is ignored here."""
    out = []
    for line in (stderr or b"").decode(errors="replace").splitlines():
        if not line.startswith("BREAK "):
            continue
        try:
            parts = dict(p.split("=", 1) for p in line.split()[1:])
            dec, live = parts["decided"].split("/")
            out.append(
                {
                    "side": parts["side"],
                    "turn": int(parts["turn"]),
                    "decided": int(dec),
                    "live": int(live),
                }
            )
        except (KeyError, ValueError):
            continue
    return out


def _run_once(cmd: list, root: Path, env: dict, timeout: int) -> bytes:
    """One engine invocation; returns stderr. Raises
    TimeoutError/RuntimeError.

    Engine stdout (the turn-by-turn visualizer stream, hundreds of MB
    on 250-turn 10-seat games) goes straight to DEVNULL: buffering it
    with capture_output=True piles GBs in RAM under concurrency and
    OOM-kills the trainer. Nothing reads stdout (replay and records
    come from log_dir/side dirs); stderr stays piped so failures still
    report their tail, and bot BREAK lines ride it to the logs dir."""
    try:
        proc = subprocess.run(
            cmd, cwd=root, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, env=env, timeout=timeout,
        )
        proc.check_returncode()
        return proc.stderr
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"engine game timed out after {timeout}s") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"engine failed: {exc.stderr.decode()[-2000:]}") from exc


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
    for tag in Path(outdir).glob("side_*"):
        shutil.rmtree(tag, ignore_errors=True)
