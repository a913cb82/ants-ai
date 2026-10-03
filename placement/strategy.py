"""Placement strategy. Optimise select_next_game."""

import math
from dataclasses import dataclass
from statistics import NormalDist

try:
    from openskill.models import BradleyTerryFull as _BT

    _MODEL = _BT()
except ImportError:  # pragma: no cover
    _MODEL = None


@dataclass
class Rating:
    mu: float
    sigma: float


def _info_duel(
    bot: Rating, ratings: list[Rating], side: int = 0, width: int = 40, rank: int = 0
) -> list[int]:
    """Tail duel: rank-th best predict_draw + 0.02 sigma over width nearest."""
    order = sorted(
        range(len(ratings)),
        key=lambda c: (abs(ratings[c].mu - bot.mu), ratings[c].sigma, c),
    )[:width]
    gated = [c for c in order if (ratings[c].mu - bot.mu) * side > 0] or order
    if not gated:
        return []
    scored: list[tuple[float, int, int]] = []
    for pos, c in enumerate(gated):
        teams = [[_MODEL.rating(mu=bot.mu, sigma=bot.sigma)]]
        sig = bot.sigma
        for i in (c,):
            teams.append([_MODEL.rating(mu=ratings[i].mu, sigma=ratings[i].sigma)])
            sig += ratings[i].sigma
        v = _MODEL.predict_draw(teams) + 0.02 * sig
        scored.append((v, pos, c))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [scored[min(rank, len(scored) - 1)][2]]


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


def _calsnap(
    ratings: list[Rating], k: int, tol: float = 0.15, mid: bool = False
) -> list[int]:
    """Decile sites; lowest-sigma snap within tol, else nearest."""
    n = len(ratings)
    pool = sorted(r.mu for r in ratings)
    sites = [pool[min(int(n * (j + 1) / (k + 1)), n - 1)] for j in range(k)]
    picked: list[int] = []
    used: set[int] = set()
    for j, t in enumerate(sites):
        cands = [c for c in range(n) if c not in used]
        if not cands:
            break
        extreme = mid and (j == 0 or j == len(sites) - 1)
        near = [] if extreme else [c for c in cands if abs(ratings[c].mu - t) <= tol]
        src = near or cands
        if near:
            i = min(src, key=lambda c: (ratings[c].sigma, abs(ratings[c].mu - t), c))
        else:
            i = min(src, key=lambda c: (abs(ratings[c].mu - t), ratings[c].sigma, c))
        used.add(i)
        picked.append(i)
    return picked


def _strata(
    bot: Rating,
    ratings: list[Rating],
    k: int,
    split: bool = False,
    five: bool = False,
    off: float = 0.0,
    edge: float = 1.0,
    root: bool = False,
) -> list[int]:
    """k rulers across bins by mass quota (3-bin, or 4-bin signed-peer)."""
    pool = _established(ratings, k, 0)
    s = max(bot.sigma, 0.5) * edge
    bins: list[list[int]] = [[], [], []]
    for c in pool:
        d = ratings[c].mu - bot.mu
        bins[0 if d < -s else (2 if d > s else 1)].append(c)
    if five:
        ordered = sorted(bins[1], key=lambda c: ratings[c].mu)
        t1, t2 = len(ordered) // 3, 2 * len(ordered) // 3
        bins = [bins[0], ordered[:t1], ordered[t1:t2], ordered[t2:], bins[2]]
    elif split or off:
        cut = bot.mu + off * max(bot.sigma, 0.5)
        bins = [
            bins[0],
            [c for c in bins[1] if ratings[c].mu < cut],
            [c for c in bins[1] if ratings[c].mu >= cut],
            bins[2],
        ]
    masses = [len(b) for b in bins]
    if root:
        masses = [m**0.5 for m in masses]
    total = sum(masses) or 1
    nb = len(bins)
    quota = [max(1 if m else 0, round(k * m / total)) for m in masses]
    while sum(quota) > k:
        j = max(range(nb), key=lambda j: quota[j] - k * masses[j] / total)
        quota[j] -= 1
    while sum(quota) < k:
        j = max(range(nb), key=lambda j: k * masses[j] / total - quota[j])
        quota[j] += 1
    out: list[int] = []
    for b, q in zip(bins, quota, strict=True):
        near = sorted(
            b, key=lambda c: (abs(ratings[c].mu - bot.mu), ratings[c].sigma, c)
        )
        out += near[: max(q, 0)]
    if len(out) < k:
        rest = sorted(
            (c for c in pool if c not in set(out)),
            key=lambda c: (abs(ratings[c].mu - bot.mu), ratings[c].sigma, c),
        )
        out += rest[: k - len(out)]
    return out[:k]


