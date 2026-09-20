"""Bot pool: <path>-<sha> identity, content-hash dedup, worktrees.

Historical bots play from git worktrees; the engine always stays at the
workspace tip, so only bot code time-travels, never the rules.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKBASE = Path("/tmp/antwork")


class DirtyTree(Exception):
    """bots/ has uncommitted changes. Records pin committed shas, so
    logged play refuses dirty code: commit or stash first."""


def is_clean(root: str | Path = ROOT) -> bool:
    out = subprocess.run(["git", "-C", str(root), "status",
                          "--porcelain", "--", "bots/"],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip() == ""


def bot_id(path: str, sha: str) -> str:
    return f"{path}-{sha}"


def parse_id(bid: str) -> tuple[str, str]:
    path, sha = bid.rsplit("-", 1)
    return path, sha


def _git(root: str | Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(root), *args],
                         capture_output=True, text=True, check=True)
    return out.stdout


def short(root: str | Path, rev: str) -> str:
    return _git(root, "rev-parse", "--short", rev).strip()


def all_commits(root: str | Path = ROOT) -> list[str]:
    seen: set[str] = set()
    commits = []
    for sha in _git(root, "log", "--all", "--format=%h", "--reverse",
                    "--", "bots/").split():
        if sha not in seen:
            seen.add(sha)
            commits.append(sha)
    return commits


def bots_at(root: str | Path, commit: str) -> list[str]:
    """Bot dirs at a commit: dirs directly under bots/ holding .py files."""
    try:
        out = _git(root, "ls-tree", "-r", "--name-only", commit, "--", "bots/")
    except subprocess.CalledProcessError:
        return []
    names = set()
    for line in out.splitlines():
        parts = line.split("/")
        if len(parts) == 3 and (parts[2].endswith(".py")
                                or parts[2].endswith(".py3")):
            names.add(f"{parts[0]}/{parts[1]}")
    return sorted(names)


def entry_file(root: str | Path, commit: str, botdir: str) -> Path:
    """The runnable file: the single top-level .py that is not ants.py.
    Resolved from the worktree checkout (same bytes git would list,
    without a racy post-add ls-tree in the main repo)."""
    wt = worktree(root, short(root, commit))
    cands = sorted(p.name for p in (wt / botdir).glob("*.py*")
                   if p.is_file() and p.suffix in (".py", ".py3")
                   and p.name != "ants.py")
    if len(cands) != 1:
        raise ValueError(f"{botdir}@{commit}: want 1 entry, see {cands}")
    return Path(botdir) / cands[0]


def content_hash(root: str | Path, commit: str, botdir: str) -> str:
    """sha1 over the bot dir's git blob shas. Identical code = one entry,
    wherever it lived in history."""
    out = _git(root, "ls-tree", "-r", commit, "--", f"{botdir}/")
    blobs = sorted(l.split()[2] for l in out.splitlines() if l.strip())
    return hashlib.sha1("".join(blobs).encode()).hexdigest()[:10]


def choose_canonical(specs: list[tuple[str, str]],
                     games_of: dict[tuple[str, str], int],
                     order: dict[str, int]) -> tuple[str, str]:
    """Rated entry wins (most games); ties go to the oldest commit."""
    return sorted(specs,
                  key=lambda bs: (-games_of.get(bs, 0),
                                  order.get(bs[1], 10 ** 9)))[0]


def pool(root: str | Path = ROOT, ratings: dict | None = None) -> list[str]:
    commits = all_commits(root)
    pairs: list[tuple[str, str]] = []
    for c in commits:
        for b in bots_at(root, c):
            pairs.append((b, c))
    head = short(root, "HEAD")
    for b in bots_at(root, "HEAD"):
        pairs.append((b, head))
    order = {sha: i for i, sha in enumerate(commits + [head])}
    games_of = {(b.rsplit("-", 1)[0], b.rsplit("-", 1)[1]): e.get("games", 0)
                for b, e in (ratings or {}).items()
                if "-" in b}
    by_hash: dict[str, list[tuple[str, str]]] = {}
    for b, sha in pairs:
        try:
            h = content_hash(root, sha, b)
        except subprocess.CalledProcessError:
            continue
        by_hash.setdefault(f"{b}@{h}", []).append((b, sha))
    return sorted(bot_id(*choose_canonical(specs, games_of, order))
                  for specs in by_hash.values())


def worktree(root: str | Path, sha: str) -> Path:
    d = WORKBASE / f"antwork_{sha}"
    if not (d / "bots").is_dir():
        subprocess.run(["git", "-C", str(root), "worktree", "add",
                        "--detach", str(d), sha],
                       check=True, capture_output=True)
    # Validate the new admin dir before use (and warm up later reads).
    subprocess.run(["git", "-C", str(d), "rev-parse", "--verify",
                    "HEAD"], check=True, capture_output=True)
    return d


def bot_cmd(root: str | Path, bid: str, python: str) -> tuple[str, str]:
    """(interpreter, entry) as absolute paths. Absolute: the engine runs
    each bot from its own dir, where relative paths do not resolve."""
    from pathlib import Path as _P
    path, sha = parse_id(bid)
    wt = worktree(root, sha)
    entry = wt / entry_file(root, sha, path)
    return (str(_P(python).resolve()), str(entry.resolve()))
