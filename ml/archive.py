"""Population store: frozen checkpoints, payoff matrices, matchmaking.

Everything learned lives here, outside git: checkpoints as weight
lists, one manifest line per member, one payoff entry per duel. Two
matrices: train (diagnostic, exploratory games) and eval (canonical,
greedy games). Opponent sampling (PFSP-lite) and promotion ranking
(Nash mass over the empirical game) read the eval matrix only, so
exploration noise never ranks or teaches.
Pure files + numpy; knows nothing about torch or the engine.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

DEFAULT_DIR = Path(__file__).resolve().parent / "archive"


def _paths(base: Path) -> dict[str, Path]:
    return {
        "dir": base,
        "checkpoints": base / "checkpoints",
        "manifest": base / "manifest.jsonl",
        "matrix": base / "matrix.json",
    }


def init(base: Path = DEFAULT_DIR) -> None:
    p = _paths(base)
    p["checkpoints"].mkdir(parents=True, exist_ok=True)
    if not p["matrix"].exists():
        p["matrix"].write_text(json.dumps({"ids": [], "eval": {}, "train": {}}))


def get_champion(base: Path = DEFAULT_DIR) -> str | None:
    champ = _paths(base)["dir"] / "champion.json"
    if not champ.exists():
        return None
    return json.loads(champ.read_text())["id"]


def set_champion(base: Path, cid: str) -> None:
    init(base)
    (_paths(base)["dir"] / "champion.json").write_text(json.dumps({"id": cid}))


def store(base: Path, cid: str, weights: dict) -> None:
    """Persist a member's weights. Train-matrix entries logged under an
    id describe work-in-progress play, never final strength; the eval
    matrix (promotion, PFSP, Nash) only ever sees frozen weights."""
    (_paths(base)["checkpoints"] / f"{cid}.json").write_text(json.dumps(weights))


def members(base: Path = DEFAULT_DIR) -> list[dict]:
    p = _paths(base)
    if not p["manifest"].exists():
        return []
    return [json.loads(line) for line in p["manifest"].read_text().splitlines() if line.strip()]


def _next_id(base: Path) -> str:
    """Monotonic member id; survives manifest truncation (max + 1)."""
    taken = [
        int(m.group(1))
        for m in (re.fullmatch(r"g(\d+)", m["id"]) for m in members(base))
        if m is not None
    ]
    return f"g{(max(taken) + 1) if taken else 0:03d}"


def save_checkpoint(base: Path, weights: dict, role: str, parent: str | None) -> str:
    """Freeze new population member. Returns its id ("g000", ...)."""
    init(base)
    p = _paths(base)
    cid = _next_id(base)
    store(base, cid, weights)
    with open(p["manifest"], "a") as f:
        f.write(json.dumps({"id": cid, "role": role, "parent": parent}) + "\n")
    return cid


def load_checkpoint(base: Path, cid: str) -> dict:
    return json.loads((_paths(base)["checkpoints"] / f"{cid}.json").read_text())


def record_result(
    base: Path, a: str, b: str, score_a: float, score_b: float, kind: str = "eval"
) -> None:
    """Log a duel: 1/0.5/0 from each side's perspective.

    kind="eval": greedy, canonical, feeds promotion/PFSP/Nash.
    kind="train": exploratory, diagnostic only.
    """
    assert kind in ("eval", "train")
    init(base)
    p = _paths(base)
    data = json.loads(p["matrix"].read_text())
    for cid in (a, b):
        if cid not in data["ids"]:
            data["ids"].append(cid)
    key = f"{a} vs {b}"
    wins = data[kind].get(key, [0.0, 0.0])
    if score_a > score_b:
        wins[0] += 1
    elif score_b > score_a:
        wins[1] += 1
    else:
        wins[0] += 0.5
        wins[1] += 0.5
    data[kind][key] = wins
    p["matrix"].write_text(json.dumps(data))


def log_game(
    base: Path, gen: str, kind: str, a: str, b: str,
    score_a: float, score_b: float, replay: str,
) -> None:
    """Append one game to the dashboard index (replay path archive-relative)."""
    init(base)
    with open(_paths(base)["dir"] / "games.jsonl", "a") as f:
        f.write(json.dumps({
            "gen": gen, "kind": kind, "a": a, "b": b,
            "score_a": score_a, "score_b": score_b, "replay": replay,
        }) + "\n")


def write_status(base: Path, status: dict) -> None:
    """Live progress for the dashboard (overwritten as a generation runs)."""
    init(base)
    (_paths(base)["dir"] / "status.json").write_text(json.dumps(status))


def read_status(base: Path) -> dict:
    path = base / "status.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def list_games(base: Path, member: str | None = None) -> list[dict]:
    """Newest first; optionally only games involving member."""
    path = _paths(base)["dir"] / "games.jsonl"
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    rows.reverse()
    if member is not None:
        rows = [r for r in rows if r["a"] == member or r["b"] == member]
    return rows


def _head_to_head(data: dict, kind: str, a: str, b: str) -> tuple[float, float]:
    """(a's wins, b's wins) across both slot orders, with a +1/+1
    Laplace prior: unplayed reads as 0.5 and small samples shrink to it."""
    w_ab = data[kind].get(f"{a} vs {b}", [0.0, 0.0])
    w_ba = data[kind].get(f"{b} vs {a}", [0.0, 0.0])
    return (w_ab[0] + w_ba[1] + 1.0, w_ab[1] + w_ba[0] + 1.0)


def win_rates(
    base: Path, student: str, kind: str = "eval"
) -> dict[str, float]:
    """Opponent -> opponent's win rate against student (eval matrix)."""
    data = json.loads(_paths(base)["matrix"].read_text())
    rates = {}
    for cid in data["ids"]:
        if cid == student:
            continue
        mine, theirs = _head_to_head(data, kind, student, cid)
        rates[cid] = theirs / (mine + theirs)
    return rates