def _bounty(bot: Rating, ratings: list[Rating]) -> list[int]:
    """Max-sigma ruler in the peer band over the last-400 window."""
    n = len(ratings)
    lo = max(0, n - 400)
    band = max(bot.sigma, 0.5)
    elig = [c for c in range(lo, n) if abs(ratings[c].mu - bot.mu) <= band] or list(
        range(lo, n)
    )
    if not elig:
        return []
    return [
        max(
            elig,
            key=lambda c: (ratings[c].sigma, -abs(ratings[c].mu - bot.mu), -c),
        )
    ]


def _infoscore(
    bot: Rating, field: list[int], ratings: list[Rating], c: int, w: float = 0.02
) -> float:
    """Draw probability + sigma weight for bot+field+c (info value proxy)."""
    teams = [[_MODEL.rating(mu=bot.mu, sigma=bot.sigma)]]
    sig = bot.sigma
    for i in field + [c]:
        teams.append([_MODEL.rating(mu=ratings[i].mu, sigma=ratings[i].sigma)])
        sig += ratings[i].sigma
    return _MODEL.predict_draw(teams) + w * sig


def _infostrata(bot: Rating, ratings: list[Rating], k: int) -> list[int]:
    """Mass-quota bins; within-bin sequential argmax of info score."""
    pool = _established(ratings, k, 0)
    s = max(bot.sigma, 0.5)
    bins: list[list[int]] = [[], [], []]
    for c in pool:
        d = ratings[c].mu - bot.mu
        bins[0 if d < -s else (2 if d > s else 1)].append(c)
    masses = [len(b) for b in bins]
    total = sum(masses) or 1
    quota = [max(1 if m else 0, round(k * m / total)) for m in masses]
    while sum(quota) > k:
        j = max(range(3), key=lambda j: quota[j] - k * masses[j] / total)
        quota[j] -= 1
    while sum(quota) < k:
        j = max(range(3), key=lambda j: k * masses[j] / total - quota[j])
        quota[j] += 1
    picked: list[int] = []
    used: set[int] = set()
    for b, q in zip(bins, quota, strict=True):
        near = sorted(
            b, key=lambda c: (abs(ratings[c].mu - bot.mu), ratings[c].sigma, c)
        )[:40]
        for _ in range(max(q, 0)):
            cands = [c for c in near if c not in used]
            if not cands:
                break
            i = max(cands, key=lambda c: (_infoscore(bot, picked, ratings, c), c))
            used.add(i)
            picked.append(i)
    if len(picked) < k:
        rest = sorted(
            (c for c in pool if c not in used),
            key=lambda c: (abs(ratings[c].mu - bot.mu), ratings[c].sigma, c),
        )
        picked += rest[: k - len(picked)]
    return picked[:k]


def _gridstrata(
    bot: Rating, ratings: list[Rating], k: int, width: float = 1.0
) -> list[int]:
    """Mass-quota bins; within-bin picks at Gaussian quantile targets."""
    pool = _established(ratings, k, 0)
    s = max(bot.sigma, 0.5)
    bins: list[list[int]] = [[], [], []]
    for c in pool:
        d = ratings[c].mu - bot.mu
        bins[0 if d < -s else (2 if d > s else 1)].append(c)
    masses = [len(b) for b in bins]
    total = sum(masses) or 1
    quota = [max(1 if m else 0, round(k * m / total)) for m in masses]
    while sum(quota) > k:
        j = max(range(3), key=lambda j: quota[j] - k * masses[j] / total)
        quota[j] -= 1
    while sum(quota) < k:
        j = max(range(3), key=lambda j: k * masses[j] / total - quota[j])
        quota[j] += 1
    grid = NormalDist(bot.mu, max(width * bot.sigma, 0.5))
    picked: list[int] = []
    used: set[int] = set()
    for b, q in zip(bins, quota, strict=True):
        cands = [c for c in b if c not in used]
        for i in range(max(q, 0)):
            live = [c for c in cands if c not in used]
            if not live:
                break
            t = grid.inv_cdf((i + 1) / (q + 1))
            pick = min(
                live, key=lambda c: (abs(ratings[c].mu - t), ratings[c].sigma, c)
            )
            used.add(pick)
            picked.append(pick)
    if len(picked) < k:
        rest = sorted(
            (c for c in pool if c not in used),
            key=lambda c: (abs(ratings[c].mu - bot.mu), ratings[c].sigma, c),
        )
        picked += rest[: k - len(picked)]
    return picked[:k]


