"""Merge curated events + sharp-change explanations, flag inflection events,
validate anchors, write web/events.js.

An event is flagged "inflection": true when it pairs with a detected sharp
change (same anchor or its succession partner, within the change window
+/- tolerance) — the renderer gives those placement priority and weight.

Usage: merge_events.py <explanations.json>
"""
import json
import sys
from bisect import bisect_left

import pandas as pd

RAW = r"data\processed\events_raw.json"
CHANGES = r"data\processed\sharp_changes.csv"
DATA = r"web\data.js"
OUT = r"web\events.js"
PAIR_TOL = 40


def main():
    events = json.load(open(RAW, encoding="utf-8"))["events"]
    for path in sys.argv[1:]:
        extra = json.load(open(path, encoding="utf-8"))
        extra = extra["events"] if isinstance(extra, dict) else extra
        events = events + extra
        print(f"{len(extra)} events merged from {path}")

    rjs = open(r"web\regions.js", encoding="utf-8").read()
    REG = json.loads(rjs[rjs.index("=") + 1:].rstrip().rstrip(";"))["regions"]

    js = open(DATA, encoding="utf-8").read()
    d = json.loads(js[js.index("=") + 1:].rstrip().rstrip(";"))
    years, series = d["years"], d["series"]

    def bracket_idxs(y):
        i = bisect_left(years, y)
        return [j for j in (i - 1, i) if 0 <= j < len(years)]

    ch = pd.read_csv(CHANGES)
    windows = []  # (anchorset, y0, y1)
    for r in ch.to_dict("records"):
        anchors = {r["stream"]}
        if isinstance(r.get("succession_partner"), str):
            anchors |= {p.strip() for p in r["succession_partner"].split("|") if p.strip()}
        windows.append((anchors, r["from"] - PAIR_TOL, r["to"] + PAIR_TOL))

    out, seen = [], set()
    fixed = dropped = inflections = 0
    for e in events:
        text = e["text"].strip()
        key = (text.lower(), round(e["year"] / 25))
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        if e.get("banner"):
            if e.get("region") not in REG:
                dropped += 1
                continue
            out.append({"year": int(e["year"]), "text": text,
                        "importance": int(e["importance"]),
                        "region": e["region"], "banner": True})
            inflections += 1
            continue
        if e.get("region"):
            # column-only ruler event: anchor must be a ruler of that region
            if (e.get("region") not in REG
                    or e.get("anchor") not in REG[e["region"]]["rulers"]):
                dropped += 1
                continue
            out.append({"year": int(e["year"]), "text": text,
                        "anchor": e["anchor"],
                        "importance": int(e["importance"]),
                        "region": e["region"], "inflection": True})
            inflections += 1
            continue
        anchor = e["anchor"]
        if anchor != "global":
            s = series.get(anchor)
            if s is None or not any(s[j]["share"] > 0 for j in bracket_idxs(e["year"])):
                anchor = "global"
                fixed += 1
        infl = any(anchor in a and y0 <= e["year"] <= y1 for a, y0, y1 in windows)
        if infl:
            inflections += 1
        rec = {"year": int(e["year"]), "text": text, "anchor": anchor,
               "importance": int(e["importance"])}
        if infl:
            rec["inflection"] = True
        out.append(rec)
    out.sort(key=lambda x: x["year"])
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("const HISTOMAP_EVENTS = " + json.dumps(out) + ";\n")
    print(f"{len(out)} events ({inflections} inflection-paired, "
          f"{fixed} re-anchored global, {dropped} dupes dropped) -> {OUT}")


if __name__ == "__main__":
    main()
