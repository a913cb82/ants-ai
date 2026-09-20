"""Leaderboard: derived from the games log in one pass. Never stored."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ratings as R
from matchmake import GAMES_LOG, read_log


def table(games: list[dict]) -> list[dict]:
    ratings = R.rebuild(games)
    wins: dict[str, int] = {}
    for g in games:
        wins[g["result"][0]] = wins.get(g["result"][0], 0) + 1
    rows = [{"id": bid, "mu": e["mu"], "sigma": e["sigma"],
             "lb": e["mu"] - 3 * e["sigma"],
             "games": e["games"], "wins": wins.get(bid, 0)}
            for bid, e in ratings.items()]
    return sorted(rows, key=lambda r: -r["lb"])


def render(games: list[dict]) -> None:
    print(f"{'#':>3}  {'bot':36} {'mu':>6} {'sigma':>6} {'lb':>6} "
          f"{'games':>5} {'wins':>4}")
    for i, r in enumerate(table(games), 1):
        print(f"{i:>3}  {r['id']:36} {r['mu']:6.1f} {r['sigma']:6.2f} "
              f"{r['lb']:6.1f} {r['games']:>5} {r['wins']:>4}")


def main(argv=None) -> int:
    render(read_log(GAMES_LOG))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
