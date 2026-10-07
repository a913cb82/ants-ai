"""Valid coder starts from the autoresearch tree.

Usage:
    candidates.py            extend pick, split points, idle pick, dead lines

Rules (PROGRAM.md Tree): dead lines get nothing. Extend takes the
newest scored leaf of the most recently examined live line. Split
branches the parent of a scored failure that already has a child.
Idle takes the oldest unscored leaf of the line with the fewest
children in flight. The champion line never dies.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import log as L

CHAMPION_LINE = "champion"


def _merge_lines(root: Path) -> set[str]:
    """line names from merge tree/<line>-<n> subjects."""
    out: set[str] = set()
    for _, _, subject in L._commits(root):
        if subject.startswith("merge tree/"):
            line = subject[len("merge tree/") :].split(":", 1)[0].rsplit("-", 1)[0]
            out.add(line)
    return out


def _leaf_lines(nodes: list[tuple[str, list[str], str]]) -> dict[str, str]:
    """merged exp sha -> line, from merge second parents."""
    out = {}
    for _, parents, subject in nodes:
        if subject.startswith("merge tree/") and len(parents) > 1:
            line = subject[len("merge tree/") :].split(":", 1)[0].rsplit("-", 1)[0]
            out[parents[1]] = line
    return out


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


def _prefix(bot: str) -> str:
    m = re.match(r"([A-Za-z]+)", bot.split("/bot/")[-1])
    return m.group(1).lower() if m else ""


def candidates(
    nodes: list[tuple[str, list[str], str]],
    exams: list[tuple[str, float]],
    flight: set[str],
    champion: str | None,
    known: set[str],
) -> dict:
    """Pure pick logic. exams is (bot, score) in PROGRESS order."""
    known = known | {CHAMPION_LINE}
    ideas = {s: subj[5:] for s, _, subj in nodes if subj.startswith("exp:")}
    order = [s for s, _, subj in nodes if subj.startswith("exp:")]
    pos = {s: i for i, s in enumerate(reversed(order))}
    parents_of = {s: ps for s, ps, _ in nodes}
    leaf_line = _leaf_lines(nodes)

    seq: dict[str, list[float]] = {ln: [] for ln in known}
    exp_line: dict[str, str] = {}
    score_of: dict[str, float] = {}
    for bot, score in exams:
        short = bot.rsplit("-", 1)[-1] if "-" in bot else ""
        sha = next((s for s in order if short and s.startswith(short)), None)
        if champion and sha == champion:
            ln = CHAMPION_LINE
        elif _prefix(bot) in known:
            ln = _prefix(bot)
        else:
            continue
        seq[ln].append(score)
        if sha is not None:
            exp_line.setdefault(sha, ln)
            score_of[sha] = score
    for sha, ln in leaf_line.items():
        if ln in known:
            exp_line.setdefault(sha, ln)
    if champion and champion in ideas:
        exp_line.setdefault(champion, CHAMPION_LINE)

    def dead(ln: str) -> bool:
        if ln == CHAMPION_LINE:
            return False
        s = [x for x in seq[ln] if x == x]
        return len(s) >= 4 and max(s[-3:]) <= max(s[:-3])

    dead_lines = {ln for ln in known if dead(ln)}
    live = {ln for ln in known if ln not in dead_lines}

    by_line: dict[str, list[str]] = {ln: [] for ln in live}
    for sha, ln in exp_line.items():
        if ln in live:
            by_line[ln].append(sha)
    for ln in by_line:
        by_line[ln].sort(key=lambda s: pos.get(s, -1))

    def examined(sha: str) -> bool:
        return sha in score_of

    avail: dict[str, str] = {}
    for ln in live:
        cands = [s for s in reversed(by_line[ln]) if examined(s)]
        if cands and cands[0] not in flight:
            avail[ln] = cands[0]
    extend = None
    if avail:
        last_exam: dict[str, int] = {}
        for i, (bot, _) in enumerate(exams):
            short = bot.rsplit("-", 1)[-1] if "-" in bot else ""
            sha = next((s for s in order if short and s.startswith(short)), None)
            if sha in exp_line and exp_line[sha] in live:
                last_exam[exp_line[sha]] = i
        pick = max(avail, key=lambda ln: last_exam.get(ln, -1))
        extend = (avail[pick], pick)

    best = {ln: max(seq[ln]) for ln in live if seq[ln]}
    split = []
    for ln in live:
        for i, sha in enumerate(by_line[ln]):
            if not examined(sha):
                continue
            later = by_line[ln][i + 1 :]
            if score_of[sha] < best[ln] and (later or sha in flight):
                ps = parents_of.get(sha, [])
                split.append((sha, ln, ps[0] if ps else ""))

    unscored = [
        sha
        for ln in live
        for sha in by_line[ln]
        if not examined(sha) and sha not in flight
    ]
    flying: dict[str, int] = dict.fromkeys(live, 0)
    for sha in flight:
        if sha in exp_line and exp_line[sha] in flying:
            flying[exp_line[sha]] += 1
    idle = None
    if unscored:
        pick = min(unscored, key=lambda s: (flying[exp_line[s]], pos.get(s, 0)))
        idle = (pick, exp_line[pick])
    return {
        "extend": extend,
        "split": split,
        "idle": idle,
        "dead": sorted(dead_lines),
        "ideas": ideas,
    }


def main(root: Path) -> None:
    nodes = L._commits(root)
    exams: list[tuple[str, float]] = []
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
            exams.append((r.get("bot", ""), float(score)))
    try:
        champion = (
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
    out = candidates(nodes, exams, flight, champion, _merge_lines(root))
    if out["extend"]:
        sha, ln = out["extend"]
        print(f"extend {sha[:7]} {ln} {out['ideas'].get(sha, '')}")
    else:
        print("extend: none")
    for sha, ln, parent in out["split"]:
        print(f"split {sha[:7]} {ln} from {parent[:7]}")
    if out["idle"]:
        sha, ln = out["idle"]
        print(f"idle {sha[:7]} {ln} {out['ideas'].get(sha, '')}")
    for ln in out["dead"]:
        print(f"dead {ln}")


if __name__ == "__main__":
    main(Path(__file__).resolve().parents[1])
