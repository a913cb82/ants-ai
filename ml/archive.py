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
import os
import re
import tempfile
import threading
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


def atomic_write_json(path: Path, obj: object) -> None:
    """Write JSON atomically: readers see old-or-new, never torn."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(obj))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def set_champion(base: Path, cid: str) -> None:
    init(base)
    atomic_write_json(_paths(base)["dir"] / "champion.json", {"id": cid})


def last_exploiter(base: Path = DEFAULT_DIR, line: int = 0) -> str | None:
    """Most recent exploiter id on the given line, or None.

    Two rival lines alternate exploiter gens (line A even counts,
    line B odd). Entries without a line key are legacy line A.
    The persistent rival chains from its own line's tip (weights +
    optimizer), developing its own style over many gens."""
    for m in reversed(members(base)):
        if m.get("role") in ("exploiter", "spoiler") \
                and m.get("line", 0) == line:
            return m["id"]
    return None


def get_main(base: Path = DEFAULT_DIR) -> str | None:
    main = _paths(base)["dir"] / "main.json"
    if not main.exists():
        return None
    return json.loads(main.read_text())["id"]


def set_main(base: Path, cid: str) -> None:
    init(base)
    atomic_write_json(_paths(base)["dir"] / "main.json", {"id": cid})


def save_opt(base: Path, cid: str, blob: dict) -> None:
    """Persist a member's optimizer state next to its weights."""
    init(base)
    atomic_write_json(_paths(base)["checkpoints"] / f"{cid}.opt.json", blob)


def load_opt(base: Path, cid: str) -> dict | None:
    p = _paths(base)["checkpoints"] / f"{cid}.opt.json"
    if not p.exists():
        return None
    try:
        blob = json.loads(p.read_text())
    except ValueError:
        return None
    return blob if isinstance(blob, dict) else None


def store(base: Path, cid: str, weights: dict) -> None:
    """Persist a member's weights. Train-matrix entries logged under an
    id describe work-in-progress play, never final strength; the eval
    matrix (promotion, PFSP, Nash) only ever sees frozen weights."""
    atomic_write_json(_paths(base)["checkpoints"] / f"{cid}.json", weights)


def members(base: Path = DEFAULT_DIR) -> list[dict]:
    """Manifest entries; skips malformed lines (one bad line must not
    brick the page)."""
    p = _paths(base)
    if not p["manifest"].exists():
        return []
    return read_jsonl(
        p["manifest"],
        lambda row: isinstance(row, dict) and isinstance(row.get("id"), str),
    )


def _next_id(base: Path) -> str:
    """Monotonic member id; survives manifest truncation (max + 1)."""
    taken = [
        int(m.group(1))
        for m in (re.fullmatch(r"g(\d+)", m["id"]) for m in members(base))
        if m is not None
    ]
    return f"g{(max(taken) + 1) if taken else 0:03d}"


def save_checkpoint(base: Path, weights: dict, role: str, parent: str | None,
                    line: int | None = None) -> str:
    """Freeze new population member. Returns its id ("g000", ...)."""
    init(base)
    p = _paths(base)
    cid = _next_id(base)
    store(base, cid, weights)
    row = {"id": cid, "role": role, "parent": parent}
    if line is not None:
        row["line"] = line
    with open(p["manifest"], "a") as f:
        f.write(json.dumps(row) + "\n")
    return cid


def load_checkpoint(base: Path, cid: str) -> dict:
    return json.loads((_paths(base)["checkpoints"] / f"{cid}.json").read_text())


def append_jsonl(path: Path, row: dict) -> None:
    """One JSON line appended. Shared by games index and history log."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(row) + "\n")


def read_jsonl(path: Path, valid) -> list[dict]:
    """Tolerant line reader: skips blanks, bad JSON, rejected rows."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if valid(row):
            out.append(row)
    return out


def _key(a: str, b: str) -> str:
    """Single constructor for matchup keys (built here, parsed nowhere:
    _head_to_head derives both orders from one key)."""
    return f"{a} vs {b}"


