"""Build a deliberate region grid from Natural Earth country polygons.

Replaces the lon/lat box regions: each 5' cell gets a region id from real
country borders (Natural Earth admin-0, public domain), assigned through an
explicit, auditable country -> region table: UN subregion defaults plus
deliberate overrides where history disagrees with modern bureaucracy
(Iran/Afghanistan -> Middle East despite UN 'Southern Asia'; Mongolia ->
steppe; Russia split at the Urals ~60E into Europe/steppe). The Himalaya is
the India/East Asia boundary because the actual border polygon is. Oceania
and Antarctica stay unregioned (0) — regions are views, not a partition.

Outputs data/processed/region_grid.npy (uint8) + region_grid_audit.csv.
"""
import io
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio
from rasterio.features import rasterize
from rasterio.transform import from_origin

from compute_shares import ROOT, snap_dilate

NE_URL = "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip"
RAW_DIR = ROOT / "data" / "raw" / "naturalearth"
OUT_NPY = ROOT / "data" / "processed" / "region_grid.npy"
OUT_AUDIT = ROOT / "data" / "processed" / "region_grid_audit.csv"

REGION_IDS = {
    "indiansub": 1, "eastasia": 2, "seasia": 3, "mideast": 4, "nafrica": 5,
    "ssafrica": 6, "europe": 7, "steppe": 8, "americas": 9,
}

SUBREGION_DEFAULT = {
    "Southern Asia": "indiansub",
    "Eastern Asia": "eastasia",
    "South-Eastern Asia": "seasia",
    "Western Asia": "mideast",
    "Central Asia": "steppe",
    "Northern Africa": "nafrica",
    "Sub-Saharan Africa": "ssafrica",
    "Eastern Africa": "ssafrica", "Western Africa": "ssafrica",
    "Middle Africa": "ssafrica", "Southern Africa": "ssafrica",
    "Northern Europe": "europe", "Western Europe": "europe",
    "Southern Europe": "europe", "Eastern Europe": "europe",
    "Northern America": "americas", "Central America": "americas",
    "South America": "americas", "Caribbean": "americas",
    # Oceania subregions intentionally unmapped -> unregioned
}

# Deliberate departures from the UN scheme.
COUNTRY_OVERRIDES = {
    "Iran": "mideast",          # UN says Southern Asia; Persia is not the subcontinent
    "Afghanistan": "mideast",   # Persianate sphere; the Sulaiman line bounds India
    "Mongolia": "steppe",       # UN says Eastern Asia; the steppe heartland
    "Kazakhstan": "steppe",
    "Cyprus": "europe",
}
RUSSIA_URALS_LON = 60.0  # west of the Urals -> europe, east -> steppe


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    shp = list(RAW_DIR.glob("*.shp"))
    if not shp:
        print("downloading Natural Earth admin-0 (50m)...")
        req = urllib.request.Request(NE_URL, headers={"User-Agent": "histomap2/0.1"})
        data = urllib.request.urlopen(req, timeout=120).read()
        zipfile.ZipFile(io.BytesIO(data)).extractall(RAW_DIR)
        shp = list(RAW_DIR.glob("*.shp"))
    gdf = pyogrio.read_dataframe(shp[0])

    assignments = []
    shapes = []
    for rec in gdf.itertuples():
        name = rec.ADMIN
        sub = rec.SUBREGION
        region = COUNTRY_OVERRIDES.get(name, SUBREGION_DEFAULT.get(sub))
        assignments.append({"country": name, "subregion": sub,
                            "region": region or "(unregioned)"})
        if name == "Russia":
            continue  # handled by the Urals split below
        if region:
            shapes.append((rec.geometry, REGION_IDS[region]))

    shape = (2160, 4320)
    transform = from_origin(-180, 90, 1 / 12, 1 / 12)
    grid = rasterize(shapes, out_shape=shape, transform=transform,
                     fill=0, dtype="uint8")

    russia = gdf[gdf.ADMIN == "Russia"]
    if len(russia):
        rmask = rasterize([(g, 1) for g in russia.geometry], out_shape=shape,
                          transform=transform, fill=0, dtype="uint8") > 0
        cols = np.arange(shape[1])
        lons = -180 + (cols + 0.5) / 12
        west = np.broadcast_to(lons < RUSSIA_URALS_LON, shape)
        grid[rmask & west] = REGION_IDS["europe"]
        grid[rmask & ~west] = REGION_IDS["steppe"]

    # Cover coastal/island population cells whose centers miss the polygons.
    grid = snap_dilate(grid, 3)

    np.save(OUT_NPY, grid)
    pd.DataFrame(assignments).sort_values(["region", "country"]).to_csv(
        OUT_AUDIT, index=False)
    counts = {k: int((grid == i).sum()) for k, i in REGION_IDS.items()}
    print("cells per region:", counts)
    unreg = [a["country"] for a in assignments if a["region"] == "(unregioned)"]
    print(f"unregioned countries ({len(unreg)}):", unreg[:12], "...")
    print(f"wrote {OUT_NPY} and {OUT_AUDIT}")


if __name__ == "__main__":
    main()
