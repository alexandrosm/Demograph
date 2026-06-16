"""Print the orthodox block in display order with its boundary neighbors."""
import json

js = open(r"web\data.js", encoding="utf-8").read()
d = json.loads(js[js.index("=") + 1:].rstrip().rstrip(";"))
order, regs = d["order"], d["regions"]
idxs = [i for i, n in enumerate(order) if regs.get(n) == "orthodox"]
for i in range(min(idxs) - 2, max(idxs) + 3):
    if 0 <= i < len(order):
        n = order[i]
        mark = " <-- orthodox" if regs.get(n) == "orthodox" else ""
        print(f"{i:3d} [{regs.get(n, '-'):10s}] {n}{mark}")
