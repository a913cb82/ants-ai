"""Tests for autoresearch/log.py: git is the log."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import log as L


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args], capture_output=True, check=True, cwd=cwd
    ).stdout.decode()
    return out.strip()


def _fixture(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "autoresearch" / "docs").mkdir(parents=True)
    _git(root, "init", "-q")
    _git(
        root,
        "-c",
        "user.email=t@t",
        "-c",
        "user.name=t",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "init",
    )
    _git(
        root,
        "-c",
        "user.email=t@t",
        "-c",
        "user.name=t",
        "checkout",
        "-qb",
        "autoresearch/main",
    )
    _git(
        root,
        "-c",
        "user.email=t@t",
        "-c",
        "user.name=t",
        "checkout",
        "-qb",
        "tree/tables-1",
    )
    _git(
        root,
        "-c",
        "user.email=t@t",
        "-c",
        "user.name=t",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "exp: tables",
    )
    leaf = _git(root, "rev-parse", "HEAD")
    _git(
        root,
        "-c",
        "user.email=t@t",
        "-c",
        "user.name=t",
        "checkout",
        "-q",
        "autoresearch/main",
    )
    _git(
        root,
        "-c",
        "user.email=t@t",
        "-c",
        "user.name=t",
        "merge",
        "-q",
        "--no-ff",
        "tree/tables-1",
        "-m",
        "merge tree/tables-1: tables",
    )
    _git(root, "branch", "-D", "tree/tables-1")
    rows = [
        {"bot": f"autoresearch/bot/Tables.bot-{leaf[:7]}", "mu": 55.5, "score": 55.5},
    ]
    prog = root / "autoresearch" / "docs" / "PROGRESS.jsonl"
    prog.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return root


def test_frontier_empty_when_leaf_examined(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    assert L.frontier(root) == []


def test_show_reports_idea_and_score(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    leaf = _git(root, "rev-parse", "autoresearch/main^2")
    info = L.show(root, leaf)
    assert info["idea"] == "tables"
    assert info["score"] == 55.5


def test_lines_groups_by_merge_message(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    assert L.lines(root) == {"tables": 1}


def test_check_msg_accepts_known_kinds(tmp_path: Path) -> None:
    for subject in [
        "exp: tables",
        "log: tables win",
        "merge tree/tables-1: tables",
        "docs: trim",
        "fix: blank line",
        "port: xathis",
    ]:
        msg = tmp_path / "msg"
        msg.write_text(subject + "\n\nbody\n")
        assert L.check_msg(msg), subject


def test_check_msg_rejects_unknown_kind(tmp_path: Path) -> None:
    msg = tmp_path / "msg"
    msg.write_text("wip stuff\n")
    assert not L.check_msg(msg)


def test_scores_skips_corrupt_lines(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    prog = root / "autoresearch" / "docs" / "PROGRESS.jsonl"
    with prog.open("a") as fh:
        fh.write("not json\n")
        fh.write("[1, 2]\n")
        fh.write("\n")
    assert L.best(root)["score"] == 55.5


def test_show_unknown_sha_reports_error(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    assert L.show(root, "deadbee")["error"] == "unknown revision"


def test_check_msg_rejects_empty_file(tmp_path: Path) -> None:
    msg = tmp_path / "msg"
    msg.write_text("")
    assert not L.check_msg(msg)
