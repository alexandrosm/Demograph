"""Succession-transfer matrix: for each consecutive slice pair, the population
living in grid cells that passed from polity A's rule to polity B's rule
(including to/from statelessness). This measures "large-scale exchange"
between polities, used to keep high-exchange pairs adjacent in the stream
stacking so their width swaps don't whiplash unrelated streams.

Outputs data/processed/transfer_matrix.csv (from, to, population).
"""
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio
from rasterio.features import rasterize
from shapely.validation import make_valid

from compute_shares import (
    CLIOPATRIA, SLICE_YEARS, active_records, population_for,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = ROOT / "data" / "processed" / "transfer_matrix.csv"
STATELESS = "Stateless & unmapped"


def label_grid_for(gdf, year, shape, transform, name_ids):
    """Winner-takes-cell polity label grid (smaller polities burn last)."""
    active = active_records(gdf, year)
    active = active.sort_values("Area", ascending=False)
    shapes = [(g, name_ids[n]) for g, n in zip(active.geometry, active.Name)]
    if not shapes:
        return np.zeros(shape, dtype="int32")
    return rasterize(shapes, out_shape=shape, transform=transform,
                     fill=0, dtype="int32")


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
    id_names = {i: n for n, i in name_ids.items()}
    id_names[0] = STATELESS

    transfers = defaultdict(float)
    prev_labels = None
    prev_year = None
    for year in SLICE_YEARS:
        pop, transform = population_for(year)
        labels = label_grid_for(gdf, year, pop.shape, transform, name_ids)
        if prev_labels is not None:
            changed = prev_labels != labels
            a = prev_labels[changed]
            b = labels[changed]
            p = pop[changed]
            for key, w in zip(
                (a.astype("int64") << 32) | b.astype("int64"),
                p,
            ):
                transfers[key] += w
            print(f"{prev_year} -> {year}: {changed.sum()} cells changed hands")
        prev_labels, prev_year = labels, year

    rows = [
        {"from": id_names[k >> 32], "to": id_names[k & 0xFFFFFFFF], "population": v}
        for k, v in transfers.items()
        if v > 0
    ]
    out = pd.DataFrame(rows).sort_values("population", ascending=False)
    out.to_csv(OUT_CSV, index=False)
    print(f"wrote {len(out)} transfer pairs -> {OUT_CSV}")
    print(out.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
