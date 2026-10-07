"""Coder starts from exam scores and game ranks.

Usage:
    candidates.py            ranked starts, then dead lines

Rules: the champion (best recorded score) starts first. Other
starts rank by games: first bots that beat the champion, then
bots that beat strong bots. Only the top starts print: the rest
is history.
"""

import json
from pathlib import Path

TOP_N = 6
PAD_GAMES = 9


def _basename(bot: str) -> str:
    """entry name without sha: unique per entry, stable across revs."""
    return bot.split("/")[-1].rsplit("-", 1)[0]


def candidates(
    exams: list[tuple[str, float]],
    games: list[list[str]],
    mu_of: dict[str, float],
) -> dict:
    """Pure pick logic. exams is (bot id, score) in PROGRESS order."""
    champ = max(exams, key=lambda r: r[1])[0] if exams else ""
    champ_names = {_basename(champ)}

    main: dict[str, int] = {}
    seen: dict[str, set[str]] = {}
    played: dict[str, int] = {}
    for result in games:
        names = [_basename(b) for b in result]
        for winner in names:
            played[winner] = played.get(winner, 0) + 1
        for i, winner in enumerate(names):
            for loser in names[i + 1 :]:
                if loser in champ_names:
                    main[winner] = main.get(winner, 0) + 1
                seen.setdefault(winner, set()).add(loser)
    cover = {w: sum(mu_of.get(v, 0.0) for v in vs) for w, vs in seen.items()}
    rate = {
        w: (
            main.get(w, 0) / (played[w] + PAD_GAMES),
            cover.get(w, 0.0) / (played[w] + PAD_GAMES),
        )
        for w in played
    }

    ranked = sorted(
        exams,
        key=lambda r: (
            r[0] != champ,
            -rate.get(_basename(r[0]), (0, 0))[0],
            -rate.get(_basename(r[0]), (0, 0))[1],
        ),
    )
    return {
        "starts": ranked[:TOP_N],
        "champion": champ,
    }


def main(root: Path) -> None:
    exams: list[tuple[str, str, float]] = []
    prog = root / "autoresearch" / "docs" / "PROGRESS.jsonl"
    for line in prog.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict) and ("score" in r or "mu" in r):
            score = r.get("score", r.get("mu"))
            assert isinstance(score, (int, float))
            exams.append((r.get("bot", ""), r.get("budget", ""), float(score)))
    current = exams[-1][1] if exams else ""
    era = [(b, s) for b, budget, s in exams if budget == current]

    games: list[list[str]] = []
    gprog = root / "league" / "games.jsonl"
    for line in gprog.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict) and isinstance(r.get("result"), list):
            games.append([str(b) for b in r["result"]])

    mu_of: dict[str, float] = {}
    rprog = root / "league" / "ratings.json"
    try:
        data = json.loads(rprog.read_text())
    except (OSError, json.JSONDecodeError):
        data = {}
    bots = data.get("bots", data) if isinstance(data, dict) else {}
    for bid, e in bots.items():
        if isinstance(e, dict) and "mu" in e:
            name = _basename(str(bid))
            mu_of[name] = max(mu_of.get(name, e["mu"]), e["mu"])

    out = candidates(era, games, mu_of)
    for bot, score in out["starts"]:
        print(f"start {bot} {round(score, 1)}")


if __name__ == "__main__":
    main(Path(__file__).resolve().parents[1])
