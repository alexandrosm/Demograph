"""Global consistency diagnostics for the residual ("stateless") band.

1. Modern era: where is the unassigned population at 2000, and how much of it
   is a coastline artifact (populated cells whose 5' center falls just outside
   a polity polygon, adjacent to assigned cells)?
2. The 250/300 CE dip: how much unassigned population sits in cells that WERE
   assigned at 200 and again at 350/400 — i.e. a transient mapping gap, not
   genuine statelessness?
"""
import numpy as np
import pyogrio
from shapely.validation import make_valid

from compute_shares import CLIOPATRIA, population_for
from transfer_matrix import label_grid_for

CELL = 1 / 12  # 5 arc-minutes


def neighbor_assigned(mask, radius):
    """Cells with at least one assigned cell within `radius` (Chebyshev)."""
    out = np.zeros_like(mask)
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            if dr == 0 and dc == 0:
                continue
            out |= np.roll(np.roll(mask, dr, axis=0), dc, axis=1)
    return out


def coords(rows, cols):
    return 90 - (rows + 0.5) * CELL, -180 + (cols + 0.5) * CELL


def report_unassigned(year, gdf, name_ids):
    pop, transform = population_for(year)
    labels = label_grid_for(gdf, year, pop.shape, transform, name_ids)
    world = pop.sum()
    un = (labels == 0) & (pop > 0)
    un_pop = pop[un].sum()
    print(f"\n=== {year}: world {world/1e6:.1f}M, unassigned "
          f"{un_pop/1e6:.1f}M ({un_pop/world:.2%}) ===")
    assigned = labels > 0
    for radius in (1, 2):
        coastal = un & neighbor_assigned(assigned, radius)
        print(f"  within {radius} cells of an assigned cell: "
              f"{pop[coastal].sum()/1e6:7.1f}M "
              f"({pop[coastal].sum()/un_pop:.1%} of unassigned)")
    # Interior unassigned: aggregate to 10-degree boxes, show the top ones.
    interior = un & ~neighbor_assigned(assigned, 2)
    rows, cols = np.where(interior)
    lats, lons = coords(rows, cols)
    p = pop[interior]
    boxes = {}
    for la, lo, pp in zip(lats // 10 * 10, lons // 10 * 10, p):
        boxes[(la, lo)] = boxes.get((la, lo), 0) + pp
    print(f"  interior unassigned: {p.sum()/1e6:.1f}M; top boxes:")
    for (la, lo), pp in sorted(boxes.items(), key=lambda kv: -kv[1])[:8]:
        print(f"    lat {la:+.0f}..{la+10:+.0f}, lon {lo:+.0f}..{lo+10:+.0f}: "
              f"{pp/1e6:6.1f}M")
    return labels, pop


def main():
    print("reading Cliopatria...")
    gdf = pyogrio.read_dataframe(CLIOPATRIA)
    gdf = gdf[gdf["Type"] == "POLITY"].copy()
    bad = ~gdf.geometry.is_valid
    if bad.any():
        gdf.loc[bad, "geometry"] = gdf.loc[bad, "geometry"].apply(make_valid)
    names = sorted(gdf.Name.unique())
    name_ids = {n: i + 1 for i, n in enumerate(names)}

    report_unassigned(2000, gdf, name_ids)
    report_unassigned(1900, gdf, name_ids)

    # Transient-gap analysis around the 3rd-century dip.
    l200, p200 = report_unassigned(200, gdf, name_ids)
    l300, p300 = report_unassigned(300, gdf, name_ids)
    pop400, transform = population_for(400)
    l400 = label_grid_for(gdf, 400, pop400.shape, transform, name_ids)
    un300 = (l300 == 0) & (p300 > 0)
    bridged = un300 & (l200 > 0) & (l400 > 0)
    print(f"\n=== 300 CE transient-gap check ===")
    print(f"unassigned at 300: {p300[un300].sum()/1e6:.1f}M")
    print(f"  of that, assigned at BOTH 200 and 400 (mapping gap): "
          f"{p300[bridged].sum()/1e6:.1f}M "
          f"({p300[bridged].sum()/p300[un300].sum():.1%})")
    rows, cols = np.where(bridged)
    lats, lons = coords(rows, cols)
    p = p300[bridged]
    boxes = {}
    for la, lo, pp in zip(lats // 10 * 10, lons // 10 * 10, p):
        boxes[(la, lo)] = boxes.get((la, lo), 0) + pp
    print("  gap population by 10-degree box (top 6):")
    for (la, lo), pp in sorted(boxes.items(), key=lambda kv: -kv[1])[:6]:
        print(f"    lat {la:+.0f}..{la+10:+.0f}, lon {lo:+.0f}..{lo+10:+.0f}: "
              f"{pp/1e6:6.1f}M")


if __name__ == "__main__":
    main()
