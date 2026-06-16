"""Diff family assignments: current data.js vs freshly computed classifier."""
import json

import pandas as pd

from fingerprint import Classifier

js = open(r"web\data.js", encoding="utf-8").read()
old = json.loads(js[js.index("=") + 1:].rstrip().rstrip(";"))
old_regions = old["regions"]

df = pd.read_csv(r"data\processed\population_shares.csv")
agg = df[df.name != "Stateless & unmapped"].groupby("name").agg(
    lon=("lon", "mean"), lat=("lat", "mean"),
    first=("year", "min"), last=("year", "max"),
)
clf = Classifier()
changes = []
for name, c in agg.iterrows():
    if name not in old_regions:
        continue
    fam, sub = clf.classify(name, c.lon, c.lat, int(c.first), int(c.last))
    if fam != old_regions[name]:
        changes.append((name, old_regions[name], fam, sub))
print(f"{len(changes)} polities changed family:")
for name, was, now, sub in sorted(changes):
    print(f"  {name[:42]:42s} {was:12s} -> {now} [{sub}]")
