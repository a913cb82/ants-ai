"""Pool: *.bot manifest identity, directory-code dedup, worktrees."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "league"))


def make_repo(path: Path, layout: dict[str, str]) -> Path:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"], check=True)
    for rel, content in layout.items():
        p = path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "bots"], check=True)
    return path


def test_id_roundtrip():
    from pool import bot_id, parse_id

    assert parse_id(bot_id("bots/pas11/main.bot", "a1c11d2")) == (
        "bots/pas11/main.bot",
        "a1c11d2",
    )


def test_dir_without_manifest_is_not_a_bot(tmp_path):
    from pool import pool

    r = make_repo(tmp_path / "r", {"bots/naked/Bot.py": "x\n"})
    assert pool(r) == []


def test_manifest_makes_a_bot(tmp_path):
    from pool import pool

    r = make_repo(
        tmp_path / "r", {"bots/a/main.bot": "python A.py\n", "bots/a/A.py": "x\n"}
    )
    assert len(pool(r)) == 1 and pool(r)[0].startswith("bots/a/main.bot-")


def test_two_manifests_one_dir_are_two_bots(tmp_path):
    from pool import pool

    r = make_repo(
        tmp_path / "r",
        {
            "bots/a/slow.bot": "python A.py --slow\n",
            "bots/a/fast.bot": "python A.py --fast\n",
            "bots/a/A.py": "x\n",
        },
    )
    ids = pool(r)
    assert len(ids) == 2
    assert {i.split("-")[0] for i in ids} == {"bots/a/slow.bot", "bots/a/fast.bot"}


def test_identical_dup_manifests_collapse(tmp_path):
    from pool import pool

    r = make_repo(
        tmp_path / "r",
        {
            "bots/a/one.bot": "python A.py\n",
            "bots/a/two.bot": "python A.py\n",
            "bots/a/A.py": "x\n",
        },
    )
    assert len(pool(r)) == 1


def test_code_change_rehashes(tmp_path):
    from pool import content_hash

    r = make_repo(
        tmp_path / "r", {"bots/a/main.bot": "python A.py\n", "bots/a/A.py": "x = 1\n"}
    )
    before = content_hash(r, "HEAD", "bots/a/main.bot")
    (r / "bots" / "a" / "A.py").write_text("x = 2\n")
    subprocess.run(["git", "-C", str(r), "commit", "-qam", "tweak"], check=True)
    assert content_hash(r, "HEAD", "bots/a/main.bot") != before


def test_choose_canonical_prefers_rated():
    from pool import choose_canonical

    specs = [("bots/x/main.bot", "newsha"), ("bots/x/main.bot", "oldsha")]
    games_of = {("bots/x/main.bot", "newsha"): 0, ("bots/x/main.bot", "oldsha"): 5}
    order = {"newsha": 1, "oldsha": 0}
    assert choose_canonical(specs, games_of, order) == ("bots/x/main.bot", "oldsha")


def test_choose_canonical_tie_goes_oldest():
    from pool import choose_canonical

    specs = [("bots/x/main.bot", "newsha"), ("bots/x/main.bot", "oldsha")]
    order = {"oldsha": 0, "newsha": 1}
    assert choose_canonical(specs, {}, order) == ("bots/x/main.bot", "oldsha")


def test_command_text_is_verbatim(tmp_path):
    from pool import bot_cmd, pool

    r = make_repo(
        tmp_path / "r", {"bots/a/main.bot": "python A.py --x 1\n", "bots/a/A.py": "x\n"}
    )
    assert bot_cmd(r, pool(r)[0], workbase=tmp_path / "work") == "python A.py --x 1"


def test_nested_manifests_found(tmp_path):
    from pool import pool

    r = make_repo(
        tmp_path / "r", {"tools/sample/x.bot": "run x\n", "tools/sample/x.py": "x\n"}
    )
    assert len(pool(r)) == 1
    assert pool(r)[0].startswith("tools/sample/x.bot-")


def test_unknown_sha_is_loud_tmp(tmp_path):
    import pytest
    from pool import bot_cmd

    r = make_repo(
        tmp_path / "r", {"bots/a/main.bot": "python A.py\n", "bots/a/A.py": "x\n"}
    )
    with pytest.raises(subprocess.CalledProcessError):
        bot_cmd(r, "bots/a/main.bot-deadbee", workbase=tmp_path / "work")


def test_prune_replays_evicts_oldest_over_cap(tmp_path):
    import os

    from pool import prune_replays

    base = tmp_path / "replays"
    (base / "old").mkdir(parents=True)
    (base / "old" / "0.replay").write_text("x" * 100)
    (base / "new").mkdir()
    (base / "new" / "0.replay").write_text("x" * 100)
    os.utime(base / "old" / "0.replay", (1, 1))
    os.utime(base / "new" / "0.replay", (2, 2))
    freed = prune_replays(base, max_bytes=150)
    assert freed == 100
    assert not (base / "old").exists()
    assert (base / "new").exists()


def test_prune_replays_protects_paths(tmp_path):
    from pool import prune_replays

    base = tmp_path / "replays"
    (base / "old").mkdir(parents=True)
    (base / "old" / "0.replay").write_text("x" * 100)
    freed = prune_replays(base, max_bytes=0, protect={str(base / "old")})
    assert freed == 0 and (base / "old").exists()


def test_prune_replays_missing_store_is_zero(tmp_path):
    from pool import prune_replays

    assert prune_replays(tmp_path / "nope", max_bytes=0) == 0


def test_last_touch_ignores_later_commits(tmp_path):
    from pool import last_touch

    r = make_repo(
        tmp_path / "r", {"bots/a/main.bot": "python A.py\n", "bots/a/A.py": "x\n"}
    )
    first = subprocess.run(
        ["git", "-C", str(r), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    (r / "README.md").write_text("hi\n")
    subprocess.run(["git", "-C", str(r), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(r), "commit", "-qm", "docs"], check=True)
    assert last_touch(r, "bots/a") == first
