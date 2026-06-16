"""Detect sharp changes inside region-focus columns.

Two kinds the world view can't see:
- REGION-TOTAL demographic shocks: the region's population falls outright
  across a transition (plague, conquest devastation, Columbian collapse).
  In-region shares are blind to these — everyone shrinks together — so they
  become column-spanning banner events.
- PER-RULER in-region share inflections: conquests and successions that are
  large within the region but diluted to invisibility at world scale.

Pairs with existing events (anchor == ruler, within tolerance; succession
partners via the transfer matrix count for either side). Writes unexplained
items to data/processed/region_unexplained.json for the explanation workflow.
"""
import json

import pandas as pd

REGIONS_JS = r"web\regions.js"
EVENTS_JS = r"web\events.js"
TRANSFER = r"data\processed\transfer_matrix.csv"
OUT = r"data\processed\region_unexplained.json"

TOTAL_DROP = 0.05    # region population falls >= 5% across a transition
RULER_ABS = 0.06     # ruler's in-region share moves >= 6 points
RULER_RATE = 0.0006  # ... at >= 3 points per 50 years
PAIR_TOL = 40


def main():
    js = open(REGIONS_JS, encoding="utf-8").read()
    R = json.loads(js[js.index("=") + 1:].rstrip().rstrip(";"))
    years = R["years"]
    ejs = open(EVENTS_JS, encoding="utf-8").read()
    events = json.loads(ejs[ejs.index("=") + 1:].rstrip().rstrip(";"))

    t = pd.read_csv(TRANSFER)
    aff = {}
    for src, dst, pop in t.itertuples(index=False, name=None):
        if pop >= 5e5:
            aff.setdefault(src, set()).add(dst)
            aff.setdefault(dst, set()).add(src)

    items, n_paired = [], 0
    for key, reg in R["regions"].items():
        total = reg["total"]
        # (a) region-total shocks
        for k in range(len(years) - 1):
            if total[k] <= 0:
                continue
            rel = (total[k + 1] - total[k]) / total[k]
            if rel <= -TOTAL_DROP:
                y0, y1 = years[k], years[k + 1]
                paired = [e for e in events
                          if e.get("region") == key and e.get("banner")
                          and y0 - PAIR_TOL <= e["year"] <= y1 + PAIR_TOL]
                if paired:
                    n_paired += 1
                    continue
                items.append({"type": "total", "region": key,
                              "regionLabel": reg["label"],
                              "from": y0, "to": y1,
                              "drop_pct": round(-rel * 100, 1),
                              "pop_before_M": round(total[k] / 1e6, 1),
                              "pop_after_M": round(total[k + 1] / 1e6, 1)})
        # (b) per-ruler in-region share inflections
        for name, arr in reg["rulers"].items():
            shares = [a / t0 if t0 > 0 else 0 for a, t0 in zip(arr, total)]
            for k in range(len(years) - 1):
                d = shares[k + 1] - shares[k]
                gap = years[k + 1] - years[k]
                if abs(d) < RULER_ABS or abs(d) / gap < RULER_RATE:
                    continue
                y0, y1 = years[k], years[k + 1]
                anchors = {name} | (aff.get(name, set()) & set(reg["rulers"]))
                paired = [e for e in events
                          if e["anchor"] in anchors
                          and y0 - PAIR_TOL <= e["year"] <= y1 + PAIR_TOL]
                if paired:
                    n_paired += 1
                    continue
                items.append({"type": "ruler", "region": key,
                              "regionLabel": reg["label"], "stream": name,
                              "from": y0, "to": y1,
                              "kind": "surge" if d > 0 else "collapse",
                              "share_before": round(shares[k], 3),
                              "share_after": round(shares[k + 1], 3)})

    totals = [i for i in items if i["type"] == "total"]
    rulers = sorted([i for i in items if i["type"] == "ruler"],
                    key=lambda i: -abs(i["share_after"] - i["share_before"]))
    keep = totals + rulers[:50]
    json.dump(keep, open(OUT, "w", encoding="utf-8"))
    print(f"{len(totals)} region-total shocks, {len(rulers)} ruler inflections "
          f"unexplained ({n_paired} already paired); kept {len(keep)} -> {OUT}")
    print("\nRegion-total shocks:")
    for i in totals:
        print(f"  {i['regionLabel'][:28]:28s} {i['from']}-{i['to']}: "
              f"-{i['drop_pct']}% ({i['pop_before_M']}M -> {i['pop_after_M']}M)")
    print("\nTop 15 ruler inflections:")
    for i in rulers[:15]:
        print(f"  [{i['region']:9s}] {i['stream'][:30]:30s} {i['from']}-{i['to']} "
              f"{i['kind']:8s} {i['share_before']:.0%} -> {i['share_after']:.0%}")


if __name__ == "__main__":
    main()
