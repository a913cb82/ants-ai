"""Behavioral cloning from PRO bot replays (imitate-then-self-play, AlphaStar recipe).

Step 1 (data): play_pro_games() runs xathis-vs-xathis engine games and
saves replays. Step 2 (rows): extract_rows() rebuilds every ant's
9x9 6-channel egocentric window at every decision turn and labels it
with the ant's actual order. Step 3 (init): train_supervised() fits
CNNPolicy's actor head with cross-entropy; the best-val checkpoint is
saved in policy_weights list format for self-play to start from.

Order-char -> ACTIONS mapping (tools/ants.py): bots may only issue
`o row col <d>` with d in {n,e,s,w} (parse_orders rejects the rest);
do_orders records one char per ant per turn, "-" when the ant got no
order (stay / blocked dest / dead player). Combat is fully automatic
(do_attack_*), so no attack/wait chars exist; any char outside
{n,e,s,w,-} is skipped as ambiguous. Replay entry
[r, c, spawn, end, owner, orders] carries orders[i] = move executed on
turn spawn+1+i ("-" = stay; rewards.trajectories). The spawn turn has
no decision and yields no row; turns past len(orders) (dead ants) have
no order and are skipped. A killed ant's death-turn row IS kept: the
ant was alive at decision time.

Window rebuild at decision turn t reuses rewards.trajectories() for
positions and the food presence convention s<=t<=e. The ant decides
from its turn-(t-1) tile; other ants are placed at their turn-(t-1)
tiles (only ants alive then appear). Hills are static (all replay
hills, split by owner); water is static ('%' cells of the replay map).
The window itself is built by features.local_window with a prebuilt
view, so no live engine object is needed.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "ml"))

import algorithm  # noqa: E402
import features  # noqa: E402
import model  # noqa: E402
import rewards  # noqa: E402
from features import ACTIONS  # noqa: E402
from grid import dist2, step  # noqa: E402

ORDER_TO_ACTION = {"n": "n", "e": "e", "s": "s", "w": "w", "-": "stay"}
ACTION_INDEX = {a: i for i, a in enumerate(ACTIONS)}
LABEL_OF = {c: ACTION_INDEX[a] for c, a in ORDER_TO_ACTION.items()}

PRO_MAPS = [
    "tools/maps/example/tutorial1.map",
    "tools/maps/generated/gen2p_00.map",
    "tools/maps/generated/gen2p_01.map",
    "tools/maps/generated/gen2p_02.map",
    "tools/maps/maze/maze_p02_01.map",
    "tools/maps/maze/maze_p02_02.map",
]


@dataclass
class Row:
    """One supervised example: window, label, and rollout-sanity fields."""

    window: object  # torch.Tensor (6, H, W), float32
    label: int
    turn: int
    owner: int
    loc: tuple[int, int]
    foods: tuple  # present-food tiles at decision turn
    dims: tuple[int, int]  # (rows, cols) of the map, for toroidal dist


def label_of(char: str) -> int | None:
    """Order char -> ACTIONS index; None means skip (ambiguous)."""
    return LABEL_OF.get(char)


def water_of(replaydata: dict) -> set:
    """Static water set from the replay map ('%' cells)."""
    out = set()
    for r, line in enumerate(replaydata["map"]["data"]):
        for c, ch in enumerate(line):
            if ch == "%":
                out.add((r, c))
    return out


def extract_rows(replaydata: dict, radius: int = features.DEFAULT_RADIUS) -> list[Row]:
    """Replay -> supervised rows for BOTH players' ants."""
    rows = replaydata["map"]["rows"]
    cols = replaydata["map"]["cols"]
    dims = (rows, cols)
    sight2 = replaydata.get("viewradius2", 77)
    water = water_of(replaydata)
    trajs = rewards.trajectories(replaydata)
    entries = list(replaydata["ants"])
    by_ant = []
    for idx, (_r, _c, spawn, _end, owner, orders) in enumerate(entries):
        by_ant.append((spawn, owner, orders,
                       {t: loc for t, loc in trajs[(owner, idx)]}))
    hills = [(r, c, o) for r, c, o, _e in replaydata.get("hills", [])]
    foods = [(r, c, s, e) for r, c, s, e, *_ in replaydata.get("food", [])]

    out: list[Row] = []
    for spawn, owner, orders, d in by_ant:
        for i, char in enumerate(orders):
            label = label_of(char)
            if label is None:
                continue
            t = spawn + 1 + i
            if t - 1 not in d:
                continue  # dead before decision time; no window
            loc = tuple(d[t - 1])
            own_ants, enemy_ants = set(), set()
            for _s2, o2, _o3, d2 in by_ant:
                if t - 1 in d2:
                    (own_ants if o2 == owner else enemy_ants).add(tuple(d2[t - 1]))
            present = tuple((fr, fc) for fr, fc, fs, fe in foods if fs <= t <= fe)
            view = SimpleNamespace(
                rows=rows, cols=cols, sight2=sight2,
                own_ants=own_ants,
                own_hills={(hr, hc) for hr, hc, ho in hills if ho == owner},
                enemy_ants=enemy_ants,
                enemy_hills={(hr, hc) for hr, hc, ho in hills if ho != owner},
                foods=set(present),
                water=water,
            )
            window = features.local_window(None, loc, radius=radius, view=view)
            out.append(Row(window, label, t, owner, loc, present, dims))
    return out


