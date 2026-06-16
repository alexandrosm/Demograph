"""Build web/minimap.js — a lightweight, year-indexed vector world map for the
side minimap.

For each time slice, the prominent named streams' polygons (simplified +
reprojected to a normalized equirectangular 1000x500 box) are stored as SVG
path strings, keyed by year. The web minimap renders one year's frame at a
time, colored by the same civilizational family as the main chart, and
highlights the hovered/focused stream. A dissolved low-res land outline from
Natural Earth provides a recognizable backdrop.

Output: web/minimap.js  (const MINIMAP = {years, land, frames})
"""
import json
from pathlib import Path

import numpy as np
import pyogrio
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

from compute_shares import CLIOPATRIA, ROOT, SLICE_YEARS

DATA_JS = ROOT / "web" / "data.js"
NE_DIR = ROOT / "data" / "raw" / "naturalearth"
OUT = ROOT / "web" / "minimap.js"

VW, VH = 1000, 500
SIMPLIFY_DEG = 0.7          # polygon simplification tolerance
LAND_SIMPLIFY = 0.9
MIN_SHARE = 0.004           # drop streams below 0.4% of world at that slice
MIN_RING_AREA = 6.0         # deg^2, drop tiny rings/islands in the basemap


def project_ring(coords):
    """lon/lat ring -> 'x y x y ...' ints in the VWxVH equirectangular box."""
    out = []
    for lon, lat in coords:
        x = int(round((lon + 180) / 360 * VW))
        y = int(round((90 - lat) / 180 * VH))
        out.append((max(0, min(VW, x)), max(0, min(VH, y))))
    # drop consecutive duplicates after rounding
    dedup = [out[0]]
    for p in out[1:]:
        if p != dedup[-1]:
            dedup.append(p)
    return dedup


def geom_to_path(geom, simplify):
    if geom.is_empty:
        return None
    g = geom.simplify(simplify, preserve_topology=True)
    if g.is_empty:
        return None
    polys = g.geoms if isinstance(g, MultiPolygon) else [g]
    parts = []
    for poly in polys:
        if not isinstance(poly, Polygon) or poly.area < 0.15:
            continue
        ring = project_ring(list(poly.exterior.coords))
        if len(ring) < 4:
            continue
        parts.append("M" + "L".join(f"{x} {y}" for x, y in ring) + "Z")
    return "".join(parts) or None


def load_prominent_names():
    js = DATA_JS.read_text(encoding="utf-8")
    d = json.loads(js[js.index("=") + 1:].rstrip().rstrip(";"))
    names, series = [], d["series"]
    for n in d["order"]:
        if (n == d["residual"] or n.startswith("Smaller ")
                or n.startswith("Unrecorded ")):
            continue
        names.append(n)
    return set(names), d["years"], series


def main():
    print("reading Cliopatria...")
    gdf = pyogrio.read_dataframe(CLIOPATRIA)
    gdf = gdf[gdf["Type"] == "POLITY"].copy()
    bad = ~gdf.geometry.is_valid
    if bad.any():
        gdf.loc[bad, "geometry"] = gdf.loc[bad, "geometry"].apply(make_valid)

    prominent, years, series = load_prominent_names()
    share_at = {n: {p["year"]: p["share"] for p in series[n]} for n in prominent}

    frames = {}
    for year in SLICE_YEARS:
        active = gdf[(gdf.FromYear <= year) & (gdf.ToYear >= year)
                     & gdf.Name.isin(prominent)]
        active = active.sort_values("FromYear").groupby("Name", as_index=False).tail(1)
        feats = []
        for rec in active.itertuples():
            if share_at.get(rec.Name, {}).get(year, 0) < MIN_SHARE:
                continue
            path = geom_to_path(rec.geometry, SIMPLIFY_DEG)
            if path:
                feats.append({"n": rec.Name, "d": path})
        if feats:
            frames[str(year)] = feats
        print(f"{year:>6}: {len(feats)} polities")

    print("dissolving Natural Earth land basemap...")
    shp = list(NE_DIR.glob("*.shp"))
    land_paths = []
    if shp:
        ne = pyogrio.read_dataframe(shp[0])
        land = unary_union(ne.geometry.values)
        land = land.simplify(LAND_SIMPLIFY, preserve_topology=True)
        polys = land.geoms if isinstance(land, MultiPolygon) else [land]
        for poly in polys:
            if poly.area < MIN_RING_AREA:
                continue
            ring = project_ring(list(poly.exterior.coords))
            if len(ring) >= 4:
                land_paths.append("M" + "L".join(f"{x} {y}" for x, y in ring) + "Z")
    print(f"land: {len(land_paths)} polygons")

    payload = {"vw": VW, "vh": VH, "years": years,
               "land": land_paths, "frames": frames}
    OUT.write_text("const MINIMAP = " + json.dumps(payload) + ";\n",
                   encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1e6:.1f} MB, {len(frames)} frames)")


if __name__ == "__main__":
    main()