def prune_missing(base: Path, ids: list[str], probs) -> tuple[list[str], object]:
    """Drop mixture members whose weights are gone, renormalize."""
    keep = []
    for i, p in zip(ids, probs):
        try:
            load_checkpoint(base, i)
        except (FileNotFoundError, ValueError, KeyError):
            continue
        keep.append((i, float(p)))
    if not keep:
        return [], np.array([])
    names = [i for i, _ in keep]
    w = np.array([p for _, p in keep])
    return names, w / w.sum() if w.sum() > 0 else np.ones(len(names)) / len(names)


def mixture_draw(ids: list[str], probs, k: int, rng, exclude: tuple = ()) -> list[str]:
    """Draw k opponents with replacement from a FIXED mixture.

    The mixture is computed ONCE per generation (nash_mixture over a
    1700-member matrix costs ~40s); per-game sampling must be pure
    arithmetic, never I/O. Renormalizes over members minus exclude;
    degenerate (all-zero) mass falls back to even-split. Deterministic
    in the caller's rng."""
    elig = [(i, p) for i, p in zip(ids, probs) if i not in exclude]
    if k <= 0 or not elig:
        return []
    names = [i for i, _ in elig]
    w = np.array([p for _, p in elig], dtype=float)
    if w.sum() <= 0:
        w = np.ones(len(names))
    w = w / w.sum()
    picks = []
    for _ in range(k):
        if rng.random() <= 0.0 or w.sum() <= 0.0:
            picks.append(names[0])
        else:
            picks.append(str(rng.choice(names, p=w)))
    return picks


def outcome_of(score_a: float, score_b: float) -> float:
    """Duel outcome from A's view: 1.0 win, 0.5 draw, 0.0 loss.

    Single constructor for the score->outcome mapping (B3: it used to
    live in three places with three spellings)."""
    if score_a > score_b:
        return 1.0
    if score_b > score_a:
        return 0.0
    return 0.5


_write_lock = threading.Lock()


def record_result(
    base: Path, a: str, b: str, score_a: float, score_b: float, kind: str = "eval"
) -> None:
    """Log a duel: 1/0.5/0 from each side's perspective.

    kind="eval": greedy, canonical, feeds promotion/PFSP/Nash and
    registers population members. kind="train": exploratory,
    diagnostic only (logged under keys, never as members).
    """
    assert kind in ("eval", "train")
    init(base)
    with _write_lock:  # games run in a thread pool; keep read-modify-write safe
        p = _paths(base)
        data = json.loads(p["matrix"].read_text())
        if kind == "eval":
            for cid in (a, b):
                if cid not in data["ids"]:
                    data["ids"].append(cid)
        key = _key(a, b)
        wins = data[kind].get(key, [0.0, 0.0])
        out = outcome_of(score_a, score_b)
        wins[0] += out
        wins[1] += 1.0 - out
        data[kind][key] = wins
        atomic_write_json(p["matrix"], data)


def next_drill_maps(base: Path, pool: list, n: int, gen_num: int) -> list:
    """Round-robin drill reservation: the n least-recently-trained boards.

    Game index alone pins training to the first few maps once the pool
    outgrows games-per-gen. This guarantees every board trains at least
    once per ceil(len(pool)/n) gens however large the pool grows
    (rung-3 ready). Ties break by pool order, so small pools sweep
    exactly like the old gen-rotation."""
    init(base)
    path = _paths(base)["dir"] / "drills.json"
    try:
        last = json.loads(path.read_text())
    except (OSError, ValueError):
        last = {}
    order = {m: i for i, m in enumerate(pool)}
    ranked = sorted(pool, key=lambda m: (last.get(m, -1), order[m]))
    chosen = [ranked[i % len(ranked)] for i in range(max(n, 0))] if ranked else []
    for m in ranked[:n]:
        last[m] = gen_num
    atomic_write_json(path, last)
    return chosen


def log_game(
    base: Path, gen: str, kind: str, a: str, b: str,
    score_a: float, score_b: float, replay: str, map: str | None = None,
    game: str | None = None,
) -> None:
    """Append one game to the dashboard index (replay path archive-relative).

    One row is logged per seat-pair, so an N-player game yields N*(N-1)/2
    rows sharing one `game` id ("<outdir>#<token>", one play, one id).
    Rows logged before the id existed carry None and group by replay path."""
    init(base)
    append_jsonl(_paths(base)["dir"] / "games.jsonl", {
        "gen": gen, "kind": kind, "a": a, "b": b,
        "score_a": score_a, "score_b": score_b, "replay": replay,
        "map": map, "game": game,
    })