def split_rows(rows: list[Row], val_frac: float = 0.1,
               seed: int = 0) -> tuple[list[Row], list[Row]]:
    """Deterministic shuffle; first val_frac -> val."""
    import random

    idx = list(range(len(rows)))
    random.Random(seed).shuffle(idx)
    val_ids = set(idx[:int(len(rows) * val_frac)])
    return ([r for i, r in enumerate(rows) if i not in val_ids],
            [r for i, r in enumerate(rows) if i in val_ids])


def batch_loss(policy, batch: list) -> object:
    """Mean cross-entropy over (window, label) pairs."""
    import torch

    windows = torch.stack([w for w, _ in batch])
    labels = torch.tensor([y for _, y in batch], dtype=torch.long)
    return torch.nn.functional.cross_entropy(policy(windows), labels)


def accuracy(policy, rows: list[Row], batch_size: int = 512) -> float:
    """Top-1 accuracy, no grad."""
    import torch

    if not rows:
        return 0.0
    correct = 0
    with torch.no_grad():
        for i in range(0, len(rows), batch_size):
            chunk = rows[i:i + batch_size]
            pred = policy(torch.stack([r.window for r in chunk])).argmax(dim=1)
            correct += int((pred == torch.tensor(
                [r.label for r in chunk])).sum())
    return correct / len(rows)


def train_supervised(train_rows: list[Row], val_rows: list[Row],
                     epochs: int = 10, lr: float = 1e-3,
                     batch_size: int = 256, seed: int = 0,
                     arch: str = "base") -> tuple:
    """Cross-entropy fit of a randomly init'ed actor; best-val kept."""
    import torch

    torch.manual_seed(seed)
    policy = model.CNNPolicy(arch=arch)
    opt = torch.optim.Adam(policy.parameters(), lr=lr)
    best = copy.deepcopy(policy.state_dict())
    best_val = -1.0
    for _ in range(epochs):
        order = torch.randperm(len(train_rows)).tolist()
        policy.train()
        for i in range(0, len(train_rows), batch_size):
            chunk = [train_rows[j] for j in order[i:i + batch_size]]
            opt.zero_grad()
            loss = batch_loss(policy, [(r.window, r.label) for r in chunk])
            loss.backward()
            opt.step()
        val_acc = accuracy(policy, val_rows)
        if val_acc > best_val:
            best_val, best = val_acc, copy.deepcopy(policy.state_dict())
    policy.load_state_dict(best)
    policy.eval()
    return policy, {"train_acc": accuracy(policy, train_rows),
                    "val_acc": accuracy(policy, val_rows)}


def food_progress(rows: list[Row], policy) -> float:
    """Rollout sanity: fraction of food-visible rows where the greedy
    action strictly reduces toroidal distance to the nearest food."""
    import torch

    hits, total = 0, 0
    with torch.no_grad():
        for r in rows:
            if not r.foods:
                continue
            total += 1
            before = min(dist2(r.loc, f, *r.dims) for f in r.foods)
            pred = ACTIONS[int(policy(r.window.unsqueeze(0)).argmax())]
            after = min(dist2(step(r.loc, pred, *r.dims), f, *r.dims)
                        for f in r.foods)
            hits += after < before
    return hits / total if total else 0.0


def save_weights(policy, path: str | Path) -> dict:
    """Best checkpoint in policy_weights list format (bot-loadable)."""
    lists = algorithm.policy_weights(policy)
    Path(path).write_text(json.dumps(lists))
    return lists


def play_pro_games(outdir: str | Path, python: str,
                   maps: list[str] = PRO_MAPS, turns: int = 200,
                   timeout: int = 1200) -> tuple[list[Path], str]:
    """One pro-vs-pro game per map; per-map fallback to fourmidable if
    the xathis game carries no score. Returns replay paths plus which
    pro bot actually played ("xathis", "fourmidable", or "mixed")."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    paths, used = [], set()
    for i, map_rel in enumerate(maps):
        for attempt in ("xathis", "fourmidable"):
            d = outdir / f"g{i}"
            d.mkdir(parents=True, exist_ok=True)
            bot = str(ROOT / f"bots/{attempt}/{attempt}.sh")
            cmd = [python, str(ROOT / "tools" / "playgame.py"),
                   "--map_file", str(ROOT / map_rel), "--turns", str(turns),
                   "--nolaunch", "--player_seed", str(1000 + i),
                   "--engine_seed", str(2000 + i), "--turntime", "2000",
                   "--loadtime", "30000", "--log_dir", str(d), bot, bot]
            subprocess.run(cmd, cwd=ROOT, capture_output=True,
                           timeout=timeout, check=True)
            game = json.loads((d / "0.replay").read_text())
            if "score" in game:
                paths.append(d / "0.replay")
                used.add(attempt)
                break
    pro = used.pop() if len(used) == 1 else "mixed"
    return paths, pro


def main() -> None:
    outdir = Path("/tmp/bcpros")
    paths, pro = play_pro_games(outdir / "games", sys.executable)
    rows: list[Row] = []
    for p in paths:
        rows.extend(extract_rows(json.loads(Path(p).read_text())["replaydata"]))
    train_rows, val_rows = split_rows(rows)
    policy, stats = train_supervised(train_rows, val_rows)
    wpath = outdir / "bc_weights.json"
    save_weights(policy, wpath)
    print(json.dumps({
        "pro": pro, "games": len(paths), "rows": len(rows),
        "train_acc": round(stats["train_acc"], 4),
        "val_acc": round(stats["val_acc"], 4),
        "food_progress": round(food_progress(val_rows, policy), 4),
        "weights": str(wpath)}))


if __name__ == "__main__":
    main()
