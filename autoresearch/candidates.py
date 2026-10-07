"""Coder starts from the autoresearch tree.

Usage:
    candidates.py            ranked starts, unscored queue, dead lines

Rules: the champion is a start. Other starts rank by games:
first bots that beat the champion, then bots that beat strong
bots. Dead lines get nothing. No bot gets two coders at once.
Only the top starts print: the rest is history.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import log as L

CHAMPION_LINE = "champion"
TOP_N = 6


def _flight(root: Path, shas: set[str]) -> set[str]:
    """nodes with a child on a live tree/* branch."""
    out: set[str] = set()
    branches = subprocess.run(
        ["git", "branch", "--list", "tree/*", "--format=%(refname:short)"],
        capture_output=True,
        check=True,
        cwd=root,
    ).stdout.decode()
    for br in branches.split():
        log = subprocess.run(
            ["git", "log", f"{L.BRANCH}..{br}", "--format=%H %P"],
            capture_output=True,
            check=True,
            cwd=root,
        ).stdout.decode()
        rows = [r.split(" ") for r in log.splitlines() if r.strip()]
        if rows:
            out.update(p for p in rows[-1][1:] if p in shas)
    return out


def _basename(bot: str) -> str:
    """entry name without sha: unique per entry, stable across revs."""
    return bot.split("/")[-1].rsplit("-", 1)[0]


def _prefix(bot: str) -> str:
    m = re.match(r"([A-Za-z]+)", bot.split("/bot/")[-1])
    return m.group(1).lower() if m else ""


def _leafs(nodes: list[tuple[str, list[str], str]]) -> set[str]:
    """exp shas merged as tree/<line>-<n> second parents."""
    out: set[str] = set()
    for _, parents, subject in nodes:
        if subject.startswith("merge tree/") and len(parents) > 1:
            out.add(parents[1])
    return out


def candidates(
    nodes: list[tuple[str, list[str], str]],
    exams: list[tuple[str, float]],
    flight: set[str],
    champion: str | None,
    games: list[list[str]],
    mu_of: dict[str, float],
) -> dict:
    """Pure pick logic. exams is (bot, score) in PROGRESS order."""
    ideas = {s: subj[5:] for s, _, subj in nodes if subj.startswith("exp:")}
    order = [s for s, _, subj in nodes if subj.startswith("exp:")]
    leafs = _leafs(nodes)

    name_of: dict[str, str] = {}
    seq: dict[str, list[float]] = {}
    champ_names: set[str] = set()
    for bot, score in exams:
        short = bot.rsplit("-", 1)[-1] if "-" in bot else ""
        sha = next((s for s in order if short and s.startswith(short)), None)
        name = _basename(bot)
        if champion and sha == champion:
            ln, champ = CHAMPION_LINE, True
        else:
            ln, champ = _prefix(bot), False
        if champ:
            champ_names.add(name)
        seq.setdefault(ln, []).append(score)
        if sha is not None:
            name_of.setdefault(sha, name)

    def dead(ln: str) -> bool:
        if ln == CHAMPION_LINE:
            return False
        s = seq.get(ln, [])
        return len(s) >= 4 and max(s[-3:]) <= max(s[:-3])

    dead_lines = {ln for ln in seq if dead(ln)}

    scored: dict[str, tuple[str, str]] = {}
    for bot, _ in exams:
        short = bot.rsplit("-", 1)[-1] if "-" in bot else ""
        sha = next((s for s in order if short and s.startswith(short)), None)
        if sha is None or sha in flight:
            continue
        ln = CHAMPION_LINE if champion and sha == champion else _prefix(bot)
        if ln in dead_lines:
            continue
        scored[sha] = (ln, _basename(bot))

    main: dict[str, int] = {}
    seen: dict[str, set[str]] = {}
    for result in games:
        names = [_basename(b) for b in result]
        for i, winner in enumerate(names):
            for loser in names[i + 1 :]:
                if loser in champ_names:
                    main[winner] = main.get(winner, 0) + 1
                seen.setdefault(winner, set()).add(loser)
    cover = {w: sum(mu_of.get(v, 0.0) for v in vs) for w, vs in seen.items()}

    champ_sha = champion if champion in order else None
    ranked = sorted(
        scored,
        key=lambda s: (
            s != champ_sha,
            -main.get(name_of.get(s, ""), 0),
            -cover.get(name_of.get(s, ""), 0.0),
        ),
    )
    unscored = [
        s for s in reversed(order) if s in leafs and s not in scored and s not in flight
    ]
    return {
        "starts": [(s, name_of.get(s, "")) for s in ranked],
        "unscored": [(s, ideas[s]) for s in unscored],
        "dead": sorted(dead_lines),
        "ideas": ideas,
    }


def _mu(root: Path) -> dict[str, float]:
    """live mu per entry basename, ports included."""
    out: dict[str, float] = {}
    prog = root / "league" / "ratings.json"
    if not prog.exists():
        return out
    try:
        data = json.loads(prog.read_text())
    except json.JSONDecodeError:
        return out
    bots = data.get("bots", data) if isinstance(data, dict) else {}
    for bid, e in bots.items():
        if isinstance(e, dict) and "mu" in e:
            name = _basename(str(bid))
            out[name] = max(out.get(name, e["mu"]), e["mu"])
    return out


def _games(root: Path) -> list[list[str]]:
    """rank-ordered result lists, winner first."""
    out: list[list[str]] = []
    prog = root / "league" / "games.jsonl"
    if not prog.exists():
        return out
    for line in prog.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict) and isinstance(r.get("result"), list):
            out.append([str(b) for b in r["result"]])
    return out


def main(root: Path) -> None:
    nodes = L._commits(root)
    exams: list[tuple[str, str, float]] = []
    prog = root / "autoresearch" / "docs" / "PROGRESS.jsonl"
    for line in prog.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict) and ("score" in r or "mu" in r):
            score = r.get("score", r.get("mu"))
            assert isinstance(score, (int, float))
            exams.append((r.get("bot", ""), r.get("budget", ""), float(score)))
    try:
        champion: str | None = (
            subprocess.run(
                ["git", "rev-parse", "champion/main"],
                capture_output=True,
                check=True,
                cwd=root,
            )
            .stdout.decode()
            .strip()
        )
    except subprocess.CalledProcessError:
        champion = None
    flight = _flight(root, {s for s, _, _ in nodes})
    current = exams[-1][1] if exams else ""
    era = [(b, s) for b, budget, s in exams if budget == current]
    out = candidates(nodes, era, flight, champion, _games(root), _mu(root))
    for sha, name in out["starts"][:TOP_N]:
        print(f"start {sha[:7]} {name} {out['ideas'].get(sha, '')}")
    for sha, idea in out["unscored"][:TOP_N]:
        print(f"unscored {sha[:7]} {idea}")
    for ln in out["dead"]:
        print(f"dead {ln}")


if __name__ == "__main__":
    main(Path(__file__).resolve().parents[1])