def _comp(bot: Rating, ratings: list[Rating], k: int) -> list[int]:
    """k nearest established rulers, no bins, no grid."""
    pool = _established(ratings, k, 0)
    near = sorted(
        pool, key=lambda c: (abs(ratings[c].mu - bot.mu), ratings[c].sigma, c)
    )
    return near[:k]


def _medstrata(
    bot: Rating, ratings: list[Rating], k: int, far: bool = False
) -> list[int]:
    """Mass-quota bins; within-bin picks nearest the bin median (or farthest)."""
    pool = _established(ratings, k, 0)
    s = max(bot.sigma, 0.5)
    bins: list[list[int]] = [[], [], []]
    for c in pool:
        d = ratings[c].mu - bot.mu
        bins[0 if d < -s else (2 if d > s else 1)].append(c)
    masses = [len(b) for b in bins]
    total = sum(masses) or 1
    quota = [max(1 if m else 0, round(k * m / total)) for m in masses]
    while sum(quota) > k:
        j = max(range(3), key=lambda j: quota[j] - k * masses[j] / total)
        quota[j] -= 1
    while sum(quota) < k:
        j = max(range(3), key=lambda j: k * masses[j] / total - quota[j])
        quota[j] += 1
    out: list[int] = []
    used: set[int] = set()
    for b, q in zip(bins, quota, strict=True):
        if not b or q <= 0:
            continue
        mus = sorted(ratings[c].mu for c in b)
        med = mus[len(mus) // 2]
        near = sorted(
            [c for c in b if c not in used],
            key=lambda c: (abs(ratings[c].mu - med), ratings[c].sigma, c),
            reverse=far,
        )
        for c in near[: max(q, 0)]:
            used.add(c)
            out.append(c)
    if len(out) < k:
        rest = sorted(
            (c for c in pool if c not in used),
            key=lambda c: (abs(ratings[c].mu - bot.mu), ratings[c].sigma, c),
        )
        out += rest[: k - len(out)]
    return out[:k]


def _side_duel(
    bot: Rating, ratings: list[Rating], rank: int, first: int = 1
) -> list[int]:
    """Nearest ruler strictly above/below bot mu, parity from first."""
    side = first if rank % 2 == 0 else -first
    cands = [
        c for c in range(len(ratings)) if (ratings[c].mu - bot.mu) * side > 0
    ] or list(range(len(ratings)))
    if not cands:
        return []
    return [
        min(
            cands,
            key=lambda c: (abs(ratings[c].mu - bot.mu), ratings[c].sigma, c),
        )
    ]


def _credpin(bot: Rating, ratings: list[Rating]) -> list[int]:
    """Lowest sigma among 10 nearest rulers (credible pin)."""
    order = sorted(
        range(len(ratings)),
        key=lambda c: (abs(ratings[c].mu - bot.mu), ratings[c].sigma, c),
    )[:10]
    if not order:
        return []
    return [
        min(order, key=lambda c: (ratings[c].sigma, abs(ratings[c].mu - bot.mu), c))
    ]


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
    # Iter 136 (camp H1): range-grid early window retest.
    early = len(ratings) < 200 and len(ratings) % 2 == 0
    if budget_left > 20:
        n = min(9, budget_left - 1, len(ratings))
        return _census(ratings, n, mode="range" if early else "quantile")
    if budget_left > 14:
        n = min(5, budget_left - 1, len(ratings))
        if early:
            return _spread(bot, ratings, n, width=1.5, anchors=False)
        return _strata(bot, ratings, n)
    return _info_duel(bot, ratings, 0, 40, 0)