def sample_opponents(
    base: Path, student: str, k: int, self_play_frac: float = 0.35, seed: int = 0
) -> list[str]:
    """PFSP-lite on the eval matrix: mostly the opponents that beat you,
    some mirror self."""
    rng = np.random.default_rng(seed)
    rates = win_rates(base, student)
    picks = []
    for _ in range(k):
        if rng.random() < self_play_frac or not rates:
            picks.append(student)
        else:
            ids = sorted(rates)
            w = np.array([rates[i] + 0.05 for i in ids])
            picks.append(str(rng.choice(ids, p=w / w.sum())))
    return picks


def payoff_matrix(base: Path, kind: str = "eval") -> tuple[list[str], np.ndarray]:
    """Symmetric zero-sum utility matrix from logged eval duels."""
    data = json.loads(_paths(base)["matrix"].read_text())
    ids = data["ids"]
    n = len(ids)
    mat = np.zeros((n, n))
    for i, a in enumerate(ids):
        for j, b in enumerate(ids):
            if i == j:
                continue
            mine, _theirs = _head_to_head(data, kind, a, b)
            total = mine + _theirs
            mat[i, j] = mine / total - 0.5
    return ids, mat  # diagonal stays 0: self-play is neutral, not a loss


def nash_mixture(base: Path, iters: int = 2000, seed: int = 0) -> dict[str, float]:
    """Nash mass over the population via fictitious play.

    Each side best-responds to the other's historical average; the
    averages converge to equilibrium. Farmers of weaklings get ~zero.
    """
    ids, mat = payoff_matrix(base)
    if not ids:
        return {}
    n = len(ids)
    avg_r = np.full(n, 1.0 / n)
    avg_c = np.full(n, 1.0 / n)
    strat_r = np.zeros(n)
    strat_c = np.zeros(n)
    for _ in range(iters):
        br_r = int(np.argmax(mat @ avg_c))
        br_c = int(np.argmin(avg_r @ mat))
        strat_r[br_r] += 1
        strat_c[br_c] += 1
        avg_r = strat_r / strat_r.sum()
        avg_c = strat_c / strat_c.sum()
    mix = (avg_r + avg_c) / 2
    return {cid: float(mix[i]) for i, cid in enumerate(ids)}


def wilson_lower(wins: float, games: int, z: float = 1.0) -> float:
    """Lower bound on the true win rate (draws pre-counted as half)."""
    if games <= 0:
        return 0.0
    p = wins / games
    denom = 1 + z * z / games
    center = p + z * z / (2 * games)
    spread = z * ((p * (1 - p) + z * z / (4 * games)) / games) ** 0.5
    return (center - spread) / denom
