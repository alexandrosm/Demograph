"""Compute per-time-slice population shares per polity.

For each slice year: select Cliopatria polity polygons valid in that year and
sum HYDE population counts inside them, as a share of world population.

Key behaviors:
- Slices between HYDE anchor years use per-cell linear interpolation of the
  two bracketing population grids (HYDE is millennial before 1 CE; without
  this, everything between 1000 BCE and 1 CE — classical Greece, Achaemenid
  Persia, Maurya India — falls between slices and never appears).
- Polities with an internal gap in their polygon records (snapshots before AND
  after the slice year, both within GAP_TOLERANCE years) are gap-filled with
  the temporally nearest snapshot. Polities are never extended beyond their
  first/last record.
- Cells claimed by several rival polities (maximal-extent borders of e.g. the
  Pala / Pratihara / Rashtrakuta tripartite struggle) have their population
  split equally among claimants instead of awarded to the smallest polity.
- Umbrella entities — Cliopatria names in parentheses like "(Mahajanapadas)" —
  only receive population in cells not claimed by any regular polity, so they
  fill unmapped territory without double-counting their members.
- Population outside any polygon becomes the explicit "Stateless & unmapped"
  residual.

Outputs data/processed/population_shares.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio
import rasterio
from rasterio import windows
from rasterio.features import geometry_mask, rasterize
from rasterio.windows import Window
from shapely.validation import make_valid

ROOT = Path(__file__).resolve().parents[1]
CLIOPATRIA = ROOT / "data" / "raw" / "cliopatria" / "cliopatria_polities_only.geojson"
HYDE_DIR = ROOT / "data" / "raw" / "hyde32"
OUT_CSV = ROOT / "data" / "processed" / "population_shares.csv"

RESIDUAL_NAME = "Stateless & unmapped"
GAP_TOLERANCE = 60  # max years to bridge an internal gap in a polity's records
SNAP_RADIUS = 2  # cells; coastal-artifact correction (see Pass 3 below)

ANCHOR_YEARS = (
    [-2000, -1000, 0]
    + list(range(100, 1800, 100))
    + [1750, 1800, 1850, 1900, 1950, 2000, 2015]
)
# Every 50 years from 950 BCE to 1700 CE (Cliopatria's polygon records
# support it; population between HYDE's millennial/century anchors is
# per-cell linear). Plus -325 for Alexander's empire (336-323 BCE), which
# falls entirely between the -400/-300 grid, and sparse early-BCE points.
INTERPOLATED_YEARS = sorted(
    set(
        # -325: Alexander alive (Cliopatria maps only Macedon proper);
        # -320: the full unified-empire polygon, which Cliopatria dates
        # -323..-319 — posthumously, under the early Diadochi.
        [-1750, -1500, -1250, -325, -320]
        + list(range(-950, 0, 50))
        + list(range(50, 1700, 50))
    )
    - set(ANCHOR_YEARS)
)
SLICE_YEARS = sorted(set(ANCHOR_YEARS) | set(INTERPOLATED_YEARS))


def anchor_label(year: int) -> str:
    return f"{-year}BC" if year < 0 else f"{year}AD"


def load_grid(year: int):
    with rasterio.open(HYDE_DIR / f"popc_{anchor_label(year)}.asc") as src:
        pop = src.read(1)
        nodata = src.nodata if src.nodata is not None else -9999
        grid = np.where(pop == nodata, 0.0, pop).astype("float64")
        return grid, src.transform


def population_for(year: int):
    """HYDE grid at an anchor year, or linear blend of the bracketing anchors."""
    if year in ANCHOR_YEARS:
        return load_grid(year)
    lo = max(a for a in ANCHOR_YEARS if a < year)
    hi = min(a for a in ANCHOR_YEARS if a > year)
    t = (year - lo) / (hi - lo)
    glo, transform = load_grid(lo)
    ghi, _ = load_grid(hi)
    return glo * (1 - t) + ghi * t, transform


def active_records(gdf: pd.DataFrame, year: int) -> pd.DataFrame:
    """Records valid at `year`, plus gap-filled nearest snapshots for polities
    with records on both sides of `year` within GAP_TOLERANCE."""
    valid = gdf[(gdf.FromYear <= year) & (gdf.ToYear >= year)]
    valid = (
        valid.sort_values("FromYear").groupby("Name", as_index=False).tail(1)
    )
    covered = set(valid.Name)
    rest = gdf[~gdf.Name.isin(covered)]
    before = rest[rest.ToYear < year]
    after = rest[rest.FromYear > year]
    fillable = set(before.Name) & set(after.Name)
    fills = []
    for name in fillable:
        recs = rest[rest.Name == name]
        prev_end = recs.ToYear[recs.ToYear < year].max()
        next_start = recs.FromYear[recs.FromYear > year].min()
        if year - prev_end > GAP_TOLERANCE or next_start - year > GAP_TOLERANCE:
            continue
        dist = np.minimum(
            np.abs(recs.FromYear - year), np.abs(recs.ToYear - year)
        )
        fills.append(recs.loc[dist.idxmin()])
    if fills:
        valid = pd.concat([valid, pd.DataFrame(fills)], ignore_index=True)
    return valid.reset_index(drop=True)


def snap_dilate(grid, radius):
    """Fill zero cells from any nonzero 8-neighbor, `radius` iterations.
    Corrects the coastal rasterization artifact (cell centers just offshore)."""
    cur = grid.copy()
    for _ in range(radius):
        base = cur.copy()
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                cand = np.roll(np.roll(base, dr, axis=0), dc, axis=1)
                fill = (cur == 0) & (cand > 0)
                cur[fill] = cand[fill]
    return cur


def window_mask(geom, transform, shape):
    """Boolean inside-mask for `geom` restricted to its bounding-box window."""
    win = windows.from_bounds(*geom.bounds, transform=transform)
    row0 = max(0, int(np.floor(win.row_off)))
    col0 = max(0, int(np.floor(win.col_off)))
    row1 = min(shape[0], int(np.ceil(win.row_off + win.height)) + 1)
    col1 = min(shape[1], int(np.ceil(win.col_off + win.width)) + 1)
    if row1 <= row0 or col1 <= col0:
        return row0, col0, np.zeros((0, 0), dtype=bool)
    wt = windows.transform(Window(col0, row0, col1 - col0, row1 - row0), transform)
    m = geometry_mask(
        [geom], out_shape=(row1 - row0, col1 - col0), transform=wt, invert=True
    )
    return row0, col0, m


def main() -> None:
    print("reading Cliopatria...")
    gdf = pyogrio.read_dataframe(CLIOPATRIA)
    gdf = gdf[gdf["Type"] == "POLITY"].copy()
    bad = ~gdf.geometry.is_valid
    if bad.any():
        print(f"fixing {bad.sum()} invalid geometries")
        gdf.loc[bad, "geometry"] = gdf.loc[bad, "geometry"].apply(make_valid)
    # Centroid per record; the web layer orders streams west->east like the
    # original chart's loose geographic layout, and classifies civilizational
    # color families from lon/lat.
    cent = gdf.geometry.centroid
    gdf["lon"] = cent.x
    gdf["lat"] = cent.y
    gdf["umbrella"] = gdf.Name.str.startswith("(")

    rows = []
    for year in SLICE_YEARS:
        pop, transform = population_for(year)
        world = pop.sum()
        active = active_records(gdf, year)
        regular = active[~active.umbrella].reset_index(drop=True)
        umbrellas = active[active.umbrella].reset_index(drop=True)

        # Pass 1: claim counts for rival-overlap splitting.
        claims = np.zeros(pop.shape, dtype=np.uint16)
        masks = []
        for geom in regular.geometry:
            r0, c0, m = window_mask(geom, transform, pop.shape)
            claims[r0 : r0 + m.shape[0], c0 : c0 + m.shape[1]] += m
            masks.append((r0, c0, m))
        weighted = np.divide(pop, claims, out=np.zeros_like(pop), where=claims > 0)

        # Pass 2: each regular polity gets contested cells / n_claimants.
        reg_tot = np.zeros(len(regular))
        for i, (r0, c0, m) in enumerate(masks):
            reg_tot[i] = weighted[r0 : r0 + m.shape[0], c0 : c0 + m.shape[1]][m].sum()

        # Umbrellas fill only territory no regular polity claims; smaller
        # umbrellas burn last and win against bigger ones.
        umb_tot = np.zeros(len(umbrellas))
        umb_label = None
        if len(umbrellas):
            umbrellas = umbrellas.sort_values("Area", ascending=False).reset_index(
                drop=True
            )
            umb_label = rasterize(
                [(g, i + 1) for i, g in enumerate(umbrellas.geometry)],
                out_shape=pop.shape,
                transform=transform,
                fill=0,
                dtype="int32",
            )
            umb_label[claims > 0] = 0
            sums = np.bincount(
                umb_label.ravel(), weights=pop.ravel(), minlength=len(umbrellas) + 1
            )
            umb_tot = sums[1 : len(umbrellas) + 1]

        # Coastal snap: populated cells whose 5' center falls just outside
        # every polygon (harbor cities, river deltas, atolls) attach to the
        # nearest mapped polity within SNAP_RADIUS cells. At 2000 CE, 98% of
        # the would-be "stateless" residual is this rasterization artifact.
        winner = np.zeros(pop.shape, dtype=np.int32)
        if umb_label is not None:
            winner = np.where(umb_label > 0, umb_label + len(regular), 0)
        for i in np.argsort(-regular.Area.values):  # smallest burns last, wins
            r0, c0, m = masks[i]
            win = winner[r0 : r0 + m.shape[0], c0 : c0 + m.shape[1]]
            win[m] = i + 1
        cur = snap_dilate(winner, SNAP_RADIUS)
        snap_cells = (winner == 0) & (cur > 0) & (pop > 0)
        snap_sums = np.bincount(
            cur[snap_cells],
            weights=pop[snap_cells],
            minlength=len(regular) + len(umbrellas) + 1,
        )
        reg_tot += snap_sums[1 : len(regular) + 1]
        umb_tot += snap_sums[len(regular) + 1 :]

        assigned = reg_tot.sum() + umb_tot.sum()
        for frame, totals in ((regular, reg_tot), (umbrellas, umb_tot)):
            for rec, p in zip(frame.itertuples(), totals):
                if p > 0:
                    rows.append(
                        {
                            "year": year,
                            "name": rec.Name,
                            "wikidata": rec.Wikidata,
                            "lon": rec.lon,
                            "lat": rec.lat,
                            "population": p,
                            "share": p / world,
                        }
                    )

        rows.append(
            {
                "year": year,
                "name": RESIDUAL_NAME,
                "wikidata": "",
                "lon": 200.0,  # sorts east of everything -> right edge of chart
                "lat": 0.0,
                "population": world - assigned,
                "share": (world - assigned) / world,
            }
        )
        interp = "" if year in ANCHOR_YEARS else " (interpolated pop)"
        print(
            f"{year:>6}: world={world/1e6:8.1f}M polities={len(active):3d} "
            f"assigned={assigned/world:6.1%}{interp}"
        )

    out = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)
    print(f"wrote {len(out)} rows -> {OUT_CSV}")


if __name__ == "__main__":
    main()
