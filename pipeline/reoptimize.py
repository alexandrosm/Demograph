"""Re-run the wiggle optimizer (3 seeds), apply the best order, re-export.
Run this after any pipeline change that alters the stream name set."""
import json
import shutil
import subprocess
import sys

PY = sys.executable

# Export FIRST so wiggle.py optimizes the CURRENT stream set (a stale
# data.js would make it optimize old names and produce a mismatched order).
subprocess.run([PY, "-X", "utf8", "pipeline/export_web.py"], check=True)

for seed in (0, 1, 2):
    subprocess.run(
        [PY, "-X", "utf8", "pipeline/wiggle.py", "both", "--seed", str(seed),
         "--out", f"orders/both{seed}.json"],
        check=True,
    )
best = min(
    (f"orders/both{s}.json" for s in (0, 1, 2)),
    key=lambda p: json.load(open(p))["wiggle"],
)
d = json.load(open(best))
print(f"best: {best} ({d['wiggle']/d['baseline']:.1%} of baseline)")
shutil.copy(best, "orders/stream_order.json")
subprocess.run([PY, "-X", "utf8", "pipeline/export_web.py"], check=True)
