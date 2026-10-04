"""Bot pool: *.bot manifest identity, directory-code dedup, worktrees.

A bot is a manifest file: any *.bot file under bots/ is a bot, and its
content is the startup command. Historical bots play from git worktrees;
the engine always stays at the workspace tip, so only bot code
time-travels, never the rules.
"""

from __future__ import annotations

import hashlib
import locale
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKBASE = Path("/tmp/antwork")

_GIT_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)


def git_env() -> dict[str, str]:
    """A git hook exports GIT_* variables. A nested git call must not
    inherit them, or it writes to the outer repository's index."""
    env = dict(os.environ)
    for key in _GIT_VARS:
        env.pop(key, None)
    return env


class DirtyTree(Exception):
    """bots/ has uncommitted changes. Records pin committed shas, so
    logged play refuses dirty code: commit or stash first."""


class EngineDiverged(Exception):
    """tools/ differs from branch main. The engine must not change."""


def bot_dirs(root: str | Path = ROOT, commit: str = "HEAD") -> set[str]:
    """Directories holding a manifest at a commit."""
    return {str(Path(b).parent) for b in bots_at(root, commit)}


def is_clean(root: str | Path = ROOT) -> bool:
    """Logged play needs committed code. Dirty = a manifest changed,
    anything changed inside a bot dir, or a new untracked manifest
    (an invisible bot). Everything else never blocks."""
    out = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
        check=True,
        env=git_env(),
    )
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


def engine_on_main(root: str | Path = ROOT) -> bool:
    """The engine that runs must match branch main. A dirty or
    committed change under tools/ stops play until it is restored."""
    diff = subprocess.run(
        ["git", "-C", str(root), "diff", "--quiet", "main", "--", "tools/"],
        capture_output=True,
        env=git_env(),
    )
    if diff.returncode != 0:
        return False
    others = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            "tools/",
        ],
        capture_output=True,
        text=True,
        check=True,
        env=git_env(),
    )
    return not others.stdout.strip()


def main_merged(root: str | Path = ROOT) -> bool:
    """True when branch main is an ancestor of HEAD. The autoresearch
    loop merges main at the start of each iteration."""
    out = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", "main", "HEAD"],
        capture_output=True,
        env=git_env(),
    )
    return out.returncode == 0


def bot_id(path: str, sha: str) -> str:
    return f"{path}-{sha}"


def parse_id(bid: str) -> tuple[str, str]:
    path, sha = bid.rsplit("-", 1)
    return path, sha


def _git(root: str | Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
        env=git_env(),
    )
    return out.stdout


def short(root: str | Path, rev: str) -> str:
    return _git(root, "rev-parse", "--short", rev).strip()


def last_touch(root: str | Path, path: str) -> str:
    """The newest commit that changed a path. A bot's identity must
    not move when unrelated commits land after it."""
    return _git(root, "log", "-1", "--format=%h", "--", path).strip()


