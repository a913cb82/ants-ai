"""Imitation probe (diagnostic, offline): can the frozen champion
architecture fit champion decisions from logged replay windows?

Reads the REAL archive (replays + champion weights) read-only; writes
nothing there. Trains a fresh student of the champion's arch with
behavioral cloning (bc.train_supervised) on the champion's own rows and
reports top-1 agreement overall and on combat rows (enemy visible in
the window). If agreement > 0.85, also evaluates the distilled policy
against the champion in scratch engine games (scratch archive under
/tmp) and reports the score. Changes no training code.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "ml"))

import algorithm  # noqa: E402
import bc  # noqa: E402
import features  # noqa: E402
import model  # noqa: E402

ENEMY = features.CHANNELS.index("enemy_ant")
REAL_ARCHIVE = Path("/home/abrai/projects/ants-ai/ml/archive")


def champ_owner(game: dict, champ_id: str) -> int:
    """Replay player index of the champion (games.jsonl a/b convention:
    player 0 issued side_a's orders, logged as `a`)."""
    return 0 if game.get("a") == champ_id else 1


def champ_rows(archive: Path, champ_id: str,
               max_games: int = 40) -> tuple[list, list[dict]]:
    """Champion-side decision rows from the most recent logged games.

    Read-only: replays are loaded, windows rebuilt via bc.extract_rows.
    Returns (rows, games_used)."""
    games = [json.loads(line) for line in
             (archive / "games.jsonl").read_text().splitlines()
             if line.strip()]
    mine = [g for g in games
            if g.get("a") == champ_id or g.get("b") == champ_id]
    rows, used = [], []
    for game in reversed(mine[-max_games:]):
        replay_path = archive / game.get("replay", "")
        if not replay_path.exists():
            continue
        try:
            replaydata = json.loads(replay_path.read_text())["replaydata"]
            all_rows = bc.extract_rows(replaydata)
        except (KeyError, ValueError, OSError):
            continue
        side = champ_owner(game, champ_id)
        keep = [r for r in all_rows if r.owner == side]
        if keep:
            rows.extend(keep)
            used.append(game)
    return rows, used


def combat_rows(rows: list) -> list:
    """Rows whose window shows at least one enemy ant (kill-relevant)."""
    return [r for r in rows if float(r.window[ENEMY].sum()) > 0]


def self_agreement(policy, rows: list, temperature: float = 2.0,
                   seed: int = 0, batch_size: int = 512) -> float:
    """Bayes ceiling for the probe: champ-argmax vs champ-sampled
    top-1 agreement at act-time temperature (multinomial over
    softmax(logits / T), the AlphaAnt.py sampling rule).

    A student can never beat this: the logged labels are single
    samples, so even the champion disagrees with its own argmax
    whenever sampling wanders. Seeded: identical seed -> identical
    draws. Both sides unmasked (rows carry no blocked set)."""
    import torch

    if not rows:
        return 0.0
    torch.manual_seed(seed)
    agree, n = 0, 0
    policy.eval()
    with torch.no_grad():
        for i in range(0, len(rows), batch_size):
            chunk = rows[i:i + batch_size]
            logits = policy(torch.stack([r.window for r in chunk]))
            argmax = logits.argmax(dim=1)
            probs = torch.softmax(logits / temperature, dim=1)
            samp = torch.multinomial(probs, 1).squeeze(1)
            agree += int((samp == argmax).sum())
            n += len(chunk)
    return agree / n


def distill(rows: list, arch: str = "base", epochs: int = 5,
            seed: int = 0) -> tuple:
    """Fresh-arch student fit on champion rows; returns (policy, stats)
    with train_acc / val_acc top-1 agreement."""
    train_rows, val_rows = bc.split_rows(rows, seed=seed)
    policy, fit = bc.train_supervised(train_rows, val_rows, epochs=epochs,
                                      seed=seed, arch=arch)
    out = dict(fit)
    out["n_rows"] = len(rows)
    combat_val = combat_rows(val_rows)
    out["combat_val_acc"] = bc.accuracy(policy, combat_val)
    out["n_combat_val"] = len(combat_val)
    return policy, out


def scratch_match(student_w: dict, champ_w: dict, games: int = 4,
                  turns: int = 60,
                  map_path: str = "tools/maps/example/tutorial1.map") -> dict:
    """Few scratch engine games, distilled student vs champion.

    Everything (stage dirs, logs) lives under a temp dir; the real
    archive is untouched. Returns wins/draws/losses for the student."""
    import game_if

    tmp = Path(tempfile.mkdtemp(prefix="probe-imit-"))
    try:
        cfg = game_if.GameConfig(map=map_path, turns=turns, temperature=0.0,
                                 player_seed=0, engine_seed=1000)
        win = draw = loss = 0
        for g in range(games):
            outdir = tmp / f"g{g}"
            # Alternate colors: student attacks both sides of the matchup.
            if g % 2 == 0:
                out = game_if.play(ROOT, sys.executable, student_w, champ_w,
                                   cfg, outdir, name_a="student",
                                   name_b="champ")
                s = out["game"]["score"]
                me, opp = s[0], s[1]
            else:
                out = game_if.play(ROOT, sys.executable, champ_w, student_w,
                                   cfg, outdir, name_a="champ",
                                   name_b="student")
                s = out["game"]["score"]
                me, opp = s[1], s[0]
            win += me > opp
            draw += me == opp
            loss += me < opp
        return {"wins": win, "draws": draw, "losses": loss, "games": games}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", default=str(REAL_ARCHIVE))
    ap.add_argument("--champ", default=None)
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--match-games", type=int, default=4)
    args = ap.parse_args()

    archive = Path(args.archive)
    champ_id = args.champ or json.loads(
        (archive / "champion.json").read_text())["id"]
    champ_w = json.loads(
        (archive / f"checkpoints/{champ_id}.json").read_text())
    arch = model.infer_arch(champ_w)
    print(f"champion {champ_id} arch={arch}")

    rows, used = champ_rows(archive, champ_id, max_games=args.games)
    print(f"games used: {len(used)} rows: {len(rows)}")
    if len(rows) < 100:
        print("too few rows; probe inconclusive")
        return
    student, stats = distill(rows, arch=arch, epochs=args.epochs,
                             seed=args.seed)
    print(f"top-1 agreement: train={stats['train_acc']:.3f} "
          f"val={stats['val_acc']:.3f} (n={stats['n_rows']})")
    print(f"combat val agreement: {stats['combat_val_acc']:.3f} "
          f"(n={stats['n_combat_val']})")
    if stats["val_acc"] > 0.85:
        student_w = algorithm.policy_weights(student)
        res = scratch_match(student_w, copy.deepcopy(champ_w),
                            games=args.match_games)
        print(f"scratch match (student vs champ): {res}")
    else:
        print("agreement <= 0.85: no scratch match (capacity suspect)")


if __name__ == "__main__":
    main()
