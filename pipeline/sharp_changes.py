"""Detect sharp changes in stream shares and pair them with curated events.

A sharp change is a slice-to-slice transition where a stream's world share
moves a lot, fast: |dshare| >= ABS_MIN and |dshare|/gap >= RATE_MIN, or a
large relative collapse (>= REL_DROP of a non-trivial stream). Births and
extinctions of sizable streams count. Aggregate bands (Smaller/Unrecorded/
Stateless) are excluded — their jumps are usually source artifacts.

Each change is paired with curated events (same anchor, within PAIR_TOL
years). Unpaired changes are the chart asking for an explanation.

Outputs data/processed/sharp_changes.csv and prints paired/unexplained.
"""
import json

import numpy as np
import pandas as pd

SHARES = r"data\processed\population_shares.csv"
EVENTS = r"web\events.js"
OUT = r"data\processed\sharp_changes.csv"

ABS_MIN = 0.008      # >= 0.8% of world population moved
RATE_MIN = 0.00010   # ... at >= 0.5% per 50 years
REL_DROP = 0.6       # or lost 60%+ of a stream that had >= 1.2%
REL_BASE = 0.012
PAIR_TOL = 40        # years


def is_aggregate(n):
    return (n.startswith("Smaller ") or n.startswith("Unrecorded ")
            or n.startswith("Stateless"))


def main():
    df = pd.read_csv(SHARES)
    years = sorted(df.year.unique())
    piv = df.pivot_table(index="name", columns="year", values="share",
                         fill_value=0.0)
    piv = piv[~piv.index.map(is_aggregate)]

    js = open(EVENTS, encoding="utf-8").read()
    events = json.loads(js[js.index("="):].lstrip("= ").rstrip().rstrip(";"))

    # Succession detection: a collapse whose transfer-matrix partner surges
    # in the same transition is a handoff, not a mystery; events anchored to
    # EITHER side explain both rows.
    t = pd.read_csv(r"data\processed\transfer_matrix.csv")
    aff = {}
    for src, dst, pop in t.itertuples(index=False, name=None):
        if pop >= 1e6:
            aff.setdefault(src, set()).add(dst)
            aff.setdefault(dst, set()).add(src)

    raw = []
    for name, s in piv.iterrows():
        v = s[years].values
        for k in range(len(years) - 1):
            y0, y1 = years[k], years[k + 1]
            d = v[k + 1] - v[k]
            gap = y1 - y0
            big = abs(d) >= ABS_MIN and abs(d) / gap >= RATE_MIN
            relcol = v[k] >= REL_BASE and v[k + 1] < v[k] * (1 - REL_DROP)
            relsurge = v[k + 1] >= REL_BASE and v[k] < v[k + 1] * (1 - REL_DROP)
            if big or relcol or relsurge:
                raw.append({
                    "stream": name, "from": y0, "to": y1,
                    "dshare": round(d, 4),
                    "kind": ("surge" if d > 0 else "collapse"),
                    "share_before": round(v[k], 4),
                    "share_after": round(v[k + 1], 4),
                })

    by_transition = {}
    for r in raw:
        by_transition.setdefault((r["from"], r["to"]), []).append(r)
    for r in raw:
        partners = [o["stream"] for o in by_transition[(r["from"], r["to"])]
                    if o is not r and o["kind"] != r["kind"]
                    and o["stream"] in aff.get(r["stream"], ())]
        r["succession_partner"] = " | ".join(partners)
        anchors = {r["stream"], *partners}
        paired = [e["text"] for e in events
                  if e["anchor"] in anchors
                  and r["from"] - PAIR_TOL <= e["year"] <= r["to"] + PAIR_TOL]
        r["paired_events"] = " | ".join(paired)
        r["explained"] = bool(paired)

    out = pd.DataFrame(raw).sort_values("dshare", key=abs, ascending=False)
    out.to_csv(OUT, index=False)
    n_exp = int(out.explained.sum())
    print(f"{len(out)} sharp changes; {n_exp} already paired with events, "
          f"{len(out) - n_exp} unexplained")
    print("\nTop 25 UNEXPLAINED:")
    for r in out[~out.explained].head(25).to_dict("records"):
        print(f"  {r['stream'][:34]:34s} {r['from']}-{r['to']} "
              f"{r['kind']:8s} {r['share_before']:.1%} -> {r['share_after']:.1%}")


if __name__ == "__main__":
    main()
