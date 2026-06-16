"""Download HYDE 3.2.1 baseline population-count grids (popc_*.asc) for the
histomap2 time slices, using HTTP range requests into the 5.3 GB DANS zip so
only the needed members (~a few hundred MB compressed) are transferred.

HYDE 3.2.1: doi:10.17026/DANS-25G-GEZ3 (DANS archaeology data station, CC0
deposit; readme states CC BY 3.0 — we attribute Klein Goldewijk et al. either way).
"""
import sys
from pathlib import Path

import zipfile_deflate64  # noqa: F401  (patches zipfile with Deflate64 support)
from remotezip import RemoteZip

BASELINE_URL = "https://archaeology.datastations.nl/api/access/datafile/5490328"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "hyde32"

# HYDE timestep labels: millennial BCE, centennial to 1700, then decadal.
SLICE_LABELS = (
    ["2000BC", "1000BC", "0AD"]
    + [f"{y}AD" for y in range(100, 1800, 100)]
    + [f"{y}AD" for y in (1750, 1800, 1850, 1900, 1950, 2000, 2015)]
)


def member_for(label: str) -> str:
    return f"baseline/asc/{label}_pop/popc_{label}.asc"


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with RemoteZip(BASELINE_URL) as z:
        by_name = {i.filename: i for i in z.infolist()}
        wanted = []
        for label in SLICE_LABELS:
            name = member_for(label)
            if name not in by_name:
                print(f"!! missing member: {name}", file=sys.stderr)
                continue
            wanted.append((label, by_name[name]))
        total = sum(i.compress_size for _, i in wanted)
        print(f"{len(wanted)} grids, {total / 1e6:.0f} MB compressed transfer")
        for label, info in wanted:
            dest = RAW_DIR / f"popc_{label}.asc"
            if dest.exists() and dest.stat().st_size == info.file_size:
                print(f"  {label}: already present, skipping")
                continue
            print(f"  {label}: {info.compress_size / 1e6:6.1f} MB -> {dest.name}")
            with z.open(info.filename) as src, open(dest, "wb") as out:
                while chunk := src.read(1 << 20):
                    out.write(chunk)
    print("done")


if __name__ == "__main__":
    main()
