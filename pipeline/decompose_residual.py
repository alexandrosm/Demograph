"""Decompose the unassigned ("stateless/unmapped") population at a given year
into named macro-regions, to separate genuine non-state population from
source coverage gaps. Usage: decompose_residual.py [year]"""
import sys

import numpy as np
import pyogrio
from shapely.validation import make_valid

from compute_shares import CLIOPATRIA, SNAP_RADIUS, population_for, snap_dilate
from transfer_matrix import label_grid_for

CELL = 1 / 12

REGIONS = [
    ("Americas",            lambda lo, la: lo < -30),
    ("Sub-Saharan Africa",  lambda lo, la: (-20 <= lo) & (lo <= 52) & (la < 12)),
    ("North Africa",        lambda lo, la: (-20 <= lo) & (lo <= 35) & (12 <= la) & (la < 38)),
    ("Europe",              lambda lo, la: (-12 <= lo) & (lo <= 42) & (la >= 38)),
    ("Mideast/Persia",      lambda lo, la: (35 < lo) & (lo <= 62) & (12 <= la) & (la < 45)),
    ("India",               lambda lo, la: (62 < lo) & (lo <= 92) & (la <= 38)),
    ("Steppe/Central Asia", lambda lo, la: (42 < lo) & (lo <= 120) & (la > 38)),
    ("SE Asia & Indonesia", lambda lo, la: (92 < lo) & (lo <= 145) & (la <= 22)),
    ("China/Korea/Japan",   lambda lo, la: (92 < lo) & (lo <= 145) & (la > 22)),
]


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 650
    gdf = pyogrio.read_dataframe(CLIOPATRIA)
    gdf = gdf[gdf["Type"] == "POLITY"].copy()
    bad = ~gdf.geometry.is_valid
    if bad.any():
        gdf.loc[bad, "geometry"] = gdf.loc[bad, "geometry"].apply(make_valid)
    gdf["umbrella"] = gdf.Name.str.startswith("(")
    names = sorted(gdf.Name.unique())
    name_ids = {n: i + 1 for i, n in enumerate(names)}

    pop, transform = population_for(year)
    labels = snap_dilate(
        label_grid_for(gdf, year, pop.shape, transform, name_ids), SNAP_RADIUS
    )
    world = pop.sum()
    un = (labels == 0) & (pop > 0)
    rows, cols = np.where(un)
    lats = 90 - (rows + 0.5) * CELL
    lons = -180 + (cols + 0.5) * CELL
    p = pop[un]
    print(f"{year}: world {world/1e6:.1f}M, unassigned {p.sum()/1e6:.1f}M "
          f"({p.sum()/world:.1%})")
    rest = np.ones(len(p), dtype=bool)
    for name, fn in REGIONS:
        m = fn(lons, lats) & rest
        rest &= ~m
        print(f"  {name:22s} {p[m].sum()/1e6:7.1f}M  ({p[m].sum()/world:5.1%} of world)")
    print(f"  {'(other)':22s} {p[rest].sum()/1e6:7.1f}M  ({p[rest].sum()/world:5.1%})")


if __name__ == "__main__":
    main()
