"""Bot pool: path+sha identity, content-hash dedup, worktrees."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "league"))


def test_id_roundtrip():
    from pool import bot_id, parse_id
    assert parse_id(bot_id("bots/pas11", "a1c11d2")) == ("bots/pas11", "a1c11d2")


def test_content_hash_stable():
    from pool import content_hash, ROOT
    h1 = content_hash(ROOT, "HEAD", "bots/pas11")
    h2 = content_hash(ROOT, "HEAD", "bots/pas11")
    assert h1 == h2 and len(h1) == 10


def test_content_hash_sees_code_change():
    # pas11 bot file differs from the starter template: hashes differ
    from pool import content_hash, ROOT
    assert content_hash(ROOT, "HEAD", "bots/pas11") != \
        content_hash(ROOT, "HEAD", "bots/py3_starter")


def test_choose_canonical_prefers_rated():
    from pool import choose_canonical
    specs = [("bots/x", "newsha"), ("bots/x", "oldsha")]
    games_of = {("bots/x", "newsha"): 0, ("bots/x", "oldsha"): 5}
    assert choose_canonical(specs, games_of, order={}) == ("bots/x", "oldsha")


def test_choose_canonical_tie_goes_oldest():
    from pool import choose_canonical
    specs = [("bots/x", "newsha"), ("bots/x", "oldsha")]
    order = {"oldsha": 0, "newsha": 1}
    assert choose_canonical(specs, {}, order) == ("bots/x", "oldsha")


def test_pool_lists_repo_bots():
    from pool import pool
    ids = pool()
    assert any(i.startswith("bots/pas11-") for i in ids)
    assert any(i.startswith("bots/py3_starter-") for i in ids)
    assert ids == sorted(ids)


def test_entry_point_discovery():
    from pool import entry_file, ROOT
    assert entry_file(ROOT, "HEAD", "bots/py3_starter").name == "MyBot.py"
    assert entry_file(ROOT, "HEAD", "bots/pas11").name == "Pas11.py"
    # history holds the pre-rename .py3 entry: discovery covers it too
    from pool import pool, parse_id, short, ROOT as _R
    head = short(_R, "HEAD")
    old = next(i for i in pool() if i.startswith("bots/py3_starter-")
               and not i.endswith(head))
    assert entry_file(ROOT, parse_id(old)[1],
                       "bots/py3_starter").name == "MyBot.py3"


def test_worktree_and_cmd_exist():
    from pool import pool, worktree, bot_cmd, parse_id, ROOT
    import sys as _sys
    bid = next(i for i in pool() if i.startswith("bots/py3_starter-"))
    path, sha = parse_id(bid)
    wt = worktree(ROOT, sha)
    assert (wt / path).is_dir()
    py, entry = bot_cmd(ROOT, bid, _sys.executable)
    assert Path(entry).is_file() and Path(py).is_file()
