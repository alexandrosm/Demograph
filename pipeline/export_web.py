"""Export population_shares.csv to web/data.js for the D3 prototype.

- Civilizational families come from the religion-language fingerprint
  classifier (pipeline/fingerprint.py): Wikidata religion (P140) and language
  (P37/P2936) claims, with era rules and a geographic fallback.
- Streams are ordered in contiguous family blocks (west->east across blocks);
  within a block, by language subfamily then centroid longitude, so the
  color ramp position encodes linguistic kinship.
- Sub-threshold polities aggregate into per-family bundle streams
  ("Smaller Islamic states", ...) at the eastern edge of their block —
  there is no global "Other" band.
- A curated lineage list marks streams that diverged from a parent
  civilization (USA from Britain, Byzantium from Rome, ...); the web layer
  renders those as vertical color gradients parent->own over ~150 years.
"""
import json
from pathlib import Path

import pandas as pd

from fingerprint import Classifier

ROOT = Path(__file__).resolve().parents[1]
IN_CSV = ROOT / "data" / "processed" / "population_shares.csv"
OUT_JS = ROOT / "web" / "data.js"

PROMINENCE_THRESHOLD = 0.010
RESIDUAL_NAME = "Stateless & unmapped"
UNRECORDED_CSV = ROOT / "data" / "processed" / "unrecorded_states.csv"
UNRECORDED_LABEL = {
    "classical": "Classical", "americas": "American",
    "westeurope": "Western", "africa": "African",
    "orthodox": "Orthodox", "ancientne": "Near Eastern", "islam": "Islamic",
    "steppe": "steppe", "dharmic": "Indic", "sinic": "East Asian",
    "japan": "Japanese",
}

FAMILY_ORDER = [
    "americas", "classical", "westeurope", "africa", "orthodox", "ancientne",
    "islam", "steppe", "dharmic", "sinic", "japan",
]

BUNDLE_NAMES = {
    "classical": "Smaller classical states",
    "americas": "Smaller American states",
    "westeurope": "Smaller Western states",
    "africa": "Smaller African states",
    "orthodox": "Smaller Orthodox states",
    "ancientne": "Smaller ancient Near East states",
    "islam": "Smaller Islamic states",
    "steppe": "Smaller steppe powers",
    "dharmic": "Smaller Indic states",
    "sinic": "Smaller East Asian states",
    "japan": "Smaller Japanese states",
}

# Within-block ordering: language subfamilies in ramp order, so the color
# ramp position reads as linguistic kinship. Unlisted subfamilies sort last.
SUBFAMILY_RAMP = {
    "classical": ["Greek", "classical", "Romance"],
    "westeurope": ["classical", "Romance", "SlavicWest", "Germanic"],
    "orthodox": ["Greek", "Romance", "SlavicEast"],
    "ancientne": ["Egyptian", "Semitic", "AncientNE", "Greek", "Iranian"],
    "islam": ["Semitic", "Turkic", "Iranian", "IndoAryan", "Austronesian"],
    "dharmic": ["harappan", "Greek", "IndoAryan", "Dravidian", "TibetoBurman",
                "KhmerMon", "Burmese", "Tai", "Austronesian"],
    "sinic": ["Sinitic", "Tungusic", "Koreanic", "Vietic"],
}

# child stream -> parent stream (or family) it civilizationally diverged from
LINEAGE = {
    "United States of America": "British Empire",
    "Mexico": "Spanish Empire",
    "Republic of Brazil": "Spanish Empire",
    "Brazilian Republic": "Spanish Empire",
    "Byzantine Empire": "Roman Empire",
    "Eastern Roman Empire": "Roman Empire",
    "Western Roman Empire": "Roman Empire",  # classical azure -> western blue
    "Ottoman Empire": "@steppe",  # parent is a family, not a stream
}