def write_status(base: Path, status: dict) -> None:
    """Live progress for the dashboard (overwritten as a generation runs)."""
    init(base)
    atomic_write_json(_paths(base)["dir"] / "status.json", status)


def read_status(base: Path) -> dict:
    path = base / "status.json"
    if not path.exists():
        return {}
    try:
        row = json.loads(path.read_text())
    except ValueError:
        return {}
    return row if isinstance(row, dict) else {}


def _game_row(row: object) -> bool:
    required = {"gen", "kind", "a", "b", "score_a", "score_b", "replay"}
    return (
        isinstance(row, dict)
        and required <= set(row)
        and isinstance(row["score_a"], (int, float))
        and isinstance(row["score_b"], (int, float))
    )


def list_games(base: Path, member: str | None = None) -> list[dict]:
    """Newest first; optionally only games involving member.

    Skips malformed lines/rows: one bad line must not brick the page."""
    rows = read_jsonl(_paths(base)["dir"] / "games.jsonl", _game_row)
    rows.reverse()
    if member is not None:
        rows = [r for r in rows if r["a"] == member or r["b"] == member]
    return rows


def _head_to_head(data: dict, kind: str, a: str, b: str) -> tuple[float, float]:
    """(a's wins, b's wins) across both slot orders, with a +1/+1
    Laplace prior: unplayed reads as 0.5 and small samples shrink to it."""
    w_ab = data[kind].get(_key(a, b), [0.0, 0.0])
    w_ba = data[kind].get(_key(b, a), [0.0, 0.0])
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
    if not np.any(mat):
        return {cid: round(1.0 / n, 4) for cid in ids}  # all draws: split evenly
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


# ---------------------------------------------------------------------------
# Continuous league (phase 2 of ml/runs/plan-league.md). ADDITIVE section:
# nothing above this line is modified by the league work; training math
# stays byte-identical. Going-forward manifest roles, league.json
# scheduler state, anchor.jsonl measurement rows, and pool game counts
# for the PFSP newcomer boost (sampling itself lives in ml/pfsp.py).
# ---------------------------------------------------------------------------

#: Going-forward manifest roles for the continuous league. The pre-league
#: population keeps its legacy roles untouched; new snapshots append with
#: one of these.
ROLE_MAIN_SNAPSHOT = "main-snapshot"
ROLE_ME = "me"
ROLE_LE = "le"
ROLE_ADMITTED = "admitted"

#: The valid roles for save_league_snapshot (a tuple, so error messages
#: read deterministically).
LEAGUE_ROLES = (ROLE_MAIN_SNAPSHOT, ROLE_ME, ROLE_LE, ROLE_ADMITTED)

#: Deterministic round-robin training order: equal shares (25% each).
SCHEDULER_ORDER = ("main", "me", "le-a", "le-b")

#: Micro-batch PPO cadence: one update per N own-games per learner.
MICRO_BATCH_SIZE = 8

#: Admission/stall bookkeeping: last-N window vs the role target.
WINDOW_SIZE = 40

#: Default live-exploiter slots (ME + two independent LEs).
DEFAULT_EXPLOITERS = ("me", "le-a", "le-b")


def save_league_snapshot(base: Path, weights: dict, role: str,
                         parent: str | None) -> str:
    """Freeze a league snapshot: thin wrapper reusing save_checkpoint.

    Only going-forward league roles are accepted; anything else raises
    ValueError before touching disk. Returns the new member id."""
    if role not in LEAGUE_ROLES:
        raise ValueError(f"save_league_snapshot: bad role {role!r}; "
                         f"expected one of {list(LEAGUE_ROLES)}")
    return save_checkpoint(base, weights, role, parent)


