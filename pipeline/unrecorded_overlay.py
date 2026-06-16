"""Build the "unrecorded states" overlay — our own derived layer on top of
Cliopatria.

REGION RULE (civilizational look-back): for every slice, a populated cell
with no mapped polity is attributed to the civilizational family of its most
recent ruler, provided that rule was within LOOKBACK years. Rationale: once a
region has state organization, its population does not revert to
statelessness when the sources lose track — unrecorded local successor
polities exist (post-Gupta India, sub-Roman Britain, the post-Byzantine
Maghreb). Cells never governed within the window stay in the gray residual —
the genuinely non-state or never-mapped world (pre-Columbian Amazonia,
pre-state Africa) is not claimed.

Attribution does NOT extend the clock: only an actual mapped polygon
refreshes a cell's "last governed" year, so a region can drift back to gray
at most LOOKBACK years after its last recorded polity.

Outputs:
  data/processed/unrecorded_states.csv   year, family, population, share
  data/processed/unrecorded_overlay.npz  per-year uint8 grid of family
                                          indices (0 = none), key "y<year>",
                                          plus "families" name array
"""
import numpy as np
import pandas as pd
import pyogrio
from shapely.validation import make_valid

from compute_shares import (
    CLIOPATRIA, ROOT, SLICE_YEARS, SNAP_RADIUS, population_for, snap_dilate,
)
from fingerprint import Classifier
from transfer_matrix import label_grid_for

OUT_CSV = ROOT / "data" / "processed" / "unrecorded_states.csv"
OUT_NPZ = ROOT / "data" / "processed" / "unrecorded_overlay.npz"
LOOKBACK = 500  # years a civilization's claim outlives its last mapped polity


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

    # Family per polity id, via the fingerprint classifier.
    cent = gdf.geometry.centroid
    agg = pd.DataFrame(
        {"name": gdf.Name, "lon": cent.x, "lat": cent.y,
         "frm": gdf.FromYear, "to": gdf.ToYear}
    ).groupby("name").agg(lon=("lon", "mean"), lat=("lat", "mean"),
                          first=("frm", "min"), last=("to", "max"))
    clf = Classifier()
    fam_of = {
        n: clf.classify(n, r.lon, r.lat, int(r.first), int(r.last))[0]
        for n, r in agg.iterrows()
    }
    families = sorted(set(fam_of.values()))
    fam_idx = {f: i + 1 for i, f in enumerate(families)}
    polity_fam = np.zeros(len(names) + 1, dtype=np.uint8)
    for n, f in fam_of.items():
        polity_fam[name_ids[n]] = fam_idx[f]

    rows = []
    grids = {}
    last_fam = None
    last_year = None
    for year in SLICE_YEARS:
        pop, transform = population_for(year)
        labels = snap_dilate(
            label_grid_for(gdf, year, pop.shape, transform, name_ids),
            SNAP_RADIUS,
        )
        if last_fam is None:
            last_fam = np.zeros(pop.shape, dtype=np.uint8)
            last_year = np.full(pop.shape, -(10 ** 6), dtype=np.int32)
        governed = labels > 0
        eligible = (
            (~governed) & (pop > 0) & (last_fam > 0)
            & (year - last_year <= LOOKBACK)
        )
        fam_grid = np.where(eligible, last_fam, 0).astype(np.uint8)
        world = pop.sum()
        sums = np.bincount(fam_grid.ravel(), weights=pop.ravel(),
                           minlength=len(families) + 1)
        total = sums[1:].sum()
        if total > 0:
            grids[f"y{year}"] = fam_grid
            for f, i in fam_idx.items():
                if sums[i] > 0:
                    rows.append({"year": year, "family": f,
                                 "population": sums[i],
                                 "share": sums[i] / world})
        print(f"{year:>6}: unrecorded {total/1e6:6.1f}M ({total/world:5.1%})")
        # Only real polygons refresh the memory — attribution doesn't.
        last_fam[governed] = polity_fam[labels[governed]]
        last_year[governed] = year

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)
    np.savez_compressed(OUT_NPZ, families=np.array(families), **grids)
    print(f"wrote {OUT_CSV} ({len(out)} rows) and {OUT_NPZ} "
          f"({OUT_NPZ.stat().st_size/1e6:.1f} MB, {len(grids)} slices)")
    if len(out):
        top = out.groupby("family").population.sum().sort_values(ascending=False)
        print("total unrecorded population-slice by family:")
        print((top / 1e6).round(1).to_string())


if __name__ == "__main__":
    main()
