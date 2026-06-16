"""Stream-ordering optimizer: minimize stacked-graph "wiggle" (whiplash).

Metric (after Byron & Wattenberg 2008, weighted wiggle): with streams in
stack order, boundaries g_0..g_n (shares, expand-normalized; the stateless
residual is pinned as half-width bands at both edges), the whiplash energy is

    W = sum_t sum_i  w_i(t) * ((g'_{i-1}(t) + g'_i(t)) / 2)^2 * dt

where g' = d(boundary)/d(year): each stream's lateral velocity squared,
weighted by its width — exactly the "spill-out" the eye reads as waviness.

Strategies (all keep the residual edges fixed):
  current          score the existing data.js order
  within           2-opt within each family block (blocks fixed)
  blocks           2-opt on block order (within-block order fixed)
  both             alternate blocks/within until converged
  transfer         seed within-block order by greedy max-adjacency on the
                   succession-transfer matrix, then 2-opt
  free             simulated annealing, no family constraint (upper bound)

Usage: wiggle.py <strategy> [--seed N] [--out orders/<name>.json]
"""
import argparse
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_JS = ROOT / "web" / "data.js"
TRANSFER_CSV = ROOT / "data" / "processed" / "transfer_matrix.csv"


def load():
    js = DATA_JS.read_text(encoding="utf-8")
    d = json.loads(js[js.index("=") + 1:].rstrip().rstrip(";"))
    years = np.array(d["years"], dtype=float)
    names = [n for n in d["order"] if n != d["residual"]]
    shares = np.array([[p["share"] for p in d["series"][n]] for n in names])
    residual = np.array([p["share"] for p in d["series"][d["residual"]]])
    families = d["regions"]
    return d, years, names, shares, residual, families


def wiggle(order_idx, shares, residual, years):
    """Whiplash energy for streams (rows of `shares`) in the given order."""
    w = shares[order_idx]                      # (n, T)
    half = residual / 2.0
    bounds = np.vstack([half, half + np.cumsum(w, axis=0)])  # (n+1, T)
    dt = np.diff(years)                        # (T-1,)
    dg = np.diff(bounds, axis=1) / dt          # boundary velocity per year
    center_v = (dg[:-1] + dg[1:]) / 2.0        # (n, T-1)
    w_seg = (w[:, :-1] + w[:, 1:]) / 2.0
    return float(np.sum(w_seg * center_v**2 * dt))


def two_opt(order, movable, score, rng, passes=40):
    """Hill-climb: swap / segment-reverse among `movable` index positions."""
    best = score(order)
    n = len(movable)
    improved = True
    p = 0
    while improved and p < passes:
        improved = False
        p += 1
        for _ in range(n * n):
            i, j = rng.sample(range(n), 2)
            a, b = movable[i], movable[j]
            order[a], order[b] = order[b], order[a]
            s = score(order)
            if s < best - 1e-12:
                best, improved = s, True
            else:
                order[a], order[b] = order[b], order[a]
    return best


def block_slices(names, families, order):
    """Contiguous [start, end) index ranges per family block in `order`."""
    out, start = [], 0
    for k in range(1, len(order) + 1):
        if k == len(order) or families[names[order[k]]] != families[names[order[start]]]:
            out.append((start, k))
            start = k
    return out


# --- succession-fidelity constraint ---------------------------------------
# Adjacent streams whose active spans HAND OFF in the same visual slot (one
# dies, the other rises, gap < GAP_MAX years) read as demographic succession.
# Forbid that adjacency unless the transfer matrix records real exchange —
# otherwise the optimizer manufactures false successions (it loves pairing
# anti-correlated widths, e.g. Byzantium dying into Russia rising).
AFF_MIN = 2e6      # people; below this, no succession is "recorded"
GAP_MAX = 600      # years between one stream's end and the other's start
                   # (600 so Byzantium [d.1453] can't neighbor the USSR
                   # [b.1922, gap 469] — the optimizer found that loophole)
# No peak filter: every named stream already passes the 1% prominence bar,
# and even a 1.4% stream (Tsardom of Russia) produces a succession reading —
# the optimizer exploited exactly that gap.
MAJOR_PEAK = 0.0
EPS = 1e-4


def is_aggregate(name):
    return (name.startswith("Smaller ") or name.startswith("Unrecorded ")
            or name.startswith("Stateless"))


