"""Dirty-tree guard lives in pool; play refuses to log dirty code."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "league"))


def make_repo(path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@t"],
                   check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"],
                   check=True)
    (path / "bots" / "a").mkdir(parents=True)
    (path / "bots" / "a" / "main.bot").write_text("python A.py\n")
    (path / "bots" / "a" / "A.py").write_text("x = 1\n")
    (path / "bots" / "a" / "ants.py").write_text("y = 2\n")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "bot"],
                   check=True)
    return path


def test_clean_tree_passes(tmp_path):
    from pool import is_clean
    assert is_clean(make_repo(tmp_path / "r")) is True


def test_modified_bot_fails(tmp_path):
    from pool import is_clean
    r = make_repo(tmp_path / "r")
    (r / "bots" / "a" / "A.py").write_text("x = 2\n")
    assert is_clean(r) is False


def test_untracked_dir_without_manifest_is_clean(tmp_path):
    # no manifest, invisible to the pool: harmless
    from pool import is_clean
    r = make_repo(tmp_path / "r")
    (r / "bots" / "b").mkdir()
    (r / "bots" / "b" / "B.py").write_text("z = 3\n")
    assert is_clean(r) is True


def test_untracked_manifest_elsewhere_blocks(tmp_path):
    from pool import is_clean
    r = make_repo(tmp_path / "r")
    (r / "tools" / "x").mkdir(parents=True)
    (r / "tools" / "x" / "y.bot").write_text("run\n")
    assert is_clean(r) is False


def test_new_code_in_bot_dir_blocks(tmp_path):
    from pool import is_clean
    r = make_repo(tmp_path / "r")
    (r / "bots" / "a" / "New.py").write_text("n = 1\n")
    assert is_clean(r) is False


def test_unrelated_untracked_file_is_clean(tmp_path):
    from pool import is_clean
    r = make_repo(tmp_path / "r")
    (r / "notes.txt").write_text("hi\n")
    assert is_clean(r) is True


def test_unrelated_tracked_dirt_is_clean(tmp_path):
    from pool import is_clean
    r = make_repo(tmp_path / "r")
    (r / "README.md").write_text("docs\n")
    assert is_clean(r) is True
