"""Bot game-day behavior: records, sampling, weights override, threads.

Split from the test_alphastarzero monolith; no behavior change.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))
sys.path.insert(0, str(ROOT / "ml"))

import features

_C = features.INPUT_CHANNELS
_S = 2 * features.DEFAULT_RADIUS + 1




def test_bot_records_turn_rows_when_env_set(tmp_path, monkeypatch):
    import AlphaAnt

    monkeypatch.setenv("AA_RECORD_DIR", str(tmp_path))

    class StubAnts:
        rows, cols = 10, 10
        viewradius2 = 77

        def my_ants(self):
            return [(4, 4)]

        def enemy_ants(self):
            return []

        def food(self):
            return [(5, 5)]

        def my_hills(self):
            return []

        def enemy_hills(self):
            return []

        def destination(self, loc, d):
            return {"n": (3, 4), "s": (5, 4), "e": (4, 5), "w": (4, 3)}[d]

        def passable(self, loc):
            return True

        def distance(self, a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        def issue_order(self, order):
            pass

        def time_remaining(self):
            return 1000

    bot = AlphaAnt.AlphaAntBot()
    bot.do_setup(StubAnts())
    bot.do_turn(StubAnts())
    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    row = json.loads(files[0].read_text().strip().splitlines()[-1])
    assert row["turn"] == 1
    assert row["action"] in ("n", "e", "s", "w", "stay")
    assert "dest" in row and "legal" in row
    assert features.decode_window(row["window"]).shape[0] == features.INPUT_CHANNELS
    assert features.decode_window(row["window"]).shape[1] == 2 * features.DEFAULT_RADIUS + 1
    assert len(row["legal"]) == 5




def test_bot_weights_path_override(tmp_path):
    import json

    import AlphaAnt
    import model
    import torch

    torch.manual_seed(123)
    alt = tmp_path / "alt.json"
    alt.write_text(json.dumps(model.state_dict_to_lists(model.CNNPolicy())))
    bot = AlphaAnt.AlphaAntBot(weights_path=str(alt))
    assert bot.policy(torch.zeros(1, _C, _S, _S)).shape == (1, 5)




def test_bot_env_is_single_threaded():
    import game_if

    env = game_if._bot_env(game_if.GameConfig(map="m", turns=1, temperature=0.5))
    assert env["OMP_NUM_THREADS"] == "1"
    assert env["MKL_NUM_THREADS"] == "1"
    assert env["OPENBLAS_NUM_THREADS"] == "1"
    assert env["AA_TEMPERATURE"] == "0.5"
    assert env["AA_RECORD_DIR"] == "records"
