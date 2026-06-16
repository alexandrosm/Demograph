"""Validate curated events against the chart data and write web/events.js.

Checks per event: anchor stream exists; anchor has nonzero share at the
nearest slice to the event year (a chart can only place an event inside an
existing stream). Failing anchors fall back to 'global' (rendered in the
stateless margin) rather than being lost; exact-duplicate texts dedupe.

Usage: validate_events.py <raw_events.json>
"""
import json
import sys
from bisect import bisect_left

ROOT_DATA = r"web\data.js"
OUT = r"web\events.js"


def main():
    raw = json.load(open(sys.argv[1], encoding="utf-8"))
    events = raw["events"] if isinstance(raw, dict) else raw

    js = open(ROOT_DATA, encoding="utf-8").read()
    d = json.loads(js[js.index("=") + 1:].rstrip().rstrip(";"))
    years = d["years"]
    series = d["series"]

    def bracket_idxs(y):
        i = bisect_left(years, y)
        return [j for j in (i - 1, i) if 0 <= j < len(years)]

    out, seen = [], set()
    fixed, kept, dropped = 0, 0, 0
    for e in events:
        text = e["text"].strip()
        key = (text.lower(), round(e["year"] / 25))
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        anchor = e["anchor"]
        if anchor != "global":
            s = series.get(anchor)
            if s is None or not any(s[j]["share"] > 0 for j in bracket_idxs(e["year"])):
                anchor = "global"
                fixed += 1
        kept += 1
        out.append({"year": int(e["year"]), "text": text,
                    "anchor": anchor, "importance": int(e["importance"])})
    out.sort(key=lambda x: x["year"])
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("const HISTOMAP_EVENTS = " + json.dumps(out) + ";\n")
    print(f"{kept} events kept ({fixed} re-anchored to global, "
          f"{dropped} duplicates dropped) -> {OUT}")
    from collections import Counter
    eras = Counter(("BCE" if e["year"] < 0 else f"{e['year'] // 500 * 500}s")
                   for e in out)
    print("distribution:", dict(sorted(eras.items(), key=lambda kv: str(kv[0]))))


if __name__ == "__main__":
    main()
