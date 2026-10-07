"""Scorer queue from pool and exam rows.

Usage:
    candidate_scorer.py      count of unscored bots, then the oldest

An autoresearch bot is unscored when no PROGRESS row names it.
Oldest means earliest birth commit among its pool revisions.
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from league.pool import pool


def _basename(bot: str) -> str:
    """entry name without sha: unique per entry, stable across revs."""
    return bot.split("/")[-1].rsplit("-", 1)[0]


def _rev(bot: str) -> str:
    return bot.rsplit("-", 1)[-1] if "-" in bot else ""


def unscored(pool_ids: list[str], scored: set[str]) -> list[str]:
    """pool ids under autoresearch/bot/ with no exam row."""
    return [
        b
        for b in pool_ids
        if b.startswith("autoresearch/bot/") and _basename(b) not in scored
    ]


def group_by_code(pairs: list[tuple[str, str]]) -> dict[str, list[str]]:
    """bot ids by code blob: same file contents means same bot."""
    out: dict[str, list[str]] = {}
    for bid, blob in pairs:
        out.setdefault(blob, []).append(bid)
    return out


def code_blobs(root: Path, revs: list[str]) -> dict[str, dict[str, str]]:
    """rev -> {filename: blob} for the bot dir, one git call per rev."""
    out: dict[str, dict[str, str]] = {}
    for rev in dict.fromkeys(r for r in revs if r):
        log = subprocess.run(
            ["git", "ls-tree", "-r", rev, "--", "autoresearch/bot/"],
            capture_output=True,
            check=True,
            cwd=root,
        ).stdout.decode()
        blobs = {}
        for line in log.splitlines():
            parts = line.split()
            if len(parts) == 4:
                blobs[parts[3].split("/")[-1]] = parts[2]
        out[rev] = blobs
    return out


def births(root: Path, revs: list[str]) -> dict[str, str]:
    """input rev -> committer date, one git call."""
    out: dict[str, str] = {}
    revs = [r for r in revs if r]
    if not revs:
        return out
    log = subprocess.run(
        ["git", "log", "--no-walk", "--format=%H %cI"] + revs,
        capture_output=True,
        check=True,
        cwd=root,
    ).stdout.decode()
    fulls = [line.split(" ", 1) for line in log.splitlines() if line.strip()]
    for rev in revs:
        for sha, date in fulls:
            if sha.startswith(rev):
                out[rev] = date
                break
    return out


def oldest(pool_ids: list[str], birth_of: dict[str, str]) -> str:
    """id with earliest birth date; ties keep pool order."""
    dated = [(birth_of.get(_rev(b), ""), i, b) for i, b in enumerate(pool_ids)]
    dated = [(d, i, b) for d, i, b in dated if d]
    if not dated:
        return pool_ids[0] if pool_ids else ""
    return min(dated)[2]


def main(root: Path) -> None:
    scored: set[str] = set()
    prog = root / "autoresearch" / "docs" / "PROGRESS.jsonl"
    for line in prog.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict) and "bot" in r:
            scored.add(_basename(str(r["bot"])))
    queue = unscored(pool(root), scored)
    revs = [_rev(b) for b in queue]
    blobs = code_blobs(root, revs)
    pairs = []
    for b in queue:
        code = _basename(b)[:-4] + ".py"
        pairs.append((b, blobs.get(_rev(b), {}).get(code, "MISSING:" + b)))
    groups = group_by_code(pairs)
    print(len(groups))
    if groups:
        birth_of = births(root, revs)
        dated = {_rev(b): birth_of.get(_rev(b), "") for b in queue}

        def born(ids: list[str]) -> str:
            dates = [dated.get(_rev(b), "") for b in ids]
            dates = [d for d in dates if d]
            return min(dates) if dates else "~~"

        first = min(groups.values(), key=born)
        print(oldest(first, dated))


if __name__ == "__main__":
    main(Path(__file__).resolve().parents[1])