def save_named_snapshot(base: Path, member_id: str, weights: dict, role: str,
                        parent: str | None, line: int | None = None) -> str:
    """Freeze a league snapshot under a caller-supplied family id.

    Same role validation + store + manifest-append as save_checkpoint,
    but the id is caller-supplied (universe naming: mainN snapshots,
    meN/le-aN/le-bN admissions, 0-based). Raises ValueError for a
    bad role or when the id is already in the manifest. The g-allocator
    (_next_id) is untouched: named ids never consume g-numbers."""
    if role not in LEAGUE_ROLES:
        raise ValueError(f"save_named_snapshot: bad role {role!r}; "
                         f"expected one of {list(LEAGUE_ROLES)}")
    init(base)
    taken = {m.get("id") for m in members(base)
             if isinstance(m.get("id"), str)}
    if member_id in taken:
        raise ValueError(f"save_named_snapshot: id {member_id!r} "
                         f"already in manifest")
    store(base, member_id, weights)
    row: dict = {"id": member_id, "role": role, "parent": parent}
    if line is not None:
        row["line"] = line
    with open(_paths(base)["manifest"], "a") as f:
        f.write(json.dumps(row) + "\n")
    return member_id


def append_member(base: Path, member_id: str, role: str,
                  parent: str | None) -> str:
    """Manifest-only member row (no weights file).

    For live slot ids (bare names whose weights live in live-state
    files, never frozen). Raises ValueError on duplicate id, mirroring
    save_named_snapshot so manifest ids stay unique.
    """
    init(base)
    taken = {m.get("id") for m in members(base)
             if isinstance(m.get("id"), str)}
    if member_id in taken:
        raise ValueError(f"append_member: id {member_id!r} "
                         f"already in manifest")
    row = {"id": member_id, "role": role, "parent": parent}
    with open(_paths(base)["manifest"], "a") as f:
        f.write(json.dumps(row) + "\n")
    return member_id


def _league_path(base: Path) -> Path:
    return base / "league.json"


def _anchor_path(base: Path) -> Path:
    return base / "anchor.jsonl"


def _default_exploiter(target: str) -> dict:
    return {"id": None, "games": 0, "window": [], "target": target}


def init_league(base: Path, main_id: str, anchors: list[str],
                exploiters: tuple = DEFAULT_EXPLOITERS) -> dict:
    """Create league.json: main working id, micro-batch progress,
    per-exploiter {id, games, last-40 window vs target}, anchors list,
    empty admissions, scheduler position, snapshot counter.

    ME tracks the live main; LEs track the pool. Atomically written."""
    init(base)
    state = {
        "main_id": main_id,
        "micro_batch_progress": 0,
        "micro_batch_size": MICRO_BATCH_SIZE,
        "exploiters": {
            name: _default_exploiter(
                main_id if name == "me" else "pool")
            for name in exploiters
        },
        "anchors": list(anchors),
        "admissions": [],
        "resets": [],
        "scheduler_pos": 0,
        "snapshot_counter": 0,
    }
    atomic_write_json(_league_path(base), state)
    return state


def load_league(base: Path) -> dict | None:
    """Read league.json; None when absent or corrupt (never bricks)."""
    path = _league_path(base)
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text())
    except ValueError:
        return None
    return state if isinstance(state, dict) else None


def save_league(base: Path, state: dict) -> None:
    """Atomically rewrite league.json (temp + rename, old-or-new)."""
    init(base)
    atomic_write_json(_league_path(base), state)


def _require_league(base: Path) -> dict:
    state = load_league(base)
    if state is None:
        raise FileNotFoundError(f"no league.json under {base}")
    return state


def record_admission(base: Path, member_id: str, role: str, at_game: int,
                     record: str) -> dict:
    """Append an admissions entry {id, role, at_game, record}.

    Returns the entry. Raises FileNotFoundError without league.json."""
    state = _require_league(base)
    entry = {"id": member_id, "role": role,
             "at_game": at_game, "record": record}
    state.setdefault("admissions", []).append(entry)
    save_league(base, state)
    return entry


def note_reset(base: Path, slot: str, seat: str, game_no: int,
               tick: int) -> dict:
    """Append a reset-log entry {slot, seat, game, tick}.

    seat + game_no identify the reset-triggering game
    (games/{seat}/train{game_no}), so the Elo pass can cut the slot's
    theta exactly after it. Resets are append-only; the log is the
    record-severance mechanism replacing incarnation ids. Raises
    FileNotFoundError without league.json."""
    state = _require_league(base)
    entry = {"slot": slot, "seat": seat, "game": game_no,
             "tick": tick}
    state.setdefault("resets", []).append(entry)
    save_league(base, state)
    return entry


