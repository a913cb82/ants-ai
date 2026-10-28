#!/usr/bin/env python3
"""Stuck-near-water measurement. Reads engine replay JSON, reconstructs
per-turn ant positions from order strings, reports stuck rates.
Read-only wrt repo; outputs to stdout only."""
import json, sys, glob
from collections import defaultdict

AIM = {"n": (-1, 0), "e": (0, 1), "s": (1, 0), "w": (0, -1), "-": (0, 0)}

def torus_delta(a, b, n):
    d = abs(a - b) % n
    return min(d, n - d)

def load_replay(path):
    with open(path) as f:
        return json.load(f)

def analyze(paths, label):
    # accumulators over stuck windows
    for N in (10, 25):
        pass
    agg = {10: defaultdict(int), 25: defaultdict(int)}
    # keys: near_elig, near_stuck, open_elig, open_stuck,
    #       trapped, turtle, turtle_hill
    # spawn-order quartile stats: per owner rank quartile -> [elig10, stuck10]
    quart = defaultdict(lambda: [0, 0])
    n_replays = 0
    n_ants = 0
    for path in paths:
        try:
            r = load_replay(path)
        except Exception as e:
            print(f"skip {path}: {e}", file=sys.stderr)
            continue
        rd = r["replaydata"]
        rows, cols = rd["map"]["rows"], rd["map"]["cols"]
        grid = rd["map"]["data"]
        water = set()
        for rr in range(rows):
            row = grid[rr]
            for cc in range(cols):
                if row[cc] == "%":
                    water.add((rr, cc))
        if not water:
            has_water = False
        else:
            has_water = True
        # water-distance (chebyshev, torus) via brute force ok for small maps
        # precompute for all cells: min chebyshev torus dist to water
        wlist = list(water)
        def wdist(p):
            best = 10 ** 9
            for (wr, wc) in wlist:
                d = max(torus_delta(p[0], wr, rows), torus_delta(p[1], wc, cols))
                if d < best:
                    best = d
                    if best == 0:
                        break
            return best
        hills = rd.get("hills", [])  # [row, col, owner, end]
        own_hills = defaultdict(list)
        for h in hills:
            own_hills[h[2]].append((h[0], h[1]))
        ants = rd["ants"]
        n_replays += 1
        # per-owner spawn rank
        by_owner = defaultdict(list)
        for idx, a in enumerate(ants):
            by_owner[a[4]].append(idx)
        rank_of = {}
        for o, idxs in by_owner.items():
            idxs_sorted = sorted(idxs, key=lambda i: (ants[i][2], i))
            for rank, i in enumerate(idxs_sorted):
                rank_of[i] = rank / max(1, len(idxs_sorted) - 1)  # 0..1
        for idx, a in enumerate(ants):
            r0, c0, t0, t1, owner, orders = a
            n_ants += 1
            # note: killed ants log no order on death turn, so len(orders) may be t1-t0-1
            pos = [(r0, c0)]
            for ch in orders:
                dr, dc = AIM.get(ch, (0, 0))
                pr, pc = pos[-1]
                pos.append(((pr + dr) % rows, (pc + dc) % cols))
            # pos[k] = location during turn t0+k, k=0..len(orders)-1; pos has len+1 entries
            life = len(orders)
            q = rank_of[idx]
            qb = min(3, int(q * 4))
            for N in (10, 25):
                if life < N:
                    continue
                for s in range(0, life - N + 1):
                    window = pos[s:s + N]
                    p = window[0]
                    stuck = all(x == p for x in window)
                    near = has_water and wdist(p) <= 2
                    agg[N]["elig"] += 1
                    quart[(N, qb)][0] += 1
                    if near:
                        agg[N]["near_elig"] += 1
                    else:
                        agg[N]["open_elig"] += 1
                    if stuck:
                        agg[N]["stuck"] += 1
                        quart[(N, qb)][1] += 1
                        if near:
                            agg[N]["near_stuck"] += 1
                            # trapped vs turtle heuristic:
                            # W2 = water tiles within chebyshev<=2 of p
                            w2 = sum(1 for (wr, wc) in wlist
                                     if max(torus_delta(p[0], wr, rows),
                                            torus_delta(p[1], wc, cols)) <= 2)
                            # passable orthogonal neighbours (non-water)
                            pn = 0
                            for dr, dc in ((-1, 0), (1, 0), (0, 1), (0, -1)):
                                if ((p[0] + dr) % rows, (p[1] + dc) % cols) not in water:
                                    pn += 1
                            if w2 >= 6 or pn <= 1:
                                agg[N]["trapped"] += 1
                            else:
                                agg[N]["turtle"] += 1
                                if any(max(torus_delta(p[0], hr, rows),
                                           torus_delta(p[1], hc, cols)) <= 5
                                       for (hr, hc) in own_hills.get(owner, [])):
                                    agg[N]["turtle_hill"] += 1
                        else:
                            agg[N]["open_stuck"] += 1
    print(f"== {label}: {n_replays} replays, {n_ants} ants ==")
    for N in (10, 25):
        a = agg[N]
        ne, ns = a["near_elig"], a["near_stuck"]
        oe, os_ = a["open_elig"], a["open_stuck"]
        tr, tu = a["trapped"], a["turtle"]
        print(f"N={N}: near-water stuck {ns}/{ne} = {ns/max(1,ne):.4f} | "
              f"open stuck {os_}/{oe} = {os_/max(1,oe):.4f} | ratio { (ns/max(1,ne))/(os_/max(1,oe)) if os_ else float('nan'):.2f}x")
        print(f"  shoreline-stuck split: trapped {tr} vs turtle {tu} "
              f"(of {ns}; hill-adjacent subset of turtle: {a['turtle_hill']})")
        qs = [f"Q{i+1}:{quart[(N,i)][1]}/{quart[(N,i)][0]}={quart[(N,i)][1]/max(1,quart[(N,i)][0]):.4f}"
              for i in range(4)]
        print(f"  stuck-window rate by owner spawn-order quartile (Q4=latest): {' '.join(qs)}")
    print("HEURISTICS: stuck=identical cell over N consecutive alive turns; "
          "near=chebyshev torus dist to water<=2; trapped=W2(#water within cheby2)>=6 OR <=1 passable 4-neighbour, else turtle; "
          "hill-adjacent=turtle within cheby5 of own hill.")

if __name__ == "__main__":
    label = sys.argv[1]
    analyze(sys.argv[2:], label)
