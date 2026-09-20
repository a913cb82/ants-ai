"""Bot pool: *.bot manifest identity, directory-code dedup, worktrees.

A bot is a manifest file: any *.bot file under bots/ is a bot, and its
content is the startup command. Historical bots play from git worktrees;
the engine always stays at the workspace tip, so only bot code
time-travels, never the rules.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKBASE = Path("/tmp/antwork")


class DirtyTree(Exception):
    """bots/ has uncommitted changes. Records pin committed shas, so
    logged play refuses dirty code: commit or stash first."""


def bot_dirs(root: str | Path = ROOT, commit: str = "HEAD") -> set[str]:
    """Directories holding a manifest at a commit."""
    return {str(Path(b).parent) for b in bots_at(root, commit)}


def is_clean(root: str | Path = ROOT) -> bool:
    """Logged play needs committed code. Dirty = a manifest changed,
    anything changed inside a bot dir, or a new untracked manifest
    (an invisible bot). Everything else never blocks."""
    out = subprocess.run(["git", "-C", str(root), "status",
                          "--porcelain", "--untracked-files=all"],
                         capture_output=True, text=True, check=True)
    dirs = bot_dirs(root)
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].split(" -> ")[-1]
        if path.endswith(".bot"):
            return False
        if any(path == d or path.startswith(d + "/") for d in dirs):
            return False
    return True


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


def last_touch(root: str | Path, path: str) -> str:
    """The newest commit that changed a path. A bot's identity must
    not move when unrelated commits land after it."""
    return _git(root, "log", "-1", "--format=%h", "--", path).strip()


def all_commits(root: str | Path = ROOT) -> list[str]:
    """Every commit in the repo, oldest first. bots_at filters: a
    commit with no manifest contributes nothing, and content-hash
    dedup collapses commits that leave bot code unchanged."""
    seen: set[str] = set()
    commits = []
    for sha in _git(root, "log", "--all", "--format=%h", "--reverse"
                    ).split():
        if sha not in seen:
            seen.add(sha)
            commits.append(sha)
    return commits


def bots_at(root: str | Path, commit: str) -> list[str]:
    """Every manifest in the repo at a commit. No manifest = not a bot,
    wherever it would live."""
    try:
        out = _git(root, "ls-tree", "-r", "--name-only", commit)
    except subprocess.CalledProcessError:
        return []
    return sorted(l for l in out.splitlines() if l.endswith(".bot"))


def manifest_text(root: str | Path, commit: str, botfile: str) -> str:
    return _git(root, "show", f"{commit}:{botfile}")


def content_hash(root: str | Path, commit: str, botfile: str) -> str:
    """sha1 over every blob in the manifest's directory, plus the
    manifest's own text. Same dir + same command = one entry; a
    different command (or code) re-hashes; moved copies still dedupe."""
    d = str(Path(botfile).parent)
    out = _git(root, "ls-tree", "-r", commit, "--", f"{d}/")
    blobs = sorted(l.split()[2] for l in out.splitlines() if l.strip())
    body = manifest_text(root, commit, botfile)
    return hashlib.sha1(("\0".join(blobs) + "\0" + body).encode()
                        ).hexdigest()[:10]


def choose_canonical(specs: list[tuple[str, str]],
                     games_of: dict[tuple[str, str], int],
                     order: dict[str, int]) -> tuple[str, str]:
    """Rated entry wins (most games); ties go to the oldest commit."""
    return sorted(specs,
                  key=lambda bs: (-games_of.get(bs, 0),
                                  order[bs[1]]))[0]


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
    games_of = {}
    for bid, e in (ratings or {}).items():
        games_of[parse_id(bid)] = e["games"]
    by_hash: dict[str, list[tuple[str, str]]] = {}
    for b, sha in pairs:
        h = content_hash(root, sha, b)
        by_hash.setdefault(h, []).append((b, sha))
    return sorted(bot_id(*choose_canonical(specs, games_of, order))
                  for specs in by_hash.values())


def worktree(root: str | Path, sha: str,
             workbase: str | Path = WORKBASE) -> Path:
    d = Path(workbase) / f"antwork_{sha}"
    if not (d / ".git").exists():
        subprocess.run(["git", "-C", str(root), "worktree", "add",
                        "--detach", str(d), sha],
                       check=True, capture_output=True)
    subprocess.run(["git", "-C", str(d), "rev-parse", "--verify",
                    "HEAD"], check=True, capture_output=True)
    return d


def bot_cmd(root: str | Path, bid: str,
            workbase: str | Path = WORKBASE) -> str:
    """The manifest's command, verbatim. Empty manifest is an error."""
    path, sha = parse_id(bid)
    cmd = (worktree(root, sha, workbase) / path).read_text().strip()
    if not cmd:
        raise ValueError(f"{bid}: empty command manifest")
    return cmd


def prune_worktrees(workbase: str | Path = WORKBASE,
                    max_bytes: int = 1_000_000_000) -> int:
    """Evict oldest worktrees while the cache exceeds max_bytes.
    Returns bytes freed. Stale admin entries are pruned too."""
    base = Path(workbase)
    if not base.is_dir():
        return 0
    dirs = sorted([d for d in base.iterdir() if d.is_dir()],
                  key=lambda d: d.stat().st_mtime)
    sizes = {d: sum(p.stat().st_size for p in d.rglob("*") if p.is_file())
             for d in dirs}
    total = sum(sizes.values())
    freed = 0
    for d in dirs:
        if total <= max_bytes:
            break
        shutil.rmtree(d)
        freed += sizes[d]
        total -= sizes[d]
    subprocess.run(["git", "-C", str(ROOT), "worktree", "prune"],
                   check=True, capture_output=True)
    return freed


def prune_replays(base: str | Path, max_bytes: int,
                  protect: set[str] | None = None) -> int:
    """Evict oldest entries under a replay store while it exceeds
    max_bytes. Entries are the store's direct children (files or dirs),
    aged by the newest file inside. Paths in protect are never evicted.
    Returns bytes freed."""
    base = Path(base)
    if not base.is_dir():
        return 0
    keep = {str(Path(p)) for p in (protect or set())}

    def size(e: Path) -> int:
        return (sum(f.stat().st_size for f in e.rglob("*") if f.is_file())
                if e.is_dir() else e.stat().st_size)

    def age(e: Path) -> float:
        return (max(f.stat().st_mtime for f in e.rglob("*") if f.is_file())
                if e.is_dir() else e.stat().st_mtime)

    entries = list(base.iterdir())
    sizes = {e: size(e) for e in entries}
    total = sum(sizes.values())
    freed = 0
    for e in sorted(entries, key=age):
        if total <= max_bytes:
            break
        if str(e) in keep:
            continue
        if e.is_dir():
            shutil.rmtree(e)
        else:
            e.unlink()
        freed += sizes[e]
        total -= sizes[e]
    return freed
