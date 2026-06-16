"""Per-region focus data: for each named geographic region and time slice,
the population living INSIDE the region broken down by ruling polity —
regardless of the ruler's civilizational family. Drives the click-to-focus
"story of this place" column (Mughals and the Raj belong to India's story
even though they classify Islamic/Western).

Also computes each polity's HOME REGION (lifetime population-majority), used
to map a clicked stream to the region it focuses.

Outputs web/regions.js (const REGION_FOCUS = {...}).
"""
import json

import numpy as np
import pandas as pd
import pyogrio
from shapely.validation import make_valid

from compute_shares import (
    CLIOPATRIA, ROOT, SLICE_YEARS, SNAP_RADIUS, population_for, snap_dilate,
)
from fingerprint import Classifier
from transfer_matrix import label_grid_for

OUT_JS = ROOT / "web" / "regions.js"
OVERLAY_NPZ = ROOT / "data" / "processed" / "unrecorded_overlay.npz"
SHARES_CSV = ROOT / "data" / "processed" / "population_shares.csv"
CELL = 1 / 12
RULER_MIN = 0.01   # keep rulers with >=1% of region population at some slice
PARTIAL_MAX = 0.6  # below this fraction of the realm in-region, the lane is
                   # a SUBSET of the ruler's realm and gets annotated

SHORT_LABEL = {
    "indiansub": "India", "eastasia": "East Asia", "seasia": "SE Asia",
    "mideast": "the Middle East", "nafrica": "North Africa",
    "ssafrica": "Africa", "europe": "Europe", "steppe": "the steppe",
    "americas": "the Americas",
}

# Deliberate region boundaries from Natural Earth country polygons (see
# pipeline/build_region_grid.py + data/processed/region_grid_audit.csv) —
# the Himalaya bounds India because the actual border polygon does.
REGION_GRID = ROOT / "data" / "processed" / "region_grid.npy"
REGIONS = [
    ("indiansub", "Indian subcontinent", 1),
    ("eastasia", "East Asia", 2),
    ("seasia", "Southeast Asia", 3),
    ("mideast", "Middle East & Persia", 4),
    ("nafrica", "North Africa", 5),
    ("ssafrica", "Sub-Saharan Africa", 6),
    ("europe", "Europe", 7),
    ("steppe", "Steppe, Siberia & Central Asia", 8),
    ("americas", "Americas", 9),
]


def main() -> None:
    print("reading Cliopatria...")
    gdf = pyogrio.read_dataframe(CLIOPATRIA)
    gdf = gdf[gdf["Type"] == "POLITY"].copy()
    bad = ~gdf.geometry.is_valid
    if bad.any():
        gdf.loc[bad, "geometry"] = gdf.loc[bad, "geometry"].apply(make_valid)
    gdf["umbrella"] = gdf.Name.str.startswith("(")
    names = sorted(gdf.Name.unique())
    name_ids = {n: i + 1 for i, n in enumerate(names)}
    id_names = {i + 1: n for i, n in enumerate(names)}

    overlay = np.load(OVERLAY_NPZ, allow_pickle=True)
    ov_families = [str(f) for f in overlay["families"]]

    region_grid = np.load(REGION_GRID)
    masks = {key: region_grid == rid for key, _, rid in REGIONS}

    nyears = len(SLICE_YEARS)
    ruler_pop = {key: {} for key in masks}          # name -> np.array per slice
    region_total = {key: np.zeros(nyears) for key in masks}
    unrec_pop = {key: {} for key in masks}          # family -> array
    home_acc = {}                                   # name -> {region: pop}

    for t, year in enumerate(SLICE_YEARS):
        pop, transform = population_for(year)
        labels = snap_dilate(
            label_grid_for(gdf, year, pop.shape, transform, name_ids),
            SNAP_RADIUS,
        )
        fam_grid = overlay[f"y{year}"] if f"y{year}" in overlay else None
        for key, mask in masks.items():
            p = pop[mask]
            l = labels[mask]
            region_total[key][t] = p.sum()
            sums = np.bincount(l, weights=p, minlength=len(names) + 1)
            for pid in np.nonzero(sums)[0]:
                if pid == 0:
                    continue
                n = id_names[pid]
                ruler_pop[key].setdefault(n, np.zeros(nyears))[t] = sums[pid]
                home_acc.setdefault(n, {}).setdefault(key, 0.0)
                home_acc[n][key] += sums[pid]
            if fam_grid is not None:
                fsums = np.bincount(fam_grid[mask], weights=p,
                                    minlength=len(ov_families) + 1)
                for fi in np.nonzero(fsums)[0]:
                    if fi == 0:
                        continue
                    f = ov_families[fi - 1]
                    unrec_pop[key].setdefault(f, np.zeros(nyears))[t] = fsums[fi]
        print(f"{year:>6} done")

    # Lifetime world population per polity, to flag rulers that appear in a
    # region through only a subset of their realm (occupied Japan, Manchuria).
    world_sum = pd.read_csv(SHARES_CSV).groupby("name").population.sum()

    out_regions = {}
    for key, label, _ in REGIONS:
        total = region_total[key]
        keep, other = {}, np.zeros(nyears)
        for n, arr in ruler_pop[key].items():
            frac = np.divide(arr, total, out=np.zeros_like(arr), where=total > 0)
            if frac.max() >= RULER_MIN:
                keep[n] = arr
            else:
                other += arr
        unrec = unrec_pop[key]
        assigned = sum(keep.values()) + other + sum(unrec.values()) \
            if keep or len(unrec) else other
        stateless = np.clip(total - assigned, 0, None)
        partial = [
            n for n, a in keep.items()
            if n in world_sum.index and world_sum[n] > 0
            and a.sum() / world_sum[n] < PARTIAL_MAX
        ]
        rnd = lambda a: [round(float(x)) for x in a]
        out_regions[key] = {
            "label": label,
            "short": SHORT_LABEL[key],
            "partial": partial,
            "total": rnd(total),
            "rulers": {n: rnd(a) for n, a in
                       sorted(keep.items(),
                              key=lambda kv: int(np.nonzero(kv[1])[0][0]))},
            "other": rnd(other),
            "unrecorded": {f: rnd(a) for f, a in unrec.items()},
            "stateless": rnd(stateless),
        }
        print(f"{key}: {len(keep)} rulers kept")

    home = {n: max(acc, key=acc.get) for n, acc in home_acc.items()}

    # Civilizational family per kept ruler, for coloring local rulers that
    # aren't world-level streams (e.g. 1%-of-India kingdoms).
    cent = gdf.geometry.centroid
    agg = pd.DataFrame(
        {"name": gdf.Name, "lon": cent.x, "lat": cent.y,
         "frm": gdf.FromYear, "to": gdf.ToYear}
    ).groupby("name").agg(lon=("lon", "mean"), lat=("lat", "mean"),
                          first=("frm", "min"), last=("to", "max"))
    clf = Classifier()
    kept_rulers = {n for r in out_regions.values() for n in r["rulers"]}
    ruler_families = {
        n: clf.classify(n, agg.loc[n].lon, agg.loc[n].lat,
                        int(agg.loc[n].first), int(agg.loc[n].last))[0]
        for n in kept_rulers if n in agg.index
    }

    payload = {"years": SLICE_YEARS, "regions": out_regions, "home": home,
               "families": ruler_families}
    OUT_JS.write_text("const REGION_FOCUS = " + json.dumps(payload) + ";\n",
                      encoding="utf-8")
    print(f"wrote {OUT_JS} ({OUT_JS.stat().st_size/1e3:.0f} kB)")


if __name__ == "__main__":
    main()
