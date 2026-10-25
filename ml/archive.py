"""Population store: frozen checkpoints, payoff matrix, matchmaking.

Everything learned lives here, outside git: checkpoints as weight
lists, one manifest line per member, one payoff entry per duel. From
the matrix come both training-opponent sampling (PFSP-lite: practice
mostly against what beats you, plus mirror self-play) and promotion
ranking (Nash mass over the empirical game, unfarmable by design).
Pure files + numpy; knows nothing about torch or the engine.
"""

from __future__ import annotations

import json
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
        p["matrix"].write_text(json.dumps({"ids": [], "wins": {}}))


def get_champion(base: Path = DEFAULT_DIR) -> str | None:
    champ = _paths(base)["dir"] / "champion.json"
    if not champ.exists():
        return None
    return json.loads(champ.read_text())["id"]


def set_champion(base: Path, cid: str) -> None:
    init(base)
    (_paths(base)["dir"] / "champion.json").write_text(json.dumps({"id": cid}))


def store(base: Path, cid: str, weights: dict) -> None:
    """Overwrite a member's frozen weights (trained challenger)."""
    (_paths(base)["checkpoints"] / f"{cid}.json").write_text(json.dumps(weights))


def members(base: Path = DEFAULT_DIR) -> list[dict]:
    p = _paths(base)
    if not p["manifest"].exists():
        return []
    return [json.loads(line) for line in p["manifest"].read_text().splitlines() if line.strip()]


def save_checkpoint(base: Path, weights: dict, role: str, parent: str | None) -> str:
    """Freeze new population member. Returns its id ("g000", ...)."""
    init(base)
    p = _paths(base)
    n = len(members(base))
    cid = f"g{n:03d}"
    (p["checkpoints"] / f"{cid}.json").write_text(json.dumps(weights))
    with open(p["manifest"], "a") as f:
        f.write(json.dumps({"id": cid, "role": role, "parent": parent}) + "\n")
    return cid


def load_checkpoint(base: Path, cid: str) -> dict:
    return json.loads((_paths(base)["checkpoints"] / f"{cid}.json").read_text())


def record_result(base: Path, a: str, b: str, score_a: float, score_b: float) -> None:
    """Log a duel: 1/0.5/0 from each side's perspective."""
    init(base)
    p = _paths(base)
    data = json.loads(p["matrix"].read_text())
    for cid in (a, b):
        if cid not in data["ids"]:
            data["ids"].append(cid)
    key = f"{a} vs {b}"
    if score_a > score_b:
        data["wins"][key] = data["wins"].get(key, [0.0, 0.0])
        data["wins"][key][0] += 1
    elif score_b > score_a:
        data["wins"][key] = data["wins"].get(key, [0.0, 0.0])
        data["wins"][key][1] += 1
    else:
        data["wins"][key] = data["wins"].get(key, [0.0, 0.0])
        data["wins"][key][0] += 0.5
        data["wins"][key][1] += 0.5
    p["matrix"].write_text(json.dumps(data))


def win_rates(base: Path, student: str) -> dict[str, float]:
    """Opponent -> opponent's win rate against student (unplayed = 0.5)."""
    data = json.loads(_paths(base)["matrix"].read_text())
    rates = {}
    for cid in data["ids"]:
        if cid == student:
            continue
        w_ab = data["wins"].get(f"{student} vs {cid}", [0.0, 0.0])
        w_ba = data["wins"].get(f"{cid} vs {student}", [0.0, 0.0])
        mine = w_ab[0] + w_ba[1]
        theirs = w_ab[1] + w_ba[0]
        total = mine + theirs
        rates[cid] = theirs / total if total else 0.5
    return rates


def sample_opponents(
    base: Path, student: str, k: int, self_play_frac: float = 0.35, seed: int = 0
) -> list[str]:
    """PFSP-lite: mostly the opponents that beat you, some mirror self."""
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


def payoff_matrix(base: Path) -> tuple[list[str], np.ndarray]:
    """Symmetric zero-sum utility matrix from logged duels."""
    data = json.loads(_paths(base)["matrix"].read_text())
    ids = data["ids"]
    n = len(ids)
    mat = np.zeros((n, n))
    for i, a in enumerate(ids):
        for j, b in enumerate(ids):
            if i == j:
                continue
            w_ab = data["wins"].get(f"{a} vs {b}", [0.0, 0.0])
            w_ba = data["wins"].get(f"{b} vs {a}", [0.0, 0.0])
            mine = w_ab[0] + w_ba[1]
            total = mine + w_ab[1] + w_ba[0]
            mat[i, j] = mine / total if total else 0.0
    return ids, mat - 0.5


def nash_mixture(base: Path, iters: int = 2000, seed: int = 0) -> dict[str, float]:
    """Nash mass over the population via fictitious play.

    Each side best-responds to the other's historical average; the
    averages converge to equilibrium. Farmers of weaklings get ~zero.
    """
    ids, mat = payoff_matrix(base)
    if not ids:
        return {}
    rng = np.random.default_rng(seed)
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