def current_learner(state: dict, order: tuple = SCHEDULER_ORDER) -> str:
    """Learner due at this scheduler position (pure, no I/O)."""
    return order[state["scheduler_pos"] % len(order)]


def advance_scheduler(base: Path, order: tuple = SCHEDULER_ORDER) -> str:
    """Step the round-robin scheduler one tick; returns the next learner.

    Raises FileNotFoundError without league.json."""
    state = _require_league(base)
    state["scheduler_pos"] = (state.get("scheduler_pos", 0) + 1) % len(order)
    save_league(base, state)
    return current_learner(state, order)


def note_exploiter_game(base: Path, name: str, outcome: float,
                        target: str | None = None,
                        member_id: str | None = None) -> dict:
    """Log one exploiter own-game: games +1, outcome onto the last-40
    window vs its target. Creates the slot if missing. Returns the
    updated exploiter entry. Raises FileNotFoundError without league.json."""
    state = _require_league(base)
    exp = state.setdefault("exploiters", {}).setdefault(
        name, _default_exploiter(target if target is not None else "pool"))
    if target is not None:
        exp["target"] = target
    if member_id is not None:
        exp["id"] = member_id
    exp["games"] = exp.get("games", 0) + 1
    window = exp.setdefault("window", [])
    window.append(outcome)
    del window[:-WINDOW_SIZE]
    save_league(base, state)
    return exp


def note_micro_batch(base: Path, games: int = 1) -> int:
    """Advance micro-batch progress by `games` own-games; returns the new
    progress. Raises FileNotFoundError without league.json."""
    state = _require_league(base)
    state["micro_batch_progress"] = state.get("micro_batch_progress", 0) + games
    save_league(base, state)
    return state["micro_batch_progress"]


def _anchor_row(row: object) -> bool:
    required = {"snapshot_id", "main_id", "anchor_id",
                "wins", "losses", "draws"}
    return (
        isinstance(row, dict)
        and required <= set(row)
        and isinstance(row["wins"], (int, float))
        and isinstance(row["losses"], (int, float))
        and isinstance(row["draws"], (int, float))
    )


def record_anchor(base: Path, snapshot_id: str, main_id: str, anchor_id: str,
                  wins: int, losses: int, draws: int) -> dict:
    """Append one anchor measurement row (anchor games carry no gradient).
    Returns the row."""
    row = {"snapshot_id": snapshot_id, "main_id": main_id,
           "anchor_id": anchor_id, "wins": wins,
           "losses": losses, "draws": draws}
    append_jsonl(_anchor_path(base), row)
    return row


def list_anchors(base: Path, snapshot_id: str | None = None,
                 anchor_id: str | None = None) -> list[dict]:
    """Anchor measurement rows; optionally filtered. Skips malformed
    lines/rows: one bad line must not brick the page."""
    rows = read_jsonl(_anchor_path(base), _anchor_row)
    if snapshot_id is not None:
        rows = [r for r in rows if r["snapshot_id"] == snapshot_id]
    if anchor_id is not None:
        rows = [r for r in rows if r["anchor_id"] == anchor_id]
    return rows


def member_game_counts(base: Path, kind: str = "eval") -> dict[str, float]:
    """Member id -> total games in the matrix (both slot orders summed).

    Feeds the PFSP newcomer boost (members with <10 total games get x5
    weight until evaluated). Covers every manifest member (0 when
    unplayed) plus any matrix-only ids. Reads the eval matrix: the same
    canonical record the rest of matchmaking reads."""
    data = json.loads(_paths(base)["matrix"].read_text())
    counts: dict[str, float] = {m["id"]: 0 for m in members(base)
                                if isinstance(m.get("id"), str)}
    for mid in data.get("ids", []):
        counts.setdefault(mid, 0)
    for key, wins in data.get(kind, {}).items():
        try:
            total = float(wins[0]) + float(wins[1])
        except (TypeError, IndexError, ValueError):
            continue
        a, b = key.split(" vs ", 1) if " vs " in key else (None, None)
        if a is None:
            continue
        for mid in (a, b):
            counts[mid] = counts.get(mid, 0) + total
    return counts
