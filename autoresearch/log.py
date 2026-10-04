"""Explore the autoresearch tree. Git is the log.

Usage:
    log.py frontier        merged exp leaves with no exam row yet
    log.py show <sha>      idea, parents, score for one node
    log.py lines           merge count per line
    log.py best            best recorded score and its bot
"""

import json
import subprocess
import sys
from pathlib import Path

BRANCH = "autoresearch/main"


def _git(root: Path, *args: str) -> str:
    return (
        subprocess.run(["git", *args], capture_output=True, check=True, cwd=root)
        .stdout.decode()
        .strip()
    )


def _commits(root: Path) -> list[tuple[str, list[str], str]]:
    out = _git(root, "log", BRANCH, "--format=%H %P %s")
    rows: list[tuple[str, list[str], str]] = []
    for line in out.splitlines():
        toks = line.split(" ")
        sha = toks[0]
        parents = [
            t
            for t in toks[1:]
            if len(t) == 40 and all(c in "0123456789abcdef" for c in t)
        ]
        subject = " ".join(toks[1 + len(parents) :])
        rows.append((sha, parents, subject))
    return rows


def _scores(root: Path) -> dict[str, dict]:
    prog = root / "autoresearch" / "docs" / "PROGRESS.jsonl"
    scores: dict[str, dict] = {}
    if not prog.exists():
        return scores
    for line in prog.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        bid = row.get("bot", "")
        short = bid.rsplit("-", 1)[-1] if "-" in bid else ""
        if short:
            scores[short] = row
    return scores


def _examined(root: Path) -> set[str]:
    scores = _scores(root)
    shas = {sha for sha, _, _ in _commits(root)}
    return {sha for sha in shas if any(sha.startswith(s) for s in scores)}


def frontier(root: Path) -> list[dict]:
    commits = _commits(root)
    children = {p for _, parents, _ in commits for p in parents}
    done = _examined(root)
    out = []
    for sha, _parents, subject in commits:
        if not subject.startswith("exp:"):
            continue
        if sha in children or sha in done:
            continue
        out.append({"sha": sha, "idea": subject[5:]})
    return out


def show(root: Path, sha: str) -> dict:
    try:
        full = _git(root, "rev-parse", sha)
    except subprocess.CalledProcessError:
        return {"sha": sha, "error": "unknown revision"}
    subjects = {s: (p, subj) for s, p, subj in _commits(root)}
    parents, subject = subjects[full]
    idea = subject[5:] if subject.startswith("exp: ") else subject
    scores = _scores(root)
    score = next((r for s, r in scores.items() if full.startswith(s)), {})
    return {"sha": full, "idea": idea, "parents": parents, "score": score.get("score")}


def lines(root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _, _, subject in _commits(root):
        if not subject.startswith("merge tree/"):
            continue
        line = subject[len("merge tree/") :].split(":", 1)[0]
        line = line.rsplit("-", 1)[0]
        counts[line] = counts.get(line, 0) + 1
    return counts


def best(root: Path) -> dict:
    rows = [r for r in _scores(root).values() if "score" in r]
    return max(rows, key=lambda r: r["score"]) if rows else {}


KINDS = {"exp", "log", "merge", "docs", "fix", "fmt", "port", "perf", "chore", "test"}


def check_msg(path: Path) -> bool:
    """True when the commit subject starts with a known kind."""
    lines = path.read_text().splitlines()
    if not lines or not lines[0].strip():
        return False
    subject = lines[0].strip().lower()
    return subject.split(" ", 1)[0].rstrip(":") in KINDS


def main(argv: list[str]) -> None:
    root = Path(__file__).resolve().parents[1]
    cmd = argv[1] if len(argv) > 1 else "frontier"
    if cmd == "frontier":
        for leaf in frontier(root):
            print(f"{leaf['sha'][:7]} {leaf['idea']}")
    elif cmd == "show":
        print(json.dumps(show(root, argv[2]), indent=1))
    elif cmd == "lines":
        for line, n in sorted(lines(root).items()):
            print(f"{line} {n}")
    elif cmd == "best":
        print(json.dumps(best(root), indent=1))
    elif cmd == "check-msg":
        ok = check_msg(Path(argv[2]))
        if not ok:
            print(f"bad subject; start with one of {sorted(KINDS)}")
        raise SystemExit(0 if ok else 1)
    else:
        raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    main(sys.argv)