def main() -> None:
    df = pd.read_csv(IN_CSV)
    years = sorted(df.year.unique().tolist())

    polities = df[df.name != RESIDUAL_NAME]
    agg = polities.groupby("name").agg(
        lon=("lon", "mean"), lat=("lat", "mean"),
        first=("year", "min"), last=("year", "max"),
    )
    clf = Classifier()
    families, subfamilies = {}, {}
    for name, c in agg.iterrows():
        fam, sub = clf.classify(name, c.lon, c.lat, int(c.first), int(c.last))
        families[name], subfamilies[name] = fam, sub

    peak = polities.groupby("name")["share"].max()
    keep = set(peak[peak >= PROMINENCE_THRESHOLD].index)
    print(f"{len(peak)} polities total, {len(keep)} above "
          f"{PROMINENCE_THRESHOLD:.1%} peak share")

    # Aggregate sub-threshold polities into one bundle per family per year.
    small = polities[~polities.name.isin(keep)].copy()
    small["family"] = small.name.map(families)
    bundles = (
        small.groupby(["family", "year"], as_index=False)
        .agg(population=("population", "sum"), share=("share", "sum"))
    )
    bundle_names, bundle_rows = [], []
    for fam in FAMILY_ORDER:
        sub = bundles[bundles.family == fam]
        if sub.empty or sub.share.sum() <= 0:
            continue
        bname = BUNDLE_NAMES[fam]
        bundle_names.append(bname)
        families[bname] = fam
        subfamilies[bname] = "bundle"
        for r in sub.itertuples():
            bundle_rows.append(
                {"year": r.year, "name": bname,
                 "population": r.population, "share": r.share}
            )

    main_rows = polities[polities.name.isin(keep)][
        ["year", "name", "population", "share"]
    ]

    # "Unrecorded states" overlay (pipeline/unrecorded_overlay.py): mapping-gap
    # population — governed at bracketing slices, unmapped now — carved OUT of
    # the residual into per-family streams, rendered hatched by the web layer.
    unrec_names, unrec_rows = [], []
    residual_carve = {}
    if UNRECORDED_CSV.exists():
        u = pd.read_csv(UNRECORDED_CSV)
        for fam in FAMILY_ORDER:
            sub = u[u.family == fam]
            if sub.empty:
                continue
            uname = f"Unrecorded {UNRECORDED_LABEL[fam]} states"
            unrec_names.append(uname)
            families[uname] = fam
            subfamilies[uname] = "unrecorded"
            for r in sub.itertuples():
                unrec_rows.append({"year": r.year, "name": uname,
                                   "population": r.population, "share": r.share})
        residual_carve = u.groupby("year").population.sum().to_dict()
        print(f"unrecorded overlay: {len(unrec_names)} family streams, "
              f"peak slice share {u.groupby('year').share.sum().max():.1%}")

    worlds = df.groupby("year")["population"].sum()
    residual_rows = df[df.name == RESIDUAL_NAME][
        ["year", "name", "population", "share"]
    ].copy()
    if residual_carve:
        carve = residual_rows.year.map(residual_carve).fillna(0.0)
        residual_rows.population = (residual_rows.population - carve).clip(lower=0.0)
        residual_rows.share = (
            residual_rows.population / residual_rows.year.map(worlds)
        )
    full = pd.concat(
        [main_rows, pd.DataFrame(bundle_rows), pd.DataFrame(unrec_rows),
         residual_rows],
        ignore_index=True,
    )

    # Contiguous family blocks; inside a block sort by subfamily ramp
    # position, then west->east; the family bundle closes the block.
    order, block_sizes = [], {}
    for fam in FAMILY_ORDER:
        ramp = SUBFAMILY_RAMP.get(fam, [])

        def ramp_key(n):
            sub = subfamilies.get(n, "")
            r = ramp.index(sub) if sub in ramp else len(ramp)
            return (r, agg.loc[n].lon)

        members = sorted((n for n in keep if families[n] == fam), key=ramp_key)
        bname = BUNDLE_NAMES[fam]
        if bname in bundle_names:
            members.append(bname)
        uname = f"Unrecorded {UNRECORDED_LABEL[fam]} states"
        if uname in unrec_names:
            members.append(uname)
        order.extend(members)
        block_sizes[fam] = len(members)
    order.append(RESIDUAL_NAME)
    print("block sizes:", block_sizes)

    by_year = {y: {} for y in years}
    for r in full.itertuples():
        by_year[r.year][r.name] = (r.share, r.population)
    series = {
        name: [
            {
                "year": y,
                "share": by_year[y].get(name, (0.0, 0.0))[0],
                "pop": by_year[y].get(name, (0.0, 0.0))[1],
            }
            for y in years
        ]
        for name in order
    }

    # Kinship order drives COLOR (shade ramp position); the displayed stacking
    # order may be overridden by a wiggle-optimized order (pipeline/wiggle.py)
    # so that high-exchange polities sit adjacent and width swaps stay local.
    color_order = [n for n in order if n != RESIDUAL_NAME]
    opt_path = ROOT / "orders" / "stream_order.json"
    if opt_path.exists():
        opt = json.loads(opt_path.read_text(encoding="utf-8"))
        if set(opt["order"]) == set(color_order):
            order = opt["order"] + [RESIDUAL_NAME]
            print(f"applied optimized order ({opt['strategy']}, "
                  f"wiggle {opt['wiggle']/opt['baseline']:.1%} of baseline)")
        else:
            print("!! orders/stream_order.json is stale (name set mismatch), "
                  "ignoring — rerun pipeline/wiggle.py")

    in_order = set(order)
    lineage = {}
    for child, parent in LINEAGE.items():
        if child not in in_order:
            continue
        if parent.startswith("@"):
            lineage[child] = {"parent": None, "family": parent[1:]}
        elif parent in in_order:
            lineage[child] = {"parent": parent, "family": families[parent]}
        else:
            lineage[child] = {"parent": None, "family": families.get(parent, "westeurope")}

    payload = {
        "metric": "Share of world population",
        "years": years,
        "order": order,
        "colorOrder": color_order,
        "series": series,
        "regions": {n: families[n] for n in order if n != RESIDUAL_NAME},
        "subfamilies": {n: subfamilies.get(n, "") for n in order if n != RESIDUAL_NAME},
        "lineage": lineage,
        "residual": RESIDUAL_NAME,
        "bundles": bundle_names,
        "unrecorded": unrec_names,
        "familyOrder": FAMILY_ORDER,
    }
    OUT_JS.write_text(
        "const HISTOMAP_DATA = " + json.dumps(payload) + ";\n", encoding="utf-8"
    )
    print(f"wrote {OUT_JS} ({OUT_JS.stat().st_size/1e3:.0f} kB, "
          f"{len(order)} streams, {len(years)} slices)")


if __name__ == "__main__":
    main()