def all_commits(root: str | Path = ROOT) -> list[str]:
    """Every commit on branches and tags, oldest first. Detached
    commits and stray worktree HEADs are excluded on purpose:
    unmeasured coder code must never enter the pool as rulers.
    bots_at filters: a commit with no manifest contributes nothing,
    and content-hash dedup collapses commits that leave bot code
    unchanged."""
    seen: set[str] = set()
    commits = []
    for sha in _git(
        root, "log", "--branches", "--tags", "--format=%h", "--reverse"
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
    return sorted(line for line in out.splitlines() if line.endswith(".bot"))


def manifest_text(root: str | Path, commit: str, botfile: str) -> str:
    return _git(root, "show", f"{commit}:{botfile}")


def content_hash(root: str | Path, commit: str, botfile: str) -> str:
    """sha1 over every blob in the manifest's directory, plus the
    manifest's own text. Same dir + same command = one entry; a
    different command (or code) re-hashes; moved copies still dedupe."""
    d = str(Path(botfile).parent)
    out = _git(root, "ls-tree", "-r", commit, "--", f"{d}/")
    blobs = sorted(line.split()[2] for line in out.splitlines() if line.strip())
    body = manifest_text(root, commit, botfile)
    return hashlib.sha1(("\0".join(blobs) + "\0" + body).encode()).hexdigest()[:10]


def choose_canonical(
    specs: list[tuple[str, str]],
    games_of: dict[tuple[str, str], int],
    order: dict[str, int],
) -> tuple[str, str]:
    """Rated entry wins (most games); ties go to the oldest commit."""
    return sorted(specs, key=lambda bs: (-games_of.get(bs, 0), order[bs[1]]))[0]


_POOL_CACHE: dict[
    tuple[str, tuple[str, ...], str],
    tuple[dict[str, int], dict[str, list[tuple[str, str]]]],
] = {}
"""Memoized pool geometry: (root, commits, head) -> (order, hash groups).

Commits are immutable, so the expensive half of pool() — pair discovery
plus content hashes — runs once per process and is reused. Ratings do
change, but they only feed the cheap canonical-choice step, which runs
fresh on every call."""


def _cat_batch(root: str | Path, ids: list[str]) -> dict[str, bytes]:
    """Raw contents for many objects with a single git call."""
    want = list(dict.fromkeys(ids))
    if not want:
        return {}
    proc = subprocess.run(
        ["git", "-C", str(root), "cat-file", "--batch"],
        input=("\n".join(want) + "\n").encode(),
        capture_output=True,
        check=True,
        env=git_env(),
    )
    out = proc.stdout
    res: dict[str, bytes] = {}
    pos = 0
    for _ in want:
        nl = out.index(b"\n", pos)
        sha, _typ, size_s = out[pos:nl].decode("ascii").split()
        size = int(size_s)
        res[sha] = out[nl + 1 : nl + 1 + size]
        pos = nl + 1 + size + 1
    return res


def _parse_tree(buf: bytes) -> list[tuple[str, str, str]]:
    """Tree object bytes -> [(mode, object-sha, name)]."""
    entries: list[tuple[str, str, str]] = []
    pos = 0
    while pos < len(buf):
        sp = buf.index(b" ", pos)
        mode = buf[pos:sp].decode("ascii")
        z = buf.index(b"\x00", sp)
        name = buf[sp + 1 : z].decode("utf-8", "surrogateescape")
        sha = buf[z + 1 : z + 21].hex()
        entries.append((mode, sha, name))
        pos = z + 21
    return entries


def _pool_data(
    root: str | Path,
) -> tuple[dict[str, int], dict[str, list[tuple[str, str]]]]:
    """(order, hash-groups) for pool(), in a handful of git calls.

        One `git log` maps every commit to its tree, a few `git cat-file
        --batch` rounds expand every reachable tree, and one more serves
    every manifest blob. Same pairs and hashes as the naive per-commit
        walk, without the per-commit subprocess storm."""
    commits = all_commits(root)
    head = short(root, "HEAD")
    key = (str(root), tuple(commits), head)
    hit = _POOL_CACHE.get(key)
    if hit is not None:
        return hit
    order = {sha: i for i, sha in enumerate(commits + [head])}
    rev_tree: dict[str, str] = {}
    for line in _git(
        root, "log", "--branches", "--tags", "--format=%H %T %h", "--reverse"
    ).splitlines():
        _full, tree, abbrev = line.split()
        if abbrev not in rev_tree:
            rev_tree[abbrev] = tree
    _head_full, head_tree = _git(root, "log", "-1", "--format=%H %T", "HEAD").split()
    revs = list(dict.fromkeys(commits + [head]))
    trees_of = {r: rev_tree.get(r, head_tree) for r in revs}
    tree_objs: dict[str, list[tuple[str, str, str]]] = {}
    need = set(trees_of.values())
    while True:
        missing = sorted(s for s in need if s not in tree_objs)
        if not missing:
            break
        for sha, buf in _cat_batch(root, missing).items():
            entries = _parse_tree(buf)
            tree_objs[sha] = entries
            for mode, sub, _name in entries:
                if mode in ("040000", "40000"):
                    need.add(sub)
    files_by_tree: dict[str, dict[str, str]] = {}

    def files_at(tree: str) -> dict[str, str]:
        found = files_by_tree.get(tree)
        if found is not None:
            return found
        files: dict[str, str] = {}
        stack = [(tree, "")]
        while stack:
            cur, prefix = stack.pop()
            for mode, sha, name in tree_objs[cur]:
                path = f"{prefix}{name}"
                if mode in ("040000", "40000"):
                    stack.append((sha, path + "/"))
                else:
                    files[path] = sha
        files_by_tree[tree] = files
        return files

    rev_files = {r: files_at(trees_of[r]) for r in revs}
    pairs: list[tuple[str, str]] = []
    for c in commits:
        for b in sorted(p for p in rev_files[c] if p.endswith(".bot")):
            pairs.append((b, c))
    for b in sorted(p for p in rev_files[head] if p.endswith(".bot")):
        pairs.append((b, head))
    encoding = locale.getpreferredencoding(False)
    texts = {
        sha: buf.decode(encoding)
        for sha, buf in _cat_batch(
            root, [rev_files[sha][b] for b, sha in pairs]
        ).items()
    }
    by_hash: dict[str, list[tuple[str, str]]] = {}
    for b, sha in pairs:
        files = rev_files[sha]
        d = str(Path(b).parent)
        if d == ".":
            members = sorted(files.values())
        else:
            prefix = d + "/"
            members = sorted(
                blob for path, blob in files.items() if path.startswith(prefix)
            )
        body = texts[files[b]]
        h = hashlib.sha1(("\0".join(members) + "\0" + body).encode()).hexdigest()[:10]
        by_hash.setdefault(h, []).append((b, sha))
    result = (order, by_hash)
    _POOL_CACHE[key] = result
    return result


def pool(root: str | Path = ROOT, ratings: dict | None = None) -> list[str]:
    order, by_hash = _pool_data(root)
    games_of = {}
    for bid, e in (ratings or {}).items():
        games_of[parse_id(bid)] = e["games"]
    return sorted(
        bot_id(*choose_canonical(specs, games_of, order)) for specs in by_hash.values()
    )


def worktree(root: str | Path, sha: str, workbase: str | Path = WORKBASE) -> Path:
    d = Path(workbase) / f"antwork_{sha}"
    if not (d / ".git").exists():
        subprocess.run(
            ["git", "-C", str(root), "worktree", "add", "--detach", str(d), sha],
            check=True,
            capture_output=True,
            env=git_env(),
        )
    subprocess.run(
        ["git", "-C", str(d), "rev-parse", "--verify", "HEAD"],
        check=True,
        capture_output=True,
        env=git_env(),
    )
    return d


def bot_cmd(root: str | Path, bid: str, workbase: str | Path = WORKBASE) -> str:
    """The manifest's command, verbatim. Empty manifest is an error."""
    path, sha = parse_id(bid)
    cmd = (worktree(root, sha, workbase) / path).read_text().strip()
    if not cmd:
        raise ValueError(f"{bid}: empty command manifest")
    return cmd


def prune_worktrees(
    workbase: str | Path = WORKBASE, max_bytes: int = 1_000_000_000
) -> int:
    """Evict oldest worktrees while the cache exceeds max_bytes.
    Returns bytes freed. Stale admin entries are pruned too."""
    base = Path(workbase)
    if not base.is_dir():
        return 0
    dirs = sorted(
        [d for d in base.iterdir() if d.is_dir()], key=lambda d: d.stat().st_mtime
    )
    sizes = {
        d: sum(p.stat().st_size for p in d.rglob("*") if p.is_file()) for d in dirs
    }
    total = sum(sizes.values())
    freed = 0
    for d in dirs:
        if total <= max_bytes:
            break
        shutil.rmtree(d)
        freed += sizes[d]
        total -= sizes[d]
    subprocess.run(
        ["git", "-C", str(ROOT), "worktree", "prune"],
        check=True,
        capture_output=True,
        env=git_env(),
    )
    return freed


def prune_replays(
    base: str | Path, max_bytes: int, protect: set[str] | None = None
) -> int:
    """Evict oldest entries under a replay store while it exceeds
    max_bytes. Entries are the store's direct children (files or dirs),
    aged by the newest file inside. Paths in protect are never evicted.
    Returns bytes freed."""
    base = Path(base)
    if not base.is_dir():
        return 0
    keep = {str(Path(p)) for p in (protect or set())}

    def size(e: Path) -> int:
        return (
            sum(f.stat().st_size for f in e.rglob("*") if f.is_file())
            if e.is_dir()
            else e.stat().st_size
        )

    def age(e: Path) -> float:
        return (
            max(f.stat().st_mtime for f in e.rglob("*") if f.is_file())
            if e.is_dir()
            else e.stat().st_mtime
        )

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
