"""Placement strategy. Optimise select_next_game."""

import math
from dataclasses import dataclass
from statistics import NormalDist


@dataclass
class Rating:
    mu: float
    sigma: float


def _established(ratings: list[Rating], k: int, exclude: int = 0) -> list[int]:
    """Recent low-sigma tertile (last 400), or full pool if too few."""
    end = max(0, len(ratings) - exclude)
    start = max(0, end - 400)
    if end <= start:
        end = len(ratings)
        start = max(0, end - 400)
    recent = ratings[start:end]
    cutoff = sorted(r.sigma for r in recent)[len(recent) // 3]
    pool = [c for c in range(start, end) if ratings[c].sigma <= cutoff]
    if len(pool) < k:
        pool = list(range(len(ratings)))
    return pool


def _census(ratings: list[Rating], k: int, mode: str = "range") -> list[int]:
    """Nearest ruler to sites spanning the pool: uniform range, deciles, or sinh-warp."""
    if mode == "quantile":
        pool = sorted(r.mu for r in ratings)
        n = len(pool)
        sites = [pool[min(int(n * (j + 1) / (k + 1)), n - 1)] for j in range(k)]
    else:
        lo = min(r.mu for r in ratings)
        hi = max(r.mu for r in ratings)
        if hi - lo < 1e-9:
            return list(range(min(k, len(ratings))))
        if mode == "sinh":
            mid, half = (lo + hi) / 2, (hi - lo) / 2
            w = 1.5
            s = math.sinh(w)
            sites = [
                mid + half * math.sinh(w * (2 * (j + 1) / (k + 1) - 1)) / s
                for j in range(k)
            ]
        elif mode == "bell":
            import statistics as _st

            med = _st.median(r.mu for r in ratings)
            sd = _st.pstdev([r.mu for r in ratings]) or (hi - lo) / 6 or 1.0
            bell = NormalDist(med, sd)
            sites = [
                min(max(bell.inv_cdf((j + 1) / (k + 1)), lo), hi) for j in range(k)
            ]
        else:
            sites = [lo + (hi - lo) * (j + 1) / (k + 1) for j in range(k)]
    picked: list[int] = []
    used: set[int] = set()
    for t in sites:
        i = min(
            (c for c in range(len(ratings)) if c not in used),
            key=lambda c: (abs(ratings[c].mu - t), ratings[c].sigma, c),
        )
        used.add(i)
        picked.append(i)
    return picked


def _topdecile(bot: Rating, ratings: list[Rating], k: int) -> list[int]:
    """k rulers from top mu decile, established-first, stronger-fill."""
    tert = _established(ratings, k, 0)
    sub = tert if len(tert) >= k else list(range(len(ratings)))
    mus = sorted(ratings[c].mu for c in sub)
    cut = mus[min(int(len(mus) * 0.9), len(mus) - 1)]
    picked = [c for c in sub if ratings[c].mu >= cut]
    picked.sort(key=lambda c: (abs(ratings[c].mu - cut), ratings[c].sigma, c))
    used = set(picked[:k])
    out = picked[:k]
    if len(out) < k:
        strong = sorted(
            (c for c in sub if c not in used and ratings[c].mu >= bot.mu),
            key=lambda c: (ratings[c].mu - bot.mu, ratings[c].sigma, c),
        )
        out += strong[: k - len(out)]
        used.update(out)
    if len(out) < k:
        rest = sorted(
            (c for c in sub if c not in used),
            key=lambda c: (abs(ratings[c].mu - bot.mu), ratings[c].sigma, c),
        )
        out += rest[: k - len(out)]
    return out[:k]


def _closest(bot: Rating, ratings: list[Rating]) -> int:
    """Pool index nearest bot.mu, low sigma then low index on ties."""
    return min(
        range(len(ratings)),
        key=lambda i: (abs(ratings[i].mu - bot.mu), ratings[i].sigma, i),
    )


def _spread(
    bot: Rating,
    ratings: list[Rating],
    k: int,
    width: float = 1.0,
    anchors: bool = True,
    halo: bool = False,
    kick: bool = False,
    recenter: bool = False,
    antipodal: bool = False,
    mirror: bool = False,
    cohort: bool = False,
    survey: bool = False,
    derby: bool = False,
    homeaway: bool = False,
    crew: int = -1,
    moveout: bool = False,
    checksum: bool = False,
    rewarp: bool = False,
    disjoint_shares: bool = False,
    antiwindup: bool = False,
    senior: bool = False,
) -> list[int]:
    """k distinct opponents nearest quantiles of N(mu, w*sigma)."""
    center = bot.mu
    if kick and ratings:
        mid = (min(r.mu for r in ratings) + max(r.mu for r in ratings)) / 2
        center = bot.mu + 0.5 * (bot.mu - mid)
    if recenter and ratings and k >= 1:
        landing = _spread(bot, ratings, k, 1.25)
        mus = sorted(ratings[i].mu for i in landing)
        center = mus[len(mus) // 2]
    dist = NormalDist(center, max(width * bot.sigma, 0.5))
    disjoint: set[int] = set()
    if rewarp:
        w = 1.5
        s = math.sinh(w)
        targets = [
            dist.inv_cdf(0.5 + math.sinh(w * (2 * (j + 1) / (k + 1) - 1)) / (2 * s))
            for j in range(k)
        ]
    elif checksum:
        g2 = _spread(bot, ratings, k, 1.25)
        disjoint = set(g2)
        mid_q = (k // 2 + 1) / (k + 1)
        targets = [
            dist.inv_cdf((j + 1) / (k + 1))
            for j in range(k)
            if (j + 1) / (k + 1) != mid_q
        ]
        targets.append(dist.inv_cdf(0.5))
    elif derby:
        lo = min(r.mu for r in ratings)
        hi = max(r.mu for r in ratings)
        sites = [lo + (hi - lo) * f for f in (0.25, 0.50, 0.75)]
        targets = (sites + [dist.inv_cdf((j + 1) / 7) for j in range(6)])[:k]
    elif halo and k >= 3:
        outer = NormalDist(center, max(2.5 * bot.sigma, 0.5))
        targets = (
            [outer.inv_cdf(1 / (k + 1))]
            + [dist.inv_cdf((j + 1) / (k + 1)) for j in range(1, k - 1)]
            + [outer.inv_cdf(k / (k + 1))]
        )
    else:
        targets = [dist.inv_cdf((j + 1) / (k + 1)) for j in range(k)]
    pool = (
        _established(ratings, k, 25 if senior else 0)
        if anchors
        else list(range(len(ratings)))
    )
    if antiwindup and ratings:
        plo = min(r.mu for r in ratings)
        phi = max(r.mu for r in ratings)
        targets = [min(max(t, plo), phi) for t in targets]
    if disjoint_shares:
        g2 = _spread(bot, ratings, k, 1.25)
        other = [c for c in pool if c not in set(g2)]
        if len(other) >= k:
            pool = other
    if moveout:
        g2 = _spread(bot, ratings, k, 1.25)
        near = sorted(
            g2, key=lambda i: (abs(ratings[i].mu - bot.mu), ratings[i].sigma, i)
        )[:3]
        keep = [i for i in near if i in pool]
        used5 = set(keep)
        out: list[int] = list(keep)
        for t in targets[:6]:
            cands = [c for c in pool if c not in used5]
            if not cands:
                break
            i = min(
                cands,
                key=lambda c: (abs(ratings[c].mu - t), ratings[c].sigma, c),
            )
            used5.add(i)
            out.append(i)
        return out
    if crew >= 0:
        ordered = sorted(pool, key=lambda c: (ratings[c].mu, ratings[c].sigma, c))
        half = [c for j, c in enumerate(ordered) if j % 2 == crew]
        if len(half) >= k:
            pool = half
    if homeaway:
        fresh_cut = max(0, len(ratings) - 50)
        away = [c for c in pool if c >= fresh_cut]
        home = [c for c in pool if c < fresh_cut]
        if home and away:
            picked4: list[int] = []
            used4: set[int] = set()
            for j, t in enumerate(targets):
                first, second = (home, away) if j % 2 == 0 else (away, home)
                cands = [c for c in first if c not in used4] or [
                    c for c in second if c not in used4
                ]
                i = min(
                    cands,
                    key=lambda c: (abs(ratings[c].mu - t), ratings[c].sigma, c),
                )
                used4.add(i)
                picked4.append(i)
            return picked4
    if survey:
        start = max(0, len(ratings) - 400)
        cands = sorted(
            range(start, len(ratings)),
            key=lambda c: (ratings[c].sigma, c),
        )
        return cands[:k]
    if cohort and pool:
        by_arrival = sorted(pool)
        n3 = len(by_arrival) // 3
        crews = [
            by_arrival[:n3],
            by_arrival[n3 : 2 * n3],
            by_arrival[2 * n3 :],
        ]
        groups = [targets[i::3] for i in range(3)]
        picked3: list[int] = []
        used3: set[int] = set()
        for crew, grp in [(crews[i], groups[i]) for i in range(3)]:
            for t in grp:
                cands = [c for c in crew if c not in used3] or [
                    c for c in pool if c not in used3
                ]
                i = min(
                    cands,
                    key=lambda c: (abs(ratings[c].mu - t), ratings[c].sigma, c),
                )
                used3.add(i)
                picked3.append(i)
        return picked3
    if mirror:
        g2 = _spread(bot, ratings, k, 1.25)
        order = sorted(g2, key=lambda i: -abs(ratings[i].mu - bot.mu))
        picked2: list[int] = []
        used2: set[int] = set()
        for g in order:
            mag = abs(ratings[g].mu - bot.mu)
            sgn = 1 if ratings[g].mu >= bot.mu else -1
            side = [
                c
                for c in pool
                if c not in used2 and (ratings[c].mu - bot.mu) * sgn <= 0
            ]
            cands = side or [c for c in pool if c not in used2]
            i = min(
                cands,
                key=lambda c: (
                    abs(abs(ratings[c].mu - bot.mu) - mag),
                    ratings[c].sigma,
                    c,
                ),
            )
            used2.add(i)
            picked2.append(i)
        return picked2
    ref: list[float] = []
    if antipodal:
        ref = [ratings[i].mu for i in _spread(bot, ratings, k, 1.25)]
    picked: list[int] = []
    used: set[int] = set()
    for n_t, t in enumerate(targets):
        ban = disjoint if checksum and n_t == len(targets) - 1 else set()
        live = [c for c in pool if c not in used and c not in ban] or [
            c for c in pool if c not in used
        ]
        if antipodal and ref:
            i = min(
                live,
                key=lambda c: (
                    -min(abs(ratings[c].mu - m) for m in ref),
                    abs(ratings[c].mu - t),
                    ratings[c].sigma,
                    c,
                ),
            )
        else:
            i = min(
                live,
                key=lambda c: (abs(ratings[c].mu - t), ratings[c].sigma, c),
            )
        used.add(i)
        picked.append(i)
    return picked


def select_next_game(bot: Rating, ratings: list[Rating], budget_left: int) -> list[int]:
    """Return opponent ids for the next game.

    Each id is an index into ratings. Game size is len(return) + 1.
    budget_left counts all remaining slots, including the bot.
    A duel costs 2. A 10p game costs 10. Return [] if budget_left < 2.
    The harness clips the return to budget_left and the pool size.
    """
    if not ratings or budget_left < 2:
        return []
    # Bold 2 (corr): elite separator game-2.
    if budget_left > 20:
        return _census(ratings, min(9, budget_left - 1, len(ratings)))
    if budget_left > 10:
        n = min(9, budget_left - 1, len(ratings))
        return _topdecile(bot, ratings, n)
    n = min(9, budget_left - 1, len(ratings))
    return _spread(bot, ratings, n, 1.875)