def build_forbidden(names, shares, years, aff):
    spans = []
    for r in shares:
        idx = np.where(r > EPS)[0]
        spans.append((years[idx[0]], years[idx[-1]]) if len(idx) else None)
    peaks = shares.max(axis=1)
    forbidden = set()
    for i in range(len(names)):
        if peaks[i] < MAJOR_PEAK or is_aggregate(names[i]) or spans[i] is None:
            continue
        for j in range(i + 1, len(names)):
            if peaks[j] < MAJOR_PEAK or is_aggregate(names[j]) or spans[j] is None:
                continue
            if aff[i, j] >= AFF_MIN:
                continue
            (a0, a1), (b0, b1) = spans[i], spans[j]
            gap = b0 - a1 if a1 < b0 else (a0 - b1 if b1 < a0 else None)
            if gap is not None and gap < GAP_MAX:
                forbidden.add((min(i, j), max(i, j)))
    return forbidden


def violations(order, forbidden):
    v = 0
    for k in range(len(order) - 1):
        a, b = order[k], order[k + 1]
        if (min(a, b), max(a, b)) in forbidden:
            v += 1
    return v


def transfer_affinity(names):
    t = pd.read_csv(TRANSFER_CSV)
    idx = {n: i for i, n in enumerate(names)}
    aff = np.zeros((len(names), len(names)))
    for src, dst, pop in t.itertuples(index=False, name=None):
        a, b = idx.get(src), idx.get(dst)
        if a is not None and b is not None:
            aff[a, b] += pop
            aff[b, a] += pop
    return aff


def greedy_path(members, aff):
    """Order `members` (indices) as a greedy max-affinity path."""
    if len(members) <= 2:
        return list(members)
    rest = set(members)
    sub = aff[np.ix_(members, members)]
    start = members[int(np.argmax(sub.sum(axis=1)))]
    path = [start]
    rest.remove(start)
    while rest:
        last = path[-1]
        nxt = max(rest, key=lambda m: aff[last, m])
        path.append(nxt)
        rest.remove(nxt)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("strategy", choices=[
        "current", "within", "blocks", "both", "transfer", "free"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    d, years, names, shares, residual, families = load()
    order = list(range(len(names)))
    raw = lambda o: wiggle(np.array(o), shares, residual, years)
    base = raw(order)
    # Succession-fidelity: each forbidden adjacency costs one full baseline
    # wiggle, so the optimizer eliminates them before polishing smoothness.
    forbidden = build_forbidden(names, shares, years, transfer_affinity(names))
    print(f"{len(forbidden)} forbidden (no-transfer handoff) pairs; "
          f"start order violates {violations(order, forbidden)}")
    score = lambda o: raw(o) + violations(o, forbidden) * base

    if args.strategy in ("within", "both", "transfer"):
        if args.strategy == "transfer":
            aff = transfer_affinity(names)
            new_order = []
            for s, e in block_slices(names, families, order):
                new_order.extend(greedy_path(order[s:e], aff))
            order = new_order
        for it in range(3 if args.strategy == "both" else 1):
            for s, e in block_slices(names, families, order):
                two_opt(order, list(range(s, e)), score, rng)
            if args.strategy == "both":
                # reorder whole blocks: permute block sequence by 2-opt
                blocks = [order[s:e] for s, e in block_slices(names, families, order)]
                bidx = list(range(len(blocks)))

                def bscore(bi):
                    flat = [x for k in bi for x in blocks[k]]
                    return score(flat)

                two_opt(bidx, list(range(len(bidx))), bscore, rng, passes=10)
                order = [x for k in bidx for x in blocks[k]]
    elif args.strategy == "blocks":
        blocks = [order[s:e] for s, e in block_slices(names, families, order)]
        bidx = list(range(len(blocks)))

        def bscore(bi):
            flat = [x for k in bi for x in blocks[k]]
            return score(flat)

        two_opt(bidx, list(range(len(bidx))), bscore, rng, passes=10)
        order = [x for k in bidx for x in blocks[k]]
    elif args.strategy == "free":
        # simulated annealing over unconstrained order
        cur = order[:]
        cur_s = score(cur)
        best, best_s = cur[:], cur_s
        T0, T1, steps = base * 0.002, base * 1e-6, 60000
        for k in range(steps):
            T = T0 * (T1 / T0) ** (k / steps)
            i, j = rng.sample(range(len(cur)), 2)
            cur[i], cur[j] = cur[j], cur[i]
            s = score(cur)
            if s < cur_s or rng.random() < np.exp((cur_s - s) / T):
                cur_s = s
                if s < best_s:
                    best, best_s = cur[:], s
            else:
                cur[i], cur[j] = cur[j], cur[i]
        order = best

    final = raw(order)
    nviol = violations(order, forbidden)
    print(f"strategy={args.strategy} seed={args.seed} "
          f"wiggle: {base:.6g} -> {final:.6g} ({final/base:.1%} of baseline), "
          f"forbidden adjacencies: {nviol}")
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "strategy": args.strategy, "seed": args.seed,
            "wiggle": final + nviol * base, "baseline": base,
            "violations": nviol,
            "order": [names[i] for i in order],
        }), encoding="utf-8")
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
