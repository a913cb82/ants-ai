"""One automated generation: sample opponents, play, train, evaluate, promote.

Thin orchestration over the clean layers: game_if plays, rewards
prices, algorithm trains, archive ranks. No judgment calls inside:
promotion is win-rate threshold AND Nash mass, both computed, both
logged. The rated bot file changes only on promotion.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "bots" / "alphastarzero"))

import algorithm
import archive
import game_if
import model
import rewards

BOT_WEIGHTS = ROOT / "bots" / "alphastarzero" / "weights.json"


def default_config() -> dict:
    return {
        "maps": ["tools/maps/example/tutorial1.map"],
        "turns": 50,
        "train_games": 4,
        "eval_games": 6,
        "temperature": 1.0,
        "lr": 1e-3,
        "epochs": 3,
        "promote_threshold": 0.55,
        "seed": 0,
        "archive": "ml/archive",
        "commit": True,
    }


def parse_args(argv: list[str] | None = None) -> dict:
    import argparse

    defaults = default_config()
    p = argparse.ArgumentParser(description="Run one automated generation.")
    p.add_argument("--maps", nargs="+", default=defaults["maps"])
    p.add_argument("--turns", type=int, default=defaults["turns"])
    p.add_argument("--train-games", type=int, default=defaults["train_games"])
    p.add_argument("--eval-games", type=int, default=defaults["eval_games"])
    p.add_argument("--temperature", type=float, default=defaults["temperature"])
    p.add_argument("--lr", type=float, default=defaults["lr"])
    p.add_argument("--epochs", type=int, default=defaults["epochs"])
    p.add_argument("--promote-threshold", type=float,
                   default=defaults["promote_threshold"])
    p.add_argument("--seed", type=int, default=defaults["seed"])
    p.add_argument("--archive", default=defaults["archive"])
    p.add_argument("--commit", action=argparse.BooleanOptionalAction,
                   default=defaults["commit"])
    args = p.parse_args(argv)
    return {
        "maps": args.maps,
        "turns": args.turns,
        "train_games": args.train_games,
        "eval_games": args.eval_games,
        "temperature": args.temperature,
        "lr": args.lr,
        "epochs": args.epochs,
        "promote_threshold": args.promote_threshold,
        "seed": args.seed,
        "archive": args.archive,
        "commit": args.commit,
    }


def _random_weights(seed: int) -> dict:
    torch.manual_seed(seed)
    return model.state_dict_to_lists(model.CNNPolicy())


def _train_weights(cfg: dict, base: Path, champ_id: str, champ_w: dict) -> tuple[str, dict, int]:
    """Self-play training games -> (challenger id, weights, row count)."""
    chal_id = archive.save_checkpoint(base, copy.deepcopy(champ_w), "challenger", champ_id)
    chal_w = copy.deepcopy(champ_w)
    batch: list = []
    for g in range(cfg["train_games"]):
        opp_id = archive.sample_opponents(
            base, champ_id, 1, seed=cfg["seed"] + g
        )[0]
        opp_w = archive.load_checkpoint(base, opp_id)
        game_map = cfg["maps"][g % len(cfg["maps"])]
        for slot in (0, 1):
            me_w, other_w = (chal_w, opp_w) if slot == 0 else (opp_w, chal_w)
            out = game_if.play(
                ROOT,
                sys.executable,
                me_w,
                other_w,
                game_map,
                cfg["turns"],
                base / "games" / f"train{g}_slot{slot}",
                temperature=cfg["temperature"],
                player_seed=cfg["seed"] + g,
                engine_seed=1000 + g,
            )
            game = out["game"]
            rows = out["records_a"] if slot == 0 else out["records_b"]
            rets = rewards.compute_returns(game, slot, rows)
            batch.extend(algorithm.to_batch(rows, rets))
            game_if.cleanup(base / "games" / f"train{g}_slot{slot}")
            sa, sb = game["score"][0], game["score"][1]
            archive.record_result(base, chal_id if slot == 0 else opp_id,
                                  opp_id if slot == 0 else chal_id, sa, sb)
    policy = model.CNNPolicy()
    policy.load_state_dict(model.lists_to_state_dict(chal_w))
    losses = []
    for _ in range(cfg["epochs"]):
        stats = algorithm.reinforce_step(policy, batch, lr=cfg["lr"])
        losses.append(stats["loss"])
    chal_w = model.state_dict_to_lists(policy)
    archive.store(base, chal_id, chal_w)
    mean_return = sum(r for _w, _a, r in batch) / len(batch) if batch else 0.0
    return chal_id, chal_w, {"rows": len(batch), "losses": losses,
                             "mean_return": mean_return}


def _evaluate(cfg: dict, base: Path, chal_id: str, chal_w: dict,
              champ_id: str, champ_w: dict) -> dict:
    wins = draws = 0
    for g in range(cfg["eval_games"]):
        slot = g % 2
        me_w, other_w = (chal_w, champ_w) if slot == 0 else (champ_w, chal_w)
        out = game_if.play(
            ROOT, sys.executable, me_w, other_w,
            cfg["maps"][g % len(cfg["maps"])], cfg["turns"],
            base / "games" / f"eval{g}",
            temperature=0.0, player_seed=5000 + g, engine_seed=9000 + g,
        )
        game = out["game"]
        sa, sb = game["score"][0], game["score"][1]
        archive.record_result(base, chal_id if slot == 0 else champ_id,
                              champ_id if slot == 0 else chal_id, sa, sb)
        game_if.cleanup(base / "games" / f"eval{g}")
        chal_score, champ_score = (sa, sb) if slot == 0 else (sb, sa)
        wins += chal_score > champ_score
        draws += chal_score == champ_score
    return {"wins": wins, "draws": draws, "games": cfg["eval_games"],
            "win_rate": (wins + 0.5 * draws) / cfg["eval_games"]}


def should_promote(win_rate: float, nash_chal: float, nash_champ: float,
                   threshold: float) -> bool:
    """Automated promotion: duel threshold AND Nash mass. No judgment."""
    return win_rate >= threshold and nash_chal >= nash_champ


def run_generation(cfg: dict, base: Path, commit: bool = True) -> dict:
    archive.init(base)
    champ_id = archive.get_champion(base)
    if champ_id is None:
        champ_w = _random_weights(cfg["seed"])
        champ_id = archive.save_checkpoint(base, champ_w, "main", None)
        archive.set_champion(base, champ_id)
    else:
        champ_w = archive.load_checkpoint(base, champ_id)
    chal_id, chal_w, train_stats = _train_weights(cfg, base, champ_id, champ_w)
    ev = _evaluate(cfg, base, chal_id, chal_w, champ_id, champ_w)
    mix = archive.nash_mixture(base)
    promoted = should_promote(ev["win_rate"], mix.get(chal_id, 0.0),
                              mix.get(champ_id, 0.0), cfg["promote_threshold"])
    if promoted:
        archive.set_champion(base, chal_id)
        BOT_WEIGHTS.write_text(json.dumps(chal_w))
        if commit:
            subprocess.run(
                ["git", "-C", str(ROOT), "add", str(BOT_WEIGHTS)], check=True
            )
            subprocess.run(
                ["git", "-C", str(ROOT), "commit", "-m",
                 f"ml: promote {chal_id} over {champ_id} "
                 f"(win-rate {ev['win_rate']:.2f}, nash {mix.get(chal_id, 0.0):.2f})"],
                check=True,
            )
    report = {"champion": champ_id, "challenger": chal_id,
              "train": train_stats, "eval": ev, "nash": mix,
              "promoted": promoted, "config": cfg}
    (base / "last_report.json").write_text(json.dumps(report, indent=1))
    return report


def main(argv: list[str] | None = None) -> dict:
    cfg = parse_args(argv)
    return run_generation(cfg, Path(cfg["archive"]), commit=cfg["commit"])


if __name__ == "__main__":
    report = main()
    print(json.dumps({k: v for k, v in report.items() if k != "nash"}, indent=1))
